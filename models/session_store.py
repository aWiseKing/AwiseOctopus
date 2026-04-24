import os
import json
import sqlite3
import datetime
import threading


class SessionStore:
    def __init__(self, db_path="data/session.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.ensure_schema()

    def _now(self) -> str:
        return datetime.datetime.now().isoformat()

    def ensure_schema(self) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    updated_at TEXT,
                    meta_json TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    idx INTEGER,
                    message_json TEXT,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session_idx
                ON messages(session_id, idx)
                """
            )
            cur.execute("PRAGMA table_info(sessions)")
            existing_cols = {row[1] for row in cur.fetchall() if row and len(row) > 1}

            if "name" not in existing_cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN name TEXT")
            if "is_current" not in existing_cols:
                cur.execute("ALTER TABLE sessions ADD COLUMN is_current INTEGER DEFAULT 0")

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_name_unique
                ON sessions(name)
                """
            )
            self.conn.commit()

    def _ensure_session_row(self, session_id: str) -> None:
        now = self._now()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at, meta_json, name, is_current)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, now, now, None, None, 0),
        )
        cur.execute(
            """
            UPDATE sessions
            SET updated_at = ?
            WHERE session_id = ?
            """,
            (now, session_id),
        )

    def create_session(self, session_id: str, name: str | None = None) -> None:
        now = self._now()
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at, meta_json, name, is_current)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, now, now, None, name, 0),
            )
            if name is not None:
                cur.execute(
                    """
                    UPDATE sessions
                    SET name = ?
                    WHERE session_id = ?
                    """,
                    (name, session_id),
                )
            self.conn.commit()

    def resolve_session(self, ref: str) -> str | None:
        if not ref:
            return None
        ref = str(ref).strip()
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT session_id FROM sessions WHERE session_id = ? LIMIT 1",
                (ref,),
            )
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute("SELECT session_id FROM sessions WHERE name = ? LIMIT 1", (ref,))
            row = cur.fetchone()
            if row:
                return row[0]
        return None

    def get_current(self) -> str | None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT session_id
                FROM sessions
                WHERE is_current = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        if not row:
            return None
        return row[0]

    def set_current(self, session_id: str) -> None:
        now = self._now()
        with self._lock:
            cur = self.conn.cursor()
            self._ensure_session_row(session_id)
            cur.execute("UPDATE sessions SET is_current = 0 WHERE is_current != 0")
            cur.execute(
                """
                UPDATE sessions
                SET is_current = 1, updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )
            self.conn.commit()

    def list_sessions(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT s.session_id, s.name, s.is_current, s.created_at, s.updated_at,
                       COALESCE(m.cnt, 0) AS message_count
                FROM sessions s
                LEFT JOIN (
                    SELECT session_id, COUNT(*) AS cnt
                    FROM messages
                    GROUP BY session_id
                ) m ON m.session_id = s.session_id
                ORDER BY s.is_current DESC, s.updated_at DESC
                """
            )
            rows = cur.fetchall()

        items = []
        for row in rows:
            items.append(
                {
                    "session_id": row[0],
                    "name": row[1],
                    "is_current": int(row[2] or 0),
                    "created_at": row[3],
                    "updated_at": row[4],
                    "message_count": int(row[5] or 0),
                }
            )
        return items

    def load_messages(self, session_id: str):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT message_json
                FROM messages
                WHERE session_id = ?
                ORDER BY idx ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()
        msgs = []
        for (raw,) in rows:
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if isinstance(obj, dict):
                msgs.append(obj)
        return msgs

    def append_message(self, session_id: str, message: dict) -> None:
        raw = json.dumps(message, ensure_ascii=False)
        now = self._now()
        with self._lock:
            cur = self.conn.cursor()
            self._ensure_session_row(session_id)
            cur.execute(
                """
                SELECT COALESCE(MAX(idx) + 1, 0)
                FROM messages
                WHERE session_id = ?
                """,
                (session_id,),
            )
            (next_idx,) = cur.fetchone()
            cur.execute(
                """
                INSERT INTO messages (session_id, idx, message_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, int(next_idx), raw, now),
            )
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self.conn.close()
            except Exception:
                pass
