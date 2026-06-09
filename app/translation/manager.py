from __future__ import annotations

import importlib
from typing import Any, Dict

from app.translation.registry import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGE_CODES


class Translator:
    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = DEFAULT_LANGUAGE
        self._strings: Dict[str, str] = {}
        self.set_language(language)

    def set_language(self, language: str) -> None:
        code = language if language in SUPPORTED_LANGUAGE_CODES else DEFAULT_LANGUAGE
        module = importlib.import_module(f"app.translation.{code}")
        strings = getattr(module, "TRANSLATIONS", {})
        self.language = code
        self._strings = {str(key): str(value) for key, value in strings.items()}

    def t(self, key: str, **values: Any) -> str:
        text = self._strings.get(key, key)
        if values:
            try:
                return text.format(**values)
            except Exception:
                return text
        return text

    def __call__(self, key: str, **values: Any) -> str:
        return self.t(key, **values)
