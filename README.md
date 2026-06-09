# yt-dlp GUI

A modern desktop GUI for downloading and converting video and audio with [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), `FFmpeg`, and `PySide6`.

The application provides a clean queue-based workflow, playlist handling, format selection, quality presets, theme customization, language support, and FFmpeg-based media conversion.

## Features

- Add one or multiple links at once
- Queue-based download workflow
- Expandable playlist view with editable playlist entries
- Download selected playlist entries instead of the whole playlist
- Video download formats: `mp4`, `mkv`, `mov`, `avi`
- Audio download formats: `mp3`, `ogg`, `aac`, `wav`, `wma`
- Video quality presets from `360p` up to `4K`
- Audio bitrate presets from `96 kbps` up to `320 kbps`
- Best-available mode for automatic quality selection
- Per-entry output folder assignment
- Double-click queue entries to open the source URL
- Context menu for renaming, deleting, and downloading selected entries
- Built-in media conversion dialog powered by FFmpeg
- WebM conversion with VP8/VP9 codec selection
- Optional audio inclusion for WebM output
- Theme selector with custom theme creation
- Multi-language UI via the `translation` module
- Background processing with progress feedback
- Processing dialog with cancel support

## Requirements

### Runtime requirements

- Python 3.10 or newer
- FFmpeg and FFprobe

### Python packages

Install the required Python packages with:

```bash
pip install -r requirements.txt
```

A typical `requirements.txt` contains:

```txt
PySide6>=6.6
yt-dlp>=2024.0.0
```

## Installing FFmpeg

FFmpeg is required for audio extraction, format conversion, muxing, and post-processing.

### Fedora / Fedora KDE

On Fedora, FFmpeg is usually installed through RPM Fusion:

```bash
sudo dnf install -y \
  https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm

sudo dnf install -y ffmpeg ffmpeg-libs
```

Verify the installation:

```bash
ffmpeg -version
ffprobe -version
```

### Debian / Ubuntu / Linux Mint

```bash
sudo apt update
sudo apt install -y ffmpeg
```

### Arch Linux / EndeavourOS / Manjaro / CachyOS

```bash
sudo pacman -Syu ffmpeg
```

### Windows

Using winget:

```powershell
winget install --id Gyan.FFmpeg -e
```

Using Chocolatey:

```powershell
choco install ffmpeg
```

Using Scoop:

```powershell
scoop install ffmpeg
```

After installation, restart your terminal and verify:

```bash
ffmpeg -version
```

## Running from source

Clone or open the project folder, install the requirements, and start the application:

```bash
python main.py
```

If you use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Basic usage

1. Paste one or multiple supported media links into the input field.
2. Click **Add to queue**.
3. Select the download mode: **Video** or **Audio**.
4. Choose the target format and quality.
5. Select the output folder.
6. Click **Start**.

For playlists, the first item appears as the main queue entry. Additional playlist entries are shown as expandable child items. You can remove individual entries, rename them, assign folders, or download only selected items from the context menu.

## Format conversion

Use **Convert format** to convert existing local files with FFmpeg.

Supported conversion features include:

- Audio conversion to `mp3`, `ogg`, `aac`, `wav`, and `wma`
- Video conversion to common container formats
- WebM conversion with VP8 or VP9
- Optional audio inclusion for WebM
- Video quality scaling presets
- Output folder selection

## Legal notice

This application is intended for downloading and converting media that you own, that is publicly available for download, or that you are otherwise authorized to use. Always respect copyright law and the terms of service of the source platform.
