from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal, Slot

from app.core.utils import safe_filename_template, timestamp


class Cancelled(Exception):
    pass


def render(texts: Dict[str, str], key: str, **values: object) -> str:
    template = texts.get(key, key)
    try:
        return template.format(**values)
    except Exception:
        return template


def _format_speed(speed: Optional[float]) -> str:
    if not speed:
        return ""
    units = ["B/s", "KiB/s", "MiB/s", "GiB/s"]
    value = float(speed)
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    return f"{value:.1f} {units[index]}"


def _format_eta(eta: Optional[float]) -> str:
    if eta is None:
        return ""
    minutes, seconds = divmod(int(eta), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def _load_ytdlp_tools():
    yt_dlp = importlib.import_module("yt_dlp")
    ffmpeg_module = importlib.import_module("yt_dlp.postprocessor.ffmpeg")
    utils_module = importlib.import_module("yt_dlp.utils")
    return {
        "yt_dlp": yt_dlp,
        "FFmpegPostProcessor": getattr(ffmpeg_module, "FFmpegPostProcessor"),
        "FFmpegPostProcessorError": getattr(ffmpeg_module, "FFmpegPostProcessorError"),
        "PostProcessingError": getattr(utils_module, "PostProcessingError"),
        "replace_extension": getattr(utils_module, "replace_extension"),
        "prepend_extension": getattr(utils_module, "prepend_extension"),
    }


def _entry_url(entry: Dict[str, Any], playlist_info: Dict[str, Any]) -> str:
    value = str(entry.get("webpage_url") or entry.get("url") or "").strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value

    entry_id = str(entry.get("id") or value or "").strip()
    extractor = str(entry.get("ie_key") or playlist_info.get("extractor_key") or playlist_info.get("extractor") or "")
    if entry_id and ("youtube" in extractor.lower() or re.fullmatch(r"[A-Za-z0-9_-]{11}", entry_id)):
        return f"https://www.youtube.com/watch?v={entry_id}"
    return value


class PlaylistProbeWorker(QObject):
    source_ready = Signal(dict)
    log = Signal(str)
    finished = Signal()

    @Slot(list, dict)
    def run(self, urls: List[str], config: Dict[str, Any]) -> None:
        texts = {str(k): str(v) for k, v in dict(config.get("texts", {})).items()}
        parent_item_id = config.get("target_parent_id")
        playlist_allowed = bool(config.get("playlist_allowed", True))

        try:
            yt_dlp = importlib.import_module("yt_dlp")
        except Exception as exc:
            message = render(texts, "worker_ytdlp_unavailable", error=exc)
            self.log.emit(f"[{timestamp()}] {message}")
            for url in urls:
                self.source_ready.emit({"type": "single", "url": url, "title": "", "target_parent_id": parent_item_id})
            self.finished.emit()
            return

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
            "noplaylist": not playlist_allowed,
        }

        for url in urls:
            self.log.emit(f"[{timestamp()}] {render(texts, 'log_loading_sources', url=url)}")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as exc:
                self.log.emit(f"[{timestamp()}] {render(texts, 'log_source_error', url=url, error=str(exc).strip())}")
                self.source_ready.emit({"type": "single", "url": url, "title": "", "target_parent_id": parent_item_id})
                continue

            if isinstance(info, dict) and info.get("_type") in {"playlist", "multi_video"} and info.get("entries"):
                entries: List[Dict[str, str]] = []
                for entry in info.get("entries") or []:
                    if not isinstance(entry, dict):
                        continue
                    entry_url = _entry_url(entry, info)
                    if not entry_url:
                        continue
                    entries.append({"url": entry_url, "title": str(entry.get("title") or "")})
                if entries:
                    self.source_ready.emit(
                        {
                            "type": "playlist",
                            "url": url,
                            "title": str(info.get("title") or ""),
                            "entries": entries,
                            "target_parent_id": parent_item_id,
                        }
                    )
                    self.log.emit(
                        f"[{timestamp()}] {render(texts, 'log_loaded_playlist', title=str(info.get('title') or url), count=len(entries))}"
                    )
                    continue

            title = str(info.get("title") or "") if isinstance(info, dict) else ""
            source_url = str(info.get("webpage_url") or url) if isinstance(info, dict) else url
            self.source_ready.emit({"type": "single", "url": source_url, "title": title, "target_parent_id": parent_item_id})
            self.log.emit(f"[{timestamp()}] {render(texts, 'log_loaded_url', title=title or source_url)}")

        self.finished.emit()


def _audio_args(target_ext: str, bitrate: Optional[str]) -> List[str]:
    base = ["-vn", "-map_metadata", "0"]
    if target_ext == "mp3":
        args = base + ["-acodec", "libmp3lame", "-b:a", f"{bitrate or '320'}k"]
        return args
    if target_ext == "ogg":
        args = base + ["-acodec", "libvorbis", "-b:a", f"{bitrate or '320'}k"]
        return args
    if target_ext == "aac":
        args = base + ["-acodec", "aac", "-b:a", f"{bitrate or '320'}k"]
        return args
    if target_ext == "wav":
        return base + ["-acodec", "pcm_s16le", "-f", "wav"]
    if target_ext == "wma":
        args = base + ["-acodec", "wmav2", "-b:a", f"{bitrate or '320'}k", "-f", "asf"]
        return args
    raise ValueError(target_ext)


def _video_args(target_ext: str) -> List[str]:
    if target_ext == "mkv":
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k"]
    if target_ext == "mp4":
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    if target_ext == "mov":
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k"]
    if target_ext == "avi":
        return ["-c:v", "mpeg4", "-q:v", "3", "-c:a", "mp3", "-b:a", "192k"]
    raise ValueError(target_ext)


class DownloadWorker(QObject):
    item_update = Signal(int, dict)
    log = Signal(str)
    finished = Signal()
    current_row_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._cancel_all = False
        self._paused = False
        self._current_process: subprocess.Popen | None = None

    @Slot()
    def stop(self) -> None:
        self._cancel_all = True
        self._paused = False
        process = self._current_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    @Slot()
    def toggle_pause(self) -> None:
        self._paused = not self._paused

    def _ffmpeg_executable(self, name: str) -> str:
        return shutil.which(name) or name

    def _probe_duration(self, source_path: str) -> Optional[float]:
        ffprobe = self._ffmpeg_executable("ffprobe")
        command = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            source_path,
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
            value = float((completed.stdout or "").strip())
            return value if value > 0 else None
        except Exception:
            return None

    def _run_ffmpeg_cancellable(self, item_id: int, source_path: str, target_path: str, args: List[str]) -> None:
        ffmpeg = self._ffmpeg_executable("ffmpeg")
        duration = self._probe_duration(source_path)
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-nostats",
            "-progress",
            "pipe:1",
            "-i",
            source_path,
            *args,
            target_path,
        ]
        started_at = time.monotonic()
        last_progress = -1.0
        self.item_update.emit(item_id, {"status": "processing", "progress": 0.0, "speed": "", "eta": "", "output": target_path})
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._current_process = process
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                if self._cancel_all:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    raise Cancelled()
                line = raw_line.strip()
                if not line.startswith("out_time_ms=") or not duration:
                    continue
                try:
                    out_time_ms = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                current_seconds = out_time_ms / 1_000_000
                progress = max(0.0, min(99.0, current_seconds / duration * 100.0))
                if progress - last_progress < 0.5:
                    continue
                last_progress = progress
                elapsed = max(0.1, time.monotonic() - started_at)
                eta_text = ""
                if progress > 0:
                    remaining = int(elapsed * (100.0 - progress) / progress)
                    minutes, seconds = divmod(remaining, 60)
                    hours, minutes = divmod(minutes, 60)
                    eta_text = f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:d}:{seconds:02d}"
                self.item_update.emit(item_id, {"status": "processing", "progress": progress, "eta": eta_text, "output": target_path})

            return_code = process.wait()
            if self._cancel_all:
                raise Cancelled()
            if return_code != 0:
                raise RuntimeError(f"ffmpeg exited with code {return_code}")
            self.item_update.emit(item_id, {"status": "processing", "progress": 100.0, "eta": "", "output": target_path})
        finally:
            self._current_process = None

    @Slot(list, dict)
    def run(self, jobs: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
        self._cancel_all = False
        self._paused = False
        texts = {str(k): str(v) for k, v in dict(config.get("texts", {})).items()}

        try:
            tools = _load_ytdlp_tools()
        except Exception as exc:
            message = render(texts, "worker_ytdlp_unavailable", error=exc)
            for job in jobs:
                self.item_update.emit(int(job["item_id"]), {"status": "error", "error": message})
            self.log.emit(f"[{timestamp()}] {message}")
            self.finished.emit()
            return

        yt_dlp = tools["yt_dlp"]
        FFmpegPostProcessor = tools["FFmpegPostProcessor"]
        FFmpegPostProcessorError = tools["FFmpegPostProcessorError"]
        PostProcessingError = tools["PostProcessingError"]
        replace_extension = tools["replace_extension"]
        prepend_extension = tools["prepend_extension"]
        worker_self = self

        class AudioConvertPostProcessor(FFmpegPostProcessor):
            def __init__(self, downloader=None, target_ext: str = "mp3", bitrate: Optional[str] = "320"):
                super().__init__(downloader)
                self.target_ext = target_ext
                self.bitrate = bitrate

            def run(self, information):
                source_path = information["filepath"]
                source_ext = information.get("ext") or os.path.splitext(source_path)[1].lstrip(".")
                target_path = replace_extension(source_path, self.target_ext, source_ext)
                same_target = os.path.abspath(source_path) == os.path.abspath(target_path)
                temp_path = prepend_extension(source_path, "temp") if same_target else target_path
                try:
                    args = _audio_args(self.target_ext, self.bitrate)
                except ValueError as err:
                    raise PostProcessingError(render(texts, "worker_unsupported_audio", format=str(err)))
                self.to_screen(render(texts, "worker_audio_converting", format=self.target_ext.upper(), path=target_path))
                try:
                    worker_self._run_ffmpeg_cancellable(current["item_id"], source_path, temp_path, args)
                except Cancelled:
                    raise
                except Exception as err:
                    raise PostProcessingError(render(texts, "worker_audio_conversion_failed", error=str(err)))
                files_to_delete = []
                if same_target:
                    original_path = prepend_extension(source_path, "orig")
                    os.replace(source_path, original_path)
                    os.replace(temp_path, target_path)
                    files_to_delete.append(original_path)
                else:
                    files_to_delete.append(source_path)
                information["filepath"] = target_path
                information["ext"] = self.target_ext
                return files_to_delete, information

        class VideoConvertPostProcessor(FFmpegPostProcessor):
            def __init__(self, downloader=None, target_ext: str = "mp4"):
                super().__init__(downloader)
                self.target_ext = target_ext

            def run(self, information):
                source_path = information["filepath"]
                source_ext = information.get("ext") or os.path.splitext(source_path)[1].lstrip(".")
                if source_ext.lower() == self.target_ext.lower():
                    return [], information
                target_path = replace_extension(source_path, self.target_ext, source_ext)
                try:
                    args = _video_args(self.target_ext)
                except ValueError as err:
                    raise PostProcessingError(render(texts, "worker_unsupported_video", format=str(err)))
                self.to_screen(render(texts, "worker_video_converting", format=self.target_ext.upper(), path=target_path))
                try:
                    worker_self._run_ffmpeg_cancellable(current["item_id"], source_path, target_path, args)
                except Cancelled:
                    raise
                except Exception as err:
                    raise PostProcessingError(render(texts, "worker_video_conversion_failed", error=str(err)))
                information["filepath"] = target_path
                information["ext"] = self.target_ext
                return [source_path], information

        current = {"item_id": -1}

        def wait_if_paused(item_id: int) -> None:
            if self._paused:
                self.item_update.emit(item_id, {"status": "paused"})
                self.log.emit(f"[{timestamp()}] {render(texts, 'worker_paused')}")
            while self._paused and not self._cancel_all:
                time.sleep(0.2)
            if self._cancel_all:
                raise Cancelled()

        def progress_hook(data: Dict[str, Any]) -> None:
            item_id = current["item_id"]
            if self._cancel_all:
                raise Cancelled()
            wait_if_paused(item_id)
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                progress = (downloaded / total * 100.0) if total else 0.0
                self.item_update.emit(item_id, {
                    "status": "downloading",
                    "progress": float(progress),
                    "speed": _format_speed(data.get("speed")),
                    "eta": _format_eta(data.get("eta")),
                })
            elif status == "finished":
                filename = data.get("filename") or ""
                self.item_update.emit(item_id, {"status": "processing", "progress": 100.0, "output": filename})

        def postprocessor_hook(data: Dict[str, Any]) -> None:
            item_id = current["item_id"]
            info = data.get("info_dict") or {}
            filepath = info.get("filepath") or info.get("_filename") or ""
            if filepath:
                self.item_update.emit(item_id, {"output": filepath})
            if data.get("status") == "started":
                self.item_update.emit(item_id, {"status": "processing"})

        for job in jobs:
            if self._cancel_all:
                break
            item_id = int(job["item_id"])
            url = str(job["url"])
            folder = str(job["folder"])
            os.makedirs(folder, exist_ok=True)

            current["item_id"] = item_id
            self.current_row_changed.emit(item_id)
            self.item_update.emit(item_id, {"status": "starting", "progress": 0.0, "speed": "", "eta": "", "error": ""})
            self.log.emit(f"[{timestamp()}] {render(texts, 'worker_start_url', url=url)}")

            ydl_opts = dict(config["ydl_opts"])
            ydl_opts["outtmpl"] = safe_filename_template(folder, str(job.get("title") or ""))
            ydl_opts["progress_hooks"] = [progress_hook]
            ydl_opts["postprocessor_hooks"] = [postprocessor_hook]

            try:
                wait_if_paused(item_id)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if config["mode"] == "audio":
                        ydl.add_post_processor(
                            AudioConvertPostProcessor(
                                ydl,
                                target_ext=config["audio_format"],
                                bitrate=config["audio_bitrate"],
                            ),
                            when="post_process",
                        )
                    else:
                        ydl.add_post_processor(
                            VideoConvertPostProcessor(ydl, target_ext=config["video_format"]),
                            when="post_process",
                        )
                    info = ydl.extract_info(url, download=True)

                title = ""
                filepath = ""
                if isinstance(info, dict):
                    title = info.get("title") or ""
                    filepath = info.get("filepath") or info.get("_filename") or ""
                self.item_update.emit(item_id, {"title": title, "status": "done", "progress": 100.0, "output": filepath})
                self.log.emit(f"[{timestamp()}] {render(texts, 'worker_finished', title=title or url)}")
            except Cancelled:
                self.item_update.emit(item_id, {"status": "cancelled", "error": render(texts, "worker_cancelled", url=url)})
                self.log.emit(f"[{timestamp()}] {render(texts, 'worker_cancelled', url=url)}")
            except Exception as exc:
                message = str(exc).strip()
                self.item_update.emit(item_id, {"status": "error", "error": message})
                self.log.emit(f"[{timestamp()}] {render(texts, 'worker_error', url=url, error=message)}")

        self.finished.emit()
