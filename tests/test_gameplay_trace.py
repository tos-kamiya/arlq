"""Tests for gameplay traces, legacy low-level helpers, and replay tooling."""

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq import game_engine as game_engine_module
from arlq.game_engine import (
    Floor,
    _move_player,
    _process_multi_floor_turn,
    _process_respawn_queue,
    run_game,
)
from arlq.game_events import Combat
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


# --- TraceRecorder / loader / ReplayUI -------------------------------------


def test_recorder_fills_in_defaults_and_tracks_turn_numbers():
    trace = TraceRecorder(params={"stage": 1})
    player = d.Player(2, 2, 1, 90)
    trace.set_start_state(player, floor_index=0)
    trace.begin_turn("R")
    trace.set_player(player, floor_index=0)
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
        "attack": d.current_player_attack(player),
        "floor": 0,
        "position": [2, 2],
        "lp_after_turn": 89,
    }
    assert trace.to_dict()["start"] == {"floor": 0, "position": [2, 2], "lp": 90}


def test_engine_records_damage_sources(monkeypatch):
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


def test_returning_to_previous_cell_preserves_moves_and_cost(monkeypatch):
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
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: None,
        input_direction=inputs.__next__,
        input_alphabet=lambda: None,
        map_mode=False,
    )
    trace = TraceRecorder(params={"stage": 1})

    run_game(ui, "seed", stage_num=1, trace=trace)

    assert (player.x, player.y, player.lp) == (2, 2, 88)
    assert [turn["input"] for turn in trace.turns] == ["R", "L", "Q"]
    assert trace.to_dict()["final"]["turns"] == 3


def test_replay_preserves_random_state_after_returning_to_previous_cell(monkeypatch):
    def build(*_):
        player = d.Player(10, 10, 1, 100)
        player.rescue_stage = True
        player.members.append(d.PartyMember(10, 10, d.MEMBER_YAWNING_CAT))
        current = one_floor([], up=(1, 1), down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2))
        current.seen = [[1] * d.FIELD_WIDTH for _ in current.field]
        return [current], player

    monkeypatch.setattr(game_engine_module.stage6, "build", build)
    monkeypatch.setattr(game_engine_module.stage6, "advance_spawns", lambda *_: [])

    def explore(current, player):
        player.members[0].exploration_turns += 1
        game_engine_module.rand.randrange(100)

    monkeypatch.setattr(game_engine_module.stage56, "explore_with_cat", explore)
    states = []
    inputs = iter([(1, 0), (-1, 0), (0, 1), None])
    ui = SimpleNamespace(draw_stage=lambda **kw: states.append(
        (kw["player"].x, kw["player"].y, kw["player"].lp,
         kw["player"].members[0].exploration_turns, game_engine_module.rand.getstate())
    ), input_direction=inputs.__next__, map_mode=False)
    game_engine_module.rand.set_seed(17)
    recorded = TraceRecorder(params={})
    run_game(ui, "seed", stage_num=6, trace=recorded)
    expected = states[-1]
    assert [turn["input"] for turn in recorded.turns] == ["R", "L", "D", "Q"]

    replay_states = []
    replay = ReplayUI(recorded.turns, 6)
    replay.draw_stage = lambda **kw: replay_states.append(
        (kw["player"].x, kw["player"].y, kw["player"].lp,
         kw["player"].members[0].exploration_turns, game_engine_module.rand.getstate())
    )
    game_engine_module.rand.set_seed(17)
    run_game(replay, "seed", stage_num=6)
    assert replay_states[-1] == expected


def test_stage6_replays_pre_iris_trace(monkeypatch):
    from arlq.cli import _prepare_cli_session
    import sys

    path = Path(__file__).parent / "fixtures" / "stage6-6.8.0-trace.json"
    monkeypatch.setattr(sys, "argv", ["arlq", "--trace", str(path)])
    args, data, seed, config, _ = _prepare_cli_session()
    recorded = TraceRecorder(params={})
    run_game(ReplayUI(data["turns"], args.stage), seed, stage_num=args.stage,
             config=config, trace=recorded)
    assert recorded.start == data["start"]
    assert recorded.turns[:len(data["turns"])] == data["turns"]


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
    trace.write_outputs([out])
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


# --- Current game_engine turn path ----------------------------------------


def process_engine_turn(trace, key, floors, player, stage_num, turn=1):
    floor = [0]
    checkpoint = [(player.x, player.y)]
    trace.begin_turn(key)
    _process_multi_floor_turn(
        KEYS[key],
        floors,
        player,
        floor,
        checkpoint,
        Counter(),
        turn,
        stage_num=stage_num,
        trace=trace,
    )
    trace.commit_turn()
    return trace.turns[-1]


def test_engine_wall_blocked():
    player = d.Player(2, 2, 1, 90)
    floors = [one_floor([])]
    floors[0].field[2][3] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", floors, player, stage_num=1)

    assert turn["wall"] == {"result": "blocked"}
    assert (player.x, player.y) == (2, 2)


def test_engine_wall_sword_break_reports_remaining_uses():
    player = d.Player(2, 2, 1, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 1
    floors = [one_floor([])]
    floors[0].field[2][3] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", floors, player, stage_num=1)

    assert turn["wall"] == {"result": "sword_break", "item_uses_left": 0}
    assert (player.x, player.y) == (3, 2)


def test_engine_wall_pegasus_phase():
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"])
    floors = [one_floor([])]
    floors[0].field[2][3] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", floors, player, stage_num=1)

    assert turn["wall"] == {"result": "pegasus_phase"}
    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)
    assert player.karma == 1


def test_engine_contact_treasure_locked_and_unlocked():
    player = d.Player(2, 2, 1, 90)
    treasure = d.Treasure(3, 2, "TD")
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", [one_floor([treasure])], player, stage_num=1)
    assert turn["contact"] == {"type": "treasure", "id": "TD", "collected": False}

    player2 = d.Player(2, 2, 1, 90)
    treasure2 = d.Treasure(3, 2, "TD")
    treasure2.unlocked = True
    turn2 = process_engine_turn(trace, "R", [one_floor([treasure2])], player2, stage_num=1)
    assert turn2["contact"] == {"type": "treasure", "id": "TD", "collected": True}


def test_engine_contact_fairy_join():
    player = d.Player(2, 2, 1, 90)
    fairy = d.Fairy(3, 2, d.CHAR_TO_FAIRY_TRIBE["n"])
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", [one_floor([fairy])], player, stage_num=1)

    assert turn["contact"] == {"type": "companion", "id": "n"}
    assert player.fairy is fairy


def test_engine_contact_monster_win_expires_old_item_as_overwritten():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_taken_from = "d"
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["c"])  # level 10, grants a sword
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", [one_floor([monster])], player, stage_num=1)

    assert turn["contact"] == {"type": "monster", "id": "c", "outcome": "win"}
    assert turn["expired"] == [{"type": "item_expired", "item": "d", "reason": "overwritten"}]
    assert player.item == d.ITEM_SWORD_X1_5


def test_engine_contact_monster_lose_expires_old_item_as_lost_on_defeat():
    player = d.Player(2, 2, 1, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_taken_from = "c"
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])  # level 15, beats a level-1 player
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", [one_floor([monster])], player, stage_num=1)

    assert turn["contact"]["type"] == "monster"
    assert turn["contact"]["id"] == "C"
    assert turn["contact"]["outcome"] == "lose"
    assert turn["contact"]["respawn_to"] == [2, 2]
    assert turn["expired"] == [{"type": "item_expired", "item": "c", "reason": "lost_on_defeat"}]
    assert player.item is None
    assert player.item_uses == 0
    assert player.item_taken_from is None


def test_engine_contact_high_elf_refused():
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", [one_floor([high_elf])], player, stage_num=3)

    assert turn["contact"] == {"type": "monster", "id": "H", "outcome": "refused"}


def test_engine_fairy_departed_on_karma_limit():
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["n"])
    player.karma = player.fairy.durability
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "U", [one_floor([])], player, stage_num=1)

    assert turn["expired"] == [{"type": "companion_departed", "id": "n"}]
    assert player.fairy is None


def test_world_event_is_recorded_only_inside_a_turn():
    trace = TraceRecorder(params={})
    event = {"type": "respawn", "kind": "monster", "id": "X", "at": [7, 3]}

    trace.add_world_event(event)
    assert trace.turns == []  # add_world_event() before begin_turn() is a no-op
    trace.begin_turn("R")
    trace.add_world_event(event)
    trace.commit_turn()
    assert trace.turns[-1]["world"] == [event]


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


@pytest.mark.parametrize("stage_num", [1, 2, 3, 4])
def test_current_stage2_high_elf_is_passive_and_traced(stage_num):
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.HIGH_ELF_DECOY)
    floors = [one_floor([high_elf])]
    trace = TraceRecorder(params={})

    turn = process_engine_turn(trace, "R", floors, player, stage_num=stage_num)

    assert turn["contact"] == {"type": "monster", "id": "H", "outcome": "passive"}
    assert player.lp == 90
    assert (player.x, player.y) == (3, 2)
    assert high_elf in floors[0].entities
    assert high_elf.revealed
    assert "H" in player.known_monsters


def test_high_elf_decoy_contact_does_not_emit_combat_event():
    player = d.Player(2, 2, 1, 90)
    player.last_encounter_party = "a"
    high_elf = d.Monster(3, 2, d.HIGH_ELF_DECOY)
    floors = [one_floor([high_elf])]

    events = []

    game_engine_module._process_multi_floor_turn(
        KEYS["R"], floors, player, [0], [(2, 2)], Counter(), 1,
        stage_num=2, events=events,
    )

    assert not any(isinstance(event, Combat) for event in events)
    assert high_elf in floors[0].entities
    assert player.last_encounter_party == "a"
    assert (player.x, player.y, player.lp) == (3, 2, 90)


def test_current_stage1_turn_records_respawn_created_by_the_same_turn(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["d"])
    floors = [one_floor([monster])]
    trace = TraceRecorder(params={})
    monkeypatch.setattr(
        "arlq.stage_world.find_random_place", lambda *_a, **_k: (6, 2)
    )

    turn = process_engine_turn(trace, "R", floors, player, stage_num=1, turn=65)

    assert turn["contact"] == {"type": "monster", "id": "d", "outcome": "win"}
    assert turn["world"] == [
        {"type": "respawn", "kind": "monster", "id": "d", "at": [6, 2], "floor": 0}
    ]
    assert any(
        isinstance(entity, d.Monster)
        and entity.tribe.char == "d"
        and (entity.x, entity.y) == (6, 2)
        for entity in floors[0].entities
    )


def test_sword_break_exposes_outer_wall_as_column():
    field = [[d.CHAR_WALL] * 9 for _ in range(5)]
    for row in field:
        row[3:6] = [d.CHAR_FLOOR] * 3
    floor_data = Floor(field, [], [[1] * 9 for _ in field], (3, 2), (5, 2), None)
    floor_data.update_outer_wall_decor()
    assert floor_data.decor[2][:3] == [d.DECOR_OUTER_WALL, d.DECOR_OUTER_WALL, d.DECOR_NONE]
    player = d.Player(3, 2, 10, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 2
    _move_player(KEYS['L'], floor_data, player)
    assert field[2][2] == d.CHAR_FLOOR
    assert floor_data.decor[2][1] == d.DECOR_NONE
    assert floor_data.decor[2][0] == d.DECOR_OUTER_WALL


def _torch_floor():
    # Rows 0..7; rows 2 and 5 get torches (WALL_TORCH_ROW_OFFSETS).
    field = [[d.CHAR_WALL] * 12 for _ in range(8)]
    for y in range(1, 7):
        field[y][3:9] = [d.CHAR_FLOOR] * 6
    # Row 5's west edge is a hidden passage: no torch gives it away.
    field[5][3] = d.CHAR_HIDDEN_D_GATE
    return Floor(field, [], [[1] * 12 for _ in field], (4, 2), (7, 2), None)


def test_wall_torches_mark_west_and_east_edge_walls_of_every_few_rows():
    floor_data = _torch_floor()
    floor_data.place_wall_torch_decor()
    floor_data.update_outer_wall_decor()
    torches = {(x, y): value for y, row in enumerate(floor_data.decor)
               for x, value in enumerate(row) if value in d.DECOR_WALL_TORCHES}
    assert torches == {
        (2, 2): d.DECOR_WALL_TORCH_EAST, (9, 2): d.DECOR_WALL_TORCH_WEST,
        (9, 5): d.DECOR_WALL_TORCH_WEST,
    }


def test_sword_break_removes_the_torch_of_the_broken_wall():
    floor_data = _torch_floor()
    floor_data.place_wall_torch_decor()
    floor_data.update_outer_wall_decor()
    player = d.Player(3, 2, 10, 90)
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 2
    _move_player(KEYS['L'], floor_data, player)
    assert floor_data.field[2][2] == d.CHAR_FLOOR
    assert floor_data.decor[2][2] == d.DECOR_NONE
    # The wall now at the edge gets no torch.
    assert floor_data.decor[2][1] not in d.DECOR_WALL_TORCHES
    assert floor_data.decor[2][9] == d.DECOR_WALL_TORCH_WEST


@pytest.mark.parametrize('stage_num', [1, 3, 6])
def test_stages_start_with_torches_on_their_edge_walls_only(stage_num):
    from arlq.game_session import GameSession
    session = GameSession(stage_num)
    walls = (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
    for floor_data in session.floors:
        torches = [(x, y, value) for y, row in enumerate(floor_data.decor)
                   for x, value in enumerate(row) if value in d.DECOR_WALL_TORCHES]
        assert torches
        for x, y, value in torches:
            row = floor_data.field[y]
            assert row[x] == d.CHAR_WALL
            assert y % (d.TILE_HEIGHT + 1) in d.WALL_TORCH_ROW_OFFSETS
            interior = [i for i, cell in enumerate(row) if cell not in walls]
            assert x == (interior[0] - 1 if value == d.DECOR_WALL_TORCH_EAST
                         else interior[-1] + 1)


def test_top_and_bottom_edge_walls_stay_columns_when_exposed():
    field = [[d.CHAR_WALL] * 5 for _ in range(5)]
    field[2][2] = d.CHAR_FLOOR
    floor_data = Floor(field, [], [[1] * 5 for _ in field], (2, 2), (2, 2), None)
    floor_data.update_outer_wall_decor()
    assert floor_data.decor[0][2] == d.DECOR_OUTER_WALL
    assert floor_data.decor[4][2] == d.DECOR_OUTER_WALL
    field[1][2] = d.CHAR_FLOOR
    field[3][2] = d.CHAR_FLOOR
    floor_data.update_outer_wall_decor()
    assert floor_data.decor[0][2] == d.DECOR_NONE
    assert floor_data.decor[4][2] == d.DECOR_NONE


def test_interior_solid_wall_is_flat_until_a_diagonal_cell_opens():
    field = [[d.CHAR_FLOOR] * 7 for _ in range(7)]
    for y in range(1, 6):
        for x in range(1, 6):
            field[y][x] = d.CHAR_WALL
    floor_data = Floor(field, [], [[1] * 7 for _ in field], (0, 0), (6, 6), None)
    floor_data.update_outer_wall_decor()
    assert floor_data.decor[3][3] == d.DECOR_BURIED_WALL
    assert floor_data.decor[1][3] == d.DECOR_NONE

    field[2][2] = d.CHAR_FLOOR
    floor_data.update_outer_wall_decor()
    assert floor_data.decor[3][3] == d.DECOR_NONE
    assert floor_data.decor[4][4] == d.DECOR_BURIED_WALL


@pytest.mark.parametrize(
    ('edge', 'diagonal'),
    [((0, 2), (1, 1)), ((4, 2), (3, 1)),
     ((2, 0), (1, 1)), ((2, 4), (1, 3))],
)
def test_edge_wall_stays_a_column_when_diagonally_exposed(edge, diagonal):
    field = [[d.CHAR_WALL] * 5 for _ in range(5)]
    field[2][2] = d.CHAR_FLOOR
    floor_data = Floor(field, [], [[1] * 5 for _ in field], (2, 2), (2, 2), None)
    floor_data.update_outer_wall_decor()
    x, y = edge
    assert floor_data.decor[y][x] == d.DECOR_OUTER_WALL

    dx, dy = diagonal
    field[dy][dx] = d.CHAR_FLOOR
    floor_data.update_outer_wall_decor()
    assert floor_data.decor[y][x] == d.DECOR_NONE


def test_stage3_wall_pegasus_phase():
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"])
    floor_data = one_floor([])
    floor_data.field[2][3] = d.CHAR_WALL
    trace = TraceRecorder(params={})

    trace.begin_turn("R")
    _move_player(KEYS["R"], floor_data, player, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["wall"] == {"result": "pegasus_phase"}


def test_stage3_wall_pegasus_phase_after_player_state_is_deepcopied():
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE[d.CHAR_PEGASUS])
    player = deepcopy(player)
    floor_data = one_floor([])
    floor_data.field[2][3] = d.CHAR_WALL

    _move_player(KEYS["R"], floor_data, player)

    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)


def test_stage3_wall_blocked_when_pegasus_jump_target_is_solid():
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"])
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
        _process_multi_floor_turn(KEYS["R"], floors, player, floor, checkpoint, Counter(), 1, trace=trace)
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

    _process_multi_floor_turn(
        KEYS["R"], floors, player, floor, [(2, 2)], Counter(), 1,
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
    _process_multi_floor_turn(KEYS["R"], floors, player, floor, checkpoint, Counter(), 1, trace=trace)
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
    _process_multi_floor_turn(KEYS["R"], floors, player, floor, checkpoint, Counter(), 1, trace=trace)
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
    _process_multi_floor_turn(KEYS["R"], floors2, player2, floor2, checkpoint2, Counter(), 1, trace=trace2)
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
    _process_multi_floor_turn(KEYS["R"], floors, player, floor, checkpoint, Counter(), 1, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["contact"] == {"type": "stairs", "from_floor": 0, "to_floor": 1}
    assert floor[0] == 1


def test_stage3_fairy_departed_on_karma_limit():
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"], origin_floor=0)
    player.karma = 5  # p's durability
    floors = [one_floor([])]
    floor = [0]
    checkpoint = [(2, 2)]
    trace = TraceRecorder(params={})

    trace.begin_turn("U")
    _process_multi_floor_turn(KEYS["U"], floors, player, floor, checkpoint, Counter(), 1, trace=trace)
    trace.commit_turn()

    assert trace.turns[-1]["expired"] == [{"type": "companion_departed", "id": "p"}]
    assert player.fairy is None


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


@pytest.mark.parametrize("flags, item, guardian, allowed", [
    (0, None, False, False),
    (d.ELF_STAGE_H_FLAG, None, False, True),
    (d.ELF_STAGE_H_FLAG, d.ITEM_SWORD_CURSED, False, False),
    (0, None, True, True),
])
def test_pegasus_barrier_landing_requires_protection(flags, item, guardian, allowed):
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"])
    player.elf_stage_flags = flags
    player.item = item
    if guardian:
        player.members.append(d.PartyMember(0, 0, d.MEMBER_GUARDIAN))
    floor = one_floor([])
    floor.field[2][3] = d.CHAR_WALL
    floor.field[2][2 + d.PEGASUS_STEP_X] = d.CHAR_BARRIER
    result = _move_player(KEYS["R"], floor, player)
    assert result.result == ("pegasus_phase" if allowed else "blocked")
    assert player.x == (2 + d.PEGASUS_STEP_X if allowed else 2)


@pytest.mark.parametrize("rogue", [False, True])
def test_pegasus_landing_on_golem_wall(rogue):
    player = d.Player(2, 2, 1, 90)
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"])
    if rogue:
        player.members.append(d.PartyMember(0, 0, d.MEMBER_ROGUE))
    floor = one_floor([])
    floor.field[2][3] = d.CHAR_WALL
    target = (2 + d.PEGASUS_STEP_X, 2)
    floor.field[target[1]][target[0]] = d.CHAR_GOLEM_WALL
    result = _move_player(KEYS["R"], floor, player)
    assert result.result == ("pegasus_phase" if rogue else "blocked")
    assert ((player.x, player.y) == target) == rogue
    assert (target in floor.broken_walls) == rogue
    assert floor.field[target[1]][target[0]] == (d.CHAR_FLOOR if rogue else d.CHAR_GOLEM_WALL)


def test_replay_discards_input_until_continuation_even_when_fast_forwarding():
    calls = []

    class UI:
        def begin_replay(self):
            calls.append("begin")

        def poll_events(self):
            calls.append("poll")
            return False

        def end_replay(self):
            calls.append("end")

        def input_direction(self):
            calls.append("live")
            return (1, 0)

    ui = ReplayUI([{"input": "U"}], 1, UI(), continue_play=True, final_state_only=True)
    assert ui.input_direction() == KEY_TO_DIR["U"]
    assert ui.input_direction() == (1, 0)
    assert ui.input_direction() == (1, 0)
    ui.finish_replay()
    assert calls == ["begin", "poll", "poll", "end", "live", "live"]


@pytest.mark.parametrize("fast_forward", [False, True])
def test_replay_poll_can_cancel_before_recorded_input(fast_forward):
    class UI:
        def poll_events(self):
            return True

    ui = ReplayUI([{"input": "U"}], 1, UI(), final_state_only=fast_forward)
    assert ui.input_direction() is None
    assert not ui.ran_dry


@pytest.mark.parametrize("quit_key", ["q", "Q", "escape"])
def test_terminal_replay_discards_other_keys_and_accepts_quit(quit_key):
    from types import SimpleNamespace
    from arlq.blessed_funcs import BlessedUI

    class Key(str):
        @property
        def code(self):
            return 27 if self == "escape" else None

    keys = iter([Key("w"), Key(quit_key), Key("d"), ""])
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(KEY_ESCAPE=27, inkey=lambda timeout: next(keys))
    assert ui.poll_events()
    assert next(keys, None) is None
