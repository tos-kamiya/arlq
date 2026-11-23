from types import SimpleNamespace
from importlib import import_module

import pytest

from arlq import defs as d
from arlq.braille_effects import effect_frames
from arlq.game_events import Combat
from arlq.presentation import play_defeat_effects


@pytest.mark.parametrize("name", ["Vortex", "Dungeon Core", "Boss", "Core Calamity"])
def test_frames_are_clipped_and_disabled_by_combat_setting(name):
    assert effect_frames(name, (0, 0), 0) == (0, [])
    duration, frames = effect_frames(name, (0, 0), 0.3)
    assert duration > 0 and any(frames)
    for frame in frames:
        for (x, y), char, color in frame:
            assert 0 <= x < d.FIELD_WIDTH and 0 <= y < d.FIELD_HEIGHT
            assert 0x2800 < ord(char) <= 0x28ff
            assert len(color) == 3


@pytest.mark.parametrize("name, expected", [("Boss", 14 / 15), ("Dungeon Core", 1.0),
                                            ("Core Calamity", 2.0)])
def test_defeat_effect_duration_is_fixed_when_enabled(name, expected):
    for setting in (0.1, 1.0):
        duration, frames = effect_frames(name, (10, 9), setting)
        assert duration == pytest.approx(expected)
        assert frames


def test_defeat_effects_only_follow_wins_on_the_current_floor():
    calls = []
    ui = SimpleNamespace(draw_boss_afterglow=lambda p: calls.append(("boss", p)),
                         draw_core_burst=lambda p: calls.append(("core", p)))
    events = [Combat(0, (1, 1), [], True, 0, boss_at=(2, 2)),
              Combat(1, (1, 1), [], False, 0, core_at=(3, 3)),
              Combat(1, (1, 1), [], True, 0, core_at=(4, 4))]
    play_defeat_effects(ui, SimpleNamespace(events=events, floor_after=1))
    assert calls == [("core", (4, 4))]


def test_terminal_effect_keeps_player_cell(monkeypatch, capsys):
    from arlq import blessed_funcs

    ui = blessed_funcs.BlessedUI.__new__(blessed_funcs.BlessedUI)
    ui.combat_effect_seconds = 0.3
    ui._effect_player_pos = (2, 2)
    ui._stage_snapshot = "stage"
    ui._combat_cell_backgrounds = {}
    ui.map_mode = False
    ui._wait_for_terminal_size = lambda: None
    ui._style = lambda text, **kwargs: text
    ui.term = SimpleNamespace(number_of_colors=0, normal="", inkey=lambda timeout: "",
                              move_xy=lambda x, y: f"[{x},{y}]")
    monkeypatch.setattr(blessed_funcs, "effect_frames", lambda *args: (
        0.1, [[((2, 2), "⣿", (255, 255, 255)),
               ((3, 2), "⠁", (255, 255, 255))]]))
    monkeypatch.setattr(blessed_funcs.time, "sleep", lambda _: None)
    ui.draw_core_burst((2, 2))
    output = capsys.readouterr().out
    assert "[2,2]" not in output
    assert "[3,2]⠁" in output


def test_gui_effect_keeps_player_cell(monkeypatch):
    from arlq import braille_effects, pyglet_funcs

    ui = pyglet_funcs.PygletUI.__new__(pyglet_funcs.PygletUI)
    ui.combat_effect_seconds = 0.3
    ui._effect_player_pos = (2, 2)
    ui._combat_cell_colors = {}
    ui._closed = False
    ui.cell_size_x = ui.cell_size_y = 10
    ui.window_height = 100
    ui.font_size = 10
    ui.batch = None
    ui._field_col_x = lambda x: x * 10
    ui._field_col_width = lambda x: 10
    ui._field_text_x_offset = lambda: 0
    ui._display_color = lambda color: color
    ui._flip = lambda: None
    ui._pump = lambda: None
    positions = []
    item = lambda *args, **kwargs: SimpleNamespace(delete=lambda: None)
    monkeypatch.setattr(import_module("pyglet.shapes"), "Rectangle",
                        lambda x, y, w, h, **kwargs: (positions.append((x, y, w, h)), item())[1])
    monkeypatch.setattr(braille_effects, "effect_frames", lambda *args: (
        0, [[((2, 2), "⣿", (255, 255, 255)),
             ((3, 2), "⠁", (255, 255, 255))]]))
    ui.draw_core_burst((2, 2))
    assert positions == [(30, 70, 10, 10), (30, 77.5, 5, 2.5)]


def test_gui_combat_effect_pumps_events_until_deadline(monkeypatch):
    from arlq import pyglet_funcs

    ui = pyglet_funcs.PygletUI.__new__(pyglet_funcs.PygletUI)
    ui.combat_effect_seconds = 0.05
    ui._closed = False
    ui._stage_input_active = False
    ui._combat_cell_colors = {}
    ui.cell_size_y = 10
    ui._field_col_x = lambda x: x * 10
    ui._field_col_width = lambda x: 10
    ui._field_text_x_offset = lambda: 0
    ui._draw_rect = lambda *args, **kwargs: None
    ui._draw_text = lambda *args, **kwargs: None
    ui._flip = lambda: None
    now = [0.0]
    active = []
    ui._pump = lambda: active.append(ui._stage_input_active)
    monkeypatch.setattr(pyglet_funcs.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(pyglet_funcs.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))

    ui.draw_combat_effect((1, 1), True)

    assert active and all(active)
    assert now[0] == pytest.approx(0.05)
    assert not ui._stage_input_active


def test_braille_dot_mapping():
    from arlq.pyglet_funcs import _braille_dots

    assert list(_braille_dots("⠁")) == [(0, 0)]
    assert list(_braille_dots("⢀")) == [(1, 3)]
    assert len(list(_braille_dots("⣿"))) == 8



def test_iris_ration_effect_follows_events_on_the_current_floor():
    from arlq.game_events import IrisRation
    from arlq.presentation import play_iris_ration

    calls = []
    ui = SimpleNamespace(draw_iris_ration=calls.append)
    events = [IrisRation(0, (1, 1)), IrisRation(1, (2, 2))]
    play_iris_ration(ui, SimpleNamespace(events=events, floor_after=1))
    assert calls == [(2, 2)]


def test_iris_sparkle_uses_free_floor_cells_beside_her():
    from arlq.treasure_particles import iris_sparkle_cells, iris_sparkle_frame

    field = [[d.CHAR_FLOOR] * 5 for _ in range(5)]
    field[1][2] = d.CHAR_WALL
    visible = [[1] * 5 for _ in range(5)]
    visible[2][1] = 0
    player = d.Player(3, 2, 1, 0)
    cells = iris_sparkle_cells((2, 2), player, [], field, visible)
    # Up is a wall, right is the player, left is out of sight.
    assert cells == [(2, 3)]
    chars = [char for index in range(8) for _, char in iris_sparkle_frame(cells, index, (2, 2))]
    assert chars and all(0x2800 < ord(char) <= 0x28ff for char in chars)


def _sparkle_context():
    field = [[d.CHAR_FLOOR] * 8 for _ in range(8)]
    visible = [[1] * 8 for _ in range(8)]
    return (d.Player(6, 6, 1, 0), [], field, visible, None, set())


def test_terminal_iris_ration_twinkles_beside_her(monkeypatch, capsys):
    from arlq import blessed_funcs

    ui = blessed_funcs.BlessedUI.__new__(blessed_funcs.BlessedUI)
    ui.combat_effect_seconds = 0.3
    ui._stage_snapshot = "stage"
    ui._combat_cell_backgrounds = {}
    ui._sparkle_context = _sparkle_context()
    ui._wait_for_terminal_size = lambda: None
    ui._style = lambda text, **kwargs: text
    queued = ["d", "d"]
    ui.term = SimpleNamespace(normal="", move_xy=lambda x, y: f"[{x},{y}]",
                              inkey=lambda timeout: queued.pop() if queued else "")
    monkeypatch.setattr(blessed_funcs.time, "sleep", lambda _: None)
    ui.draw_iris_ration((4, 3))
    # Keys repeated while the effect played are dropped.
    assert queued == []
    output = capsys.readouterr().out
    assert "[4,3]" not in output
    assert all(f"[{x},{y}]" in output for x, y in ((4, 2), (5, 3), (4, 4), (3, 3)))
    assert output.endswith("stage")


def test_gui_iris_ration_draws_dots_beside_her(monkeypatch):
    from arlq import pyglet_funcs

    ui = pyglet_funcs.PygletUI.__new__(pyglet_funcs.PygletUI)
    ui.combat_effect_seconds = 0.3
    ui._closed = False
    ui._sparkle_context = _sparkle_context()
    ui.cell_size_x = ui.cell_size_y = 16
    ui.window_height = 160
    ui.batch = None
    ui._field_col_x = lambda x: x * 16
    ui._field_col_width = lambda x: 16
    ui._display_color = lambda color: color
    ui._flip = lambda: None
    ui._pump = lambda: None
    rects = []
    item = lambda *args, **kwargs: SimpleNamespace(delete=lambda: None)
    monkeypatch.setattr(import_module("pyglet.shapes"), "Rectangle",
                        lambda x, y, w, h, **kwargs: (rects.append((x, y, w, h)), item())[1])
    monkeypatch.setattr(pyglet_funcs, "IRIS_SPARKLE_SECONDS", 0)
    ui.draw_iris_ration((2, 3))
    cells = {(int(x // 16), int((160 - y - h) // 16)) for x, y, w, h in rects}
    assert cells == {(2, 2), (3, 3), (2, 4), (1, 3)}


def test_iris_sparkle_above_and_below_stays_in_the_half_near_her():
    from arlq.treasure_particles import iris_sparkle_frame

    center = (2, 2)
    cells = [(2, 1), (3, 2), (2, 3), (1, 2)]
    lower_half, upper_half = 0x04 | 0x20 | 0x40 | 0x80, 0x01 | 0x02 | 0x08 | 0x10
    for index in range(8):
        for point, char in iris_sparkle_frame(cells, index, center):
            mask = ord(char) - 0x2800
            if point == (2, 1):
                assert not mask & ~lower_half
            elif point == (2, 3):
                assert not mask & ~upper_half


def test_terminal_stop_movement_repeat_discards_queued_keys():
    from arlq import blessed_funcs

    ui = blessed_funcs.BlessedUI.__new__(blessed_funcs.BlessedUI)
    queued = ["d", "d", "d"]
    timeouts = []

    def inkey(timeout):
        timeouts.append(timeout)
        return queued.pop() if queued else ""

    ui.term = SimpleNamespace(inkey=inkey)
    ui.stop_movement_repeat()
    assert queued == [] and set(timeouts) == {0}
