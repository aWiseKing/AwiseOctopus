import click
from rich.table import Table

from models.config_manager import ConfigManager

@click.group()
def env():
    """管理环境变量配置 (基于 SQLite)"""
    pass

@env.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_obj
def set_env(ctx_obj, key: str, value: str):
    """设置环境变量"""
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
