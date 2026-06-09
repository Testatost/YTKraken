from __future__ import annotations

from typing import Dict, List, Tuple

EUROPEAN_LANGUAGES: List[Tuple[str, str]] = [
    ("sq", "Shqip"),
    ("be", "Беларуская"),
    ("bs", "Bosanski"),
    ("bg", "Български"),
    ("ca", "Català"),
    ("hr", "Hrvatski"),
    ("cs", "Čeština"),
    ("da", "Dansk"),
    ("nl", "Nederlands"),
    ("en", "English"),
    ("et", "Eesti"),
    ("fo", "Føroyskt"),
    ("fi", "Suomi"),
    ("fr", "Français"),
    ("gl", "Galego"),
    ("de", "Deutsch"),
    ("el", "Ελληνικά"),
    ("hu", "Magyar"),
    ("is", "Íslenska"),
    ("ga", "Gaeilge"),
    ("it", "Italiano"),
    ("lv", "Latviešu"),
    ("lt", "Lietuvių"),
    ("lb", "Lëtzebuergesch"),
    ("mk", "Македонски"),
    ("mt", "Malti"),
    ("no", "Norsk"),
    ("pl", "Polski"),
    ("pt", "Português"),
    ("ro", "Română"),
    ("rm", "Rumantsch"),
    ("ru", "Русский"),
    ("sr", "Српски"),
    ("sk", "Slovenčina"),
    ("sl", "Slovenščina"),
    ("es", "Español"),
    ("sv", "Svenska"),
    ("uk", "Українська"),
    ("cy", "Cymraeg"),
    ("eu", "Euskara"),
]

LANGUAGE_NAMES: Dict[str, str] = dict(EUROPEAN_LANGUAGES)
SUPPORTED_LANGUAGE_CODES = {code for code, _name in EUROPEAN_LANGUAGES}
DEFAULT_LANGUAGE = "de"
