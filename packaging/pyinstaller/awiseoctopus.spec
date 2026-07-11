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
datas += tree_datas("models/personas", "models/personas")
datas += tree_datas("libs/Everything_SDK", "libs/Everything_SDK")
datas += collect_data_files("chromadb")

hiddenimports = []
hiddenimports += [name for name in collect_submodules("chromadb") if not name.startswith("chromadb.test")]
hiddenimports += collect_submodules("onnxruntime")
hiddenimports += collect_submodules("tokenizers")

hiddenimports += collect_submodules("aiohappyeyeballs")
hiddenimports += collect_submodules("aiohttp")
hiddenimports += collect_submodules("aiosignal")
hiddenimports += collect_submodules("altgraph")
hiddenimports += collect_submodules("annotated-doc")
hiddenimports += collect_submodules("annotated-types")
hiddenimports += collect_submodules("anyio")
hiddenimports += collect_submodules("APScheduler")
hiddenimports += collect_submodules("async-timeout")
hiddenimports += collect_submodules("attrs")
hiddenimports += collect_submodules("awiseoctopus")
hiddenimports += collect_submodules("bcrypt")
hiddenimports += collect_submodules("build")
hiddenimports += collect_submodules("certifi")
hiddenimports += collect_submodules("charset-normalizer")
hiddenimports += collect_submodules("chromadb")
hiddenimports += collect_submodules("click")
hiddenimports += collect_submodules("colorama")
hiddenimports += collect_submodules("coloredlogs")
hiddenimports += collect_submodules("distro")
hiddenimports += collect_submodules("duckduckgo_search")
hiddenimports += collect_submodules("durationpy")
hiddenimports += collect_submodules("exceptiongroup")
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("filelock")
hiddenimports += collect_submodules("flatbuffers")
hiddenimports += collect_submodules("frozenlist")
hiddenimports += collect_submodules("fsspec")
hiddenimports += collect_submodules("googleapis-common-protos")
hiddenimports += collect_submodules("grpcio")
hiddenimports += collect_submodules("h11")
hiddenimports += collect_submodules("hf-xet")
hiddenimports += collect_submodules("httpcore")
hiddenimports += collect_submodules("httptools")
hiddenimports += collect_submodules("httpx")
hiddenimports += collect_submodules("huggingface_hub")
hiddenimports += collect_submodules("humanfriendly")
hiddenimports += collect_submodules("idna")
hiddenimports += collect_submodules("importlib_resources")
hiddenimports += collect_submodules("jiter")
hiddenimports += collect_submodules("jsonschema")
hiddenimports += collect_submodules("jsonschema-specifications")
hiddenimports += collect_submodules("kubernetes")
hiddenimports += collect_submodules("lxml")
hiddenimports += collect_submodules("markdown-it-py")
hiddenimports += collect_submodules("mdurl")
hiddenimports += collect_submodules("mmh3")
hiddenimports += collect_submodules("mpmath")
hiddenimports += collect_submodules("multidict")
hiddenimports += collect_submodules("numpy")
hiddenimports += collect_submodules("oauthlib")
hiddenimports += collect_submodules("openai")
hiddenimports += collect_submodules("opentelemetry-api")
hiddenimports += collect_submodules("opentelemetry-exporter-otlp-proto-common")
hiddenimports += collect_submodules("opentelemetry-exporter-otlp-proto-grpc")
hiddenimports += collect_submodules("opentelemetry-proto")
hiddenimports += collect_submodules("opentelemetry-sdk")
hiddenimports += collect_submodules("opentelemetry-semantic-conventions")
hiddenimports += collect_submodules("orjson")
hiddenimports += collect_submodules("overrides")
hiddenimports += collect_submodules("packaging")
hiddenimports += collect_submodules("pefile")
hiddenimports += collect_submodules("pip")
hiddenimports += collect_submodules("primp")
hiddenimports += collect_submodules("prompt_toolkit")
hiddenimports += collect_submodules("propcache")
hiddenimports += collect_submodules("protobuf")
hiddenimports += collect_submodules("pybase64")
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("pydantic_core")
hiddenimports += collect_submodules("pydantic-settings")
hiddenimports += collect_submodules("Pygments")
hiddenimports += collect_submodules("pyinstaller")
hiddenimports += collect_submodules("pyinstaller-hooks-contrib")
hiddenimports += collect_submodules("PyPika")
hiddenimports += collect_submodules("pyproject_hooks")
hiddenimports += collect_submodules("pyreadline3")
hiddenimports += collect_submodules("python-dateutil")
hiddenimports += collect_submodules("python-dotenv")
hiddenimports += collect_submodules("pywin32-ctypes")
hiddenimports += collect_submodules("PyYAML")
hiddenimports += collect_submodules("referencing")
hiddenimports += collect_submodules("requests")
hiddenimports += collect_submodules("requests-oauthlib")
hiddenimports += collect_submodules("rich")
hiddenimports += collect_submodules("rpds-py")
hiddenimports += collect_submodules("setuptools")
hiddenimports += collect_submodules("shellingham")
hiddenimports += collect_submodules("six")
hiddenimports += collect_submodules("sniffio")
hiddenimports += collect_submodules("starlette")
hiddenimports += collect_submodules("sympy")
hiddenimports += collect_submodules("tenacity")
hiddenimports += collect_submodules("tomli")
hiddenimports += collect_submodules("tqdm")
hiddenimports += collect_submodules("typer")
hiddenimports += collect_submodules("typing_extensions")
hiddenimports += collect_submodules("typing-inspection")
hiddenimports += collect_submodules("tzdata")
hiddenimports += collect_submodules("tzlocal")
hiddenimports += collect_submodules("urllib3")
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("watchfiles")
hiddenimports += collect_submodules("wcwidth")
hiddenimports += collect_submodules("websocket-client")
hiddenimports += collect_submodules("websockets")
hiddenimports += collect_submodules("yarl")

hiddenimports += collect_submodules("duckduckgo_search")
hiddenimports += collect_submodules("prompt_toolkit")


a = Analysis(
    [str(ROOT / "acli" / "packaged_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
