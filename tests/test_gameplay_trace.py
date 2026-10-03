"""Tests for gameplay traces, legacy low-level helpers, and replay tooling."""

import json
from collections import Counter, deque
from copy import deepcopy
from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq import game_engine as game_engine_module
from arlq.arlq import respawn_entity, update_entities
from arlq.game_engine import (
    Floor,
    _move_player,
    _process_respawn_queue,
    _step,
    run_game,
)
from arlq.trace import (
    KEY_TO_DIR,
    ReplayUI,
    TraceRecorder,
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
    player = d.Player(2, 2, 1, 90)
    trace.set_start_state(player, floor_index=0)
    trace.begin_turn("R")
    trace.set_player(player, stage_num=1, floor_index=0)
    trace.set_turn_end_lp(89)
    trace.commit_turn()
    trace.begin_turn("Q")  # a normal (non-quit) turn can still be turn-numbered
    trace.commit_turn()

    assert [t["turn"] for t in trace.turns] == [1, 2]
    assert trace.turns[0]["wall"] is None
    assert trace.turns[0]["contact"] is None
    assert trace.turns[0]["expired"] == []
    assert trace.turns[0]["world"] == []
    assert trace.turns[0]["damage"] == []
    assert trace.turns[0]["seen_added_count"] == 0
    assert trace.turns[0]["known_monsters_added"] == []
    assert trace.turns[0]["player"] == {
        "lp": 90,
        "level": 1,
        "attack": d.current_player_attack(player, 1),
        "floor": 0,
        "position": [2, 2],
        "lp_after_turn": 89,
    }
    assert trace.to_dict()["start"] == {"floor": 0, "position": [2, 2], "lp": 90}


def test_recorder_tracks_rewind_relevant_changes_and_truncates_turns():
    trace = TraceRecorder(params={})
    player = d.Player(4, 5, 1, 90)
    trace.set_start_state(player, floor_index=2)
    trace.begin_turn("R")
    trace.set_player(player, stage_num=1, floor_index=2)
    trace.record_damage("barrier")
    trace.record_state_changes(2, ["b", "k"])
    trace.set_turn_end_lp(88)
    trace.commit_turn()
    trace.begin_turn("L")
    trace.set_player(player, stage_num=1, floor_index=2)
    trace.commit_turn()

    trace.truncate_after_turn(1)

    assert len(trace.turns) == 1
    assert trace.to_dict()["final"]["turns"] == 1
    assert trace.turns[0]["damage"] == [{"source": "barrier"}]
    assert trace.turns[0]["seen_added_count"] == 2
    assert trace.turns[0]["known_monsters_added"] == ["b", "k"]


def record_assist_test_turn(trace, key, position, lp=90, floor=0, **events):
    player = d.Player(*position, 1, lp)
    trace.begin_turn(key)
    trace.set_player(player, stage_num=1, floor_index=floor)
    trace.set_turn_end_lp(lp - 1)
    for name, value in events.items():
        if name == "contact":
            trace.record_contact(value)
        elif name == "damage":
            for source in value:
                trace.record_damage(source)
        elif name == "state_changes":
            trace.record_state_changes(*value)
        elif name == "expired":
            trace.add_expired(value)
        elif name == "world":
            trace.add_world_event(value)
        elif name == "wall":
            trace.record_wall(SimpleNamespace(**value))
    trace.commit_turn()


def test_assist_rewind_target_allows_locked_treasure_contact():
    trace = TraceRecorder(params={})
    player = d.Player(2, 2, 1, 90)
    trace.set_start_state(player, floor_index=0)
    record_assist_test_turn(
        trace,
        "R",
        (3, 2),
        lp=89,
        contact={"type": "treasure", "id": "TW", "collected": False},
    )
    record_assist_test_turn(trace, "L", (2, 2), lp=88)

    assert trace.find_overshoot_rewind_target() == (0, 0, (2, 2), 90)


def test_assist_rewind_markers_show_only_recent_safe_return_cells():
    trace = TraceRecorder(params={})
    trace.set_start_state(d.Player(2, 2, 1, 90), floor_index=0)
    record_assist_test_turn(trace, "R", (3, 2), lp=89)
    assert trace.overshoot_rewind_markers(0) == {(2, 2)}

    record_assist_test_turn(trace, "R", (4, 2), lp=88)
    assert trace.overshoot_rewind_markers(0) == {(2, 2), (3, 2)}

    record_assist_test_turn(
        trace,
        "R",
        (5, 2),
        lp=87,
        contact={"type": "monster", "id": "M", "outcome": "win"},
    )
    assert trace.overshoot_rewind_markers(0) == set()


@pytest.mark.parametrize(
    "event",
    [
        {"contact": {"type": "treasure", "id": "TW", "collected": True}},
        {"contact": {"type": "monster", "id": "M", "outcome": "win"}},
        {"damage": ["barrier"]},
        {"state_changes": (1, ["b"])},
        {"expired": {"type": "companion_departed", "id": "p"}},
        {"world": {"type": "respawn", "kind": "monster", "id": "b", "at": [8, 8]}},
        {"wall": {"result": "sword_break", "item_uses_left": 2}},
    ],
)
def test_assist_rewind_target_rejects_state_changing_events(event):
    trace = TraceRecorder(params={})
    player = d.Player(2, 2, 1, 90)
    trace.set_start_state(player, floor_index=0)
    record_assist_test_turn(trace, "R", (3, 2), lp=89, **event)
    record_assist_test_turn(trace, "L", (2, 2), lp=88)

    assert trace.find_overshoot_rewind_target() is None
    assert trace.overshoot_rewind_markers(0) == {(3, 2)}


def test_engine_records_assist_disqualifying_damage_sources(monkeypatch):
    player = d.Player(3, 3, 100, 90)
    floor = one_floor([player])
    trace = TraceRecorder(params={})

    floor.field[player.y][player.x] = d.CHAR_CALTROP
    trace.begin_turn("R")
    game_engine_module._apply_terrain_hazards(
        floor, player, (player.x - 1, player.y), trace=trace
    )
    trace.commit_turn()
    assert trace.turns[-1]["damage"] == [{"source": "caltrop"}]

    floor.field[player.y][player.x] = d.CHAR_FLOOR
    monkeypatch.setattr(game_engine_module, "apply_barrier_damage", lambda *_: True)
    trace.begin_turn("R")
    game_engine_module._apply_terrain_hazards(
        floor, player, (player.x - 1, player.y), trace=trace
    )
    trace.commit_turn()
    assert trace.turns[-1]["damage"] == [{"source": "barrier"}]

    marksman = d.Monster(7, 3, d.CHAR_TO_MONSTER_TRIBE["k"])
    floor.entities.append(marksman)
    trace.begin_turn("R")
    assert game_engine_module._marksman_shoot(floor, player, trace=trace)
    trace.commit_turn()
    assert trace.turns[-1]["damage"] == [{"source": "marksman"}]


def test_run_game_trace_records_start_position_and_end_of_turn_state(monkeypatch):
    player = d.Player(2, 2, 1, 90)
    floor = one_floor([], up=(2, 2), down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2))
    floor.field = [
        [
            d.CHAR_WALL
            if x in (0, d.FIELD_WIDTH - 1) or y in (0, d.FIELD_HEIGHT - 1)
            else d.CHAR_FLOOR
            for x in range(d.FIELD_WIDTH)
        ]
        for y in range(d.FIELD_HEIGHT)
    ]
    monkeypatch.setattr(
        game_engine_module,
        "build_single_floor",
        lambda *_args: ([floor], player),
    )
    inputs = iter([(1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **_kwargs: None,
        input_direction=inputs.__next__,
        input_alphabet=lambda: None,
        map_mode=False,
    )
    trace = TraceRecorder(params={"stage": 1})

    run_game(ui, "seed", stage_num=1, trace=trace)

    data = trace.to_dict()
    assert data["start"] == {"floor": 0, "position": [2, 2], "lp": 90}
    assert data["turns"][0]["player"]["floor"] == 0
    assert data["turns"][0]["player"]["position"] == [3, 2]
    assert data["turns"][0]["player"]["lp_after_turn"] == 89
    assert data["turns"][0]["seen_added_count"] > 0


def test_run_game_applies_assist_rewind_and_truncates_trace(monkeypatch):
    player = d.Player(2, 2, 1, 90)
    floor = one_floor([], up=(2, 2), down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2))
    floor.field = [
        [
            d.CHAR_WALL
            if x in (0, d.FIELD_WIDTH - 1) or y in (0, d.FIELD_HEIGHT - 1)
            else d.CHAR_FLOOR
            for x in range(d.FIELD_WIDTH)
        ]
        for y in range(d.FIELD_HEIGHT)
    ]
    floor.seen = [
        [1 for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)
    ]
    monkeypatch.setattr(
        game_engine_module,
        "build_single_floor",
        lambda *_args: ([floor], player),
    )
    monkeypatch.setattr(
        game_engine_module, "reveal_entities_in_fov", lambda *_args, **_kwargs: None
    )
    inputs = iter([(1, 0), (-1, 0), None])
    drawn_markers = []
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: drawn_markers.append(
            kwargs.get("overshoot_markers", set())
        ),
        input_direction=inputs.__next__,
        input_alphabet=lambda: None,
        map_mode=False,
    )
    trace = TraceRecorder(params={"stage": 1})

    run_game(ui, "seed", stage_num=1, trace=trace)

    assert (player.x, player.y, player.lp) == (2, 2, 90)
    assert trace.turns == [{"turn": 1, "input": "Q"}]
    assert trace.to_dict()["final"]["turns"] == 1
    assert drawn_markers == [set(), {(2, 2)}, set()]


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

    assert data["schema_version"] == 3
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


def test_load_trace_accepts_previous_schema_version(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"schema_version": 2, "params": {}, "turns": []}))

    assert load_trace(path)["schema_version"] == 2


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

    ReplayUI([], stage=1).draw_stage(turn=1, player=2, message="x")
    assert calls == []

    ReplayUI([], stage=1, draw_ui=Recorder()).draw_stage(turn=1, player=2, message="x")
    assert calls == [((), {"turn": 1, "player": 2, "message": "x"})]


# --- Legacy arlq.arlq compatibility API -----------------------------------


def test_fast_forward_continue_waits_on_game_over_screen():
    draws = []
    game_over_inputs = []

    class DrawTarget:
        def draw_stage(self, **kwargs):
            draws.append(kwargs)

        def input_game_over(self):
            game_over_inputs.append(True)
            return None

    ui = ReplayUI(
        [], stage=4, draw_ui=DrawTarget(), continue_play=True, final_state_only=True
    )
    ui.draw_stage(turn=3, message="game over")

    assert ui.input_game_over() is None
    assert draws == [{"turn": 3, "message": "game over"}]
    assert game_over_inputs == [True]


def test_legacy_wall_blocked():
    player = d.Player(2, 2, 1, 90)
    field = blank_field()
    field[2][3] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    turn = committed_turn(trace, "R", update_entities, KEYS["R"], field, player, [player], set())

    assert turn["wall"] == {"result": "blocked"}
    assert (player.x, player.y) == (2, 2)


def test_legacy_wall_sword_break_reports_remaining_uses():
    player = d.Player(2, 2, 1, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 1
    field = blank_field()
    field[2][3] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    turn = committed_turn(trace, "R", update_entities, KEYS["R"], field, player, [player], set())

    assert turn["wall"] == {"result": "sword_break", "item_uses_left": 0}
    assert (player.x, player.y) == (3, 2)


def test_legacy_wall_pegasus_phase():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    field = blank_field()
    field[2][3] = d.CHAR_WALL
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
        trace, "R", update_entities, KEYS["R"], field, player, [player, treasure]
    )
    assert turn["contact"] == {"type": "treasure", "id": "TD", "collected": False}

    player2 = d.Player(2, 2, 1, 90)
    treasure2 = d.Treasure(3, 2, "TD")
    treasure2.unlocked = True
    turn2 = committed_turn(
        trace, "R", update_entities, KEYS["R"], field, player2, [player2, treasure2]
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


# --- Current game_engine turn path ----------------------------------------


def process_engine_turn(trace, key, floors, player, stage_num, turn=1):
    floor = [0]
    checkpoint = [(player.x, player.y)]
    trace.begin_turn(key)
    _step(
        KEYS[key],
        floors,
        player,
        floor,
        checkpoint,
        Counter(),
        deque(),
        turn,
        stage_num=stage_num,
        trace=trace,
    )
    trace.commit_turn()
    return trace.turns[-1]


def test_current_stage1_turn_records_boss_defeat_and_treasure_collection():
    player = d.Player(2, 2, 200, 90)
    dragon = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON])
    treasure = d.Treasure(4, 2, "TD")
    floors = [one_floor([dragon, treasure])]
    trace = TraceRecorder(params={})

    defeat_turn = process_engine_turn(trace, "R", floors, player, stage_num=1)
    collect_turn = process_engine_turn(trace, "R", floors, player, stage_num=1, turn=2)

    assert defeat_turn["contact"] == {
        "type": "monster",
        "id": d.CHAR_DRAGON,
        "outcome": "win",
    }
    assert treasure.unlocked
    assert collect_turn["contact"] == {
        "type": "treasure",
        "id": "TD",
        "collected": True,
    }
    assert player.boss_defeated
    assert player.treasure_collected


def test_current_stage2_high_elf_is_passive_and_traced():
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    floors = [one_floor([high_elf])]
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", floors, player, stage_num=2)

    assert turn["contact"] == {"type": "monster", "id": "H", "outcome": "passive"}
    assert player.lp == 90
    assert (player.x, player.y) == (3, 2)
    assert high_elf in floors[0].entities
    assert high_elf.revealed
    assert "H" in player.known_monsters


def test_current_stage1_turn_records_respawn_created_by_the_same_turn(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["d"])
    floors = [one_floor([monster])]
    trace = TraceRecorder(params={})
    monkeypatch.setattr(
        "arlq.stage_world.find_random_place", lambda *_a, **_k: (5, 2)
    )

    turn = process_engine_turn(trace, "R", floors, player, stage_num=1, turn=65)

    assert turn["contact"] == {"type": "monster", "id": "d", "outcome": "win"}
    assert turn["world"] == [
        {"type": "respawn", "kind": "monster", "id": "d", "at": [5, 2], "floor": 0}
    ]
    assert any(
        isinstance(entity, d.Monster)
        and entity.tribe.char == "d"
        and (entity.x, entity.y) == (5, 2)
        for entity in floors[0].entities
    )


def test_stage3_wall_pegasus_phase():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    floor_data = one_floor([])
    floor_data.field[2][3] = d.CHAR_WALL
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
    floor_data.field[2][3] = d.CHAR_WALL

    _move_player(KEYS["R"], floor_data, player)

    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)


def test_stage3_wall_blocked_when_pegasus_jump_target_is_solid():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    floor_data = one_floor([])
    floor_data.field[2][3] = d.CHAR_WALL
    floor_data.field[2][2 + d.PEGASUS_STEP_X] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _move_player(KEYS["R"], floor_data, player, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["wall"] == {"result": "blocked"}


def test_stage3_elf_contact_granted_and_refused():
    for char, outcome, flags in [("I", "granted", 0), ("J", "granted", 0), ("K", "refused", 0), ("H", "refused", 0)]:
        player = d.Player(2, 2, 1, 90)
        player.elf_stage_flags = flags
        elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[char])
        floors = [one_floor([elf])]
        floor = [0]
        checkpoint = [(2, 2)]
        trace = TraceRecorder(params={})

        trace.begin_turn("R")
        _step(KEYS["R"], floors, player, floor, checkpoint, Counter(), deque(), 1, trace=trace)
        trace.commit_turn()

        assert trace.turns[-1]["contact"] == {"type": "monster", "id": char, "outcome": outcome}, char


def test_lifebringer_raises_permanent_lp_cap_and_restores_to_120():
    player = d.Player(2, 2, 1, 90)
    player.item = d.ITEM_POISONED
    player.item_taken_from = "d"
    lifebringer = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["L"])
    floors = [one_floor([lifebringer])]
    floor = [0]
    trace = TraceRecorder(params={})
    trace.begin_turn("R")

    assert d.player_lp_max(player) == d.LP_MAX

    _step(
        KEYS["R"], floors, player, floor, [(2, 2)], Counter(), deque(), 1,
        trace=trace,
    )
    trace.commit_turn()

    assert player.elf_stage_flags & d.ELF_STAGE_L_FLAG
    assert d.player_lp_max(player) == 105
    assert player.lp == d.LP_OVERCHARGE_MAX
    assert player.level == 1
    assert player.item is None
    assert player.item_taken_from is None
    assert trace.turns[-1]["expired"] == [
        {"type": "item_expired", "item": "d", "reason": "cleansed"}
    ]


def test_lifebringer_cap_limits_feeding_after_overcharge_is_spent():
    player = d.Player(2, 2, 1, 104)
    player.elf_stage_flags |= d.ELF_STAGE_L_FLAG
    player.lifebringer_lp_max = 105

    d.apply_feed(player, 10)

    assert player.lp == 105


def test_stage3_repeat_elf_contact_is_refused():
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    high_elf.met = True
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

    monkeypatch.setattr("arlq.stage_world.find_random_place", lambda *_a, **_k: (6, 4))

    trace.begin_turn("R")
    _process_respawn_queue(floors, player, floor, queue, turn=0, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["world"] == [
        {"type": "respawn", "kind": "monster", "id": "a", "at": [6, 4], "floor": 1}
    ]
    assert queue[(1, "a")] == 0
