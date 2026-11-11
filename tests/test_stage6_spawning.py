from collections import Counter

import pytest

from arlq import defs as d, game_engine, stage6, stage56
from arlq.stage_types import Floor


def floor():
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    return Floor(field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (2, 2), None)


def monster(x, y, char="a"):
    return d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[char])


def test_spawn_accepts_eight_and_rejects_nine(monkeypatch):
    current = floor()
    current.entities = [monster(10, y) for y in range(2, 9)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 9)])
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert len(stage56.monster_party(current, current.entities[-1])) == 8
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))


def test_spawn_checks_both_sides_and_special_monsters(monkeypatch):
    current = floor()
    current.entities = [monster(10, y) for y in (2, 3, 4, 5, 7, 8, 9, 10)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 6)])
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    current.entities = [monster(10, 5, "c")]
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    current.entities = [monster(10, 5)]
    assert stage6.spawn_monster(current, 0, variant=("c", 1))


def test_spawn_tries_at_most_ten_distinct_positions(monkeypatch):
    current = floor()
    current.entities = [monster(10, y) for y in range(2, 22, 2)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, y) for y in range(3, 24, 2)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    attempts = []
    monkeypatch.setattr(stage6, "_can_join_at", lambda *args, **kwargs: attempts.append(args[2]) or False)
    assert not stage6.spawn_monster(current, 0, variant=("a", 1), prefer_adjacent=False)
    assert len(attempts) == d.STAGE6_SPAWN_ATTEMPTS
    assert len(current.entities) == 10


def test_floor2_spawn_queue_has_one_vortex_slot(monkeypatch):
    current = floor()
    monkeypatch.setattr(stage6, "_open_points", lambda _: [])
    monkeypatch.setattr(stage56, "_open_points", lambda *_args, **_kwargs: [])

    assert not stage6.spawn_monster(current, 1)

    assert current.monster_spawn_queue.count(("V", 1)) == 1


def test_wyrm_spawn_ranks_by_floor():
    assert [(count, rank) for char, count, rank, _ in d.STAGE6_ROSTER[0] if char == "w"] == []
    assert [(count, rank) for char, count, rank, _ in d.STAGE6_ROSTER[1] if char == "w"] == [(1, 1)]
    assert [(count, rank) for char, count, rank, _ in d.STAGE6_ROSTER[2] if char == "w"] == [(2, 1), (1, 2)]


def test_defeat_does_not_queue_monster_respawn():
    current = floor()
    enemy = monster(5, 5, "b")
    current.entities.append(enemy)
    player = d.Player(5, 5, 100, d.LP_INIT)
    queue = Counter()
    game_engine._resolve_party_contact(enemy, current, [current], player, [0], [(1, 1)], queue, None, 6)
    assert not queue


def test_vortex_keeps_monster_when_no_safe_destination(monkeypatch):
    current = floor()
    enemy = monster(10, 8)
    current.entities.append(enemy)
    player = d.Player(1, 1, 1, d.LP_INIT)
    monkeypatch.setattr(game_engine, "iterate_ellipse_points", lambda *_: [(10, 8)])
    game_engine._vortex_rearrange(current, player, 0, (10, 8))
    assert enemy in current.entities
    assert (enemy.x, enemy.y) == (10, 8)


@pytest.mark.parametrize("stage_num", [3, 4, 5, 6])
@pytest.mark.parametrize("rank, expected_radius", [(1, 1.0), (2, 1.2)])
def test_vortex_uses_same_rearrangement_for_every_stage(monkeypatch, stage_num, rank, expected_radius):
    current = floor()
    player = d.Player(1, 1, 100, d.LP_INIT)
    vortex = d.Monster(10, 8, d.CHAR_TO_MONSTER_TRIBE["V"], rank)
    calls = []
    monkeypatch.setattr(game_engine, "_vortex_rearrange", lambda *args, **kwargs: calls.append(kwargs))
    game_engine._defeat_monster(vortex, current, player, [0], [(1, 1)], Counter(),
                                floors=[current], stage_num=stage_num)
    assert calls == [{"floors": [current], "radius_multiplier": expected_radius}]


def test_spawn_can_prefer_vertical_neighbor(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage6.rand, "choice", lambda values: values[0])
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert (current.entities[-1].x, current.entities[-1].y) == (10, 9)


@pytest.mark.parametrize("char,rank", [("w", 1), ("w", 2), ("f", 2)])
def test_spawn_joins_barrier_monster_and_clears_spawn_cell(monkeypatch, char, rank):
    current = floor()
    source = d.Monster(10, 10, d.CHAR_TO_MONSTER_TRIBE[char], rank)
    current.entities.append(source)
    stage56.place_monster_barriers(current, source)
    current.persistent_barriers.add((10, 9))
    monkeypatch.setattr(stage6, "_open_points", lambda _: [])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)

    assert stage6.spawn_monster(current, 2, variant=("a", 1))
    joined = current.entities[-1]
    assert (joined.x, joined.y) == (10, 9)
    assert len(stage56.monster_party(current, source)) == 2
    assert current.field[9][10] == d.CHAR_FLOOR
    assert (10, 9) not in current.persistent_barriers
    assert current.field[10][11] == d.CHAR_BARRIER


def test_failed_spawn_does_not_remove_barrier(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10, "c")]
    current.field[9][10] = d.CHAR_BARRIER
    current.persistent_barriers.add((10, 9))
    monkeypatch.setattr(stage6, "_open_points", lambda _: [])
    monkeypatch.setattr(stage56, "_open_points", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)

    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    assert current.field[9][10] == d.CHAR_BARRIER
    assert (10, 9) in current.persistent_barriers


def test_special_spawn_does_not_prefer_neighbors(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("c", 1))
    assert (current.entities[-1].x, current.entities[-1].y) == (20, 10)


def test_timed_spawn_glows_but_initial_spawn_does_not(monkeypatch):
    current = floor()
    player = d.Player(4, 4, 1, d.LP_INIT)
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert current.respawn_glows == {}
    current.entities.clear()
    stage6.advance_spawns([current], player, 0, d.STAGE6_SPAWN_INTERVAL - 1)
    assert current.respawn_glows == {(10, 10): d.RESPAWN_GLOW_TURNS}
    assert game_engine.respawn_glow_cells(current) == {(10, 10)}
    current.entities.clear()
    assert game_engine.respawn_glow_cells(current) == set()


def test_failed_timed_spawn_does_not_glow(monkeypatch):
    current = floor()
    player = d.Player(4, 4, 1, d.LP_INIT)
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    stage6.advance_spawns([current], player, 0, d.STAGE6_SPAWN_INTERVAL - 1)
    assert current.respawn_glows == {}


def test_initial_spawn_does_not_prefer_neighbors(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("a", 1), prefer_adjacent=False)
    assert (current.entities[-1].x, current.entities[-1].y) == (20, 10)


def test_spawn_excludes_blocked_sections(monkeypatch):
    current = floor()
    current.monster_spawn_blocked_rooms = {stage6.tile_at((10, 10))}
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10), (40, 10)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("a", 1), prefer_adjacent=False)
    assert (current.entities[-1].x, current.entities[-1].y) == (40, 10)


def test_rare_amoeba_spawn_weight_is_half_of_roster_weight(monkeypatch):
    current = floor()
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
    assert stage6.spawn_monster(current, 2)
    captured = current.monster_spawn_queue
    for char, count, rank, spawn_weight in d.STAGE6_ROSTER[2]:
        assert captured.count((char, rank)) == count * spawn_weight


def test_bison_variants_have_halved_weights(monkeypatch):
    for floor_index, rank in ((0, 1), (1, 2), (2, 2), (3, 3)):
        current = floor()
        monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
        monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
        assert stage6.spawn_monster(current, floor_index)
        captured = current.monster_spawn_queue
        weight = next(count for char, count, r, _ in d.STAGE6_ROSTER[floor_index]
                      if char == "b" and r == rank)
        assert captured.count(("b", rank)) == weight


def test_golem_weight_is_halved_only_on_second_floor(monkeypatch):
    for floor_index in range(3):
        current = floor()
        monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
        monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
        assert stage6.spawn_monster(current, floor_index)
        captured = current.monster_spawn_queue
        weight, spawn_weight = next(
            (count, spawn_weight)
            for char, count, rank, spawn_weight in d.STAGE6_ROSTER[floor_index]
            if char == "g" and rank == 1
        )
        assert captured.count(("g", 1)) == weight * spawn_weight


def test_first_floor_doubles_cobra_weight_using_amoeba_weight():
    roster = d.STAGE6_ROSTER[0]
    assert next(count for char, count, rank, _ in roster if (char, rank) == ("f", 1)) == 2
    assert next(count for char, count, rank, _ in roster if (char, rank) == ("a", 1)) == 12


def test_bridgehead_restores_only_on_entry_and_preserves_higher_lp():
    first, second = floor(), floor()
    first.bridgehead = (10, 10)
    player = d.Player(10, 10, 1, 25)
    stage6.recover_at_bridgehead([first, second], player, 0, 0, (9, 10))
    assert player.lp == 60
    player.lp = 90
    stage6.recover_at_bridgehead([first, second], player, 0, 0, (9, 10))
    assert player.lp == 90
    player.lp = 20
    stage6.recover_at_bridgehead([first, second], player, 0, 0, (11, 10))
    assert player.lp == 20
    stage6.recover_at_bridgehead([first, second], player, 1, 1, (9, 10))
    assert player.lp == 20
    stage6.recover_at_bridgehead([first, second], player, 0, 1, (10, 10))
    assert player.lp == 60


def test_bridgehead_on_another_floor_restores_on_entry():
    from arlq import bridgehead

    first, second = floor(), floor()
    second.bridgehead = (10, 10)
    player = d.Player(10, 10, 1, 25)
    assert bridgehead.recover_at_bridgehead([first, second], player, 1, 0, (10, 10))
    assert player.lp == 60
    player.lp = 20
    assert not bridgehead.recover_at_bridgehead([first, second], player, 1, 1, (11, 10))
    assert player.lp == 20


def test_bridgehead_in_stage3_works_in_game_and_replay(monkeypatch):
    from types import SimpleNamespace
    from arlq import stage_replay
    from arlq.arlq import GameConfig
    from arlq.stage_types import ReplayContext

    def build(*_args):
        current = floor()
        current.bridgehead = (10, 10)
        return [current], d.Player(9, 10, 1, 25)

    monkeypatch.setattr(game_engine, "build", build)
    monkeypatch.setattr(stage_replay, "build", build)
    frames = []
    moves = iter([(1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: frames.append(kwargs["player"].lp),
        input_direction=lambda: next(moves), map_mode=False,
    )
    game_engine.run_game(ui, "test", stage_num=3)
    replay = ReplayContext(3, 123, GameConfig())
    replay.operations.append((1, 0))
    _, replayed_player, *_ = stage_replay.replay_to_operation(replay, 1)
    assert frames == [25, 60]
    assert replayed_player.lp == 60


def test_bridgehead_healing_persists_after_leaving_in_game_loop(monkeypatch):
    from types import SimpleNamespace

    current = floor()
    current.bridgehead = (10, 10)
    current.seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    player = d.Player(9, 10, 1, 25)
    monkeypatch.setattr(stage6, "build", lambda *_: ([current], player))
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: None)
    frames = []
    moves = iter([(1, 0), (-1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: frames.append((kwargs["player"].x, kwargs["player"].lp)),
        input_direction=lambda: next(moves),
        map_mode=False,
    )
    from arlq.trace import TraceRecorder
    trace = TraceRecorder(params={})
    game_engine.run_game(ui, "test", stage_num=6, trace=trace)
    assert frames == [(9, 25), (10, 60), (9, 59)]
    assert not trace.turns[0].get("world")
    assert len(trace.turns) == 3


def test_bridgehead_entry_does_not_heal_above_sixty(monkeypatch):
    from types import SimpleNamespace
    from arlq.trace import TraceRecorder

    current = floor()
    current.bridgehead = (10, 10)
    current.seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    player = d.Player(9, 10, 1, 90)
    monkeypatch.setattr(stage6, "build", lambda *_: ([current], player))
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: None)
    frames = []
    moves = iter([(1, 0), (-1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: frames.append((kwargs["player"].x, kwargs["player"].lp)),
        input_direction=lambda: next(moves), map_mode=False,
    )
    trace = TraceRecorder(params={})
    game_engine.run_game(ui, "test", stage_num=6, trace=trace)
    assert frames == [(9, 90), (10, 89), (9, 88)]
    assert not trace.turns[0].get("world")
    assert len(trace.turns) == 3


def test_timed_spawn_is_recorded_as_world_change(monkeypatch):
    from arlq.trace import TraceRecorder

    current = floor()
    player = d.Player(4, 4, 1, d.LP_INIT)
    spawned = monster(10, 10)
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: [(0, spawned)])
    trace = TraceRecorder(params={})
    trace.begin_turn("R")
    game_engine._step((1, 0), [current], player, [0], [(4, 4)], Counter(), 9,
                      stage_num=6, trace=trace)
    trace.commit_turn()
    assert trace.turns[0]["world"] == [{
        "type": "spawn", "kind": "monster", "id": "a", "at": [10, 10], "floor": 0,
    }]


def test_simultaneous_spawns_are_all_recorded(monkeypatch):
    from arlq.trace import TraceRecorder

    floors = [floor() for _ in range(3)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    monsters = [monster(10 + index, 10) for index in range(3)]
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: list(enumerate(monsters)))
    trace = TraceRecorder(params={})
    trace.begin_turn("R")
    game_engine._step((1, 0), floors, player, [0], [(4, 4)], Counter(), 14,
                      stage_num=6, trace=trace)
    trace.commit_turn()
    assert [(event["floor"], event["at"]) for event in trace.turns[0]["world"]] == [
        (0, [10, 10]), (1, [11, 10]), (2, [12, 10]),
    ]


def test_first_floor_amoeba_uses_roster_weight(monkeypatch):
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
    current = floor()
    assert stage6.spawn_monster(current, 0)
    assert current.monster_spawn_queue.count(("a", 1)) == 24
    assert current.monster_spawn_queue.count(("f", 1)) == 4


def test_spawn_does_not_place_monster_on_bridgehead(monkeypatch):
    current = floor()
    current.bridgehead = (10, 10)
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10), (11, 10)])
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    assert not current.entities


def test_spore_monsters_and_rare_erebus_spawn_weights(monkeypatch):
    totals = []
    m_weights = []
    for floor_index in range(4):
        current = floor()
        monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
        monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 10)])
        assert stage6.spawn_monster(current, floor_index)
        queue = current.monster_spawn_queue
        totals.append(len(queue))
        m_weights.append(queue.count(("m", 1)))
        assert queue.count(("E", 1)) == (0, 1, 1, 0)[floor_index]
        assert sum(char == "i" for char, _ in queue) == (0, 3, 5, 6)[floor_index]
        assert queue.count(("g", 2)) == (0, 0, 2, 6)[floor_index]
    assert totals == [59, 36, 50, 62]
    assert m_weights == [2, 1, 2, 2]


def test_second_floor_monster_draw_can_select_e_and_m(monkeypatch):
    floors = [floor() for _ in range(3)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    counts = Counter()
    pool = [(char, rank) for char, count, rank, spawn_weight in d.STAGE6_ROSTER[1]
            for _ in range(count * spawn_weight)]

    def sample(current, index, **kwargs):
        if index == 1:
            counts[stage6.rand.choice(pool)] += 1
        return False

    monkeypatch.setattr(stage6, "spawn_monster", sample)
    monkeypatch.setattr(stage6.rand, "_state", stage6.rand._state[:])
    monkeypatch.setattr(stage6.rand, "_index", stage6.rand._index)
    monkeypatch.setattr(stage6.rand, "seed", stage6.rand.seed)
    stage6.rand.set_seed(37318)
    for turn in range(d.STAGE6_SPAWN_INTERVAL - 1, d.STAGE6_SPAWN_INTERVAL * 20000,
                      d.STAGE6_SPAWN_INTERVAL):
        stage6.advance_spawns(floors, player, 0, turn)
    assert counts[("E", 1)] > 50
    assert counts[("m", 1)] > 50
    assert 0.6 < counts[("E", 1)] / counts[("m", 1)] < 1.6


def test_every_floor_spawned_every_thirty_six_turns(monkeypatch):
    floors = [floor() for _ in range(4)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    calls = []
    monkeypatch.setattr(stage6, "spawn_monster", lambda current, index, **kw: calls.append((index, kw)) or False)
    for turn in range(72):
        stage6.advance_spawns(floors, player, 1, turn)
        assert len(calls) == 4 * ((turn + 1) // 36)
    assert [index for index, _ in calls] == [0, 1, 2, 3, 0, 1, 2, 3]
    assert calls[1][1]["avoid"] == {(x, y) for x in range(2, 7) for y in range(2, 7)}
    assert calls[0][1]["avoid"] == set()


def test_spawn_avoids_player_square_only_on_active_floor(monkeypatch):
    floors = [floor(), floor()]
    player = d.Player(10, 10, 1, d.LP_INIT)
    points = [(8, 8), (12, 12), (13, 10)]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: points.copy())
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage6.rand, "choice", lambda pool: ("a", 1))
    spawned = stage6.advance_spawns(floors, player, 0, d.STAGE6_SPAWN_INTERVAL - 1)
    assert [(index, (entity.x, entity.y)) for index, entity in spawned] == [
        (0, (13, 10)), (1, (8, 8)),
    ]


def test_initial_monsters_avoid_player_square():
    for seed in range(5):
        stage6.rand.set_seed(seed)
        floors, player = stage6.build()
        for entity in floors[0].entities:
            if isinstance(entity, d.Monster) and not isinstance(entity, d.Collapse):
                assert abs(entity.x - player.x) > 2 or abs(entity.y - player.y) > 2


def test_neighbor_preference_has_fifty_percent_threshold(monkeypatch):
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(20, 10), (10, 9)])
    for roll in range(100):
        current = floor()
        current.entities = [monster(10, 10)]
        monkeypatch.setattr(stage6.rand, "randrange", lambda n: roll if n == 100 else 0)
        assert stage6.spawn_monster(current, 0, variant=("a", 1))
        assert (current.entities[-1].x, current.entities[-1].y) == ((10, 9) if roll < 50 else (20, 10))


def test_party_preference_falls_back_after_five_failures(monkeypatch):
    current = floor()
    current.entities = [monster(x, 10) for x in (10, 12, 14, 16, 18)]
    nearby = [(x, 9) for x in (10, 12, 14, 16, 18)]
    random_points = [(30 + x, 10) for x in range(5)]
    attempts = []
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: nearby + random_points)
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)

    def can_join(current, monster, point, **kwargs):
        attempts.append(point)
        return point == random_points[-1]

    monkeypatch.setattr(stage6, "_can_join_at", can_join)
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert attempts == nearby + random_points


def test_party_preference_without_neighbors_falls_back(monkeypatch):
    current = floor()
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(20, 10)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert (current.entities[-1].x, current.entities[-1].y) == (20, 10)


def test_generated_spawn_exclusions_only_include_start_room():
    floors, player = stage6.build()
    assert floors[0].monster_spawn_blocked_rooms == {stage6.tile_at((player.x, player.y))}
    assert not floors[1].monster_spawn_blocked_rooms
    assert not floors[-1].monster_spawn_blocked_rooms
    for index, current in enumerate(floors):
        for entity in current.entities:
            if isinstance(entity, d.Monster) and not isinstance(entity, d.Collapse):
                if index == len(floors) - 1 and entity.tribe.char in ("F", "V", "k"):
                    continue
                assert stage6.tile_at((entity.x, entity.y)) not in current.monster_spawn_blocked_rooms


def test_monster_can_spawn_in_boss_room_and_join_boss_party(monkeypatch):
    current = floor()
    boss = monster(10, 10, "F")
    vortex = monster(10, 11, "V")
    marksman = monster(10, 12, "k")
    current.entities = [boss, vortex, marksman]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 13)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 2, variant=("a", 1))
    assert len(stage56.monster_party(current, boss)) == 4
    assert stage6.tile_at((10, 13)) == stage6.tile_at((boss.x, boss.y))


def test_boss_party_still_obeys_limit_and_special_monster_rules(monkeypatch):
    current = floor()
    boss = monster(10, 3, "F")
    current.entities = [boss, monster(10, 4, "V"), monster(10, 5, "k")]
    current.entities.extend(monster(10, y) for y in range(6, 11))
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 11)])
    assert not stage6.spawn_monster(current, 2, variant=("a", 1))
    current.entities = current.entities[:3]
    monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [(10, 6)])
    assert not stage6.spawn_monster(current, 2, variant=("c", 1))


def test_initial_spawn_attempts_can_access_boss_room(monkeypatch):
    stage6.rand.set_seed(123)
    original = stage6.spawn_monster
    eligible = []

    def record(current, index, **kwargs):
        if index == d.STAGE6_FLOORS - 1:
            boss = next(e for e in current.entities
                        if isinstance(e, d.Monster) and e.tribe.char == "F")
            room = stage6.tile_at((boss.x, boss.y))
            eligible.append(any(stage6.tile_at(point) == room for point in stage6._open_points(current)))
        return original(current, index, **kwargs)

    monkeypatch.setattr(stage6, "spawn_monster", record)
    stage6.build()
    assert len(eligible) == 25
    assert eligible[0]


def test_stage_setup_attempts_random_spawns_per_floor(monkeypatch):
    original = stage6.spawn_monster
    draws = []
    def record(current, index, **kwargs):
        draws.append((index, kwargs.get("prefer_adjacent")))
        return original(current, index, **kwargs)
    monkeypatch.setattr(stage6, "spawn_monster", record)
    floors, _ = stage6.build()
    assert draws == [(index, index > 0) for index, count in enumerate((40, 35, 30, 25))
                     for _ in range(count)]
    assert all(not current.respawn_glows for current in floors)
