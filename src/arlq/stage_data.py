"""Stage layouts, rosters, and spawn configuration."""

from typing import Dict, List, Tuple

from .symbols import CHAR_DRAGON, CHAR_FIRE_DRAKE, CHAR_PEGASUS

Point = Tuple[int, int]
STAGE1_COLUMN_MARGIN: int = 1
STAGE2_BOSS_BARRIER_COUNT: int = 5


def make_spawn_configs(tribes, spawn_config, monster_tribe):
    """Build the first two stages' spawns from the shared tribe definitions."""
    # Stage 1 spawn configurations.
    # Stage 1 is a smaller, introductory map: it walls off this many tile
    # columns on each of the left and right edges (6 -> 4 wide), leaving
    # TILE_NUM_Y unchanged.
    SPAWN_CONFIGS_ST1 = [
        spawn_config(tribes["a"], 9),
        spawn_config(tribes["A"], 2),
        spawn_config(tribes["b"], 4),
        spawn_config(tribes["b"], 1),
        spawn_config(tribes["c"], 1),
        spawn_config(tribes["d"], 2),
        spawn_config(tribes[CHAR_DRAGON], 1),
        spawn_config(tribes["n"], 0.7),
        spawn_config(tribes["o"], 0.7),
    ]

    # Stage 2 spawn configurations.
    HIGH_ELF_DECOY = monster_tribe("H", level=0, feed=0, passive=True)
    SPAWN_CONFIGS_ST2 = [
        spawn_config(tribes["a"], 20),
        spawn_config(tribes["A"], 3),
        spawn_config(tribes["b"], 4),
        spawn_config(tribes["b"], 2, empowered=2),
        spawn_config(tribes["b"], 1),
        spawn_config(tribes["c"], 2),
        spawn_config(tribes["C"], 1),
        spawn_config(tribes["d"], 4),
        spawn_config(tribes[CHAR_FIRE_DRAKE], 1),
        spawn_config(tribes["e"], 1),
        spawn_config(tribes["g"], 1),
        spawn_config(HIGH_ELF_DECOY, 1),
        spawn_config(tribes["X"], 1),
        spawn_config(tribes["n"], 0.7),
        spawn_config(tribes["o"], 0.7),
        spawn_config(tribes[CHAR_PEGASUS], 0.7),
    ]

    # Mapping stages to their corresponding spawn configurations.
    STAGE_TO_SPAWN_CONFIGS = [
        SPAWN_CONFIGS_ST1,
        SPAWN_CONFIGS_ST2,
        [],  # Stage 3 uses its per-floor roster in game_engine.py.
        [],  # Stage 4 uses its per-floor roster in game_engine.py.
    ]
    return HIGH_ELF_DECOY, SPAWN_CONFIGS_ST1, SPAWN_CONFIGS_ST2, STAGE_TO_SPAWN_CONFIGS


# Per-floor rosters for the multi-floor stages. Each entry is
# (tribe character, population, empowered rank).
STAGE3_FLOOR_LAYOUT: List[Tuple[int, int]] = [(1, 0), (0, 0), (0, 0)]
STAGE3_STAIR_PAIRS_PER_TRANSITION = 1
STAGE3_ROSTER: List[List[Tuple[str, int, int]]] = [
    [
        ("a", 20, 1),
        ("A", 2, 1),
        ("b", 8, 1),
        ("b", 2, 1),
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
        ("b", 3, 1),
        ("b", 3, 2),
        ("b", 2, 1),
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
        ("b", 4, 2),
        ("b", 2, 1),
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

STAGE3_FLOORS = len(STAGE3_ROSTER)

STAGE4_FLOOR_LAYOUT: List[Tuple[int, int]] = [
    (1, 1),
    (0, 1),
    (0, 1),
    (0, 1),
    (0, 1),
]
# build() shuffles these counts across floors when no explicit layout is given.
STAGE4_FILLED_ROOM_COUNTS: Tuple[int, ...] = (0, 1, 1, 2, 3)
STAGE4_STAIR_PAIRS_PER_TRANSITION = 2
STAGE4_FINAL_FLOOR_BARRIER_PERCENT = 10
STAGE4_ROSTER: List[List[Tuple[str, int, int]]] = [
    [
        ("a", 20, 1),
        ("A", 1, 1),
        ("b", 8, 1),
        ("b", 2, 1),
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
        ("b", 3, 1),
        ("b", 3, 2),
        ("b", 2, 1),
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
        ("b", 6, 2),
        ("b", 2, 1),
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
        ("b", 3, 2),
        ("b", 3, 3),
        ("b", 2, 1),
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
        ("b", 6, 3),
        ("b", 2, 1),
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

STAGE4_FLOORS = len(STAGE4_ROSTER)

# Stage 6 dungeon and monster-party settings.
STAGE6_FLOORS = 3
STAGE6_EXTRA_CORRIDORS = 0
STAGE6_INITIAL_MONSTERS = 18
STAGE6_INITIAL_SPAWN_DRAWS = (40, 35, 30)
STAGE6_SPAWN_INTERVAL = 20
STAGE6_PARTY_SPAWN_PERCENT = 45
STAGE6_SPAWN_ATTEMPTS = 10
STAGE6_PARTY_SPAWN_ATTEMPTS = 5
STAGE6_REDUCED_SPAWN_VARIANTS = (("A", 1), ("b", 1), ("b", 2), ("b", 3), ("i", 2))
STAGE6_FLOOR2_REDUCED_SPAWN_VARIANTS = (("g", 1), ("E", 1), ("m", 1))
STAGE6_MONSTER_PARTY_LIMIT = 8
STAGE6_BRIDGEHEAD_KNOWN_VORTEX_RATIO = 0.2
STAGE6_INITIAL_PARTY_ROOMS: Tuple[Point, ...] = (
    (0, 0), (2, 0), (4, 0), (0, 2), (2, 2), (4, 2),
)
STAGE6_INITIAL_PARTY_PRIORITY = (("b", 2), ("b", 1), ("B", 2), ("B", 1))
# Weights for parties of 1, 2, and 3 monsters, by floor; larger sizes are disabled.
STAGE6_PARTY_SIZE_WEIGHTS = (
    (78, 21, 1, 0, 0),
    (60, 30, 10, 0, 0),
    (45, 30, 25, 0, 0),
    (45, 30, 25, 0, 0),
)
# Each roster entry (character, count, rank) supplies party leaders.
# Sword carriers stay scarce; deeper floors progress to rank 2 and 3.
STAGE6_EXTRA_BISON_RANKS = (1, None, None, None)
STAGE6_ROSTER = (
    (
        ("a", 12, 1), ("a", 3, 2), ("A", 2, 1), ("b", 5, 1), ("B", 1, 1), ("c", 1, 1),
        ("f", 2, 1),
        ("d", 4, 1), ("e", 1, 1), ("g", 1, 1), ("m", 1, 1),
    ),
    (
        ("a", 1, 2), ("A", 2, 1), ("b", 5, 2), ("B", 1, 2), ("c", 1, 1),
        ("d", 2, 1), ("d", 2, 2), ("f", 1, 1), ("f", 1, 2), ("w", 1, 1), ("g", 3, 1),
        ("k", 1, 1), ("i", 1, 1), ("i", 1, 2), ("X", 1, 1), ("E", 1, 1), ("m", 1, 1),
    ),
    (
        ("a", 2, 2), ("a", 4, 3), ("A", 3, 1), ("b", 5, 3), ("B", 1, 3),
        ("c", 1, 1), ("d", 1, 2), ("f", 1, 1), ("f", 2, 2),
        ("w", 1, 1), ("w", 2, 2), ("g", 2, 1), ("g", 1, 2),
        ("k", 3, 1), ("i", 2, 1), ("i", 1, 2), ("X", 1, 2), ("m", 1, 1),
    ),
)
STAGE6_BOSS_PARTY = (("F", 2), ("V", 1), ("k", 1))
STAGE6_BOSS_ESCORTS = (("w", 1),)
_STAGE6_DEEP_SUPPORT_POOL = (
    ("a", 1), ("a", 1), ("e", 1), ("e", 1),
    ("b", 1), ("w", 2), ("k", 1),
)
_STAGE6_FLOOR2_SUPPORT_POOL = (
    ("a", 1), ("a", 1), ("a", 1),
    ("b", 1), ("b", 1),
    ("e", 1), ("e", 1),
)
STAGE6_SUPPORT_POOLS = (
    (("a", 1),), _STAGE6_FLOOR2_SUPPORT_POOL
) + (
    _STAGE6_DEEP_SUPPORT_POOL,
    (("a", 3), ("b", 2), ("b", 3)),
)
STAGE6_HAZARD_COUNTS = ((0, 0), (0, 2), (0, 2), (0, 2))
STAGE6_FINAL_FLOOR_BARRIER_PERCENT = 7
STAGE6_BARRIER_VORTEX_RADIUS_MULTIPLIER = 1.5

# Elves placed by the multi-floor builder instead of the static floor rosters.
STAGE_RUNTIME_ELVES: Dict[int, Tuple[str, ...]] = {
    3: ("C", "I"),
    4: ("C", "I", "J", "K", "H", "S", "L"),
}

STAGE_BOSSES: Dict[int, Tuple[str, int]] = {
    3: ("W", 1),
    4: (CHAR_FIRE_DRAKE, 2),
}

# Display duration and untranslated text; empty stages have no opening message.
STAGE_START_MESSAGES: Dict[int, Tuple[int, str]] = {
    1: (-1, ""),
    2: (-1, ""),
    3: (5, "-- The King has ordered the Dread Wyrm (W) slain."),
    4: (5, "-- The King has ordered the Strong Fire Drake (F') slain."),
    5: (12, "-- Explore the training ground and claim the Fire Drake’s treasure."),
    6: (12, "-- Defeat the Wyrm on the final floor, then take the treasure."),
}

