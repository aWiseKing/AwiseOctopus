import click
from rich.table import Table

from acli.model_registry import get_model_providers
from models.config_manager import ConfigManager


DEFAULT_CONFIG_KEYS = (
    (
        "api_key",
        "LLM 服务 API Key；也可通过同名系统环境变量提供。",
        "无",
    ),
    (
        "base_url",
        "OpenAI 兼容接口地址。",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    (
        "MODEL",
        "默认模型名称。",
        "glm-5",
    ),
    (
        "persona_name",
        "当前启用的人格目录名；Agent 会从对应人格目录读取 system prompt。",
        "GongnengLove",
    ),
    (
        "default_workspace",
        "默认工作目录；未指定 session 工作目录时使用。",
        "无",
    ),
    (
        "session_id",
        "当前会话 ID；通常由 chat/run/session 命令自动维护。",
        "自动生成",
    ),
)


@click.group()
def env():
    """管理环境变量配置 (基于 SQLite)"""
    pass


def _print_default_config_keys(console):
    table = Table(title="系统默认设置键")
    table.add_column("Key", style="bold")
    table.add_column("说明")
    table.add_column("默认值", style="cyan")

    for key, description, default_value in DEFAULT_CONFIG_KEYS:
        table.add_row(key, description, default_value)

    console.print(table)

    provider_table = Table(title="常见 AI 模型厂商 base_url")
    provider_table.add_column("厂商", style="bold")
    provider_table.add_column("base_url", style="cyan")
    provider_table.add_column("API Key 配置键")
    provider_table.add_column("示例模型")

    for provider in get_model_providers():
        provider_table.add_row(
            provider.name,
            provider.base_url,
            provider.api_key_config_key,
            ", ".join(provider.model_examples),
        )

    console.print(provider_table)


@env.command("set")
@click.option(
    "-l",
    "--list-defaults",
    is_flag=True,
    help="显示系统默认设置键的名称及解释。",
)
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.pass_obj
def set_env(ctx_obj, list_defaults: bool, key: str | None, value: str | None):
    """设置环境变量"""
    if list_defaults:
        _print_default_config_keys(ctx_obj.console)
        return

    if key is None or value is None:
        raise click.UsageError("缺少参数 KEY 或 VALUE。查看默认设置键请使用：env set -l")

    config_mgr = ConfigManager()
    config_mgr.set(key, value)
    ctx_obj.console.print(f"[green][成功] 已设置环境变量[/green] [bold]{key}[/bold] = [cyan]{value}[/cyan]")

@env.command("get")
@click.argument("key")
@click.pass_obj
def get_env(ctx_obj, key: str):
    """获取环境变量"""
    config_mgr = ConfigManager()
    value = config_mgr.get(key)
    if value is not None:
        ctx_obj.console.print(f"[bold]{key}[/bold] = [cyan]{value}[/cyan]")
    else:
        ctx_obj.console.print(f"[yellow][警告] 未找到环境变量[/yellow] [bold]{key}[/bold]")

@env.command("list")
@click.pass_obj
def list_env(ctx_obj):
    """列出所有环境变量"""
    config_mgr = ConfigManager()
    all_configs = config_mgr.get_all()
    
    if not all_configs:
        ctx_obj.console.print("[yellow][警告] 当前没有任何环境变量配置。[/yellow]")
        return
        
    table = Table(title="环境变量配置")
    table.add_column("Key", style="bold")
    table.add_column("Value", style="cyan")
    
    for k, v in all_configs.items():
        table.add_row(k, v)
        
    ctx_obj.console.print(table)

@env.command("delete")
@click.argument("key")
@click.pass_obj
def delete_env(ctx_obj, key: str):
    """删除环境变量"""
    config_mgr = ConfigManager()
    if config_mgr.get(key) is not None:
        config_mgr.delete(key)
        ctx_obj.console.print(f"[green][成功] 已删除环境变量[/green] [bold]{key}[/bold]")
    else:
        ctx_obj.console.print(f"[yellow][警告] 未找到环境变量[/yellow] [bold]{key}[/bold]")
