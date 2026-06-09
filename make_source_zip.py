#!/usr/bin/env python3
"""
Create a clean source-code ZIP for YTKraken without requiring Git.

Run this file from the project root:

    python3 make_source_zip.py

The ZIP will be created as:

    ./YTKraken-source.zip
"""

from __future__ import annotations

import fnmatch
import os
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ZIP = PROJECT_ROOT / "YTKraken-source.zip"


EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "logs",
    "log",
    "tmp",
    "temp",
    "cache",
    ".cache",
    "downloads",
    "Downloads",
    "output",
    "converted",
}


EXCLUDED_FILE_PATTERNS = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.log",
    "*.tmp",
    "*.bak",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".directory",
    ".env",
    ".env.*",
    "secrets.*",
    "cookies.txt",
    "*.cookies",
    "*.part",
    "*.ytdl",
    "*.ytdl.tmp",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.7z",
    "*.rar",
    "*.mp3",
    "*.ogg",
    "*.aac",
    "*.wav",
    "*.wma",
    "*.mp4",
    "*.mkv",
    "*.mov",
    "*.avi",
    "*.webm",
}


def should_exclude(path: Path) -> bool:
    relative = path.relative_to(PROJECT_ROOT)
    parts = set(relative.parts)

    if parts & EXCLUDED_DIR_NAMES:
        return True

    name = path.name
    for pattern in EXCLUDED_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True

    return False


def main() -> None:
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    files: list[Path] = []

    for root, dirs, filenames in os.walk(PROJECT_ROOT):
        root_path = Path(root)

        dirs[:] = [
            directory
            for directory in dirs
            if not should_exclude(root_path / directory)
        ]

        for filename in filenames:
            path = root_path / filename
            if path == OUTPUT_ZIP:
                continue
            if should_exclude(path):
                continue
            files.append(path)

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(PROJECT_ROOT))

    print(f"Created: {OUTPUT_ZIP}")
    print(f"Files included: {len(files)}")


if __name__ == "__main__":
    main()
