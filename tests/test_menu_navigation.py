"""Keyboard navigation checks for the GUI menus."""

import json

import pytest
from collections import deque

from pyglet.window import key

from arlq import defs
from arlq.pyglet_funcs import PygletUI


def _menu_ui(monkeypatch, events):
    ui = PygletUI.__new__(PygletUI)
    ui._closed = False
    ui._menu_active = False
    ui._menu_font_resize_pending = False
    ui._menu_scale = 1.0
    ui._menu_cell_size_x = 13
    ui._key_queue = []
    ui._escape_key_held = False
    ui.joystick = None
    ui.scale = 1.0
    ui.key_repeat_interval = None
    ui.auto_repeat_stop_enabled = True
    ui.cell_size_x = 13
    ui._events = deque(events)
    ui._pump = lambda: None
    ui._next_key_event = lambda: ui._events.popleft() if ui._events else None
    ui._discard_queued_key = lambda _symbol: None
    ui._clear_drawables = lambda: None
    ui._draw_text = lambda *_args, **_kwargs: None
    ui._text_width = lambda *_args, **_kwargs: 0
    ui._flip = lambda: None
    ui.quit_called = False
    ui.quit = lambda: setattr(ui, "quit_called", True)
    monkeypatch.setattr("arlq.pyglet_funcs.time.sleep", lambda *_args: None)
    return ui


def test_escape_from_settings_returns_to_stage_selection(monkeypatch):
    """Esc cancels Settings and leaves the app ready for a stage choice."""
    ui = _menu_ui(
        monkeypatch,
        [(key.S, 0), (key.ESCAPE, 0), (key._1, 0)],
    )

    selected_stage = ui.select_stage()

    assert selected_stage == 1
    assert ui.quit_called is False
    assert ui._closed is False


def test_entering_settings_from_stage_list_and_escape_keeps_app_open(monkeypatch):
    """Arrow navigation and Enter reach Settings; Esc returns to the list."""
    events = [(key.DOWN, 0)] * len(defs.PUBLIC_STAGE_NUMBERS)
    events.extend([(key.RETURN, 0), (key.ESCAPE, 0), (key._1, 0)])
    ui = _menu_ui(monkeypatch, events)

    selected_stage = ui.select_stage()

    assert selected_stage == 1
    assert ui.quit_called is False
    assert ui._closed is False


def test_settings_can_disable_and_persist_automatic_repeat_stop(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: settings_path)
    ui = _menu_ui(
        monkeypatch,
        [(key.DOWN, 0), (key.DOWN, 0), (key.RIGHT, 0), (key.RETURN, 0)],
    )
    ui.set_scale = lambda scale: setattr(ui, "scale", scale)

    ui.settings_menu()

    assert ui.auto_repeat_stop_enabled is False
    assert json.loads(settings_path.read_text()) == {
        "key_repeat_interval": None,
        "auto_repeat_stop_enabled": False,
        "combat_effect_seconds": 0.3,
    }


@pytest.mark.parametrize("seconds", defs.COMBAT_EFFECT_SECONDS_CHOICES)
def test_settings_select_and_reload_combat_effect_duration(monkeypatch, tmp_path, seconds):
    from arlq.settings import combat_effect_seconds, load_settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"scale": 1.5}))
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    events = [(key.DOWN, 0)] * 3 + [(key.LEFT, 0)] * 5
    events += [(key.RIGHT, 0)] * round(seconds * 10) + [(key.RETURN, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert ui.combat_effect_seconds == seconds
    assert combat_effect_seconds(load_settings(path)) == seconds
    assert load_settings(path)["scale"] == 1.5


def test_cancel_combat_effect_duration_keeps_saved_value(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    original = '{"combat_effect_seconds": 0.3}'
    path.write_text(original)
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    ui = _menu_ui(monkeypatch, [(key.DOWN, 0)] * 3 + [(key.RIGHT, 0), (key.ESCAPE, 0)])
    ui.combat_effect_seconds = 0.3

    ui.settings_menu()

    assert ui.combat_effect_seconds == 0.3
    assert path.read_text() == original


@pytest.mark.parametrize("value", [None, True, "0.1", -0.1, 0.6, 0.25, float("nan")])
def test_invalid_combat_effect_duration_uses_default(value):
    from arlq.settings import combat_effect_seconds

    assert combat_effect_seconds({"combat_effect_seconds": value}) == 0.3


def test_zero_duration_skips_effect_in_all_frontends():
    from arlq.blessed_funcs import BlessedUI
    from arlq.sprite_funcs import SpriteUI

    for frontend in (PygletUI, SpriteUI, BlessedUI):
        ui = frontend.__new__(frontend)
        ui.combat_effect_seconds = 0
        # No window or terminal is available; zero must return before rendering.
        ui.draw_combat_effect((0, 0), True)
        ui.draw_combat_effect((0, 0), False)
