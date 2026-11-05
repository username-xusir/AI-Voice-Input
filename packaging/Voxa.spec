# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
APP = ROOT / "app"

datas = []
binaries = []
hiddenimports = []
for package in (
    "openvino",
    "openvino_genai",
    "openvino_tokenizers",
    "faster_whisper",
    "ctranslate2",
    "sounddevice",
    "soxr",
    "av",
    "onnxruntime",
    "opencc",
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception as exc:
        print(f"collect_all({package}) failed: {exc}")

a = Analysis(
    [str(APP / "main.py")],
    pathex=[str(APP)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "transformers",
        "datasets",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "tkinter",
        "pytest",
        "llvmlite",
        "numba",
        "PIL",
        "onnxruntime.quantization",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Voxa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "packaging" / "app.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Voxa",
)
