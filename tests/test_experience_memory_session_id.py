import sqlite3
import tempfile
import unittest

import models.experience_memory as experience_memory
from models.experience_memory import ExperienceMemoryManager


class TestExperienceMemorySessionId(unittest.TestCase):
    def setUp(self) -> None:
        experience_memory.chromadb = None
        ExperienceMemoryManager._instance = None

    def test_migration_adds_session_id_column_and_persists_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/experience.db"
            mgr = ExperienceMemoryManager(db_path=db_path, chroma_path=f"{td}/vec")

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(experiences)")
            cols = {row[1] for row in cur.fetchall()}
            self.assertIn("session_id", cols)

            mgr.add_experience(
                "thinking",
                "instruction",
                "process",
                "result",
                0.9,
                session_id="s1",
            )

            cur.execute(
                "SELECT session_id FROM experiences WHERE instruction = ? ORDER BY created_at DESC LIMIT 1",
                ("instruction",),
            )
            (sid,) = cur.fetchone()
            self.assertEqual(sid, "s1")
            conn.close()
            mgr.close()


if __name__ == "__main__":
    unittest.main()
