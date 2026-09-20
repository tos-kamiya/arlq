#!/usr/bin/env python3
"""Proof-of-concept: detect the OS/environment's preferred UI language tag.

This is exploratory code only -- it is not imported by the `arlq` package
and has no effect on the game. See
dev-notes/handoff-lang-auto-detection-20260921.md for the design it
follows.

Run directly:

    python3 dev-samples/detect_locale.py

Detection order:
  1. LC_ALL / LC_MESSAGES / LANG (POSIX precedence: first non-empty wins,
     even if it's "C" or "POSIX" -- this also acts as an explicit
     override on Windows/macOS if a user has exported one of these).
  2. If none of those are set:
     - Windows: GetUserPreferredUILanguages(MUI_LANGUAGE_NAME), not
       GetUserDefaultLocaleName -- Windows lets "Display language" (UI
       language) and "Region" (format locale) differ, and we want the
       former.
     - macOS: the first entry of AppleLanguages, read via
       `defaults export NSGlobalDomain -` (an XML plist plistlib can
       parse) rather than `defaults read -g AppleLanguages` (old-style
       NeXTSTEP plist text plistlib cannot parse). Shells out to the
       `defaults` CLI instead of adding a PyObjC dependency.
     - Linux/BSD/other: no further fallback; treated as undetected.
"""

import os
import plistlib
import subprocess
import sys
from typing import List


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
    """Explicit environment variable override, POSIX precedence."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            return value
    return ""


def _from_windows_ui_language() -> str:
    """Windows: the user's preferred UI language, or "" if unavailable."""
    if sys.platform != "win32":
        return ""

    import ctypes

    MUI_LANGUAGE_NAME = 0x8

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

    # The buffer is a MULTI_SZ: languages separated by NUL, ending in a
    # double NUL. Reading the raw buffer (not buffer.value, which stops
    # at the first NUL) preserves that structure.
    raw = ctypes.wstring_at(ctypes.addressof(buffer), buffer_size.value)
    languages = [lang for lang in raw.split("\x00") if lang]
    return languages[0] if languages else ""


def _from_macos_ui_language() -> str:
    """macOS: the user's preferred UI language, or "" if unavailable."""
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
    """Return the most specific language tag found, or "" if none."""
    raw = _from_env()
    if not raw:
        if sys.platform == "win32":
            raw = _from_windows_ui_language()
        elif sys.platform == "darwin":
            raw = _from_macos_ui_language()
        # Other platforms (Linux/BSD): no further fallback beyond env vars.

    return normalize_locale_tag(raw)


def main() -> None:
    tag = detect_locale()
    print(f"platform:   {sys.platform}")
    print(f"env LC_ALL={os.environ.get('LC_ALL', '')!r} LC_MESSAGES={os.environ.get('LC_MESSAGES', '')!r} LANG={os.environ.get('LANG', '')!r}")
    print(f"detected:   {tag or '(none)'}")
    print(f"candidates: {locale_candidates(tag)}")


if __name__ == "__main__":
    main()
