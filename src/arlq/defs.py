from typing import List, Optional, Tuple

TILE_WIDTH = 10
TILE_HEIGHT = 4
TILE_NUM_X = 7
TILE_NUM_Y = 4
FIELD_WIDTH = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
CORRIDOR_V_WIDTH = 3
CORRIDOR_H_WIDTH = 2
WALL_CHARS = "###"  # cross, horizontal, vertical

TORCH_RADIUS = 4
TORCH_WIDTH_EXPANSION_RATIO = 1.5
FAIRY_TORCH_EXTENSION = 2
CLAIRVOYANCE_TORCH_EXTENSION = 6

LP_MAX = 100
LP_INIT = 90
LP_RESPAWN_MIN = 20

MONSTER_RESPAWN_RATE = 120

ITEM_SWORD_X2 = "Swordx2"
ITEM_SWORD_X3 = "Swordx3"
ITEM_POISONED = "Poisoned"
ITEM_TREASURE = "Treasure"

EFFECT_SPECIAL_EXP = "Special Exp."
EFFECT_FEED_MUCH = "Feed Much"
EFFECT_TREASURE_POINTER = "Treasure Ptr."
EFFECT_ENERGY_DRAIN = "Energy Drain"
EFFECT_CALTROP_SPREAD = "Caltrop"

COMPANION_KARMA_LIMIT = 15

COMPANION_FAIRY = "Fairy"
COMPANION_HIPPOGRIFF = "Hippogriff"
COMPANION_GOBLIN = "Goblin"

COMPANION_TO_ATTR_CHAR = {
    COMPANION_FAIRY: "f",
    COMPANION_HIPPOGRIFF: "h",
    COMPANION_GOBLIN: "g",
}

HIPPOGRIFF_FLY_STEP = 9
CALTROP_SPREAD_RADIUS = 3
CALTROP_WIDTH_EXPANSION_RATIO = 1.5
CALTROP_LP_DAMAGE = 3

CHAR_DRAGON = "D"
CHAR_TREASURE = "T"
CHAR_CALTROP = "x"

Point = Tuple[int, int]
Edge = Tuple[Point, Point]


class Entity:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    def __init__(self, x, y):
        super().__init__(x, y)


class Player(Entity):
    def __init__(self, x, y, level, lp):
        super().__init__(x, y)
        self.level = level
        self.lp = lp
        self.item = ""
        self.item_taken_from = ""
        self.companion = ""
        self.karma = 0


class Monster(Entity):
    def __init__(self, x, y, tribe):
        super().__init__(x, y)
        self.tribe = tribe


class MonsterTribe:
    def __init__(self, char, level, feed, population, item="", effect="", companion=""):
        self.char = char
        self.level = level
        self.feed = feed
        self.population = population
        self.item = item
        self.effect = effect
        self.companion = companion


MONSTER_TRIBES: List[MonsterTribe] = [
    MonsterTribe("a", 1, 12, 30),  # Amoeba
    MonsterTribe("b", 5, 20, 4, effect=EFFECT_FEED_MUCH),  # Bison
    MonsterTribe("c", 10, 12, 4, item=ITEM_SWORD_X2),  # Chimera
    MonsterTribe("d", 20, 20, 4, item=ITEM_POISONED),  # Comodo Dragon
    MonsterTribe(CHAR_DRAGON, 40, 12, 1, effect=EFFECT_TREASURE_POINTER),  # Dragon
    MonsterTribe("e", 1, -12, 4, effect=EFFECT_ENERGY_DRAIN),  # Erebus
    MonsterTribe("E", 999, -12, 1, effect=EFFECT_ENERGY_DRAIN),  # Eldritch

    MonsterTribe("A", 1, 12, 0.7, effect=EFFECT_SPECIAL_EXP),  # Amoeba rare
    MonsterTribe("B", 5, 30, 0.7, effect=EFFECT_FEED_MUCH),  # Bison rare
    MonsterTribe("C", 10, 12, 0.7, item=ITEM_SWORD_X3),  # Chimera rare

    MonsterTribe("f", 0, 0, 0.7, companion=COMPANION_FAIRY),  # Fairy
    MonsterTribe("g", 0, 0, 0.7, companion=COMPANION_GOBLIN),  # Goblin
    MonsterTribe("h", 0, 0, 0.7, companion=COMPANION_HIPPOGRIFF),  # Hippogriff

    MonsterTribe("X", 1, 0, 2, effect=EFFECT_CALTROP_SPREAD),  # Caltrop Plant
]


def player_attack_by_level(player: Player) -> int:
    if player.item == ITEM_SWORD_X2:
        return player.level * 2
    elif player.item == ITEM_SWORD_X3:
        return player.level * 3
    elif player.item == ITEM_POISONED:
        return (player.level + 2) // 3
    else:
        return player.level


def get_max_beatable_monster_tribe(player: Player) -> Optional[MonsterTribe]:
    atk = player_attack_by_level(player)
    max_beatable = None
    for mk in MONSTER_TRIBES:
        if mk.level == 0:
            continue
        if mk.level > atk:
            break
        b = mk
        if max_beatable is None or b.level > max_beatable.level:
            max_beatable = b

    return max_beatable
