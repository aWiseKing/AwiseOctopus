import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import models.memory as memory_module
from models.memory import MemoryManager


class TestMemoryManager(unittest.TestCase):
    def setUp(self) -> None:
        MemoryManager._instance = None
        self.original_chromadb = memory_module.chromadb
        memory_module.chromadb = None

    def tearDown(self) -> None:
        instance = MemoryManager._instance
        if instance is not None and getattr(instance, "conn", None) is not None:
            instance.close()
        MemoryManager._instance = None
        memory_module.chromadb = self.original_chromadb

    def test_schema_migration_creates_new_tables_without_breaking_experiences(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/experience.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE experiences (
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
            conn.commit()
            conn.close()

            mgr = MemoryManager(db_path=db_path, chroma_path=f"{td}/vec")
            try:
                cur = mgr.conn.cursor()
                cur.execute("PRAGMA table_info(experiences)")
                experience_cols = {row[1] for row in cur.fetchall()}
                self.assertIn("session_id", experience_cols)

                cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                tables = {row[0] for row in cur.fetchall()}
                self.assertIn("memories", tables)
                self.assertIn("session_memory_state", tables)
            finally:
                mgr.close()

    def test_crud_and_context_work_without_chromadb(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = MemoryManager(db_path=f"{td}/experience.db", chroma_path=f"{td}/vec")
            try:
                short_id = mgr.add_memory(
                    mode="short_term",
                    scope="session_summary",
                    session_id="s1",
                    content="用户正在开发记忆系统。",
                    importance=0.8,
                )
                long_id = mgr.add_memory(
                    mode="long_term",
                    scope="project_context",
                    content="用户偏好中文回复。",
                    importance=0.9,
                    confidence=0.9,
                )
                mgr.add_experience(
                    "thinking",
                    "实现 memory",
                    "检查代码并设计方案",
                    "完成",
                    0.9,
                    session_id="s1",
                )

                self.assertEqual(mgr.get_memory(short_id)["content"], "用户正在开发记忆系统。")
                self.assertEqual(len(mgr.list_memories(mode="long", limit=10)), 1)
                context = mgr.build_memory_context("thinking", "实现 memory", session_id="s1")
                self.assertIn("短期记忆", context)
                self.assertIn("长期记忆", context)
                self.assertIn("历史经验参考", context)

                self.assertTrue(mgr.delete_memory(long_id))
                self.assertIsNone(mgr.get_memory(long_id))
                self.assertEqual(mgr.clear_memories(mode="short", session_id="s1"), 1)
            finally:
                mgr.close()

    def test_concurrent_experience_writes_are_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = MemoryManager(db_path=f"{td}/experience.db", chroma_path=f"{td}/vec")
            try:
                def add_item(index: int) -> str:
                    return mgr.add_experience(
                        "thinking",
                        f"instruction {index}",
                        "process",
                        "result",
                        0.8,
                        session_id="s1",
                    )

                with ThreadPoolExecutor(max_workers=8) as pool:
                    exp_ids = list(pool.map(add_item, range(24)))

                self.assertEqual(len(set(exp_ids)), 24)
                cur = mgr.conn.cursor()
                cur.execute("SELECT COUNT(*) FROM experiences WHERE session_id = ?", ("s1",))
                self.assertEqual(cur.fetchone()[0], 24)
                cur.execute("SELECT COUNT(*) FROM memories WHERE session_id = ?", ("s1",))
                self.assertEqual(cur.fetchone()[0], 24)
            finally:
                mgr.close()

    def test_default_path_uses_user_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"AWISEOCTOPUS_DATA_DIR": td}, clear=False):
            mgr = MemoryManager()
            try:
                self.assertEqual(mgr.db_path, str((Path(td) / "experience.db").resolve()))
                self.assertEqual(mgr.chroma_path, str((Path(td) / "experience_vector").resolve()))
            finally:
                mgr.close()


if __name__ == "__main__":
    unittest.main()
