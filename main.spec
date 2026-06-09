# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Linux / Fedora KDE Plasma.
# Build from the project root with:
#   pyinstaller --clean --noconfirm main.spec
#
# ffmpeg/ffprobe are not bundled here. Install them system-wide on Fedora:
#   sudo dnf install ffmpeg

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
import os

project_root = os.path.abspath('.')

icon_candidates = [
    os.path.join(project_root, 'icon.png'),
    os.path.join(project_root, 'icon.ico'),
    os.path.join(project_root, 'app', 'assets', 'icons', 'app.png'),
]
icon_file = next((path for path in icon_candidates if os.path.exists(path)), None)

hiddenimports = []

# Include the full modular app package.
hiddenimports += collect_submodules('app') + collect_submodules('app.translation')

# Explicitly include every translation file. This avoids runtime errors such as:
# ModuleNotFoundError: No module named 'app.translation.de'
translation_dir = os.path.join(project_root, 'app', 'translation')
if os.path.isdir(translation_dir):
    for filename in os.listdir(translation_dir):
        name, ext = os.path.splitext(filename)
        if ext == '.py' and name != '__init__':
            hiddenimports.append(f'app.translation.{name}')

# yt-dlp loads extractors/postprocessors dynamically.
hiddenimports += collect_submodules('yt_dlp')
hiddenimports += [
    'yt_dlp.postprocessor.ffmpeg',
    'yt_dlp.utils',
]

# Optional yt-dlp/default dependencies. They are included only when installed.
for package in (
    'certifi',
    'requests',
    'urllib3',
    'websockets',
    'mutagen',
    'brotli',
    'brotlicffi',
    'Cryptodome',
):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

# Remove duplicates while preserving order.
hiddenimports = list(dict.fromkeys(hiddenimports))

datas = []

assets_dir = os.path.join(project_root, 'app', 'assets')
if os.path.isdir(assets_dir):
    datas.append((assets_dir, 'app/assets'))

# Keep translation .py files as data as well. The hiddenimports above are the
# important part for importing, this is extra safety for inspection/debugging.
if os.path.isdir(translation_dir):
    datas.append((translation_dir, 'app/translation'))

for package in (
    'yt-dlp',
    'yt_dlp',
    'certifi',
    'requests',
    'urllib3',
    'websockets',
    'mutagen',
    'PySide6',
):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

if icon_file and not (assets_dir and icon_file.startswith(assets_dir)):
    datas.append((icon_file, '.'))

binaries = []

excludes = [
    'tkinter',
    'unittest',
    'pytest',
    'IPython',
]


a = Analysis(
    ['main.py'],
    pathex=[project_root],
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
    name='YTKraken',
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
)
