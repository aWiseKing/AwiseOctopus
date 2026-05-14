from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "AwiseOctopus"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_dir() -> Path:
    override = os.getenv("AWISEOCTOPUS_RESOURCE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    pyinstaller_root = getattr(sys, "_MEIPASS", None)
    if pyinstaller_root:
        return Path(pyinstaller_root).resolve()

    return repo_root()


def resource_path(*parts: str) -> Path:
    return resource_dir().joinpath(*parts)


def user_data_dir(
    *,
    platform: str | None = None,
    environ: dict[str, str] | None = None,
    home: str | Path | None = None,
    create: bool = True,
) -> Path:
    env = environ if environ is not None else os.environ
    override = env.get("AWISEOCTOPUS_DATA_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        current_platform = platform or sys.platform
        home_path = Path(home).expanduser() if home is not None else Path.home()

        if current_platform.startswith("win"):
            base = env.get("APPDATA")
            path = Path(base).expanduser() / APP_NAME if base else home_path / "AppData" / "Roaming" / APP_NAME
        elif current_platform == "darwin":
            path = home_path / "Library" / "Application Support" / APP_NAME
        else:
            base = env.get("XDG_DATA_HOME")
            path = Path(base).expanduser() / APP_NAME if base else home_path / ".local" / "share" / APP_NAME

    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def user_data_path(*parts: str, create_parent: bool = True) -> Path:
    path = user_data_dir(create=True).joinpath(*parts)
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path
