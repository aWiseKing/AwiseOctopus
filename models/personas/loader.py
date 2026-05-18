from __future__ import annotations

from pathlib import Path

from models.config_manager import ConfigManager
from models.runtime_paths import resource_path


DEFAULT_PERSONA_NAME = "GongnengLove"


def personas_root() -> Path:
    return resource_path("models", "personas")


def resolve_persona_name(
    persona_name: str | None = None,
    *,
    config_manager: ConfigManager | None = None,
) -> str:
    if persona_name:
        return persona_name.strip()

    manager = config_manager or ConfigManager()
    configured = manager.get("persona_name")
    if configured and configured.strip():
        return configured.strip()

    return DEFAULT_PERSONA_NAME


def list_personas() -> list[str]:
    root = personas_root()
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def get_persona_dir(
    persona_name: str | None = None,
    *,
    config_manager: ConfigManager | None = None,
) -> Path:
    resolved_name = resolve_persona_name(
        persona_name,
        config_manager=config_manager,
    )
    persona_dir = personas_root() / resolved_name
    if not persona_dir.is_dir():
        available = list_personas()
        available_text = ", ".join(available) if available else "无"
        raise FileNotFoundError(
            f"未找到人格目录: {resolved_name}。可用人格: {available_text}"
        )
    return persona_dir


def load_persona_prompt(
    prompt_name: str,
    *,
    persona_name: str | None = None,
    config_manager: ConfigManager | None = None,
    **template_vars,
) -> str:
    prompt_file = get_persona_dir(
        persona_name,
        config_manager=config_manager,
    ) / f"{prompt_name}.md"
    if not prompt_file.is_file():
        raise FileNotFoundError(f"未找到人格提示词文件: {prompt_file}")

    template = prompt_file.read_text(encoding="utf-8")
    try:
        return template.format(**template_vars)
    except KeyError as exc:
        missing_key = exc.args[0]
        raise KeyError(
            f"人格提示词模板变量缺失: {missing_key}（文件: {prompt_file}）"
        ) from exc
