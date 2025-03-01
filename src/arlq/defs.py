from typing import Dict, List, Optional, Tuple

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
CALTROP_SPREAD_RADIUS = 3
CALTROP_WIDTH_EXPANSION_RATIO = 1.5
CALTROP_LP_DAMAGE = 2

CHAR_DRAGON = "D"
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
    def __init__(self, x, y):
        super().__init__(x, y)


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
    """
    def __init__(self, x, y, level, lp):
        super().__init__(x, y)
        self.level = level
        self.lp = lp
        self.item = ""
        self.item_taken_from = ""
        self.companion = ""
        self.karma = 0


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


MONSTER_TRIBES_TABLE: Dict[str, MonsterTribe] = {
    "a": MonsterTribe("a", 1, 12),  # Amoeba
    "b": MonsterTribe("b", 5, 20, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    "c": MonsterTribe("c", 10, 12, item=ITEM_SWORD_X2, event_message="-- Got a strong sword!"),  # Chimera
    "d": MonsterTribe("d", 20, 20, item=ITEM_POISONED),  # Comodo Dragon
    CHAR_DRAGON: MonsterTribe(CHAR_DRAGON, 40, 12, effect=EFFECT_TREASURE_POINTER, event_message="-- Sparkle!"),  # Dragon
    "e": MonsterTribe("e", 1, -12, effect=EFFECT_ENERGY_DRAIN, event_message="-- Energy Drained."),  # Erebus
    "E": MonsterTribe("E", 999, -12),  # Eldritch

    "A": MonsterTribe("A", 1, 12, effect=EFFECT_SPECIAL_EXP, event_message="-- Exp. Boost!"),  # Amoeba rare
    "B": MonsterTribe("B", 5, 30, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison rare
    "C": MonsterTribe("C", 10, 12, item=ITEM_SWORD_X3, event_message="-- Got a strong sword!"),  # Chimera rare

    "n": MonsterTribe("n", 0, 0, companion=COMPANION_NOMICON, event_message="-- Nomicon joined."),  # Nomicon
    "o": MonsterTribe("o", 0, 0, companion=COMPANION_OCULAR, event_message="-- Ocular joined."),  # Ocular
    "p": MonsterTribe("p", 0, 0, companion=COMPANION_PEGASUS, event_message="-- Pegasus joined."),  # Pegasus

    "X": MonsterTribe("X", 1, 0, effect=EFFECT_CALTROP_SPREAD, event_message="-- Caltrops Scattered!"),  # Caltrop Plant
}


# Stage 1 spawn configurations.
MONSTER_SPAWN_CONFIGS_ST1: List[MonsterSpawnConfig] = [
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["a"], 30),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["b"], 4),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["c"], 4),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["d"], 4),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE[CHAR_DRAGON], 1),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["A"], 0.7),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["B"], 0.7),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["C"], 0.7),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["n"], 0.7),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["o"], 0.7),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["p"], 0.7),
]

# Stage 2 spawn configurations.
MONSTER_SPAWN_CONFIGS_ST2: List[MonsterSpawnConfig] = MONSTER_SPAWN_CONFIGS_ST1 + [
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["e"], 4),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["E"], 1),
    MonsterSpawnConfig(MONSTER_TRIBES_TABLE["X"], 2),
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
    max_beatable = None
    for mt in MONSTER_TRIBES_TABLE.values():
        if mt.level == 0:
            continue
        if mt.level > atk:
            break
        b = mt
        if max_beatable is None or b.level > max_beatable.level:
            max_beatable = b

    return max_beatable
