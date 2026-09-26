"""Minimal translation support for player-visible messages.

Only the event/status message line and the GUI (Pyglet) stage-select
screen are translated. Status-bar abbreviations and item names (LVL,
TURN, Sword, Poisoned, ...) are intentionally left in English: they sit
in fixed-width layouts (especially in the Blessed terminal frontend)
that a longer or double-width Japanese string could break.

Messages are keyed by their English source text (or, for messages with
a number, by a `str.format` template). Translating happens at display
time rather than at `defs.py` definition time, since the language is
only known after argument parsing.

Catalogs live as JSON files under `locales/<tag>.json` (a mapping of
English source text to its translation), loaded lazily and cached.
Adding a language is normally just adding a JSON file: see
`locale_candidates()` for how a detected tag falls back to a file that
exists (e.g. "zh-TW" -> zh-TW.json, then zh.json, then en.json).

This design (BCP-47-ish tags with a fallback chain, plus native
per-OS UI-language lookups instead of a locale-data library like
Babel) follows dev-notes/handoff-lang-auto-detection-20260921.md and
the proof-of-concept in dev-samples/detect_locale.py.
"""

import json
import os
import plistlib
import subprocess
import sys
from importlib import resources
from typing import Dict, List, Optional

_catalog_cache: Dict[str, Optional[Dict[str, str]]] = {}

_lang = "en"


def normalize_locale_tag(value: str) -> str:
    """Normalize a raw locale/language string to a loose BCP-47-ish tag.

    Not a full BCP-47 parser -- just enough to turn things like
    "ja_JP.UTF-8" or "Ja-jp" into "ja-JP" for matching translation
    resource filenames (see locale_candidates()).
    """
    value = value.strip()
    if not value:
        return ""

    value = value.split(".", 1)[0]  # ja_JP.UTF-8 -> ja_JP
    value = value.split("@", 1)[0]  # ja_JP@euro  -> ja_JP
    value = value.replace("_", "-")

    parts = value.split("-")
    if not parts or not parts[0]:
        return ""

    parts[0] = parts[0].lower()
    if len(parts) >= 2 and len(parts[1]) == 2:
        parts[1] = parts[1].upper()

    return "-".join(parts)


def locale_candidates(tag: str) -> List[str]:
    """Expand a language tag into fallback candidates, most specific first.

    >>> locale_candidates("zh-Hant-TW")
    ['zh-Hant-TW', 'zh-Hant', 'zh', 'en']
    >>> locale_candidates("")
    ['en']
    """
    if not tag:
        return ["en"]

    parts = tag.split("-")
    candidates = []
    while parts:
        candidates.append("-".join(parts))
        parts.pop()

    if "en" not in candidates:
        candidates.append("en")

    return candidates


def _from_env() -> str:
    """Explicit environment variable override, POSIX precedence.

    LC_ALL overrides LC_MESSAGES, which overrides LANG. The first one
    that is set at all (even to "C" or "POSIX") wins on its own,
    without falling through to the next. This also acts as an explicit
    override on Windows/macOS if a user has exported one of these
    (e.g. from a POSIX-style shell).
    """
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            return value
    return ""


def _from_windows_ui_language() -> str:
    """Windows: the user's preferred UI language, or "" if unavailable.

    Deliberately GetUserPreferredUILanguages, not
    GetUserDefaultLocaleName: Windows lets "Display language" (UI
    language) and "Region" (format locale) differ, and we want the
    former.
    """
    if sys.platform != "win32":
        return ""

    import ctypes

    MUI_LANGUAGE_NAME = 0x8

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        num_languages = ctypes.c_ulong(0)
        buffer_size = ctypes.c_ulong(0)

        # First call: ask for the required buffer size (in WCHARs).
        ok = kernel32.GetUserPreferredUILanguages(
            MUI_LANGUAGE_NAME, ctypes.byref(num_languages), None, ctypes.byref(buffer_size)
        )
        if not ok or buffer_size.value == 0:
            return ""

        buffer = ctypes.create_unicode_buffer(buffer_size.value)
        ok = kernel32.GetUserPreferredUILanguages(
            MUI_LANGUAGE_NAME, ctypes.byref(num_languages), buffer, ctypes.byref(buffer_size)
        )
        if not ok:
            return ""

        # The buffer is a MULTI_SZ: languages separated by NUL, ending in
        # a double NUL. Reading the raw buffer (not buffer.value, which
        # stops at the first NUL) preserves that structure.
        raw = ctypes.wstring_at(ctypes.addressof(buffer), buffer_size.value)
        languages = [lang for lang in raw.split("\x00") if lang]
        return languages[0] if languages else ""
    except OSError:
        return ""


def _from_macos_ui_language() -> str:
    """macOS: the user's preferred UI language, or "" if unavailable.

    Uses `defaults export NSGlobalDomain -` (an XML plist plistlib can
    parse) rather than `defaults read -g AppleLanguages` (old-style
    NeXTSTEP plist text plistlib cannot parse). Shells out to the
    `defaults` CLI instead of adding a PyObjC dependency.
    """
    if sys.platform != "darwin":
        return ""

    try:
        result = subprocess.run(
            ["defaults", "export", "NSGlobalDomain", "-"],
            capture_output=True,
            timeout=2,
            check=True,
        )
        data = plistlib.loads(result.stdout)
        languages = data.get("AppleLanguages") or []
        return languages[0] if languages else ""
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
        return ""


def detect_locale() -> str:
    """Return the most specific language tag found in the OS/environment,
    normalized, or "" if none could be determined."""
    raw = _from_env()
    if not raw:
        if sys.platform == "win32":
            raw = _from_windows_ui_language()
        elif sys.platform == "darwin":
            raw = _from_macos_ui_language()
        # Other platforms (Linux/BSD): no further fallback beyond env vars.

    return normalize_locale_tag(raw)


def _load_catalog(candidate: str) -> Optional[Dict[str, str]]:
    """Load locales/<candidate>.json, or None if it doesn't exist."""
    if candidate not in _catalog_cache:
        result: Optional[Dict[str, str]] = None
        try:
            # joinpath takes a single child on Python 3.10's Traversable.
            path = resources.files(__package__).joinpath("locales").joinpath(f"{candidate}.json")
            result = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            result = None
        _catalog_cache[candidate] = result
    return _catalog_cache[candidate]


def resolve_language(requested: str) -> str:
    """Resolve a requested language ("auto", or a tag like "ja"/"en") to
    the most specific candidate with an existing translation catalog,
    falling back to "en" if nothing else matches."""
    tag = detect_locale() if requested == "auto" else requested
    for candidate in locale_candidates(tag):
        if _load_catalog(candidate) is not None:
            return candidate
    return "en"


def set_language(requested: str) -> None:
    global _lang
    _lang = resolve_language(requested)


def get_language() -> str:
    """The resolved language tag currently in effect (see set_language())."""
    return _lang


def t(text: str) -> str:
    """Translate a fixed message string (or `str.format` template) for the
    current language. Falls back to `text` unchanged if untranslated."""
    catalog = _load_catalog(_lang) or {}
    return catalog.get(text, text)
