from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import click
from openai import OpenAI
from rich.json import JSON
from rich.panel import Panel
from rich.prompt import Prompt

from models import DAGExecutor, ThinkingAgent
from models.config_manager import ConfigManager
from models.interaction import create_approval_handler
from models.session_store import SessionStore


def _interaction_handler(console, request: dict) -> str:
    console.print(
        Panel.fit(
            f"Agent 准备执行高危操作：{request['tool_name']}",
            title="确认高危操作",
            border_style="red",
        )
    )
    console.print(JSON.from_data(request["args"]))
    if request["is_delete_operation"]:
        console.print(
            "\n[yellow]提示：这是删除类操作。即使选择 `session`，也只会同意当前这一次，不会开启会话默认同意。[/yellow]"
        )
    console.print(
        "\n[red]*[/red] 请选择授权方式：`session` / `only` / `no` (默认: no)"
    )
    return Prompt.ask(
        "[bold cyan]>[/bold cyan]",
        choices=["session", "only", "no"],
        default="no",
        show_choices=False,
        console=console,
    )


def _ensure_api_key(ctx) -> str:
    if getattr(ctx, "api_key", None):
        return ctx.api_key
    if not sys.stdin.isatty():
        api_key = (sys.stdin.readline() or "").strip()
    else:
        api_key = Prompt.ask("请输入 api_key", password=True)
    ctx.api_key = api_key
    return api_key


def _consume_run_stream(console, gen, *, allow_interaction: bool):
    user_input_to_send = None
    while True:
        try:
            if user_input_to_send is not None:
                status, payload = gen.send(user_input_to_send)
                user_input_to_send = None
            else:
                status, payload = next(gen)
        except StopIteration as e:
            return e.value

        if status == "RUNNING":
            console.print(str(payload), style="dim")
            continue

        if status == "ASK_USER":
            console.print(
                Panel.fit(str(payload), title="Agent 求助", border_style="yellow")
            )
            if not allow_interaction:
                raise click.ClickException(
                    "Agent 需要用户输入，但当前为非交互模式。请改用 `chat` 或在交互终端中运行。"
                )
            console.print("\n[red]*[/red] 请输入回复:")
            user_input_to_send = console.input("[bold cyan]>[/bold cyan] ")
            continue

        if status == "FINISHED":
            return payload

        raise click.ClickException(f"未知状态: {status}")


def _read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        raise click.ClickException("--prompt 与 --prompt-file 只能二选一")

    if prompt_file:
        p = Path(prompt_file)
        return p.read_text(encoding="utf-8")

    if prompt is not None:
        return prompt

    if not sys.stdin.isatty():
        return sys.stdin.read()

    raise click.ClickException("未提供输入。请使用 --prompt / --prompt-file 或通过 stdin 传入。")


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


@click.command("run")
@click.option("--prompt", default=None)
@click.option("--prompt-file", type=click.Path(dir_okay=False, exists=True), default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--session", "session_ref", default=None)
@click.pass_obj
def run(
    ctx,
    prompt: str | None,
    prompt_file: str | None,
    dry_run: bool,
    session_ref: str | None,
) -> None:
    console = ctx.console
    text = _read_prompt(prompt, prompt_file).strip()
    if not text:
        raise click.ClickException("输入为空。")

    config_mgr = ConfigManager()
    store = SessionStore()

    session_id = None
    if session_ref:
        session_id = store.resolve_session(session_ref)
        if not session_id:
            session_id = session_ref.strip()
            store.create_session(session_id, name=None)
        store.set_current(session_id)
        config_mgr.set("session_id", session_id)
    else:
        session_id = _sync_current_session(store, config_mgr)
        if not session_id:
            session_id = str(uuid.uuid4())
            store.create_session(session_id, name=None)
            store.set_current(session_id)
            config_mgr.set("session_id", session_id)

    if dry_run:
        _ensure_api_key(ctx)
        console.print(
            Panel.fit(
                f"base_url: {ctx.base_url}\nmodel: {ctx.model}\nsession_id: {session_id}\nchars: {len(text)}",
                title="配置校验通过（dry-run）",
                border_style="green",
            )
        )
        return

    api_key = _ensure_api_key(ctx)
    client = OpenAI(api_key=api_key, base_url=ctx.base_url)
    approval_handler = create_approval_handler(
        lambda request: _interaction_handler(console, request),
        session_id=session_id,
    )
    agent = ThinkingAgent(
        client,
        ctx.model,
        session_id=session_id,
        session_store=store,
        interaction_handler=approval_handler,
    )
    payload = _consume_run_stream(console, agent.run_stream(text), allow_interaction=sys.stdin.isatty())

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
        console.print(Panel.fit("DAG 最终执行结果", border_style="cyan"))
        console.print(JSON.from_data(results))

        console.rule("最终总结")
        for chunk in agent.summarize_dag_results_stream(text, results):
            console.print(chunk, end="")
        console.print()
        return

    console.print(Panel.fit(str(payload), title="最终答案", border_style="cyan"))
