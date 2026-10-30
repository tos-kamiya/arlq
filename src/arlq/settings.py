"""Settings shared by the graphical and terminal frontends."""

import json
from pathlib import Path
from typing import Optional

from appdirs import user_config_dir

from . import defs as d


def load_settings(path: Optional[Path] = None) -> dict:
    if path is None:
        path = Path(user_config_dir("arlq")) / "settings.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def combat_effect_seconds(settings: dict) -> float:
    value = settings.get("combat_effect_seconds", d.COMBAT_EFFECT_SECONDS)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in d.COMBAT_EFFECT_SECONDS_CHOICES:
            return float(value)
    return d.COMBAT_EFFECT_SECONDS
