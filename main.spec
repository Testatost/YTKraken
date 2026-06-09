# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows.
#
# Build from the project root with:
#   pyinstaller --clean --noconfirm main_windows.spec
#
# The output executable will be:
#   dist\YTKraken.exe
#
# Notes:
# - Use an .ico file for the Windows executable icon.
# - ffmpeg/ffprobe are only bundled if they exist under:
#     tools\ffmpeg\bin\ffmpeg.exe
#     tools\ffmpeg\bin\ffprobe.exe
#   Otherwise, ffmpeg must be installed system-wide and available in PATH.

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

project_root = Path.cwd()
app_name = "YTKraken"

icon_candidates = [
    project_root / "assets" / "icon.ico",
    project_root / "app" / "assets" / "icons" / "app.ico",
    project_root / "icon.ico",
]

icon_file = next((str(path) for path in icon_candidates if path.exists()), None)

version_file = project_root / "version_info.txt"
version_arg = str(version_file) if version_file.exists() else None

hiddenimports = []

# Include the full modular app package.
hiddenimports += collect_submodules("app")
hiddenimports += collect_submodules("app.translation")

# Explicitly include every translation module.
translation_dir = project_root / "app" / "translation"
if translation_dir.is_dir():
    for path in translation_dir.glob("*.py"):
        if path.stem != "__init__":
            hiddenimports.append(f"app.translation.{path.stem}")

# yt-dlp loads extractors and postprocessors dynamically.
hiddenimports += collect_submodules("yt_dlp")
hiddenimports += [
    "yt_dlp.postprocessor.ffmpeg",
    "yt_dlp.utils",
]

# Optional yt-dlp/default dependencies. They are included only when installed.
for package in (
    "certifi",
    "requests",
    "urllib3",
    "websockets",
    "mutagen",
    "brotli",
    "brotlicffi",
    "Cryptodome",
):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

# Remove duplicates while preserving order.
hiddenimports = list(dict.fromkeys(hiddenimports))

datas = []

# Application assets.
for assets_dir in (
    project_root / "assets",
    project_root / "app" / "assets",
):
    if assets_dir.is_dir():
        datas.append((str(assets_dir), str(assets_dir.relative_to(project_root))))

# Keep translation .py files as data as well. Hidden imports above are what
# make imports work; this is additional safety for inspection/debugging.
if translation_dir.is_dir():
    datas.append((str(translation_dir), "app/translation"))

# Package metadata and runtime data.
for package in (
    "yt-dlp",
    "yt_dlp",
    "certifi",
    "requests",
    "urllib3",
    "websockets",
    "mutagen",
    "PySide6",
):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

binaries = []

# PySide6 DLLs and plugins.
try:
    binaries += collect_dynamic_libs("PySide6")
except Exception:
    pass

# Optional bundled ffmpeg/ffprobe.
# Recommended project layout:
#   tools/ffmpeg/bin/ffmpeg.exe
#   tools/ffmpeg/bin/ffprobe.exe
ffmpeg_bin_dir = project_root / "tools" / "ffmpeg" / "bin"
for exe_name in ("ffmpeg.exe", "ffprobe.exe"):
    exe_path = ffmpeg_bin_dir / exe_name
    if exe_path.exists():
        binaries.append((str(exe_path), "."))

excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "IPython",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    version=version_arg,
)
