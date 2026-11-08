import pytest

from arlq import defs as d, stage6
from arlq.utils import rand


@pytest.mark.parametrize("seed", [0, 123, 789])
def test_four_floor_dungeon(seed):
    rand.set_seed(seed)
    floors, player = stage6.build()
    assert len(floors) == 4
    assert player.level == 1
    for floor in floors:
        assert sum(isinstance(e, d.Monster) and e.tribe.char == "f"
                   and e.empowered == 1 for e in floor.entities) <= 1
        swords = [e for e in floor.entities
                  if isinstance(e, d.Monster) and e.tribe.char == "c"]
        assert len(swords) == 1
        assert swords[0].empowered == 1
    assert any(isinstance(e, d.Monster) and e.tribe.char == "b"
               and e.empowered == 3 for e in floors[2].entities)
    assert any(isinstance(e, d.Monster) and e.tribe.char == "B"
               and e.empowered == 3 for e in floors[3].entities)
    assert all(
        not isinstance(entity, d.Monster) or entity.tribe.item != d.ITEM_SWORD_CURSED
        for floor in floors for entity in floor.entities
    )
    boss = next(e for e in floors[-1].entities
                if isinstance(e, d.Monster) and e.tribe.char == "W")
    from arlq.stage56 import monster_party
    assert sum(d.monster_level(e) for e in monster_party(floors[-1], boss)) == 230
    assert all(not isinstance(e, d.PartyMember)
               for floor in floors[2:] for e in floor.entities)


def test_member_rewards_and_knight():
    player = d.Player(1, 1, 1, d.LP_INIT)
    player.members = [
        d.PartyMember(1, 1, d.MEMBER_KNIGHT),
        d.PartyMember(1, 1, d.MEMBER_HEALER),
    ]
    assert d.experience_share_count(player) == 1
    assert d.current_player_attack(player) == 41


def test_tavern_neighborhood_is_initially_mapped():
    from arlq.arlq import iterate_ellipse_points

    floors, _ = stage6.build()
    horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
    vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
    radius = round(vortex_radius * d.STAGE6_TAVERN_KNOWN_VORTEX_RATIO)
    assert radius == 4
    assert round(radius * d.FOV_WIDTH_EXPANSION_RATIO) == 6
    for floor in floors[:2]:
        expected = set(iterate_ellipse_points(
            *floor.tavern, radius, d.FOV_WIDTH_EXPANSION_RATIO
        ))
        actual = {(x, y) for y, row in enumerate(floor.seen)
                  for x, seen in enumerate(row) if seen}
        assert actual == expected
    assert all(not any(map(any, floor.seen)) for floor in floors[2:])


def test_second_floor_tavern_does_not_reveal_entry_stairs():
    from arlq import game_engine
    from arlq.utils import rand

    for seed in range(20):
        rand.set_seed(seed)
        floors, player = stage6.build()
        upper, lower = floors[:2]
        ux, uy = upper.down
        lx, ly = lower.up
        assert not lower.seen[ly][lx]
        game_engine.observe_world(floors, player, 0, d.TORCH_RADIUS)
        assert not upper.seen[uy][ux]
