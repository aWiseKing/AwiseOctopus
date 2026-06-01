from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def resolve_executable(path: Path) -> Path:
    if path.is_file():
        return path

    candidates = []
    if platform.system().lower() == "windows":
        candidates.extend([path / "awiseoctopus.exe", path / "AwiseOctopus" / "awiseoctopus.exe"])
    else:
        candidates.extend(
            [
                path / "awiseoctopus",
                path / "AwiseOctopus" / "awiseoctopus",
                path / "usr" / "lib" / "AwiseOctopus" / "awiseoctopus",
                path / "Contents" / "Resources" / "AwiseOctopus" / "awiseoctopus",
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(f"Could not find packaged awiseoctopus executable under: {path}")


def run_check(exe: Path, args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("AWISEOCTOPUS_DATA_DIR", tempfile.mkdtemp(prefix="awiseoctopus-smoke-"))
    result = subprocess.run(
        [str(exe), *args],
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        timeout=30,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Smoke check failed: {exe} {' '.join(args)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a packaged AwiseOctopus bundle.")
    parser.add_argument("bundle", help="Path to executable or PyInstaller onedir bundle.")
    args = parser.parse_args()

    exe = resolve_executable(Path(args.bundle).expanduser().resolve())
    checks = [
        (["--version"], None),
        (["--no-color", "env", "set", "-l"], None),
        (
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
            "test-key\n",
        ),
        (["--no-color", "chat"], "exit\n"),
    ]

    for check_args, input_text in checks:
        result = run_check(exe, check_args, input_text=input_text)
        print(f"ok: {' '.join(check_args)}")
        if check_args[:1] == ["--version"]:
            print(result.stdout.strip())


if __name__ == "__main__":
    main()
