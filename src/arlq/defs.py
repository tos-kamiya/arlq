from typing import Dict, List, Optional, Tuple, Union

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
OCULAR_TORCH_EXTENSION = 3

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
    """x, y 座標を持つゲーム内エンティティの基底クラス。"""
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    """Entity を継承する宝物エンティティ。"""
    def __init__(self, x, y, encounter_type):
        super().__init__(x, y)
        self.encounter_type = encounter_type


class Tribe:
    """
    部族の基底クラス。
    
    Attributes:
        char: 部族の文字表現。
        event_message: 部族固有のイベントメッセージ。
    """
    def __init__(self, char: str, event_message: Optional[str]):
        self.char: str = char
        self.event_message: Optional[str] = event_message


class MonsterTribe(Tribe):
    """
    モンスター部族を表すクラス。
    
    Attributes:
        level: モンスターのレベル。
        feed: 餌の値（ゲーム固有のパラメータ）。
        item: ドロップする可能性のあるアイテム。
        effect: 付加効果（companion と排他）。
    """
    def __init__(self, char: str, level: int, feed: int, event_message: Optional[str] = None, item: Optional[str] = None, effect: Optional[str] = None):
        super().__init__(char, event_message)
        self.level: int = level
        self.feed: int = feed
        self.item: Optional[str] = item
        self.effect: Optional[str] = effect


class CompanionTribe(Tribe):
    """
    コンパニオン部族を表すクラス。
    """
    def __init__(self, char: str, durability: int = 1, event_message: Optional[str] = None):
        super().__init__(char, event_message)
        self.durability: int = durability


class Companion(Entity):
    """
    コンパニオンを表すクラス。
    
    Attributes:
        attribute: コンパニオン固有の属性（例: 特殊能力やステータス）。
    """
    def __init__(self, x, y, tribe: CompanionTribe):
        super().__init__(x, y)
        self.tribe: CompanionTribe = tribe


class Monster(Entity):
    """
    モンスターエンティティ。
    
    Attributes:
        tribe: モンスターの部族情報（MonsterTribe のインスタンス）。
        companion: （オプション）モンスターに紐づくコンパニオン（Companion のインスタンス）。
    """
    def __init__(self, x: int, y: int, tribe: MonsterTribe):
        super().__init__(x, y)
        self.tribe: MonsterTribe = tribe


class Player(Entity):
    """
    プレイヤーエンティティ。
    
    Attributes:
        level: プレイヤーのレベル。
        lp: ライフポイント。
        item: 所持アイテム。
        item_taken_from: アイテムの取得元。
        companion: （オプション）プレイヤーに付くコンパニオン（Companion のインスタンス）。
        karma: カルマ値。
    """
    def __init__(self, x: int, y: int, level: int, lp: int, companion: Optional[Companion] = None):
        super().__init__(x, y)
        self.level: int = level
        self.lp: int = lp
        self.item: Optional[str] = None
        self.item_taken_from: Optional[str] = None
        self.companion: Optional[Companion] = companion
        self.karma: int = 0


class SpawnConfig:
    """
    Holds the spawn configuration for a monster or companion tribe.

    Attributes:
        tribe: The Tribe object.
        population: Number of monsters/companions to spawn or a probability (if float).
    """

    def __init__(self, tribe: Tribe, population: Union[float, int]):
        self.tribe = tribe
        self.population = population


_MT = MonsterTribe
_CT = CompanionTribe

MONSTER_TRIBES: List[MonsterTribe] = [
    _MT("a", 1, 6),  # Amoeba
    _MT("A", 2, 6, effect=EFFECT_SPECIAL_EXP, event_message="-- Exp. Boost!"),  # Amoeba rare
    _MT("b", 5, 40, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    _MT("c", 10, 6, item=ITEM_SWORD_X1_5, event_message="-- Got a sword!"),  # Chimera
    _MT("C", 15, 6, item=ITEM_SWORD_CURSED, event_message="-- Got cursed sword!"),  # Chimera rare
    _MT("d", 20, 30, item=ITEM_POISONED),  # Comodo Dragon
    _MT(
        CHAR_DRAGON, 40, 6, effect=EFFECT_UNLOCK_TREASURE, event_message="-- Unlocked Dragon's treasure chest!"
    ),  # Dragon
    _MT("e", 1, -6, effect=EFFECT_ENERGY_DRAIN, event_message="-- Energy Drained!"),  # Erebus
    _MT(
        CHAR_FIRE_DRAKE, 60, 6, effect=EFFECT_UNLOCK_TREASURE, event_message="-- Unlocked Fire Drake's treasure chest!"
    ),  # Fire Drake
    _MT("g", 30, 0, effect=EFFECT_ROCK_SPREAD),  # Golem
    _MT("h", 999, 6),  # High elf
    _MT("X", 1, 6, effect=EFFECT_CALTROP_SPREAD, event_message="-- Caltrops Scattered!"),  # Caltrop Plant
]

COMPANION_TRIBES: List[CompanionTribe] = [
    _CT("n", 10, event_message="-- Nomicon joined!"),  # Nomicon
    _CT("o", 20, event_message="-- Ocular joined!"),  # Ocular
    _CT("p", 5, event_message="-- Pegasus joined!"),  # Pegasus
]

CHAR_TO_TRIBE: Dict[str, Tribe] = {mt.char: mt for mt in MONSTER_TRIBES + COMPANION_TRIBES}
CHAR_TO_MONSTER_TRIBE: Dict[str, MonsterTribe] = {mt.char: mt for mt in MONSTER_TRIBES}
CHAR_TO_COMPANION_TRIBE: Dict[str, CompanionTribe] = {mt.char: mt for mt in COMPANION_TRIBES}

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

_SC = SpawnConfig

# Stage 1 spawn configurations.
SPAWN_CONFIGS_ST1 = [
    _SC(CHAR_TO_TRIBE["a"], 15),
    _SC(CHAR_TO_TRIBE["A"], 1),
    _SC(CHAR_TO_TRIBE["b"], 7),
    _SC(CHAR_TO_TRIBE["c"], 2),
    _SC(CHAR_TO_TRIBE["d"], 2),
    _SC(CHAR_TO_TRIBE[CHAR_DRAGON], 1),
    _SC(CHAR_TO_TRIBE["n"], 0.7),
    _SC(CHAR_TO_TRIBE["o"], 0.7),
    _SC(CHAR_TO_TRIBE["p"], 0.7),
]

# Stage 2 spawn configurations.
SPAWN_CONFIGS_ST2 = [
    _SC(CHAR_TO_TRIBE["a"], 15),
    _SC(CHAR_TO_TRIBE["A"], 1),
    _SC(CHAR_TO_TRIBE["b"], 7),
    _SC(CHAR_TO_TRIBE["c"], 2),
    _SC(CHAR_TO_TRIBE["C"], 1),
    _SC(CHAR_TO_TRIBE["d"], 2),
    _SC(CHAR_TO_TRIBE[CHAR_FIRE_DRAKE], 1),
    _SC(CHAR_TO_TRIBE["e"], 1),
    _SC(CHAR_TO_TRIBE["g"], 1),
    _SC(CHAR_TO_TRIBE["h"], 1),
    _SC(CHAR_TO_TRIBE["X"], 1),
    _SC(CHAR_TO_TRIBE["n"], 0.7),
    _SC(CHAR_TO_TRIBE["o"], 0.7),
    _SC(CHAR_TO_TRIBE["p"], 0.7),
]

# Mapping stages to their corresponding spawn configurations.
STAGE_TO_SPAWN_CONFIGS = [
    SPAWN_CONFIGS_ST1,
    SPAWN_CONFIGS_ST2,
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
