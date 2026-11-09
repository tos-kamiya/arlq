import pytest

from arlq import defs as d, stage6
from arlq.utils import rand


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
    assert all(
        not isinstance(entity, d.Monster) or entity.tribe.item != d.ITEM_SWORD_CURSED
        for floor in floors for entity in floor.entities
    )
    boss = next(e for e in floors[-1].entities
                if isinstance(e, d.Monster) and e.tribe.char == "F")
    from arlq.stage56 import monster_party
    party = monster_party(floors[-1], boss)
    assert {e.tribe.char for e in party} == {"F", "V", "k"}
    assert boss.empowered == 2
    assert sum(d.monster_level(e) for e in party) == 300
    mimic = next(e for e in floors[-1].entities
                 if isinstance(e, d.Monster) and e.tribe.char == "M")
    assert (mimic.mimic_boss_char, mimic.mimic_boss_empowered) == ("F", 2)
    assert all(not isinstance(e, d.PartyMember)
               for floor in floors[2:] for e in floor.entities)


def test_member_rewards_and_knight():
    player = d.Player(1, 1, 1, d.LP_INIT)
    player.members = [
        d.PartyMember(1, 1, d.MEMBER_KNIGHT),
        d.PartyMember(1, 1, d.MEMBER_HEALER),
    ]
    assert d.current_player_attack(player) == 41


def test_tavern_neighborhood_is_initially_mapped():
    from arlq.arlq import iterate_ellipse_points

    floors, _ = stage6.build()
    horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
    vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
    radius = round(vortex_radius * d.STAGE6_TAVERN_KNOWN_VORTEX_RATIO)
    assert radius == 4
    assert round(radius * d.FOV_WIDTH_EXPANSION_RATIO) == 6
    floor = floors[0]
    expected = set(iterate_ellipse_points(
        *floor.tavern, radius, d.FOV_WIDTH_EXPANSION_RATIO
    ))
    actual = {(x, y) for y, row in enumerate(floor.seen)
              for x, seen in enumerate(row) if seen}
    assert actual == expected
    assert all(floor.tavern is None and not any(map(any, floor.seen))
               for floor in floors[1:])
