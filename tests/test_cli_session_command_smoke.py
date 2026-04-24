import os
import subprocess
import sys
import unittest
from pathlib import Path


class TestCliSessionCommandSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]

    def run_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        return subprocess.run(
            [sys.executable, "-m", "cli_rich", *args],
            cwd=str(self.repo_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input="test-key\n",
        )

    def test_session_new_use_current_list(self) -> None:
        r1 = self.run_cli(
            [
                "--no-color",
                "--base-url",
                "http://example",
                "--model",
                "test-model",
                "session",
                "new",
                "--name",
                "t1",
                "--use",
            ]
        )
        self.assertEqual(r1.returncode, 0, msg=r1.stderr)

        r2 = self.run_cli(
            [
                "--no-color",
                "--base-url",
                "http://example",
                "--model",
                "test-model",
                "session",
                "current",
            ]
        )
        self.assertEqual(r2.returncode, 0, msg=r2.stderr)
        self.assertIn("t1", r2.stdout)

        r3 = self.run_cli(
            [
                "--no-color",
                "--base-url",
                "http://example",
                "--model",
                "test-model",
                "session",
                "list",
            ]
        )
        self.assertEqual(r3.returncode, 0, msg=r3.stderr)


if __name__ == "__main__":
    unittest.main()

