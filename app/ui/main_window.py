from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QByteArray, QSize, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QInputDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from app.config import (
    DEFAULT_DOWNLOAD_DIR,
    asset_path,
    decode_qbytearray,
    encode_qbytearray,
    load_settings,
    save_settings,
)
from app.core.utils import split_urls, timestamp
from app.core.workers import DownloadWorker, PlaylistProbeWorker
from app.core.ytdlp_options import (
    AUDIO_FORMATS,
    AUDIO_QUALITY_VALUES,
    VIDEO_FORMATS,
    VIDEO_QUALITY_VALUES,
    build_audio_bitrate,
    build_ydl_options,
)
from app.models.queue_table_model import COLUMN_KEYS, ITEM_ID_ROLE, QueueTableModel
from app.themes.manager import ThemeManager
from app.themes.stylesheet import make_stylesheet
from app.translation.manager import Translator
from app.ui.conversion_dialog import ConversionDialog
from app.ui.language_dialog import LanguageDialog
from app.ui.processing_dialog import ProcessingDialog
from app.ui.theme_dialog import ThemeDialog


class MainWindow(QMainWindow):
    start_downloads = Signal(list, dict)
    load_sources = Signal(list, dict)
    stop_downloads = Signal()
    pause_downloads = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.settings: Dict[str, object] = load_settings()
        self.translator = Translator(str(self.settings.get("language", "de")))
        self.theme_manager = ThemeManager()
        self.current_theme = str(self.settings.get("theme", "Original"))
        if self.current_theme not in self.theme_manager.all_themes():
            self.current_theme = "Original"

        self.model = QueueTableModel(self.tr)
        self._tree_items_by_id: Dict[int, QTreeWidgetItem] = {}
        self._is_running = False
        self._is_paused = False
        self._current_row: Optional[int] = None
        self._is_loading_sources = False
        self._processing_dialog: Optional[ProcessingDialog] = None
        self._ui_ready = False

        self.thread = QThread(self)
        self.worker = DownloadWorker()
        self.worker.moveToThread(self.thread)
        self.thread.start()

        self.probe_thread = QThread(self)
        self.probe_worker = PlaylistProbeWorker()
        self.probe_worker.moveToThread(self.probe_thread)
        self.probe_thread.start()

        self.start_downloads.connect(self.worker.run, Qt.QueuedConnection)
        self.load_sources.connect(self.probe_worker.run, Qt.QueuedConnection)
        self.stop_downloads.connect(self.worker.stop, Qt.QueuedConnection)
        self.pause_downloads.connect(self.worker.toggle_pause, Qt.QueuedConnection)
        self.worker.item_update.connect(self.on_item_update)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.current_row_changed.connect(self.on_current_row_changed)
        self.probe_worker.source_ready.connect(self.on_source_ready)
        self.probe_worker.log.connect(self.append_log)
        self.probe_worker.finished.connect(self.on_sources_loaded)

        self.build_ui()
        self.apply_theme(self.current_theme, persist=False)
        self.retranslate_ui()
        self.restore_window_state()
        self._ui_ready = True
        self.on_mode_changed()

    def tr(self, key: str, **values) -> str:
        return self.translator.t(key, **values)

    def build_ui(self) -> None:
        width = int(self.settings.get("window_width", 1360) or 1360)
        height = int(self.settings.get("window_height", 900) or 900)
        self.resize(max(width, 1180), max(height, 680))
        self.setMinimumSize(1180, 680)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(14, 10, 14, 10)
        root_layout.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(8)

        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_panel.setMinimumWidth(500)
        right_panel.setMaximumWidth(560)
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)

        self.links_box = QGroupBox()
        links_layout = QVBoxLayout(self.links_box)
        links_layout.setContentsMargins(18, 16, 18, 12)
        input_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.btn_paste = QPushButton()
        self.btn_add = QPushButton()
        input_row.addWidget(self.url_input, 1)
        input_row.addWidget(self.btn_paste)
        input_row.addWidget(self.btn_add)
        links_layout.addLayout(input_row)
        left.addWidget(self.links_box)

        self.table = QTreeWidget()
        self.table.setColumnCount(len(COLUMN_KEYS))
        self.table.setHeaderLabels([self.tr(key) for key in COLUMN_KEYS])
        self.table.setSelectionBehavior(QTreeWidget.SelectRows)
        self.table.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.table.setUniformRowHeights(False)
        self.table.setExpandsOnDoubleClick(False)
        self.table.setIndentation(22)
        self.table.setItemsExpandable(True)
        self.table.header().setSectionResizeMode(QHeaderView.Interactive)
        self.table.header().setStretchLastSection(True)
        self.table.setRootIsDecorated(True)
        self.table.setColumnWidth(0, 390)
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 105)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 75)
        self.table.itemDoubleClicked.connect(self.open_queue_source)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_queue_context_menu)
        left.addWidget(self.table, 1)

        queue_buttons = QHBoxLayout()
        queue_buttons.setSpacing(10)
        self.btn_remove = QPushButton()
        self.btn_clear = QPushButton()
        self.btn_set_folder = QPushButton()
        queue_buttons.addWidget(self.btn_remove)
        queue_buttons.addWidget(self.btn_clear)
        queue_buttons.addWidget(self.btn_set_folder)
        queue_buttons.addStretch(1)
        left.addLayout(queue_buttons)

        self.global_progress_label = QLabel()
        self.global_progress = QProgressBar()
        self.global_progress.setRange(0, 100)
        left.addWidget(self.global_progress_label)
        left.addWidget(self.global_progress)

        top_row = QHBoxLayout()
        top_row.addStretch(1)
        self.btn_theme = QPushButton()
        self.btn_language = QPushButton()
        self.btn_theme.setIcon(QIcon(asset_path("icons", "appearance.png")))
        self.btn_language.setIcon(QIcon(asset_path("icons", "language.png")))
        self.btn_theme.setIconSize(QSize(22, 22))
        self.btn_language.setIconSize(QSize(22, 22))
        self.btn_theme.setFixedSize(44, 34)
        self.btn_language.setFixedSize(44, 34)
        top_row.addWidget(self.btn_theme)
        top_row.addWidget(self.btn_language)
        right.addLayout(top_row)

        self.options_box = QGroupBox()
        options_layout = QGridLayout(self.options_box)
        options_layout.setContentsMargins(18, 18, 18, 14)
        options_layout.setHorizontalSpacing(16)
        options_layout.setVerticalSpacing(3)
        options_layout.setColumnStretch(0, 1)
        options_layout.setColumnStretch(1, 1)
        options_layout.setColumnMinimumWidth(0, 210)
        options_layout.setColumnMinimumWidth(1, 220)

        def add_label_widget(label: QLabel, widget: QWidget, label_row: int, widget_row: int, column: int) -> None:
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            options_layout.addWidget(label, label_row, column)
            options_layout.addWidget(widget, widget_row, column)

        def make_format_box(formats: List[str], group: QButtonGroup) -> QFrame:
            box = QFrame()
            box.setObjectName("formatBox")
            box.setFixedSize(220, 78)
            box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            outer = QVBoxLayout(box)
            outer.setContentsMargins(10, 8, 10, 8)
            outer.setSpacing(6)

            group.setExclusive(True)

            columns = 3
            slot_width = 58
            slot_height = 23
            rows: List[QHBoxLayout] = []

            for _ in range(2):
                row_widget = QWidget()
                row_widget.setFixedHeight(slot_height)
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(8)
                rows.append(row)
                outer.addWidget(row_widget)

            for index in range(columns * 2):
                slot = QWidget()
                slot.setFixedSize(slot_width, slot_height)
                slot_layout = QHBoxLayout(slot)
                slot_layout.setContentsMargins(0, 0, 0, 0)
                slot_layout.setSpacing(0)

                if index < len(formats):
                    checkbox = QCheckBox(formats[index])
                    checkbox.setFixedHeight(slot_height)
                    checkbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    group.addButton(checkbox)
                    slot_layout.addWidget(checkbox, 0, Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    slot_layout.addStretch(1)

                rows[index // columns].addWidget(slot)

            return box

        self.mode_label = QLabel()
        self.mode_combo = QComboBox()
        self.video_format_label = QLabel()
        self.video_format_group = QButtonGroup(self)
        self.video_format_box = make_format_box(VIDEO_FORMATS, self.video_format_group)

        self.video_quality_label = QLabel()
        self.video_quality_combo = QComboBox()
        self.audio_format_label = QLabel()
        self.audio_format_group = QButtonGroup(self)
        self.audio_format_box = make_format_box(AUDIO_FORMATS, self.audio_format_group)

        self.audio_quality_label = QLabel()
        self.audio_quality_combo = QComboBox()

        add_label_widget(self.mode_label, self.mode_combo, 0, 1, 0)
        add_label_widget(self.video_format_label, self.video_format_box, 0, 1, 1)
        add_label_widget(self.video_quality_label, self.video_quality_combo, 2, 3, 0)
        add_label_widget(self.audio_format_label, self.audio_format_box, 2, 3, 1)
        add_label_widget(self.audio_quality_label, self.audio_quality_combo, 4, 5, 0)

        self.playlist_checkbox = QCheckBox()
        self.playlist_checkbox.setChecked(bool(self.settings.get("playlist_allowed", True)))
        options_layout.addWidget(self.playlist_checkbox, 6, 0, 1, 2)

        self.output_label = QLabel()
        self.output_edit = QLineEdit(str(self.settings.get("download_dir", DEFAULT_DOWNLOAD_DIR)))
        self.btn_browse = QPushButton()
        out_container = QWidget()
        out_row = QHBoxLayout(out_container)
        out_row.setContentsMargins(0, 0, 0, 0)
        out_row.setSpacing(8)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(self.btn_browse)
        self.output_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        options_layout.addWidget(self.output_label, 7, 0, 1, 2)
        options_layout.addWidget(out_container, 8, 0, 1, 2)
        right.addWidget(self.options_box)

        self.actions_box = QGroupBox()
        actions_layout = QVBoxLayout(self.actions_box)
        actions_layout.setContentsMargins(18, 18, 18, 14)
        actions_layout.setSpacing(7)
        self.btn_start = QPushButton()
        self.btn_pause = QPushButton()
        self.btn_stop = QPushButton()
        self.btn_convert = QPushButton()
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        actions_layout.addWidget(self.btn_start)
        actions_layout.addWidget(self.btn_pause)
        actions_layout.addWidget(self.btn_stop)
        actions_layout.addWidget(self.btn_convert)
        right.addWidget(self.actions_box)

        self.log_box = QGroupBox()
        log_layout = QVBoxLayout(self.log_box)
        log_layout.setContentsMargins(18, 18, 18, 14)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(74)
        self.log_view.setMaximumHeight(110)
        log_layout.addWidget(self.log_view)
        right.addWidget(self.log_box)
        right.addStretch(1)

        root_layout.addLayout(left, 1)
        root_layout.addWidget(right_panel, 0)

        self.apply_default_widget_sizes()
        self.apply_saved_control_values()
        self.connect_signals()

    def apply_default_widget_sizes(self) -> None:
        for widget in self.findChildren(QComboBox):
            widget.setMinimumHeight(34)
        for widget in self.findChildren(QLineEdit):
            widget.setMinimumHeight(34)
        for widget in self.findChildren(QPushButton):
            if widget not in {self.btn_theme, self.btn_language}:
                widget.setMinimumHeight(34)
        for box in (self.video_format_box, self.audio_format_box):
            box.setFixedSize(220, 78)
        self.options_box.setMinimumHeight(330)
        self.actions_box.setMinimumHeight(170)
        self.log_box.setMinimumHeight(122)
        self.log_view.setMinimumHeight(72)
        self.log_view.setMaximumHeight(96)
        self.global_progress.setMaximumHeight(18)

    def connect_signals(self) -> None:
        self.btn_add.clicked.connect(self.add_from_input)
        self.btn_paste.clicked.connect(self.add_from_clipboard)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_queue)
        self.btn_set_folder.clicked.connect(self.set_folder_for_selection)
        self.btn_browse.clicked.connect(self.pick_output_dir)
        self.btn_start.clicked.connect(self.start_queue)
        self.btn_pause.clicked.connect(self.pause_queue)
        self.btn_stop.clicked.connect(self.stop_queue)
        self.btn_theme.clicked.connect(self.open_theme_dialog)
        self.btn_language.clicked.connect(self.open_language_dialog)
        self.btn_convert.clicked.connect(self.open_conversion_dialog)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.mode_combo.currentIndexChanged.connect(self.save_ui_settings)
        self.video_quality_combo.currentIndexChanged.connect(self.save_ui_settings)
        self.audio_quality_combo.currentIndexChanged.connect(self.save_ui_settings)
        self.playlist_checkbox.stateChanged.connect(self.save_ui_settings)
        self.output_edit.editingFinished.connect(self.save_ui_settings)
        for button in self.video_format_group.buttons():
            button.toggled.connect(self.save_ui_settings)
        for button in self.audio_format_group.buttons():
            button.toggled.connect(self.save_ui_settings)

    def select_group_button(self, group: QButtonGroup, value: str) -> None:
        fallback = None
        for button in group.buttons():
            if fallback is None:
                fallback = button
            if button.text() == value:
                button.setChecked(True)
                return
        if fallback is not None:
            fallback.setChecked(True)

    def apply_saved_control_values(self) -> None:
        self.select_group_button(self.video_format_group, str(self.settings.get("video_format", "mp4")))
        self.select_group_button(self.audio_format_group, str(self.settings.get("audio_format", "mp3")))

    def restore_window_state(self) -> None:
        encoded = self.settings.get("window_geometry")
        decoded = decode_qbytearray(encoded)
        if decoded:
            self.restoreGeometry(QByteArray(decoded))
        if self.width() < 1180 or self.height() < 680:
            self.resize(max(self.width(), 1180), max(self.height(), 680))

    def save_window_state(self) -> None:
        self.settings["window_width"] = self.width()
        self.settings["window_height"] = self.height()
        self.settings["window_geometry"] = encode_qbytearray(self.saveGeometry())
        save_settings(self.settings)

    def _queue_item_values(self, item) -> List[str]:
        return [
            item.url,
            item.title,
            self.tr(f"status_{item.status}"),
            f"{item.progress:.1f}%",
            item.speed,
            item.eta,
            item.output,
            item.output_dir or self.tr("default_folder"),
        ]

    def _expanded_queue_ids(self) -> set[int]:
        return {
            item_id
            for item_id, tree_item in self._tree_items_by_id.items()
            if tree_item.isExpanded()
        }

    def _make_tree_item(self, item) -> QTreeWidgetItem:
        values = self._queue_item_values(item)
        tree_item = QTreeWidgetItem(values)
        tree_item.setData(0, ITEM_ID_ROLE, item.item_id)
        for column, value in enumerate(values):
            tree_item.setToolTip(column, item.error if item.error else value)
        return tree_item

    def _append_tree_children(self, parent_tree_item: QTreeWidgetItem, parent_queue_item) -> None:
        for child in parent_queue_item.children:
            child_tree_item = self._make_tree_item(child)
            parent_tree_item.addChild(child_tree_item)
            self._tree_items_by_id[child.item_id] = child_tree_item
            self._append_tree_children(child_tree_item, child)

    def refresh_queue_view(self, keep_expanded: bool = True) -> None:
        expanded_ids = self._expanded_queue_ids() if keep_expanded else set()
        selected_ids = {item.item_id for item in self.selected_items()} if hasattr(self, "table") else set()

        self.table.setUpdatesEnabled(False)
        self.table.clear()
        self._tree_items_by_id.clear()
        self.table.setHeaderLabels([self.tr(key) for key in COLUMN_KEYS])

        for item in self.model.items:
            tree_item = self._make_tree_item(item)
            self.table.addTopLevelItem(tree_item)
            self._tree_items_by_id[item.item_id] = tree_item
            self._append_tree_children(tree_item, item)

        for item_id in expanded_ids:
            tree_item = self._tree_items_by_id.get(item_id)
            if tree_item is not None:
                tree_item.setExpanded(True)

        for item_id in selected_ids:
            tree_item = self._tree_items_by_id.get(item_id)
            if tree_item is not None:
                tree_item.setSelected(True)

        self.table.setUpdatesEnabled(True)
        self.table.viewport().update()

    def update_queue_tree_item(self, item_id: int) -> None:
        item = self.model.get_item(item_id)
        tree_item = self._tree_items_by_id.get(item_id)
        if item is None or tree_item is None:
            self.refresh_queue_view()
            return
        values = self._queue_item_values(item)
        for column, value in enumerate(values):
            tree_item.setText(column, value)
            tree_item.setToolTip(column, item.error if item.error else value)

    def expand_and_scroll_to_item(self, item) -> None:
        tree_item = self._tree_items_by_id.get(item.item_id)
        if tree_item is None:
            return
        current = tree_item
        while current is not None:
            current.setExpanded(True)
            current = current.parent()
        self.table.scrollToItem(tree_item)

    def set_combo_items(self, combo: QComboBox, items: List[tuple[str, str]], current_data: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for text, value in items:
            combo.addItem(text, value)
        index = combo.findData(current_data)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("app_title"))
        self.links_box.setTitle(self.tr("links_group"))
        self.url_input.setPlaceholderText(self.tr("url_placeholder"))
        self.btn_paste.setText(self.tr("paste"))
        self.btn_add.setText(self.tr("add_queue"))
        self.btn_remove.setText(self.tr("remove_selected"))
        self.btn_clear.setText(self.tr("clear_all"))
        self.btn_set_folder.setText(self.tr("set_folder"))
        self.global_progress_label.setText(self.tr("global_progress"))
        self.options_box.setTitle(self.tr("options"))
        self.mode_label.setText(self.tr("mode"))
        current_mode = str(self.settings.get("mode", self.mode_combo.currentData() or "video"))
        self.set_combo_items(self.mode_combo, [(self.tr("video"), "video"), (self.tr("audio"), "audio")], current_mode)
        self.video_format_label.setText(self.tr("video_format"))
        self.audio_format_label.setText(self.tr("audio_format"))
        self.video_quality_label.setText(self.tr("video_quality"))
        self.audio_quality_label.setText(self.tr("audio_quality"))
        current_video_quality = str(self.settings.get("video_quality", self.video_quality_combo.currentData() or "1080p"))
        current_audio_quality = str(self.settings.get("audio_quality", self.audio_quality_combo.currentData() or "320"))
        self.set_combo_items(
            self.video_quality_combo,
            [(self.tr("quality_best") if value == "best" else (self.tr("quality_4k") if value == "2160p" else value), value) for value in VIDEO_QUALITY_VALUES],
            current_video_quality,
        )
        self.set_combo_items(
            self.audio_quality_combo,
            [(self.tr("quality_best") if value == "best" else f"{value} {self.tr('kbps')}", value) for value in AUDIO_QUALITY_VALUES],
            current_audio_quality,
        )
        self.playlist_checkbox.setText(self.tr("playlist_allowed"))
        self.output_label.setText(self.tr("output_dir"))
        self.btn_browse.setText(self.tr("browse"))
        self.actions_box.setTitle(self.tr("actions"))
        self.btn_start.setText(self.tr("start"))
        self.btn_pause.setText(self.tr("pause"))
        self.btn_stop.setText(self.tr("stop"))
        self.btn_convert.setText(self.tr("convert_format"))
        self.btn_theme.setToolTip(self.tr("appearance"))
        self.btn_language.setToolTip(self.tr("language"))
        self.log_box.setTitle(self.tr("log"))
        self.log_view.setPlaceholderText(self.tr("log_placeholder"))
        self.model.set_translator(self.tr)
        self.refresh_queue_view()
        self.on_mode_changed()

    def apply_theme(self, name: str, persist: bool = True) -> None:
        self.current_theme = name if name in self.theme_manager.all_themes() else "Original"
        theme = self.theme_manager.get(self.current_theme)
        QApplication.instance().setStyle("Fusion")
        self.setStyleSheet(make_stylesheet(theme))
        if self._processing_dialog is not None:
            self._processing_dialog.setStyleSheet(self.styleSheet())
        self.apply_default_widget_sizes()
        if persist:
            self.settings["theme"] = self.current_theme
            save_settings(self.settings)

    def selected_button_text(self, group: QButtonGroup, fallback: str) -> str:
        button = group.checkedButton()
        return button.text() if button is not None else fallback

    @Slot()
    def save_ui_settings(self) -> None:
        if not self._ui_ready:
            return
        self.settings["mode"] = str(self.mode_combo.currentData() or "video")
        self.settings["video_format"] = self.selected_button_text(self.video_format_group, "mp4")
        self.settings["audio_format"] = self.selected_button_text(self.audio_format_group, "mp3")
        self.settings["video_quality"] = str(self.video_quality_combo.currentData() or "1080p")
        self.settings["audio_quality"] = str(self.audio_quality_combo.currentData() or "320")
        self.settings["playlist_allowed"] = self.playlist_checkbox.isChecked()
        self.settings["download_dir"] = self.output_edit.text().strip() or DEFAULT_DOWNLOAD_DIR
        save_settings(self.settings)

    def playlist_edit_parent_id(self) -> Optional[int]:
        selected = self.selected_items()
        if len(selected) != 1:
            return None
        item = selected[0]
        root = self.model.root_for_item(item)
        if root.children or item.parent is not None:
            return root.item_id
        return None

    def enqueue_urls(self, urls: List[str]) -> None:
        clean = [url for url in urls if url.strip()]
        if not clean:
            return
        self._is_loading_sources = True
        self.btn_add.setEnabled(False)
        self.btn_paste.setEnabled(False)
        self.load_sources.emit(
            clean,
            {
                "target_parent_id": self.playlist_edit_parent_id(),
                "playlist_allowed": self.playlist_checkbox.isChecked(),
                "texts": self.translated_worker_texts(),
            },
        )

    def add_from_input(self) -> None:
        urls = split_urls(self.url_input.text())
        if urls:
            self.url_input.clear()
        self.enqueue_urls(urls)

    def add_from_clipboard(self) -> None:
        self.enqueue_urls(split_urls(QGuiApplication.clipboard().text() or ""))

    def selected_items(self) -> List:
        items = []
        for tree_item in self.table.selectedItems():
            item_id = tree_item.data(0, ITEM_ID_ROLE)
            try:
                item = self.model.get_item(int(item_id))
            except (TypeError, ValueError):
                item = None
            if item is not None:
                items.append(item)
        return items

    def selected_rows(self) -> List[int]:
        rows = []
        for tree_item in self.table.selectedItems():
            top = tree_item
            while top.parent() is not None:
                top = top.parent()
            row = self.table.indexOfTopLevelItem(top)
            if row >= 0:
                rows.append(row)
        return sorted(set(rows))

    def remove_selected(self) -> None:
        self.model.remove_items(self.selected_items())
        self.refresh_queue_view()
        self.recalc_global_progress()

    def clear_queue(self) -> None:
        if self._is_running:
            QMessageBox.warning(self, self.tr("running_title"), self.tr("running_clear_msg"))
            return
        self.model.clear()
        self.refresh_queue_view(keep_expanded=False)
        self.global_progress.setValue(0)

    def _current_home_dir(self) -> str:
        return str(Path.home())

    def _safe_directory(self, preferred: str | None = None) -> str:
        """Return a readable start directory for folder dialogs.

        KDE/Fedora builds should never depend on a hard-coded user path. If a
        saved path from another system/user is invalid, the current user's home
        directory is used.
        """
        candidate = Path(str(preferred or "")).expanduser()
        if candidate.is_dir():
            return str(candidate)
        downloads = Path.home() / "Downloads"
        if downloads.is_dir():
            return str(downloads)
        return self._current_home_dir()

    def choose_directory(self, title: str, preferred: str | None = None) -> str:
        start_dir = self._current_home_dir()
        dialog = QFileDialog(self, title, start_dir)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setDirectory(start_dir)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() == QFileDialog.Accepted:
            selected = dialog.selectedFiles()
            if selected:
                return selected[0]
        return ""

    def set_folder_for_selection(self) -> None:
        items = self.selected_items()
        if not items:
            return
        folder = self.choose_directory(self.tr("choose_folder"), self._current_home_dir())
        if folder:
            self.model.set_output_dir(items, folder)
            self.refresh_queue_view()

    def pick_output_dir(self) -> None:
        folder = self.choose_directory(self.tr("choose_folder"), self.output_edit.text() or self._current_home_dir())
        if folder:
            self.output_edit.setText(folder)
            self.save_ui_settings()

    def on_mode_changed(self) -> None:
        is_audio = self.mode_combo.currentData() == "audio"
        self.video_format_box.setEnabled(not is_audio)
        self.video_quality_combo.setEnabled(not is_audio)
        self.audio_format_box.setEnabled(is_audio)
        self.audio_quality_combo.setEnabled(True)
        self.save_ui_settings()

    def translated_worker_texts(self) -> Dict[str, str]:
        return {
            key: self.tr(key)
            for key in (
                "worker_ytdlp_unavailable",
                "worker_start_url",
                "worker_finished",
                "worker_cancelled",
                "worker_error",
                "worker_audio_converting",
                "worker_audio_conversion_failed",
                "worker_video_converting",
                "worker_video_conversion_failed",
                "worker_unsupported_audio",
                "worker_unsupported_video",
                "worker_paused",
                "log_loading_sources",
                "log_loaded_playlist",
                "log_loaded_url",
                "log_source_error",
            )
        }

    def selected_items_for_download(self) -> List:
        """Return exactly the selected queue entries, never implicit playlist children."""
        unique = {}
        for item in self.selected_items():
            unique[item.item_id] = item
        return sorted(unique.values(), key=lambda entry: self.model.item_number(entry.item_id))

    def build_download_config(self, output_dir: str) -> dict:
        mode = "audio" if self.mode_combo.currentData() == "audio" else "video"
        video_quality = str(self.video_quality_combo.currentData() or "1080p")
        audio_quality = str(self.audio_quality_combo.currentData() or "320")
        ydl_opts = build_ydl_options(mode, video_quality, False)
        return {
            "mode": mode,
            "video_format": self.selected_button_text(self.video_format_group, "mp4"),
            "audio_format": self.selected_button_text(self.audio_format_group, "mp3"),
            "audio_bitrate": build_audio_bitrate(audio_quality),
            "ydl_opts": ydl_opts,
            "texts": self.translated_worker_texts(),
        }

    def start_download_jobs(self, jobs: List[dict], config: dict, mode: str, output_dir: str, selected_only: bool = False) -> None:
        if not jobs:
            QMessageBox.information(self, self.tr("all_done_title"), self.tr("all_done_msg"))
            return

        self._is_running = True
        self._is_paused = False
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        log_key = "log_start_selected" if selected_only else "log_start_queue"
        self.append_log(self.tr(log_key, mode=self.tr(mode), folder=output_dir, count=len(jobs), time=timestamp()))
        self.start_downloads.emit(jobs, config)

    def start_selected_downloads(self) -> None:
        if self._is_running:
            return

        items = self.selected_items_for_download()
        if not items:
            QMessageBox.information(self, self.tr("no_selection_title"), self.tr("no_selection_msg"))
            return

        output_dir = self.output_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, self.tr("missing_folder_title"), self.tr("missing_folder_msg"))
            return
        os.makedirs(output_dir, exist_ok=True)
        self.save_ui_settings()

        config = self.build_download_config(output_dir)
        mode = str(config["mode"])
        jobs = []
        for item in items:
            if item.status != "done":
                self.model.update_item(item.item_id, status="waiting", progress=0.0, speed="", eta="", error="")
                self.update_queue_tree_item(item.item_id)
                jobs.append({
                    "item_id": item.item_id,
                    "url": item.url,
                    "folder": self.model.effective_output_dir(item, output_dir),
                    "title": item.title,
                })

        self.start_download_jobs(jobs, config, mode, output_dir, selected_only=True)

    def rename_queue_item(self, item) -> None:
        current_title = item.title or item.url
        new_title, accepted = QInputDialog.getText(
            self,
            self.tr("rename_dialog_title"),
            self.tr("rename_dialog_label"),
            text=current_title,
        )
        if not accepted:
            return
        cleaned = new_title.strip()
        if not cleaned:
            return
        self.model.update_item(item.item_id, title=cleaned)
        self.update_queue_tree_item(item.item_id)

    def open_queue_context_menu(self, position) -> None:
        tree_item = self.table.itemAt(position)
        if tree_item is None:
            return

        item_id = tree_item.data(0, ITEM_ID_ROLE)
        try:
            item = self.model.get_item(int(item_id))
        except (TypeError, ValueError):
            item = None
        if item is None:
            return

        if not tree_item.isSelected():
            self.table.clearSelection()
            tree_item.setSelected(True)
            self.table.setCurrentItem(tree_item)

        menu = QMenu(self)
        rename_action = menu.addAction(self.tr("context_rename"))
        delete_action = menu.addAction(self.tr("delete"))
        download_action = menu.addAction(self.tr("context_download_selected"))
        download_action.setEnabled(not self._is_running and bool(self.selected_items_for_download()))
        delete_action.setEnabled(not self._is_running)
        rename_action.setEnabled(not self._is_running)

        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen == rename_action:
            self.rename_queue_item(item)
        elif chosen == delete_action:
            self.remove_selected()
        elif chosen == download_action:
            self.start_selected_downloads()

    def start_queue(self) -> None:
        if self._is_running:
            return
        if not self.model.items:
            QMessageBox.information(self, self.tr("empty_queue_title"), self.tr("empty_queue_msg"))
            return

        output_dir = self.output_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, self.tr("missing_folder_title"), self.tr("missing_folder_msg"))
            return
        os.makedirs(output_dir, exist_ok=True)
        self.save_ui_settings()

        config = self.build_download_config(output_dir)
        mode = str(config["mode"])

        jobs = []
        for item in self.model.iter_items():
            if item.status != "done":
                self.model.update_item(item.item_id, status="waiting", progress=0.0, speed="", eta="", error="")
                self.update_queue_tree_item(item.item_id)
                jobs.append({
                    "item_id": item.item_id,
                    "url": item.url,
                    "folder": self.model.effective_output_dir(item, output_dir),
                    "title": item.title,
                })

        self.start_download_jobs(jobs, config, mode, output_dir, selected_only=False)

    def pause_queue(self) -> None:
        if not self._is_running:
            return
        self._is_paused = not self._is_paused
        self.pause_downloads.emit()
        self.append_log(self.tr("log_paused") if self._is_paused else self.tr("log_resumed"))

    def stop_queue(self) -> None:
        if not self._is_running:
            return
        self.stop_downloads.emit()
        self.append_log(self.tr("log_stopped"))

    def open_queue_source(self, tree_item: QTreeWidgetItem, column: int = 0) -> None:
        item_id = tree_item.data(0, ITEM_ID_ROLE) if tree_item is not None else None
        try:
            item = self.model.get_item(int(item_id))
        except (TypeError, ValueError):
            item = None
        if item is not None and item.url:
            QDesktopServices.openUrl(QUrl(item.url))

    def open_theme_dialog(self) -> None:
        dialog = ThemeDialog(self.theme_manager, self.current_theme, self.apply_theme, self.tr, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()

    def open_language_dialog(self) -> None:
        dialog = LanguageDialog(self.translator.language, self.tr, self)
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec() == LanguageDialog.Accepted and dialog.selected_language:
            self.set_language(dialog.selected_language)

    def set_language(self, language: str) -> None:
        self.translator.set_language(language)
        self.settings["language"] = self.translator.language
        save_settings(self.settings)
        self.retranslate_ui()

    def open_conversion_dialog(self) -> None:
        dialog = ConversionDialog(self.output_edit.text().strip() or DEFAULT_DOWNLOAD_DIR, self.tr, self)
        dialog.setStyleSheet(self.styleSheet())
        dialog.exec()

    @Slot(dict)
    def on_source_ready(self, payload: dict) -> None:
        target_parent_id = payload.get("target_parent_id")
        added_root = None
        if payload.get("type") == "playlist":
            added_root = self.model.add_playlist(list(payload.get("entries") or []), parent_item_id=target_parent_id)
        else:
            added = self.model.add_entries(
                [{"url": str(payload.get("url") or ""), "title": str(payload.get("title") or "")}],
                parent_item_id=target_parent_id,
            )
            added_root = added[0] if added else None

        self.refresh_queue_view(keep_expanded=True)
        if added_root is not None:
            root = self.model.root_for_item(added_root)
            self.expand_and_scroll_to_item(root)
        self.recalc_global_progress()

    @Slot()
    def on_sources_loaded(self) -> None:
        self._is_loading_sources = False
        self.btn_add.setEnabled(True)
        self.btn_paste.setEnabled(True)

    def ensure_processing_dialog(self) -> ProcessingDialog:
        if self._processing_dialog is None:
            self._processing_dialog = ProcessingDialog(self.tr, self.cancel_processing_dialog, self)
            self._processing_dialog.setStyleSheet(self.styleSheet())
        return self._processing_dialog

    def show_processing_dialog(self, item_id: int, fields: dict) -> None:
        item = self.model.get_item(item_id)
        label = ""
        if item is not None:
            label = item.title or item.url
        label = str(fields.get("output") or label)
        dialog = self.ensure_processing_dialog()
        if not dialog.isVisible():
            dialog.start_processing(label)
        else:
            dialog.file_label.setText(self.tr("processing_current_file").format(file=label or "—"))
        progress = fields.get("progress")
        try:
            progress_value = float(progress) if progress is not None else None
        except (TypeError, ValueError):
            progress_value = None
        dialog.update_progress(progress_value, str(fields.get("eta") or ""))

    def close_processing_dialog(self) -> None:
        if self._processing_dialog is not None and self._processing_dialog.isVisible():
            self._processing_dialog.finish_processing()

    def cancel_processing_dialog(self) -> None:
        if self._is_running:
            self.stop_downloads.emit()
            self.append_log(self.tr("processing_cancelled_by_user"))

    @Slot(int, dict)
    def on_item_update(self, item_id: int, fields: dict) -> None:
        self.model.update_item(item_id, **fields)
        self.update_queue_tree_item(item_id)
        self.recalc_global_progress()
        status = fields.get("status")
        if status == "processing":
            self.show_processing_dialog(item_id, fields)
        elif status in {"done", "error", "cancelled", "downloading", "waiting", "starting"}:
            if status != "processing":
                self.close_processing_dialog()
        if fields.get("error"):
            self.append_log(self.tr("log_error_row", row=self.model.item_number(item_id), error=fields["error"]))

    @Slot(int)
    def on_current_row_changed(self, item_id: int) -> None:
        self._current_row = item_id

    @Slot()
    def on_worker_finished(self) -> None:
        self._is_running = False
        self._is_paused = False
        self._current_row = None
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.close_processing_dialog()
        self.recalc_global_progress()
        self.append_log(self.tr("log_done_stopped"))

    def recalc_global_progress(self) -> None:
        items = list(self.model.iter_items())
        if not items:
            self.global_progress.setValue(0)
            return
        value = int(round(sum(item.progress for item in items) / len(items)))
        self.global_progress.setValue(value)

    def append_log(self, text: str) -> None:
        self.log_view.append(text)

    def closeEvent(self, event) -> None:
        self.save_ui_settings()
        self.save_window_state()
        if self._is_running:
            self.stop_downloads.emit()
        self.thread.quit()
        self.thread.wait(1500)
        self.probe_thread.quit()
        self.probe_thread.wait(1500)
        super().closeEvent(event)

def run() -> None:
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
