import os
import shutil
import subprocess

from models.tool_runtime import DEFAULT_SHELL_TIMEOUT_SECONDS

from .registry import registry


_OUTPUT_LIMIT = 4000


def _truncate_text(text: str, limit: int = _OUTPUT_LIMIT) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text

    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    omitted = len(text) - len(head) - len(tail)
    return f"{head}\n... [已截断 {omitted} 个字符] ...\n{tail}"


def _resolve_shell(shell_name: str) -> tuple[str, list[str]]:
    if shell_name == "auto":
        if os.name == "nt":
            shell_name = "powershell"
        else:
            shell_name = "bash" if shutil.which("bash") else "sh"

    if shell_name == "powershell":
        executable = shutil.which("powershell") or shutil.which("pwsh")
        if not executable:
            raise RuntimeError("未找到 PowerShell 可执行文件。")
        return "powershell", [executable, "-Command"]

    if shell_name == "bash":
        executable = shutil.which("bash")
        if not executable:
            raise RuntimeError("未找到 bash 可执行文件。")
        return "bash", [executable, "-lc"]

    if shell_name == "sh":
        executable = shutil.which("sh")
        if not executable:
            raise RuntimeError("未找到 sh 可执行文件。")
        return "sh", [executable, "-lc"]

    raise RuntimeError(f"不支持的 shell 类型: {shell_name}")


def _format_result(
    *,
    shell_name: str,
    cwd: str,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    error: str | None = None,
) -> str:
    parts = [
        f"shell: {shell_name}",
        f"cwd: {cwd}",
        f"exit_code: {exit_code if exit_code is not None else 'timeout'}",
    ]
    if error:
        parts.append(f"error: {error}")
    parts.append("stdout:")
    parts.append(_truncate_text(stdout or ""))
    parts.append("stderr:")
    parts.append(_truncate_text(stderr or ""))
    return "\n".join(parts).strip()


@registry.register(
    name="shell_command",
    description="执行一条单次 shell 命令并返回退出码、标准输出和错误输出。只读命令通常可自动放行，高危命令需要确认。",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的单条 shell 命令。"},
            "cwd": {"type": "string", "description": "命令工作目录；默认使用当前会话工作区。"},
            "timeout_seconds": {
                "type": "integer",
                "description": f"超时时间（秒），默认 {DEFAULT_SHELL_TIMEOUT_SECONDS}。",
            },
            "shell": {
                "type": "string",
                "description": "shell 类型，可选 auto / powershell / bash / sh。",
                "enum": ["auto", "powershell", "bash", "sh"],
            },
        },
        "required": ["command"],
    },
    requires_confirmation=True,
    action_kind="shell_execution",
)
def shell_command(
    command,
    cwd=None,
    timeout_seconds=DEFAULT_SHELL_TIMEOUT_SECONDS,
    shell="auto",
):
    command = str(command or "").strip()
    if not command:
        return "shell_command 执行失败：command 不能为空。"

    cwd = os.path.abspath(cwd or os.getcwd())
    if not os.path.isdir(cwd):
        return f"shell_command 执行失败：工作目录不存在: {cwd}"

    try:
        resolved_shell, prefix = _resolve_shell(str(shell or "auto").strip().lower())
    except Exception as exc:
        return f"shell_command 执行失败：{exc}"

    full_command = [*prefix, command]
    print(
        f"\n    [系统提示] 执行Agent正在使用 {resolved_shell} 执行 shell 命令: {command}\n"
        f"    [系统提示] 工作目录: {cwd}"
    )

    try:
        result = subprocess.run(
            full_command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(timeout_seconds),
            shell=False,
        )
        return _format_result(
            shell_name=resolved_shell,
            cwd=cwd,
            exit_code=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )
    except subprocess.TimeoutExpired as exc:
        return _format_result(
            shell_name=resolved_shell,
            cwd=cwd,
            exit_code=None,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            error=f"命令执行超时（>{int(timeout_seconds)}s）",
        )
    except Exception as exc:
        return _format_result(
            shell_name=resolved_shell,
            cwd=cwd,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            error="命令执行异常",
        )
