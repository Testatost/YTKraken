from __future__ import annotations

from typing import Dict, Optional

VIDEO_HEIGHTS = {
    "best": None,
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}

VIDEO_QUALITY_VALUES = list(VIDEO_HEIGHTS.keys())
AUDIO_QUALITY_VALUES = ["best", "320", "256", "192", "160", "128", "96"]
AUDIO_FORMATS = ["mp3", "ogg", "aac", "wav", "wma"]
VIDEO_FORMATS = ["mkv", "mp4", "mov", "avi"]


def quality_label_key(value: str) -> str:
    return "quality_best" if value == "best" else value


def build_video_format_selector(quality: str) -> str:
    height = VIDEO_HEIGHTS.get(quality)
    if height is None:
        return "bv*+ba/b"
    return f"bv*[height<={height}]+ba/b[height<={height}]/b"


def build_audio_bitrate(quality: str) -> Optional[str]:
    # For compressed target formats, "Bestmöglich" should not result in a
    # variable-bitrate MP3 around ~240 kbit/s. Users expect the selected quality
    # to be reflected in file properties, so the best preset maps to 320 kbit/s.
    if quality == "best":
        return "320"
    return quality


def build_ydl_options(mode: str, video_quality: str, playlist: bool) -> Dict[str, object]:
    selector = "bestaudio/best" if mode == "audio" else build_video_format_selector(video_quality)
    return {
        "format": selector,
        "noplaylist": not playlist,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "windowsfilenames": True,
    }
