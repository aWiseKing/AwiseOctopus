import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("rich") is not None, "rich is not installed")
class TestCliRichSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]

    def run_cli(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        env_overrides: dict[str, str] | None = None,
        env_remove: set[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        if env_remove:
            for k in env_remove:
                env.pop(k, None)
        if env_overrides:
            env.update(env_overrides)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        return subprocess.run(
            [sys.executable, "-m", "cli_rich", *args],
            cwd=str(self.repo_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=input_text,
        )

    def test_help(self) -> None:
        result = self.run_cli(["--help"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        out = result.stdout.lower()
        self.assertIn("chat", out)
        self.assertIn("run", out)
        self.assertNotIn("demo", out)
        self.assertNotIn("ask", out)

    def test_version(self) -> None:
        result = self.run_cli(["--version"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("0.1.0", result.stdout)

    def test_run_dry_run_interaction(self) -> None:
        result = self.run_cli(
            [
                "--no-color",
                "--base-url",
                "http://example",
                "--model",
                "test-model",
                "run",
                "--dry-run",
                "--prompt",
                "hi",
            ],
            input_text="test-key\n",
            env_remove={"api_key", "base_url", "MODEL"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("配置校验通过", result.stdout)
        self.assertIn("http://example", result.stdout)
        self.assertIn("test-model", result.stdout)
        self.assertNotIn("test-key", result.stdout + result.stderr)

