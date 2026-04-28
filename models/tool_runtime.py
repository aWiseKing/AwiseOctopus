import os


DEFAULT_SHELL_TIMEOUT_SECONDS = 30
ALLOWED_SHELLS = {"auto", "powershell", "bash", "sh"}


class ToolArgsError(ValueError):
    """Raised when tool arguments are invalid after runtime normalization."""


def resolve_workspace_for_session(session_id: str | None) -> str | None:
    workspace = None
    if session_id:
        try:
            from .session_store import SessionStore

            store = SessionStore()
            try:
                workspace = store.get_workspace(session_id)
            finally:
                store.close()
        except Exception:
            workspace = None

    if not workspace:
        try:
            from .config_manager import ConfigManager

            workspace = ConfigManager().get("default_workspace")
        except Exception:
            workspace = None

    if not workspace:
        return None
    return os.path.abspath(workspace)


def prepare_tool_args(name: str, args: dict | None, workspace: str | None = None) -> dict:
    normalized = dict(args or {})
    if name != "shell_command":
        return normalized
    return _normalize_shell_args(normalized, workspace=workspace)


def _normalize_shell_args(args: dict, workspace: str | None = None) -> dict:
    command = str(args.get("command") or "").strip()
    if not command:
        raise ToolArgsError("shell_command 的 command 不能为空。")

    shell_name = str(args.get("shell") or "auto").strip().lower() or "auto"
    if shell_name not in ALLOWED_SHELLS:
        raise ToolArgsError(
            f"不支持的 shell 类型: {shell_name}。允许值: {', '.join(sorted(ALLOWED_SHELLS))}"
        )

    raw_timeout = args.get("timeout_seconds", DEFAULT_SHELL_TIMEOUT_SECONDS)
    try:
        timeout_seconds = int(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise ToolArgsError("timeout_seconds 必须是整数。") from exc
    if timeout_seconds <= 0:
        raise ToolArgsError("timeout_seconds 必须大于 0。")

    workspace_root = os.path.abspath(workspace) if workspace else None
    raw_cwd = args.get("cwd")
    if raw_cwd in (None, ""):
        cwd = workspace_root or os.getcwd()
    else:
        raw_cwd = str(raw_cwd)
        if os.path.isabs(raw_cwd):
            cwd = os.path.abspath(raw_cwd)
        else:
            base_dir = workspace_root or os.getcwd()
            cwd = os.path.abspath(os.path.join(base_dir, raw_cwd))

    if workspace_root:
        try:
            common = os.path.commonpath([workspace_root, cwd])
        except ValueError as exc:
            raise ToolArgsError(
                f"shell_command 的 cwd 超出了工作区限制: {cwd}"
            ) from exc
        if common != workspace_root:
            raise ToolArgsError(f"shell_command 的 cwd 超出了工作区限制: {cwd}")

    normalized = dict(args)
    normalized["command"] = command
    normalized["cwd"] = cwd
    normalized["shell"] = shell_name
    normalized["timeout_seconds"] = timeout_seconds
    return normalized
