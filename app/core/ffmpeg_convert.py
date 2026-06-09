from __future__ import annotations

import os
import subprocess
from typing import Dict, List

from PySide6.QtCore import QObject, Signal, Slot

from app.core.utils import timestamp, unique_path

AUDIO_TARGETS = ["mp3", "ogg", "aac", "wav", "wma"]
VIDEO_TARGETS = ["mp4", "mkv", "mov", "avi", "webm"]
WEBM_CODECS = ["VP9", "VP8"]


def build_audio_command(input_path: str, output_path: str, target: str, bitrate: str) -> List[str]:
    base = ["ffmpeg", "-y", "-i", input_path, "-vn", "-map_metadata", "0"]
    if target == "mp3":
        return base + ["-c:a", "libmp3lame", "-b:a", f"{bitrate}k", output_path]
    if target == "ogg":
        return base + ["-c:a", "libvorbis", "-b:a", f"{bitrate}k", output_path]
    if target == "aac":
        return base + ["-c:a", "aac", "-b:a", f"{bitrate}k", output_path]
    if target == "wav":
        return base + ["-c:a", "pcm_s16le", output_path]
    if target == "wma":
        return base + ["-c:a", "wmav2", "-b:a", f"{bitrate}k", "-f", "asf", output_path]
    raise ValueError(target)


def video_filter_args(video_height: str) -> List[str]:
    height = str(video_height or "original").strip().lower()
    if height in {"", "original", "source", "best", "none"}:
        return []
    if not height.isdigit():
        return []
    # -2 keeps the aspect ratio and forces an encoder-compatible even width.
    return ["-vf", f"scale=-2:{height}"]


def build_video_command(
    input_path: str,
    output_path: str,
    target: str,
    include_audio: bool,
    webm_codec: str,
    video_height: str = "original",
) -> List[str]:
    base = ["ffmpeg", "-y", "-i", input_path]
    scale_args = video_filter_args(video_height)
    if target == "webm":
        if webm_codec == "VP8":
            video_args = ["-c:v", "libvpx", "-crf", "10", "-b:v", "1M"]
            audio_args = ["-c:a", "libvorbis", "-b:a", "192k"] if include_audio else ["-an"]
        else:
            video_args = ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0"]
            audio_args = ["-c:a", "libopus", "-b:a", "160k"] if include_audio else ["-an"]
        return base + scale_args + video_args + audio_args + [output_path]

    if target in {"mp4", "mov", "mkv"}:
        video_args = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
        audio_args = ["-c:a", "aac", "-b:a", "192k"] if include_audio else ["-an"]
        extra = ["-movflags", "+faststart"] if target == "mp4" else []
        return base + scale_args + video_args + audio_args + extra + [output_path]

    if target == "avi":
        video_args = ["-c:v", "mpeg4", "-q:v", "3"]
        audio_args = ["-c:a", "mp3", "-b:a", "192k"] if include_audio else ["-an"]
        return base + scale_args + video_args + audio_args + [output_path]

    raise ValueError(target)


def output_path_for(input_path: str, output_dir: str, target: str, webm_codec: str = "VP9") -> str:
    stem = os.path.splitext(os.path.basename(input_path))[0]
    suffix = f"_converted_{webm_codec.lower()}" if target == "webm" else "_converted"
    return unique_path(os.path.join(output_dir, f"{stem}{suffix}.{target}"))


def render(texts: Dict[str, str], key: str, **values: object) -> str:
    template = texts.get(key, key)
    try:
        return template.format(**values)
    except Exception:
        return template


class ConversionWorker(QObject):
    log = Signal(str)
    file_finished = Signal(str)
    finished = Signal()

    @Slot(list, dict)
    def run(self, files: List[str], options: Dict[str, object]) -> None:
        output_dir = str(options["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        target_kind = str(options["kind"])
        target = str(options["target"])
        include_audio = bool(options.get("include_audio", True))
        bitrate = str(options.get("bitrate", "320"))
        webm_codec = str(options.get("webm_codec", "VP9"))
        video_height = str(options.get("video_height", "original"))
        texts = {str(k): str(v) for k, v in dict(options.get("texts", {})).items()}

        for input_path in files:
            try:
                out_path = output_path_for(input_path, output_dir, target, webm_codec)
                if target_kind == "audio":
                    command = build_audio_command(input_path, out_path, target, bitrate)
                else:
                    command = build_video_command(input_path, out_path, target, include_audio, webm_codec, video_height)

                self.log.emit(f"[{timestamp()}] {render(texts, 'conversion_log_converting', file=os.path.basename(input_path))}")
                self.log.emit(" ".join(command))
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                assert process.stdout is not None
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        self.log.emit(line)
                exit_code = process.wait()
                if exit_code != 0:
                    self.log.emit(f"[{timestamp()}] {render(texts, 'conversion_log_error_code', code=exit_code, file=input_path)}")
                else:
                    self.log.emit(f"[{timestamp()}] {render(texts, 'conversion_log_done', file=out_path)}")
                    self.file_finished.emit(out_path)
            except ValueError as exc:
                key = "worker_unsupported_audio" if target_kind == "audio" else "worker_unsupported_video"
                self.log.emit(f"[{timestamp()}] {render(texts, key, format=str(exc))}")
            except Exception as exc:
                self.log.emit(f"[{timestamp()}] {render(texts, 'conversion_log_error', file=input_path, error=exc)}")
        self.finished.emit()
