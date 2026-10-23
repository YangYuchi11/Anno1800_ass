# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件夹（onedir）分发，内置 Python 与 OCR 模型。"""

from PyInstaller.utils.hooks import collect_data_files

# RapidOCR 的模型文件（.onnx）与配置文件随包分发
datas = collect_data_files("rapidocr_onnxruntime")

a = Analysis(
    ["anno_copilot.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["win32gui"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnnoCopilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AnnoCopilot",
)
