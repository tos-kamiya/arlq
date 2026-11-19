from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq import stage6
from arlq.arlq import GameConfig
from arlq.utils import rand


@pytest.mark.parametrize("seed", range(20))
def test_boss_party_has_room_to_grow_to_eight(monkeypatch, seed):
    from arlq import stage56

    rand.set_seed(seed)
    original = stage6._place_initial_boss_party
    reserved = []

    def place_boss(current):
        party, line = original(current)
        reserved.append(line)
        return party, line

    monkeypatch.setattr(stage6, "_place_initial_boss_party", place_boss)
    floors, _ = stage6.build()
    current = floors[-1]
    boss = next(entity for entity in current.entities
                if isinstance(entity, d.Monster) and entity.tribe.char == "F")
    line = reserved[-1]
    assert len(line) == d.STAGE6_MONSTER_PARTY_LIMIT
    assert len({x for x, _ in line}) == 1
    assert max(y for _, y in line) - min(y for _, y in line) == len(line) - 1
    while len(stage56.monster_party(current, boss)) < len(line):
        party = stage56.monster_party(current, boss)
        occupied = {(entity.x, entity.y) for entity in party}
        candidates = [point for point in line - occupied
                      if (point[0], point[1] - 1) in occupied
                      or (point[0], point[1] + 1) in occupied]
        monster = d.Monster(0, 0, d.CHAR_TO_MONSTER_TRIBE["a"])
        point = next(point for point in candidates
                     if current.field[point[1]][point[0]] in (d.CHAR_FLOOR, d.CHAR_BARRIER)
                     and stage6._can_join_at(current, monster, point))
        monkeypatch.setattr(stage56, "_open_points", lambda *_, **__: [point])
        assert stage6.spawn_monster(current, 2, variant=("a", 1), prefer_adjacent=False)
    assert len(stage56.monster_party(current, boss)) == 8


@pytest.mark.parametrize("config, expected_h, expected_v", [
    (GameConfig(), 3, 4),
    (GameConfig(corridor_h_width=1, corridor_v_width=2), 2, 3),
])
def test_stage6_opens_wider_corridors_and_adds_hidden_gates(
    monkeypatch, config, expected_h, expected_v
):
    original = stage6.generate_floor_field
    observed = []

    def generate(*args, **kwargs):
        result = original(*args, **kwargs)
        field = result[0]
        horizontal, vertical = set(), set()
        for ty in range(d.TILE_NUM_Y):
            for tx in range(1, d.TILE_NUM_X):
                x = d.FIELD_X_MARGIN + tx * (d.TILE_WIDTH + 1)
                cells = [field[y][x] for y in range(ty * (d.TILE_HEIGHT + 1) + 1,
                                                     (ty + 1) * (d.TILE_HEIGHT + 1))]
                count = cells.count(d.CHAR_FLOOR)
                if count:
                    horizontal.add(count)
        for ty in range(1, d.TILE_NUM_Y):
            y = ty * (d.TILE_HEIGHT + 1)
            for tx in range(d.TILE_NUM_X):
                left = d.FIELD_X_MARGIN + tx * (d.TILE_WIDTH + 1) + 1
                cells = field[y][left:left + d.TILE_WIDTH]
                count = cells.count(d.CHAR_FLOOR)
                if count:
                    vertical.add(count)
        observed.append((horizontal, vertical))
        return result

    monkeypatch.setattr(stage6, "generate_floor_field", generate)
    floors, _ = stage6.build(config)
    assert len(observed) == d.STAGE6_FLOORS
    assert all(horizontal == {expected_h} and vertical == {expected_v}
               for horizontal, vertical in observed)
    for current in floors[:-1]:
        assert sum(row.count(d.CHAR_HIDDEN_D_GATE) for row in current.field) in (1, 2)


@pytest.mark.parametrize("available", [False, True])
def test_second_detached_gate_requires_an_open_neighbor(available):
    field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    room = (1, 1)
    wall_x = d.FIELD_X_MARGIN + 2 * (d.TILE_WIDTH + 1)
    y = d.TILE_HEIGHT + 2
    field[y][wall_x - 1] = d.CHAR_FLOOR
    if available:
        field[y][wall_x + 1] = d.CHAR_FLOOR
    current = SimpleNamespace(field=field, room_components=({(0, 1), (2, 1)}, {room}))
    stage6._add_second_detached_gate(current, ((0, 1), room))
    assert field[y][wall_x] == (d.CHAR_HIDDEN_D_GATE if available else d.CHAR_WALL)


@pytest.mark.parametrize("seed", [0, 123, 789])
def test_three_floor_dungeon(seed):
    rand.set_seed(seed)
    floors, player = stage6.build()
    assert len(floors) == 3
    assert player.level == 1
    for floor in floors:
        monsters = [e for e in floor.entities if isinstance(e, d.Monster)
                    and e.active and not isinstance(e, d.Collapse)]
        assert len(monsters) >= d.STAGE6_INITIAL_MONSTERS // 2
        if floor.room_components and len(floor.room_components) == 2:
            detached = next(component for component in floor.room_components if len(component) == 1)
            isolated = [e for e in monsters if stage6.tile_at((e.x, e.y)) in detached]
            assert len(isolated) >= 2
    assert all(any(isinstance(e, d.Monster) and e.tribe.char == "c"
                   for e in floor.entities) for floor in floors)
    boss = next(e for e in floors[-1].entities
                if isinstance(e, d.Monster) and e.tribe.char == "F")
    from arlq.stage56 import monster_party
    party = monster_party(floors[-1], boss)
    assert {"F", "V"} <= {e.tribe.char for e in party}
    assert len(party) >= 3
    assert any((e.tribe.char, e.empowered) in d.STAGE6_BOSS_PARTY_ADDITIONS for e in party)
    assert len(party) <= d.STAGE6_MONSTER_PARTY_LIMIT
    assert boss.empowered == 2
    assert sum(d.monster_level(e) for e in party) >= 225
    mimic = next(e for e in floors[-1].entities
                 if isinstance(e, d.Monster) and e.tribe.char == "M")
    assert (mimic.mimic_boss_char, mimic.mimic_boss_empowered) == (d.CHAR_DUNGEON_CORE, None)
    core = next(e for e in floors[-1].entities
                if isinstance(e, d.Monster) and e.tribe.char == d.CHAR_DUNGEON_CORE)
    assert not core.active
    assert 0 < core.x < d.FIELD_WIDTH - 1
    assert core.boss_id == 2
    assert all(tribe.char != d.CHAR_DUNGEON_CORE for tribe in d.MEMBER_STAGE_ROSTER_TRIBES)
    assert all(not isinstance(e, d.PartyMember)
               for floor in floors[2:] for e in floor.entities)


def test_member_rewards_and_knight():
    player = d.Player(1, 1, 1, d.LP_INIT)
    player.members = [
        d.PartyMember(1, 1, d.MEMBER_KNIGHT),
        d.PartyMember(1, 1, d.MEMBER_HEALER),
    ]
    assert d.current_player_attack(player) == 41


def test_bridgehead_neighborhood_is_initially_mapped():
    from arlq.arlq import iterate_ellipse_points

    floors, _ = stage6.build()
    horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
    vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
    radius = round(vortex_radius * d.STAGE6_BRIDGEHEAD_KNOWN_VORTEX_RATIO)
    assert radius == 4
    assert round(radius * d.FOV_WIDTH_EXPANSION_RATIO) == 6
    floor = floors[0]
    expected = set(iterate_ellipse_points(
        *floor.bridgehead, radius, d.FOV_WIDTH_EXPANSION_RATIO
    ))
    actual = {(x, y) for y, row in enumerate(floor.seen)
              for x, seen in enumerate(row) if seen}
    assert actual == expected
    assert all(floor.bridgehead is None and not any(map(any, floor.seen))
               for floor in floors[1:])
