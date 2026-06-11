from __future__ import annotations

import click
from rich.panel import Panel
from rich.table import Table

from models.memory import MemoryManager, memory_to_api, normalize_memory_mode
from models.session_store import SessionStore


def _resolve_session(session_ref: str | None) -> str | None:
    if not session_ref:
        return None
    store = SessionStore()
    try:
        return store.resolve_session(session_ref) or session_ref
    finally:
        store.close()


@click.group("memory")
def memory():
    """管理多模式记忆"""
    pass


@memory.command("list")
@click.option("--mode", default=None, help="short / long / experience")
@click.option("--session", "session_ref", default=None, help="session ID 或名称")
@click.option("--limit", default=20, type=int)
@click.pass_obj
def list_memories(ctx, mode: str | None, session_ref: str | None, limit: int) -> None:
    manager = MemoryManager()
    try:
        normalized_mode = normalize_memory_mode(mode) if mode else None
        session_id = _resolve_session(session_ref)
        items = manager.list_memories(
            mode=normalized_mode,
            session_id=session_id,
            limit=limit,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        manager.close()

    if not items:
        ctx.console.print(Panel.fit("暂无匹配记忆。", border_style="yellow"))
        return

    table = Table(title="Memories")
    table.add_column("ID", style="cyan")
    table.add_column("Mode", style="green")
    table.add_column("Scope", style="magenta")
    table.add_column("Session")
    table.add_column("Importance", justify="right")
    table.add_column("Summary")
    for item in items:
        table.add_row(
            item.get("id", "")[:8],
            item.get("mode") or "",
            item.get("scope") or "",
            item.get("session_id") or "",
            f"{float(item.get('importance') or 0):.2f}",
            item.get("summary") or str(item.get("content") or "")[:80],
        )
    ctx.console.print(table)


@memory.command("show")
@click.argument("memory_id")
@click.pass_obj
def show_memory(ctx, memory_id: str) -> None:
    manager = MemoryManager()
    try:
        item = manager.get_memory(memory_id)
    finally:
        manager.close()
    if not item:
        raise click.ClickException(f"找不到记忆: {memory_id}")
    data = memory_to_api(item)
    body = "\n".join(f"{key}: {value}" for key, value in data.items())
    ctx.console.print(Panel.fit(body, title=f"Memory {memory_id}", border_style="cyan"))


@memory.command("delete")
@click.argument("memory_id")
@click.pass_obj
def delete_memory(ctx, memory_id: str) -> None:
    manager = MemoryManager()
    try:
        deleted = manager.delete_memory(memory_id)
    finally:
        manager.close()
    if not deleted:
        raise click.ClickException(f"找不到记忆: {memory_id}")
    ctx.console.print(Panel.fit(f"已删除记忆: {memory_id}", border_style="green"))


@memory.command("clear")
@click.option("--mode", default=None, help="short / long / experience")
@click.option("--session", "session_ref", default=None, help="session ID 或名称")
@click.pass_obj
def clear_memories(ctx, mode: str | None, session_ref: str | None) -> None:
    manager = MemoryManager()
    try:
        normalized_mode = normalize_memory_mode(mode) if mode else None
        session_id = _resolve_session(session_ref)
        count = manager.clear_memories(mode=normalized_mode, session_id=session_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        manager.close()
    ctx.console.print(Panel.fit(f"已清理 {count} 条记忆。", border_style="green"))


@memory.command("stats")
@click.pass_obj
def memory_stats(ctx) -> None:
    manager = MemoryManager()
    try:
        stats = manager.stats()
    finally:
        manager.close()
    body = (
        f"short_term: {stats['memories']['shortTerm']}\n"
        f"long_term: {stats['memories']['longTerm']}\n"
        f"experience: {stats['memories']['experience']}\n"
        f"legacy_experiences: {stats['legacyExperiences']}\n"
        f"vector_enabled: {stats['vectorEnabled']}\n"
        f"db: {stats['dbPath']}\n"
        f"vector: {stats['chromaPath']}"
    )
    ctx.console.print(Panel.fit(body, title="Memory Stats", border_style="cyan"))
