"""Stage 3 rules, kept separate from the compact legacy stage loop."""

from collections import Counter, deque
from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Container, Deque, Dict, List, Optional, Set, Tuple

from . import defs as d
from .arlq import (
    MESSAGE_TICKS,
    GameConfig,
    find_random_place,
    get_torched,
    iterate_offsets,
    move_player,
    reveal_entities_in_fov,
    spawn_at,
    spread_caltrops,
    tick_message,
    unlock_treasure_for_defeat,
)
from .i18n import t as tr
from .stage_maze import (
    generate_floor_field,
    room_center,
    shuffle_floor_layout,
    tile_at,
)
from .trace import DIR_TO_KEY, TraceRecorder
from .utils import rand

FLOORS = 3
LOOP_TURNS = 80
STAGE3_FLOOR_LAYOUT = [(1, 0), (0, 0), (0, 0)]
STAGE4_FLOOR_LAYOUT = [(1, 1), (0, 2), (0, 2)]
STAGE3_STAIR_PAIRS_PER_TRANSITION = 1
STAGE4_STAIR_PAIRS_PER_TRANSITION = 2
STAGE3_C = d.STAGE3_C_FLAG
STAGE3_I = d.STAGE3_I_FLAG
STAGE3_K = d.STAGE3_K_FLAG
STAGE3_H = d.STAGE3_H_FLAG
STAGE3_W = d.STAGE3_W_FLAG
STAGE3_J = d.STAGE3_J_FLAG

ELF_REPEAT_MESSAGES = {
    "K": "-- The Collector Elf (K) looks satisfied.",
    "H": "-- Keep the talisman close to your skin.",
}

# Each entry is [(tribe_char, population, empowered), ...] for one floor.
ROSTER: List[List[Tuple[str, int, int]]] = [
    [("a", 20, 1), ("A", 2, 1), ("b", 6, 1), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("I", 1, 1), ("J", 1, 1), ("n", 1, 1), ("o", 1, 1), (d.CHAR_PEGASUS, 1, 1)],
    [("a", 20, 1), ("A", 2, 1), ("b", 3, 1), ("b", 3, 2), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("K", 1, 1), ("n", 1, 1), ("o", 1, 1), (d.CHAR_PEGASUS, 1, 1)],
    [("A", 2, 1), ("b", 3, 1), ("b", 3, 2), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("w", 1, 1), ("W", 1, 1), ("H", 1, 1), ("n", 1, 1), ("o", 1, 1), (d.CHAR_PEGASUS, 1, 1)],
]

# Stage 4 has its own per-floor counts so balancing it does not change Stage 3.
STAGE4_ROSTER: List[List[Tuple[str, int, int]]] = [
    [("a", 20, 1), ("A", 2, 1), ("b", 6, 1), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("n", 1, 1), ("o", 1, 1), (d.CHAR_PEGASUS, 1, 1)],
    [("a", 20, 1), ("A", 2, 1), ("b", 6, 1), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("n", 1, 1), ("o", 1, 1), (d.CHAR_PEGASUS, 1, 1)],
    [("a", 20, 1), ("A", 2, 1), ("b", 3, 1), ("b", 3, 2), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("n", 1, 1), ("o", 1, 1), (d.CHAR_PEGASUS, 1, 1)],
]

# Distinct, non-elf monster tribes across all floors, strongest first: feeds
# the right-edge strength column (see d.build_strength_column), which shows
# the whole stage's roster regardless of which floor the player is on.
_ROSTER_CHARS = dict.fromkeys(char for floor in ROSTER for char, _, _ in floor)
ROSTER_TRIBES: List[d.MonsterTribe] = sorted(
    (
        d.CHAR_TO_MONSTER_TRIBE[c]
        for c in _ROSTER_CHARS
        if c in d.CHAR_TO_MONSTER_TRIBE and not d.CHAR_TO_MONSTER_TRIBE[c].is_elf
    ),
    key=lambda t: t.level,
    reverse=True,
)
STAGE4_ROSTER_TRIBES: List[d.MonsterTribe] = sorted(
    (
        d.CHAR_TO_MONSTER_TRIBE[c]
        for c in dict.fromkeys(char for floor in STAGE4_ROSTER for char, _, _ in floor)
        if c in d.CHAR_TO_MONSTER_TRIBE and not d.CHAR_TO_MONSTER_TRIBE[c].is_elf
    ),
    key=lambda t: t.level,
    reverse=True,
)

@dataclass
class Floor:
    """State owned by one floor in a multi-floor stage."""

    field: List[List[str]]
    entities: List[d.Entity]
    seen: List[List[int]]
    known_companions: Set[str]
    up: d.Point
    down: d.Point
    island: Optional[d.Point]
    up_stairs: List[d.Point] = dataclass_field(default_factory=list)
    down_stairs: List[d.Point] = dataclass_field(default_factory=list)
    contact_reveal: Optional[d.Point] = None

# History entries snapshot everything the Loop Companion can rewind.
HistoryEntry = Tuple[List[Floor], d.Player, int, d.Point, Counter[Tuple[int, str]]]


@dataclass(frozen=True)
class _ContactResult:
    """Outcome of an entity contact within one Stage 3 turn."""

    message: Optional[str]
    end_turn: bool = False
    message_ticks: int = MESSAGE_TICKS


def _place_barrier(field: List[List[str]], center: d.Point) -> None:
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not (dx or dy):
                continue
            x, y = center[0] + dx, center[1] + dy
            if not (0 <= y < len(field) and 0 <= x < len(field[0])):
                continue
            # Never punch through the sealed Isolated Elf room's
            # perimeter when another Stage 3 feature is nearby.
            if field[y][x] == d.CHAR_FLOOR:
                field[y][x] = d.CHAR_BARRIER


def _inside_island(point: Optional[d.Point], island_tile: Optional[d.Point]) -> bool:
    if point is None or island_tile is None:
        return False
    left = island_tile[0] * (d.TILE_WIDTH + 1)
    top = island_tile[1] * (d.TILE_HEIGHT + 1)
    return left < point[0] < left + d.TILE_WIDTH + 1 and top < point[1] < top + d.TILE_HEIGHT + 1


def _spawn(
    entities: List[d.Entity],
    field: List[List[str]],
    ch: str,
    avoid: Container[d.Point] = (),
    island_tile: Optional[d.Point] = None,
    floor_index: Optional[int] = None,
    empowered: int = 1,
) -> d.Point:
    while True:
        x, y = find_random_place(entities, field, distance=2)
        if (x, y) not in avoid and not _inside_island((x, y), island_tile):
            break
    spawn_at(entities, x, y, d.CHAR_TO_TRIBE[ch], empowered=empowered, origin_floor=floor_index)
    return x, y


def _find_escape_place(current: Floor) -> d.Point:
    """A random open cell for the player to be sent to, never inside a
    sealed island (e.g. the Isolated Elf's room)."""
    island_tile = current.island
    while True:
        x, y = find_random_place(current.entities, current.field, distance=2)
        if not _inside_island((x, y), island_tile):
            return x, y


def _split_floor_roster(
    roster: List[Tuple[str, int, int]], elf_floors: Dict[str, int]
) -> Tuple[List[Tuple[str, int, int]], List[Tuple[str, int, int]], List[Tuple[str, int, int]]]:
    """Separate ordinary spawns, assigned-floor elves, and Wyrm encounters."""
    ordinary, elves, wyrms = [], [], []
    for entry in roster:
        ch = entry[0]
        if ch == "I":
            continue  # I is placed inside the generated isolated room.
        if ch in {"w", "W"}:
            wyrms.append(entry)
        elif ch in elf_floors:
            elves.append(entry)
        else:
            ordinary.append(entry)
    return ordinary, elves, wyrms


def _spawn_roster_entries(
    entries: List[Tuple[str, int, int]],
    entities: List[d.Entity],
    field: List[List[str]],
    reserved: Container[d.Point],
    island_tile: Optional[d.Point],
    floor_index: int,
) -> None:
    for ch, count, empowered in entries:
        for _ in range(count):
            _spawn(entities, field, ch, reserved, island_tile, floor_index, empowered)


def _spawn_assigned_floor_elves(
    entries: List[Tuple[str, int, int]],
    elf_floors: Dict[str, int],
    floor_index: int,
    entities: List[d.Entity],
    field: List[List[str]],
    reserved: Container[d.Point],
    island_tile: Optional[d.Point],
) -> None:
    for ch, count, empowered in entries:
        if elf_floors[ch] == floor_index:
            for _ in range(count):
                _spawn(entities, field, ch, reserved, island_tile, floor_index, empowered)


def _spawn_roster_wyrms(
    entries: List[Tuple[str, int, int]],
    entities: List[d.Entity],
    field: List[List[str]],
    reserved: Container[d.Point],
    down: d.Point,
    floor_index: int,
) -> None:
    has_boss = False
    for ch, count, empowered in entries:
        for monster_index in range(count):
            if ch == "W" and monster_index == 0:
                x, y = down
                entities.append(d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[ch], empowered))
                has_boss = True
            else:
                x, y = _spawn(entities, field, ch, reserved, floor_index=floor_index, empowered=empowered)
            _place_barrier(field, (x, y))
    if has_boss:
        entities.append(d.Treasure(*_treasure_spot(entities, field, reserved), d.CHAR_TREASURE + "W"))


def _spawn_island_elf(field: List[List[str]], entities: List[d.Entity], island_tile: Optional[d.Point]) -> None:
    if island_tile is None:
        return
    left = island_tile[0] * (d.TILE_WIDTH + 1) + 1
    top = island_tile[1] * (d.TILE_HEIGHT + 1) + 1
    for y in range(top, top + d.TILE_HEIGHT):
        for x in range(left, left + d.TILE_WIDTH):
            field[y][x] = d.CHAR_FLOOR
    for x in range(left, left + d.TILE_WIDTH):
        if island_tile[1] > 0:
            field[top - 1][x] = d.WALL_CHAR
        if island_tile[1] < d.TILE_NUM_Y - 1:
            field[top + d.TILE_HEIGHT][x] = d.WALL_CHAR
    for y in range(top, top + d.TILE_HEIGHT):
        if island_tile[0] > 0:
            field[y][left - 1] = d.WALL_CHAR
        if island_tile[0] < d.TILE_NUM_X - 1:
            field[y][left + d.TILE_WIDTH] = d.WALL_CHAR
    spots = [
        (x, y)
        for y in range(top, top + d.TILE_HEIGHT)
        for x in range(left, left + d.TILE_WIDTH)
        if field[y][x] == d.CHAR_FLOOR
    ]
    x, y = rand.choice(spots)
    entities.append(d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE["I"]))


def _build_floor(
    index: int,
    special_floors: Dict[str, int],
    elf_floors: Dict[str, int],
    entry_point: Optional[d.Point] = None,
    corridor_h_width: int = d.CORRIDOR_H_WIDTH,
    corridor_v_width: int = d.CORRIDOR_V_WIDTH,
    room_counts: Tuple[int, int] = (0, 0),
    *,
    roster: List[Tuple[str, int, int]],
    stage_num: int = 3,
    up_point: Optional[d.Point] = None,
    down_point: Optional[d.Point] = None,
) -> Floor:
    island_count, filled_count = room_counts
    field, up, down, island_rooms, _ = generate_floor_field(
        up_point if up_point is not None else entry_point,
        down_point,
        corridor_h_width,
        corridor_v_width,
        island_count,
        filled_count,
    )
    island_tile = next(iter(island_rooms), None)

    if index < FLOORS - 1:
        field[down[1]][down[0]] = d.CHAR_STAIRS_DOWN
    if index:
        field[up[1]][up[0]] = d.CHAR_STAIRS_UP

    entities: List[d.Entity] = []
    reserved = {up, down}
    ordinary_roster, elf_roster, wyrm_roster = _split_floor_roster(roster, elf_floors)
    _spawn_roster_entries(ordinary_roster, entities, field, reserved, island_tile, index)
    _spawn_island_elf(field, entities, island_tile)
    _spawn_assigned_floor_elves(
        elf_roster, elf_floors, index, entities, field, reserved, island_tile
    )
    _spawn_roster_wyrms(wyrm_roster, entities, field, reserved, down, index)

    for ch, assigned_floor in special_floors.items():
        if index == assigned_floor:
            _spawn(entities, field, ch, reserved, island_tile, index)

    return Floor(
        field=field,
        entities=entities,
        seen=[[0] * len(field[0]) for _ in field],
        known_companions=set(),
        up=up,
        down=up if stage_num == 4 and index == FLOORS - 1 else down,
        island=island_tile,
        up_stairs=[up] if index else [],
        down_stairs=[down] if index < FLOORS - 1 else [],
    )


def _treasure_spot(entities: List[d.Entity], field: List[List[str]], reserved: Container[d.Point]) -> d.Point:
    while True:
        p = find_random_place(entities, field, distance=2)
        if p not in reserved:
            return p


def build(
    corridor_h_width: int = d.CORRIDOR_H_WIDTH,
    corridor_v_width: int = d.CORRIDOR_V_WIDTH,
    stage_num: int = 3,
    stair_pairs_per_transition: Optional[int] = None,
) -> Tuple[List[Floor], d.Player]:
    if stage_num not in (3, 4):
        raise ValueError("multi-floor builder supports stages 3 and 4")
    if stair_pairs_per_transition is None:
        stair_pairs_per_transition = (
            STAGE3_STAIR_PAIRS_PER_TRANSITION
            if stage_num == 3
            else STAGE4_STAIR_PAIRS_PER_TRANSITION
        )
    if stair_pairs_per_transition < 1:
        raise ValueError("each floor transition needs at least one stair pair")
    layout = STAGE3_FLOOR_LAYOUT if stage_num == 3 else STAGE4_FLOOR_LAYOUT
    floor_layout = shuffle_floor_layout(layout)
    elf_floors = {
        "I": next(index for index, counts in enumerate(floor_layout) if counts[0]),
    }
    if stage_num == 3:
        elf_floors.update({
            "J": rand.randrange(FLOORS),
            "K": rand.randrange(FLOORS - 1),
            "H": rand.randrange(FLOORS),
        })
        special_floors = {ch: rand.randrange(FLOORS) for ch in ("m", "X", "e", "g")}
        m_floor = special_floors.pop("m")
    else:
        special_floors = {}
        m_floor = None

    stair_tiles: List[d.Point] = []
    if stage_num == 4:
        tiles = [(x, y) for y in range(d.TILE_NUM_Y) for x in range(d.TILE_NUM_X)]
        stair_tiles.append(rand.choice(tiles))
        for _ in range(FLOORS - 2):
            options = [tile for tile in tiles if tile != stair_tiles[-1]]
            stair_tiles.append(rand.choice(options))

    floors: List[Floor] = []
    entry_point = None
    for index in range(FLOORS):
        up_point = None
        down_point = None
        if stage_num == 4:
            up_point = None if index == 0 else room_center(stair_tiles[index - 1])
            down_point = None if index == FLOORS - 1 else room_center(stair_tiles[index])
        roster = list(STAGE4_ROSTER[index] if stage_num == 4 else ROSTER[index])
        if index == m_floor:
            roster.append(("m", 2, 1))
        floor = _build_floor(
            index,
            special_floors,
            elf_floors,
            entry_point,
            corridor_h_width,
            corridor_v_width,
            floor_layout[index],
            roster=roster,
            stage_num=stage_num,
            up_point=up_point,
            down_point=down_point,
        )
        floors.append(floor)
        if stage_num == 3:
            entry_point = floor.down

    _add_additional_stairs(
        floors,
        stair_pairs_per_transition,
    )

    player = d.Player(floors[0].up[0], floors[0].up[1], 1, d.LP_INIT)
    player.stage3_elf_floors = {char: floor + 1 for char, floor in elf_floors.items()}
    return floors, player


def _add_additional_stairs(floors: List[Floor], pair_count: int) -> None:
    """Add matching stair pairs up to the configured count per floor link."""
    if pair_count <= 1:
        return
    for index in range(FLOORS - 1):
        upper, lower = floors[index], floors[index + 1]

        def separated_from_stairs(point: d.Point, stairs: List[d.Point]) -> bool:
            room = tile_at(point)
            return all(
                abs(room[0] - stair_room[0]) + abs(room[1] - stair_room[1]) > 1
                for stair_room in (tile_at(stair) for stair in stairs)
            )

        candidates = [
            (x, y)
            for y in range(1, d.FIELD_HEIGHT - 1)
            for x in range(1, d.FIELD_WIDTH - 1)
            if upper.field[y][x] == d.CHAR_FLOOR
            and lower.field[y][x] == d.CHAR_FLOOR
            and separated_from_stairs((x, y), upper.down_stairs)
            and (x, y) != upper.down
            and (x, y) != lower.up
        ]
        while candidates and len(upper.down_stairs) < pair_count:
            point = candidates.pop(rand.randrange(len(candidates)))
            if any(abs(entity.x - point[0]) <= 2 and abs(entity.y - point[1]) <= 2 for entity in upper.entities):
                continue
            if any(abs(entity.x - point[0]) <= 2 and abs(entity.y - point[1]) <= 2 for entity in lower.entities):
                continue
            upper.field[point[1]][point[0]] = d.CHAR_STAIRS_DOWN
            lower.field[point[1]][point[0]] = d.CHAR_STAIRS_UP
            upper.down_stairs.append(point)
            lower.up_stairs.append(point)
            candidates = [
                candidate
                for candidate in candidates
                if separated_from_stairs(candidate, upper.down_stairs)
            ]


def _move_player(
    direction: d.Point, current: Floor, player: d.Player, trace: Optional[TraceRecorder] = None
) -> None:
    """Apply one step of player movement, including sword-breaking and Pegasus jumps."""
    wall_result = move_player(
        direction,
        current.field,
        player,
        (d.CHAR_FLOOR, d.CHAR_CALTROP, *d.STAIR_CHARS, d.CHAR_BARRIER),
    )
    if trace is not None and wall_result is not None:
        trace.record_wall(wall_result)


def _apply_terrain_hazards(current: Floor, player: d.Player, previous: d.Point) -> Optional[str]:
    """Apply barrier/caltrop damage for the player's current cell.

    Returns an event message for the barrier case, or None otherwise (caltrop
    damage never produces a message, matching the legacy stages).
    """
    field = current.field
    event_message = None
    if field[player.y][player.x] == d.CHAR_BARRIER and not (player.stage3_flags & STAGE3_H) and (player.x, player.y) != previous:
        player.lp -= d.BARRIER_LP_DAMAGE
        event_message = tr("-- The barrier burns you.")
    if field[player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= d.CALTROP_LP_DAMAGE
        field[player.y][player.x] = d.CHAR_FLOOR
    return event_message


def _rewind_to_history(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    history: Deque[HistoryEntry],
) -> str:
    """Handle contact with the Loop Companion ('l'): rewind to the oldest recorded state."""
    known = player.known_monsters
    unlocked = player.unlocked_treasures
    elf_floors = player.stage3_elf_floors
    seen = [floor_data.seen for floor_data in floors]
    known_companions = [floor_data.known_companions for floor_data in floors]

    old_floors, old_player, old_floor, old_checkpoint, old_queue = history[0]
    floors[:] = old_floors
    queue.clear()
    queue.update(old_queue)
    for floor_data, preserved_seen in zip(floors, seen, strict=True):
        floor_data.seen = preserved_seen
    for floor_data, preserved_known in zip(floors, known_companions, strict=True):
        floor_data.known_companions = preserved_known

    player.__dict__.update(old_player.__dict__)
    # Monster/treasure knowledge and elf floor locations survive the rewind;
    # everything else (position, level, LP, floor, stage3_flags, ...)
    # reverts to the recorded past. met_elves must revert together
    # with stage3_flags: it gates re-processing of an elf encounter
    # (_resolve_monster_contact), so keeping it "met" while stage3_flags
    # reverts to not-yet-met would permanently block earning that elf's
    # flag again, and would render it on the field as already resolved
    # while the status bar (driven by stage3_flags) still shows it unmet.
    player.known_monsters = known
    player.unlocked_treasures = unlocked
    player.stage3_elf_floors = elf_floors

    floor[0], checkpoint[0] = old_floor, old_checkpoint
    history.clear()

    restored_entities = floors[floor[0]].entities
    for index, restored in enumerate(restored_entities):
        if isinstance(restored, d.Companion) and restored.tribe.char == "l":
            del restored_entities[index]
            break
    _spawn(restored_entities, floors[floor[0]].field, "l", {(player.x, player.y)}, floors[floor[0]].island, floor[0])

    return tr("-- Time folds back to the beginning of the recorded past.")


def _defeat_monster(
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    trace: Optional[TraceRecorder] = None,
) -> None:
    """Apply the effects of successfully defeating `entity` in combat."""
    ch = entity.tribe.char

    # A successful monster defeat establishes the next respawn point,
    # matching the legacy stages and the Rust port.
    if not entity.tribe.is_elf:
        checkpoint[0] = (player.x, player.y)

    # Every ordinary monster replaces the current item. This is important
    # for d (Poisoned): defeating another monster with no item must clear
    # the poison and identify the new source.
    if ch != "H":
        old_item, old_source = player.item, player.item_taken_from
        d.take_monster_item(player, entity.tribe.item, ch)
        if trace is not None and old_item:
            trace.add_expired({"type": "item_expired", "item": old_source, "reason": "overwritten"})

    if ch == "W":
        player.stage3_flags |= STAGE3_W
        unlock_treasure_for_defeat(entity, player.unlocked_treasures)
        player.known_monsters.add(d.monster_type_key(entity))
        if player.stage3_treasure_collected:
            player.stage3_won = True
    if ch == "K":
        player.stage3_flags |= STAGE3_K
        d.clear_player_item(player)
    if ch == "H":
        player.stage3_flags |= STAGE3_H
    if ch == "m":
        player.stage3_spores = True
    if ch == "C":
        player.stage3_flags |= STAGE3_C

    d.grant_defeat_level(player, entity.tribe.effect)
    d.apply_feed(player, entity.tribe.feed)
    player.karma += 1

    if entity.tribe.effect == d.EFFECT_CALTROP_SPREAD:
        spread_caltrops(current.field, (player.x, player.y), current.entities)
    elif entity.tribe.effect == d.EFFECT_ROCK_SPREAD:
        for x, y in iterate_offsets(
            player.x, player.y, d.ROCK_SPREAD_OFFSETS, except_for_entities=current.entities
        ):
            if current.field[y][x] == d.CHAR_FLOOR:
                current.field[y][x] = d.WALL_CHAR

    if d.monster_level(entity) > 0 and ch not in d.STAGE3_NO_RESPAWN_MONSTERS:
        spawn_key = (floor[0], d.monster_type_key(entity))
        queue[spawn_key] = queue.get(spawn_key, 0) + 1


def _resolve_monster_contact(
    hit: int,
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    event_message: Optional[str],
    trace: Optional[TraceRecorder] = None,
) -> _ContactResult:
    """Resolve contact with a monster, including early-ending elf encounters."""
    ch = entity.tribe.char
    contact_key = (floor[0], entity.x, entity.y)

    if entity.tribe.is_elf:
        player.stage3_elf_floors.setdefault(ch, floor[0] + 1)

    if ch in player.met_elves:
        current.entities.pop(hit)
        if trace is not None:
            trace.record_contact({"type": "monster", "id": ch, "outcome": "refused"})
        if ch == "I":
            # The sealed Isolated Elf island has no other way out (see
            # _inside_island): once the player has met "I", every further
            # visit sends them back out instead of trapping them inside.
            current.entities.append(entity)
            player.x, player.y = _find_escape_place(current)
            return _ContactResult(
                tr("-- The Isolated Elf wants to be left alone, and sends you elsewhere."),
                end_turn=True,
            )
        if ch in ELF_REPEAT_MESSAGES:
            current.entities.append(entity)
            return _ContactResult(tr(ELF_REPEAT_MESSAGES[ch]), end_turn=True)
        return _ContactResult(None, end_turn=True)

    # The W treasure must remain hidden until W is actually defeated. Other
    # monsters are revealed on contact, but revealing W here would also make
    # the renderer show its locked treasure.
    if ch != "W":
        player.known_monsters.add(d.monster_type_key(entity))
    current.entities.pop(hit)

    # Contact with any monster clears the spores. The Rust version resets
    # this before resolving the encounter, so defeating a different monster
    # restores the normal FOV immediately.
    player.stage3_spores = False

    if ch == "I":
        player.stage3_flags |= STAGE3_I
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "I", "outcome": "granted"})
    elif ch == "J":
        player.stage3_flags |= STAGE3_J
        player.persistent_followers.append((player.x, player.y, floor[0], "J"))
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "J", "outcome": "granted"})
    elif ch == "K" and not (player.stage3_flags & STAGE3_C):
        current.entities.append(entity)
        # The first refusal only shows a message; any later refusal sends the
        # player elsewhere, like repeat contact with the Isolated Elf.
        if player.k_elf_refused:
            player.x, player.y = _find_escape_place(current)
            event_message = tr("-- Respawned to a random location.")
        else:
            event_message = tr("-- Please bring the cursed sword (C).")
            player.k_elf_refused = True
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "K", "outcome": "refused"})
    elif ch == "H" and (player.stage3_flags & (STAGE3_I | STAGE3_J | STAGE3_K)).bit_count() < 2:
        current.entities.append(entity)
        # The first refusal only shows a message; any later refusal sends the
        # player elsewhere, like repeat contact with the Isolated Elf.
        if player.high_elf_refused:
            player.x, player.y = _find_escape_place(current)
            event_message = tr("-- Respawned to a random location.")
        else:
            event_message = tr("-- The High Elf does not recognize you yet.")
            player.high_elf_refused = True
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "H", "outcome": "refused"})
    elif d.current_player_attack(player, 3) < d.monster_level(entity):
        # Losing still identifies the monster, including W. Treasure glyphs
        # remain gated separately by their unlock state in the renderer.
        player.known_monsters.add(d.monster_type_key(entity))
        # The encounter remains on the map when the player loses. Rust
        # resolves combat before removing the monster; keeping the entity
        # here prevents a failed attack from deleting it.
        current.entities.append(entity)
        # Losing twice in a row to the very same monster (no other monster
        # contact in between) means it is blocking the only way through:
        # send the player somewhere random instead of back to the
        # checkpoint, so a too-strong monster on a bridge corridor cannot
        # soft-lock the floor.
        if player.last_contact_monster == contact_key:
            player.x, player.y = _find_escape_place(current)
            event_message = tr("-- Respawned to a random location.")
        else:
            player.x, player.y = checkpoint[0]
            # Keep the monster that caused this respawn visible for the next
            # frame, even when the checkpoint is outside its FOV.
            current.contact_reveal = (entity.x, entity.y)
            event_message = tr("-- Respawned!")
        if trace is not None:
            trace.record_contact(
                {
                    "type": "monster",
                    "id": d.monster_type_key(entity),
                    "outcome": "lose",
                    "respawn_to": [player.x, player.y],
                }
            )
        d.apply_respawn_penalty(player)
        old_item, old_source = player.item, player.item_taken_from
        d.clear_player_item(player)
        if trace is not None and old_item:
            trace.add_expired({"type": "item_expired", "item": old_source, "reason": "lost_on_defeat"})
    else:
        if trace is not None:
            trace.record_contact({"type": "monster", "id": d.monster_type_key(entity), "outcome": "win"})
        _defeat_monster(entity, current, player, floor, checkpoint, queue, trace=trace)

    if entity.tribe.is_elf and ch != "J" and entity not in current.entities:
        player.met_elves.add(ch)
        current.entities.append(entity)
    elif entity.tribe.is_elf and entity not in current.entities:
        player.met_elves.add(ch)

    player.last_contact_monster = contact_key

    if event_message is None:
        tribe_message = entity.tribe.event_message
        if tribe_message:
            event_message = tr(tribe_message)

    return _ContactResult(event_message)


def _resolve_contact(
    hit: int,
    current: Floor,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    history: Deque[HistoryEntry],
    event_message: Optional[str],
    trace: Optional[TraceRecorder] = None,
) -> _ContactResult:
    """Resolve contact with the entity at `hit` in current.entities.

    The result explicitly marks encounters that end the turn immediately,
    bypassing the usual end-of-turn processing (Loop Companion rewind and
    repeated elf contact).
    """
    entity = current.entities[hit]

    if isinstance(entity, d.Treasure):
        collected = entity.unlock_key in player.unlocked_treasures
        if trace is not None:
            trace.record_contact({"type": "treasure", "id": entity.unlock_key, "collected": collected})
        if collected:
            current.entities.pop(hit)
            player.stage3_treasure_collected = True
            if player.stage3_flags & STAGE3_W:
                player.stage3_won = True
            else:
                event_message = tr("-- You took the treasure chest, but the King's request remains.")
        return _ContactResult(event_message)

    if isinstance(entity, d.Companion):
        ch = entity.tribe.char
        current.known_companions.add(ch)
        current.entities.pop(hit)
        if trace is not None:
            trace.record_contact({"type": "companion", "id": ch})
        # l is a companion whose contact rewinds the recorded past.
        if ch == "l" and history:
            message = _rewind_to_history(floors, player, floor, checkpoint, queue, history)
            return _ContactResult(message, end_turn=True, message_ticks=5)
        player.companion = entity
        player.karma = 0
        tribe_message = entity.tribe.event_message
        return _ContactResult(tr(tribe_message) if tribe_message else None)

    assert isinstance(entity, d.Monster)
    return _resolve_monster_contact(hit, entity, current, player, floor, checkpoint, queue, event_message, trace=trace)


def _advance_persistent_followers(player: d.Player, floor_index: int, moved: bool, previous: d.Point) -> None:
    """The Javelin Elf follows one step behind; keep its recorded position in sync."""
    for i, follower in enumerate(player.persistent_followers):
        if follower[2] == floor_index and moved:
            player.persistent_followers[i] = (previous[0], previous[1], follower[2], follower[3])


def _handle_floor_transition(
    current: Floor,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
) -> Optional[str]:
    point = (player.x, player.y)
    legacy_floors = not any(f.up_stairs or f.down_stairs for f in floors)
    down_stairs = current.down_stairs or ([current.down] if legacy_floors else [])
    up_stairs = current.up_stairs or ([current.up] if legacy_floors else [])
    if floor[0] < FLOORS - 1 and point in down_stairs:
        stair_index = down_stairs.index(point)
        floor[0] += 1
        destination_stairs = floors[floor[0]].up_stairs or [floors[floor[0]].up]
        player.x, player.y = destination_stairs[min(stair_index, len(destination_stairs) - 1)]
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [(player.x, player.y, floor[0], ch) for _, _, _, ch in player.persistent_followers]
        return tr("-- Descended to floor {n}/3.").format(n=floor[0] + 1)
    if floor[0] > 0 and point in up_stairs:
        stair_index = up_stairs.index(point)
        floor[0] -= 1
        destination_stairs = floors[floor[0]].down_stairs or [floors[floor[0]].down]
        player.x, player.y = destination_stairs[min(stair_index, len(destination_stairs) - 1)]
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [(player.x, player.y, floor[0], ch) for _, _, _, ch in player.persistent_followers]
        return tr("-- Ascended to floor {n}/3.").format(n=floor[0] + 1)
    return None


def _process_respawn_queue(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    queue: Counter[Tuple[int, str]],
    hours: int,
    trace: Optional[TraceRecorder] = None,
) -> None:
    if hours % d.MONSTER_RESPAWN_INTERVAL != 0:
        return
    for (spawn_floor, type_key), count in list(queue.items()):
        if not count:
            continue
        avoid = {(player.x, player.y)} if spawn_floor == floor[0] else set()
        if type_key[-1].isdigit():
            ch = type_key[:-1]
            empowered = int(type_key[-1])
        else:
            ch = type_key
            empowered = 1
        args = (floors[spawn_floor].entities, floors[spawn_floor].field, ch, avoid, floors[spawn_floor].island, spawn_floor)
        if empowered == 1:
            x, y = _spawn(*args)
        else:
            x, y = _spawn(*args, empowered)
        queue[(spawn_floor, type_key)] -= 1
        if trace is not None:
            kind = "monster" if isinstance(d.CHAR_TO_TRIBE[ch], d.MonsterTribe) else "companion"
            trace.add_world_event(
                {"type": "respawn", "kind": kind, "id": type_key, "at": [x, y], "floor": spawn_floor}
            )


def _step(
    direction: d.Point,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    history: Deque[HistoryEntry],
    hours: int,
    trace: Optional[TraceRecorder] = None,
) -> Optional[Tuple[int, str]]:
    current = floors[floor[0]]
    history.append((deepcopy(floors), deepcopy(player), floor[0], checkpoint[0], deepcopy(queue)))
    if len(history) > LOOP_TURNS:
        history.popleft()

    previous = (player.x, player.y)
    _move_player(direction, current, player, trace=trace)
    event_message = _apply_terrain_hazards(current, player, previous)

    hit = next((i for i, e in enumerate(current.entities) if (e.x, e.y) == (player.x, player.y)), None)
    if hit is not None:
        contact = _resolve_contact(
            hit, current, floors, player, floor, checkpoint, queue, history, event_message, trace=trace
        )
        if contact.end_turn:
            return (contact.message_ticks, contact.message) if contact.message else None
        event_message = contact.message

    if player.companion is not None and player.karma >= player.companion.tribe.durability:
        ch = player.companion.tribe.char
        # Respawn on the floor the companion came from, not wherever it was
        # carried to and expired: otherwise a floor that never lost its own
        # copy can end up with two once the queued respawn fires.
        origin_floor = player.companion.origin_floor
        if origin_floor is None:
            origin_floor = floor[0]
        spawn_key = (origin_floor, ch)
        queue[spawn_key] = queue.get(spawn_key, 0) + 1
        player.companion = None
        event_message = tr("-- The companion vanishes.")
        if trace is not None:
            trace.add_expired({"type": "companion_departed", "id": ch})

    reveal_entities_in_fov(player, current.entities)
    _advance_persistent_followers(player, floor[0], (player.x, player.y) != previous, previous)

    floor_before = floor[0]
    transition_message = _handle_floor_transition(current, floors, player, floor, checkpoint)
    if transition_message is not None:
        event_message = transition_message
        if trace is not None:
            trace.record_contact({"type": "stairs", "from_floor": floor_before, "to_floor": floor[0]})

    _process_respawn_queue(floors, player, floor, queue, hours, trace=trace)

    return (MESSAGE_TICKS, event_message) if event_message else None


def run_game(
    ui: Any,
    seed_str: str,
    debug: bool = False,
    trace: Optional[TraceRecorder] = None,
    config: Optional[GameConfig] = None,
    stage_num: int = 3,
) -> None:
    if config is None:
        config = GameConfig()
    floors, player = build(
        config.corridor_h_width,
        config.corridor_v_width,
        stage_num,
        stair_pairs_per_transition=(
            STAGE3_STAIR_PAIRS_PER_TRANSITION
            if stage_num == 3
            else STAGE4_STAIR_PAIRS_PER_TRANSITION
        ),
    )
    player.known_monsters = set()
    player.unlocked_treasures = set()
    player.stage3_won = False
    player.stage3_treasure_collected = False
    player.met_elves = set()
    floor = [0]
    checkpoint = [floors[0].up]
    player.stage3_floor = 0
    view_floor = 0
    queue: Counter[Tuple[int, str]] = Counter()
    history: Deque[HistoryEntry] = deque()
    hours = 0
    message: Tuple[int, str] = (
        5,
        tr("-- The King has ordered the Dread Wyrm (W) slain.")
        if stage_num == 3
        else tr("-- Explore the sealed rooms across three floors."),
    )

    while player.lp > 0 and (stage_num == 4 or not player.stage3_won):
        current = floors[floor[0]]
        display_floor = floors[view_floor]
        cur = get_torched(player, config.torch_radius)
        if display_floor is current and display_floor.contact_reveal is not None:
            rx, ry = display_floor.contact_reveal
            # Mark the cell as explored without adding it to the current FOV;
            # this keeps the monster visible without extending the blue FOV
            # boundary out to its location.
            display_floor.seen[ry][rx] = 1
        for y in range(len(cur)):
            for x in range(len(cur[0])):
                current.seen[y][x] |= cur[y][x]

        message = tick_message(message)

        floor_view = view_floor != floor[0]
        show_entities = debug or getattr(ui, "map_mode", False)
        # The terminal renderer discovers the player from the entity list, while
        # the pygame renderer receives it separately. Keep the Stage 3 state
        # model separate and provide a render-only combined list.
        render_player = deepcopy(player) if floor_view else player
        render_player.stage3_floor = view_floor
        render_entities = [render_player, *display_floor.entities]
        known_types = player.known_monsters | display_floor.known_companions
        no_current_visibility = [[0] * len(display_floor.field[0]) for _ in display_floor.field]
        ui.draw_stage(
            hours=hours,
            player=render_player,
            entities=render_entities,
            field=display_floor.field,
            cur_torched=no_current_visibility if floor_view else cur,
            torched=display_floor.seen,
            known_types=known_types,
            show_entities=show_entities,
            stage_num=stage_num,
            message=message[1],
            checkpoint=checkpoint[0],
            unlocked_treasures=player.unlocked_treasures,
            dim_types=player.met_elves,
            stage_roster=ROSTER_TRIBES if stage_num == 3 else STAGE4_ROSTER_TRIBES,
            floor_view=floor_view,
            floor_label=f"F: {view_floor + 1}",
        )

        move = ui.input_direction()
        if move is None:
            if trace is not None:
                trace.record_quit()
                trace.set_outcome("unfinished" if getattr(ui, "ran_dry", False) else "quit")
            return
        if move == (0, 0):
            continue
        if getattr(ui, "shift_direction", False):
            view_floor = max(0, min(FLOORS - 1, view_floor + move[1]))
            continue

        # A real movement always returns the display to the player's floor.
        view_floor = floor[0]

        if trace is not None:
            key = DIR_TO_KEY.get(move)
            if key is None:
                raise RuntimeError("--trace-record does not support non-cardinal (e.g. diagonal joystick) movement")
            trace.begin_turn(key)

        event_message = _step(
            move, floors, player, floor, checkpoint, queue, history, hours,
            trace=trace,
        )
        player.stage3_floor = floor[0]
        # A stair contact can change the player's floor during _step(). Keep
        # the displayed floor in sync so the next frame shows the new floor.
        view_floor = floor[0]
        if event_message is not None:
            message = event_message

        if trace is not None:
            trace.set_player(player, stage_num)
            trace.commit_turn()

        hours += 1
        player.lp -= 1

    if trace is not None:
        trace.set_outcome("win" if stage_num == 3 and player.stage3_won else "lose")

    won = stage_num == 3 and player.stage3_won
    message = (-1, tr(">> Treasure chest obtained! <<") if won else tr(">> Collapsed from hunger! <<"))
    while True:
        current = floors[floor[0]]
        cur = get_torched(player, config.torch_radius)
        render_entities = [player, *current.entities]
        known_types = player.known_monsters | current.known_companions
        ui.draw_stage(
            hours=hours,
            player=player,
            entities=render_entities,
            field=current.field,
            cur_torched=cur,
            torched=current.seen,
            known_types=known_types,
            show_entities=debug,
            stage_num=stage_num,
            message=message[1],
            extra_keys=True,
            checkpoint=checkpoint[0],
            unlocked_treasures=player.unlocked_treasures,
            dim_types=player.met_elves,
            stage_roster=ROSTER_TRIBES if stage_num == 3 else STAGE4_ROSTER_TRIBES,
        )
        key = ui.input_alphabet()
        if key is None:
            return
        if key == "m":
            debug = not debug
        elif key == "s":
            message = (-1, tr("SEED: {seed_str}").format(seed_str=seed_str))
