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


def test_all_floors_draw_with_active_floor_preferred(monkeypatch):
    floors = [floor() for _ in range(4)]
    player = d.Player(4, 4, 1, d.LP_INIT)
    chances, spawned = [], []
    monkeypatch.setattr(stage6.rand, "randrange", lambda n: chances.append(n) or 0)
    monkeypatch.setattr(stage6, "spawn_monster", lambda current, index, **kw: spawned.append((index, kw)))
    stage6.advance_spawns(floors, player, 2)
    assert chances == [d.STAGE6_OTHER_SPAWN_CHANCE] * 2 + [d.STAGE6_ACTIVE_SPAWN_CHANCE, d.STAGE6_OTHER_SPAWN_CHANCE]
    assert [index for index, _ in spawned] == [0, 1, 2, 3]
    assert spawned[2][1]["avoid"] == {(4, 4)}


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
    stage6.advance_spawns([current], player, 0)
    assert current.respawn_glows == {(10, 10): d.RESPAWN_GLOW_TURNS}
    assert game_engine.respawn_glow_cells(current) == {(10, 10)}
    current.entities.clear()
    assert game_engine.respawn_glow_cells(current) == set()


def test_failed_timed_spawn_does_not_glow(monkeypatch):
    current = floor()
    player = d.Player(4, 4, 1, d.LP_INIT)
    monkeypatch.setattr(stage6, "_open_points", lambda _: [])
    monkeypatch.setattr(stage6.rand, "randrange", lambda _: 0)
    stage6.advance_spawns([current], player, 0)
    assert current.respawn_glows == {}
