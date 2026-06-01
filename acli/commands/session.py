from __future__ import annotations

import uuid

import click
from rich.panel import Panel
from rich.table import Table

from models.config_manager import ConfigManager
from models.session_store import SessionStore


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


@click.group("session")
def session():
    """管理与切换会话 session"""
    pass


@session.command("list")
@click.pass_obj
def list_sessions(ctx) -> None:
    store = SessionStore()
    config_mgr = ConfigManager()
    _sync_current_session(store, config_mgr)

    items = store.list_sessions()
    if not items:
        ctx.console.print(Panel.fit("暂无 session。可使用 `awiseoctopus session new --use` 创建。", border_style="yellow"))
        return

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

    ctx.console.print(table)


@session.command("workspace")
@click.argument("path", required=False)
@click.option("--session-id", help="指定 session ID。不传则使用当前 session")
@click.pass_obj
def set_session_workspace(ctx, path: str | None, session_id: str | None):
    """查看或设置会话的专属工作区"""
    store = SessionStore()
    config_mgr = ConfigManager()
    
    target_id = session_id or _sync_current_session(store, config_mgr)
    if not target_id:
        ctx.console.print("[red][错误] 当前无可用 session，请先创建或指定 --session-id。[/red]")
        return
        
    resolved = store.resolve_session(target_id)
    if not resolved:
        ctx.console.print(f"[red][错误] 找不到指定的 session: {target_id}[/red]")
        return

    if path is None:
        # 查看
        ws = store.get_workspace(resolved)
        if ws:
            ctx.console.print(f"[green]Session {resolved} 的工作区是:[/green] {ws}")
        else:
            ctx.console.print(f"[yellow]Session {resolved} 当前未设置专属工作区。[/yellow]")
    else:
        import os
        abs_path = os.path.abspath(path)
        store.set_workspace(resolved, abs_path)
        ctx.console.print(f"[green][成功] 已将 Session {resolved} 的工作区设置为:[/green] {abs_path}")


@session.command("current")
@click.pass_obj
def current(ctx) -> None:
    store = SessionStore()
    config_mgr = ConfigManager()
    sid = _sync_current_session(store, config_mgr)
    if not sid:
        ctx.console.print(Panel.fit("当前未选择 session。", border_style="yellow"))
        return

    resolved = store.resolve_session(sid) or sid
    name = ""
    ws = ""
    for it in store.list_sessions():
        if it.get("session_id") == resolved:
            name = it.get("name") or ""
            ws = it.get("workspace") or ""
            break

    title = "当前 Session"
    body = f"name: {name}\nsession_id: {resolved}\nshort: {_short_sid(resolved)}\nworkspace: {ws}"
    ctx.console.print(Panel.fit(body, title=title, border_style="cyan"))


@session.command("new")
@click.option("--name", default=None)
@click.option("--use", "use_after", is_flag=True, default=False)
@click.pass_obj
def new_session(ctx, name: str | None, use_after: bool) -> None:
    store = SessionStore()
    config_mgr = ConfigManager()

    sid = str(uuid.uuid4())
    store.create_session(sid, name=name)

    if use_after:
        config_mgr.set("session_id", sid)
        store.set_current(sid)

    msg = f"已创建 session\nname: {name or ''}\nsession_id: {sid}\nshort: {_short_sid(sid)}"
    if use_after:
        msg += "\n已设为当前 session"
    ctx.console.print(Panel.fit(msg, border_style="green"))


@session.command("use")
@click.argument("ref")
@click.pass_obj
def use_session(ctx, ref: str) -> None:
    store = SessionStore()
    config_mgr = ConfigManager()

    sid = store.resolve_session(ref)
    if not sid:
        if ref:
            sid = ref.strip()
            store.create_session(sid, name=None)
        else:
            raise click.ClickException("ref 不能为空。")

    config_mgr.set("session_id", sid)
    store.set_current(sid)
    ctx.console.print(Panel.fit(f"已切换到 session: {sid}", border_style="green"))

