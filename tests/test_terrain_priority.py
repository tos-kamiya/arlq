from collections import Counter

from arlq import defs as d, game_engine, stage56
from arlq.arlq import spread_caltrops
from arlq.stage_types import Floor


def floor():
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    return Floor(field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (2, 2), None)


def defeat(current, char):
    player = d.Player(10, 10, 100, d.LP_INIT)
    monster = d.Monster(10, 10, d.CHAR_TO_MONSTER_TRIBE[char])
    game_engine._defeat_monster(monster, current, player, [0], [(10, 10)], Counter(),
                                floors=[current], stage_num=6)


def test_caltrops_replace_barriers_and_walls_but_not_golem_rubble():
    current = floor()
    current.field[10][8] = d.CHAR_BARRIER
    current.field[10][12] = d.CHAR_WALL
    current.field[8][10] = d.CHAR_GOLEM_WALL
    current.persistent_barriers.add((8, 10))
    defeat(current, "X")
    assert current.field[10][8] == current.field[10][12] == d.CHAR_CALTROP
    assert current.field[8][10] == d.CHAR_GOLEM_WALL
    assert (8, 10) not in current.persistent_barriers


def test_golem_rubble_replaces_caltrops_barriers_and_walls():
    current = floor()
    current.field[9][9] = d.CHAR_CALTROP
    current.field[9][11] = d.CHAR_BARRIER
    current.field[11][9] = d.CHAR_WALL
    current.persistent_barriers.add((11, 9))
    defeat(current, "g")
    assert all(current.field[y][x] == d.CHAR_GOLEM_WALL
               for x, y in ((9, 9), (11, 9), (9, 11)))
    assert (11, 9) not in current.persistent_barriers


def test_barriers_cannot_replace_walls_caltrops_or_rubble():
    current = floor()
    cobra = d.Monster(10, 10, d.CHAR_TO_MONSTER_TRIBE["f"], empowered=2)
    current.entities.append(cobra)
    positions = ((10, 9), (11, 10), (10, 11), (9, 10))
    for (x, y), cell in zip(positions, (d.CHAR_WALL, d.CHAR_CALTROP,
                                        d.CHAR_GOLEM_WALL, d.CHAR_FLOOR)):
        current.field[y][x] = cell
    stage56.place_monster_barriers(current, cobra)
    assert [current.field[y][x] for x, y in positions] == [
        d.CHAR_WALL, d.CHAR_CALTROP, d.CHAR_GOLEM_WALL, d.CHAR_BARRIER,
    ]


def test_secret_passages_and_pit_landings_survive_scatter():
    for char in ("X", "g"):
        current = floor()
        current.field[9][9] = d.CHAR_HIDDEN_D_GATE
        current.field[9][11] = d.CHAR_D_GATE
        current.field[11][9] = d.CHAR_SCHOLAR_STAIRS_UP
        current.collapse_landings.add((11, 11))
        current.d_gates[(12, 10)] = "."
        current.scholar_up_stairs.append((8, 10))
        defeat(current, char)
        assert current.field[9][9] == d.CHAR_HIDDEN_D_GATE
        assert current.field[9][11] == d.CHAR_D_GATE
        assert current.field[11][9] == d.CHAR_SCHOLAR_STAIRS_UP
        assert current.field[11][11] == d.CHAR_FLOOR
        assert current.field[10][12] == d.CHAR_FLOOR
        assert current.field[10][8] == d.CHAR_FLOOR


def test_legacy_caltrop_spread_replaces_barriers():
    current = floor()
    current.field[10][12] = d.CHAR_BARRIER
    spread_caltrops(current.field, (10, 10), [])
    assert current.field[10][12] == d.CHAR_CALTROP


def test_barriers_preserve_hidden_passage_and_pit_landing():
    current = floor()
    cobra = d.Monster(10, 10, d.CHAR_TO_MONSTER_TRIBE["f"], empowered=2)
    current.entities.append(cobra)
    current.collapse_landings.add((10, 9))
    current.d_gates[(11, 10)] = "."
    current.scholar_up_stairs.append((10, 11))
    stage56.place_monster_barriers(current, cobra)
    assert all(current.field[y][x] == d.CHAR_FLOOR
               for x, y in ((10, 9), (11, 10), (10, 11)))
    assert current.field[10][9] == d.CHAR_BARRIER
