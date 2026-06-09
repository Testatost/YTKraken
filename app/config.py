from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Optional

APP_NAME = "yt-dlp GUI"
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_ROOT)
ASSETS_DIR = os.path.join(APP_ROOT, "assets")
SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".yt_dlp_gui")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
SETTINGS_SCHEMA_VERSION = 8

DEFAULT_SETTINGS: Dict[str, Any] = {
    "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    "theme": "Original",
    "language": "de",
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "mode": "video",
    "video_format": "mp4",
    "audio_format": "mp3",
    "video_quality": "1080p",
    "audio_quality": "320",
    "playlist_allowed": True,
    "window_width": 1360,
    "window_height": 900,
    "window_geometry": "",
}


def asset_path(*parts: str) -> str:
    return os.path.join(ASSETS_DIR, *parts)


def _sanitize_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _sanitize_choice(value: Any, allowed: set[str], default: str) -> str:
    value = str(value or "")
    return value if value in allowed else default


def load_settings() -> Dict[str, Any]:
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            return dict(DEFAULT_SETTINGS)
    except Exception:
        return dict(DEFAULT_SETTINGS)

    data = dict(DEFAULT_SETTINGS)
    data.update(raw)

    # Migration: the earlier generated theme versions could store unreadable test themes.
    # Reset only once while keeping other user settings from then on.
    if int(raw.get("settings_schema_version", 0) or 0) < SETTINGS_SCHEMA_VERSION:
        data["theme"] = "Original"
        data["window_width"] = DEFAULT_SETTINGS["window_width"]
        data["window_height"] = DEFAULT_SETTINGS["window_height"]
        data["window_geometry"] = ""
        data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
        save_settings(data)

    data["mode"] = _sanitize_choice(data.get("mode"), {"video", "audio"}, DEFAULT_SETTINGS["mode"])
    data["video_format"] = _sanitize_choice(data.get("video_format"), {"mkv", "mp4", "mov", "avi"}, DEFAULT_SETTINGS["video_format"])
    data["audio_format"] = _sanitize_choice(data.get("audio_format"), {"mp3", "ogg", "aac", "wav", "wma"}, DEFAULT_SETTINGS["audio_format"])
    data["video_quality"] = _sanitize_choice(data.get("video_quality"), {"best", "2160p", "1440p", "1080p", "720p", "480p", "360p"}, DEFAULT_SETTINGS["video_quality"])
    data["audio_quality"] = _sanitize_choice(data.get("audio_quality"), {"best", "320", "256", "192", "160", "128", "96"}, DEFAULT_SETTINGS["audio_quality"])
    data["playlist_allowed"] = _sanitize_bool(data.get("playlist_allowed"), DEFAULT_SETTINGS["playlist_allowed"])

    # Do not keep stale /home/<other-user>/... paths when the app is copied to
    # another Fedora/KDE account. Always fall back to the current user home.
    download_dir = str(data.get("download_dir") or DEFAULT_DOWNLOAD_DIR)
    current_home = os.path.expanduser("~")
    if download_dir.startswith("/home/") and not download_dir.startswith(current_home):
        download_dir = DEFAULT_DOWNLOAD_DIR
    data["download_dir"] = download_dir

    try:
        data["window_width"] = max(1180, min(2200, int(data.get("window_width", DEFAULT_SETTINGS["window_width"]))))
        data["window_height"] = max(680, min(1400, int(data.get("window_height", DEFAULT_SETTINGS["window_height"]))))
    except Exception:
        data["window_width"] = DEFAULT_SETTINGS["window_width"]
        data["window_height"] = DEFAULT_SETTINGS["window_height"]
    return data


def save_settings(settings: Dict[str, Any]) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    data = dict(DEFAULT_SETTINGS)
    data.update(settings)
    data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    with open(SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def encode_qbytearray(value) -> str:
    try:
        return base64.b64encode(bytes(value)).decode("ascii")
    except Exception:
        return ""


def decode_qbytearray(value: Any) -> Optional[bytes]:
    if not value:
        return None
    try:
        return base64.b64decode(str(value).encode("ascii"))
    except Exception:
        return None
