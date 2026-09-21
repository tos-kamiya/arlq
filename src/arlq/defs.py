from typing import Dict, List, NamedTuple, Optional, Set, Tuple, Union

TILE_WIDTH: int = 12
TILE_HEIGHT: int = 6
TILE_NUM_X: int = 6
TILE_NUM_Y: int = 3
FIELD_WIDTH: int = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT: int = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
# Stage 1 is a smaller, introductory map: it walls off this many tile
# columns on each of the left and right edges (6 -> 4 wide), leaving
# TILE_NUM_Y unchanged.
STAGE1_COLUMN_MARGIN: int = 1
CORRIDOR_V_WIDTH: int = 3
CORRIDOR_H_WIDTH: int = 2
WALL_CHAR: str = "#"

TORCH_RADIUS: int = 3
TORCH_WIDTH_EXPANSION_RATIO: float = 1.7
FOV_WIDTH_EXPANSION_RATIO: float = 1.4
OCULAR_TORCH_EXTENSION: int = 3

LP_MAX: int = 100
LP_INIT: int = 90
LP_RESPAWN_MIN: int = 20
LP_RESPAWN_COST: int = 6
LP_LOW_THRESHOLD: int = 20  # LP bar/player "@" turn red at or below this

MONSTER_RESPAWN_INTERVAL: int = 65
SWORD_USES: int = 3
NO_RESPAWN_MONSTERS = {"a", "A", "b", "c", "C"}
# W and w stay down for the rest of a Stage 3 run.
STAGE3_NO_RESPAWN_MONSTERS = NO_RESPAWN_MONSTERS | {"W", "w"}
STAGE3_C_FLAG: int = 1
STAGE3_I_FLAG: int = 2
STAGE3_K_FLAG: int = 4
STAGE3_H_FLAG: int = 8
STAGE3_W_FLAG: int = 16
STAGE3_J_FLAG: int = 64
# Order of the Stage 3 status-line marks. The treasure mark "T" is added separately.
STAGE3_PROGRESS: List[Tuple[str, int]] = [
    ("C", STAGE3_C_FLAG),
    ("I", STAGE3_I_FLAG),
    ("J", STAGE3_J_FLAG),
    ("K", STAGE3_K_FLAG),
    ("H", STAGE3_H_FLAG),
    ("W", STAGE3_W_FLAG),
]

ITEM_SWORD_X1_5: str = "Sword"
ITEM_SWORD_CURSED: str = "Cursed Sword"
ITEM_POISONED: str = "Poisoned"
ITEM_TREASURE: str = "Treasure"

EFFECT_SPECIAL_EXP: str = "Special Exp."
EFFECT_FEED_MUCH: str = "Feed Much"
EFFECT_UNLOCK_TREASURE: str = "Unlock Treasure"
EFFECT_ENERGY_DRAIN: str = "Energy Drain"
EFFECT_CALTROP_SPREAD: str = "Caltrop Spread"
EFFECT_ROCK_SPREAD: str = "Rock Spread"
EFFECT_GOT_TREASURE: str = "Got Treasure"

PEGASUS_STEP_X: int = 9
PEGASUS_STEP_Y: int = 4

CALTROP_SPREAD_RADIUS: int = 3
CALTROP_WIDTH_EXPANSION_RATIO: float = 1.7
CALTROP_LP_DAMAGE: int = 3
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
CHAR_TREASURE: str = "T"
CHAR_CALTROP: str = "x"
CHAR_BARRIER: str = "="

Point = Tuple[int, int]
Edge = Tuple[Point, Point]


class Entity:
    """Base class for entities in the game that have x and y coordinates."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    """Entity that inherits from the Treasure class."""

    def __init__(self, x, y, encounter_type, unlock_key: Optional[str] = None):
        super().__init__(x, y)
        self.encounter_type = encounter_type
        self.unlock_key = unlock_key or encounter_type


class Tribe:
    """
    Base class for tribes in the game.

    Attributes:
        char: Character representation of the tribe.
        event_message: Event message specific to the tribe.
    """

    def __init__(self, char: str, event_message: Optional[str]):
        self.char: str = char
        self.event_message: Optional[str] = event_message


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
        treasure_key: Optional[str] = None,
        is_elf: bool = False,
    ):
        super().__init__(char, event_message)
        self.level: int = level
        self.feed: int = feed
        self.item: Optional[str] = item
        self.effect: Optional[str] = effect
        self.treasure_key: Optional[str] = treasure_key
        self.is_elf: bool = is_elf


class CompanionTribe(Tribe):
    """
    Class representing companion tribes in the game.

    Attributes:
        durability: Durability of the companion.
    """

    def __init__(self, char: str, durability: int = 1, event_message: Optional[str] = None):
        super().__init__(char, event_message)
        self.durability: int = durability


class Companion(Entity):
    """
    Class representing companions in the game.

    Attributes:
        tribe: Tribe information of the companion (CompanionTribe instance).
        origin_floor: (Stage 3 only) index of the floor this companion was
            spawned on, used to respawn it there after it is carried to
            another floor and expires.
    """

    def __init__(self, x, y, tribe: CompanionTribe, origin_floor: Optional[int] = None):
        super().__init__(x, y)
        self.tribe: CompanionTribe = tribe
        self.origin_floor: Optional[int] = origin_floor


class Monster(Entity):
    """
    Class representing monster entities in the game.

    Attributes:
        tribe: Tribe information of the monster (MonsterTribe instance).
        empowered: Level multiplier for an enhanced monster instance.
    """

    def __init__(self, x: int, y: int, tribe: MonsterTribe, empowered: int = 1):
        super().__init__(x, y)
        self.tribe: MonsterTribe = tribe
        if empowered < 1:
            raise ValueError("empowered must be positive")
        self.empowered: int = empowered


def monster_level(monster: Monster) -> int:
    return monster.tribe.level * (1 if monster.empowered == 1 else 3)


def monster_type_key(monster: Monster) -> str:
    return monster.tribe.char if monster.empowered == 1 else f"{monster.tribe.char}{monster.empowered}"


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

    def __init__(self, x: int, y: int, level: int, lp: int, companion: Optional[Companion] = None):
        super().__init__(x, y)
        self.level: int = level
        self.lp: int = lp
        self.item: Optional[str] = None
        self.item_uses: int = 0
        self.item_taken_from: Optional[str] = None
        self.companion: Optional[Companion] = companion
        self.karma: int = 0
        # Monster identities are known globally across all floors and stages.
        self.known_monsters: Set[str] = set()
        # Stages 1 and 2 have one floor, while Stage 3 keeps this per floor.
        self.known_companions: Set[str] = set()
        self.unlocked_treasures: Set[str] = set()
        self.stage3_met_elves: Set[str] = set()
        self.stage3_elf_floors: Dict[str, int] = {}
        # Stage 3 state. Keeping these on Player preserves the small shared
        # entity model used by both frontends.
        self.stage3_flags: int = 0
        self.stage3_spores: bool = False
        self.stage3_treasure_collected: bool = False
        self.stage3_won: bool = False
        self.stage3_floor: int = 0
        self.persistent_followers: List[Tuple[int, int, int, str]] = []
        # (floor, x, y) of the monster involved in the most recent monster
        # contact (win, loss, or a no-combat gatekeeper like High Elf), or
        # None. Losing combat against the same (floor, x, y) twice in a row,
        # with no other monster contact in between, means that monster is
        # blocking the only way through a bridge corridor; see the escape
        # branch in update_entities()/_resolve_monster_contact().
        self.last_contact_monster: Optional[Tuple[int, int, int]] = None
        # Whether the player has already been turned away by an unrecognized
        # High Elf at least once (Stage 2's gatekeeper, or Stage 3's before
        # meeting two of I/J/K). The first refusal only shows a message; any
        # later refusal sends the player elsewhere, like repeat contact with
        # the Isolated Elf.
        self.high_elf_refused: bool = False
        # Same idea as high_elf_refused, but for Stage 3's Collector Elf (K)
        # before the player has the cursed sword.
        self.k_elf_refused: bool = False


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
_CT = CompanionTribe

MIN_FOOD = 8

MONSTER_TRIBES: List[MonsterTribe] = [
    _MT("a", 1, 10),  # Amoeba
    _MT("A", 2, MIN_FOOD, effect=EFFECT_SPECIAL_EXP, event_message="-- Level boosted!"),  # Amoeba rare
    _MT("b", 5, 60, effect=EFFECT_FEED_MUCH, event_message="-- Stuffed!"),  # Bison
    _MT("c", 10, MIN_FOOD, item=ITEM_SWORD_X1_5, event_message="-- Got a sword (c)!"),  # Chimera
    _MT("C", 15, MIN_FOOD, item=ITEM_SWORD_CURSED, event_message="-- Got a cursed sword (C)!"),  # Chimera rare
    _MT("d", 20, 60, item=ITEM_POISONED),  # Comodo Dragon
    _MT(
        CHAR_DRAGON,
        35,
        MIN_FOOD,
        effect=EFFECT_UNLOCK_TREASURE,
        event_message="-- Unlocked the Dragon's treasure chest!",
        treasure_key=CHAR_TREASURE + CHAR_DRAGON,
    ),  # Dragon
    _MT("e", 1, -5, effect=EFFECT_ENERGY_DRAIN, event_message="-- Your energy was drained!"),  # Erebus
    _MT(
        CHAR_FIRE_DRAKE,
        60,
        MIN_FOOD,
        effect=EFFECT_UNLOCK_TREASURE,
        event_message="-- Unlocked the Fire Drake's treasure chest!",
        treasure_key=CHAR_TREASURE + CHAR_FIRE_DRAKE,
    ),  # Fire Drake
    _MT("f", 50, MIN_FOOD),  # Fire Lizard
    _MT("g", 30, 0, effect=EFFECT_ROCK_SPREAD),  # Golem
    _MT("X", 1, MIN_FOOD, effect=EFFECT_CALTROP_SPREAD, event_message="-- Caltrops were scattered!"),  # Caltrop Plant
    _MT("I", 0, 0, event_message="-- The Isolated Elf told you about the history of the elves.", is_elf=True),
    _MT("J", 0, 0, event_message="-- The Javelin Elf joined your hunt for the Dread Wyrm!", is_elf=True),
    _MT("K", 0, 0, event_message="-- The Collector Elf (K) gave you a rustless blade for your Cursed Sword!", is_elf=True),
    _MT("H", 0, 0, event_message="-- The High Elf bestowed the talisman upon you!", is_elf=True),
    _MT("m", 5, MIN_FOOD, event_message="-- Spores cloud your vision!"),
    _MT("w", 50, MIN_FOOD),
    _MT("W", 150, MIN_FOOD, event_message=">> Dread Wyrm (W) defeated! <<", treasure_key=CHAR_TREASURE + "W"),
]

COMPANION_TRIBES: List[CompanionTribe] = [
    _CT("l"),  # Looping companion; contact always rewinds via _rewind_to_history, so no event_message here
    _CT("n", 10, event_message="-- Nomicon joined!"),  # Nomicon
    _CT("o", 20, event_message="-- Ocular joined!"),  # Ocular
    _CT("p", 5, event_message="-- Pegasus joined!"),  # Pegasus
]

CHAR_TO_TRIBE: Dict[str, Tribe] = {mt.char: mt for mt in MONSTER_TRIBES + COMPANION_TRIBES}
CHAR_TO_MONSTER_TRIBE: Dict[str, MonsterTribe] = {mt.char: mt for mt in MONSTER_TRIBES}
CHAR_TO_COMPANION_TRIBE: Dict[str, CompanionTribe] = {mt.char: mt for mt in COMPANION_TRIBES}

_SC = SpawnConfig

# Stage 1 spawn configurations.
SPAWN_CONFIGS_ST1 = [
    _SC(CHAR_TO_TRIBE["a"], 10),
    _SC(CHAR_TO_TRIBE["A"], 2),
    _SC(CHAR_TO_TRIBE["b"], 7),
    _SC(CHAR_TO_TRIBE["c"], 1),
    _SC(CHAR_TO_TRIBE["d"], 2),
    _SC(CHAR_TO_TRIBE[CHAR_DRAGON], 1),
    _SC(CHAR_TO_TRIBE["n"], 0.7),
    _SC(CHAR_TO_TRIBE["o"], 0.7),
]

# Stage 2 spawn configurations.
SPAWN_CONFIGS_ST2 = [
    _SC(CHAR_TO_TRIBE["a"], 20),
    _SC(CHAR_TO_TRIBE["A"], 2),
    _SC(CHAR_TO_TRIBE["b"], 3),
    _SC(CHAR_TO_TRIBE["b"], 3, empowered=2),
    _SC(CHAR_TO_TRIBE["c"], 2),
    _SC(CHAR_TO_TRIBE["C"], 1),
    _SC(CHAR_TO_TRIBE["d"], 6),
    _SC(CHAR_TO_TRIBE[CHAR_FIRE_DRAKE], 1),
    _SC(CHAR_TO_TRIBE["e"], 1),
    _SC(CHAR_TO_TRIBE["g"], 1),
    _SC(CHAR_TO_TRIBE["H"], 1),
    _SC(CHAR_TO_TRIBE["X"], 1),
    _SC(CHAR_TO_TRIBE["n"], 0.7),
    _SC(CHAR_TO_TRIBE["o"], 0.7),
    _SC(CHAR_TO_TRIBE["p"], 0.7),
]

# Mapping stages to their corresponding spawn configurations.
STAGE_TO_SPAWN_CONFIGS = [
    SPAWN_CONFIGS_ST1,
    SPAWN_CONFIGS_ST2,
    [],  # Stage 3 uses its per-floor roster in stage3.py.
]


def _stage3_javelin_active(player: Player) -> bool:
    return any(follower[3] == "J" for follower in player.persistent_followers)


def apply_feed(player: Player, feed: int) -> None:
    # Feeding never drops LP below 1. Starvation is checked separately.
    player.lp = max(1, min(LP_MAX, player.lp + feed))


def apply_respawn_penalty(player: Player) -> None:
    player.lp -= LP_RESPAWN_COST
    player.lp = max(LP_RESPAWN_MIN, min(player.lp, LP_INIT))


def take_monster_item(
    player: Player,
    item: Optional[str],
    source: str,
    sword_uses: int = SWORD_USES,
) -> None:
    player.item = item
    player.item_taken_from = source
    player.item_uses = sword_uses if item in (ITEM_SWORD_X1_5, ITEM_SWORD_CURSED) else 0
    if item == ITEM_SWORD_CURSED:
        player.lp = (player.lp * 3 + 3) // 4


def grant_defeat_level(player: Player, effect: Optional[str]) -> None:
    player.level += 10 if effect == EFFECT_SPECIAL_EXP else 1


def current_player_attack(player: Player, stage_num: int = 0) -> int:
    """
    Player's current attack power: level and equipped item, plus Stage 3's
    elf/flag bonuses when playing Stage 3. This is the single place that
    combines those bonuses, so every caller (combat resolution, on-screen
    color coding, the strength ranking column) sees the same value.
    """
    if player.item == ITEM_SWORD_X1_5:
        value = player.level * 3 // 2
    elif player.item == ITEM_SWORD_CURSED:
        value = player.level * 3
    elif player.item == ITEM_POISONED:
        value = (player.level + 1) // 2
    else:
        value = player.level

    if stage_num == 3:
        if player.stage3_flags & STAGE3_K_FLAG:
            value = (value * 6 + 1) // 5
        if _stage3_javelin_active(player):
            value = (value * 5 + 2) // 4
    return value


def get_stage_roster_tribes(stage_num: int) -> List[MonsterTribe]:
    """Distinct, non-elf monster tribes that can appear in stage 1 or 2, strongest first."""
    configs = STAGE_TO_SPAWN_CONFIGS[stage_num - 1]
    chars = dict.fromkeys(
        sc.tribe.char for sc in configs if isinstance(sc.tribe, MonsterTribe) and not sc.tribe.is_elf
    )
    return sorted((CHAR_TO_MONSTER_TRIBE[c] for c in chars), key=lambda t: t.level, reverse=True)


def build_strength_column(
    tribes: List[MonsterTribe],
    player_attack: int,
    max_rows: int,
) -> List[Tuple[Optional[str], bool]]:
    """
    Lay out a stage's monster tribes and the player for the right-edge
    strength column, replacing the old ">X" beatable-monster indicator.

    The player is fixed near the vertical center with a blank row on each
    side. Tribes stronger than the player stack above it (strongest at the
    top, closest to the player at the bottom, right above the gap); tribes
    the player can beat (including a tie) stack below it (closest to the
    player at the top, right below the gap, weakest at the bottom). If a
    side has more tribes than fit, the ones closest to the player's
    strength are kept and the rest are dropped, leaving blank rows at that
    side's far end.

    Returns exactly `max_rows` (char, is_player) pairs, char is None for a
    blank row.
    """
    stronger = sorted((t for t in tribes if t.level > player_attack), key=lambda t: t.level, reverse=True)
    weaker = sorted((t for t in tribes if t.level <= player_attack), key=lambda t: t.level, reverse=True)

    center = max_rows // 2
    above_cap = max(center - 1, 0)
    below_cap = max(max_rows - center - 2, 0)

    kept_above = stronger[-above_cap:] if above_cap else []
    kept_below = weaker[:below_cap]

    above_column: List[Tuple[Optional[str], bool]] = [(None, False)] * (above_cap - len(kept_above))
    above_column += [(t.char, False) for t in kept_above]
    below_column: List[Tuple[Optional[str], bool]] = [(t.char, False) for t in kept_below]
    below_column += [(None, False)] * (below_cap - len(kept_below))

    return above_column + [(None, False), ("@", True), (None, False)] + below_column


def level_item_labels(player: Player, stage_num: int) -> Tuple[str, str]:
    """Level and item fragments shared by both status bars.

    Stage 3's K (x1.2) and J (+25%) suffixes apply only in that stage.
    x1.2 is omitted while a sword already replaces the base multiplier.
    """
    stage3 = stage_num == 3
    has_k = stage3 and bool(player.stage3_flags & STAGE3_K_FLAG)
    has_j = stage3 and _stage3_javelin_active(player)
    item = player.item
    if item == ITEM_SWORD_X1_5:
        level = f"LVL: {player.level} x1.5"
        item_str = f"+{item}({player.item_taken_from})"
    elif item == ITEM_SWORD_CURSED:
        level = f"LVL: {player.level} x3"
        item_str = f"+{item}({player.item_taken_from})"
    elif item == ITEM_POISONED:
        level = f"LVL: {player.level} /2"
        item_str = f"+{item}({player.item_taken_from})"
    else:
        level = f"LVL: {player.level}"
        item_str = ""
    if has_k and item not in (ITEM_SWORD_X1_5, ITEM_SWORD_CURSED):
        level += " x1.2"
    if has_j:
        level += " +25%"
    return level, item_str


def status_prefix(player: Player, stage_num: int, hours: int) -> str:
    """Text to the left of the LP readout, including the trailing spaces."""
    level_str, item_str = level_item_labels(player, stage_num)
    text = ""
    if stage_num == 3:
        text += f"ST: 3 F: {player.stage3_floor + 1}  "
    elif stage_num != 0:
        text += f"ST: {stage_num}  "
    text += f"HRS: {hours}  "
    text += level_str + "  "
    text += item_str + "  "
    return text


def stage3_progress_marks(player: Player) -> List[Tuple[str, bool]]:
    """Elf and treasure marks for the Stage 3 status line, in display order.

    Each entry is (label, achieved). With the Isolated Elf flag, an elf label
    gains the floor number recorded in ``stage3_elf_floors``.
    """
    show_floors = bool(player.stage3_flags & STAGE3_I_FLAG)
    marks: List[Tuple[str, bool]] = []
    for label, bit in STAGE3_PROGRESS:
        text = label
        if show_floors and label in player.stage3_elf_floors:
            text += str(player.stage3_elf_floors[label])
        marks.append((text, bool(player.stage3_flags & bit)))
    marks.append(("T", player.stage3_won))
    return marks


class FieldGlyph(NamedTuple):
    """One character to draw on the field.

    ``tone`` is a semantic name (``yellow``, ``blue``, ``red``, ``companion``,
    ``default``, ``black``, ``magenta``). Each frontend maps it. ``companion``
    is green in the GUI and the terminal's default color.
    """

    x: int
    y: int
    char: str
    tone: str
    bold: bool = False
    dim: bool = False


def player_appearance(player: Player) -> Tuple[str, Optional[str]]:
    """Foreground and background tones for '@'.

    Low LP is a red background. Poison is magenta text. Both at once use
    black text, because magenta on red is hard to read. Foreground
    ``default`` is the frontend's normal text color.
    """
    low = player.lp <= LP_LOW_THRESHOLD
    poisoned = player.item == ITEM_POISONED
    if low and poisoned:
        foreground = "black"
    elif poisoned:
        foreground = "magenta"
    else:
        foreground = "default"
    return foreground, ("red" if low else None)


def preview_entity_glyphs(entity: Entity) -> List[FieldGlyph]:
    """Dim glyphs for an entity when the whole map is revealed."""
    char = None
    if isinstance(entity, (Companion, Monster)):
        char = entity.tribe.char
    elif isinstance(entity, Treasure):
        char = CHAR_TREASURE
    if char is None:
        return []
    glyphs = [FieldGlyph(entity.x, entity.y, char, "default", dim=True)]
    if isinstance(entity, Monster) and entity.empowered > 1:
        glyphs.append(FieldGlyph(entity.x + 1, entity.y, "'", "default", dim=True))
    return glyphs


def revealed_entity_glyphs(
    entity: Entity,
    known_types: Set[str],
    show_entities: bool,
    player_attack: int,
    unlocked_treasures: Optional[Set[str]],
    dim_types: Optional[Set[str]],
) -> List[FieldGlyph]:
    """Glyphs for an entity inside the explored map.

    Empty when the entity stays hidden (an unknown monster while the whole
    map is already shown, or a treasure that is still locked).
    """
    if isinstance(entity, Companion):
        char = entity.tribe.char
        if char not in known_types and not show_entities:
            char = "!"
        return [FieldGlyph(entity.x, entity.y, char, "companion", bold=True)]
    if isinstance(entity, Monster):
        char = entity.tribe.char
        if monster_type_key(entity) not in known_types:
            if show_entities:
                return []
            return [FieldGlyph(entity.x, entity.y, "?", "yellow", bold=True)]
        if monster_level(entity) <= player_attack:
            tone = "yellow" if entity.tribe.effect == EFFECT_UNLOCK_TREASURE else "blue"
        else:
            tone = "red"
        dim = bool(dim_types and char in dim_types)
        glyphs = [FieldGlyph(entity.x, entity.y, char, tone, bold=True, dim=dim)]
        if entity.empowered > 1:
            glyphs.append(FieldGlyph(entity.x + 1, entity.y, "'", tone, bold=True, dim=dim))
        return glyphs
    if isinstance(entity, Treasure):
        if unlocked_treasures is not None and entity.unlock_key in unlocked_treasures:
            return [FieldGlyph(entity.x, entity.y, CHAR_TREASURE, "yellow", bold=True)]
    return []
