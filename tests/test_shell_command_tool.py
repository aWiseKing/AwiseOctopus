import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models.tools.shell_command import shell_command


class TestShellCommandTool(unittest.TestCase):
    def test_shell_command_returns_exit_code_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch(
            "models.tools.shell_command._resolve_shell",
            return_value=("powershell", ["powershell", "-Command"]),
        ), patch(
            "models.tools.shell_command.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="ok\n", stderr=""),
        ) as mock_run:
            result = shell_command("git status", cwd=td, timeout_seconds=5, shell="powershell")

        self.assertIn("shell: powershell", result)
        self.assertIn("exit_code: 0", result)
        self.assertIn("stdout:\nok", result)
        self.assertIn(f"cwd: {td}", result)
        mock_run.assert_called_once()

    def test_shell_command_timeout_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch(
            "models.tools.shell_command._resolve_shell",
            return_value=("bash", ["bash", "-lc"]),
        ), patch(
            "models.tools.shell_command.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=["bash", "-lc", "sleep 5"],
                timeout=1,
                output="partial",
                stderr="still running",
            ),
        ):
            result = shell_command("sleep 5", cwd=td, timeout_seconds=1, shell="bash")

        self.assertIn("exit_code: timeout", result)
        self.assertIn("命令执行超时", result)
        self.assertIn("partial", result)
        self.assertIn("still running", result)

    def test_shell_command_truncates_long_output(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch(
            "models.tools.shell_command._resolve_shell",
            return_value=("sh", ["sh", "-lc"]),
        ), patch(
            "models.tools.shell_command.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="a" * 5000, stderr=""),
        ):
            result = shell_command("cat big.log", cwd=td, timeout_seconds=5, shell="sh")

        self.assertIn("已截断", result)

    def test_shell_command_reports_missing_shell(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch(
            "models.tools.shell_command._resolve_shell",
            side_effect=RuntimeError("未找到 bash 可执行文件。"),
        ):
            result = shell_command("ls", cwd=td, timeout_seconds=5, shell="bash")

        self.assertIn("shell_command 执行失败", result)
        self.assertIn("未找到 bash 可执行文件", result)


if __name__ == "__main__":
    unittest.main()
