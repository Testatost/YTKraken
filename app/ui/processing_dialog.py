from __future__ import annotations

import math
import time
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class SpinnerWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(52, 52)

    def start(self) -> None:
        self._timer.start(70)

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 2 - 7
        base_color = self.palette().highlight().color()

        for index in range(12):
            alpha = int(45 + (index + 1) * 17)
            color = QColor(base_color)
            color.setAlpha(alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            angle = math.radians(self._angle - index * 30)
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            painter.drawEllipse(int(x - 3), int(y - 3), 6, 6)


class ProcessingDialog(QDialog):
    def __init__(self, tr: Callable[[str], str], cancel_callback: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tr = tr
        self._cancel_callback = cancel_callback
        self._started_at: Optional[float] = None
        self._active = False
        self._cancel_requested = False

        self.setWindowTitle(self._tr("processing_title"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(16)
        self.spinner = SpinnerWidget(self)
        text_col = QVBoxLayout()
        text_col.setSpacing(5)
        self.title_label = QLabel(self._tr("processing_message"))
        self.title_label.setObjectName("processingTitle")
        self.file_label = QLabel("")
        self.file_label.setWordWrap(True)
        self.progress_label = QLabel(self._tr("processing_unknown_eta"))
        self.elapsed_label = QLabel("")
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.file_label)
        text_col.addWidget(self.progress_label)
        text_col.addWidget(self.elapsed_label)
        top.addWidget(self.spinner, 0, Qt.AlignTop)
        top.addLayout(text_col, 1)
        root.addLayout(top)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.cancel_button = QPushButton(self._tr("processing_cancel"))
        self.cancel_button.clicked.connect(self.cancel_processing)
        button_row.addWidget(self.cancel_button)
        root.addLayout(button_row)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_elapsed)

    def start_processing(self, label: str) -> None:
        self._active = True
        self._cancel_requested = False
        self._started_at = time.monotonic()
        self.file_label.setText(self._tr("processing_current_file").format(file=label or "—"))
        self.progress_label.setText(self._tr("processing_unknown_eta"))
        self.elapsed_label.setText(self._tr("processing_elapsed").format(time="0:00"))
        self.cancel_button.setText(self._tr("processing_cancel"))
        self.cancel_button.setEnabled(True)
        self.spinner.start()
        self._timer.start(500)
        if not self.isVisible():
            self.show()

    def update_progress(self, progress: float | None = None, eta: str | None = None) -> None:
        if progress is None or progress <= 0:
            self.progress_label.setText(self._tr("processing_unknown_eta"))
            return
        progress_text = f"{progress:.1f}%"
        if eta:
            self.progress_label.setText(self._tr("processing_eta").format(progress=progress_text, eta=eta))
        else:
            self.progress_label.setText(self._tr("processing_progress").format(progress=progress_text))

    def finish_processing(self) -> None:
        self._active = False
        self._timer.stop()
        self.spinner.stop()
        self.hide()

    def cancel_processing(self) -> None:
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.cancel_button.setText(self._tr("processing_cancelling"))
        self.cancel_button.setEnabled(False)
        self._cancel_callback()
        self.finish_processing()

    def _update_elapsed(self) -> None:
        if self._started_at is None:
            return
        seconds = int(time.monotonic() - self._started_at)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            value = f"{hours:d}:{minutes:02d}:{seconds:02d}"
        else:
            value = f"{minutes:d}:{seconds:02d}"
        self.elapsed_label.setText(self._tr("processing_elapsed").format(time=value))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._active and not self._cancel_requested:
            self.cancel_processing()
            event.accept()
            return
        super().closeEvent(event)
