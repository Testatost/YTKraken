from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from app.translation.registry import EUROPEAN_LANGUAGES


class LanguageDialog(QDialog):
    def __init__(self, current_language: str, translator: Callable[[str], str], parent=None):
        super().__init__(parent)
        self._tr = translator
        self.current_language = current_language
        self.selected_language: Optional[str] = None
        self.setWindowTitle(self._tr("language_title"))
        self.resize(420, 470)

        root = QVBoxLayout(self)
        self.instruction = QLabel(self._tr("language_instruction"))
        self.instruction.setWordWrap(True)
        root.addWidget(self.instruction)

        self.list_widget = QListWidget()
        for code, name in EUROPEAN_LANGUAGES:
            item = QListWidgetItem(f"{name} ({code})")
            item.setData(256, code)
            self.list_widget.addItem(item)
            if code == current_language:
                self.list_widget.setCurrentItem(item)
        root.addWidget(self.list_widget, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_ok = QPushButton(self._tr("ok"))
        self.btn_cancel = QPushButton(self._tr("cancel"))
        buttons.addWidget(self.btn_ok)
        buttons.addWidget(self.btn_cancel)
        root.addLayout(buttons)

        self.list_widget.itemDoubleClicked.connect(lambda _item: self.apply_selection())
        self.btn_ok.clicked.connect(self.apply_selection)
        self.btn_cancel.clicked.connect(self.reject)

    def apply_selection(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_language = str(item.data(256))
        self.accept()
