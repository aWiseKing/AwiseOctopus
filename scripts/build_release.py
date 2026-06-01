from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
PYINSTALLER_DIST = DIST_DIR / "pyinstaller"
ARTIFACT_DIR = DIST_DIR / "artifacts"
SPEC_PATH = ROOT / "packaging" / "pyinstaller" / "awiseoctopus.spec"


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def version() -> str:
    sys.path.insert(0, str(ROOT))
    from acli import __version__

    return __version__


def current_platform() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    raise SystemExit(f"Unsupported platform: {platform.system()}")


def executable_path(bundle_dir: Path) -> Path:
    if current_platform() == "windows":
        return bundle_dir / "awiseoctopus.exe"
    return bundle_dir / "awiseoctopus"


def build_pyinstaller() -> Path:
    if not SPEC_PATH.exists():
        raise SystemExit(f"Missing PyInstaller spec: {SPEC_PATH}")

    shutil.rmtree(PYINSTALLER_DIST, ignore_errors=True)
    env = dict(os.environ)
    env.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / "build" / "pyinstaller-config"))
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(PYINSTALLER_DIST),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
            str(SPEC_PATH),
        ],
        env=env,
    )
    bundle = PYINSTALLER_DIST / "AwiseOctopus"
    exe = executable_path(bundle)
    if not exe.exists():
        raise SystemExit(f"PyInstaller did not produce expected executable: {exe}")
    return bundle


def make_archive(bundle: Path, artifact_name: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    base = ARTIFACT_DIR / artifact_name
    archive = shutil.make_archive(str(base), "zip", root_dir=str(bundle.parent), base_dir=bundle.name)
    return Path(archive)


def build_windows(bundle: Path, app_version: str) -> list[Path]:
    artifacts = [make_archive(bundle, f"AwiseOctopus-{app_version}-windows-x64-portable")]
    iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    if not iscc:
        print("Inno Setup not found; portable zip was created instead of setup.exe.")
        return artifacts

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    script = ROOT / "packaging" / "windows" / "awiseoctopus.iss"
    run(
        [
            iscc,
            f"/DAppVersion={app_version}",
            f"/DSourceDir={bundle}",
            f"/DOutputDir={ARTIFACT_DIR}",
            str(script),
        ]
    )
    setup = ARTIFACT_DIR / f"AwiseOctopus-{app_version}-windows-x64-setup.exe"
    if setup.exists():
        artifacts.append(setup)
    return artifacts


def build_macos(bundle: Path, app_version: str) -> list[Path]:
    app_root = DIST_DIR / "macos" / "AwiseOctopus.app"
    resources = app_root / "Contents" / "Resources"
    macos = app_root / "Contents" / "MacOS"
    shutil.rmtree(app_root, ignore_errors=True)
    resources.mkdir(parents=True, exist_ok=True)
    macos.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle, resources / "AwiseOctopus")

    plist_path = ROOT / "packaging" / "macos" / "Info.plist"
    with plist_path.open("rb") as f:
        plist = plistlib.load(f)
    plist["CFBundleShortVersionString"] = app_version
    plist["CFBundleVersion"] = app_version
    with (app_root / "Contents" / "Info.plist").open("wb") as f:
        plistlib.dump(plist, f)

    launcher = macos / "AwiseOctopus"
    launcher.write_text(
        """#!/bin/sh
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$APP_DIR/Resources/AwiseOctopus/awiseoctopus"
osascript -e 'tell application "Terminal" to activate' \
  -e "tell application \\"Terminal\\" to do script quoted form of \\"$EXE\\""
""",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    dmg = ARTIFACT_DIR / f"AwiseOctopus-{app_version}-macos-universal.dmg"
    if shutil.which("hdiutil"):
        if dmg.exists():
            dmg.unlink()
        try:
            run(["hdiutil", "create", "-volname", "AwiseOctopus", "-srcfolder", str(app_root), "-ov", "-format", "UDZO", str(dmg)])
            return [dmg]
        except subprocess.CalledProcessError:
            print("hdiutil failed; app zip will be created instead of dmg.")
    else:
        print("hdiutil not found; app zip will be created instead of dmg.")

    return [Path(shutil.make_archive(str(ARTIFACT_DIR / f"AwiseOctopus-{app_version}-macos-universal"), "zip", root_dir=str(app_root.parent), base_dir=app_root.name))]


def build_linux(bundle: Path, app_version: str) -> list[Path]:
    artifacts: list[Path] = []
    appdir = DIST_DIR / "linux" / "AwiseOctopus.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "lib").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle, appdir / "usr" / "lib" / "AwiseOctopus")
    shutil.copy2(ROOT / "packaging" / "linux" / "awiseoctopus.desktop", appdir / "awiseoctopus.desktop")
    shutil.copy2(ROOT / "packaging" / "linux" / "awiseoctopus.desktop", appdir / "usr" / "share" / "applications" / "awiseoctopus.desktop")

    bin_link = appdir / "usr" / "bin" / "awiseoctopus"
    bin_link.write_text(
        """#!/bin/sh
exec "$(dirname "$0")/../lib/AwiseOctopus/awiseoctopus" "$@"
""",
        encoding="utf-8",
    )
    bin_link.chmod(bin_link.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    app_run = appdir / "AppRun"
    app_run.write_text(
        """#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/AwiseOctopus/awiseoctopus" "$@"
""",
        encoding="utf-8",
    )
    app_run.chmod(app_run.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    appimagetool = shutil.which("appimagetool")
    if appimagetool:
        appimage = ARTIFACT_DIR / f"AwiseOctopus-{app_version}-linux-x64.AppImage"
        env = dict(os.environ)
        env["ARCH"] = "x86_64"
        print("+", appimagetool, str(appdir), str(appimage))
        subprocess.run([appimagetool, str(appdir), str(appimage)], cwd=str(ROOT), env=env, check=True)
        artifacts.append(appimage)
    else:
        print("appimagetool not found; AppDir tar.gz was created instead of AppImage.")
        artifacts.append(Path(shutil.make_archive(str(ARTIFACT_DIR / f"AwiseOctopus-{app_version}-linux-x64-AppDir"), "gztar", root_dir=str(appdir.parent), base_dir=appdir.name)))

    if shutil.which("dpkg-deb"):
        deb_root = DIST_DIR / "linux" / "deb" / "awiseoctopus"
        shutil.rmtree(deb_root, ignore_errors=True)
        install_root = deb_root / "opt" / "AwiseOctopus"
        control_dir = deb_root / "DEBIAN"
        desktop_dir = deb_root / "usr" / "share" / "applications"
        bin_dir = deb_root / "usr" / "bin"
        shutil.copytree(bundle, install_root)
        control_dir.mkdir(parents=True, exist_ok=True)
        desktop_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        (control_dir / "control").write_text(
            f"""Package: awiseoctopus
Version: {app_version}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: AwiseOctopus
Description: AwiseOctopus CLI Chat
""",
            encoding="utf-8",
        )
        (bin_dir / "awiseoctopus").write_text(
            """#!/bin/sh
exec /opt/AwiseOctopus/awiseoctopus "$@"
""",
            encoding="utf-8",
        )
        (bin_dir / "awiseoctopus").chmod(0o755)
        shutil.copy2(ROOT / "packaging" / "linux" / "awiseoctopus.desktop", desktop_dir / "awiseoctopus.desktop")
        deb = ARTIFACT_DIR / f"awiseoctopus_{app_version}_amd64.deb"
        run(["dpkg-deb", "--build", str(deb_root), str(deb)])
        artifacts.append(deb)
    else:
        print("dpkg-deb not found; deb package skipped.")

    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AwiseOctopus release artifacts.")
    parser.add_argument("--platform", choices=["current", "windows", "macos", "linux"], default="current")
    args = parser.parse_args()

    target = current_platform() if args.platform == "current" else args.platform
    host = current_platform()
    if target != host:
        raise SystemExit(f"Cross-building is not supported here. Host={host}, target={target}")

    app_version = version()
    bundle = build_pyinstaller()

    if target == "windows":
        artifacts = build_windows(bundle, app_version)
    elif target == "macos":
        artifacts = build_macos(bundle, app_version)
    else:
        artifacts = build_linux(bundle, app_version)

    print("Artifacts:")
    for artifact in artifacts:
        print(f"  {artifact}")


if __name__ == "__main__":
    main()
