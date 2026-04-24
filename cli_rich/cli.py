from __future__ import annotations

import os

import click
from rich.console import Console
from rich.traceback import install

from models.config_manager import ConfigManager
from . import __version__
from .commands.chat import chat
from .commands.run import run
from .commands.env import env
from .commands.session import session


class AppContext:
    def __init__(
        self, console: Console, api_key: str | None, base_url: str, model: str
    ):
        self.console = console
        self.api_key = api_key
        self.base_url = base_url
        self.model = model


def _resolve_config(
    *,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> tuple[str | None, str, str]:
    config_mgr = ConfigManager()

    resolved_api_key = api_key or config_mgr.get("api_key") or os.getenv("api_key")

    resolved_base_url = (
        base_url
        or config_mgr.get("base_url")
        or os.getenv("base_url")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    resolved_model = model or config_mgr.get("MODEL") or os.getenv("MODEL") or "glm-5"
    return resolved_api_key, resolved_base_url, resolved_model


@click.group()
@click.option("--no-color", is_flag=True, default=False)
@click.option("--api-key", default=None)
@click.option("--base-url", default=None)
@click.option("--model", default=None)
@click.version_option(__version__, "--version", prog_name="cli_rich")
@click.pass_context
def main(
    ctx: click.Context,
    no_color: bool,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> None:
    install(show_locals=False)
    console = Console(no_color=no_color)
    resolved_api_key, resolved_base_url, resolved_model = _resolve_config(
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    ctx.obj = AppContext(console, resolved_api_key, resolved_base_url, resolved_model)


main.add_command(chat)
main.add_command(run)
main.add_command(env)
main.add_command(session)

