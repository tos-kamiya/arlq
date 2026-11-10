from collections import Counter

from arlq import defs as d
from arlq import display, game_engine, stage5, stage6, stage_world
from arlq.arlq import (
    GameConfig,
    activate_dungeon_core_for_defeat,
    activate_mimic_for_defeat,
    unlock_treasure_for_defeat,
)
from arlq.stage_types import Floor


def floor(entities):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    return Floor(field, entities, [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (2, 2), None)


def test_boss_id_links_exact_individual_and_cross_floor_targets():
    tribe = d.CHAR_TO_MONSTER_TRIBE["F"]
    boss = d.Monster(5, 5, tribe, empowered=2, boss_id=1)
    other = d.Monster(6, 5, tribe, empowered=2, boss_id=2)
    ordinary = d.Monster(7, 5, tribe, empowered=2)
    first = d.Treasure(10, 10, "TF", boss_id=1)
    second = d.Treasure(11, 10, "TF", boss_id=2)
    mimic = d.Monster(12, 10, d.CHAR_TO_MONSTER_TRIBE["M"], boss_id=1)
    mimic.active = False
    floors = [floor([ordinary, boss, other]), floor([first, second, mimic])]
    player = d.Player(3, 3, 1000, d.LP_INIT)
    game_engine._defeat_monster(ordinary, floors[0], player, [0], [(1, 1)], Counter(), floors=floors, stage_num=6)
    assert not first.unlocked and not second.unlocked and not mimic.active
    assert not player.boss_defeated
    game_engine._defeat_monster(boss, floors[0], player, [0], [(1, 1)], Counter(), floors=floors, stage_num=6)
    assert first.unlocked and mimic.active and not second.unlocked
    assert player.boss_defeated


def test_mimic_does_not_trigger_its_own_linked_targets():
    mimic = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["M"], boss_id=1)
    chest = d.Treasure(3, 2, "TF", boss_id=1)
    other_mimic = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["M"], boss_id=1)
    other_mimic.active = False
    unlock_treasure_for_defeat(mimic, [chest])
    activate_mimic_for_defeat(mimic, [other_mimic])
    assert not chest.unlocked and not other_mimic.active


def test_dungeon_core_activates_after_final_fire_drake_and_unlocks_its_reward():
    boss = d.Monster(
        5, 5, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE], empowered=2, boss_id=1
    )
    core = d.Monster(10, 10, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DUNGEON_CORE], boss_id=2)
    core.active = False
    chest = d.Treasure(11, 10, "T*", boss_id=2)
    mimic = d.Monster(12, 10, d.CHAR_TO_MONSTER_TRIBE["M"], boss_id=2)
    mimic.active = False
    entities = [boss, core, chest, mimic]

    activate_dungeon_core_for_defeat(boss, entities)
    assert core.active and core.revealed
    glyphs = display.revealed_entity_glyphs(core, set(), False, 1, None)
    assert [(glyph.x, glyph.char) for glyph in glyphs] == [(9, "["), (10, "*"), (11, "]")]
    game_engine._defeat_monster(
        core,
        floor(entities),
        d.Player(2, 2, 100, d.LP_INIT),
        [0],
        [(2, 2)],
        Counter(),
        stage_num=6,
    )
    assert chest.unlocked and mimic.active


def test_generated_stages_assign_matching_boss_ids():
    for stage_num in (1, 2, 3, 4, 5, 6):
        if stage_num < 3:
            floors, _ = stage_world.build_single_floor(GameConfig(), stage_num)
        elif stage_num < 5:
            floors, _ = stage_world.build(stage_num=stage_num)
        elif stage_num == 5:
            floors, _ = stage5.build_member_trial()
        else:
            floors, _ = stage6.build()
        entities = [entity for current in floors for entity in current.entities]
        bosses = [e for e in entities if isinstance(e, d.Monster) and e.tribe.char != "M" and e.boss_id is not None]
        chests = [e for e in entities if isinstance(e, d.Treasure)]
        assert bosses and chests
        assert all(chest.boss_id in {boss.boss_id for boss in bosses} for chest in chests)
        for mimic in (e for e in entities if isinstance(e, d.Monster) and e.tribe.char == "M"):
            assert mimic.boss_id in {boss.boss_id for boss in bosses}
