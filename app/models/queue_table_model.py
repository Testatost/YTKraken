from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from app.models.queue_item import QueueItem

COLUMN_KEYS = [
    "table_url",
    "table_title",
    "table_status",
    "table_progress",
    "table_speed",
    "table_eta",
    "table_file",
    "table_folder",
]

ITEM_ID_ROLE = int(Qt.UserRole) + 1


class QueueTableModel(QStandardItemModel):
    """Reliable tree model for the queue.

    Earlier versions used a hand-written QAbstractItemModel. On some KDE/Qt
    combinations the data was present, but QTreeView did not repaint inserted
    playlist rows reliably. QStandardItemModel is used here deliberately: it is
    the native Qt tree model and is much less fragile for expandable queues.
    """

    def __init__(self, translator: Callable[[str], str], items: Optional[List[QueueItem]] = None):
        super().__init__()
        self.root_item = QueueItem(url="", title="")
        self.root_item.children = []
        self._tr = translator
        self._items_by_id: Dict[int, QueueItem] = {}
        self._row_items_by_id: Dict[int, List[QStandardItem]] = {}
        self.setColumnCount(len(COLUMN_KEYS))
        self._apply_headers()
        if items:
            for item in items:
                self.root_item.add_child(item)
                self.invisibleRootItem().appendRow(self._make_row(item))
                self._append_existing_children(item)
        self._rebuild_id_map()

    @property
    def items(self) -> List[QueueItem]:
        return self.root_item.children

    def _apply_headers(self) -> None:
        self.setHorizontalHeaderLabels([self._tr(key) for key in COLUMN_KEYS])

    def set_translator(self, translator: Callable[[str], str]) -> None:
        self._tr = translator
        self._apply_headers()
        for item in self.iter_items():
            self._refresh_row(item)

    def emit_all_changed(self) -> None:
        for item in self.iter_items():
            self._refresh_row(item)

    def force_refresh(self) -> None:
        """Force QTreeView to re-read the currently stored rows."""
        for item in self.iter_items():
            self._refresh_row(item)
        self.layoutChanged.emit()

    def _display_values(self, item: QueueItem) -> List[str]:
        return [
            item.url,
            item.title,
            self._tr(f"status_{item.status}"),
            f"{item.progress:.1f}%",
            item.speed,
            item.eta,
            item.output,
            item.output_dir or self._tr("default_folder"),
        ]

    def _make_row(self, item: QueueItem) -> List[QStandardItem]:
        row: List[QStandardItem] = []
        for value in self._display_values(item):
            cell = QStandardItem(value)
            cell.setEditable(False)
            cell.setData(item.item_id, ITEM_ID_ROLE)
            row.append(cell)
        self._row_items_by_id[item.item_id] = row
        return row

    def _append_existing_children(self, item: QueueItem) -> None:
        parent_std = self._std_item_for_item(item)
        if parent_std is None:
            return
        for child in item.children:
            parent_std.appendRow(self._make_row(child))
            self._append_existing_children(child)

    def _std_item_for_item(self, item: QueueItem) -> Optional[QStandardItem]:
        row = self._row_items_by_id.get(item.item_id)
        return row[0] if row else None

    def _parent_std_for_item(self, parent_item: QueueItem) -> QStandardItem:
        if parent_item is self.root_item:
            return self.invisibleRootItem()
        parent_std = self._std_item_for_item(parent_item)
        return parent_std if parent_std is not None else self.invisibleRootItem()

    def _refresh_row(self, item: QueueItem) -> None:
        row = self._row_items_by_id.get(item.item_id)
        if not row:
            return
        values = self._display_values(item)
        for column, value in enumerate(values):
            if column < len(row):
                row[column].setText(value)
                row[column].setToolTip(item.error if item.error else value)

    def _rebuild_id_map(self) -> None:
        self._items_by_id.clear()
        for item in self.iter_items():
            self._items_by_id[item.item_id] = item

    def _drop_row_mapping(self, item: QueueItem) -> None:
        for child in list(item.children):
            self._drop_row_mapping(child)
        self._items_by_id.pop(item.item_id, None)
        self._row_items_by_id.pop(item.item_id, None)

    def item_from_index(self, index: QModelIndex) -> Optional[QueueItem]:
        if not index.isValid():
            return None
        item_id = index.data(ITEM_ID_ROLE)
        if item_id is None:
            return None
        try:
            return self._items_by_id.get(int(item_id))
        except (TypeError, ValueError):
            return None

    def index_for_item(self, item: QueueItem, column: int = 0) -> QModelIndex:
        row = self._row_items_by_id.get(item.item_id)
        if not row or column < 0 or column >= len(row):
            return QModelIndex()
        return row[column].index()

    def get_item(self, item_id: int) -> Optional[QueueItem]:
        return self._items_by_id.get(item_id)

    def iter_items(self) -> Iterable[QueueItem]:
        def walk(items: Sequence[QueueItem]) -> Iterable[QueueItem]:
            for item in items:
                yield item
                yield from walk(item.children)
        yield from walk(self.root_item.children)

    def item_number(self, item_id: int) -> int:
        for number, item in enumerate(self.iter_items(), start=1):
            if item.item_id == item_id:
                return number
        return item_id

    def root_for_item(self, item: QueueItem) -> QueueItem:
        current = item
        while current.parent is not None and current.parent is not self.root_item:
            current = current.parent
        return current

    def add_items(self, urls: List[str], parent_item_id: Optional[int] = None) -> List[QueueItem]:
        entries = [{"url": url.strip(), "title": ""} for url in urls if url.strip()]
        return self.add_entries(entries, parent_item_id=parent_item_id)

    def add_entries(self, entries: List[dict], parent_item_id: Optional[int] = None) -> List[QueueItem]:
        clean = [entry for entry in entries if str(entry.get("url", "")).strip()]
        if not clean:
            return []

        parent_item = self.get_item(parent_item_id) if parent_item_id else self.root_item
        if parent_item is None:
            parent_item = self.root_item
        parent_std = self._parent_std_for_item(parent_item)

        new_items: List[QueueItem] = []
        for entry in clean:
            item = QueueItem(
                url=str(entry.get("url", "")).strip(),
                title=str(entry.get("title", "") or ""),
            )
            parent_item.add_child(item)
            parent_std.appendRow(self._make_row(item))
            new_items.append(item)

        self._rebuild_id_map()
        self.force_refresh()
        return new_items

    def add_playlist(
        self,
        entries: List[dict],
        parent_item_id: Optional[int] = None,
        target_parent_id: Optional[int] = None,
    ) -> Optional[QueueItem]:
        if parent_item_id is None:
            parent_item_id = target_parent_id
        clean = [entry for entry in entries if str(entry.get("url", "")).strip()]
        if not clean:
            return None

        if parent_item_id:
            added = self.add_entries(clean, parent_item_id=parent_item_id)
            return added[0] if added else None

        parent_entry = clean[0]
        parent_item = QueueItem(
            url=str(parent_entry.get("url", "")).strip(),
            title=str(parent_entry.get("title", "") or ""),
        )
        self.root_item.add_child(parent_item)
        self.invisibleRootItem().appendRow(self._make_row(parent_item))

        parent_std = self._std_item_for_item(parent_item)
        if parent_std is not None:
            for child_entry in clean[1:]:
                child = QueueItem(
                    url=str(child_entry.get("url", "")).strip(),
                    title=str(child_entry.get("title", "") or ""),
                )
                parent_item.add_child(child)
                parent_std.appendRow(self._make_row(child))

        self._rebuild_id_map()
        self.force_refresh()
        return parent_item

    def remove_items(self, items: List[QueueItem]) -> None:
        if not items:
            return

        selected: List[QueueItem] = []
        for item in items:
            if any(item.is_descendant_of(other) for other in items):
                continue
            selected.append(item)

        for item in sorted(selected, key=lambda value: self.item_number(value.item_id), reverse=True):
            parent_item = item.parent or self.root_item
            parent_std = self._parent_std_for_item(parent_item)
            try:
                row = parent_item.children.index(item)
            except ValueError:
                continue
            parent_item.children.pop(row)
            parent_std.removeRow(row)
            item.parent = None
            self._drop_row_mapping(item)

        self._rebuild_id_map()
        self.force_refresh()

    def remove_rows(self, rows: List[int]) -> None:
        items = [self.root_item.children[row] for row in sorted(set(rows)) if 0 <= row < len(self.root_item.children)]
        self.remove_items(items)

    def clear(self) -> None:
        self.root_item.children.clear()
        self._items_by_id.clear()
        self._row_items_by_id.clear()
        super().clear()
        self.setColumnCount(len(COLUMN_KEYS))
        self._apply_headers()

    def set_output_dir(self, items: List[QueueItem], folder: str) -> None:
        changed: List[QueueItem] = []

        def apply(item: QueueItem) -> None:
            item.output_dir = folder
            changed.append(item)
            for child in item.children:
                apply(child)

        for item in items:
            apply(item)

        for item in changed:
            self._refresh_row(item)

    def effective_output_dir(self, item: QueueItem, default_folder: str) -> str:
        current: Optional[QueueItem] = item
        while current is not None and current is not self.root_item:
            if current.output_dir:
                return current.output_dir
            current = current.parent
        return default_folder

    def update_item(self, item_id: int, **fields) -> None:
        item = self.get_item(item_id)
        if item is None:
            return
        for key, value in fields.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self._refresh_row(item)
