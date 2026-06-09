from __future__ import annotations

import json
import os
import re
from typing import Dict

from app.config import SETTINGS_DIR
from app.themes.palette import DEFAULT_THEMES, THEME_KEYS

CUSTOM_THEME_FILE = os.path.join(SETTINGS_DIR, "custom_themes.json")


def is_hex_color(value: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", str(value).strip()))


def normalize_theme(data: Dict[str, str], fallback_name: str = "Original") -> Dict[str, str]:
    fallback = DEFAULT_THEMES.get(fallback_name, DEFAULT_THEMES["Original"])
    result = dict(fallback)
    for key in THEME_KEYS:
        value = str(data.get(key, fallback[key])).strip()
        result[key] = value if is_hex_color(value) else fallback[key]
    return result


def load_custom_themes() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(CUSTOM_THEME_FILE):
        return {}
    try:
        with open(CUSTOM_THEME_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    themes: Dict[str, Dict[str, str]] = {}
    for name, value in raw.items():
        name = str(name).strip()
        if not name or name in DEFAULT_THEMES or not isinstance(value, dict):
            continue
        themes[name] = normalize_theme({str(k): str(v) for k, v in value.items()})
    return themes


def save_custom_themes(themes: Dict[str, Dict[str, str]]) -> None:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(CUSTOM_THEME_FILE, "w", encoding="utf-8") as handle:
        json.dump(themes, handle, indent=2, ensure_ascii=False)


class ThemeManager:
    def __init__(self) -> None:
        self.custom_themes = load_custom_themes()

    def all_themes(self) -> Dict[str, Dict[str, str]]:
        merged = dict(DEFAULT_THEMES)
        merged.update(self.custom_themes)
        return merged

    def get(self, name: str) -> Dict[str, str]:
        return self.all_themes().get(name, DEFAULT_THEMES["Original"])

    def save_custom(self, name: str, data: Dict[str, str]) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("theme_error_missing_name")
        if clean_name in DEFAULT_THEMES:
            raise ValueError("theme_error_overwrite_default")
        self.custom_themes[clean_name] = normalize_theme(data)
        save_custom_themes(self.custom_themes)

    def delete_custom(self, name: str) -> None:
        if name not in self.custom_themes:
            raise ValueError("theme_error_delete_custom_only")
        self.custom_themes.pop(name, None)
        save_custom_themes(self.custom_themes)

    def reset_custom(self) -> None:
        self.custom_themes.clear()
        save_custom_themes(self.custom_themes)
