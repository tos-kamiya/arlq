from collections import Counter

from arlq import defs as d, game_engine, stage6
from arlq.stage_types import Floor


def test_solo_monster_does_not_move_as_turns_pass(monkeypatch):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    current = Floor(field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (2, 2), None)
    enemy = d.Monster(10, 10, d.CHAR_TO_MONSTER_TRIBE["a"])
    current.entities.append(enemy)
    player = d.Player(4, 4, 1, 100)
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_: [])
    for turn in range(20):
        game_engine._process_multi_floor_turn((0, 0), [current], player, [0], [(4, 4)], Counter(), turn, stage_num=6)
    assert (enemy.x, enemy.y) == (10, 10)
