"""Minimal translation support for player-visible messages.

Only the event/status message line and the GUI (Pyglet) stage-select
screen are translated. Status-bar abbreviations and item names (LVL,
HRS, Sword, Poisoned, ...) are intentionally left in English: they sit
in fixed-width layouts (especially in the Blessed terminal frontend)
that a longer or double-width Japanese string could break.

Messages are keyed by their English source text (or, for messages with
a number, by a `str.format` template). Translating happens at display
time rather than at `defs.py` definition time, since the language is
only known after argument parsing.

Catalogs live as JSON files under `locales/<lang>.json` (a mapping of
English source text to its translation), loaded lazily and cached.
"""

import json
import os
from importlib import resources
from typing import Dict, Optional

_SUPPORTED_LANGUAGES = ("ja",)

_catalog_cache: Dict[str, Dict[str, str]] = {}

_lang = "en"


def _load_catalog(lang: str) -> Dict[str, str]:
    if lang not in _catalog_cache:
        catalog: Dict[str, str] = {}
        try:
            path = resources.files(__package__).joinpath("locales", f"{lang}.json")
            catalog = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            pass
        _catalog_cache[lang] = catalog
    return _catalog_cache[lang]


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in _SUPPORTED_LANGUAGES else "en"


def detect_language() -> str:
    """Guess a language from the environment's locale variables."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value.lower().startswith("ja"):
            return "ja"
    return "en"


def t(text: Optional[str]) -> Optional[str]:
    """Translate a fixed message string (or `str.format` template) for the
    current language. Falls back to `text` unchanged if untranslated."""
    if text is None or _lang == "en":
        return text
    return _load_catalog(_lang).get(text, text)
