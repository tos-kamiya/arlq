"""Presentation events coexist with legacy hooks without changing gameplay."""

from copy import deepcopy

import pytest

from arlq import defs as d
from arlq import game_engine as engine
from arlq.game_events import BarrierHit, Combat, FloorChanged, Rewound
from arlq.game_session import GameSession, LegacyHooks
from arlq.stage_types import Floor
from arlq.trace import TraceRecorder


def make_floor(entities=()):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    return Floor(
        field, list(entities), [[0] * len(row) for row in field], (2, 2), (70, 18), None
    )


def make_session(monkeypatch, floors, player, stage_num=1, hooks=None, trace=None):
    monkeypatch.setattr(engine, "build_single_floor", lambda *_: (floors, player))
    monkeypatch.setattr(engine, "build", lambda *_: (floors, player))
    monkeypatch.setattr(
        engine.stage5, "build_member_trial", lambda *_: (floors, player)
    )
    return GameSession(stage_num, hooks=hooks, trace=trace)


def test_uid_survives_snapshot_without_consuming_randomness():
    engine.rand.set_seed(123)
    state = engine.rand.getstate()
    first = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    second = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    assert first.uid != second.uid
    assert deepcopy(first).uid == first.uid
    assert engine.rand.getstate() == state


@pytest.mark.parametrize("with_hooks", [False, True])
@pytest.mark.parametrize("stage_num", [1, 5])
@pytest.mark.parametrize("won", [False, True])
def test_combat_snapshots_and_legacy_hook(monkeypatch, stage_num, won, with_hooks):
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    current = make_floor([monster])
    player = d.Player(2, 2, 100 if won else 0.1, 90)
    calls = []
    session = make_session(
        monkeypatch,
        [current],
        player,
        stage_num,
        LegacyHooks(combat_effect=lambda *args: calls.append(args))
        if with_hooks
        else None,
    )
    result = session.step((1, 0))
    assert [type(event) for event in result.events] == [Combat]
    event = result.events[0]
    assert event.floor == 0
    assert event.attacker == (2, 2)
    assert event.targets[0][0].uid == monster.uid
    assert event.targets[0][0].glyph == "a"
    assert event.targets[0][1] == (3, 2)
    assert event.won is won
    assert event.lp_delta == pytest.approx(player.lp + d.movement_lp_cost(player) - 90)
    expected = [(3, 2)] if won else [(2, 2)]
    assert calls == (
        [(expected if stage_num == 5 else expected[0], won)] if with_hooks else []
    )
    monster.x = 50
    assert event.targets[0][1] == (3, 2)
    assert (monster in current.entities) is not won


def test_barrier_precedes_combat(monkeypatch):
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    current = make_floor([monster])
    current.field[2][3] = d.CHAR_BARRIER
    player = d.Player(2, 2, 100, 90)
    calls = []
    hooks = LegacyHooks(
        combat_effect=lambda *_: calls.append("combat"),
        barrier_effect=lambda _: calls.append("barrier"),
    )
    session = make_session(monkeypatch, [current], player, hooks=hooks)
    result = session.step((1, 0))
    assert [type(event) for event in result.events] == [BarrierHit, Combat]
    assert result.events[0].at == (3, 2)
    assert result.events[0].amount > 0
    assert calls == ["barrier", "combat"]


@pytest.mark.parametrize("fall", [False, True])
def test_floor_changed_precedes_destination_events(monkeypatch, fall):
    upper, lower = make_floor(), make_floor()
    upper.field[2][3] = d.CHAR_COLLAPSE if fall else d.CHAR_STAIRS_DOWN
    upper.down_stairs = [(3, 2)]
    lower.field[4][4] = d.CHAR_STAIRS_UP
    lower.up_stairs = [(4, 4)]
    if fall:
        lower.field[2][3] = d.CHAR_BARRIER
    calls = []
    player = d.Player(2, 2, 100, 90)
    session = make_session(
        monkeypatch,
        [upper, lower],
        player,
        hooks=LegacyHooks(floor_transition=lambda *args: calls.append(args)),
    )
    result = session.step((1, 0))
    event = result.events[0]
    assert isinstance(event, FloorChanged)
    assert event.floor == 0
    assert event.to_floor == result.floor_after == 1
    assert event.exit_point == (3, 2)
    assert event.kind == ("fall" if fall else "down")
    assert calls[0][0] == event.kind
    if fall:
        assert isinstance(result.events[1], BarrierHit)
        assert result.events[1].floor == 1


def test_rewind_event_survives_early_return_and_copies_trail(monkeypatch):
    current = make_floor([d.Fairy(4, 2, d.CHAR_TO_FAIRY_TRIBE["l"])])
    player = d.Player(2, 2, 10, 90)
    calls = []
    session = make_session(
        monkeypatch, [current], player, 3, LegacyHooks(rewind_transition=calls.append)
    )
    assert session.step((1, 0)).events == []
    result = session.step((1, 0))
    assert [type(event) for event in result.events] == [Rewound]
    event = result.events[0]
    assert event.floor == 0
    assert calls == [event.message]
    assert event.trail == session.loop_trail_by_floor
    saved = deepcopy(event.trail)
    for points in session.loop_trail_by_floor.values():
        points.clear()
    session.loop_trail_by_floor.clear()
    assert event.trail == saved


def test_unconsumed_steps_have_separate_empty_event_lists(monkeypatch):
    session = make_session(monkeypatch, [make_floor()], d.Player(2, 2, 10, 90))
    first, second = session.step((0, 0)), session.step((0, 0))
    assert not first.consumed
    assert first.events == second.events == []
    assert first.events is not second.events


@pytest.mark.parametrize("stage_num", range(1, 7))
def test_collecting_events_preserves_trace_and_random_state(stage_num):
    results = []
    for collect in (False, True):
        engine.rand.set_seed(12345)
        trace = TraceRecorder({"stage": stage_num})
        session = GameSession(stage_num, trace=trace)
        for move in [(1, 0), (0, 1), (-1, 0), (0, -1)] * 20:
            result = session.step(move, collect_events=collect)
            if not collect:
                assert result.events == []
            if session.phase != "playing":
                break
        results.append(
            (
                deepcopy(trace.turns),
                trace.start,
                trace.outcome,
                engine.rand.getstate(),
                session.player.lp,
                session.turn,
            )
        )
    assert results[0] == results[1]


def test_repeat_stop_discards_no_turn_and_emits_nothing(monkeypatch):
    current = make_floor()
    current.field[2][3] = d.CHAR_BARRIER
    current.seen[2][3] = 1
    session = make_session(monkeypatch, [current], d.Player(2, 2, 10, 90))
    result = session.step((1, 0), repeat=True)
    assert not result.consumed
    assert result.stop_repeat
    assert result.events == []
    assert session.turn == 0


@pytest.mark.parametrize("collect", [False, True])
def test_barrier_event_survives_early_elf_return(monkeypatch, collect):
    elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["K"])
    current = make_floor([elf])
    current.field[2][3] = d.CHAR_BARRIER
    player = d.Player(2, 2, 10, 90)
    # A repeated elf encounter returns before respawns and floor handling.
    player.last_contact_monster = (0, 3, 2)
    session = make_session(monkeypatch, [current], player)
    result = session.step((1, 0), collect_events=collect)
    assert result.consumed
    assert [type(event) for event in result.events] == ([BarrierHit] if collect else [])


@pytest.mark.parametrize("scenario", ["win", "lose", "fall", "stairs", "rewind"])
def test_eventful_turns_preserve_trace_when_collection_is_disabled(
    monkeypatch, scenario
):
    runs = []
    for collect in (False, True):
        engine.rand.set_seed(2468)
        current = make_floor()
        floors = [current]
        player = d.Player(2, 2, 0.1 if scenario == "lose" else 100, 90)
        stage_num = 3 if scenario == "rewind" else 1
        moves = [(1, 0)]
        if scenario in ("win", "lose"):
            current.field[2][3] = d.CHAR_BARRIER
            current.entities.append(d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"]))
            expected = [BarrierHit, Combat]
        elif scenario == "rewind":
            current.entities.append(d.Fairy(4, 2, d.CHAR_TO_FAIRY_TRIBE["l"]))
            moves.append((1, 0))
            expected = [Rewound]
        else:
            lower = make_floor()
            floors.append(lower)
            current.field[2][3] = (
                d.CHAR_COLLAPSE if scenario == "fall" else d.CHAR_STAIRS_DOWN
            )
            current.down_stairs = [(3, 2)]
            lower.field[4][4] = d.CHAR_STAIRS_UP
            lower.up_stairs = [(4, 4)]
            expected = [FloorChanged]
        trace = TraceRecorder({"stage": stage_num})
        session = make_session(monkeypatch, floors, player, stage_num, trace=trace)
        for move in moves:
            result = session.step(move, collect_events=collect)
        assert [type(event) for event in result.events] == (expected if collect else [])
        runs.append(
            (
                deepcopy(trace.turns),
                trace.outcome,
                engine.rand.getstate(),
                player.x,
                player.y,
                player.lp,
                session.floor_index,
            )
        )
    assert runs[0] == runs[1]
