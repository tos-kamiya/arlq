"""Tests for stopping held movement at known hazards and game events."""

from collections import Counter, deque

import pytest

from arlq import defs as d
from arlq import game_engine
from arlq.arlq import GameConfig
from arlq.game_engine import (
    Floor,
    _ContactResult,
    _process_multi_floor_turn,
    _should_stop_movement_repeat,
)


def blank_field():
    return [[d.CHAR_FLOOR for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]


def floor_with(entities=()):
    return Floor(
        field=blank_field(),
        entities=list(entities),
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )


@pytest.mark.parametrize(
    "cell",
    [
        d.CHAR_WALL,
        d.CHAR_CALTROP,
        d.CHAR_BARRIER,
        d.CHAR_COLLAPSE,
        *d.STAIR_CHARS,
    ],
)
def test_repeat_stops_before_entering_known_special_terrain(cell):
    player = d.Player(2, 2, 100, 90)
    floor = floor_with([player])
    floor.field[2][3] = cell
    floor.seen[2][3] = 1

    assert _should_stop_movement_repeat((1, 0), floor, player)


def test_repeat_does_not_inspect_unknown_terrain_ahead():
    player = d.Player(2, 2, 100, 90)
    floor = floor_with([player])
    floor.field[2][3] = d.CHAR_WALL

    assert not _should_stop_movement_repeat((1, 0), floor, player)


@pytest.mark.parametrize(
    "entity",
    [
        d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["a"]),
        d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W"),
        d.Collapse(4, 2),
        d.Companion(4, 2, d.CHAR_TO_TRIBE["n"]),
    ],
)
def test_repeat_stops_when_approaching_displayed_entity_within_two_steps(entity):
    player = d.Player(2, 2, 100, 90)
    floor = floor_with([player, entity])
    floor.seen[entity.y][entity.x] = 1

    assert _should_stop_movement_repeat((1, 0), floor, player)


def test_repeat_can_move_away_from_nearby_entity():
    player = d.Player(2, 2, 100, 90)
    monster = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floor = floor_with([player, monster])
    floor.seen[monster.y][monster.x] = 1

    assert not _should_stop_movement_repeat((-1, 0), floor, player)


def test_repeat_does_not_stop_for_entity_more_than_two_steps_away():
    player = d.Player(2, 2, 100, 90)
    monster = d.Monster(5, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floor = floor_with([monster])
    floor.seen[monster.y][monster.x] = 1

    assert not _should_stop_movement_repeat((1, 0), floor, player)


def test_repeat_does_not_stop_for_unseen_entity():
    player = d.Player(2, 2, 100, 90)
    monster = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floor = floor_with([player, monster])

    assert not _should_stop_movement_repeat((1, 0), floor, player)


def test_inactive_mimic_is_ignored_until_its_glyph_is_revealed():
    player = d.Player(2, 2, 100, 90)
    mimic = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W")
    mimic.active = False
    floor = floor_with([player, mimic])
    floor.seen[mimic.y][mimic.x] = 1

    assert not _should_stop_movement_repeat((1, 0), floor, player)

    mimic.active = True
    assert _should_stop_movement_repeat((1, 0), floor, player)


def run_step_for_repeat_reasons(player, floors, direction, stage_num=3):
    reasons = set()
    _process_multi_floor_turn(
        direction,
        floors,
        player,
        [0],
        [(player.x, player.y)],
        Counter(),
        deque(),
        1,
        stage_num=stage_num,
        repeat_stop_reasons=reasons,
    )
    return reasons


def test_blocked_movement_marks_repeat_stop_reason():
    player = d.Player(2, 2, 100, 90)
    floor = floor_with()
    floor.field[2][3] = d.CHAR_WALL

    assert "wall_interaction" in run_step_for_repeat_reasons(player, [floor], (1, 0))


def test_wall_break_marks_repeat_stop_reason():
    player = d.Player(2, 2, 100, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 2
    floor = floor_with()
    floor.field[2][3] = d.CHAR_WALL

    reasons = run_step_for_repeat_reasons(player, [floor], (1, 0))

    assert "wall_interaction" in reasons
    assert (player.x, player.y) == (3, 2)


def test_pegasus_jump_marks_repeat_stop_reason():
    player = d.Player(2, 2, 100, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_TRIBE[d.CHAR_PEGASUS])
    floor = floor_with()
    floor.field[2][3] = d.CHAR_WALL

    reasons = run_step_for_repeat_reasons(player, [floor], (1, 0))

    assert "wall_interaction" in reasons
    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)


def test_entity_contact_marks_repeat_stop_reason(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floor = floor_with([monster])
    monkeypatch.setattr(
        "arlq.game_engine._resolve_contact",
        lambda *_args, **_kwargs: _ContactResult(None),
    )

    reasons = run_step_for_repeat_reasons(player, [floor], (1, 0))

    assert "entity_contact" in reasons


def test_collapse_trigger_marks_repeat_stop_reason():
    player = d.Player(2, 2, 100, 90)
    collapse = d.Collapse(3, 2)
    floor = floor_with([collapse])

    reasons = run_step_for_repeat_reasons(player, [floor], (1, 0))

    assert "collapse_triggered" in reasons


def test_falling_from_collapse_marks_repeat_stop_reason():
    player = d.Player(2, 2, 100, 90)
    upper = floor_with([d.Collapse(2, 2)])
    upper.field[2][2] = d.CHAR_COLLAPSE
    lower = floor_with()
    floors = [upper, lower]
    floor_index = [0]
    reasons = set()

    _process_multi_floor_turn(
        (1, 0),
        floors,
        player,
        floor_index,
        [(player.x, player.y)],
        Counter(),
        deque(),
        1,
        repeat_stop_reasons=reasons,
    )

    assert "collapse_transition" in reasons
    assert floor_index == [1]


def test_stair_transition_marks_repeat_stop_reason():
    player = d.Player(2, 2, 100, 90)
    upper = floor_with()
    lower = floor_with()
    upper.field[2][3] = d.CHAR_STAIRS_DOWN
    upper.down_stairs = [(3, 2)]
    lower.up_stairs = [(4, 4)]
    floors = [upper, lower]
    reasons = set()

    _process_multi_floor_turn(
        (1, 0),
        floors,
        player,
        [0],
        [(player.x, player.y)],
        Counter(),
        deque(),
        1,
        repeat_stop_reasons=reasons,
    )

    assert "floor_transition" in reasons
    assert (player.x, player.y) == (4, 4)


def test_marksman_hit_marks_repeat_stop_reason(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    floor = floor_with()
    monkeypatch.setattr("arlq.game_engine._marksman_shoot", lambda *_args: True)

    reasons = run_step_for_repeat_reasons(player, [floor], (1, 0), stage_num=4)

    assert "marksman_hit" in reasons


def test_disabling_automatic_repeat_stop_skips_precheck_and_event_stop(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    floor = floor_with()
    monkeypatch.setattr(
        game_engine, "build_single_floor", lambda *_args: ([floor], player)
    )
    precheck_calls = []
    monkeypatch.setattr(
        game_engine,
        "_should_stop_movement_repeat",
        lambda *_args, **_kwargs: precheck_calls.append(True) or True,
    )
    step_repeat_reasons = []

    def fake_step(*_args, **kwargs):
        step_repeat_reasons.append(kwargs["repeat_stop_reasons"])
        player.lp = 0

    monkeypatch.setattr(game_engine, "_process_multi_floor_turn", fake_step)

    class UI:
        auto_repeat_stop_enabled = False
        input_was_repeat = True
        farthest_preview = False
        shift_direction = False

        def __init__(self):
            self.moves = iter([(1, 0)])

        def draw_stage(self, **_kwargs):
            pass

        def input_direction(self):
            return next(self.moves, None)

        def input_alphabet(self):
            return None

    game_engine.run_game(UI(), "test-seed", config=GameConfig(), stage_num=1)

    assert precheck_calls == []
    assert step_repeat_reasons == [None]
