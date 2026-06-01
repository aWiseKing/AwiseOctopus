from __future__ import annotations

import asyncio
import shlex
import subprocess
import sys
import uuid

import click
from openai import OpenAI
from rich.json import JSON
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from acli.model_registry import (
    fetch_provider_models,
    find_provider,
    get_active_api_key,
    get_model_providers,
    get_provider_api_key,
    infer_provider,
    save_provider_api_key,
)
from models import DAGExecutor, ThinkingAgent
from models.agent_errors import AgentOperationAbortedError, abort_message_for_user
from models.config_manager import ConfigManager
from models.interaction import create_approval_handler
from models.personas import (
    DEFAULT_PERSONA_NAME,
    list_personas,
    resolve_persona_name,
)
from models.session_store import SessionStore

from .run import _consume_run_stream, _interaction_handler


def _short_sid(sid: str | None) -> str:
    if not sid:
        return ""
    s = str(sid)
    if len(s) <= 8:
        return s
    return s[:8]


def _sync_current_session(store: SessionStore, config_mgr: ConfigManager) -> str | None:
    cfg = config_mgr.get("session_id")
    db = store.get_current()
    if cfg:
        if cfg != db:
            store.set_current(cfg)
        return cfg
    if db:
        config_mgr.set("session_id", db)
        return db
    return None


def _get_session_name(store: SessionStore, session_id: str) -> str:
    for it in store.list_sessions():
        if it.get("session_id") == session_id:
            return it.get("name") or ""
    return ""


def _build_info_content(ctx, store: SessionStore, config_mgr: ConfigManager, session_id: str, session_name: str) -> str:
    provider = infer_provider(base_url=ctx.base_url, model=ctx.model)
    provider_display = provider.name if provider else "自定义"
    persona_name = resolve_persona_name(config_manager=config_mgr)
    available_personas = list_personas()
    if persona_name in available_personas:
        persona_display = f"[green]{persona_name}[/green]"
    else:
        persona_display = f"[yellow]{persona_name}[/yellow] (未安装)"
    ws = store.get_workspace(session_id)
    if ws:
        ws_display = f"[magenta]{ws}[/magenta]"
    else:
        default_ws = config_mgr.get("default_workspace")
        if default_ws:
            ws_display = f"[magenta]{default_ws}[/magenta] (默认)"
        else:
            ws_display = "[magenta]当前目录[/magenta] (未设置)"

    return (
        f"模型: [green]{ctx.model}[/green]\n"
        f"厂商: [green]{provider_display}[/green]\n"
        f"接口: [green]{ctx.base_url}[/green]\n"
        f"人格: {persona_display}\n"
        f"会话: [green]{session_name}[/green] [cyan]{_short_sid(session_id)}[/cyan]\n"
        f"工作区: {ws_display}\n"
        f"提示: [yellow]exit 退出；/shell 切换 Shell；/chat 切回 Chat；/session 管理会话；/model 切换模型；/persona 切换人格。[/yellow]"
    )


def _create_prompt_session(
    store: SessionStore,
    session_id: str,
    prompt_session_cls,
    file_history_cls,
):
    history_path = store.get_prompt_history_path(session_id)
    return prompt_session_cls(history=file_history_cls(history_path))


def _build_agent(
    client,
    ctx,
    store: SessionStore,
    approval_handler,
    session_id: str,
    config_mgr: ConfigManager,
):
    return ThinkingAgent(
        client,
        ctx.model,
        session_id=session_id,
        session_store=store,
        interaction_handler=approval_handler,
        persona_name=resolve_persona_name(config_manager=config_mgr),
    )


def _build_provider_table() -> Table:
    table = Table(title="常见 AI 模型厂商")
    table.add_column("ID", style="bold")
    table.add_column("厂商")
    table.add_column("base_url", style="cyan")
    table.add_column("示例模型")
    for provider in get_model_providers():
        table.add_row(
            provider.id,
            provider.name,
            provider.base_url,
            ", ".join(provider.model_examples),
        )
    return table


def _build_model_table(provider_name: str, models: list[str]) -> Table:
    table = Table(title=f"{provider_name} 可用模型")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Model")
    for idx, model in enumerate(models, start=1):
        table.add_row(str(idx), model)
    return table


def _parse_model_command(prompt: str) -> list[str]:
    try:
        return shlex.split(prompt)
    except ValueError:
        return prompt.strip().split()


def _prompt_provider(console, provider_ref: str | None):
    if provider_ref:
        provider = find_provider(provider_ref)
        if provider:
            return provider
        console.print(Panel.fit(f"未知模型厂商: {provider_ref}", border_style="yellow"))

    providers = get_model_providers()
    console.print(_build_provider_table())
    choices = [provider.id for provider in providers]
    provider_id = Prompt.ask(
        "请选择模型厂商 ID",
        choices=choices,
        default=providers[0].id,
        show_choices=True,
        console=console,
    )
    return find_provider(provider_id)


def _has_model_setup(config_mgr: ConfigManager, ctx) -> bool:
    configured_base_url = config_mgr.get("base_url")
    configured_model = config_mgr.get("MODEL")
    provider = infer_provider(base_url=configured_base_url or ctx.base_url, model=configured_model or ctx.model)
    configured_api_key = get_active_api_key(provider, config_mgr, fallback_api_key=getattr(ctx, "api_key", None))
    return bool(configured_base_url and configured_model and configured_api_key)


def _run_first_use_model_setup(ctx, console, config_mgr: ConfigManager) -> None:
    console.print(
        Panel.fit(
            "首次使用前需要配置 AI 模型。之后可随时用 /model switch 切换。",
            title="模型初始化",
            border_style="cyan",
        )
    )
    provider = _prompt_provider(console, None)
    if provider is None:
        return

    recorded_base_url = config_mgr.get("base_url")
    default_base_url = (
        recorded_base_url
        if recorded_base_url and infer_provider(base_url=recorded_base_url, model=None) == provider
        else provider.base_url
    )
    base_url = Prompt.ask(
        "请输入 base_url，直接回车使用系统记录的厂商接口",
        default=default_base_url,
        show_default=True,
        console=console,
    ).strip()
    if not base_url:
        base_url = default_base_url

    recorded_model = config_mgr.get("MODEL")
    default_model = recorded_model or provider.default_model
    model = Prompt.ask(
        "请输入模型名称",
        default=default_model,
        show_default=True,
        console=console,
    ).strip()
    if not model:
        model = default_model

    api_key = get_active_api_key(provider, config_mgr, fallback_api_key=getattr(ctx, "api_key", None))
    if api_key:
        console.print(f"[green]已读取 {provider.name} 已保存的 API Key。[/green]")
    else:
        api_key = Prompt.ask(
            f"请输入 {provider.name} API Key",
            password=True,
            console=console,
        ).strip()

    ctx.base_url = base_url
    ctx.model = model
    ctx.api_key = api_key
    config_mgr.set("base_url", base_url)
    config_mgr.set("MODEL", model)
    config_mgr.set("api_key", api_key)
    save_provider_api_key(provider, config_mgr, api_key)
    console.print(Panel.fit(f"已完成模型配置: {provider.name} / {model}", border_style="green"))


def _ensure_provider_api_key(ctx, console, config_mgr: ConfigManager, provider) -> str:
    api_key = get_provider_api_key(provider, config_mgr)
    if api_key:
        return api_key

    api_key = Prompt.ask(
        f"请输入 {provider.name} API Key",
        password=True,
        console=console,
    )
    save_provider_api_key(provider, config_mgr, api_key)
    config_mgr.set("api_key", api_key)
    ctx.api_key = api_key
    return api_key


def _ensure_current_model_api_key(ctx, console, config_mgr: ConfigManager) -> str:
    provider = infer_provider(base_url=ctx.base_url, model=ctx.model)
    api_key = get_active_api_key(provider, config_mgr, fallback_api_key=getattr(ctx, "api_key", None))
    if api_key:
        ctx.api_key = api_key
        return api_key
    if provider:
        return _ensure_provider_api_key(ctx, console, config_mgr, provider)
    api_key = Prompt.ask("请输入 api_key", password=True, console=console)
    config_mgr.set("api_key", api_key)
    ctx.api_key = api_key
    return api_key


def _select_model(console, provider, api_key: str, explicit_model: str | None) -> str | None:
    if explicit_model:
        return explicit_model

    models: list[str] = []
    try:
        models = fetch_provider_models(provider, api_key)
    except Exception as e:
        console.print(
            Panel.fit(
                f"自动拉取模型列表失败：{e}\n已改用内置示例模型。",
                border_style="yellow",
            )
        )

    if not models:
        models = list(provider.model_examples)

    displayed_models = models[:50]
    console.print(_build_model_table(provider.name, displayed_models))
    answer = Prompt.ask(
        "请选择模型序号或输入模型名",
        default=provider.default_model if provider.default_model in displayed_models else displayed_models[0],
        console=console,
    ).strip()
    if not answer:
        return None
    if answer.isdigit():
        idx = int(answer)
        if 1 <= idx <= len(displayed_models):
            return displayed_models[idx - 1]
        console.print(Panel.fit(f"模型序号超出范围: {answer}", border_style="yellow"))
        return None
    return answer


def _apply_model_switch(ctx, config_mgr: ConfigManager, provider, model: str, api_key: str) -> OpenAI:
    ctx.base_url = provider.base_url
    ctx.model = model
    ctx.api_key = api_key
    config_mgr.set("base_url", provider.base_url)
    config_mgr.set("MODEL", model)
    config_mgr.set("api_key", api_key)
    save_provider_api_key(provider, config_mgr, api_key)
    return OpenAI(api_key=api_key, base_url=provider.base_url)


@click.command("chat")
@click.pass_obj
def chat(ctx) -> None:
    console = ctx.console
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import (
            ExecutableCompleter,
            merge_completers,
            WordCompleter,
        )
        from prompt_toolkit.formatted_text import HTML
        from prompt_toolkit.history import FileHistory
    except ModuleNotFoundError as e:
        raise click.ClickException(
            "缺少依赖 prompt_toolkit，无法使用 chat 子命令。请安装 prompt_toolkit 后重试。"
        ) from e
    from rich.align import Align

    config_mgr = ConfigManager()
    if sys.stdin.isatty() and not _has_model_setup(config_mgr, ctx):
        _run_first_use_model_setup(ctx, console, config_mgr)

    awise_header = "\n".join(
        [
            "[bold white]Awise[/bold white][bold magenta]Octopus[/bold magenta] [bright_black]//[/bright_black] [bold cyan]Agent Command Deck[/bold cyan] [bright_black]v0.1[/bright_black]",
            "[bright_cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bright_cyan]",
            "[magenta]◆[/magenta] [cyan]Thinking Core[/cyan]  [bright_black]·[/bright_black]  [magenta]◆[/magenta] [cyan]DAG Executor[/cyan]  [bright_black]·[/bright_black]  [magenta]◆[/magenta] [cyan]Session Memory[/cyan]",
        ]
    )
    api_key = ctx.api_key or "missing-api-key"
    client = OpenAI(api_key=api_key, base_url=ctx.base_url)
    store = SessionStore()

    session_id = _sync_current_session(store, config_mgr)
    if not session_id:
        session_id = str(uuid.uuid4())
        store.create_session(session_id, name=None)
        store.set_current(session_id)
        config_mgr.set("session_id", session_id)

    session_name = _get_session_name(store, session_id)
    info_content = _build_info_content(ctx, store, config_mgr, session_id, session_name)
    content = f"{awise_header}\n\n{info_content}"
    console.print(
        Panel(
            content,
            title="[bold cyan]AwiseOctopus[/bold cyan]",
            subtitle="[bright_black]ready[/bright_black]",
            border_style="bright_cyan",
            expand=True,
        )
    )

    approval_handler = create_approval_handler(
        lambda request: _interaction_handler(console, request),
        session_id=session_id,
    )
    agent = _build_agent(client, ctx, store, approval_handler, session_id, config_mgr)

    current_mode = "chat"

    built_in_completer = WordCompleter(
        [
            "/shell",
            "/chat",
            "/session",
            "/model",
            "/persona",
            "/persona list",
            "/persona current",
            "/persona use",
            "/model switch",
            "/model list",
            "/model fetch",
            *[f"/persona use {persona_name}" for persona_name in list_personas()],
            *[f"/model switch {provider.id}" for provider in get_model_providers()],
            "exit",
        ],
        ignore_case=True,
    )
    system_completer = ExecutableCompleter()
    chat_mode_completer = built_in_completer
    shell_mode_completer = merge_completers([built_in_completer, system_completer])

    session = _create_prompt_session(store, session_id, PromptSession, FileHistory)

    while True:
        if current_mode == "chat":
            console.print("\n[red]*[/red] 请输入问题 (当前: Chat):")
            active_completer = chat_mode_completer
        else:
            console.print("\n[red]*[/red] 请输入命令 (当前: Shell):")
            active_completer = shell_mode_completer
            
        try:
            prompt = session.prompt(
                HTML("<ansicyan>&gt; </ansicyan>"),
                completer=active_completer,
                complete_while_typing=True
            ).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not prompt:
            continue
        if prompt.lower() == "exit":
            break
        
        if prompt == "/shell":
            current_mode = "shell"
            console.print("[green]已切换到 Shell 模式[/green]")
            continue
        elif prompt == "/chat":
            current_mode = "chat"
            console.print("[green]已切换到 Chat 模式[/green]")
            continue
        elif current_mode == "chat" and prompt.startswith("/session"):
            parts = prompt.strip().split()
            sub = parts[1] if len(parts) >= 2 else ""

            if sub in ("list", "ls"):
                items = store.list_sessions()
                if not items:
                    console.print(Panel.fit("暂无 session。", border_style="yellow"))
                    continue
                table = Table(title="Sessions")
                table.add_column("*", justify="center")
                table.add_column("Name", style="bold")
                table.add_column("Session ID", style="cyan")
                table.add_column("Updated", style="green")
                table.add_column("Msgs", justify="right")
                table.add_column("Workspace", style="magenta")
                for it in items:
                    star = "*" if it.get("is_current") else ""
                    name = it.get("name") or ""
                    sid = it.get("session_id") or ""
                    updated = it.get("updated_at") or ""
                    msgs = str(it.get("message_count") or 0)
                    ws = it.get("workspace") or ""
                    table.add_row(star, name, sid, updated, msgs, ws)
                console.print(table)
                continue

            if sub in ("current", "cur"):
                sid = _sync_current_session(store, config_mgr)
                if not sid:
                    console.print(Panel.fit("当前未选择 session。", border_style="yellow"))
                    continue
                name = _get_session_name(store, sid)
                ws = store.get_workspace(sid) or ""
                console.print(
                    Panel.fit(
                        f"name: {name}\nsession_id: {sid}\nshort: {_short_sid(sid)}\nworkspace: {ws}",
                        title="当前 Session",
                        border_style="cyan",
                    )
                )
                continue

            if sub == "new":
                name = parts[2] if len(parts) >= 3 else None
                sid = str(uuid.uuid4())
                store.create_session(sid, name=name)
                store.set_current(sid)
                config_mgr.set("session_id", sid)
                session_id = sid
                session_name = _get_session_name(store, session_id)
                approval_handler = create_approval_handler(
                    lambda request: _interaction_handler(console, request),
                    session_id=session_id,
                )
                agent = _build_agent(
                    client, ctx, store, approval_handler, session_id, config_mgr
                )
                session = _create_prompt_session(store, session_id, PromptSession, FileHistory)
                info_content = _build_info_content(ctx, store, config_mgr, session_id, session_name)
                console.print(Panel.fit(f"已创建并切换到 session: {sid}", border_style="green"))
                continue

            if sub == "use":
                if len(parts) < 3:
                    console.print(Panel.fit("用法: /session use <name|session_id>", border_style="yellow"))
                    continue
                ref = parts[2]
                sid = store.resolve_session(ref)
                if not sid:
                    sid = ref.strip()
                    store.create_session(sid, name=None)
                store.set_current(sid)
                config_mgr.set("session_id", sid)
                session_id = sid
                session_name = _get_session_name(store, session_id)
                approval_handler = create_approval_handler(
                    lambda request: _interaction_handler(console, request),
                    session_id=session_id,
                )
                agent = _build_agent(
                    client, ctx, store, approval_handler, session_id, config_mgr
                )
                session = _create_prompt_session(store, session_id, PromptSession, FileHistory)
                info_content = _build_info_content(ctx, store, config_mgr, session_id, session_name)
                console.print(Panel.fit(f"已切换到 session: {sid}", border_style="green"))
                continue

            if sub == "workspace":
                if len(parts) >= 3:
                    import os
                    new_ws = os.path.abspath(parts[2])
                    store.set_workspace(session_id, new_ws)
                    console.print(Panel.fit(f"已将当前 session 的工作区设置为: {new_ws}", border_style="green"))
                    # Update info content
                    info_content = _build_info_content(ctx, store, config_mgr, session_id, session_name)
                    # Recreate agent to pick up the new workspace limit in system prompt
                    agent = _build_agent(
                        client, ctx, store, approval_handler, session_id, config_mgr
                    )
                else:
                    ws = store.get_workspace(session_id)
                    if ws:
                        console.print(Panel.fit(f"当前 session 的工作区是: {ws}", border_style="cyan"))
                    else:
                        console.print(Panel.fit("当前 session 未设置专属工作区。", border_style="yellow"))
                continue

            console.print(
                Panel.fit(
                    "用法: /session list | /session current | /session new [name] | /session use <name|session_id> | /session workspace [path]",
                    border_style="yellow",
                )
            )
            continue

        elif current_mode == "chat" and prompt.startswith("/persona"):
            parts = prompt.strip().split()
            sub = parts[1] if len(parts) >= 2 else ""

            if sub in ("", "help"):
                console.print(
                    Panel.fit(
                        "用法: /persona list | /persona current | /persona use <name>\n"
                        f"默认人格: {DEFAULT_PERSONA_NAME}",
                        title="人格命令",
                        border_style="cyan",
                    )
                )
                continue

            if sub in ("list", "ls"):
                personas = list_personas()
                if not personas:
                    console.print(Panel.fit("当前没有可用人格目录。", border_style="yellow"))
                    continue
                table = Table(title="可用人格")
                table.add_column("Persona", style="bold")
                current_persona = resolve_persona_name(config_manager=config_mgr)
                for persona_name in personas:
                    label = f"{persona_name} (当前)" if persona_name == current_persona else persona_name
                    table.add_row(label)
                console.print(table)
                continue

            if sub in ("current", "cur"):
                current_persona = resolve_persona_name(config_manager=config_mgr)
                console.print(
                    Panel.fit(
                        f"当前人格: {current_persona}",
                        title="人格信息",
                        border_style="cyan",
                    )
                )
                continue

            if sub == "use":
                if len(parts) < 3:
                    console.print(Panel.fit("用法: /persona use <name>", border_style="yellow"))
                    continue
                persona_name = parts[2].strip()
                personas = list_personas()
                if persona_name not in personas:
                    available = ", ".join(personas) if personas else "无"
                    console.print(
                        Panel.fit(
                            f"未知人格: {persona_name}\n可用人格: {available}",
                            border_style="yellow",
                        )
                    )
                    continue
                config_mgr.set("persona_name", persona_name)
                agent = _build_agent(
                    client, ctx, store, approval_handler, session_id, config_mgr
                )
                info_content = _build_info_content(
                    ctx, store, config_mgr, session_id, session_name
                )
                console.print(
                    Panel.fit(f"已切换人格: {persona_name}", border_style="green")
                )
                continue

            console.print(
                Panel.fit(
                    "用法: /persona list | /persona current | /persona use <name>",
                    border_style="yellow",
                )
            )
            continue

        elif current_mode == "chat" and prompt.startswith("/model"):
            parts = _parse_model_command(prompt)
            sub = parts[1] if len(parts) >= 2 else ""

            if sub in ("", "help"):
                console.print(
                    Panel.fit(
                        "用法: /model list | /model fetch <provider> | /model switch [provider] [model]\n"
                        "示例: /model switch deepseek deepseek-chat\n"
                        "未提供 model 时会自动拉取该厂商模型列表供选择。",
                        title="模型命令",
                        border_style="cyan",
                    )
                )
                continue

            if sub in ("list", "ls", "providers"):
                console.print(_build_provider_table())
                continue

            if sub == "fetch":
                provider = _prompt_provider(console, parts[2] if len(parts) >= 3 else None)
                if provider is None:
                    continue
                api_key = _ensure_provider_api_key(ctx, console, config_mgr, provider)
                try:
                    models = fetch_provider_models(provider, api_key)
                except Exception as e:
                    console.print(Panel.fit(f"拉取模型列表失败：{e}", border_style="red"))
                    continue
                if not models:
                    console.print(Panel.fit("该接口未返回模型列表。", border_style="yellow"))
                    continue
                console.print(_build_model_table(provider.name, models[:100]))
                continue

            if sub == "switch":
                provider = _prompt_provider(console, parts[2] if len(parts) >= 3 else None)
                if provider is None:
                    continue
                api_key = _ensure_provider_api_key(ctx, console, config_mgr, provider)
                selected_model = _select_model(
                    console,
                    provider,
                    api_key,
                    parts[3] if len(parts) >= 4 else None,
                )
                if not selected_model:
                    continue
                client = _apply_model_switch(ctx, config_mgr, provider, selected_model, api_key)
                agent = _build_agent(
                    client, ctx, store, approval_handler, session_id, config_mgr
                )
                info_content = _build_info_content(ctx, store, config_mgr, session_id, session_name)
                console.print(
                    Panel.fit(
                        f"已切换模型: {provider.name} / {selected_model}",
                        border_style="green",
                    )
                )
                continue

            console.print(
                Panel.fit(
                    "用法: /model list | /model fetch <provider> | /model switch [provider] [model]",
                    border_style="yellow",
                )
            )
            continue

        if current_mode == "shell":
            try:
                if sys.platform == "win32":
                    result = subprocess.run(["powershell", "-Command", prompt], capture_output=True, text=True, errors="replace")
                else:
                    result = subprocess.run(prompt, shell=True, capture_output=True, text=True, errors="replace")
                
                output = result.stdout.strip()
                if result.stderr.strip():
                    output += ("\n" if output else "") + result.stderr.strip()
                if not output:
                    output = "（执行成功，无输出）"
                console.print(Panel(output, title="[bold cyan]Shell 执行结果[/bold cyan]", border_style="cyan", expand=True))
            except Exception as e:
                console.print(Panel(f"执行命令时出错: {e}", title="[bold red]错误[/bold red]", border_style="red", expand=True))
        else:
            try:
                api_key = _ensure_current_model_api_key(ctx, console, config_mgr)
                client = OpenAI(api_key=api_key, base_url=ctx.base_url)
                agent = _build_agent(
                    client, ctx, store, approval_handler, session_id, config_mgr
                )
                payload = _consume_run_stream(console, agent.run_stream(prompt), allow_interaction=True)

                if isinstance(payload, list):
                    console.rule("DAG 调度执行")
                    executor = DAGExecutor(
                        payload,
                        client,
                        ctx.model,
                        agent,
                        interaction_handler=approval_handler,
                    )
                    results = asyncio.run(executor.execute())
                    console.print(Panel(JSON.from_data(results), title="[bold cyan]DAG 最终执行结果[/bold cyan]", border_style="cyan", expand=True))

                    summary_text = ""
                    with Live(Panel(summary_text, title="[bold cyan]最终总结[/bold cyan]", border_style="cyan", expand=True), console=console, refresh_per_second=10) as live:
                        for chunk in agent.summarize_dag_results_stream(prompt, results):
                            summary_text += chunk
                            live.update(Panel(summary_text, title="[bold cyan]最终总结[/bold cyan]", border_style="cyan", expand=True))
                else:
                    console.print(Panel(str(payload), title="[bold cyan]最终答案[/bold cyan]", border_style="cyan", expand=True))
            except AgentOperationAbortedError as e:
                console.print(
                    Panel.fit(
                        abort_message_for_user(e),
                        title="[bold yellow]Agent 已中止[/bold yellow]",
                        border_style="yellow",
                    )
                )
                console.print(
                    Panel.fit("已返回对话输入状态，可继续输入新指令。", border_style="cyan")
                )
                continue

        console.print(
            Panel(
                info_content,
                title="[bold cyan]AwiseOctopus[/bold cyan]",
                border_style="cyan",
                expand=True,
            )
        )
