"""Tests for the gameplay trace record/replay instrumentation
(docs/gameplay-trace-spec.md): the TraceRecorder hooks in update_entities()
(arlq.py) and _step() (stage3.py), plus the ReplayUI/loader in trace.py.
"""

import json
from collections import Counter, deque
from copy import deepcopy
from pathlib import Path

import pytest

from arlq import defs as d
from arlq.arlq import respawn_entity, update_entities
from arlq.stage3 import Floor, _move_player, _process_respawn_queue, _step
from arlq.trace import (
    KEY_TO_DIR,
    ReplayUI,
    TraceRecorder,
    default_replay_output_path,
    load_trace,
)

KEYS = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}


def blank_field():
    return [[" " for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]


def one_floor(entities, **overrides):
    floor = Floor(
        field=blank_field(),
        entities=entities,
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        known_companions=set(),
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )
    for key, value in overrides.items():
        setattr(floor, key, value)
    return floor


def committed_turn(recorder, key, func, *args, **kwargs):
    recorder.begin_turn(key)
    result = func(*args, **kwargs)
    if hasattr(result, "events"):
        recorder.record_events(result.events)
    recorder.commit_turn()
    return recorder.turns[-1]


# --- TraceRecorder / loader / ReplayUI -------------------------------------


def test_recorder_fills_in_defaults_and_tracks_turn_numbers():
    trace = TraceRecorder(params={"stage": 1})
    trace.begin_turn("R")
    trace.set_player(d.Player(2, 2, 1, 90), stage_num=1)
    trace.commit_turn()
    trace.begin_turn("Q")  # a normal (non-quit) turn can still be turn-numbered
    trace.commit_turn()

    assert [t["turn"] for t in trace.turns] == [1, 2]
    assert trace.turns[0]["wall"] is None
    assert trace.turns[0]["contact"] is None
    assert trace.turns[0]["expired"] == []
    assert trace.turns[0]["world"] == []


def test_recorder_quit_turn_has_only_input_and_bumps_turn_count():
    trace = TraceRecorder(params={})
    trace.begin_turn("R")
    trace.commit_turn()
    trace.record_quit()

    assert trace.turns[-1] == {"turn": 2, "input": "Q"}
    trace.set_outcome("quit")
    final = trace.to_dict()["final"]
    assert final == {"outcome": "quit", "turns": 2}


def test_recorder_to_dict_schema_and_write(tmp_path):
    trace = TraceRecorder(params={"stage": 1, "seed": "v1-x-1-1"})
    trace.set_outcome("quit")
    data = trace.to_dict()

    assert data["schema_version"] == 2
    assert "arlq_version" in data
    assert "recorded_at" in data
    assert data["params"] == {"stage": 1, "seed": "v1-x-1-1"}
    assert data["turns"] == []
    assert data["final"] == {"outcome": "quit", "turns": 0}

    out = tmp_path / "trace.json"
    trace.write(out)
    assert json.loads(out.read_text()) == data


def test_load_trace_rejects_wrong_schema_version(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 999, "params": {}, "turns": []}))
    with pytest.raises(ValueError):
        load_trace(path)


def test_replay_ui_feeds_recorded_inputs_and_marks_ran_dry():
    turns = [{"turn": 1, "input": "U"}, {"turn": 2, "input": "R"}]
    ui = ReplayUI(turns, stage=2)

    assert ui.select_stage() == 2
    assert ui.input_direction() == KEY_TO_DIR["U"]
    assert ui.input_direction() == KEY_TO_DIR["R"]
    assert not ui.ran_dry
    assert ui.input_direction() is None  # ran out of recorded input
    assert ui.ran_dry
    assert ui.input_alphabet() is None


def test_replay_ui_stops_at_recorded_quit_without_ran_dry():
    ui = ReplayUI([{"turn": 1, "input": "Q"}], stage=1)
    assert ui.input_direction() is None
    assert not ui.ran_dry


def test_replay_ui_draw_stage_forwards_only_when_given_a_draw_target():
    calls = []

    class Recorder:
        def draw_stage(self, *args, **kwargs):
            calls.append((args, kwargs))

    ReplayUI([], stage=1).draw_stage(hours=1, player=2, message="x")
    assert calls == []

    ReplayUI([], stage=1, draw_ui=Recorder()).draw_stage(hours=1, player=2, message="x")
    assert calls == [((), {"hours": 1, "player": 2, "message": "x"})]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("foo.json", "foo.replay.json"),
        ("dir/foo.json", "dir/foo.replay.json"),
        ("foo", "foo.replay"),
    ],
)
def test_default_replay_output_path(path, expected):
    assert default_replay_output_path(Path(path)) == Path(expected)


# --- Legacy stage (arlq.py update_entities) wall/contact/expired events ----


def test_legacy_wall_blocked():
    player = d.Player(2, 2, 1, 90)
    field = blank_field()
    field[2][3] = d.WALL_CHAR
    trace = TraceRecorder(params={})

    turn = committed_turn(trace, "R", update_entities, KEYS["R"], field, player, [player], set())

    assert turn["wall"] == {"result": "blocked"}
    assert (player.x, player.y) == (2, 2)


def test_legacy_wall_sword_break_reports_remaining_uses():
    player = d.Player(2, 2, 1, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 1
    field = blank_field()
    field[2][3] = d.WALL_CHAR
    trace = TraceRecorder(params={})

    turn = committed_turn(trace, "R", update_entities, KEYS["R"], field, player, [player], set())

    assert turn["wall"] == {"result": "sword_break", "item_uses_left": 0}
    assert (player.x, player.y) == (3, 2)


def test_legacy_wall_pegasus_phase():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    field = blank_field()
    field[2][3] = d.WALL_CHAR
    trace = TraceRecorder(params={})

    turn = committed_turn(trace, "R", update_entities, KEYS["R"], field, player, [player], set())

    assert turn["wall"] == {"result": "pegasus_phase"}
    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)
    assert player.karma == 1


def test_legacy_contact_treasure_locked_and_unlocked():
    player = d.Player(2, 2, 1, 90)
    treasure = d.Treasure(3, 2, "TD")
    field = blank_field()
    trace = TraceRecorder(params={})

    turn = committed_turn(
        trace, "R", update_entities, KEYS["R"], field, player, [player, treasure], set()
    )
    assert turn["contact"] == {"type": "treasure", "id": "TD", "collected": False}

    player2 = d.Player(2, 2, 1, 90)
    treasure2 = d.Treasure(3, 2, "TD")
    turn2 = committed_turn(
        trace, "R", update_entities, KEYS["R"], field, player2, [player2, treasure2], {"TD"}
    )
    assert turn2["contact"] == {"type": "treasure", "id": "TD", "collected": True}


def test_legacy_contact_companion_join():
    player = d.Player(2, 2, 1, 90)
    companion = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    field = blank_field()
    trace = TraceRecorder(params={})

    turn = committed_turn(
        trace, "R", update_entities, KEYS["R"], field, player, [player, companion], set()
    )

    assert turn["contact"] == {"type": "companion", "id": "n"}
    assert player.companion is companion


def test_legacy_contact_monster_win_expires_old_item_as_overwritten():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_taken_from = "d"
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["c"])  # level 10, grants a sword
    field = blank_field()
    trace = TraceRecorder(params={})

    turn = committed_turn(
        trace, "R", update_entities, KEYS["R"], field, player, [player, monster], set()
    )

    assert turn["contact"] == {"type": "monster", "id": "c", "outcome": "win"}
    assert turn["expired"] == [{"type": "item_expired", "item": "d", "reason": "overwritten"}]
    assert player.item == d.ITEM_SWORD_X1_5


def test_legacy_contact_monster_lose_expires_old_item_as_lost_on_defeat():
    player = d.Player(2, 2, 1, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_taken_from = "c"
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])  # level 15, beats a level-1 player
    field = blank_field()
    trace = TraceRecorder(params={})

    turn = committed_turn(
        trace,
        "R",
        update_entities,
        KEYS["R"],
        field,
        player,
        [player, monster],
        set(),
        respawn_point=(5, 5),
    )

    assert turn["contact"] == {"type": "monster", "id": "C", "outcome": "lose", "respawn_to": [5, 5]}
    assert turn["expired"] == [{"type": "item_expired", "item": "c", "reason": "lost_on_defeat"}]
    assert player.item is None
    assert player.item_uses == 0
    assert player.item_taken_from is None


def test_legacy_contact_high_elf_always_refused():
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    field = blank_field()
    trace = TraceRecorder(params={})

    turn = committed_turn(
        trace, "R", update_entities, KEYS["R"], field, player, [player, high_elf], set()
    )

    assert turn["contact"] == {"type": "monster", "id": "H", "outcome": "refused"}


def test_legacy_companion_departed_on_karma_limit():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["l"])  # durability 1
    player.karma = 1
    field = blank_field()
    trace = TraceRecorder(params={})

    turn = committed_turn(trace, "U", update_entities, KEYS["U"], field, player, [player], set())

    assert turn["expired"] == [{"type": "companion_departed", "id": "l"}]
    assert player.companion is None


def test_legacy_world_respawn_event_reports_position(monkeypatch):
    entities = []
    field = blank_field()
    trace = TraceRecorder(params={})
    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_a, **_k: (7, 3))

    entity = respawn_entity(d.CHAR_TO_MONSTER_TRIBE["X"], entities, field)
    trace.add_world_event({"type": "respawn", "kind": "monster", "id": "X", "at": [entity.x, entity.y]})

    assert trace.turns == []  # add_world_event() before begin_turn() is a no-op
    trace.begin_turn("R")
    trace.add_world_event({"type": "respawn", "kind": "monster", "id": "X", "at": [entity.x, entity.y]})
    trace.commit_turn()
    assert trace.turns[-1]["world"] == [{"type": "respawn", "kind": "monster", "id": "X", "at": [7, 3]}]


# --- Stage 3 (stage3.py _step / _move_player / _process_respawn_queue) ----


def test_stage3_wall_pegasus_phase():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    floor_data = one_floor([])
    floor_data.field[2][3] = d.WALL_CHAR
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _move_player(KEYS["R"], floor_data, player, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["wall"] == {"result": "pegasus_phase"}


def test_stage3_wall_pegasus_phase_after_player_state_is_deepcopied():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE[d.CHAR_PEGASUS])
    player = deepcopy(player)
    floor_data = one_floor([])
    floor_data.field[2][3] = d.WALL_CHAR

    _move_player(KEYS["R"], floor_data, player)

    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)


def test_stage3_wall_blocked_when_pegasus_jump_target_is_solid():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    floor_data = one_floor([])
    floor_data.field[2][3] = d.WALL_CHAR
    floor_data.field[2][2 + d.PEGASUS_STEP_X] = d.WALL_CHAR
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _move_player(KEYS["R"], floor_data, player, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["wall"] == {"result": "blocked"}


def test_stage3_elf_contact_granted_and_refused():
    for char, outcome, flags in [("I", "granted", 0), ("J", "granted", 0), ("K", "refused", 0), ("H", "refused", 0)]:
        player = d.Player(2, 2, 1, 90)
        player.stage3_flags = flags
        elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[char])
        floors = [one_floor([elf])]
        floor = [0]
        checkpoint = [(2, 2)]
        trace = TraceRecorder(params={})

        trace.begin_turn("R")
        _step(KEYS["R"], floors, player, floor, checkpoint, Counter(), deque(), 1, trace=trace)
        trace.commit_turn()

        assert trace.turns[-1]["contact"] == {"type": "monster", "id": char, "outcome": outcome}, char


def test_stage3_repeat_elf_contact_is_refused():
    player = d.Player(2, 2, 1, 90)
    player.stage3_met_elves = {"H"}
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    floors = [one_floor([high_elf])]
    floor = [0]
    checkpoint = [(2, 2)]
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _step(KEYS["R"], floors, player, floor, checkpoint, Counter(), deque(), 1, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["contact"] == {"type": "monster", "id": "H", "outcome": "refused"}


def test_stage3_monster_win_and_lose_expire_old_item():
    player = d.Player(2, 2, 200, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_taken_from = "d"
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    floors = [one_floor([wyrm])]
    floor = [0]
    checkpoint = [(2, 2)]
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _step(KEYS["R"], floors, player, floor, checkpoint, Counter(), deque(), 1, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["contact"] == {"type": "monster", "id": "W", "outcome": "win"}
    assert trace.turns[-1]["expired"] == [{"type": "item_expired", "item": "d", "reason": "overwritten"}]

    player2 = d.Player(2, 2, 1, 90)
    player2.item = d.ITEM_SWORD_X1_5
    player2.item_taken_from = "c"
    tough = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])
    floors2 = [one_floor([tough])]
    floor2 = [0]
    checkpoint2 = [(2, 2)]
    trace2 = TraceRecorder(params={})

    trace2.begin_turn("R")
    _step(KEYS["R"], floors2, player2, floor2, checkpoint2, Counter(), deque(), 1, trace=trace2)
    trace2.commit_turn()

    assert trace2.turns[-1]["contact"]["outcome"] == "lose"
    assert trace2.turns[-1]["expired"] == [{"type": "item_expired", "item": "c", "reason": "lost_on_defeat"}]


def test_stage3_stairs_contact_records_floor_transition():
    player = d.Player(2, 2, 1, 90)
    down_floor = one_floor([], down=(3, 2))
    up_floor = one_floor([], up=(1, 1))
    floors = [down_floor, up_floor]
    floor = [0]
    checkpoint = [(2, 2)]
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _step(KEYS["R"], floors, player, floor, checkpoint, Counter(), deque(), 1, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["contact"] == {"type": "stairs", "from_floor": 0, "to_floor": 1}
    assert floor[0] == 1


def test_stage3_companion_departed_on_karma_limit():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"], origin_floor=0)
    player.karma = 5  # p's durability
    floors = [one_floor([])]
    floor = [0]
    checkpoint = [(2, 2)]
    trace = TraceRecorder(params={})

    trace.begin_turn("U")
    _step(KEYS["U"], floors, player, floor, checkpoint, Counter(), deque(), 1, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["expired"] == [{"type": "companion_departed", "id": "p"}]
    assert player.companion is None


def test_stage3_world_respawn_event_includes_floor(monkeypatch):
    floors = [one_floor([]), one_floor([])]
    player = d.Player(2, 2, 1, 90)
    floor = [0]
    queue = Counter({(1, "a"): 1})
    trace = TraceRecorder(params={})

    monkeypatch.setattr("arlq.stage3.find_random_place", lambda *_a, **_k: (6, 4))

    trace.begin_turn("R")
    _process_respawn_queue(floors, player, floor, queue, hours=0, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["world"] == [
        {"type": "respawn", "kind": "monster", "id": "a", "at": [6, 4], "floor": 1}
    ]
    assert queue[(1, "a")] == 0
