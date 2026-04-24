from __future__ import annotations

import asyncio
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

from models import DAGExecutor, ThinkingAgent
from models.config_manager import ConfigManager
from models.session_store import SessionStore

from .run import _consume_run_stream, _ensure_api_key, _interaction_handler


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
        from prompt_toolkit.history import InMemoryHistory
    except ModuleNotFoundError as e:
        raise click.ClickException(
            "缺少依赖 prompt_toolkit，无法使用 chat 子命令。请安装 prompt_toolkit 后重试。"
        ) from e
    from rich.align import Align

    config_mgr = ConfigManager()

    sword_shield_art = r"""
        />_________________________________
[########[]_________________________________>
        \>

       |`-._/\_.-`|
       |    ||    |
       |___o()o___|
       |__((<>))__|
       \   o\/o   /
        \   ||   /
         \  ||  /
          '.||.'
"""
    api_key = _ensure_api_key(ctx)
    client = OpenAI(api_key=api_key, base_url=ctx.base_url)
    store = SessionStore()

    session_id = _sync_current_session(store, config_mgr)
    if not session_id:
        session_id = str(uuid.uuid4())
        store.create_session(session_id, name=None)
        store.set_current(session_id)
        config_mgr.set("session_id", session_id)

    session_name = _get_session_name(store, session_id)
    info_content = (
        f"模型: [green]{ctx.model}[/green]\n"
        f"接口: [green]{ctx.base_url}[/green]\n"
        f"会话: [green]{session_name}[/green] [cyan]{_short_sid(session_id)}[/cyan]\n"
        f"提示: [yellow]exit 退出；/shell 切换 Shell；/chat 切回 Chat；/session 管理会话。[/yellow]"
    )
    content = f"[bold cyan]{sword_shield_art}[/bold cyan]\n{info_content}"
    console.print(Panel(content, title="[bold cyan]AwiseOctopus[/bold cyan]", border_style="cyan", expand=True))

    agent = ThinkingAgent(
        client,
        ctx.model,
        session_id=session_id,
        session_store=store,
        interaction_handler=lambda tool_name, args: _interaction_handler(
            console, tool_name, args
        ),
    )

    current_mode = "chat"

    built_in_completer = WordCompleter(
        ["/shell", "/chat", "/session", "exit"], ignore_case=True
    )
    system_completer = ExecutableCompleter()
    chat_mode_completer = built_in_completer
    shell_mode_completer = merge_completers([built_in_completer, system_completer])

    session = PromptSession(history=InMemoryHistory())

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
                for it in items:
                    star = "*" if it.get("is_current") else ""
                    name = it.get("name") or ""
                    sid = it.get("session_id") or ""
                    updated = it.get("updated_at") or ""
                    msgs = str(it.get("message_count") or 0)
                    table.add_row(star, name, sid, updated, msgs)
                console.print(table)
                continue

            if sub in ("current", "cur"):
                sid = _sync_current_session(store, config_mgr)
                if not sid:
                    console.print(Panel.fit("当前未选择 session。", border_style="yellow"))
                    continue
                name = _get_session_name(store, sid)
                console.print(
                    Panel.fit(
                        f"name: {name}\nsession_id: {sid}\nshort: {_short_sid(sid)}",
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
                agent = ThinkingAgent(
                    client,
                    ctx.model,
                    session_id=session_id,
                    session_store=store,
                    interaction_handler=lambda tool_name, args: _interaction_handler(
                        console, tool_name, args
                    ),
                )
                info_content = (
                    f"模型: [green]{ctx.model}[/green]\n"
                    f"接口: [green]{ctx.base_url}[/green]\n"
                    f"会话: [green]{session_name}[/green] [cyan]{_short_sid(session_id)}[/cyan]\n"
                    f"提示: [yellow]exit 退出；/shell 切换 Shell；/chat 切回 Chat；/session 管理会话。[/yellow]"
                )
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
                agent = ThinkingAgent(
                    client,
                    ctx.model,
                    session_id=session_id,
                    session_store=store,
                    interaction_handler=lambda tool_name, args: _interaction_handler(
                        console, tool_name, args
                    ),
                )
                info_content = (
                    f"模型: [green]{ctx.model}[/green]\n"
                    f"接口: [green]{ctx.base_url}[/green]\n"
                    f"会话: [green]{session_name}[/green] [cyan]{_short_sid(session_id)}[/cyan]\n"
                    f"提示: [yellow]exit 退出；/shell 切换 Shell；/chat 切回 Chat；/session 管理会话。[/yellow]"
                )
                console.print(Panel.fit(f"已切换到 session: {sid}", border_style="green"))
                continue

            console.print(
                Panel.fit(
                    "用法: /session list | /session current | /session new [name] | /session use <name|session_id>",
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
            payload = _consume_run_stream(console, agent.run_stream(prompt), allow_interaction=True)

            if isinstance(payload, list):
                console.rule("DAG 调度执行")
                executor = DAGExecutor(
                    payload,
                    client,
                    ctx.model,
                    agent,
                    interaction_handler=lambda tool_name, args: _interaction_handler(
                        console, tool_name, args
                    ),
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

        console.print(
            Panel(
                info_content,
                title="[bold cyan]AwiseOctopus[/bold cyan]",
                border_style="cyan",
                expand=True,
            )
        )
