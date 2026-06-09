from __future__ import annotations

import os
from typing import Callable, List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.config import DEFAULT_DOWNLOAD_DIR
from app.core.ffmpeg_convert import AUDIO_TARGETS, VIDEO_TARGETS, WEBM_CODECS, ConversionWorker


class ConversionDialog(QDialog):
    start_conversion = Signal(list, dict)

    def __init__(self, default_output_dir: str = DEFAULT_DOWNLOAD_DIR, translator: Callable[[str], str] | None = None, parent=None):
        super().__init__(parent)
        self._tr = translator or (lambda key, **values: key.format(**values) if values else key)
        self.setWindowTitle(self._tr("conversion_title"))
        self.resize(760, 540)
        self.thread = QThread(self)
        self.worker = ConversionWorker()
        self.worker.moveToThread(self.thread)
        self.thread.start()
        self.start_conversion.connect(self.worker.run, Qt.QueuedConnection)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)

        self._running = False
        self.build_ui(default_output_dir)
        self.on_kind_changed()

    def build_ui(self, default_output_dir: str) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        self.files_box = QGroupBox(self._tr("files"))
        files_layout = QVBoxLayout(self.files_box)
        self.file_list = QListWidget()
        files_layout.addWidget(self.file_list, 1)
        file_buttons = QHBoxLayout()
        self.btn_add_files = QPushButton(self._tr("add_files"))
        self.btn_remove_files = QPushButton(self._tr("remove_selected"))
        file_buttons.addWidget(self.btn_add_files)
        file_buttons.addWidget(self.btn_remove_files)
        file_buttons.addStretch(1)
        files_layout.addLayout(file_buttons)
        root.addWidget(self.files_box, 1)

        self.options_box = QGroupBox(self._tr("target_format"))
        options_layout = QVBoxLayout(self.options_box)

        row1 = QHBoxLayout()
        self.kind_label = QLabel(self._tr("type"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItem(self._tr("audio"), "audio")
        self.kind_combo.addItem(self._tr("video"), "video")
        self.format_label = QLabel(self._tr("format"))
        self.target_combo = QComboBox()
        row1.addWidget(self.kind_label)
        row1.addWidget(self.kind_combo)
        row1.addWidget(self.format_label)
        row1.addWidget(self.target_combo)
        options_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.audio_bitrate_label = QLabel(self._tr("audio_bitrate"))
        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(["320", "256", "192", "160", "128", "96"])

        self.video_quality_label = QLabel(self._tr("video_quality"))
        self.video_quality_combo = QComboBox()
        self.video_quality_combo.addItem(self._tr("quality_original"), "original")
        self.video_quality_combo.addItem("4K / 2160p", "2160")
        self.video_quality_combo.addItem("1440p", "1440")
        self.video_quality_combo.addItem("1080p", "1080")
        self.video_quality_combo.addItem("720p", "720")
        self.video_quality_combo.addItem("480p", "480")
        self.video_quality_combo.addItem("360p", "360")

        self.webm_codec_label = QLabel(self._tr("webm_codec"))
        self.webm_codec_combo = QComboBox()
        self.webm_codec_combo.addItems(WEBM_CODECS)
        self.include_audio_checkbox = QCheckBox(self._tr("include_audio"))
        self.include_audio_checkbox.setChecked(True)

        row2.addWidget(self.audio_bitrate_label)
        row2.addWidget(self.audio_bitrate_combo)
        row2.addWidget(self.video_quality_label)
        row2.addWidget(self.video_quality_combo)
        row2.addWidget(self.webm_codec_label)
        row2.addWidget(self.webm_codec_combo)
        row2.addWidget(self.include_audio_checkbox)
        row2.addStretch(1)
        options_layout.addLayout(row2)

        out_row = QHBoxLayout()
        self.output_dir_label = QLabel(self._tr("output_folder"))
        self.output_dir_edit = QLineEdit(default_output_dir)
        self.btn_browse = QPushButton(self._tr("browse"))
        out_row.addWidget(self.output_dir_label)
        out_row.addWidget(self.output_dir_edit, 1)
        out_row.addWidget(self.btn_browse)
        options_layout.addLayout(out_row)
        root.addWidget(self.options_box)

        action_row = QHBoxLayout()
        self.btn_convert = QPushButton(self._tr("convert"))
        self.btn_close = QPushButton(self._tr("close"))
        action_row.addStretch(1)
        action_row.addWidget(self.btn_convert)
        action_row.addWidget(self.btn_close)
        root.addLayout(action_row)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_remove_files.clicked.connect(self.remove_selected_files)
        self.btn_browse.clicked.connect(self.pick_output_dir)
        self.btn_convert.clicked.connect(self.start)
        self.btn_close.clicked.connect(self.accept)
        self.kind_combo.currentIndexChanged.connect(self.on_kind_changed)
        self.target_combo.currentTextChanged.connect(self.on_target_changed)

    def add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, self._tr("choose_files"))
        for path in files:
            if path and not self.file_list.findItems(path, Qt.MatchExactly):
                self.file_list.addItem(path)

    def remove_selected_files(self) -> None:
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def pick_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, self._tr("choose_output_folder"), self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)

    def files(self) -> List[str]:
        return [self.file_list.item(index).text() for index in range(self.file_list.count())]

    def on_kind_changed(self) -> None:
        target_kind = self.kind_combo.currentData() or "audio"
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItems(AUDIO_TARGETS if target_kind == "audio" else VIDEO_TARGETS)
        self.target_combo.blockSignals(False)
        self.on_target_changed(self.target_combo.currentText())

    def on_target_changed(self, text: str) -> None:
        target_kind = self.kind_combo.currentData() or "audio"
        is_audio = target_kind == "audio"
        is_video = target_kind == "video"
        is_webm = is_video and text == "webm"

        # Audio settings are only relevant when the conversion target is audio.
        self.audio_bitrate_label.setVisible(is_audio)
        self.audio_bitrate_combo.setVisible(is_audio)
        self.audio_bitrate_combo.setEnabled(is_audio)

        # Video quality / resolution is only relevant for video conversion targets.
        self.video_quality_label.setVisible(is_video)
        self.video_quality_combo.setVisible(is_video)
        self.video_quality_combo.setEnabled(is_video)

        # WebM-specific options must not be visible for normal audio/video formats.
        self.webm_codec_label.setVisible(is_webm)
        self.webm_codec_combo.setVisible(is_webm)
        self.webm_codec_combo.setEnabled(is_webm)
        self.include_audio_checkbox.setVisible(is_webm)
        self.include_audio_checkbox.setEnabled(is_webm)

    def start(self) -> None:
        if self._running:
            return
        files = self.files()
        if not files:
            QMessageBox.information(self, self._tr("no_files_title"), self._tr("no_files_msg"))
            return
        missing = [path for path in files if not os.path.exists(path)]
        if missing:
            QMessageBox.warning(self, self._tr("file_missing_title"), self._tr("file_missing_msg", files="\n".join(missing)))
            return
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, self._tr("output_folder_missing_title"), self._tr("output_folder_missing_msg"))
            return

        self._running = True
        self.btn_convert.setEnabled(False)
        options = {
            "kind": self.kind_combo.currentData() or "audio",
            "target": self.target_combo.currentText(),
            "output_dir": output_dir,
            "bitrate": self.audio_bitrate_combo.currentText(),
            "video_height": self.video_quality_combo.currentData() or "original",
            "include_audio": self.include_audio_checkbox.isChecked(),
            "webm_codec": self.webm_codec_combo.currentText(),
            "texts": {
                "conversion_log_converting": self._tr("conversion_log_converting"),
                "conversion_log_error_code": self._tr("conversion_log_error_code"),
                "conversion_log_done": self._tr("conversion_log_done"),
                "conversion_log_error": self._tr("conversion_log_error"),
                "worker_unsupported_audio": self._tr("worker_unsupported_audio"),
                "worker_unsupported_video": self._tr("worker_unsupported_video"),
            },
        }
        self.start_conversion.emit(files, options)

    def append_log(self, text: str) -> None:
        self.log_view.append(text)

    def on_finished(self) -> None:
        self._running = False
        self.btn_convert.setEnabled(True)
        self.append_log(self._tr("conversion_finished"))

    def closeEvent(self, event) -> None:
        self.thread.quit()
        self.thread.wait(1500)
        super().closeEvent(event)
