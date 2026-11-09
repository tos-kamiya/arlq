from collections import Counter

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
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 9)])
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert len(stage56.monster_party(current, current.entities[-1])) == 8
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))


def test_spawn_checks_both_sides_and_special_monsters(monkeypatch):
    current = floor()
    current.entities = [monster(10, y) for y in (2, 3, 4, 5, 7, 8, 9, 10)]
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 6)])
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    current.entities = [monster(10, 5, "c")]
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    current.entities = [monster(10, 5)]
    assert not stage6.spawn_monster(current, 0, variant=("c", 1))


def test_spawn_tries_at_most_five_distinct_positions(monkeypatch):
    current = floor()
    current.entities = [monster(10, y, "c") for y in range(2, 12, 2)]
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, y) for y in (3, 5, 7, 9, 11, 15)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    assert len(current.entities) == 5


def test_wyrm_spawn_ranks_by_floor():
    assert [(count, rank) for char, count, rank in d.STAGE6_ROSTER[0] if char == "w"] == []
    assert [(count, rank) for char, count, rank in d.STAGE6_ROSTER[1] if char == "w"] == [(1, 1)]
    assert [(count, rank) for char, count, rank in d.STAGE6_ROSTER[2] if char == "w"] == [(1, 1), (2, 2)]


def test_spawn_attempts_once_every_ten_turns_on_one_chosen_floor(monkeypatch):
    floors = [floor() for _ in range(3)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    spawned = []
    choices = iter([2, 1])
    monkeypatch.setattr(stage6.rand, "randrange", lambda n: next(choices))
    monkeypatch.setattr(stage6, "spawn_monster", lambda current, index, **kw: spawned.append((index, kw)))
    for turn in range(20):
        stage6.advance_spawns(floors, player, 2, turn)
        assert len(spawned) == (turn + 1) // 10
    assert [index for index, _ in spawned] == [2, 1]
    assert spawned[0][1]["avoid"] == {(4, 4)}
    assert spawned[1][1]["avoid"] == set()


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
    game_engine._vortex_rearrange(current, player, 0, (10, 8), bounded_relocation=True)
    assert enemy in current.entities
    assert (enemy.x, enemy.y) == (10, 8)


def test_spawn_can_prefer_vertical_neighbor(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10)]
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage6.rand, "choice", lambda values: values[0])
    assert stage6.spawn_monster(current, 0, variant=("a", 1))
    assert (current.entities[-1].x, current.entities[-1].y) == (10, 9)


def test_special_spawn_does_not_prefer_neighbors(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10)]
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("c", 1))
    assert (current.entities[-1].x, current.entities[-1].y) == (20, 10)


def test_timed_spawn_glows_but_initial_spawn_does_not(monkeypatch):
    current = floor()
    player = d.Player(4, 4, 1, d.LP_INIT)
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
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
    monkeypatch.setattr(stage6, "_open_points", lambda _: [])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    stage6.advance_spawns([current], player, 0, d.STAGE6_SPAWN_INTERVAL - 1)
    assert current.respawn_glows == {}


def test_initial_spawn_does_not_prefer_neighbors(monkeypatch):
    current = floor()
    current.entities = [monster(10, 10)]
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("a", 1), prefer_adjacent=False)
    assert (current.entities[-1].x, current.entities[-1].y) == (20, 10)


def test_spawn_prefers_neighbor_for_four_of_ten_draws(monkeypatch):
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(20, 10), (10, 9)])
    monkeypatch.setattr(stage6.rand, "choice", lambda values: values[0])
    for roll in range(10):
        current = floor()
        current.entities = [monster(10, 10)]
        monkeypatch.setattr(stage6.rand, "randrange", lambda n: roll if n == 10 else 0)
        assert stage6.spawn_monster(current, 0, variant=("a", 1))
        expected = (10, 9) if roll < 4 else (20, 10)
        assert (current.entities[-1].x, current.entities[-1].y) == expected


def test_spawn_excludes_blocked_sections(monkeypatch):
    current = floor()
    current.monster_spawn_blocked_rooms = {stage6.tile_at((10, 10))}
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10), (40, 10)])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    assert stage6.spawn_monster(current, 0, variant=("a", 1), prefer_adjacent=False)
    assert (current.entities[-1].x, current.entities[-1].y) == (40, 10)


def test_generated_spawn_exclusions_and_initial_exceptions():
    floors, _ = stage6.build()
    for current in floors:
        rooms = set().union(*current.room_components)
        assert len(current.monster_spawn_blocked_rooms) == (len(rooms) * 30 + 50) // 100
        assert current.monster_spawn_blocked_rooms <= rooms
        detached = set().union(*(component for component in current.room_components
                                 if len(component) == 1))
        for entity in current.entities:
            if not isinstance(entity, d.Monster) or not entity.active:
                continue
            if isinstance(entity, d.Collapse) or entity.tribe.char in ("F", "V", "k"):
                continue
            room = stage6.tile_at((entity.x, entity.y))
            assert room in detached or room not in current.monster_spawn_blocked_rooms


def test_rare_amoeba_spawn_weight_is_half_of_roster_weight(monkeypatch):
    current = floor()
    captured = []

    def choose(pool):
        captured.extend(pool)
        return pool[0]

    monkeypatch.setattr(stage6.rand, "choice", choose)
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
    assert stage6.spawn_monster(current, 2)
    for char, count, rank in d.STAGE6_ROSTER[2]:
        assert captured.count((char, rank)) == count * (1 if (char, rank) in d.STAGE6_REDUCED_SPAWN_VARIANTS else 2)


def test_bison_variants_have_halved_weights(monkeypatch):
    for floor_index, rank in ((0, 1), (1, 2), (2, 3)):
        current = floor()
        captured = []
        monkeypatch.setattr(stage6.rand, "choice", lambda pool: captured.extend(pool) or pool[0])
        monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
        monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
        assert stage6.spawn_monster(current, floor_index)
        weight = next(count for char, count, r in d.STAGE6_ROSTER[floor_index]
                      if char == "b" and r == rank)
        assert captured.count(("b", rank)) == weight


def test_golem_weight_is_halved_only_on_second_floor(monkeypatch):
    for floor_index in range(3):
        current = floor()
        captured = []
        monkeypatch.setattr(stage6.rand, "choice", lambda pool: captured.extend(pool) or pool[0])
        monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
        monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
        assert stage6.spawn_monster(current, floor_index)
        weight = next(count for char, count, rank in d.STAGE6_ROSTER[floor_index]
                      if char == "g" and rank == 1)
        assert captured.count(("g", 1)) == weight * (1 if floor_index == 1 else 2)


def test_first_floor_doubles_cobra_weight_using_amoeba_weight():
    roster = d.STAGE6_ROSTER[0]
    assert next(count for char, count, rank in roster if (char, rank) == ("f", 1)) == 2
    assert next(count for char, count, rank in roster if (char, rank) == ("a", 1)) == 12


def test_section_spawn_rates_accept_and_reject_at_threshold(monkeypatch):
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
    for rate, roll, expected in ((40, 39, True), (40, 40, False),
                                 (60, 59, True), (60, 60, False)):
        current = floor()
        current.monster_spawn_room_rates = {stage6.tile_at((10, 10)): rate}
        monkeypatch.setattr(stage6.rand, "randrange", lambda n: roll if n == 100 else 0)
        assert stage6.spawn_monster(current, 0, variant=("a", 1)) is expected


def test_generated_section_rates_partition_available_rooms():
    floors, _ = stage6.build()
    for current in floors:
        rooms = set().union(*current.room_components)
        rates = current.monster_spawn_room_rates
        assert set(rates) | current.monster_spawn_blocked_rooms == rooms
        assert not set(rates) & current.monster_spawn_blocked_rooms
        assert set(rates.values()) == {40, 60}
        assert abs(list(rates.values()).count(40) - list(rates.values()).count(60)) <= 1


def test_tavern_restores_only_on_entry_and_preserves_higher_lp():
    first, second = floor(), floor()
    first.tavern = (10, 10)
    player = d.Player(10, 10, 1, 25)
    stage6.recover_at_tavern([first, second], player, 0, 0, (9, 10))
    assert player.lp == 50
    player.lp = 90
    stage6.recover_at_tavern([first, second], player, 0, 0, (9, 10))
    assert player.lp == 90
    player.lp = 20
    stage6.recover_at_tavern([first, second], player, 0, 0, (11, 10))
    assert player.lp == 20
    stage6.recover_at_tavern([first, second], player, 1, 1, (9, 10))
    assert player.lp == 20
    stage6.recover_at_tavern([first, second], player, 0, 1, (10, 10))
    assert player.lp == 50


def test_tavern_healing_persists_after_leaving_in_game_loop(monkeypatch):
    from types import SimpleNamespace

    current = floor()
    current.tavern = (10, 10)
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
    assert frames == [(9, 25), (10, 50), (9, 49)]
    assert not trace.turns[0].get("world")
    assert len(trace.turns) == 3


def test_tavern_entry_clears_overshoot_history_without_healing(monkeypatch):
    from types import SimpleNamespace
    from arlq.trace import TraceRecorder

    current = floor()
    current.tavern = (10, 10)
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
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: (0, spawned))
    trace = TraceRecorder(params={})
    trace.begin_turn("R")
    game_engine._step((1, 0), [current], player, [0], [(4, 4)], Counter(), 9,
                      stage_num=6, trace=trace)
    trace.commit_turn()
    assert trace.turns[0]["world"] == [{
        "type": "spawn", "kind": "monster", "id": "a", "at": [10, 10], "floor": 0,
    }]


def test_stage_setup_performs_fifty_regular_spawn_draws(monkeypatch):
    original = stage6.advance_spawns
    draws = []

    def record(floors, player, floor_index, turn):
        draws.append((floor_index, turn))
        return original(floors, player, floor_index, turn)

    monkeypatch.setattr(stage6, "advance_spawns", record)
    floors, _ = stage6.build()
    assert draws == [(0, (i + 1) * d.STAGE6_SPAWN_INTERVAL - 1)
                     for i in range(d.STAGE6_INITIAL_SPAWN_DRAWS)]
    assert all(not current.respawn_glows for current in floors)


def test_first_floor_amoeba_uses_roster_weight(monkeypatch):
    pools = []
    monkeypatch.setattr(stage6.rand, "choice", lambda pool: pools.append(pool[:]) or pool[0])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
    assert stage6.spawn_monster(floor(), 0)
    assert pools[0].count(("a", 1)) == 24
    assert pools[0].count(("f", 1)) == 4


def test_spawn_floor_weights_current_floor_twice(monkeypatch):
    floors = [floor() for _ in range(3)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    selected = []
    monkeypatch.setattr(stage6, "spawn_monster", lambda current, index, **kw: selected.append(index))
    for active in range(3):
        selected.clear()
        for draw in range(4):
            monkeypatch.setattr(stage6.rand, "randrange", lambda n: draw)
            stage6.advance_spawns(floors, player, active, d.STAGE6_SPAWN_INTERVAL - 1)
        assert selected.count(active) == 2
        assert all(selected.count(i) == (2 if i == active else 1) for i in range(3))


def test_spawn_does_not_place_monster_on_tavern(monkeypatch):
    current = floor()
    current.tavern = (10, 10)
    monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10), (11, 10)])
    assert not stage6.spawn_monster(current, 0, variant=("a", 1))
    assert not current.entities


def test_spore_monsters_and_rare_erebus_spawn_weights(monkeypatch):
    totals = []
    m_weights = []
    for floor_index in range(3):
        current = floor()
        pools = []
        monkeypatch.setattr(stage6.rand, "choice", lambda pool: pools.append(pool[:]) or pool[0])
        monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
        monkeypatch.setattr(stage6, "_open_points", lambda _: [(10, 10)])
        assert stage6.spawn_monster(current, floor_index)
        totals.append(len(pools[0]))
        m_weights.append(pools[0].count(("m", 1)))
        assert pools[0].count(("E", 1)) == (1 if floor_index == 1 else 0)
    assert totals == [59, 38, 60]
    assert m_weights == [2, 1, 2]


def test_second_floor_monster_draw_can_select_e_and_m(monkeypatch):
    floors = [floor() for _ in range(3)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    counts = Counter()
    reduced = set(d.STAGE6_REDUCED_SPAWN_VARIANTS) | set(d.STAGE6_FLOOR2_REDUCED_SPAWN_VARIANTS)
    pool = [(char, rank) for char, weight, rank in d.STAGE6_ROSTER[1]
            for _ in range(weight * (1 if (char, rank) in reduced else 2))]

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
