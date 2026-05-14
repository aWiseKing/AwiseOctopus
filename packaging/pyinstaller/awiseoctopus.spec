# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).resolve().parents[1]


def tree_datas(source: str, target: str):
    source_path = ROOT / source
    if not source_path.exists():
        return []
    datas = []
    for path in source_path.rglob("*"):
        if path.is_file():
            rel_parent = path.parent.relative_to(source_path)
            datas.append((str(path), str(Path(target) / rel_parent)))
    return datas


datas = []
datas += tree_datas("skills", "skills")
datas += tree_datas("libs/Everything_SDK", "libs/Everything_SDK")
datas += collect_data_files("chromadb")

hiddenimports = []
hiddenimports += [name for name in collect_submodules("chromadb") if not name.startswith("chromadb.test")]
hiddenimports += collect_submodules("duckduckgo_search")
hiddenimports += collect_submodules("prompt_toolkit")


a = Analysis(
    [str(ROOT / "cli_rich" / "packaged_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["streamlit"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="awiseoctopus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AwiseOctopus",
)
