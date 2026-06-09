from __future__ import annotations

from typing import Dict


def make_stylesheet(theme: Dict[str, str]) -> str:
    text = theme.get("text", "#e7e7e7")
    surface = theme.get("surface", "#171a21")
    background = theme.get("background", "#0f1115")
    selection = theme.get("selection", "#2f6fed")
    border = theme.get("border", theme.get("overlay_border", "#2a2f3a"))
    hover = theme.get("button_hover", "#343b49")
    pressed = theme.get("button_pressed", "#212633")
    table = theme.get("table", surface)
    disabled_text = theme.get("disabled_text", "#888888")

    return f"""
    QWidget {{
        font-size: 12px;
        color: {text};
    }}
    QMainWindow, QDialog {{
        background: {background};
    }}
    QLabel {{
        color: {text};
    }}
    QLineEdit, QTextEdit, QComboBox, QListWidget {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 6px 8px;
        color: {text};
        selection-background-color: {selection};
        selection-color: #ffffff;
        min-height: 20px;
    }}
    QComboBox::drop-down {{
        border: 0px;
        width: 28px;
    }}
    QComboBox QAbstractItemView {{
        background: {surface};
        color: {text};
        selection-background-color: {selection};
        selection-color: #ffffff;
        border: 1px solid {border};
        outline: 0;
    }}

    QFileDialog {{
        background: {background};
        color: {text};
    }}
    QFileDialog QWidget {{
        background: {background};
        color: {text};
    }}
    QFileDialog QTreeView, QFileDialog QListView, QFileDialog QTableView,
    QTreeView, QTreeWidget, QListView {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        selection-background-color: {selection};
        selection-color: #ffffff;
        alternate-background-color: {background};
    }}
    QFileDialog QHeaderView::section {{
        background: {surface};
        color: {text};
        border: 0px;
        border-bottom: 1px solid {border};
        padding: 6px;
    }}
    QFileDialog QToolButton {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 4px;
    }}
    QFileDialog QToolButton:hover {{
        background: {hover};
    }}
    QFileDialog QComboBox, QFileDialog QLineEdit {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
    }}

    QPushButton {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 7px 12px;
        color: {text};
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: {hover};
    }}
    QPushButton:pressed {{
        background: {pressed};
    }}
    QPushButton:disabled {{
        color: {disabled_text};
        background: {pressed};
        border-color: {border};
    }}
    QToolTip {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
    }}

    QMenu {{
        background: {surface};
        color: {text};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        background: transparent;
        color: {text};
        padding: 7px 28px 7px 12px;
        min-width: 180px;
    }}
    QMenu::item:selected {{
        background: {selection};
        color: #ffffff;
    }}
    QMenu::item:disabled {{
        background: transparent;
        color: {disabled_text};
    }}
    QMenu::separator {{
        height: 1px;
        background: {border};
        margin: 4px 6px;
    }}
    QInputDialog, QMessageBox {{
        background: {background};
        color: {text};
    }}
    QInputDialog QLabel, QMessageBox QLabel {{
        color: {text};
    }}
    QGroupBox {{
        border: 1px solid {border};
        border-radius: 12px;
        margin-top: 10px;
        padding: 10px;
        background: transparent;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {text};
    }}
    QGroupBox#formatBox, QFrame#formatBox {{
        border: 1px solid {border};
        border-radius: 10px;
        margin-top: 0px;
        padding: 0px;
        background: transparent;
    }}
    QCheckBox {{
        spacing: 8px;
        color: {text};
        min-height: 20px;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid {border};
        border-radius: 3px;
        background: {surface};
    }}
    QCheckBox::indicator:checked {{
        background: {selection};
        border-color: {selection};
    }}
    QTableView, QTreeView, QTreeWidget {{
        background: {table};
        border: 1px solid {border};
        border-radius: 12px;
        gridline-color: {border};
        selection-background-color: {selection};
        selection-color: #ffffff;
        alternate-background-color: {surface};
    }}

    QTreeView::item, QTreeWidget::item, QTableView::item {{
        min-height: 24px;
        padding: 3px 4px;
        color: {text};
    }}
    QTreeView::item:selected, QTreeWidget::item:selected, QTableView::item:selected {{
        background: {selection};
        color: #ffffff;
    }}

    QHeaderView::section {{
        background: {surface};
        border: 0px;
        border-bottom: 1px solid {border};
        padding: 8px;
        color: {text};
        min-height: 18px;
    }}
    QProgressBar {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 9px;
        height: 14px;
        text-align: center;
        color: {text};
    }}
    QProgressBar::chunk {{
        border-radius: 9px;
        background: {selection};
    }}
    QScrollArea {{
        border: 1px solid {border};
        background: {background};
    }}
    """
