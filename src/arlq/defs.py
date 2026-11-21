from itertools import count
from math import ceil
from typing import Optional, Sequence, Union

from .stage_data import (
    STAGE1_COLUMN_MARGIN as STAGE1_COLUMN_MARGIN,
)
from .stage_data import (
    STAGE2_BOSS_BARRIER_COUNT as STAGE2_BOSS_BARRIER_COUNT,
)
from .stage_data import (
    STAGE3_FLOOR_LAYOUT as STAGE3_FLOOR_LAYOUT,
)
from .stage_data import (
    STAGE3_FLOORS as STAGE3_FLOORS,
)
from .stage_data import (
    STAGE3_ROSTER as STAGE3_ROSTER,
)
from .stage_data import (
    STAGE3_STAIR_PAIRS_PER_TRANSITION as STAGE3_STAIR_PAIRS_PER_TRANSITION,
)
from .stage_data import (
    STAGE4_FILLED_ROOM_COUNTS as STAGE4_FILLED_ROOM_COUNTS,
)
from .stage_data import (
    STAGE4_FINAL_FLOOR_BARRIER_PERCENT as STAGE4_FINAL_FLOOR_BARRIER_PERCENT,
)
from .stage_data import (
    STAGE4_FLOOR_LAYOUT as STAGE4_FLOOR_LAYOUT,
)
from .stage_data import (
    STAGE4_FLOORS as STAGE4_FLOORS,
)
from .stage_data import (
    STAGE4_ROSTER as STAGE4_ROSTER,
)
from .stage_data import (
    STAGE4_STAIR_PAIRS_PER_TRANSITION as STAGE4_STAIR_PAIRS_PER_TRANSITION,
)
from .stage_data import (
    STAGE6_BARRIER_VORTEX_RADIUS_MULTIPLIER as STAGE6_BARRIER_VORTEX_RADIUS_MULTIPLIER,
)
from .stage_data import (
    STAGE6_BOSS_ESCORTS as STAGE6_BOSS_ESCORTS,
)
from .stage_data import (
    STAGE6_BOSS_PARTY as STAGE6_BOSS_PARTY,
)
from .stage_data import (
    STAGE6_BOSS_PARTY_ADDITIONS as STAGE6_BOSS_PARTY_ADDITIONS,
)
from .stage_data import (
    STAGE6_BRIDGEHEAD_KNOWN_VORTEX_RATIO as STAGE6_BRIDGEHEAD_KNOWN_VORTEX_RATIO,
)
from .stage_data import (
    STAGE6_CORE_GROWTH_TURNS as STAGE6_CORE_GROWTH_TURNS,
)
from .stage_data import (
    STAGE6_EXTRA_BISON_RANKS as STAGE6_EXTRA_BISON_RANKS,
)
from .stage_data import (
    STAGE6_EXTRA_CORRIDORS as STAGE6_EXTRA_CORRIDORS,
)
from .stage_data import (
    STAGE6_FINAL_FLOOR_BARRIER_PERCENT as STAGE6_FINAL_FLOOR_BARRIER_PERCENT,
)
from .stage_data import (
    STAGE6_FIXED_MONSTERS as STAGE6_FIXED_MONSTERS,
)
from .stage_data import (
    STAGE6_FLOORS as STAGE6_FLOORS,
)
from .stage_data import (
    STAGE6_HAZARD_COUNTS as STAGE6_HAZARD_COUNTS,
)
from .stage_data import (
    STAGE6_INITIAL_MONSTERS as STAGE6_INITIAL_MONSTERS,
)
from .stage_data import (
    STAGE6_INITIAL_SPAWN_DRAWS as STAGE6_INITIAL_SPAWN_DRAWS,
)
from .stage_data import (
    STAGE6_MONSTER_PARTY_LIMIT as STAGE6_MONSTER_PARTY_LIMIT,
)
from .stage_data import (
    STAGE6_PARTY_SPAWN_ATTEMPTS as STAGE6_PARTY_SPAWN_ATTEMPTS,
)
from .stage_data import (
    STAGE6_PARTY_SPAWN_PERCENT as STAGE6_PARTY_SPAWN_PERCENT,
)
from .stage_data import (
    STAGE6_ROSTER as STAGE6_ROSTER,
)
from .stage_data import (
    STAGE6_SPAWN_ATTEMPTS as STAGE6_SPAWN_ATTEMPTS,
)
from .stage_data import (
    STAGE6_SPAWN_INTERVAL as STAGE6_SPAWN_INTERVAL,
)
from .stage_data import (
    STAGE6_SUPPORT_POOLS as STAGE6_SUPPORT_POOLS,
)
from .stage_data import (
    STAGE6_TURN_LIMIT as STAGE6_TURN_LIMIT,
)
from .stage_data import (
    STAGE_BOSSES as STAGE_BOSSES,
)
from .stage_data import (
    STAGE_RUNTIME_ELVES as STAGE_RUNTIME_ELVES,
)
from .stage_data import (
    STAGE_START_MESSAGES as STAGE_START_MESSAGES,
)
from .stage_data import (
    make_spawn_configs,
)
from .symbols import (
    CHAR_DRAGON as CHAR_DRAGON,
)
from .symbols import (
    CHAR_FIRE_DRAKE as CHAR_FIRE_DRAKE,
)
from .symbols import (
    CHAR_PEGASUS as CHAR_PEGASUS,
)

TILE_WIDTH: int = 11
FIELD_X_MARGIN: int = 1
FIELD_SIDEBAR_GAP: int = 2
INITIALLY_KNOWN_MONSTERS: tuple[str, ...] = ("a",)
TILE_HEIGHT: int = 6
TILE_NUM_X: int = 6
TILE_NUM_Y: int = 3
FIELD_WIDTH: int = (TILE_WIDTH + 1) * TILE_NUM_X + 1 + 2 * FIELD_X_MARGIN
FIELD_HEIGHT: int = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
# Stages available from the game's UI and command line.
PUBLIC_STAGE_NUMBERS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
MEMBER_JESTER = "Jester"
MEMBER_JAVELIN_ELF = "Javelin Elf"
MEMBER_HEALER = "Healer"
MEMBER_ROGUE = "Rogue"
MEMBER_KNIGHT = "Knight"
MEMBER_DUNGEON_EXPLORER = "Dungeon Explorer"
MEMBER_GUARDIAN = "Guardian"
MEMBER_NOBLE = "Noble"
MEMBER_YAWNING_CAT = "Yawning Cat"
MEMBER_FAIRY_SEER = "Fairy Seer"
MEMBER_IRIS = "Iris"
MEMBERS_BLOCKED_BY_BARRIERS = frozenset({MEMBER_FAIRY_SEER, MEMBER_HEALER, MEMBER_JESTER})
CAT_EXPLORE_INTERVAL = 20
CAT_EXPLORE_SIZE = 2
CAT_EXPLORE_RADIUS = 10  # Vertical radius, tuned independently of Vortex.

PARTY_LIMIT = 2
# Iris carries one ration; while she is in the party and LP drops to 0 or
# below, it sets LP to this value. Entering a bridgehead with her refills it.
IRIS_RATION_LP = 30
MEMBER_STAGE_JESTER_EXP_MULTIPLIER = 1.5
KNIGHT_INITIAL_LEVEL = 40
JESTER_DEPARTURE_LEVEL = 100
HEALER_MOVE_COST = 0.75
HEALER_RESPAWN_COST = 3
RECRUITABLE_MEMBER_ROLES = (
    MEMBER_JESTER, MEMBER_HEALER, MEMBER_ROGUE, MEMBER_KNIGHT,
    MEMBER_DUNGEON_EXPLORER, MEMBER_GUARDIAN, MEMBER_YAWNING_CAT, MEMBER_FAIRY_SEER,
    MEMBER_IRIS,
)
MEMBER_GLYPHS = {
    MEMBER_JESTER: "J", MEMBER_HEALER: "H", MEMBER_ROGUE: "R",
    MEMBER_KNIGHT: "K", MEMBER_DUNGEON_EXPLORER: "D", MEMBER_GUARDIAN: "G", MEMBER_NOBLE: "N",
    MEMBER_YAWNING_CAT: "Y",
    MEMBER_FAIRY_SEER: "S",
    MEMBER_IRIS: "I",
}
# Stages that feature elves and share the multi-floor progress state.
ELF_STAGES = frozenset({3, 4})
CORRIDOR_V_WIDTH: int = 3
CORRIDOR_H_WIDTH: int = 2
CHAR_WALL: str = "#"
# Internal identity only; renderers show this as the ordinary wall glyph.
CHAR_GOLEM_WALL: str = "G"
WALL_CHARS: tuple[str, str] = (CHAR_WALL, CHAR_GOLEM_WALL)
CHAR_FLOOR: str = " "
CHAR_STAIRS_UP: str = "^"
CHAR_STAIRS_DOWN: str = "v"
# Hidden terrain markers are rendered as ordinary floor or wall until found.
CHAR_HIDDEN_STAIRS_UP: str = "u"
CHAR_HIDDEN_STAIRS_DOWN: str = "w"
# A pit landing is always floor-like; D can climb when the pit above is open.
CHAR_PIT_LANDING: str = "j"
CHAR_SCHOLAR_STAIRS_UP: str = "↑"
CHAR_SCHOLAR_STAIRS_DOWN: str = "↓"
CHAR_HIDDEN_D_GATE: str = "|"
CHAR_D_GATE: str = "."
HIDDEN_STAIRS_CHARS: tuple[str, ...] = (
    CHAR_HIDDEN_STAIRS_UP,
    CHAR_HIDDEN_STAIRS_DOWN,
    CHAR_PIT_LANDING,
)
HIDDEN_PASSAGE_CHARS: tuple[str, str] = (CHAR_HIDDEN_D_GATE, CHAR_D_GATE)
SCHOLAR_STAIR_CHARS: tuple[str, str] = (
    CHAR_SCHOLAR_STAIRS_UP,
    CHAR_SCHOLAR_STAIRS_DOWN,
)
STAIR_CHARS: tuple[str, ...] = (
    CHAR_STAIRS_UP,
    CHAR_STAIRS_DOWN,
    *SCHOLAR_STAIR_CHARS,
)
CHAR_COLLAPSE: str = "O"
# Decorations kept beside the field (Floor.decor): no rule reads them; only
# the sprite GUI draws them.
DECOR_NONE: str = ""
DECOR_BRIDGEHEAD_PREFIX: str = "bridgehead:"
DECOR_FALLEN_ROCKS: str = "fallen rocks"  # below a pit on the floor above
DECOR_BOSS_ROUTE: str = "boss route"
DECOR_BOSS_ROUTE_FALLEN_ROCKS: str = "boss route and fallen rocks"
DECOR_OUTER_WALL: str = "outer wall"
DECOR_BURIED_WALL: str = "buried wall"

TORCH_RADIUS: int = 3
FOV_WIDTH_EXPANSION_RATIO: float = 1.4
OCULAR_TORCH_EXTENSION: int = 3
ELLIPSE_CELL_EDGE_THRESHOLD: float = 0.65
VORTEX_FLOOR_DIAMETER_RATIO: float = 0.7

LP_MAX: int = 100
LP_MAX_LIFEBRINGER: int = 120
LIFEBRINGER_LP_MAX_INCREASE: int = 5
BISON_LP_OVERCHARGE: int = 5
LP_OVERCHARGE_MAX: int = 120
BRIDGEHEAD_RECOVERY_LP: int = 60
LP_INIT: int = LP_OVERCHARGE_MAX
LP_RESPAWN_MIN: int = 20
LP_RESPAWN_COST: int = 6
LP_WARNING_THRESHOLD: int = 40
LP_LOW_THRESHOLD: int = 20  # LP bar/player "@" turn red at or below this

MONSTER_RESPAWN_INTERVAL: int = 65
# Turns a respawned monster (not an elf) stands in the sprite GUI's light
# column (the player's lasts until its next move).
RESPAWN_GLOW_TURNS: int = 3
MARKSMAN_RESPAWN_INTERVAL: int = 3 * MONSTER_RESPAWN_INTERVAL
SWORD_USES: int = 3
CURSED_SWORD_LP_COST: int = 10
NO_RESPAWN_MONSTERS = {"a", "A", "b", "B", "c", "C"}
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
SYLVAN_FAIRY_DURATION_MULTIPLIER: float = 1.25
LOOP_TURNS = 80
LOOP_TRAIL_TURNS = 10
MARKSMAN_ARROW_LIMIT = 20
MARKSMAN_COOLDOWN_TURNS = 2
# Order of the elf-stage status-line marks. The stage boss and treasure "T"
# are added separately.
ELF_STAGE_PROGRESS: list[tuple[str, int]] = [
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

PEGASUS_STEP_X: int = 9
PEGASUS_STEP_Y: int = 4

CALTROP_SPREAD_RADIUS: int = 3
CALTROP_WIDTH_EXPANSION_RATIO: float = 1.0
CALTROP_LP_DAMAGE: int = 3
MARKSMAN_LP_DAMAGE: int = 4
IVY_LP_DAMAGE: int = 4
BARRIER_LP_DAMAGE: int = 30
GUARDIAN_BARRIER_LP_DAMAGE: int = 5

ROCK_SPREAD_OFFSETS: list[tuple[int, int]] = [
    (-2, -2),
    (2, -2),
    (-1, -1),
    (1, -1),
    (-1, 1),
    (1, 1),
    (-2, 2),
    (2, 2),
]


CHAR_TREASURE: str = "T"
CHAR_DUNGEON_CORE: str = "*"
CHAR_CALTROP: str = "x"
CHAR_BARRIER: str = "="

Point = tuple[int, int]
Edge = tuple[Point, Point]

COLLAPSE_FOOTPRINT_OFFSETS: tuple[Point, ...] = (
    (0, 0),
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
)


DUNGEON_CORE_GROWTHS: tuple[str, ...] = ("small", "medium", "large", "huge")


def dungeon_core_growth(turn: int) -> str:
    """How far the Stage 6 Dungeon Core has grown at `turn`, one stage every
    STAGE6_CORE_GROWTH_TURNS, staying at the last."""
    stage = min(max(turn, 0) // STAGE6_CORE_GROWTH_TURNS, len(DUNGEON_CORE_GROWTHS) - 1)
    return DUNGEON_CORE_GROWTHS[stage]


def collapse_footprint(center: Point) -> set[Point]:
    x, y = center
    return {(x + dx, y + dy) for dx, dy in COLLAPSE_FOOTPRINT_OFFSETS}


def collapse_placement_cells_valid(
    point: Point, *fields: Sequence[Sequence[str]]
) -> bool:
    """Check the footprint and ensure every possible landing is floor."""
    if not fields:
        return False
    for field in fields:
        height = len(field)
        width = len(field[0]) if field else 0
        for x, y in collapse_footprint(point):
            if not (0 <= x < width and 0 <= y < height):
                return False
            if field[y][x] not in (
                CHAR_FLOOR,
                *WALL_CHARS,
                *HIDDEN_PASSAGE_CHARS,
            ):
                return False
    if len(fields) >= 2:
        upper, lower = fields[:2]
        for x, y in collapse_footprint(point):
            if upper[y][x] == CHAR_FLOOR and lower[y][x] != CHAR_FLOOR:
                return False
    return True


_entity_uids = count()


class Entity:
    """Base class for entities in the game that have x and y coordinates."""

    def __init__(self, x, y):
        self.uid = next(_entity_uids)
        self.x = x
        self.y = y


class Treasure(Entity):
    """A chest whose unlock state is part of the chest instance."""

    def __init__(self, x, y, encounter_type, unlock_key: Optional[str] = None,
                 boss_id: Optional[int] = None):
        super().__init__(x, y)
        self.encounter_type = encounter_type
        self.unlock_key = unlock_key or encounter_type
        self.boss_id = boss_id
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
        experience: Base experience awarded on defeat.
        item: Item that can be dropped.
        effect: Additional effect (exclusive with fairy).
        passive: Reveal on contact without combat, removal, or respawn.
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
        passive: bool = False,
        experience: int = 1,
    ):
        super().__init__(char, event_message, event_message_importance)
        self.level: int = level
        self.feed: int = feed
        self.experience: int = experience
        self.item: Optional[str] = item
        self.effect: Optional[str] = effect
        self.is_elf: bool = is_elf
        self.passive: bool = passive
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


class FairyTribe(Tribe):
    """
    Class representing fairy tribes in the game.

    Attributes:
        durability: Durability of the fairy.
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


class Fairy(Entity):
    """
    Class representing fairies in the game.

    Attributes:
        tribe: Tribe information of the fairy (FairyTribe instance).
        origin_floor: (multi-floor stages) index of the floor this fairy was
            spawned on, used to respawn it there after it is carried to
            another floor and expires.
    """

    def __init__(self, x, y, tribe: FairyTribe, origin_floor: Optional[int] = None):
        super().__init__(x, y)
        self.tribe: FairyTribe = tribe
        # Per-instance effective lifetime; bonuses must not change the
        # tribe's shared base durability.
        self.durability: int = tribe.durability
        self.origin_floor: Optional[int] = origin_floor
        self.revealed: bool = False


class PartyMember(Entity):
    """A permanent recruit, separate from the temporary fairy slot."""

    def __init__(
        self, x: int, y: int, role: str, origin_floor: Optional[int] = None
    ):
        super().__init__(x, y)
        self.role = role
        self.exploration_turns = 0
        self.origin_floor = origin_floor
        self.level: float = KNIGHT_INITIAL_LEVEL if role == MEMBER_KNIGHT else 0
        self.has_ration: bool = role == MEMBER_IRIS


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
        boss_id: Optional[int] = None,
    ):
        super().__init__(x, y)
        self.tribe: MonsterTribe = tribe
        if empowered < 1:
            raise ValueError("empowered must be positive")
        self.empowered: int = empowered
        # Mimics are identified by the boss whose treasure they imitate.
        self.mimic_boss_char: Optional[str] = mimic_boss_char
        self.mimic_boss_empowered: Optional[int] = mimic_boss_empowered
        self.boss_id: Optional[int] = boss_id
        self.revealed: bool = False
        self.met: bool = False
        self.active: bool = True
        self.arrow_marks: list[tuple[Point, str]] = []
        self.marksman_cooldown: int = 0
        self.marksman_shots_fired: int = 0


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
        fairy: (Optional) Fairy associated with the player (Fairy instance).
        karma: Karma value.
    """

    def __init__(
        self, x: int, y: int, level: float, lp: float, fairy: Optional[Fairy] = None
    ):
        super().__init__(x, y)
        self.level: float = level
        self.lp: float = lp
        self.item: Optional[str] = None
        self.item_uses: int = 0
        self.item_taken_from: Optional[str] = None
        self.fairy: Optional[Fairy] = fairy
        self.karma: int = 0
        self.boss_defeated: bool = False
        self.dungeon_core_destroyed: bool = False
        self.treasure_collected: bool = False
        # Identified monster types are known across all floors.
        self.known_monsters: set[str] = set(INITIALLY_KNOWN_MONSTERS)
        # Floors where the Cursed Chimera has been identified or defeated us.
        self.known_c_floors: set[int] = set()
        self.elf_stage_floors: dict[str, int] = {}
        self.known_elf_floors: set[str] = set()
        self.known_member_floors: dict[str, int] = {}
        self.joined_members: set[str] = set()
        self.seen_members: set[str] = set()
        # Shared progress for the elf stages, including Stage 3's W flag.
        self.elf_stage_flags: int = 0
        self.lifebringer_lp_max: int = LP_MAX
        self.current_floor: int = 0
        self.just_climbed_pit: bool = False
        # The cell the player last left a floor from (stairs or pit), for the UI.
        self.last_member_scatter_route: Optional[tuple[tuple[int, Point], ...]] = None
        self.members: list[PartyMember] = []
        self.facing: Point = (0, -1)
        self.rescue_stage = False
        self.treasure_stage = False
        self.noble_returned = False
        # (floor, x, y) of the monster involved in the most recent monster
        # contact (win, loss, or a no-combat gatekeeper like High Elf), or
        # None. Losing combat against the same (floor, x, y) twice in a row,
        # with no other monster contact in between, means that monster is
        # blocking the only way through a bridge corridor; see the escape
        # branch in game_engine._resolve_monster_contact().
        self.last_contact_monster: Optional[tuple[int, int, int]] = None
        self.last_encounter_party: str = ""
        self.status_popup: Optional[str] = None
        self.status_popup_tone: str = "default"
        self.status_popup_ticks: int = 0
        self.marksman_damage_prevented: bool = False
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
        if self.rescue_stage and not self.treasure_stage:
            return self.noble_returned
        return self.boss_defeated and self.treasure_collected


class SpawnConfig:
    """
    Holds the spawn configuration for a monster or fairy tribe.

    Attributes:
        tribe: The Tribe object.
        population: Number of monsters/fairies to spawn or a probability (if float).
    """

    def __init__(self, tribe: Tribe, population: Union[float, int], empowered: int = 1):
        self.tribe = tribe
        self.population = population
        self.empowered = empowered


_MT = MonsterTribe
_ET = ElfTribe
_CT = FairyTribe

MIN_FOOD = 8

MONSTER_TRIBES: list[MonsterTribe] = [
    _MT("a", 1, 10),  # Amoeba
    _MT(
        "A", 2, MIN_FOOD, effect=EFFECT_SPECIAL_EXP, event_message="-- Level boosted!", experience=10
    ),  # Amoeba rare
    _MT("b", 5, 60, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    _MT("B", 8, 90, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Buffalo
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
    _MT("f", 25, MIN_FOOD, experience=5),  # Stage 6's early-game challenge
    _MT(
        "E",
        30,
        MIN_FOOD,
        effect=EFFECT_LEVEL_REDUCE,
        experience=0,
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
            "-- The Sylvan Elf gave you fairy nectar! Fairies will stay with you longer."
        ),
        event_message_importance=7,
    ),
    _MT("i", 50, MIN_FOOD),  # Ivy
    _MT("k", 80, MIN_FOOD, experience=3),  # Marksman
    _MT(
        "M",
        1,
        1,
        event_message="-- You defeated the Mimic, but were sent somewhere else.",
    ),  # Mimic
    _MT(CHAR_DUNGEON_CORE, 1, 0, experience=0),  # Stage 6's stationary objective
    _MT(
        "m",
        5,
        MIN_FOOD,
        item=ITEM_SPORES,
        event_message="-- Spores cloud your vision!",
    ),
    _MT("w", 50, MIN_FOOD, experience=5),
    _MT(
        "W",
        150,
        MIN_FOOD,
        experience=5,
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

FAIRY_TRIBES: list[FairyTribe] = [
    _CT(
        "l"
    ),  # Looping fairy; contact always rewinds via _rewind, so no event_message here
    _CT("n", 10, event_message="-- Nomicon joined!", event_message_importance=3),
    _CT("o", 20, event_message="-- Ocular joined!", event_message_importance=3),
    _CT(
        CHAR_PEGASUS,
        5,
        event_message="-- Pegasus joined!",
        event_message_importance=3,
    ),
]

CHAR_TO_TRIBE: dict[str, Tribe] = {
    mt.char: mt for mt in MONSTER_TRIBES + FAIRY_TRIBES
}
CHAR_TO_MONSTER_TRIBE: dict[str, MonsterTribe] = {mt.char: mt for mt in MONSTER_TRIBES}
CHAR_TO_FAIRY_TRIBE: dict[str, FairyTribe] = {
    mt.char: mt for mt in FAIRY_TRIBES
}

HIGH_ELF_DECOY, SPAWN_CONFIGS_ST1, SPAWN_CONFIGS_ST2, STAGE_TO_SPAWN_CONFIGS = (
    make_spawn_configs(CHAR_TO_TRIBE, SpawnConfig, MonsterTribe)
)


def decode_stage_roster_entry(
    roster_char: str, empowered: int
) -> tuple[str, int, Optional[str], int]:
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


def _get_stage_roster_tribes(roster: list[list[tuple[str, int, int]]]):
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


STAGE3_ROSTER_TRIBES: list[MonsterTribe] = sorted(
    [*_get_stage_roster_tribes(STAGE3_ROSTER), CHAR_TO_MONSTER_TRIBE["C"]],
    key=lambda tribe: tribe.level,
    reverse=True,
)
# Collapse is a fixed stage object, but appears at level 1 on the strength gauge.
STAGE4_ROSTER_TRIBES: list[MonsterTribe] = sorted(
    [
        *_get_stage_roster_tribes(STAGE4_ROSTER),
        CHAR_TO_MONSTER_TRIBE["C"],
        MonsterTribe(CHAR_COLLAPSE, level=1, feed=0),
    ],
    key=lambda tribe: tribe.level,
    reverse=True,
)


def _get_member_stage_roster_tribes() -> list[MonsterTribe]:
    variants = {
        (char, rank)
        for floor in STAGE6_ROSTER
        for char, _, rank, _ in floor
    }
    variants.update(
        variant for floor_pool in STAGE6_SUPPORT_POOLS for variant in floor_pool
    )
    variants.update(STAGE6_BOSS_PARTY)
    variants.update((char, rank) for floor in STAGE6_FIXED_MONSTERS for char, rank, _ in floor)
    variants.update(STAGE6_BOSS_ESCORTS)
    variants.add(("M", 1))
    return sorted(
        (
            _empowered_strength_tribe(char, rank)
            for char, rank in variants
        ),
        key=lambda tribe: tribe.level,
        reverse=True,
    )


MEMBER_STAGE_ROSTER_TRIBES: list[MonsterTribe] = _get_member_stage_roster_tribes()


def _javelin_follower_active(player: Player) -> bool:
    return has_member(player, MEMBER_JAVELIN_ELF)


def player_lp_max(player: Player) -> int:
    """Return the player's permanent LP maximum, including Lifebringer's bonus."""
    return min(player.lifebringer_lp_max, LP_MAX_LIFEBRINGER)


def apply_feed(player: Player, feed: int, lp_overcharge: int = 0) -> None:
    # Preserve temporary LP above the permanent cap until it is spent. Feeding
    # cannot refill the overcharge once LP has risen above that cap.
    cap = min(
        LP_OVERCHARGE_MAX,
        max(player_lp_max(player) + lp_overcharge, player.lp),
    )
    player.lp = max(1, min(cap, player.lp + feed))


def apply_respawn_penalty(player: Player) -> None:
    player.lp -= HEALER_RESPAWN_COST if has_member(player, MEMBER_HEALER) else LP_RESPAWN_COST
    player.lp = max(LP_RESPAWN_MIN, player.lp)


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


def grant_defeat_level(player: Player, tribe: MonsterTribe) -> None:
    if tribe.effect == EFFECT_LEVEL_REDUCE:
        player.level = max(1, player.level * 2 // 3)
    else:
        player.level += tribe.experience


def has_member(player: Player, role: str) -> bool:
    return any(member.role == role for member in player.members)


def experience_multiplier(player: Player) -> float:
    if not has_member(player, MEMBER_JESTER):
        return 1
    return MEMBER_STAGE_JESTER_EXP_MULTIPLIER


def movement_lp_cost(player: Player) -> float:
    return HEALER_MOVE_COST if has_member(player, MEMBER_HEALER) else 1


def current_player_attack(player: Player) -> float:
    """
    Player's current attack power: level and equipped item, plus permanent
    bonuses from the Collector's flag and the Javelin Elf follower. Bonuses
    apply in every stage, and this shared calculation keeps combat and display
    consistent. An accompanying Knight's level is added after equipment
    and bonuses have been applied to the player's attack.
    """
    knight_level = next(
        (member.level for member in player.members if member.role == MEMBER_KNIGHT),
        0,
    )
    if player.rescue_stage:
        value = player.level
        if player.item == ITEM_SWORD_X1_5:
            value *= 1.5
        elif player.item == ITEM_SWORD_CURSED:
            value *= 3
        elif player.item == ITEM_POISONED:
            value = ceil(value / 3)
        return value + knight_level
    if player.item == ITEM_SWORD_X1_5:
        value = player.level * 3 // 2
    elif player.item == ITEM_SWORD_CURSED:
        value = player.level * 3
    elif player.item == ITEM_POISONED:
        value = (player.level + 2) // 3
    else:
        value = player.level

    if player.elf_stage_flags & ELF_STAGE_K_FLAG:
        value = (value * 6 + 1) // 5
    if _javelin_follower_active(player):
        value = (value * 5 + 2) // 4
    return value + knight_level


def get_stage_roster_tribes(stage_num: int) -> list[MonsterTribe]:
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



COMBAT_EFFECT_SECONDS = 0.3
# The sprite GUI's still between floors (stairs and pits), set in Settings;
# 0 skips it.
FLOOR_TRANSITION_SECONDS = 0.5
FLOOR_TRANSITION_SECONDS_CHOICES = tuple(n / 10 for n in range(11))
# The sprite GUI's hop of characters in view while waiting for input, set in
# Settings.
IDLE_BOB_ENABLED = True
# The sprite GUI's glide of the player (and the field's scroll) into each
# one-cell step, set in Settings.
MOVE_GLIDE_ENABLED = True
COMBAT_EFFECT_SECONDS_CHOICES = tuple(n / 10 for n in range(6))
