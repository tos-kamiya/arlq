"""Settings shared by the graphical and terminal frontends."""

import json
import math
from pathlib import Path
from typing import Optional

from appdirs import user_config_dir

from . import defs as d
from .i18n import t as tr

MIN_UI_SCALE = 0.5
MAX_UI_SCALE = 4.0
UI_SCALE_CHOICES = tuple(n / 100 for n in range(50, 401, 25))
KEY_REPEAT_CHOICES = tuple(n / 10 for n in range(1, 11)) + (None,)
GAMEPAD_BUTTON_NAMES = (
    "A",
    "B",
    "X",
    "Y",
    "Left shoulder",
    "Right shoulder",
    "Back",
    "Start",
    "Guide",
    "Left stick press",
    "Right stick press",
    "Left trigger",
    "Right trigger",
)
GAMEPAD_BUTTONS = tuple(range(len(GAMEPAD_BUTTON_NAMES)))
GAMEPAD_BUTTON_CHOICES = (None,) + GAMEPAD_BUTTONS
GAMEPAD_PREVIEW_MODES = ("hold", "toggle")
DEFAULT_UI_SCALE = 1.0
DEFAULT_KEY_REPEAT_INTERVAL = None
DEFAULT_AUTO_REPEAT_STOP_ENABLED = True
DEFAULT_GAMEPAD_HELP_BUTTON = 3
DEFAULT_GAMEPAD_PREVIEW_BUTTON = 2
DEFAULT_GAMEPAD_PREVIEW_MODE = "hold"


def settings_path() -> Path:
    return Path(user_config_dir("arlq")) / "settings.json"


def load_settings(path: Optional[Path] = None) -> dict:
    if path is None:
        path = settings_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_settings(updates: dict, path: Optional[Path] = None) -> None:
    """Merge updates into the saved settings, keeping other keys."""
    if path is None:
        path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        settings = load_settings(path)
        settings.update(updates)
        path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError:
        # A read-only or unusual environment should not prevent the game from
        # starting; the setting simply will not persist in that case.
        pass


def valid_ui_scale(scale) -> float:
    try:
        scale = float(scale)
    except (ValueError, TypeError):
        return DEFAULT_UI_SCALE
    if not math.isfinite(scale):
        return DEFAULT_UI_SCALE
    return min(MAX_UI_SCALE, max(MIN_UI_SCALE, scale))


def valid_key_repeat_interval(interval) -> Optional[float]:
    if interval is None:
        return None
    try:
        interval = float(interval)
    except (ValueError, TypeError):
        return 0.2
    if not math.isfinite(interval):
        return 0.2
    return min(1.0, max(0.1, interval))


def ui_scale(settings: dict) -> float:
    return valid_ui_scale(settings.get("scale", DEFAULT_UI_SCALE))


def key_repeat_interval(settings: dict) -> Optional[float]:
    return valid_key_repeat_interval(
        settings.get("key_repeat_interval", DEFAULT_KEY_REPEAT_INTERVAL)
    )


def auto_repeat_stop_enabled(settings: dict) -> bool:
    value = settings.get("auto_repeat_stop_enabled", DEFAULT_AUTO_REPEAT_STOP_ENABLED)
    return value if isinstance(value, bool) else DEFAULT_AUTO_REPEAT_STOP_ENABLED


def combat_effect_seconds(settings: dict) -> float:
    value = settings.get("combat_effect_seconds", d.COMBAT_EFFECT_SECONDS)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in d.COMBAT_EFFECT_SECONDS_CHOICES:
            return float(value)
    return d.COMBAT_EFFECT_SECONDS


def idle_bob_enabled(settings: dict) -> bool:
    value = settings.get("idle_bob_enabled", d.IDLE_BOB_ENABLED)
    return value if isinstance(value, bool) else d.IDLE_BOB_ENABLED


def move_glide_enabled(settings: dict) -> bool:
    value = settings.get("move_glide_enabled", d.MOVE_GLIDE_ENABLED)
    return value if isinstance(value, bool) else d.MOVE_GLIDE_ENABLED


def floor_transition_seconds(settings: dict) -> float:
    value = settings.get("floor_transition_seconds", d.FLOOR_TRANSITION_SECONDS)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in d.FLOOR_TRANSITION_SECONDS_CHOICES:
            return float(value)
    return d.FLOOR_TRANSITION_SECONDS


def valid_gamepad_bindings(
    help_button, preview_button, preview_mode
) -> tuple[Optional[int], Optional[int], str]:
    if help_button is not None and (
        type(help_button) is not int or help_button not in GAMEPAD_BUTTONS
    ):
        help_button = DEFAULT_GAMEPAD_HELP_BUTTON
    if preview_button is not None and (
        type(preview_button) is not int or preview_button not in GAMEPAD_BUTTONS
    ):
        preview_button = DEFAULT_GAMEPAD_PREVIEW_BUTTON
    if help_button is not None and help_button == preview_button:
        preview_button = None
    if preview_mode not in GAMEPAD_PREVIEW_MODES:
        preview_mode = DEFAULT_GAMEPAD_PREVIEW_MODE
    return help_button, preview_button, preview_mode


def gamepad_bindings(settings: dict) -> tuple[Optional[int], Optional[int], str]:
    return valid_gamepad_bindings(
        settings.get("gamepad_help_button", DEFAULT_GAMEPAD_HELP_BUTTON),
        settings.get("gamepad_preview_button", DEFAULT_GAMEPAD_PREVIEW_BUTTON),
        settings.get("gamepad_preview_mode", DEFAULT_GAMEPAD_PREVIEW_MODE),
    )


def gamepad_bindings_settings(help_button, preview_button, preview_mode) -> dict:
    help_button, preview_button, preview_mode = valid_gamepad_bindings(
        help_button, preview_button, preview_mode
    )
    return {
        "gamepad_help_button": help_button,
        "gamepad_preview_button": preview_button,
        "gamepad_preview_mode": preview_mode,
    }


def default_settings() -> dict:
    """Every setting shown in the Settings screens, at its default value."""
    return {
        "scale": DEFAULT_UI_SCALE,
        "key_repeat_interval": DEFAULT_KEY_REPEAT_INTERVAL,
        "auto_repeat_stop_enabled": DEFAULT_AUTO_REPEAT_STOP_ENABLED,
        "combat_effect_seconds": d.COMBAT_EFFECT_SECONDS,
        "floor_transition_seconds": d.FLOOR_TRANSITION_SECONDS,
        "idle_bob_enabled": d.IDLE_BOB_ENABLED,
        "move_glide_enabled": d.MOVE_GLIDE_ENABLED,
        **gamepad_bindings_settings(
            DEFAULT_GAMEPAD_HELP_BUTTON,
            DEFAULT_GAMEPAD_PREVIEW_BUTTON,
            DEFAULT_GAMEPAD_PREVIEW_MODE,
        ),
    }


def clear_default_settings(path: Optional[Path] = None) -> None:
    """Remove saved settings that equal their defaults, as after a reset.

    Unsaved settings follow the defaults of the running version.
    """
    if path is None:
        path = settings_path()
    settings = load_settings(path)
    for name, value in default_settings().items():
        if name in settings and settings[name] == value:
            del settings[name]
    try:
        if settings:
            path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
    except OSError:
        pass


def current_settings(settings: dict) -> dict:
    """Every setting shown in the Settings screens, validated."""
    return {
        "scale": ui_scale(settings),
        "key_repeat_interval": key_repeat_interval(settings),
        "auto_repeat_stop_enabled": auto_repeat_stop_enabled(settings),
        "combat_effect_seconds": combat_effect_seconds(settings),
        "floor_transition_seconds": floor_transition_seconds(settings),
        "idle_bob_enabled": idle_bob_enabled(settings),
        "move_glide_enabled": move_glide_enabled(settings),
        **gamepad_bindings_settings(*gamepad_bindings(settings)),
    }


def gamepad_button_label(button: Optional[int]) -> str:
    """Return a readable label for one of pyglet's standard controller inputs."""
    if button is None:
        return tr("Unassigned")
    return tr("Button {n} ({name})").format(
        n=button, name=tr(GAMEPAD_BUTTON_NAMES[button])
    )


def next_gamepad_button(
    current: Optional[int], step: int, occupied: Optional[int]
) -> Optional[int]:
    """Cycle bindings while skipping the other mode key's assigned button."""
    index = GAMEPAD_BUTTON_CHOICES.index(current)
    for offset in range(1, len(GAMEPAD_BUTTON_CHOICES) + 1):
        candidate = GAMEPAD_BUTTON_CHOICES[
            (index + step * offset) % len(GAMEPAD_BUTTON_CHOICES)
        ]
        if candidate is None or candidate != occupied:
            return candidate
    return None
