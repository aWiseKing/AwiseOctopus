from __future__ import annotations

import asyncio
import subprocess
import sys

import click
from openai import OpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import ExecutableCompleter, merge_completers, WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from rich.json import JSON
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt

from models import DAGExecutor, ThinkingAgent

from .run import _consume_run_stream, _ensure_api_key, _interaction_handler


@click.command("chat")
@click.pass_obj
def chat(ctx) -> None:
    console = ctx.console
    from rich.align import Align

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
    info_content = (
        f"模型: [green]{ctx.model}[/green]\n"
        f"接口: [green]{ctx.base_url}[/green]\n"
        f"提示: [yellow]输入 exit 退出，输入 /shell 切换到命令行模式，输入 /chat 切换回聊天模式。[/yellow]"
    )
    content = (
        f"[bold cyan]{sword_shield_art}[/bold cyan]\n"
        f"{info_content}"
    )
    console.print(
        Panel(
            content,
            title="[bold cyan]AwiseOctopus[/bold cyan]",
            border_style="cyan",
            expand=True,
        )
    )

    api_key = _ensure_api_key(ctx)
    client = OpenAI(api_key=api_key, base_url=ctx.base_url)
    agent = ThinkingAgent(
        client,
        ctx.model,
        interaction_handler=lambda tool_name, args: _interaction_handler(
            console, tool_name, args
        ),
    )

    current_mode = "chat"

    built_in_completer = WordCompleter(["/shell", "/chat", "exit"], ignore_case=True)
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
