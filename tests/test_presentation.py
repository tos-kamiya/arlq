"""Text frontends replay each event once after the turn is committed."""

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
    from arlq.sprite_funcs import SpriteUI

    ui_type = {"blessed": BlessedUI, "pyglet": PygletUI, "sprite": SpriteUI}[frontend]
    ui = ui_type.__new__(ui_type)
    ui.map_mode = False
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
        assert len(trace.turns) == (0 if frontend == "sprite" else 1)
        if frontend != "sprite":
            assert trace.turns[0]["player"]["lp_after_turn"] == player.lp
        calls.append(("effect", pos, victory))

    ui.draw_combat_effect = combat
    engine.run_game(ui, "test", trace=trace, stage_num=1)
    effects = [("effect", (3, 2), False), ("effect", (3, 2) if won else (2, 2), won)]
    if frontend == "sprite":
        expected = [("draw", 0), ("draw", 0), *effects, ("stop",), ("draw", 1)]
    else:
        expected = [("draw", 0), ("stop",), *effects, ("draw", 1)]
    assert calls == expected


@pytest.mark.parametrize(
    "torch_radius", [d.TORCH_RADIUS - 1, d.TORCH_RADIUS, d.TORCH_RADIUS + 1]
)
def test_text_event_path_preserves_legacy_barrier_trace(monkeypatch, torch_radius):
    traces = []
    for event_effects in (False, True):
        engine.rand.set_seed(12345)
        field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
        field[8][16] = d.CHAR_BARRIER
        current = Floor(
            field, [], [[0] * len(row) for row in field], (15, 8), (70, 18), None
        )
        player = d.Player(15, 8, 10, 90)
        monkeypatch.setattr(
            engine,
            "build_single_floor",
            lambda *_, current=current, player=player: ([current], player),
        )
        trace = TraceRecorder({"stage": 1})
        moves = iter([(1, 0), None])
        ui = SimpleNamespace(
            uses_event_effects=event_effects,
            draw_stage=lambda **_: None,
            input_direction=lambda moves=moves: next(moves),
        )
        engine.run_game(
            ui,
            "test",
            trace=trace,
            stage_num=1,
            config=engine.GameConfig(torch_radius=torch_radius),
        )
        traces.append((trace.turns, engine.rand.getstate()))
    assert traces[0] == traces[1]
