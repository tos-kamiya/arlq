"""Confirmation controls shared by the game-over UI."""
from collections import deque
from types import SimpleNamespace

import pytest
from pyglet.window import key

from arlq.pyglet_funcs import PygletUI


@pytest.mark.parametrize('symbols,expected', [
    ([key.Y], True), ([key.N], False), ([key.RETURN], False),
    ([key.LEFT, key.RETURN], True),
    ([key.LEFT, key.RIGHT, key.RETURN], False),
    ([key.ESCAPE], None), ([key.Q], None),
])
def test_gui_confirmation_keys(symbols, expected):
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui._closed = False
    ui._key_queue = []
    ui.field_pixel_width = 800
    ui.field_height = 30
    ui.cell_size_y = 20
    ui.stop_movement_repeat = lambda: None
    ui._clear_drawables = lambda: None
    ui._draw_rect = lambda *a: None
    ui._draw_text = lambda *a, **kw: None
    ui._text_width = lambda text, **kw: len(text) * 8
    ui._flip = lambda: None
    ui._pump = lambda: None
    events = deque((symbol, 0) for symbol in symbols)
    ui._next_key_event = events.popleft
    assert ui.confirm_game_over() is expected


@pytest.mark.parametrize('text,expected', [('y', True), ('n', False), ('q', None), ('\x1b', None)])
def test_terminal_confirmation_direct_keys(text, expected):
    from blessed.keyboard import Keystroke

    from arlq.blessed_funcs import BlessedUI
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(home='', clear='', normal='', width=80, height=30,
                              move_xy=lambda *a: '', length=len, KEY_ESCAPE=27)
    ui._wait_for_terminal_size = lambda: None
    ui._style = lambda text, **kw: text
    ui._read_key = lambda: Keystroke(text, code=27 if text == '\x1b' else None)
    assert ui.confirm_game_over() is expected


def test_gui_game_over_redraws_after_resize():
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui._closed = False
    ui._key_queue = []
    ui._gamepad_pressed_buttons = set()
    ui.gamepad_help_button = None
    ui._pump = lambda: None
    ui._resize_redraw_pending = True
    # A resize returns a no-op input, so the game loop redraws the final
    # screen (and anything drawn over it) for the new window size.
    assert ui.input_game_over() == (0, 0, False)
    assert not ui._resize_redraw_pending
