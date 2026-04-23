from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from openai import OpenAI
from rich.json import JSON
from rich.panel import Panel
from rich.prompt import Prompt

from models import DAGExecutor, ThinkingAgent


def _interaction_handler(console, tool_name: str, args: dict) -> str:
    console.print(
        Panel.fit(
            f"Agent 准备执行高危操作：{tool_name}",
            title="确认高危操作",
            border_style="red",
        )
    )
    console.print(JSON.from_data(args))
    return Prompt.ask("是否允许？输入 y 允许，或输入修改建议/拒绝原因", default="n")


def _ensure_api_key(ctx) -> str:
    if getattr(ctx, "api_key", None):
        return ctx.api_key
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
            user_input_to_send = Prompt.ask("请输入回复")
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


@click.command("run")
@click.option("--prompt", default=None)
@click.option("--prompt-file", type=click.Path(dir_okay=False, exists=True), default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.pass_obj
def run(ctx, prompt: str | None, prompt_file: str | None, dry_run: bool) -> None:
    console = ctx.console
    text = _read_prompt(prompt, prompt_file).strip()
    if not text:
        raise click.ClickException("输入为空。")

    if dry_run:
        _ensure_api_key(ctx)
        console.print(
            Panel.fit(
                f"base_url: {ctx.base_url}\nmodel: {ctx.model}\nchars: {len(text)}",
                title="配置校验通过（dry-run）",
                border_style="green",
            )
        )
        return

    api_key = _ensure_api_key(ctx)
    client = OpenAI(api_key=api_key, base_url=ctx.base_url)
    agent = ThinkingAgent(client, ctx.model)
    payload = _consume_run_stream(console, agent.run_stream(text), allow_interaction=sys.stdin.isatty())

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
        console.print(Panel.fit("DAG 最终执行结果", border_style="cyan"))
        console.print(JSON.from_data(results))

        console.rule("最终总结")
        for chunk in agent.summarize_dag_results_stream(text, results):
            console.print(chunk, end="")
        console.print()
        return

    console.print(Panel.fit(str(payload), title="最终答案", border_style="cyan"))
