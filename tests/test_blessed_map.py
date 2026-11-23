import pytest
from blessed import Terminal

from arlq.blessed_map import BlessedMap


class TerminalStub:
    width = 160

    def __init__(self):
        self.term = Terminal(force_styling=False)

    def move_xy(self, x, y):
        return f"<{x},{y}>"

    def length(self, text):
        return self.term.length(text)


def test_narrow_map_and_screen_text_keep_original_coordinates_and_text():
    view = BlessedMap(TerminalStub())
    assert view.map_cell(3, 4, "@") == "<3,4>@"
    assert view.screen_text(3, 22, "LP: 10") == "<3,22>LP: 10"
    assert view.width == 160


def test_wide_map_expands_coordinates_and_ascii_characters():
    view = BlessedMap(TerminalStub(), cell_width=2)
    assert view.map_text(3, 4, "@[ #]") == "<6,4>＠［　＃］"
    assert view.screen_text(3, 22, "LP: 10") == "<3,22>LP: 10"


def test_effect_padding_is_included_in_style():
    view = BlessedMap(TerminalStub(), cell_width=2)
    assert view.effect_cell(2, 5, "⠁", lambda text: f"({text})") == "<4,5>(⠁ )"
    assert view.map_cell(2, 5, "界") == "<4,5>界"


def test_rejects_invalid_cell_width_and_non_cell_text():
    with pytest.raises(ValueError):
        BlessedMap(TerminalStub(), cell_width=3)
    view = BlessedMap(TerminalStub(), cell_width=2)
    with pytest.raises(ValueError):
        view.map_cell(0, 0, "ab")
    with pytest.raises(ValueError):
        view.map_cell(0, 0, "\n")
