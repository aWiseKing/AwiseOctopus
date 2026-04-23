from __future__ import annotations

import asyncio

import click
from openai import OpenAI
from rich.json import JSON
from rich.panel import Panel
from rich.prompt import Prompt

from models import DAGExecutor, ThinkingAgent

from .run import _consume_run_stream, _ensure_api_key, _interaction_handler


@click.command("chat")
@click.pass_obj
def chat(ctx) -> None:
    console = ctx.console
    console.print(
        Panel.fit(
            f"model: {ctx.model}\nbase_url: {ctx.base_url}\n输入 exit 退出。",
            title="AwiseOctopus",
            border_style="cyan",
        )
    )

    api_key = _ensure_api_key(ctx)
    client = OpenAI(api_key=api_key, base_url=ctx.base_url)
    agent = ThinkingAgent(client, ctx.model)

    while True:
        prompt = Prompt.ask("请输入问题", default="").strip()
        if not prompt:
            continue
        if prompt.lower() == "exit":
            break

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
            console.print(Panel.fit("DAG 最终执行结果", border_style="cyan"))
            console.print(JSON.from_data(results))

            console.rule("最终总结")
            for chunk in agent.summarize_dag_results_stream(prompt, results):
                console.print(chunk, end="")
            console.print()
        else:
            console.print(Panel.fit(str(payload), title="最终答案", border_style="cyan"))

        console.rule()
