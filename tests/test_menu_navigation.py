"""Keyboard navigation checks for the GUI menus."""

from collections import deque

from pyglet.window import key

from arlq import defs
from arlq.pyglet_funcs import PygletUI


def _menu_ui(monkeypatch, events):
    ui = PygletUI.__new__(PygletUI)
    ui._closed = False
    ui._key_queue = []
    ui._escape_key_held = False
    ui.joystick = None
    ui.scale = 1.0
    ui.key_repeat_interval = None
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
