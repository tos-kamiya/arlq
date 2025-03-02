from typing import Dict, List, Optional, Tuple

TILE_WIDTH = 10
TILE_HEIGHT = 4
TILE_NUM_X = 7
TILE_NUM_Y = 4
FIELD_WIDTH = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
CORRIDOR_V_WIDTH = 3
CORRIDOR_H_WIDTH = 2
WALL_CHARS = "####"  # single, cross, horizontal, vertical

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
EFFECT_UNLOCK_TREASURE = "Unlock Treasure"
EFFECT_ENERGY_DRAIN = "Energy Drain"
EFFECT_CALTROP_SPREAD = "Caltrop Spread"
EFFECT_ROCK_SPREAD = "Rock Spread"
EFFECT_FIRE = "Fire"

COMPANION_KARMA_LIMIT = 18

COMPANION_NOMICON = "Nomicon"
COMPANION_OCULAR = "Ocular"
COMPANION_PEGASUS = "Pegasus"

COMPANION_TO_ATTR_CHAR = {
    COMPANION_NOMICON: "n",
    COMPANION_OCULAR: "o",
    COMPANION_PEGASUS: "p",
}

PEGASUS_STEP = 9
CALTROP_SPREAD_RADIUS = 2
CALTROP_WIDTH_EXPANSION_RATIO = 1.5
CALTROP_LP_DAMAGE = 2
FIRE_OFFSETS = [
    (0, -2), (0, -1),
    (0, 1), (0, 2),
    (-2, 0), (-1, 0),
    (1, 0), (2, 0),
]
ROCK_SPREAD_OFFSETS = [
    (0, -3),
    (-2, -2), (2, -2),
    (-1, -1), (1, -1),
    (-3, 0), (3, 0),
    (-1, 1), (1, 1),
    (-2, 2), (2, 2),
    (0, 3),
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


class Player(Entity):
    """
    Player entity with additional attributes.

    Attributes:
        level: The level of the player.
        lp: Life points of the player.
        item: Currently held item.
        item_taken_from: Source of the item.
        companion: Companion character.
        karma: Player's karma.
        treasure_remains: Number of remaining treasures.
    """

    def __init__(self, x, y, level, lp, treasure_remains):
        super().__init__(x, y)
        self.level = level
        self.lp = lp
        self.item = ""
        self.item_taken_from = ""
        self.companion = ""
        self.karma = 0
        self.treasure_remains = treasure_remains


class Monster(Entity):
    """
    Monster entity belonging to a specific tribe.

    Attributes:
        tribe: The monster's tribe information.
    """

    def __init__(self, x, y, tribe):
        super().__init__(x, y)
        self.tribe = tribe


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

    def __init__(self, char, level, feed, item="", effect="", companion="", event_message=""):
        self.char = char
        self.level = level
        self.feed = feed
        self.item = item
        # Ensure that effect and companion are not both provided.
        assert not (effect and companion), "A tribe cannot have both effect and companion."
        self.effect = effect
        self.companion = companion
        self.event_message = event_message


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
    _MT("a", 1, 12),  # Amoeba
    _MT("A", 2, 12, effect=EFFECT_SPECIAL_EXP, event_message="-- Exp. Boost!"),  # Amoeba rare
    _MT("b", 5, 20, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    _MT("B", 10, 30, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison rare
    _MT("c", 10, 12, item=ITEM_SWORD_X2, event_message="-- Got a sword!"),  # Chimera
    _MT("C", 15, 12, item=ITEM_SWORD_X3, event_message="-- Got a sword!"),  # Chimera rare
    _MT("d", 20, 20, item=ITEM_POISONED),  # Comodo Dragon
    _MT(CHAR_DRAGON, 40, 12, effect=EFFECT_UNLOCK_TREASURE, event_message="-- Unlocked Dragon's treasure chest!"),  # Dragon
    _MT("e", 1, -12, effect=EFFECT_ENERGY_DRAIN, event_message="-- Energy Drained!"),  # Erebus
    _MT("f", 40, 6, effect=EFFECT_FIRE),  # Firebird
    _MT(CHAR_FIRE_DRAKE, 60, 12, effect=EFFECT_UNLOCK_TREASURE, event_message="-- Unlocked Fire Drake's treasure chest!"),  # Fire Drake
    _MT("g", 50, 12, effect=EFFECT_ROCK_SPREAD),  # Golem
    _MT("h", 999, 12),  # High elf
    _MT("n", 0, 0, companion=COMPANION_NOMICON, event_message="-- Nomicon joined!"),  # Nomicon
    _MT("o", 0, 0, companion=COMPANION_OCULAR, event_message="-- Ocular joined!"),  # Ocular
    _MT("p", 0, 0, companion=COMPANION_PEGASUS, event_message="-- Pegasus joined!"),  # Pegasus
    _MT("X", 1, 12, effect=EFFECT_CALTROP_SPREAD, event_message="-- Caltrops Scattered!"),  # Caltrop Plant
]

m: Dict[str, MonsterTribe] = {mt.char: mt for mt in MONSTER_TRIBES}

MONSTER_LEVEL_GAUGE: List[MonsterTribe] = [
    m["a"],
    m["b"],
    m["c"],
    m["d"],
    m[CHAR_DRAGON],
    m[CHAR_FIRE_DRAKE],
]

_MSC = MonsterSpawnConfig

# Stage 1 spawn configurations.
MONSTER_SPAWN_CONFIGS_ST1: List[List[MonsterSpawnConfig]] = [
    [
        _MSC(m["a"], 30),
        _MSC(m["b"], 5),
        _MSC(m["c"], 4),
        _MSC(m["C"], 1),
        _MSC(m["d"], 4),
        _MSC(m[CHAR_DRAGON], 1),
        _MSC(m["A"], 1),
        _MSC(m["n"], 0.7),
        _MSC(m["o"], 0.7),
        _MSC(m["p"], 0.7),
    ],
    [],
]

# Stage 2 spawn configurations.
MONSTER_SPAWN_CONFIGS_ST2: List[List[MonsterSpawnConfig]] = [
    MONSTER_SPAWN_CONFIGS_ST1[0],
    [
        _MSC(m["a"], 6),
        _MSC(m["b"], 2),
        _MSC(m["B"], 1),
        _MSC(m["e"], 4),
        _MSC(m["f"], 3),
        _MSC(m[CHAR_FIRE_DRAKE], 1),
        _MSC(m["g"], 3),
        _MSC(m["h"], 1),
        _MSC(m["X"], 3),
        _MSC(m["n"], 0.7),
        _MSC(m["o"], 0.7),
        _MSC(m["p"], 0.7),
    ],
]

# Mapping stages to their corresponding spawn configurations.
STAGE_TO_MONSTER_SPAWN_CONFIGS = [
    MONSTER_SPAWN_CONFIGS_ST1,
    MONSTER_SPAWN_CONFIGS_ST2,
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
    for mt in MONSTER_LEVEL_GAUGE[::-1]:
        if mt.level <= atk:
            return mt
    return None
