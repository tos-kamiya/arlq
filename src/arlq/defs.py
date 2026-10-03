from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

TILE_WIDTH: int = 12
TILE_HEIGHT: int = 6
TILE_NUM_X: int = 6
TILE_NUM_Y: int = 3
FIELD_WIDTH: int = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT: int = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
# Stages available from the game's UI and command line.
PUBLIC_STAGE_NUMBERS: Tuple[int, ...] = (1, 2, 3, 4)
# Stages that feature elves and share the multi-floor progress state.
ELF_STAGES = frozenset({3, 4})
# Stage 1 is a smaller, introductory map: it walls off this many tile
# columns on each of the left and right edges (6 -> 4 wide), leaving
# TILE_NUM_Y unchanged.
STAGE1_COLUMN_MARGIN: int = 1
CORRIDOR_V_WIDTH: int = 3
CORRIDOR_H_WIDTH: int = 2
CHAR_WALL: str = "#"
CHAR_FLOOR: str = " "
CHAR_STAIRS_UP: str = "^"
CHAR_STAIRS_DOWN: str = "v"
STAIR_CHARS: Tuple[str, str] = (CHAR_STAIRS_UP, CHAR_STAIRS_DOWN)
CHAR_COLLAPSE: str = "O"

TORCH_RADIUS: int = 3
FOV_WIDTH_EXPANSION_RATIO: float = 1.4
OCULAR_TORCH_EXTENSION: int = 3
ELLIPSE_CELL_EDGE_THRESHOLD: float = 0.65
VORTEX_FLOOR_DIAMETER_RATIO: float = 0.8

LP_MAX: int = 100
LP_MAX_LIFEBRINGER: int = 120
LIFEBRINGER_LP_MAX_INCREASE: int = 5
LP_OVERCHARGE_MAX: int = 120
LP_INIT: int = 90
LP_RESPAWN_MIN: int = 20
LP_RESPAWN_COST: int = 6
LP_WARNING_THRESHOLD: int = 40
LP_LOW_THRESHOLD: int = 20  # LP bar/player "@" turn red at or below this

MONSTER_RESPAWN_INTERVAL: int = 65
SWORD_USES: int = 3
CURSED_SWORD_LP_COST: int = 10
NO_RESPAWN_MONSTERS = {"a", "A", "b", "c", "C"}
# These monsters do not respawn after defeat in the current game engine.
MONSTERS_EXCLUDED_FROM_RESPAWN = NO_RESPAWN_MONSTERS | {
    "W",
    "w",
    "M",
    "F",
    CHAR_COLLAPSE,
}
ELF_STAGE_C_FLAG: int = 1
ELF_STAGE_I_FLAG: int = 2
ELF_STAGE_K_FLAG: int = 4
ELF_STAGE_H_FLAG: int = 8
STAGE3_W_FLAG: int = 16
ELF_STAGE_S_FLAG: int = 32
ELF_STAGE_J_FLAG: int = 64
ELF_STAGE_L_FLAG: int = 128
SYLVAN_COMPANION_DURATION_MULTIPLIER: float = 1.25
STAGE4_FINAL_FLOOR_BARRIER_PERCENT = 10
LOOP_TURNS = 80
OVERSHOOT_REWIND_TURNS = 5
MARKSMAN_ARROW_LIMIT = 20
MARKSMAN_COOLDOWN_TURNS = 2
STAGE3_FLOOR_LAYOUT: List[Tuple[int, int]] = [(1, 0), (0, 0), (0, 0)]
STAGE4_FLOOR_LAYOUT: List[Tuple[int, int]] = [
    (1, 1),
    (0, 1),
    (0, 1),
    (0, 1),
    (0, 1),
]
# build() shuffles these counts across floors when no explicit layout is given.
STAGE4_FILLED_ROOM_COUNTS: Tuple[int, ...] = (0, 1, 1, 2, 3)
STAGE3_STAIR_PAIRS_PER_TRANSITION = 1
STAGE4_STAIR_PAIRS_PER_TRANSITION = 2
# Order of the elf-stage status-line marks. The stage boss and treasure "T"
# are added separately.
ELF_STAGE_PROGRESS: List[Tuple[str, int]] = [
    ("C", ELF_STAGE_C_FLAG),
    ("I", ELF_STAGE_I_FLAG),
    ("J", ELF_STAGE_J_FLAG),
    ("K", ELF_STAGE_K_FLAG),
    ("H", ELF_STAGE_H_FLAG),
    ("S", ELF_STAGE_S_FLAG),
]

ITEM_SWORD_X1_5: str = "Sword"
ITEM_SWORD_CURSED: str = "Cursed Sword"
ITEM_POISONED: str = "Poisoned"
ITEM_SPORES: str = "Spores"
EFFECT_SPECIAL_EXP: str = "Special Exp."
EFFECT_LEVEL_REDUCE: str = "Level Reduce"
EFFECT_FEED_MUCH: str = "Feed Much"
EFFECT_UNLOCK_TREASURE: str = "Unlock Treasure"
EFFECT_ENERGY_DRAIN: str = "Energy Drain"
EFFECT_CALTROP_SPREAD: str = "Caltrop Spread"
EFFECT_ROCK_SPREAD: str = "Rock Spread"
EFFECT_VORTEX: str = "Vortex"
EFFECT_GOT_TREASURE: str = "Got Treasure"

PEGASUS_STEP_X: int = 9
PEGASUS_STEP_Y: int = 4

CALTROP_SPREAD_RADIUS: int = 3
CALTROP_WIDTH_EXPANSION_RATIO: float = 1.7
CALTROP_LP_DAMAGE: int = 3
MARKSMAN_LP_DAMAGE: int = 4
BARRIER_LP_DAMAGE: int = 30

ROCK_SPREAD_OFFSETS: List[Tuple[int, int]] = [
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


CHAR_DRAGON: str = "D"
CHAR_FIRE_DRAKE: str = "F"
CHAR_PEGASUS: str = "p"
CHAR_TREASURE: str = "T"
CHAR_CALTROP: str = "x"
CHAR_BARRIER: str = "="

Point = Tuple[int, int]
Edge = Tuple[Point, Point]

COLLAPSE_FOOTPRINT_OFFSETS: Tuple[Point, ...] = (
    (0, 0),
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
)


def collapse_footprint(center: Point) -> Set[Point]:
    x, y = center
    return {(x + dx, y + dy) for dx, dy in COLLAPSE_FOOTPRINT_OFFSETS}


def collapse_placement_cells_valid(
    point: Point, *fields: Sequence[Sequence[str]]
) -> bool:
    """Check that a Collapse footprint contains only floor or wall cells."""
    if not fields:
        return False
    for field in fields:
        height = len(field)
        width = len(field[0]) if field else 0
        for x, y in collapse_footprint(point):
            if not (0 <= x < width and 0 <= y < height):
                return False
            if field[y][x] not in (CHAR_FLOOR, CHAR_WALL):
                return False
    return True


class Entity:
    """Base class for entities in the game that have x and y coordinates."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    """A chest whose unlock state is part of the chest instance."""

    def __init__(self, x, y, encounter_type, unlock_key: Optional[str] = None):
        super().__init__(x, y)
        self.encounter_type = encounter_type
        self.unlock_key = unlock_key or encounter_type
        self.unlocked: bool = False


class Tribe:
    """
    Base class for tribes in the game.

    Attributes:
        char: Character representation of the tribe.
        event_message: Event message specific to the tribe.
        event_message_importance: Display priority for the event message.
    """

    def __init__(
        self,
        char: str,
        event_message: Optional[str],
        event_message_importance: int = 5,
    ):
        self.char: str = char
        self.event_message: Optional[str] = event_message
        self.event_message_importance = event_message_importance


class MonsterTribe(Tribe):
    """
    Class representing monster tribes in the game.

    Attributes:
        level: Level of the monster.
        feed: Feed value (game-specific parameter).
        item: Item that can be dropped.
        effect: Additional effect (exclusive with companion).
    """

    def __init__(
        self,
        char: str,
        level: int,
        feed: int,
        event_message: Optional[str] = None,
        item: Optional[str] = None,
        effect: Optional[str] = None,
        is_elf: bool = False,
        respawn_on_random_floor: bool = False,
        event_message_importance: int = 5,
    ):
        super().__init__(char, event_message, event_message_importance)
        self.level: int = level
        self.feed: int = feed
        self.item: Optional[str] = item
        self.effect: Optional[str] = effect
        self.is_elf: bool = is_elf
        self.respawn_on_random_floor: bool = respawn_on_random_floor


class ElfTribe(MonsterTribe):
    """An elf tribe, kept separate from ordinary monster tribes."""

    def __init__(
        self,
        char: str,
        event_message: Optional[str] = None,
        respawn_on_random_floor: bool = False,
        event_message_importance: int = 5,
    ):
        super().__init__(
            char,
            level=0,
            feed=0,
            event_message=event_message,
            event_message_importance=event_message_importance,
            is_elf=True,
            respawn_on_random_floor=respawn_on_random_floor,
        )


class CompanionTribe(Tribe):
    """
    Class representing companion tribes in the game.

    Attributes:
        durability: Durability of the companion.
    """

    def __init__(
        self,
        char: str,
        durability: int = 1,
        event_message: Optional[str] = None,
        event_message_importance: int = 5,
    ):
        super().__init__(char, event_message, event_message_importance)
        self.durability: int = durability


class Companion(Entity):
    """
    Class representing companions in the game.

    Attributes:
        tribe: Tribe information of the companion (CompanionTribe instance).
        origin_floor: (multi-floor stages) index of the floor this companion was
            spawned on, used to respawn it there after it is carried to
            another floor and expires.
    """

    def __init__(self, x, y, tribe: CompanionTribe, origin_floor: Optional[int] = None):
        super().__init__(x, y)
        self.tribe: CompanionTribe = tribe
        # Per-instance effective lifetime; bonuses must not change the
        # tribe's shared base durability.
        self.durability: int = tribe.durability
        self.origin_floor: Optional[int] = origin_floor
        self.revealed: bool = False


class Monster(Entity):
    """
    Class representing monster entities in the game.

    Attributes:
        tribe: Tribe information of the monster (MonsterTribe instance).
        empowered: Empowerment rank for an enhanced monster instance.
    """

    def __init__(
        self,
        x: int,
        y: int,
        tribe: MonsterTribe,
        empowered: int = 1,
        mimic_boss_char: Optional[str] = None,
        mimic_boss_empowered: Optional[int] = None,
    ):
        super().__init__(x, y)
        self.tribe: MonsterTribe = tribe
        if empowered < 1:
            raise ValueError("empowered must be positive")
        self.empowered: int = empowered
        # Mimics are identified by the boss whose treasure they imitate.
        self.mimic_boss_char: Optional[str] = mimic_boss_char
        self.mimic_boss_empowered: Optional[int] = mimic_boss_empowered
        self.revealed: bool = False
        self.met: bool = False
        self.active: bool = True
        self.arrow_marks: List[Tuple[Point, str]] = []
        self.marksman_cooldown: int = 0


class Collapse(Monster):
    """A fixed level-one monster that reveals nearby Collapse holes."""

    def __init__(self, x: int, y: int):
        super().__init__(x, y, MonsterTribe(CHAR_COLLAPSE, level=1, feed=0))


class Elf(Monster):
    """An encounterable elf. Elves share map state with monsters but do not fight."""

    def __init__(self, x: int, y: int, tribe: ElfTribe):
        super().__init__(x, y, tribe)


def monster_level(monster: Monster) -> int:
    if monster.empowered == 1:
        return monster.tribe.level
    level = monster.tribe.level * 3 + 10
    for _ in range(3, monster.empowered + 1):
        level *= 3
    return level


def monster_type_key(monster: Monster) -> str:
    char = monster.tribe.char
    if char == "M" and monster.mimic_boss_char is not None:
        char += monster.mimic_boss_char
        if (
            monster.mimic_boss_empowered is not None
            and monster.mimic_boss_empowered > 1
        ):
            marker = "'" if monster.mimic_boss_empowered == 2 else '"'
            char += marker
    return char if monster.empowered == 1 else f"{char}{monster.empowered}"


class Player(Entity):
    """
    Class representing player entities in the game.

    Attributes:
        level: Level of the player.
        lp: Life points.
        item: Item held by the player.
        item_uses: Remaining uses for consumable item effects.
        item_taken_from: Source from which the item was taken.
        companion: (Optional) Companion associated with the player (Companion instance).
        karma: Karma value.
    """

    def __init__(
        self, x: int, y: int, level: int, lp: int, companion: Optional[Companion] = None
    ):
        super().__init__(x, y)
        self.level: int = level
        self.lp: int = lp
        self.item: Optional[str] = None
        self.item_uses: int = 0
        self.item_taken_from: Optional[str] = None
        self.companion: Optional[Companion] = companion
        self.karma: int = 0
        self.boss_defeated: bool = False
        self.treasure_collected: bool = False
        # Identified monster types are known across all floors.
        self.known_monsters: Set[str] = set()
        # Floors where the Cursed Chimera has been identified or defeated us.
        self.known_c_floors: Set[int] = set()
        self.elf_stage_floors: Dict[str, int] = {}
        self.known_elf_floors: Set[str] = set()
        # Shared progress for the elf stages, including Stage 3's W flag.
        self.elf_stage_flags: int = 0
        self.lifebringer_lp_max: int = LP_MAX
        self.current_floor: int = 0
        self.persistent_followers: List[Tuple[int, int, int, str]] = []
        # (floor, x, y) of the monster involved in the most recent monster
        # contact (win, loss, or a no-combat gatekeeper like High Elf), or
        # None. Losing combat against the same (floor, x, y) twice in a row,
        # with no other monster contact in between, means that monster is
        # blocking the only way through a bridge corridor; see the escape
        # branch in game_engine._resolve_monster_contact().
        self.last_contact_monster: Optional[Tuple[int, int, int]] = None
        # Whether the player has already been turned away by an unrecognized
        # High Elf at least once (Stage 2's gatekeeper, or Stage 3's before
        # meeting two of I/J/K). The first refusal only shows a message; any
        # later refusal sends the player elsewhere, like repeat contact with
        # the Isolated Elf.
        self.high_elf_refused: bool = False
        # Same idea as high_elf_refused for Stage 3's Collector Elf (K).
        self.k_elf_refused: bool = False

    @property
    def stage_won(self) -> bool:
        return self.boss_defeated and self.treasure_collected


class SpawnConfig:
    """
    Holds the spawn configuration for a monster or companion tribe.

    Attributes:
        tribe: The Tribe object.
        population: Number of monsters/companions to spawn or a probability (if float).
    """

    def __init__(self, tribe: Tribe, population: Union[float, int], empowered: int = 1):
        self.tribe = tribe
        self.population = population
        self.empowered = empowered


_MT = MonsterTribe
_ET = ElfTribe
_CT = CompanionTribe

MIN_FOOD = 8

MONSTER_TRIBES: List[MonsterTribe] = [
    _MT("a", 1, 10),  # Amoeba
    _MT(
        "A", 2, MIN_FOOD, effect=EFFECT_SPECIAL_EXP, event_message="-- Level boosted!"
    ),  # Amoeba rare
    _MT("b", 5, 60, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    _MT(
        "c",
        10,
        MIN_FOOD,
        item=ITEM_SWORD_X1_5,
        event_message="-- Got a sword (c)!",
        event_message_importance=7,
    ),  # Chimera
    _MT(
        "C",
        15,
        MIN_FOOD,
        item=ITEM_SWORD_CURSED,
        event_message="-- Got a cursed sword (C)!",
        event_message_importance=7,
    ),  # Chimera rare
    _MT("d", 20, 60, item=ITEM_POISONED),  # Comodo Dragon
    _MT(
        CHAR_DRAGON,
        35,
        MIN_FOOD,
        effect=EFFECT_UNLOCK_TREASURE,
        event_message="-- Unlocked the Dragon's treasure chest!",
        event_message_importance=7,
    ),  # Dragon
    _MT(
        "e",
        1,
        -5,
        effect=EFFECT_ENERGY_DRAIN,
        event_message="-- Your energy was drained!",
    ),  # Erebus
    _MT(
        "E",
        30,
        MIN_FOOD,
        effect=EFFECT_LEVEL_REDUCE,
        event_message="-- Your level was reduced!",
        respawn_on_random_floor=True,
    ),  # Erebus rare
    _MT(
        CHAR_FIRE_DRAKE,
        60,
        MIN_FOOD,
        effect=EFFECT_UNLOCK_TREASURE,
        event_message="-- Unlocked the Fire Drake's treasure chest!",
        event_message_importance=7,
    ),  # Fire Drake
    _MT("f", 50, MIN_FOOD),  # Fire Lizard
    _MT("g", 30, 0, effect=EFFECT_ROCK_SPREAD),  # Golem
    _MT(
        "X",
        1,
        MIN_FOOD,
        effect=EFFECT_CALTROP_SPREAD,
        event_message="-- Caltrops were scattered!",
        respawn_on_random_floor=True,
    ),  # Caltrop Plant
    _ET(
        "I",
        event_message="-- The Isolated Elf told you about the history of the elves.",
        event_message_importance=3,
    ),
    _ET(
        "J",
        event_message="-- The Javelin Elf joined your hunt!",
        event_message_importance=7,
    ),
    _ET(
        "K",
        event_message="-- The Collector Elf (K) gave you a rustless blade for your Cursed Sword!",
        event_message_importance=7,
    ),
    _ET(
        "H",
        event_message="-- The High Elf bestowed the protective amulet upon you!",
        event_message_importance=7,
    ),
    _ET(
        "L",
        event_message="-- The Lifebringer Elf restored your health!",
        respawn_on_random_floor=True,
    ),
    _ET(
        "S",
        event_message=(
            "-- The Sylvan Elf gave you fairy nectar! Companions will stay with you longer."
        ),
        event_message_importance=7,
    ),
    _MT("k", 80, MIN_FOOD),  # Marksman
    _MT(
        "M",
        1,
        1,
        event_message="-- You defeated the Mimic, but were sent somewhere else.",
    ),  # Mimic
    _MT(
        "m",
        5,
        MIN_FOOD,
        item=ITEM_SPORES,
        event_message="-- Spores cloud your vision!",
    ),
    _MT("w", 50, MIN_FOOD),
    _MT(
        "W",
        150,
        MIN_FOOD,
        event_message=">> Dread Wyrm (W) defeated! <<",
        event_message_importance=9,
    ),
    _MT(
        "V",
        30,
        MIN_FOOD,
        effect=EFFECT_VORTEX,
        event_message="-- The Vortex rearranges the floor!",
        respawn_on_random_floor=True,
    ),
]
assert len({tribe.char for tribe in MONSTER_TRIBES}) == len(MONSTER_TRIBES), (
    "Duplicate tribe char"
)

COMPANION_TRIBES: List[CompanionTribe] = [
    _CT(
        "l"
    ),  # Looping companion; contact always rewinds via _rewind_to_history, so no event_message here
    _CT("n", 10, event_message="-- Nomicon joined!", event_message_importance=3),
    _CT("o", 20, event_message="-- Ocular joined!", event_message_importance=3),
    _CT(
        CHAR_PEGASUS,
        5,
        event_message="-- Pegasus joined!",
        event_message_importance=3,
    ),
]

CHAR_TO_TRIBE: Dict[str, Tribe] = {
    mt.char: mt for mt in MONSTER_TRIBES + COMPANION_TRIBES
}
CHAR_TO_MONSTER_TRIBE: Dict[str, MonsterTribe] = {mt.char: mt for mt in MONSTER_TRIBES}
CHAR_TO_COMPANION_TRIBE: Dict[str, CompanionTribe] = {
    mt.char: mt for mt in COMPANION_TRIBES
}

_SC = SpawnConfig

# Stage 1 spawn configurations.
SPAWN_CONFIGS_ST1 = [
    _SC(CHAR_TO_TRIBE["a"], 9),
    _SC(CHAR_TO_TRIBE["A"], 2),
    _SC(CHAR_TO_TRIBE["b"], 5),
    _SC(CHAR_TO_TRIBE["c"], 1),
    _SC(CHAR_TO_TRIBE["d"], 2),
    _SC(CHAR_TO_TRIBE[CHAR_DRAGON], 1),
    _SC(CHAR_TO_TRIBE["n"], 0.7),
    _SC(CHAR_TO_TRIBE["o"], 0.7),
]

# Stage 2 spawn configurations.
STAGE2_BOSS_BARRIER_COUNT: int = 5
SPAWN_CONFIGS_ST2 = [
    _SC(CHAR_TO_TRIBE["a"], 20),
    _SC(CHAR_TO_TRIBE["A"], 3),
    _SC(CHAR_TO_TRIBE["b"], 5),
    _SC(CHAR_TO_TRIBE["b"], 2, empowered=2),
    _SC(CHAR_TO_TRIBE["c"], 2),
    _SC(CHAR_TO_TRIBE["C"], 1),
    _SC(CHAR_TO_TRIBE["d"], 4),
    _SC(CHAR_TO_TRIBE[CHAR_FIRE_DRAKE], 1),
    _SC(CHAR_TO_TRIBE["e"], 1),
    _SC(CHAR_TO_TRIBE["g"], 1),
    _SC(CHAR_TO_TRIBE["H"], 1),
    _SC(CHAR_TO_TRIBE["X"], 1),
    _SC(CHAR_TO_TRIBE["n"], 0.7),
    _SC(CHAR_TO_TRIBE["o"], 0.7),
    _SC(CHAR_TO_TRIBE[CHAR_PEGASUS], 0.7),
]

# Mapping stages to their corresponding spawn configurations.
STAGE_TO_SPAWN_CONFIGS = [
    SPAWN_CONFIGS_ST1,
    SPAWN_CONFIGS_ST2,
    [],  # Stage 3 uses its per-floor roster in game_engine.py.
    [],  # Stage 4 uses its per-floor roster in game_engine.py.
]

# Per-floor rosters for the multi-floor stages. Each entry is
# (tribe character, population, empowered rank).
STAGE3_ROSTER: List[List[Tuple[str, int, int]]] = [
    [
        ("a", 20, 1),
        ("A", 2, 1),
        ("b", 10, 1),
        ("c", 1, 1),
        ("c", 1, 2),
        ("d", 3, 1),
        ("d", 3, 2),
        ("l", 1, 1),
        ("J", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
    ],
    [
        ("a", 16, 1),
        ("A", 2, 1),
        ("b", 4, 1),
        ("b", 4, 2),
        ("c", 1, 1),
        ("c", 1, 2),
        ("d", 3, 1),
        ("d", 3, 2),
        ("l", 1, 1),
        ("K", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
    ],
    [
        ("a", 12, 1),
        ("A", 2, 1),
        ("b", 2, 1),
        ("b", 6, 2),
        ("d", 3, 1),
        ("d", 3, 2),
        ("l", 1, 1),
        ("w", 1, 1),
        ("W", 1, 1),
        ("H", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
    ],
]

STAGE4_ROSTER: List[List[Tuple[str, int, int]]] = [
    [
        ("a", 20, 1),
        ("A", 1, 1),
        ("b", 10, 1),
        ("c", 1, 1),
        ("d", 4, 1),
        ("d", 2, 2),
        ("e", 1, 1),
        ("l", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
    ],
    [
        ("a", 16, 1),
        ("X", 1, 1),
        ("A", 1, 1),
        ("b", 4, 1),
        ("b", 4, 2),
        ("c", 1, 1),
        ("g", 2, 1),
        ("d", 6, 2),
        ("k", 2, 1),
        ("l", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
        ("V", 1, 1),
        ("E", 1, 1),
    ],
    [
        ("a", 12, 1),
        ("X", 1, 1),
        ("A", 1, 1),
        ("b", 8, 2),
        ("c", 1, 1),
        ("g", 2, 1),
        ("d", 6, 2),
        ("k", 3, 1),
        ("l", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
    ],
    [
        ("a", 8, 1),
        ("X", 1, 1),
        ("A", 1, 1),
        ("b", 4, 2),
        ("b", 4, 3),
        ("c", 1, 1),
        ("g", 2, 1),
        ("d", 4, 2),
        ("d", 2, 3),
        ("k", 3, 1),
        ("l", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
        ("w", 2, 1),
    ],
    [
        ("a", 4, 1),
        ("A", 1, 1),
        ("b", 8, 3),
        ("c", 1, 1),
        ("g", 2, 1),
        ("d", 2, 2),
        ("d", 4, 3),
        ("l", 1, 1),
        ("n", 1, 1),
        ("o", 1, 1),
        (CHAR_PEGASUS, 1, 1),
        ("F", 1, 2),
        ("MF'", 1, 1),
    ],
]

# Elves placed by the multi-floor builder instead of the static floor rosters.
STAGE_RUNTIME_ELVES: Dict[int, Tuple[str, ...]] = {
    3: ("C", "I"),
    4: ("C", "I", "J", "K", "H", "S", "L"),
}

STAGE3_FLOORS = len(STAGE3_ROSTER)
STAGE4_FLOORS = len(STAGE4_ROSTER)
STAGE_BOSSES: Dict[int, Tuple[str, int]] = {
    3: ("W", 1),
    4: (CHAR_FIRE_DRAKE, 2),
}


def decode_stage_roster_entry(
    roster_char: str, empowered: int
) -> Tuple[str, int, Optional[str], int]:
    """Decode a roster token into monster and optional mimic target data.

    ``MF'`` means a rank-1 Mimic linked to a rank-2 Fire Drake. ``MW``
    links a Mimic to a normal Wyrm. The tuple result is monster character,
    monster rank, mimic boss character, and mimic boss rank.
    """
    if roster_char == "M":
        return "M", empowered, None, 1
    if roster_char.startswith("M"):
        target = roster_char[1:]
        if target.endswith("'"):
            boss_empowered = 2
            boss_char = target[:-1]
        elif target.endswith('"'):
            boss_empowered = 3
            boss_char = target[:-1]
        else:
            boss_empowered = 1
            boss_char = target
        if len(boss_char) == 1 and boss_char in CHAR_TO_MONSTER_TRIBE:
            return "M", empowered, boss_char, boss_empowered
        raise ValueError(f"invalid mimic roster token: {roster_char!r}")
    return roster_char, empowered, None, 1


def _empowered_strength_tribe(char: str, empowered: int) -> MonsterTribe:
    tribe = CHAR_TO_MONSTER_TRIBE[char]
    level = (
        tribe.level
        if empowered == 1
        else (tribe.level * 3 + 10) * 3 ** (empowered - 2)
    )
    return MonsterTribe(monster_variant_label(char, empowered), level, tribe.feed)


def monster_variant_label(char: str, empowered: int) -> str:
    """Return the roster/display label for a monster and its rank."""
    if empowered == 1:
        return char
    marker = "'" if empowered == 2 else '"'
    return f"{char}{marker}"


def stage_boss_label(stage_num: int) -> str:
    """Return a stage boss's display label from its stage configuration."""
    char, empowered = STAGE_BOSSES[stage_num]
    return monster_variant_label(char, empowered)


def _get_stage_roster_tribes(roster: List[List[Tuple[str, int, int]]]):
    variants = dict.fromkeys(
        (monster_char, monster_empowered)
        for floor in roster
        for char, _, empowered in floor
        for monster_char, monster_empowered, _, _ in [
            decode_stage_roster_entry(char, empowered)
        ]
        if monster_char in CHAR_TO_MONSTER_TRIBE
        and not CHAR_TO_MONSTER_TRIBE[monster_char].is_elf
    )
    return sorted(
        (
            _empowered_strength_tribe(char, empowered)
            for char, empowered in variants
        ),
        key=lambda tribe: tribe.level,
        reverse=True,
    )


STAGE3_ROSTER_TRIBES: List[MonsterTribe] = sorted(
    [*_get_stage_roster_tribes(STAGE3_ROSTER), CHAR_TO_MONSTER_TRIBE["C"]],
    key=lambda tribe: tribe.level,
    reverse=True,
)
# Collapse is a fixed stage object, but appears at level 1 on the strength gauge.
STAGE4_ROSTER_TRIBES: List[MonsterTribe] = sorted(
    [
        *_get_stage_roster_tribes(STAGE4_ROSTER),
        CHAR_TO_MONSTER_TRIBE["C"],
        MonsterTribe(CHAR_COLLAPSE, level=1, feed=0),
    ],
    key=lambda tribe: tribe.level,
    reverse=True,
)
def _javelin_follower_active(player: Player) -> bool:
    return any(follower[3] == "J" for follower in player.persistent_followers)


def player_lp_max(player: Player) -> int:
    """Return the player's permanent LP maximum, including Lifebringer's bonus."""
    return min(player.lifebringer_lp_max, LP_MAX_LIFEBRINGER)


def apply_feed(player: Player, feed: int) -> None:
    # Preserve temporary LP above the permanent cap until it is spent. Feeding
    # cannot refill the overcharge once LP has risen above that cap.
    cap = min(LP_OVERCHARGE_MAX, max(player_lp_max(player), player.lp))
    player.lp = max(1, min(cap, player.lp + feed))


def apply_respawn_penalty(player: Player) -> None:
    player.lp -= LP_RESPAWN_COST
    player.lp = max(LP_RESPAWN_MIN, min(player.lp, LP_INIT))


def clear_player_item(player: Player) -> None:
    """Remove the held item and all state associated with it."""
    player.item = None
    player.item_uses = 0
    player.item_taken_from = None


def take_monster_item(
    player: Player,
    item: Optional[str],
    source: str,
    sword_uses: int = SWORD_USES,
) -> None:
    player.item = item
    player.item_taken_from = source
    player.item_uses = sword_uses if item in (ITEM_SWORD_X1_5, ITEM_SWORD_CURSED) else 0


def grant_defeat_level(player: Player, effect: Optional[str]) -> None:
    if effect == EFFECT_LEVEL_REDUCE:
        player.level = max(1, player.level * 2 // 3)
    else:
        player.level += 10 if effect == EFFECT_SPECIAL_EXP else 1


def current_player_attack(player: Player, stage_num: int = 0) -> int:
    """
    Player's current attack power: level and equipped item, plus permanent
    bonuses from the Collector's flag and the Javelin Elf follower. Bonuses
    apply in every stage, and this shared calculation keeps combat and display
    consistent. `stage_num` is retained for existing callers.
    """
    if player.item == ITEM_SWORD_X1_5:
        value = player.level * 3 // 2
    elif player.item == ITEM_SWORD_CURSED:
        value = player.level * 3
    elif player.item == ITEM_POISONED:
        value = (player.level + 1) // 2
    else:
        value = player.level

    if player.elf_stage_flags & ELF_STAGE_K_FLAG:
        value = (value * 6 + 1) // 5
    if _javelin_follower_active(player):
        value = (value * 5 + 2) // 4
    return value


def get_stage_roster_tribes(stage_num: int) -> List[MonsterTribe]:
    """Distinct, non-elf monster tribes that can appear in stage 1 or 2, strongest first."""
    configs = STAGE_TO_SPAWN_CONFIGS[stage_num - 1]
    variants = dict.fromkeys(
        (sc.tribe.char, sc.empowered)
        for sc in configs
        if isinstance(sc.tribe, MonsterTribe) and not sc.tribe.is_elf
    )
    return sorted(
        (_empowered_strength_tribe(char, empowered) for char, empowered in variants),
        key=lambda t: t.level,
        reverse=True,
    )



# Keep the established import surface while frontends use the display module.
from .display import (
    FieldGlyph as FieldGlyph,
    build_strength_column as build_strength_column,
    elf_stage_progress_marks as elf_stage_progress_marks,
    level_item_labels as level_item_labels,
    player_appearance as player_appearance,
    preview_entity_glyphs as preview_entity_glyphs,
    revealed_entity_glyphs as revealed_entity_glyphs,
    status_prefix as status_prefix,
)
