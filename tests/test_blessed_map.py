import pytest
from blessed import Terminal

from arlq.blessed_map import BlessedMap, EffectAnimation, EffectCell


class TerminalStub:
    width = 160
    number_of_colors = 256

    def __init__(self):
        self.term = Terminal(force_styling=False)

    def move_xy(self, x, y):
        return f"<{x},{y}>"

    def length(self, text):
        return self.term.length(text)

    def __getattr__(self, name):
        return lambda text: f"[{name}:{text}]"


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


def test_effect_animation_renders_frames_with_timing_and_restores_snapshot(monkeypatch, capsys):
    term = TerminalStub()
    term.normal = "!"
    view = BlessedMap(term, cell_width=2)
    waits = []
    monkeypatch.setattr("arlq.blessed_map.time.sleep", waits.append)
    sizes = []
    animation = EffectAnimation([
        [EffectCell(2, 3, "⠁", "yellow")],
        [EffectCell(4, 5, "⣿", "red")],
    ], 0.25)
    view.play_effect(animation, "stage", lambda: sizes.append(True))
    assert capsys.readouterr().out == "stage<4,3>[yellow:⠁ ]!stage<8,5>[red:⣿ ]!stage"
    assert waits == [0.25, 0.25]
    assert sizes == [True, True]


def test_effect_rgb_fallback_and_background_are_applied_by_adapter():
    term = TerminalStub()
    term.number_of_colors = 16
    view = BlessedMap(term, cell_width=2)
    cell = EffectCell(1, 2, "⠁", (1, 2, 3), "black", True, "yellow")
    assert view.effect_frame([cell]) == "<2,2>[bold:[yellow_on_black:⠁ ]]"
    term.number_of_colors = 256
    term.color_rgb = lambda *rgb: lambda text: f"[rgb{rgb}:{text}]"
    assert view.effect_frame([cell]) == "<2,2>[rgb(1, 2, 3):[bold:[on_black:⠁ ]]]"


def test_rejects_invalid_cell_width_and_non_cell_text():
    with pytest.raises(ValueError):
        BlessedMap(TerminalStub(), cell_width=3)
    view = BlessedMap(TerminalStub(), cell_width=2)
    with pytest.raises(ValueError):
        view.map_cell(0, 0, "ab")
    with pytest.raises(ValueError):
        view.map_cell(0, 0, "\n")
