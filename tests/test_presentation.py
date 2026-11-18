"""All frontends replay each event once after the turn is committed."""

from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq import game_engine as engine
from arlq.game_events import BarrierHit, Combat, EntityRef, FloorChanged, Rewound
from arlq.game_session import TurnResult
from arlq.presentation import play_turn_events
from arlq.stage_types import Floor
from arlq.trace import TraceRecorder


def recording_ui():
    calls = []
    ui = SimpleNamespace(
        draw_combat_effect=lambda *args: calls.append(("combat", *args)),
        draw_rewind_transition=lambda *args: calls.append(("rewind", *args)),
        draw_floor_transition=lambda *args: calls.append(("floor", *args)),
    )
    return ui, calls


@pytest.mark.parametrize("stage_num", [1, 3, 5, 6])
@pytest.mark.parametrize("won", [False, True])
def test_combat_replays_snapshot_positions(stage_num, won):
    player = d.Player(50, 10, 10, 90)
    targets = [
        (EntityRef(1, "a", "monster"), (3, 2)),
        (EntityRef(2, "b", "monster"), (3, 3)),
    ]
    party_positions = [(2, 2), (1, 2)]
    event = Combat(0, (2, 2), targets, won, -10, party_positions)
    result = TurnResult(True, None, True, 0, 0, [event])
    ui, calls = recording_ui()
    play_turn_events(ui, result, player, stage_num)
    positions = [(3, 2), (3, 3)] if won else party_positions
    assert calls == [
        ("combat", positions if stage_num in (5, 6) else positions[0], won)
    ]
    assert (player.x, player.y) == (50, 10)


def test_effect_order_and_floor_filtering():
    player = d.Player(2, 2, 10, 90)
    result = TurnResult(
        True,
        None,
        True,
        0,
        0,
        [
            BarrierHit(0, (3, 2), 5),
            BarrierHit(1, (6, 6), 5),
            FloorChanged(0, "down", 1, (3, 2)),
            BarrierHit(0, (7, 7), 5),
            BarrierHit(1, (4, 4), 5),
            FloorChanged(1, "up", 0, (5, 4)),
            Rewound(0, "Time folds back.", {0: {(3, 2)}}),
        ],
    )
    ui, calls = recording_ui()
    play_turn_events(ui, result, player, 3)
    assert calls == [
        ("combat", (3, 2), False),
        ("floor", "down", player, (3, 2)),
        ("combat", (4, 4), False),
        ("floor", "up", player, (5, 4)),
        ("rewind", "Time folds back."),
    ]


def test_optional_effects_and_empty_turns():
    result = TurnResult(False, None, True, 0, 0)
    ui, calls = recording_ui()
    player = d.Player(2, 2, 10, 90)
    play_turn_events(ui, result, player, 1)
    assert calls == []
    result.events = [
        BarrierHit(0, (3, 2), 5),
        FloorChanged(0, "down", 1, (3, 2)),
        Rewound(1, "Time folds back.", {}),
    ]
    play_turn_events(SimpleNamespace(), result, player, 1)


@pytest.mark.parametrize("frontend", ["blessed", "pyglet", "sprite"])
@pytest.mark.parametrize("won", [False, True])
def test_frontends_use_one_effect_path_at_the_expected_time(monkeypatch, frontend, won):
    from arlq.blessed_funcs import BlessedUI
    from arlq.pyglet_funcs import PygletUI
    from arlq.sprites.sprite_funcs import SpriteUI

    ui_type = {"blessed": BlessedUI, "pyglet": PygletUI, "sprite": SpriteUI}[frontend]
    ui = ui_type.__new__(ui_type)
    ui.map_mode = False
    if frontend == "sprite":
        from arlq.sprites.sprite_fx import Presenter

        ui._presenter = Presenter()
        ui._stage_input_active = False
        ui._closed = False
        ui._pump = lambda: None
    calls = []
    ui.draw_stage = lambda **kwargs: calls.append(("draw", kwargs["turn"]))
    ui.stop_movement_repeat = lambda: calls.append(("stop",))
    ui.input_game_over = lambda: None
    moves = iter([(1, 0), None])
    ui.input_direction = lambda: next(moves)
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[2][3] = d.CHAR_BARRIER
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    current = Floor(
        field, [monster], [[0] * len(row) for row in field], (2, 2), (70, 18), None
    )
    player = d.Player(2, 2, 100 if won else 0.1, 90)
    monkeypatch.setattr(
        engine,
        "build_single_floor",
        lambda *_, current=current, player=player: ([current], player),
    )
    trace = TraceRecorder({"stage": 1})

    def combat(pos, victory):
        # The old hook runs before commit_turn, so this also detects using
        # both paths by accident.
        assert len(trace.turns) == 1
        assert trace.turns[0]["player"]["lp_after_turn"] == player.lp
        calls.append(("effect", pos, victory))

    ui.draw_combat_effect = combat
    engine.run_game(ui, "test", trace=trace, stage_num=1)
    effects = [("effect", (3, 2), False), ("effect", (3, 2) if won else (2, 2), won)]
    expected = [("draw", 0), *effects, ("draw", 1)]
    assert calls == expected


@pytest.mark.parametrize("torch_radius, expected_seen", [(2, 36), (3, 66), (4, 106)])
def test_barrier_trace_matches_pre_hook_removal_baseline(
    monkeypatch, torch_radius, expected_seen
):
    engine.rand.set_seed(12345)
    random_state = engine.rand.getstate()
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[8][16] = d.CHAR_BARRIER
    current = Floor(
        field, [], [[0] * len(row) for row in field], (15, 8), (70, 18), None
    )
    player = d.Player(15, 8, 10, 90)
    monkeypatch.setattr(engine, "build_single_floor", lambda *_: ([current], player))
    trace = TraceRecorder({"stage": 1})
    moves = iter([(1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **_: None, input_direction=lambda: next(moves)
    )
    engine.run_game(
        ui,
        "test",
        trace=trace,
        stage_num=1,
        config=engine.GameConfig(torch_radius=torch_radius),
    )
    assert trace.turns[0] == {
        "turn": 1,
        "input": "R",
        "damage": [{"source": "barrier"}],
        "player": {
            "lp": 60,
            "level": 10,
            "attack": 10,
            "floor": 0,
            "position": [16, 8],
            "lp_after_turn": 59,
        },
        "seen_added_count": expected_seen,
        "known_monsters_added": [],
        "wall": None,
        "contact": None,
        "expired": [],
        "world": [],
    }
    assert engine.rand.getstate() == random_state


@pytest.mark.parametrize("completed", [False, True])
def test_closing_presenter_skips_further_draws_and_preserves_completed_outcome(
    monkeypatch, completed
):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    current = Floor(
        field, [], [[0] * len(row) for row in field], (2, 2), (70, 18), None
    )
    player = d.Player(2, 2, 10, 90)
    monkeypatch.setattr(engine, "build_single_floor", lambda *_: ([current], player))
    trace = TraceRecorder({"stage": 1})
    frames = []

    def step(*_, **__):
        if completed:
            player.boss_defeated = player.treasure_collected = True

    monkeypatch.setattr(engine, "_process_multi_floor_turn", step)
    ui = SimpleNamespace(
        draw_stage=lambda **view: frames.append(view["turn"]),
        input_direction=lambda: (1, 0),
        present_turn=lambda *_: False,
    )
    engine.run_game(ui, "test", stage_num=1, trace=trace)
    assert frames == [0]
    assert trace.outcome == ("win" if completed else "quit")


@pytest.mark.parametrize("won", [False, True])
def test_won_combat_against_vortex_plays_vortex_effect(won):
    player = d.Player(2, 2, 10, 90)
    targets = [
        (EntityRef(1, "F", "monster"), (3, 2)),
        (EntityRef(2, "V", "monster"), (3, 3)),
    ]
    event = Combat(0, (2, 2), targets, won, 0, [(2, 2)])
    result = TurnResult(True, None, True, 0, 0, [event])
    ui, calls = recording_ui()
    ui.draw_vortex_effect = lambda *args: calls.append(("vortex", *args))
    play_turn_events(ui, result, player, 6)
    vortex_calls = [call for call in calls if call[0] == "vortex"]
    assert vortex_calls == ([("vortex", (3, 3))] if won else [])
    if won:
        assert calls[0][0] == "combat"


def _fight(glyph, stage_num, boss_defeated=False):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[glyph])
    current = Floor(
        field, [monster], [[0] * len(row) for row in field], (2, 2), (70, 18), None
    )
    player = d.Player(2, 2, 100, 90)
    player.level = 10000
    player.boss_defeated = boss_defeated
    events = []
    engine._process_multi_floor_turn((1, 0), [current], player, [0], [(2, 2)], engine.Counter(), 1,
                 stage_num=stage_num, events=events)
    return next(event for event in events if isinstance(event, Combat))


def test_first_stage_boss_defeat_marks_where_the_boss_stood():
    assert _fight("W", 3).boss_at == (3, 2)
    assert _fight("W", 3, boss_defeated=True).boss_at is None
    assert _fight("a", 3).boss_at is None


def test_stage6_boss_party_marks_its_boss_but_not_the_dungeon_core():
    from arlq import stage6

    floors, player = stage6.build()
    current = floors[-1]
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F"
    )
    player.members.append(d.PartyMember(player.x, player.y, "Knight"))
    player.level = 10000
    player.x, player.y = boss.x, boss.y
    events = []
    engine._process_multi_floor_turn((0, 0), floors, player, [len(floors) - 1], [current.up],
                 engine.Counter(), 1, stage_num=6, events=events)
    combat = next(event for event in events if isinstance(event, Combat))
    assert player.boss_defeated
    assert combat.boss_at == (boss.x, boss.y)

    core = next(e for e in current.entities if isinstance(e, d.Monster)
                and e.tribe.char == d.CHAR_DUNGEON_CORE)
    player.x, player.y = core.x, core.y
    events = []
    engine._process_multi_floor_turn((0, 0), floors, player, [len(floors) - 1], [current.up],
                 engine.Counter(), 2, stage_num=6, events=events)
    fights = [event for event in events if isinstance(event, Combat)]
    assert player.dungeon_core_destroyed and fights
    assert all(fight.won and fight.boss_at is None for fight in fights)
    assert [fight.core_at for fight in fights] == [(core.x, core.y)]
    assert combat.core_at is None
