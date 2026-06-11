import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from models.memory import MemoryManager


class TestCliMemoryCommandSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.tempdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tempdir.name) / "data"
        self.manager = MemoryManager(
            db_path=str(self.data_dir / "experience.db"),
            chroma_path=str(self.data_dir / "experience_vector"),
        )
        self.memory_id = self.manager.add_memory(
            mode="long_term",
            scope="user_preference",
            content="用户偏好中文回复。",
            summary="中文回复偏好",
            confidence=0.9,
            importance=0.9,
        )
        self.manager.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env["AWISEOCTOPUS_DATA_DIR"] = str(self.data_dir)
        return subprocess.run(
            [sys.executable, "-m", "acli", *args],
            cwd=str(self.repo_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input="test-key\n",
        )

    def test_memory_list_show_delete_stats(self) -> None:
        common = ["--no-color", "--base-url", "http://example", "--model", "test-model"]

        listed = self.run_cli([*common, "memory", "list", "--mode", "long"])
        self.assertEqual(listed.returncode, 0, msg=listed.stderr)
        self.assertIn("中文回复偏好", listed.stdout)

        shown = self.run_cli([*common, "memory", "show", self.memory_id])
        self.assertEqual(shown.returncode, 0, msg=shown.stderr)
        self.assertIn("用户偏好中文回复", shown.stdout)

        stats = self.run_cli([*common, "memory", "stats"])
        self.assertEqual(stats.returncode, 0, msg=stats.stderr)
        self.assertIn("long_term", stats.stdout)

        deleted = self.run_cli([*common, "memory", "delete", self.memory_id])
        self.assertEqual(deleted.returncode, 0, msg=deleted.stderr)


if __name__ == "__main__":
    unittest.main()
