import pytest
from blessed import Terminal

from arlq.blessed_map import BlessedMap, EffectAnimation, EffectCell


class TerminalStub:
    width = 160
    height = 24
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
    assert view.map_text(3, 4, "@[ #]") == "<6,4>＠［  ＃］"
    assert view.screen_text(3, 22, "LP: 10") == "<3,22>LP: 10"


def test_effect_padding_is_included_in_style():
    view = BlessedMap(TerminalStub(), cell_width=2)
    assert view.effect_cell(2, 5, "⠁", lambda text: f"({text})") == "<4,5>(⠁ )"
    assert view.map_cell(2, 5, "界") == "<4,5>界"


def test_wide_effect_subcells_are_rendered_in_adjacent_terminal_columns():
    view = BlessedMap(TerminalStub(), cell_width=2)
    cells = [EffectCell(2, 5, "⠁", subcell=0), EffectCell(2, 5, "⢀", subcell=1)]
    assert view.effect_frame(cells) == "<4,5>⠁<5,5>⢀"


def test_rank_marks_use_requested_unicode_characters_only_in_wide_mode():
    term = TerminalStub()
    assert BlessedMap(term).rank_text("b' c\"") == "b' c\""
    view = BlessedMap(term, cell_width=2)
    assert view.rank_text("b' c\"") == "b❜ c❞"
    assert view.map_text(0, 0, view.rank_text("'\"")) == "<0,0>❜ ❞ "


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


def test_dialogue_stays_unscaled_and_is_positioned_in_terminal_columns():
    view = BlessedMap(TerminalStub(), cell_width=2)
    assert view.dialogue(3, 4, "Hello\n日本語", 20, 10) == (
        "<8,2>[bold:[yellow:/ Hello]]<8,3>[bold:[yellow:\\ 日本語]]"
    )
    assert view.dialogue(19, 4, "Hello", 20, 10) == (
        "<31,3>[bold:[yellow:Hello >]]"
    )


@pytest.mark.parametrize("cell_width", [1, 2])
def test_status_popup_uses_terminal_width_and_unchanged_text(cell_width):
    view = BlessedMap(TerminalStub(), cell_width=cell_width)
    assert view.status_popup(3, 4, "LP-10", "red", 20, 10) == (
        f"<{4 * cell_width},3>[bold:[red:LP-10]]"
    )
    assert view.status_popup(19, 4, "LP-10", "default", 20, 10) == (
        f"<{19 * cell_width - 5},5>[bold:LP-10]"
    )
    assert view.status_popup(3, 0, "LP-10", "red", 20, 10, True) == (
        f"<{max(0, 3 * cell_width - 5)},1>[bold:LP-10]"
    )


def test_rewind_transition_scales_background_and_keeps_message_unscaled():
    term = TerminalStub()
    term.normal = "!"
    view = BlessedMap(term, cell_width=2)
    result = view.rewind_transition("Loop", 8, 2)
    assert result == ("<0,0>[on_black:          ]<0,1>[on_black:          ]"
                      "<3,1>[bold:[white_on_black:Loop]]!")


def test_rejects_invalid_cell_width_and_non_cell_text():
    with pytest.raises(ValueError):
        BlessedMap(TerminalStub(), cell_width=3)
    view = BlessedMap(TerminalStub(), cell_width=2)
    with pytest.raises(ValueError):
        view.map_cell(0, 0, "ab")
    with pytest.raises(ValueError):
        view.map_cell(0, 0, "\n")


def test_wide_ui_draws_map_sidebar_dialogue_and_status(monkeypatch):
    from arlq import defs as d
    from arlq import display
    from arlq.blessed_funcs import BlessedUI
    from arlq.stage5 import TrialDialogue

    term = TerminalStub()
    term.home = term.clear = term.normal = ""
    ui = BlessedUI.__new__(BlessedUI)
    ui.term, ui.wide, ui.dots = term, True, False
    ui._style = lambda text, *args, **kwargs: text
    monkeypatch.setattr(display, "build_strength_column", lambda *_: [("b'", False)])
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[2][3] = d.CHAR_WALL
    field[2][5] = d.CHAR_HIDDEN_D_GATE
    seen = [[1] * d.FIELD_WIDTH for _ in field]
    player = d.Player(2, 2, 1, 100)
    monsters = [d.Monster(10, 4, d.MONSTER_TRIBES[0], empowered=2),
                d.Monster(14, 4, d.MONSTER_TRIBES[0], empowered=3)]
    known = {d.monster_type_key(monster) for monster in monsters}
    output = ui._draw_stage([player, *monsters], field, seen, seen, known, stage_roster=[],
                            message=TrialDialogue("Hello"), loop_trail_markers={(4, 2)})
    assert "<4,2>＠" in output
    assert "<6,2>□" in output
    assert "<10,2>□" in output
    assert "<8,2>・" in output
    assert "<22,4>❜ " in output
    assert "<30,4>❞ " in output
    assert f"<{(d.FIELD_WIDTH + d.FIELD_SIDEBAR_GAP) * 2},0>ｂ❜ " in output
    assert "<6,1>[bold:[yellow:< Hello]]" in output
    assert "<0,22>" in ui._draw_status_bar(player, 0)
    assert ui._terminal_is_large_enough()
    term.width = 159
    assert not ui._terminal_is_large_enough()


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("dots", [False, True])
def test_terminal_stair_glyphs(wide, dots):
    from arlq import defs as d
    from arlq.blessed_funcs import BlessedUI

    term = TerminalStub()
    term.home = term.clear = term.normal = ""
    ui = BlessedUI.__new__(BlessedUI)
    ui.term, ui.wide, ui.dots = term, wide, dots
    ui._style = lambda text, *args, **kwargs: text
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[2][3:8] = [d.CHAR_STAIRS_UP, d.CHAR_STAIRS_DOWN,
                     d.CHAR_SCHOLAR_STAIRS_UP, d.CHAR_SCHOLAR_STAIRS_DOWN,
                     d.CHAR_PIT_UP_MARKER]
    seen = [[1] * d.FIELD_WIDTH for _ in field]
    player = d.Player(2, 2, 1, 100)
    output = ui._draw_stage([player], field, seen, seen, set(), stage_roster=[])
    for x, glyph in zip(range(3, 8), ("∆", "∇", "∆", "∇", "▵") if wide else ("^", "v", "^", "v", "^")):
        assert f"<{x * (2 if wide else 1)},2>{glyph}" in output


def test_wide_walls_omitted_in_sprite_mode_use_small_squares():
    from arlq import defs as d
    from arlq.blessed_funcs import BlessedUI

    term = TerminalStub()
    term.home = term.clear = term.normal = ""
    ui = BlessedUI.__new__(BlessedUI)
    ui.term, ui.wide, ui.dots = term, True, False
    ui._style = lambda text, *args, **kwargs: text
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[3][0:2] = [d.CHAR_WALL, d.CHAR_WALL]
    field[3][-2:] = [d.CHAR_WALL, d.CHAR_WALL]
    field[4][1] = d.CHAR_WALL
    decor = [[d.DECOR_NONE] * d.FIELD_WIDTH for _ in field]
    decor[3][0] = d.DECOR_OUTER_WALL
    decor[3][-1] = d.DECOR_BURIED_WALL
    seen = [[1] * d.FIELD_WIDTH for _ in field]
    output = ui._draw_stage([d.Player(4, 4, 1, 100)], field, seen, seen, set(),
                            stage_roster=[], decor=decor)
    assert "<0,3>▫" in output
    assert "<2,3>□" in output
    assert f"<{(d.FIELD_WIDTH - 2) * 2},3>□" in output
    assert f"<{(d.FIELD_WIDTH - 1) * 2},3>▫" in output
    assert "<2,4>□" in output


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("item", ["ITEM_SWORD_X1_5", "ITEM_SWORD_CURSED"])
def test_terminal_sword_glyph(wide, item):
    from arlq import defs as d
    from arlq.blessed_funcs import BlessedUI

    term = TerminalStub()
    term.home = term.clear = term.normal = ""
    ui = BlessedUI.__new__(BlessedUI)
    ui.term, ui.wide, ui.dots = term, wide, False
    ui._style = lambda text, *args, **kwargs: text
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    seen = [[1] * d.FIELD_WIDTH for _ in field]
    player = d.Player(2, 2, 1, 100)
    d.take_monster_item(player, getattr(d, item), "test")
    output = ui._draw_stage([player], field, seen, seen, set(), stage_roster=[])
    assert f"<{2 if wide else 1},2>{'⍀' if wide else chr(92)}" in output
