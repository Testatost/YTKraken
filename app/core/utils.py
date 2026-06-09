import os
import re
from datetime import datetime
from typing import Iterable, List, Optional


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def split_urls(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    parts = re.split(r"[\s,;]+", text)
    urls = [part.strip() for part in parts if part.startswith(("http://", "https://"))]
    if urls:
        return urls

    return re.findall(r"https?://\S+", text)


def safe_file_stem(value: str) -> str:
    """Return a filesystem-safe filename stem without adding technical IDs.

    The UI should save files as the visible video/song title only. This helper
    removes path separators and characters that commonly break filenames, but it
    deliberately does not append the yt-dlp id.
    """
    text = (value or "").strip()
    text = re.sub(r"[\\/]+", " - ", text)
    text = re.sub(r"[\0\r\n\t]+", " ", text)
    text = re.sub(r"[:*?\"<>|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text.replace("%", "％")
    return text[:200] or "download"


def safe_filename_template(folder: str, title: Optional[str] = None) -> str:
    """Build the yt-dlp output template.

    No playlist index and no video id are appended. If a custom/renamed title is
    supplied, it is used as the fixed output filename stem; otherwise yt-dlp's
    extracted title is used.
    """
    if title:
        return os.path.join(folder, f"{safe_file_stem(title)}.%(ext)s")
    return os.path.join(folder, "%(title).200s.%(ext)s")


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base} ({counter}){ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def first_existing(paths: Iterable[str]) -> str:
    for path in paths:
        if path and os.path.exists(path):
            return path
    return ""
