from collections import Counter

from arlq import defs as d, game_engine, stage6, stage56
from arlq.stage_types import Floor
from arlq.trace import TraceRecorder


def floor():
    field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    return Floor(field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (2, 2), None)


def monster(x, y, char="a", rank=1):
    return d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[char], rank)


def test_only_eighth_turn_moves_solo_monster(monkeypatch):
    current, player = floor(), d.Player(1, 1, 1, 100)
    current.field[5][5] = current.field[5][6] = d.CHAR_FLOOR
    enemy = monster(5, 5)
    current.entities.append(enemy)
    monkeypatch.setattr(stage6.rand, "choice", lambda options: options[0])
    assert stage6.advance_monster_movement([current], player, 0, 6) is None
    assert (enemy.x, enemy.y) == (5, 5)
    assert stage6.advance_monster_movement([current], player, 0, 7) == (0, enemy, (5, 5))
    assert (enemy.x, enemy.y) == (6, 5)


def test_selected_party_member_does_not_move_or_select_another(monkeypatch):
    current, player = floor(), d.Player(1, 1, 1, 100)
    current.entities = [monster(5, 5), monster(5, 6), monster(10, 10)]
    current.field[5][6] = current.field[10][11] = d.CHAR_FLOOR
    monkeypatch.setattr(stage6.rand, "choice", lambda options: options[0])
    assert stage6.advance_monster_movement([current], player, 0, 7) is None
    assert [(m.x, m.y) for m in current.entities] == [(5, 5), (5, 6), (10, 10)]


def test_movement_avoids_player_and_occupied_cells(monkeypatch):
    current, player = floor(), d.Player(6, 5, 1, 100)
    current.entities = [monster(5, 5), d.Fairy(5, 4, d.CHAR_TO_TRIBE["n"])]
    current.field[4][5] = current.field[5][6] = d.CHAR_FLOOR
    monkeypatch.setattr(stage6.rand, "choice", lambda options: options[0])
    assert stage6.advance_monster_movement([current], player, 0, 7) is None


def test_barrier_moves_with_monster_and_glow(monkeypatch):
    current, player = floor(), d.Player(1, 1, 1, 100)
    for y in range(3, 8):
        for x in range(3, 9):
            current.field[y][x] = d.CHAR_FLOOR
    enemy = monster(5, 5, "f", 2)
    current.entities = [enemy]
    stage56.initialize_monster_barriers(current)
    current.respawn_glows[(5, 5)] = 2
    monkeypatch.setattr(stage6.rand, "choice", lambda options: options[0])
    assert stage6.advance_monster_movement([current], player, 0, 7)
    assert (enemy.x, enemy.y) == (5, 4)
    assert current.respawn_glows == {(5, 4): 2}
    assert current.field[6][5] == d.CHAR_FLOOR
    assert current.field[3][5] == d.CHAR_BARRIER
    assert current.field[4][5] == d.CHAR_FLOOR


def test_move_is_recorded_for_overshoot_rewind(monkeypatch):
    current, player = floor(), d.Player(4, 4, 1, 100)
    current.field[4][4] = current.field[4][5] = d.CHAR_FLOOR
    enemy = monster(10, 10)
    monkeypatch.setattr(stage6, "advance_monster_movement", lambda *_: (0, enemy, (10, 9)))
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: None)
    trace = TraceRecorder(params={})
    trace.begin_turn("R")
    game_engine._step((1, 0), [current], player, [0], [(4, 4)], Counter(), 9,
                      stage_num=6, trace=trace)
    trace.commit_turn()
    assert trace.turns[0]["world"] == [{
        "type": "monster_move", "id": "a", "from": [10, 9], "at": [10, 10], "floor": 0,
    }]
