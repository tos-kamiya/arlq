from collections import Counter

import pytest

from arlq import defs as d, game_engine, stage6
from arlq.game_engine import Floor


def make_floor(entities):
    return Floor(
        field=[[" "] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        entities=entities,
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1), down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2), island=None,
    )


@pytest.mark.parametrize("position, damage", [
    ((5, 4), 4), ((5, 6), 4), ((4, 5), 4), ((6, 5), 4),
    ((4, 4), 0), ((5, 3), 0), ((5, 5), 0),
])
def test_ivy_attack_range(position, damage):
    ivy = d.Monster(5, 5, d.CHAR_TO_MONSTER_TRIBE["i"])
    player = d.Player(*position, 1, 100)
    game_engine._ivy_attack(make_floor([ivy]), player)
    assert player.lp == 100 - damage


def test_ivy_attacks_stack_and_ignore_inactive_monsters():
    entities = [d.Monster(x, 5, d.CHAR_TO_MONSTER_TRIBE["i"]) for x in (4, 6)]
    inactive = d.Monster(5, 4, d.CHAR_TO_MONSTER_TRIBE["i"])
    inactive.active = False
    player = d.Player(5, 5, 1, 100)
    game_engine._ivy_attack(make_floor(entities + [inactive]), player)
    assert player.lp == 92
    assert "i" in player.known_monsters


@pytest.mark.parametrize("stage_num", range(1, 7))
def test_ivy_attacks_every_turn_even_without_movement(monkeypatch, stage_num):
    ivy = d.Monster(5, 5, d.CHAR_TO_MONSTER_TRIBE["i"])
    player = d.Player(5, 4, 1, 100)
    current = make_floor([ivy])
    monkeypatch.setattr(stage6, "advance_spawns", lambda *args: None)
    reasons = set()
    for turn in (1, 2):
        game_engine._step((0, 0), [current], player, [0], [(5, 4)], Counter(),
                          turn, stage_num=stage_num, repeat_stop_reasons=reasons)
    assert player.lp == 92
    assert "ivy_hit" in reasons


def test_ivy_roster_on_deeper_floors():
    assert all(char != "i" for char, *_ in d.STAGE6_ROSTER[0])
    assert all(any(char == "i" and rank == 1 for char, _, rank, _ in roster)
               for roster in d.STAGE6_ROSTER[1:])
    assert d.CHAR_TO_MONSTER_TRIBE["i"].level == 50
