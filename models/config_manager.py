import os
import sqlite3

from .runtime_paths import user_data_path


class ConfigManager:
    _instance = None

    @staticmethod
    def _resolve_db_path(db_path: str | None = None) -> str:
        if db_path is None:
            return str(user_data_path("config.db"))
        return os.path.abspath(os.path.expanduser(db_path))

    def __new__(cls, db_path: str | None = None):
        resolved_db_path = cls._resolve_db_path(db_path)
        if cls._instance is None or getattr(cls._instance, "db_path", None) != resolved_db_path:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str | None = None):
        resolved_db_path = self._resolve_db_path(db_path)
        if self._initialized:
            return
            
        self._initialized = True
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(resolved_db_path), exist_ok=True)
        
        self.db_path = resolved_db_path
        
        # Initialize SQLite
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()

    def set(self, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO config (key, value)
            VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()

    def get(self, key: str, default=None) -> str:
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return default

    def get_all(self) -> dict[str, str]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT key, value FROM config')
        return {row[0]: row[1] for row in cursor.fetchall()}

    def delete(self, key: str):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM config WHERE key = ?', (key,))
        self.conn.commit()
