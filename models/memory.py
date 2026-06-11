from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

from .runtime_paths import user_data_path

try:
    import chromadb
except ImportError:
    chromadb = None


MEMORY_MODES = {"experience", "short_term", "long_term"}
MODE_ALIASES = {
    "short": "short_term",
    "long": "long_term",
    "experience": "experience",
    "short_term": "short_term",
    "long_term": "long_term",
}


def normalize_memory_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    normalized = MODE_ALIASES.get(str(mode).strip())
    if normalized not in MEMORY_MODES:
        raise ValueError("mode must be one of: short, long, experience")
    return normalized


class MemoryManager:
    _instance = None
    _SQLITE_TIMEOUT_SECONDS = 30.0
    _COMMIT_RETRY_ATTEMPTS = 5

    @staticmethod
    def _resolve_paths(
        db_path: str | None = None,
        chroma_path: str | None = None,
    ) -> tuple[str, str]:
        resolved_db_path = (
            str(user_data_path("experience.db"))
            if db_path is None
            else os.path.abspath(os.path.expanduser(db_path))
        )
        resolved_chroma_path = (
            str(user_data_path("experience_vector", create_parent=False))
            if chroma_path is None
            else os.path.abspath(os.path.expanduser(chroma_path))
        )
        return resolved_db_path, resolved_chroma_path

    def __new__(cls, db_path: str | None = None, chroma_path: str | None = None):
        resolved_db_path, resolved_chroma_path = cls._resolve_paths(db_path, chroma_path)
        current_key = getattr(cls._instance, "_path_key", None) if cls._instance is not None else None
        if cls._instance is None or current_key != (resolved_db_path, resolved_chroma_path):
            cls._instance = super(MemoryManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | None = None, chroma_path: str | None = None):
        resolved_db_path, resolved_chroma_path = self._resolve_paths(db_path, chroma_path)
        if self._initialized:
            return

        self._initialized = True
        self._path_key = (resolved_db_path, resolved_chroma_path)
        self.db_path = resolved_db_path
        self.chroma_path = resolved_chroma_path
        self._lock = threading.RLock()

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.chroma_path, exist_ok=True)

        self.conn = sqlite3.connect(
            self.db_path,
            timeout=self._SQLITE_TIMEOUT_SECONDS,
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self._configure_connection()
        self._create_schema()
        self._migrate_schema()

        if chromadb:
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(name="agent_experiences")
            self.memory_collection = self.chroma_client.get_or_create_collection(name="agent_memories")
        else:
            self.chroma_client = None
            self.collection = None
            self.memory_collection = None

    def _configure_connection(self) -> None:
        timeout_ms = int(self._SQLITE_TIMEOUT_SECONDS * 1000)
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA busy_timeout = {timeout_ms}")
        try:
            cur.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        cur.execute("PRAGMA synchronous = NORMAL")

    def _commit(self) -> None:
        delay = 0.05
        for attempt in range(self._COMMIT_RETRY_ATTEMPTS):
            try:
                self.conn.commit()
                return
            except sqlite3.OperationalError as exc:
                if "database is locked" not in str(exc).lower() or attempt == self._COMMIT_RETRY_ATTEMPTS - 1:
                    raise
                time.sleep(delay)
                delay *= 2

    def _now(self) -> str:
        return datetime.datetime.now().isoformat()

    def _create_schema(self) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS experiences (
                    id TEXT PRIMARY KEY,
                    task_type TEXT,
                    instruction TEXT,
                    process_log TEXT,
                    result TEXT,
                    success_score REAL,
                    weight REAL,
                    created_at TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    mode TEXT,
                    scope TEXT,
                    session_id TEXT,
                    task_type TEXT,
                    content TEXT,
                    summary TEXT,
                    metadata_json TEXT,
                    confidence REAL,
                    importance REAL,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    last_used_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS session_memory_state (
                    session_id TEXT PRIMARY KEY,
                    summary_memory_id TEXT,
                    last_message_count INTEGER DEFAULT 0,
                    working_set_memory_id TEXT,
                    updated_at TEXT
                )
                """
            )
            self._commit()

    def _migrate_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(experiences)")
        experience_cols = {row[1] for row in cur.fetchall() if row and len(row) > 1}
        if "session_id" not in experience_cols:
            cur.execute("ALTER TABLE experiences ADD COLUMN session_id TEXT")

        cur.execute("PRAGMA table_info(memories)")
        memory_cols = {row[1] for row in cur.fetchall() if row and len(row) > 1}
        expected = {
            "mode": "TEXT",
            "scope": "TEXT",
            "session_id": "TEXT",
            "task_type": "TEXT",
            "content": "TEXT",
            "summary": "TEXT",
            "metadata_json": "TEXT",
            "confidence": "REAL",
            "importance": "REAL",
            "created_at": "TEXT",
            "updated_at": "TEXT",
            "expires_at": "TEXT",
            "last_used_at": "TEXT",
        }
        for col, col_type in expected.items():
            if col not in memory_cols:
                cur.execute(f"ALTER TABLE memories ADD COLUMN {col} {col_type}")

        cur.execute("PRAGMA table_info(session_memory_state)")
        state_cols = {row[1] for row in cur.fetchall() if row and len(row) > 1}
        state_expected = {
            "summary_memory_id": "TEXT",
            "last_message_count": "INTEGER DEFAULT 0",
            "working_set_memory_id": "TEXT",
            "updated_at": "TEXT",
        }
        for col, col_type in state_expected.items():
            if col not in state_cols:
                cur.execute(f"ALTER TABLE session_memory_state ADD COLUMN {col} {col_type}")

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_experiences_task_session_time
            ON experiences(task_type, session_id, created_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_mode_scope_session_time
            ON memories(mode, scope, session_id, updated_at)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_mode_importance
            ON memories(mode, importance, updated_at)
            """
        )
        self._commit()
        self._migrate_legacy_experiences_to_memories()

    def _migrate_legacy_experiences_to_memories(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, task_type, instruction, process_log, result, weight,
                   created_at, session_id
            FROM experiences
            WHERE id NOT IN (SELECT id FROM memories)
            """
        )
        rows = cur.fetchall()
        for row in rows:
            created_at = row["created_at"] or self._now()
            content = (
                f"任务: {row['instruction']}\n"
                f"过程: {row['process_log']}\n"
                f"结果: {row['result']}\n"
                f"得分: {row['weight']}"
            )
            cur.execute(
                """
                INSERT OR IGNORE INTO memories (
                    id, mode, scope, session_id, task_type, content, summary,
                    metadata_json, confidence, importance, created_at, updated_at,
                    expires_at, last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    "experience",
                    "task_experience",
                    row["session_id"],
                    row["task_type"],
                    content,
                    row["instruction"],
                    self._metadata_json(
                        {
                            "legacy_experience_id": row["id"],
                            "process_log": row["process_log"],
                            "result": row["result"],
                        }
                    ),
                    1.0,
                    float(row["weight"] or 0.0),
                    created_at,
                    created_at,
                    None,
                    None,
                ),
            )
        self._commit()

    def _metadata_json(self, metadata: dict[str, Any] | None) -> str:
        return json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)

    def _row_to_memory(self, row: sqlite3.Row | tuple | None) -> dict[str, Any] | None:
        if row is None:
            return None
        obj = dict(row)
        raw = obj.get("metadata_json")
        try:
            obj["metadata"] = json.loads(raw) if raw else {}
        except Exception:
            obj["metadata"] = {}
        return obj

    def _memory_document(self, *, content: str, summary: str | None) -> str:
        return (summary or content or "").strip()

    def _chroma_metadata(self, memory: dict[str, Any]) -> dict[str, str | int | float | bool]:
        metadata: dict[str, str | int | float | bool] = {
            "mode": str(memory.get("mode") or ""),
            "scope": str(memory.get("scope") or ""),
        }
        for key in ("session_id", "task_type"):
            value = memory.get(key)
            if value is not None:
                metadata[key] = str(value)
        return metadata

    def _add_or_update_vector(self, memory: dict[str, Any]) -> None:
        if not self.memory_collection:
            return
        document = self._memory_document(
            content=str(memory.get("content") or ""),
            summary=memory.get("summary"),
        )
        if not document:
            return
        metadata = self._chroma_metadata(memory)
        try:
            self.memory_collection.upsert(
                documents=[document],
                metadatas=[metadata],
                ids=[memory["id"]],
            )
        except AttributeError:
            self.memory_collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[memory["id"]],
            )

    def _delete_vector(self, memory_id: str) -> None:
        if not self.memory_collection:
            return
        try:
            self.memory_collection.delete(ids=[memory_id])
        except Exception:
            pass

    def add_memory(
        self,
        *,
        mode: str,
        scope: str,
        content: str,
        summary: str | None = None,
        session_id: str | None = None,
        task_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: float = 1.0,
        importance: float = 0.5,
        expires_at: str | None = None,
        memory_id: str | None = None,
    ) -> str:
        with self._lock:
            mode = normalize_memory_mode(mode) or mode
            if not scope:
                raise ValueError("scope is required")
            content = str(content or "").strip()
            if not content:
                raise ValueError("content is required")

            now = self._now()
            mid = memory_id or str(uuid.uuid4())
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO memories (
                    id, mode, scope, session_id, task_type, content, summary,
                    metadata_json, confidence, importance, created_at, updated_at,
                    expires_at, last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    mode,
                    scope,
                    session_id,
                    task_type,
                    content,
                    summary,
                    self._metadata_json(metadata),
                    float(confidence),
                    float(importance),
                    now,
                    now,
                    expires_at,
                    None,
                ),
            )
            self._commit()
            memory = self.get_memory(mid)
            if memory:
                self._add_or_update_vector(memory)
            return mid

    def update_memory(self, memory_id: str, **fields: Any) -> bool:
        with self._lock:
            allowed = {
                "scope",
                "session_id",
                "task_type",
                "content",
                "summary",
                "confidence",
                "importance",
                "expires_at",
                "last_used_at",
            }
            updates: list[str] = []
            values: list[Any] = []
            for key, value in fields.items():
                if key == "metadata":
                    updates.append("metadata_json = ?")
                    values.append(self._metadata_json(value))
                elif key in allowed:
                    updates.append(f"{key} = ?")
                    values.append(value)
            if not updates:
                return False
            updates.append("updated_at = ?")
            values.append(self._now())
            values.append(memory_id)
            cur = self.conn.cursor()
            cur.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", values)
            self._commit()
            if cur.rowcount:
                memory = self.get_memory(memory_id)
                if memory:
                    self._add_or_update_vector(memory)
                return True
            return False

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM memories WHERE id = ? LIMIT 1", (memory_id,))
            return self._row_to_memory(cur.fetchone())

    def list_memories(
        self,
        *,
        mode: str | None = None,
        session_id: str | None = None,
        scope: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self._lock:
            mode = normalize_memory_mode(mode) if mode else None
            clauses = []
            values: list[Any] = []
            if mode:
                clauses.append("mode = ?")
                values.append(mode)
            if session_id is not None:
                clauses.append("session_id = ?")
                values.append(session_id)
            if scope is not None:
                clauses.append("scope = ?")
                values.append(scope)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            values.append(max(1, int(limit)))
            cur = self.conn.cursor()
            cur.execute(
                f"""
                SELECT * FROM memories
                {where}
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                values,
            )
            return [self._row_to_memory(row) for row in cur.fetchall()]

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            self._commit()
            if cur.rowcount:
                self._delete_vector(memory_id)
                return True
            return False

    def clear_memories(
        self,
        *,
        mode: str | None = None,
        session_id: str | None = None,
    ) -> int:
        with self._lock:
            mode = normalize_memory_mode(mode) if mode else None
            memories = self.list_memories(mode=mode, session_id=session_id, limit=100000)
            for memory in memories:
                self._delete_vector(memory["id"])
            clauses = []
            values: list[Any] = []
            if mode:
                clauses.append("mode = ?")
                values.append(mode)
            if session_id is not None:
                clauses.append("session_id = ?")
                values.append(session_id)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            cur = self.conn.cursor()
            cur.execute(f"DELETE FROM memories {where}", values)
            self._commit()
            return int(cur.rowcount or 0)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT mode, COUNT(*) FROM memories GROUP BY mode")
            counts = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute("SELECT COUNT(*) FROM experiences")
            legacy_count = int(cur.fetchone()[0])
            return {
                "memories": {
                    "shortTerm": counts.get("short_term", 0),
                    "longTerm": counts.get("long_term", 0),
                    "experience": counts.get("experience", 0),
                },
                "legacyExperiences": legacy_count,
                "dbPath": self.db_path,
                "chromaPath": self.chroma_path,
                "vectorEnabled": bool(self.memory_collection),
            }

    def add_experience(
        self,
        task_type: str,
        instruction: str,
        process_log: Any,
        result: Any,
        success_score: float,
        session_id: str | None = None,
    ) -> str:
        with self._lock:
            exp_id = str(uuid.uuid4())
            created_at = self._now()
            weight = float(success_score)
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO experiences (
                    id, task_type, instruction, process_log, result, success_score,
                    weight, created_at, session_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp_id,
                    task_type,
                    instruction,
                    str(process_log),
                    str(result),
                    float(success_score),
                    weight,
                    created_at,
                    session_id,
                ),
            )
            self._commit()

            if self.collection:
                metadata: dict[str, str] = {"task_type": str(task_type)}
                if session_id is not None:
                    metadata["session_id"] = str(session_id)
                self.collection.add(
                    documents=[str(instruction)],
                    metadatas=[metadata],
                    ids=[exp_id],
                )

            content = (
                f"任务: {instruction}\n"
                f"过程: {process_log}\n"
                f"结果: {result}\n"
                f"得分: {success_score}"
            )
            try:
                self.add_memory(
                    mode="experience",
                    scope="task_experience",
                    session_id=session_id,
                    task_type=task_type,
                    content=content,
                    summary=str(instruction),
                    memory_id=exp_id,
                    metadata={
                        "legacy_experience_id": exp_id,
                        "process_log": str(process_log),
                        "result": str(result),
                    },
                    confidence=1.0,
                    importance=weight,
                )
            except Exception:
                pass
            return exp_id

    def _legacy_experience_rows(
        self,
        *,
        task_type: str,
        exp_ids: list[str] | None = None,
        session_id: str | None = None,
        limit: int = 6,
    ) -> list[sqlite3.Row]:
        with self._lock:
            cur = self.conn.cursor()
            if exp_ids:
                placeholders = ",".join("?" for _ in exp_ids)
                cur.execute(
                    f"""
                    SELECT id, instruction, process_log, result, weight
                    FROM experiences
                    WHERE id IN ({placeholders})
                    ORDER BY weight DESC
                    """,
                    exp_ids,
                )
                return cur.fetchall()

            clauses = ["task_type = ?"]
            values: list[Any] = [task_type]
            if session_id is not None:
                clauses.append("session_id = ?")
                values.append(session_id)
            values.append(max(1, int(limit)))
            cur.execute(
                f"""
                SELECT id, instruction, process_log, result, weight
                FROM experiences
                WHERE {' AND '.join(clauses)}
                ORDER BY weight DESC, created_at DESC
                LIMIT ?
                """,
                values,
            )
            return cur.fetchall()

    def search_experience(
        self,
        task_type: str,
        instruction: str,
        top_k: int = 3,
        session_id: str | None = None,
    ) -> str:
        rows: list[sqlite3.Row] = []
        if self.collection:
            where_conditions: list[dict[str, str]] = [{"task_type": str(task_type)}]
            if session_id is not None:
                where_conditions.append({"session_id": str(session_id)})
            where = {"$and": where_conditions} if len(where_conditions) > 1 else where_conditions[0]
            results = self.collection.query(
                query_texts=[str(instruction)],
                n_results=top_k * 2,
                where=where,
            )
            exp_ids: list[str] = []
            if results.get("ids") and results["ids"][0]:
                if results.get("distances"):
                    for i, distance in enumerate(results["distances"][0]):
                        if distance <= 0.38:
                            exp_ids.append(results["ids"][0][i])
                else:
                    exp_ids = list(results["ids"][0])
            if exp_ids:
                rows = self._legacy_experience_rows(task_type=task_type, exp_ids=exp_ids)

        if not rows:
            rows = self._legacy_experience_rows(
                task_type=task_type,
                session_id=session_id,
                limit=top_k * 2,
            )
        return self.format_experience_rows(rows, top_k=top_k)

    def format_experience_rows(self, rows: list[sqlite3.Row], top_k: int = 3) -> str:
        successful_exps = []
        failed_exps = []
        for row in rows:
            exp = {
                "instruction": row["instruction"],
                "process_log": row["process_log"],
                "result": row["result"],
                "weight": row["weight"],
            }
            if float(exp["weight"] or 0) >= 0.6:
                if len(successful_exps) < top_k:
                    successful_exps.append(exp)
            else:
                if len(failed_exps) < top_k:
                    failed_exps.append(exp)

        if not successful_exps and not failed_exps:
            return ""

        hint = "【历史经验参考】\n针对类似的任务，系统有以下经验记录：\n"
        if successful_exps:
            hint += "\n成功的做法（高分经验）：\n"
            for i, exp in enumerate(successful_exps, 1):
                hint += f"  {i}. 任务: {exp['instruction']}\n     过程: {exp['process_log']}\n     结果: {exp['result']}\n"
        if failed_exps:
            hint += "\n失败的做法（请避免这些错误）：\n"
            for i, exp in enumerate(failed_exps, 1):
                hint += f"  {i}. 任务: {exp['instruction']}\n     过程: {exp['process_log']}\n     结果: {exp['result']}\n"
        return hint

    def search_memories(
        self,
        *,
        mode: str,
        query: str,
        session_id: str | None = None,
        task_type: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        with self._lock:
            mode = normalize_memory_mode(mode) or mode
            memory_ids: list[str] = []
            if self.memory_collection:
                where_conditions: list[dict[str, str]] = [{"mode": mode}]
                if session_id is not None:
                    where_conditions.append({"session_id": str(session_id)})
                if task_type is not None:
                    where_conditions.append({"task_type": str(task_type)})
                where = {"$and": where_conditions} if len(where_conditions) > 1 else where_conditions[0]
                try:
                    results = self.memory_collection.query(
                        query_texts=[str(query or "")],
                        n_results=max(1, int(top_k)),
                        where=where,
                    )
                    if results.get("ids") and results["ids"][0]:
                        memory_ids = list(results["ids"][0])
                except Exception:
                    memory_ids = []

            memories: list[dict[str, Any]] = []
            if memory_ids:
                placeholders = ",".join("?" for _ in memory_ids)
                cur = self.conn.cursor()
                cur.execute(
                    f"SELECT * FROM memories WHERE id IN ({placeholders})",
                    memory_ids,
                )
                by_id = {row["id"]: self._row_to_memory(row) for row in cur.fetchall()}
                memories = [by_id[mid] for mid in memory_ids if by_id.get(mid)]
            else:
                memories = self.list_memories(
                    mode=mode,
                    session_id=session_id,
                    limit=top_k,
                )
            now = self._now()
            for memory in memories:
                self.update_memory(memory["id"], last_used_at=now)
            return memories

    def upsert_session_summary(
        self,
        *,
        session_id: str,
        content: str,
        message_count: int,
    ) -> str:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT summary_memory_id FROM session_memory_state WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            memory_id = row["summary_memory_id"] if row and row["summary_memory_id"] else None
            if memory_id and self.update_memory(
                memory_id,
                content=content,
                summary=content[:240],
                confidence=1.0,
                importance=0.8,
            ):
                mid = memory_id
            else:
                mid = self.add_memory(
                    mode="short_term",
                    scope="session_summary",
                    session_id=session_id,
                    content=content,
                    summary=content[:240],
                    confidence=1.0,
                    importance=0.8,
                )
            cur.execute(
                """
                INSERT INTO session_memory_state (
                    session_id, summary_memory_id, last_message_count, updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary_memory_id = excluded.summary_memory_id,
                    last_message_count = excluded.last_message_count,
                    updated_at = excluded.updated_at
                """,
                (session_id, mid, int(message_count), self._now()),
            )
            self._commit()
            return mid

    def upsert_task_working_set(
        self,
        *,
        session_id: str | None,
        task_type: str,
        content: str,
        status: str = "active",
    ) -> str | None:
        with self._lock:
            if not session_id or not content:
                return None
            cur = self.conn.cursor()
            cur.execute(
                "SELECT working_set_memory_id FROM session_memory_state WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            memory_id = row["working_set_memory_id"] if row and row["working_set_memory_id"] else None
            metadata = {"status": status}
            if memory_id and self.update_memory(
                memory_id,
                content=content,
                summary=content[:240],
                task_type=task_type,
                metadata=metadata,
                confidence=1.0,
                importance=0.9,
            ):
                mid = memory_id
            else:
                mid = self.add_memory(
                    mode="short_term",
                    scope="task_working_set",
                    session_id=session_id,
                    task_type=task_type,
                    content=content,
                    summary=content[:240],
                    metadata=metadata,
                    confidence=1.0,
                    importance=0.9,
                )
            cur.execute(
                """
                INSERT INTO session_memory_state (
                    session_id, working_set_memory_id, updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    working_set_memory_id = excluded.working_set_memory_id,
                    updated_at = excluded.updated_at
                """,
                (session_id, mid, self._now()),
            )
            self._commit()
            return mid

    def build_memory_context(
        self,
        agent_role: str,
        user_request: str,
        session_id: str | None = None,
        *,
        max_chars: int = 6000,
    ) -> str:
        sections: list[str] = []
        if session_id:
            task_items = self.list_memories(
                mode="short_term",
                session_id=session_id,
                scope="task_working_set",
                limit=2,
            )
            if task_items:
                sections.append(
                    "【短期记忆：当前任务工作集】\n"
                    + "\n".join(f"- {item['content']}" for item in task_items)
                )

            summaries = self.list_memories(
                mode="short_term",
                session_id=session_id,
                scope="session_summary",
                limit=1,
            )
            if summaries:
                sections.append(
                    "【短期记忆：当前会话摘要】\n"
                    + "\n".join(f"- {item['content']}" for item in summaries)
                )

        long_items = self.search_memories(
            mode="long_term",
            query=user_request,
            top_k=4,
        )
        if long_items:
            sections.append(
                "【长期记忆：跨会话相关事实】\n"
                + "\n".join(f"- {item['content']}" for item in long_items)
            )

        experience = self.search_experience(
            agent_role,
            user_request,
            session_id=session_id,
        )
        if experience:
            sections.append(experience)

        context = "\n\n".join(section for section in sections if section.strip())
        if len(context) > max_chars:
            context = context[:max_chars].rstrip() + "\n...(记忆上下文已截断)"
        return context

    def close(self) -> None:
        with self._lock:
            try:
                self.conn.close()
            except Exception:
                pass
            self._initialized = False
            type(self)._instance = None


def memory_to_api(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": memory.get("id"),
        "mode": memory.get("mode"),
        "scope": memory.get("scope"),
        "sessionId": memory.get("session_id"),
        "taskType": memory.get("task_type"),
        "content": memory.get("content"),
        "summary": memory.get("summary"),
        "metadata": memory.get("metadata") or {},
        "confidence": memory.get("confidence"),
        "importance": memory.get("importance"),
        "createdAt": memory.get("created_at"),
        "updatedAt": memory.get("updated_at"),
        "expiresAt": memory.get("expires_at"),
        "lastUsedAt": memory.get("last_used_at"),
    }
