from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
    QVBoxLayout,
)

from app.themes.manager import ThemeManager, is_hex_color
from app.themes.palette import DEFAULT_THEMES, THEME_KEYS

HIDDEN_DEFAULT_THEMES = {"Original", "Light"}
THEME_ALIASES = {"Original": "Dunkel", "Light": "Hell"}


class ColorButton(QPushButton):
    def __init__(self, key: str, value: str, translator: Callable[[str], str]):
        super().__init__(value)
        self.key = key
        self.value = value
        self._tr = translator
        self.clicked.connect(self.pick_color)
        self.refresh()

    def refresh(self) -> None:
        text_color = "#ffffff"
        if self.value.lower() in {"#ffffff", "#f8fafc", "#fff9e9", "#fff1f5", "#f4f4f5"}:
            text_color = "#111827"
        self.setText(self.value)
        self.setStyleSheet(
            f"QPushButton {{ background: {self.value}; color: {text_color}; border: 1px solid #6b7280; border-radius: 6px; padding: 4px 7px; min-height: 24px; }}"
        )

    def pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.value), self, self._tr("choose_color"))
        if color.isValid():
            self.value = color.name()
            self.refresh()
            parent = self.parent()
            while parent is not None and not isinstance(parent, ThemeDialog):
                parent = parent.parent()
            if isinstance(parent, ThemeDialog):
                parent.update_preview_from_editor()


class ThemeDialog(QDialog):
    def __init__(
        self,
        manager: ThemeManager,
        current_theme: str,
        apply_callback: Callable[[str], None],
        translator: Callable[[str], str],
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        requested_theme = THEME_ALIASES.get(current_theme, current_theme)
        self.current_theme = requested_theme if requested_theme in manager.all_themes() else "Dunkel"
        self.apply_callback = apply_callback
        self._tr = translator
        self.color_buttons: Dict[str, ColorButton] = {}
        self.color_labels: Dict[str, QLabel] = {}
        self.theme_buttons: Dict[str, QPushButton] = {}

        self.setWindowTitle(self._tr("appearance_title"))
        self.resize(820, 520)
        self.setMinimumSize(760, 500)
        self.build_ui()
        self.load_theme(self.current_theme)
        self.refresh_theme_grid()

    def theme_display_name(self, name: str) -> str:
        if name in DEFAULT_THEMES:
            return self._tr(f"theme_{name.lower()}")
        return name

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        self.description = QLabel(self._tr("appearance_description"))
        self.description.setWordWrap(True)
        root.addWidget(self.description)

        self.suggestions_label = QLabel(self._tr("suggestions"))
        root.addWidget(self.suggestions_label)

        self.suggestions_widget = QWidget()
        self.suggestions_widget.setObjectName("themeSuggestions")
        self.suggestions_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.suggestions_layout = QGridLayout(self.suggestions_widget)
        self.suggestions_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestions_layout.setHorizontalSpacing(6)
        self.suggestions_layout.setVerticalSpacing(6)
        root.addWidget(self.suggestions_widget)

        self.custom_box = QGroupBox(self._tr("custom_colors"))
        custom_layout = QGridLayout(self.custom_box)
        custom_layout.setContentsMargins(18, 18, 18, 12)
        custom_layout.setHorizontalSpacing(8)
        custom_layout.setVerticalSpacing(7)

        for row, key in enumerate(THEME_KEYS):
            label = QLabel(self._tr(f"theme_key_{key}"))
            self.color_labels[key] = label
            color_button = ColorButton(key, "#ffffff", self._tr)
            self.color_buttons[key] = color_button
            custom_layout.addWidget(label, row, 0)
            custom_layout.addWidget(color_button, row, 1)

        self.preview = QLabel(self._tr("preview_text"))
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(90)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        custom_layout.addWidget(self.preview, 0, 2, 3, 1, Qt.AlignVCenter)
        custom_layout.setColumnStretch(2, 1)
        root.addWidget(self.custom_box, 0)

        bottom = QHBoxLayout()
        self.btn_reset_themes = QPushButton(self._tr("reset_themes"))
        self.btn_reset_editor = QPushButton(self._tr("reset"))
        self.btn_delete = QPushButton(self._tr("delete"))
        self.btn_save = QPushButton(self._tr("save"))
        self.btn_ok = QPushButton(self._tr("ok"))
        self.btn_cancel = QPushButton(self._tr("cancel"))

        bottom.addWidget(self.btn_reset_themes)
        bottom.addWidget(self.btn_reset_editor)
        bottom.addWidget(self.btn_delete)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_save)
        bottom.addWidget(self.btn_ok)
        bottom.addWidget(self.btn_cancel)
        root.addLayout(bottom)

        self.btn_reset_themes.clicked.connect(self.reset_custom_themes)
        self.btn_reset_editor.clicked.connect(lambda: self.load_theme(self.current_theme))
        self.btn_delete.clicked.connect(self.delete_current_theme)
        self.btn_save.clicked.connect(self.save_current_editor_as_theme)
        self.btn_ok.clicked.connect(self.accept_selected_theme)
        self.btn_cancel.clicked.connect(self.reject)

    def refresh_theme_grid(self) -> None:
        while self.suggestions_layout.count():
            item = self.suggestions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.theme_buttons.clear()

        themes = [(name, theme) for name, theme in self.manager.all_themes().items() if name not in HIDDEN_DEFAULT_THEMES]
        for index, (name, theme) in enumerate(themes):
            button = QPushButton(self.theme_display_name(name))
            button.setFixedHeight(38)
            button.setMinimumWidth(116)
            button.clicked.connect(lambda _checked=False, n=name: self.select_theme(n))
            self.theme_buttons[name] = button
            self.suggestions_layout.addWidget(button, index // 6, index % 6)
            self.style_theme_button(button, name, theme)

    def style_theme_button(self, button: QPushButton, name: str, theme: Dict[str, str]) -> None:
        selected = name == self.current_theme
        border_width = "3px" if selected else "1px"
        border_color = theme["selection"] if selected else theme["overlay_border"]
        button.setStyleSheet(
            f"QPushButton {{ background: {theme['surface']}; color: {theme['text']}; border: {border_width} solid {border_color}; border-radius: 7px; padding: 5px 8px; outline: none; }}"
            f"QPushButton:hover {{ border: 2px solid {theme['selection']}; }}"
        )

    def editor_theme(self) -> Dict[str, str]:
        return {key: button.value for key, button in self.color_buttons.items()}

    def load_theme(self, name: str) -> None:
        theme = self.manager.get(name)
        self.current_theme = name
        for key, value in theme.items():
            if key in self.color_buttons:
                self.color_buttons[key].value = value
                self.color_buttons[key].refresh()
        self.update_preview_from_editor()
        self.refresh_theme_grid()

    def select_theme(self, name: str) -> None:
        self.load_theme(name)

    def accept_selected_theme(self) -> None:
        if self.current_theme not in self.manager.all_themes():
            self.current_theme = "Dunkel"
        self.apply_callback(self.current_theme)
        self.accept()

    def update_preview_from_editor(self) -> None:
        theme = self.editor_theme()
        self.preview.setText(self._tr("preview_text"))
        self.preview.setStyleSheet(
            f"QLabel {{ background: {theme['surface']}; color: {theme['text']}; border: 1px solid {theme['overlay_border']}; border-left: 6px solid {theme['selection']}; border-right: 6px solid {theme['overlay_split']}; border-radius: 9px; padding: 8px; }}"
        )

    def validate_editor(self) -> Optional[Dict[str, str]]:
        data = self.editor_theme()
        invalid = [self._tr(f"theme_key_{key}") for key, value in data.items() if not is_hex_color(value)]
        if invalid:
            QMessageBox.warning(self, self._tr("invalid_colors_title"), self._tr("invalid_colors_msg", fields="\n".join(invalid)))
            return None
        return data

    def save_current_editor_as_theme(self) -> None:
        data = self.validate_editor()
        if data is None:
            return
        suggested = self.current_theme if self.current_theme not in self.manager.all_themes() else self._tr("default_custom_theme_name")
        name, ok = QInputDialog.getText(self, self._tr("save_theme_title"), self._tr("name_label"), text=suggested)
        if not ok or not name.strip():
            return
        try:
            self.manager.save_custom(name.strip(), data)
        except Exception as exc:
            QMessageBox.warning(self, self._tr("save_failed"), self._tr(str(exc)))
            return
        self.current_theme = name.strip()
        self.refresh_theme_grid()
        self.load_theme(self.current_theme)

    def delete_current_theme(self) -> None:
        if self.current_theme not in self.manager.custom_themes:
            QMessageBox.information(self, self._tr("delete_not_allowed_title"), self._tr("delete_not_allowed_msg"))
            return
        answer = QMessageBox.question(self, self._tr("delete_theme_title"), self._tr("delete_theme_msg", name=self.current_theme))
        if answer != QMessageBox.Yes:
            return
        try:
            self.manager.delete_custom(self.current_theme)
        except Exception as exc:
            QMessageBox.warning(self, self._tr("delete_failed"), self._tr(str(exc)))
            return
        self.current_theme = "Dunkel"
        self.load_theme("Dunkel")

    def reset_custom_themes(self) -> None:
        answer = QMessageBox.question(self, self._tr("reset_themes_confirm_title"), self._tr("reset_themes_confirm_msg"))
        if answer != QMessageBox.Yes:
            return
        self.manager.reset_custom()
        self.current_theme = "Dunkel"
        self.load_theme("Dunkel")
