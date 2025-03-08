from typing import Dict, List, Tuple

TILE_WIDTH = 12
TILE_HEIGHT = 6
TILE_NUM_X = 6
TILE_NUM_Y = 3
FIELD_WIDTH = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
CORRIDOR_V_WIDTH = 3
CORRIDOR_H_WIDTH = 2
WALL_CHAR = "#"

TORCH_RADIUS = 3
TORCH_WIDTH_EXPANSION_RATIO = 1.7
OCULAR_TORCH_EXTENSION = 2

LP_MAX = 100
LP_INIT = 90
LP_RESPAWN_MIN = 20
LP_RESPAWN_COST = 6

MONSTER_RESPAWN_INTERVAL = 60

ITEM_SWORD_X1_5 = "Sword"
ITEM_SWORD_CURSED = "Cursed Sword"
ITEM_POISONED = "Poisoned"
ITEM_TREASURE = "Treasure"

EFFECT_SPECIAL_EXP = "Special Exp."
EFFECT_FEED_MUCH = "Feed Much"
EFFECT_UNLOCK_TREASURE = "Unlock Treasure"
EFFECT_ENERGY_DRAIN = "Energy Drain"
EFFECT_CALTROP_SPREAD = "Caltrop Spread"
EFFECT_ROCK_SPREAD = "Rock Spread"
EFFECT_GOT_TREASURE = "Got Treasure"

COMPANION_KARMA_LIMIT = 12

COMPANION_NOMICON = "Nomicon"
COMPANION_OCULAR = "Ocular"
COMPANION_PEGASUS = "Pegasus"

COMPANION_TO_ATTR_CHAR = {
    COMPANION_NOMICON: "n",
    COMPANION_OCULAR: "o",
    COMPANION_PEGASUS: "p",
}

PEGASUS_STEP_X = 9
PEGASUS_STEP_Y = 4

CALTROP_SPREAD_RADIUS = 3
CALTROP_WIDTH_EXPANSION_RATIO = 1.7
CALTROP_LP_DAMAGE = 3

ROCK_SPREAD_OFFSETS = [
    (-3, -3),
    (3, -3),
    (-2, -2),
    (2, -2),
    (-1, -1),
    (1, -1),
    (-1, 1),
    (1, 1),
    (-2, 2),
    (2, 2),
    (-3, 3),
    (3, 3),
]

CHAR_DRAGON = "D"
CHAR_FIRE_DRAKE = "F"
CHAR_TREASURE = "T"
CHAR_CALTROP = "x"

Point = Tuple[int, int]
Edge = Tuple[Point, Point]


class Entity:
    """Base class for game entities with x and y coordinates."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    """Treasure entity that inherits from Entity."""

    def __init__(self, x, y, encounter_type):
        super().__init__(x, y)
        self.encounter_type = encounter_type


class MonsterTribe:
    """
    Represents a monster tribe with inherent properties.

    Attributes:
        char: Character representation of the tribe.
        level: Level of the monster.
        feed: Feed value (game-specific parameter).
        item: Optional item that the monster may drop.
        effect: Optional effect, mutually exclusive with companion.
        companion: Optional companion, mutually exclusive with effect.
        event_message: Message shown when an event occurs with this monster.
    """

    def __init__(self, char, level, feed, item="", effect="", companion=None, event_message=""):
        self.char = char
        self.level = level
        self.feed = feed
        self.item = item
        # Ensure that effect and companion are not both provided.
        assert not (effect and companion), "A tribe cannot have both effect and companion."
        self.effect = effect
        self.companion = companion
        self.event_message = event_message


class Monster(Entity):
    """
    Monster entity belonging to a specific tribe.

    Attributes:
        tribe: The monster's tribe information.
    """

    def __init__(self, x: int, y: int, tribe: MonsterTribe):
        super().__init__(x, y)
        self.tribe: MonsterTribe = tribe


class Player(Entity):
    """
    Player entity with additional attributes.

    Attributes:
        level: The level of the player.
        lp: Life points of the player.
        item: Currently held item.
        item_taken_from: Source of the item.
        companion: Companion monster.
        karma: Player's karma.
    """

    def __init__(self, x: int, y: int, level: int, lp: int):
        super().__init__(x, y)
        self.level: int = level
        self.lp: int = lp
        self.item: str = ""
        self.item_taken_from: str = ""
        self.companion: str = ""
        self.karma: int = 0


class MonsterSpawnConfig:
    """
    Holds the spawn configuration for a monster tribe.

    Attributes:
        tribe: The MonsterTribe object.
        population: Number of monsters to spawn or a probability (if float).
    """

    def __init__(self, tribe: MonsterTribe, population):
        self.tribe = tribe
        self.population = population


_MT = MonsterTribe

MONSTER_TRIBES: List[MonsterTribe] = [
    _MT("a", 1, 6),  # Amoeba
    _MT("A", 2, 6, effect=EFFECT_SPECIAL_EXP, event_message="-- Exp. Boost!"),  # Amoeba rare
    _MT("b", 5, 35, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    _MT("c", 10, 6, item=ITEM_SWORD_X1_5, event_message="-- Got a sword!"),  # Chimera
    _MT("C", 15, 6, item=ITEM_SWORD_CURSED, event_message="-- Got cursed sword!"),  # Chimera rare
    _MT("d", 20, 25, item=ITEM_POISONED),  # Comodo Dragon
    _MT(
        CHAR_DRAGON, 40, 6, effect=EFFECT_UNLOCK_TREASURE, event_message="-- Unlocked Dragon's treasure chest!"
    ),  # Dragon
    _MT("e", 1, -6, effect=EFFECT_ENERGY_DRAIN, event_message="-- Energy Drained!"),  # Erebus
    _MT(
        CHAR_FIRE_DRAKE, 60, 6, effect=EFFECT_UNLOCK_TREASURE, event_message="-- Unlocked Fire Drake's treasure chest!"
    ),  # Fire Drake
    _MT("g", 30, 0, effect=EFFECT_ROCK_SPREAD),  # Golem
    _MT("h", 999, 6),  # High elf
    _MT("n", 0, 0, companion=COMPANION_NOMICON, event_message="-- Nomicon joined!"),  # Nomicon
    _MT("o", 0, 0, companion=COMPANION_OCULAR, event_message="-- Ocular joined!"),  # Ocular
    _MT("p", 0, 0, companion=COMPANION_PEGASUS, event_message="-- Pegasus joined!"),  # Pegasus
    _MT("X", 1, 6, effect=EFFECT_CALTROP_SPREAD, event_message="-- Caltrops Scattered!"),  # Caltrop Plant
]

CHAR_TO_MONSTER_TRIBE: Dict[str, MonsterTribe] = {mt.char: mt for mt in MONSTER_TRIBES}

MONSTER_LEVEL_GAUGE1: List[MonsterTribe] = [
    CHAR_TO_MONSTER_TRIBE["a"],
    CHAR_TO_MONSTER_TRIBE["b"],
    CHAR_TO_MONSTER_TRIBE["c"],
    CHAR_TO_MONSTER_TRIBE["d"],
]

MONSTER_LEVEL_GAUGE2: List[MonsterTribe] = [
    CHAR_TO_MONSTER_TRIBE[CHAR_DRAGON],
    CHAR_TO_MONSTER_TRIBE[CHAR_FIRE_DRAKE],
]

_MSC = MonsterSpawnConfig

# Stage 1 spawn configurations.
MONSTER_SPAWN_CONFIGS_ST1 = [
    _MSC(CHAR_TO_MONSTER_TRIBE["a"], 15),
    _MSC(CHAR_TO_MONSTER_TRIBE["A"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["b"], 10),
    _MSC(CHAR_TO_MONSTER_TRIBE["c"], 2),
    _MSC(CHAR_TO_MONSTER_TRIBE["d"], 2),
    _MSC(CHAR_TO_MONSTER_TRIBE[CHAR_DRAGON], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["n"], 0.7),
    _MSC(CHAR_TO_MONSTER_TRIBE["o"], 0.7),
    _MSC(CHAR_TO_MONSTER_TRIBE["p"], 0.7),
]

# Stage 2 spawn configurations.
MONSTER_SPAWN_CONFIGS_ST2 = [
    _MSC(CHAR_TO_MONSTER_TRIBE["a"], 15),
    _MSC(CHAR_TO_MONSTER_TRIBE["A"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["b"], 10),
    _MSC(CHAR_TO_MONSTER_TRIBE["c"], 2),
    _MSC(CHAR_TO_MONSTER_TRIBE["C"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["d"], 2),
    _MSC(CHAR_TO_MONSTER_TRIBE[CHAR_FIRE_DRAKE], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["e"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["g"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["h"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["X"], 1),
    _MSC(CHAR_TO_MONSTER_TRIBE["n"], 0.7),
    _MSC(CHAR_TO_MONSTER_TRIBE["o"], 0.7),
    _MSC(CHAR_TO_MONSTER_TRIBE["p"], 0.7),
]

# Mapping stages to their corresponding spawn configurations.
STAGE_TO_MONSTER_SPAWN_CONFIGS = [
    MONSTER_SPAWN_CONFIGS_ST1,
    MONSTER_SPAWN_CONFIGS_ST2,
]


def player_attack_by_level(player: Player) -> int:
    if player.item == ITEM_SWORD_X1_5:
        return player.level * 3 // 2
    elif player.item == ITEM_SWORD_CURSED:
        return player.level * 3
    elif player.item == ITEM_POISONED:
        return (player.level + 2) // 3
    else:
        return player.level


def get_max_beatable_monster_tribe(player: Player) -> List[MonsterTribe]:
    atk = player_attack_by_level(player)
    r = []
    for mt in MONSTER_LEVEL_GAUGE1[::-1]:
        if mt.level <= atk:
            r.append(mt)
            break
    for mt in MONSTER_LEVEL_GAUGE2[::-1]:
        if mt.level <= atk:
            r.append(mt)
            break
    return r
