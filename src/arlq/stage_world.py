"""Floor construction and map generation for the multi-floor stages."""

from typing import Container, Dict, List, Optional, Tuple

from . import defs as d
from .arlq import GameConfig, create_field, find_random_place, spawn_at, spawn_entities
from .stage_maze import generate_floor_field, room_center, shuffle_floor_layout, tile_at
from .stage_types import Floor
from .utils import rand


def _place_barrier(
    field: List[List[str]], center: d.Point, protected: Container[d.Point] = ()
) -> None:
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not (dx or dy):
                continue
            x, y = center[0] + dx, center[1] + dy
            if not (0 <= y < len(field) and 0 <= x < len(field[0])):
                continue
            # Never punch through the sealed Isolated Elf room's
            # perimeter when another Stage 3 feature is nearby.
            if field[y][x] == d.CHAR_FLOOR and (x, y) not in protected:
                field[y][x] = d.CHAR_BARRIER


def _place_stage4_final_floor_barriers(floor: Floor) -> None:
    """Cover ten percent of eligible final-floor cells with barriers."""
    occupied = {(entity.x, entity.y) for entity in floor.entities}
    protected = {
        floor.up,
        floor.down,
        *floor.up_stairs,
        *floor.down_stairs,
        *floor.collapse_landings,
        *occupied,
    }
    candidates = [
        (x, y)
        for y, row in enumerate(floor.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_FLOOR and (x, y) not in protected
    ]
    count = len(candidates) * d.STAGE4_FINAL_FLOOR_BARRIER_PERCENT // 100
    for _ in range(count):
        x, y = candidates.pop(rand.randrange(len(candidates)))
        floor.field[y][x] = d.CHAR_BARRIER


def _inside_island(point: Optional[d.Point], island_tile: Optional[d.Point]) -> bool:
    if point is None or island_tile is None:
        return False
    left = island_tile[0] * (d.TILE_WIDTH + 1)
    top = island_tile[1] * (d.TILE_HEIGHT + 1)
    return (
        left < point[0] < left + d.TILE_WIDTH + 1
        and top < point[1] < top + d.TILE_HEIGHT + 1
    )


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
    spawn_at(
        entities,
        x,
        y,
        d.CHAR_TO_TRIBE[ch],
        empowered=empowered,
        origin_floor=floor_index,
    )
    return x, y


def _find_escape_place(current: Floor, far_from: Optional[d.Point] = None) -> d.Point:
    """A random open cell for the player to be sent to, never inside a
    sealed island (e.g. the Isolated Elf's room)."""
    island_tile = current.island
    return find_random_place(
        current.entities,
        current.field,
        distance=2,
        far_from=far_from,
        avoid=lambda point: _inside_island(point, island_tile),
    )


def _split_floor_roster(
    roster: List[Tuple[str, int, int]], elf_floors: Dict[str, int]
) -> Tuple[
    List[Tuple[str, int, int]], List[Tuple[str, int, int]], List[Tuple[str, int, int]]
]:
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


def _spawn_island_chimera_pair(
    components: Tuple[set[d.Point], ...],
    entities: List[d.Entity],
    field: List[List[str]],
    reserved: Container[d.Point],
    floor_index: int,
    empowered: int,
) -> None:
    """Place each c beside a wall between the split room components."""
    first, second = components
    boundaries = []
    for room in first:
        for neighbor in (
            (room[0] - 1, room[1]),
            (room[0] + 1, room[1]),
            (room[0], room[1] - 1),
            (room[0], room[1] + 1),
        ):
            if neighbor in second:
                boundaries.append((room, neighbor))
    if not boundaries:
        raise ValueError("split room components must share a wall")

    room_a, room_b = rand.choice(boundaries)
    if room_a[1] == room_b[1]:
        wall_x = max(room_a[0], room_b[0]) * (d.TILE_WIDTH + 1)
        center_y = room_center(room_a)[1]
        points = [(wall_x - 2, center_y + 1), (wall_x + 2, center_y + 1)]
    else:
        wall_y = max(room_a[1], room_b[1]) * (d.TILE_HEIGHT + 1)
        center_x = room_center(room_a)[0]
        points = [(center_x + 1, wall_y - 2), (center_x + 1, wall_y + 2)]

    # Leave one floor cell between each c and the split wall so neither
    # occupies the passage endpoint. If a stair or entity occupies either
    # cell, move both along the wall while keeping that gap.
    offsets = [0, 1, -2, 2, -3, 3, -4]
    for offset in offsets:
        if room_a[1] == room_b[1]:
            candidate_points = [(x, y + offset) for x, y in points]
        else:
            candidate_points = [(x + offset, y) for x, y in points]
        if any(
            point in reserved
            or field[point[1]][point[0]] != d.CHAR_FLOOR
            or any((entity.x, entity.y) == point for entity in entities)
            for point in candidate_points
        ):
            continue
        for point in candidate_points:
            spawn_at(
                entities,
                *point,
                d.CHAR_TO_TRIBE["c"],
                empowered=empowered,
                origin_floor=floor_index,
            )
        return
    raise ValueError("could not place c beside the split room wall")


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
                _spawn(
                    entities, field, ch, reserved, island_tile, floor_index, empowered
                )


def _spawn_monsters_with_barriers(
    entries: List[Tuple[str, int, int]],
    entities: List[d.Entity],
    field: List[List[str]],
    reserved: Container[d.Point],
    down: d.Point,
    floor_index: int,
) -> None:
    for ch, count, empowered in entries:
        for monster_index in range(count):
            if ch == "W" and monster_index == 0:
                x, y = down
                entities.append(d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[ch], empowered))
            else:
                x, y = _spawn(
                    entities,
                    field,
                    ch,
                    reserved,
                    floor_index=floor_index,
                    empowered=empowered,
                )
            _place_barrier(field, (x, y))


def _place_roster_treasures_and_mimics(
    roster: List[Tuple[str, int, int]],
    entities: List[d.Entity],
    field: List[List[str]],
    reserved: Container[d.Point],
) -> None:
    treasure_bosses = list(
        dict.fromkeys(
            ch
            for ch, count, _ in roster
            if count
            and ch in d.CHAR_TO_MONSTER_TRIBE
            and (
                ch == "W"
                or d.CHAR_TO_MONSTER_TRIBE[ch].effect == d.EFFECT_UNLOCK_TREASURE
            )
        )
    )
    for boss_char in treasure_bosses:
        entities.append(
            d.Treasure(
                *_treasure_spot(entities, field, reserved),
                d.CHAR_TREASURE + boss_char,
            )
        )
    mimic_index = 0
    for ch, count, _ in roster:
        if ch == "M":
            for _ in range(count):
                mimic_boss_char = (
                    treasure_bosses[mimic_index % len(treasure_bosses)]
                    if treasure_bosses
                    else None
                )
                mimic = d.Monster(
                    *_treasure_spot(entities, field, reserved),
                    d.CHAR_TO_MONSTER_TRIBE["M"],
                    mimic_boss_char=mimic_boss_char,
                )
                mimic.active = False
                entities.append(mimic)
                mimic_index += 1


def _spawn_island_elf(
    field: List[List[str]], entities: List[d.Entity], island_tile: Optional[d.Point]
) -> None:
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
    experimental_stage = stage_num in (4, 5)
    floor_count = (
        d.STAGE5_FLOORS
        if stage_num == 5
        else d.STAGE4_FLOORS
        if stage_num == 4
        else d.STAGE3_FLOORS
    )
    island_count, filled_count = room_counts
    split_island_graph = stage_num == 4 and index in (1, 3)
    field, up, down, island_rooms, _, room_components = generate_floor_field(
        up_point if up_point is not None else entry_point,
        down_point,
        corridor_h_width,
        corridor_v_width,
        island_count,
        filled_count,
        split_room_graph=split_island_graph,
    )
    island_tile = next(iter(island_rooms), None)

    if index < floor_count - 1:
        field[down[1]][down[0]] = d.CHAR_STAIRS_DOWN
    if index:
        field[up[1]][up[0]] = d.CHAR_STAIRS_UP

    entities: List[d.Entity] = []
    reserved = {up, down}
    spawn_roster = [entry for entry in roster if entry[0] != "M"]
    if room_components:
        c_count = sum(count for ch, count, _ in spawn_roster if ch == "c")
        if c_count < len(room_components):
            raise ValueError("split Stage 4 floor needs one c per room component")
        c_to_remove = len(room_components)
        adjusted_roster = []
        for ch, count, empowered in spawn_roster:
            if ch == "c" and c_to_remove:
                removed = min(count, c_to_remove)
                count -= removed
                c_to_remove -= removed
            if count:
                adjusted_roster.append((ch, count, empowered))
        spawn_roster = adjusted_roster
    ordinary_roster, elf_roster, wyrm_roster = _split_floor_roster(
        spawn_roster, elf_floors
    )
    if room_components:
        island_chimera_rank = 2 if index == 1 else 3
        _spawn_island_chimera_pair(
            room_components,
            entities,
            field,
            reserved,
            index,
            island_chimera_rank,
        )
    _spawn_roster_entries(
        ordinary_roster, entities, field, reserved, island_tile, index
    )
    _spawn_island_elf(field, entities, island_tile)
    _spawn_assigned_floor_elves(
        elf_roster, elf_floors, index, entities, field, reserved, island_tile
    )
    _spawn_monsters_with_barriers(wyrm_roster, entities, field, reserved, down, index)
    _place_roster_treasures_and_mimics(roster, entities, field, reserved)

    for ch, assigned_floor in special_floors.items():
        if index == assigned_floor:
            _spawn(entities, field, ch, reserved, island_tile, index)

    return Floor(
        field=field,
        entities=entities,
        seen=[[0] * len(field[0]) for _ in field],
        up=up,
        down=up if experimental_stage and index == floor_count - 1 else down,
        island=island_tile,
        up_stairs=[up] if index else [],
        down_stairs=[down] if index < floor_count - 1 else [],
        room_components=room_components,
    )


def _treasure_spot(
    entities: List[d.Entity], field: List[List[str]], reserved: Container[d.Point]
) -> d.Point:
    while True:
        p = find_random_place(entities, field, distance=2)
        if p not in reserved:
            return p


def build(
    corridor_h_width: int = d.CORRIDOR_H_WIDTH,
    corridor_v_width: int = d.CORRIDOR_V_WIDTH,
    stage_num: int = 3,
    stair_pairs_per_transition: Optional[int] = None,
    floor_layout: Optional[List[Tuple[int, int]]] = None,
) -> Tuple[List[Floor], d.Player]:
    if stage_num not in (3, 4, 5):
        raise ValueError("multi-floor builder supports stages 3, 4, and 5")
    if stair_pairs_per_transition is None:
        stair_pairs_per_transition = (
            d.STAGE3_STAIR_PAIRS_PER_TRANSITION
            if stage_num == 3
            else d.STAGE5_STAIR_PAIRS_PER_TRANSITION
            if stage_num == 5
            else d.STAGE4_STAIR_PAIRS_PER_TRANSITION
        )
    if stair_pairs_per_transition < 1:
        raise ValueError("each floor transition needs at least one stair pair")
    floor_count = (
        d.STAGE5_FLOORS
        if stage_num == 5
        else d.STAGE4_FLOORS
        if stage_num == 4
        else d.STAGE3_FLOORS
    )
    default_layout = (
        d.STAGE3_FLOOR_LAYOUT
        if stage_num == 3
        else d.STAGE5_FLOOR_LAYOUT
        if stage_num == 5
        else d.STAGE4_FLOOR_LAYOUT
    )
    layout = list(default_layout if floor_layout is None else floor_layout)
    if stage_num == 4 and floor_layout is None:
        room_counts = list(d.STAGE4_FILLED_ROOM_COUNTS)
        shuffled_room_counts = []
        while room_counts:
            shuffled_room_counts.append(
                room_counts.pop(rand.randrange(len(room_counts)))
            )
        layout = [
            (islands, shuffled_room_counts[index])
            for index, (islands, _) in enumerate(layout)
        ]
    if len(layout) != floor_count:
        raise ValueError(f"floor_layout must contain {floor_count} entries")
    if any(islands < 0 or filled < 0 for islands, filled in layout):
        raise ValueError("room counts cannot be negative")
    if sum(islands for islands, _ in layout) > 1:
        raise ValueError("the multi-floor builder supports at most one isolated room")
    layout_by_floor = shuffle_floor_layout(layout)
    island_floor = next(
        (index for index, counts in enumerate(layout_by_floor) if counts[0]),
        None,
    )
    elf_floors: Dict[str, int] = {}
    if island_floor is not None:
        elf_floors["I"] = island_floor
    if stage_num == 3:
        elf_floors.update(
            {
                "J": rand.randrange(floor_count),
                "K": rand.randrange(d.STAGE3_FLOORS - 1),
                "H": rand.randrange(floor_count),
            }
        )
        special_floors = {
            ch: rand.randrange(floor_count) for ch in ("m", "X", "e", "g")
        }
        m_floor = special_floors.pop("m")
    elif stage_num in (4, 5):
        elf_floors.update(
            {
                "J": rand.randrange(floor_count),
                "K": rand.randrange(floor_count - 1),
                "H": rand.randrange(floor_count),
            }
        )
        if stage_num == 4:
            voe_options = list(range(1, floor_count - 1))
            v_floor = voe_options.pop(rand.randrange(len(voe_options)))
            e_floor = voe_options.pop(rand.randrange(len(voe_options)))
            voe_floors = {"V": v_floor, "E": e_floor}
        else:
            voe_floors = {
                char: rand.randrange(1, floor_count) for char in ("V", "E")
            }
        special_floors = {"g": rand.randrange(floor_count)}
        m_floor = None
    else:
        special_floors = {}
        m_floor = None

    stair_tiles: List[d.Point] = []
    if stage_num in (4, 5):
        tiles = [(x, y) for y in range(d.TILE_NUM_Y) for x in range(d.TILE_NUM_X)]
        stair_tiles.append(rand.choice(tiles))
        for _ in range(floor_count - 2):
            options = [tile for tile in tiles if tile != stair_tiles[-1]]
            stair_tiles.append(rand.choice(options))

    floors: List[Floor] = []
    entry_point = None
    for index in range(floor_count):
        up_point = None
        down_point = None
        if stage_num in (4, 5):
            up_point = None if index == 0 else room_center(stair_tiles[index - 1])
            down_point = (
                None if index == floor_count - 1 else room_center(stair_tiles[index])
            )
        roster = list(
            d.STAGE5_ROSTER[index]
            if stage_num == 5
            else d.STAGE4_ROSTER[index]
            if stage_num == 4
            else d.STAGE3_ROSTER[index]
        )
        roster = [entry for entry in roster if entry[0] not in {"I", "J", "K", "H"}]
        if stage_num == 3 and elf_floors["K"] == index:
            roster.append(("C", 1, 1))
        elif stage_num in (4, 5):
            roster = [entry for entry in roster if entry[0] not in {"V", "E"}]
            roster.extend(
                (char, 1, 1)
                for char, assigned_floor in voe_floors.items()
                if assigned_floor == index
            )
        roster.extend(
            (char, 1, 1)
            for char, assigned_floor in elf_floors.items()
            if char != "I" and assigned_floor == index
        )
        if index == m_floor:
            roster.append(("m", 2, 1))
        floor = _build_floor(
            index,
            special_floors,
            elf_floors,
            entry_point,
            corridor_h_width,
            corridor_v_width,
            layout_by_floor[index],
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
    if stage_num in (4, 5):
        _place_collapses(floors)
    if stage_num == 4:
        _place_stage4_final_floor_barriers(floors[-1])

    player = d.Player(floors[0].up[0], floors[0].up[1], 1, d.LP_INIT)
    player.stage3_elf_floors = {char: floor + 1 for char, floor in elf_floors.items()}
    return floors, player


def build_trap_test(
    corridor_h_width: int = d.CORRIDOR_H_WIDTH,
    corridor_v_width: int = d.CORRIDOR_V_WIDTH,
) -> Tuple[List[Floor], d.Player]:
    """Build a one-floor arena for manually exercising Stage 4 traps."""
    field, entry, wyrm_point = create_field(
        corridor_h_width,
        corridor_v_width,
        d.WALL_CHAR,
        margin_x=d.STAGE1_COLUMN_MARGIN,
    )
    wyrm = d.Monster(*wyrm_point, d.CHAR_TO_MONSTER_TRIBE["W"])
    entities: List[d.Entity] = [wyrm]
    _place_barrier(field, wyrm_point)
    reserved = {entry, wyrm_point}
    _place_roster_treasures_and_mimics(
        [("W", 1, 1), ("M", 1, 1)], entities, field, reserved
    )
    for _ in range(3):
        _spawn(entities, field, "b", reserved, floor_index=0)
        _spawn(entities, field, "d", reserved, floor_index=0)
    _spawn(entities, field, "V", reserved, floor_index=0)

    arena = Floor(
        field=field,
        entities=entities,
        seen=[[0] * len(field[0]) for _ in field],
        up=entry,
        down=wyrm_point,
        island=None,
    )
    player = d.Player(entry[0], entry[1], 150, d.LP_INIT)
    player.stage3_elf_floors = {}
    player.stage3_flags |= d.STAGE3_H_FLAG
    return [arena], player


def _transition_candidates(
    upper: Floor,
    lower: Floor,
    stairs_to_avoid: List[d.Point],
    allowed_rooms: Optional[Container[d.Point]] = None,
    avoid_stair_rooms: bool = True,
) -> List[d.Point]:
    """Return matching floor cells outside the stairs' and adjacent rooms."""
    stair_rooms = [tile_at(stair) for stair in stairs_to_avoid]
    candidates = []
    for y in range(1, d.FIELD_HEIGHT - 1):
        for x in range(1, d.FIELD_WIDTH - 1):
            if upper.field[y][x] != d.CHAR_FLOOR or lower.field[y][x] != d.CHAR_FLOOR:
                continue
            room = tile_at((x, y))
            if allowed_rooms is not None and room not in allowed_rooms:
                continue
            if avoid_stair_rooms and not all(
                abs(room[0] - stair_room[0]) + abs(room[1] - stair_room[1]) > 1
                for stair_room in stair_rooms
            ):
                continue
            candidates.append((x, y))
    return candidates


def _add_additional_stairs(floors: List[Floor], pair_count: int) -> None:
    """Add matching stair pairs up to the configured count per floor link."""
    if pair_count <= 1:
        return
    for index in range(len(floors) - 1):
        upper, lower = floors[index], floors[index + 1]
        split_floor = (
            lower
            if lower.room_components
            else upper
            if upper.room_components
            else None
        )
        target_rooms: Optional[Container[d.Point]] = None
        avoid_stair_rooms = True
        if split_floor is not None:
            primary_stair = lower.up if split_floor is lower else upper.down
            target_rooms = next(
                rooms
                for rooms in split_floor.room_components
                if tile_at(primary_stair) in rooms
            )
            avoid_stair_rooms = False
        candidates = [
            point
            for point in _transition_candidates(
                upper,
                lower,
                upper.down_stairs,
                allowed_rooms=target_rooms,
                avoid_stair_rooms=avoid_stair_rooms,
            )
            if point != upper.down and point != lower.up
        ]
        while candidates and len(upper.down_stairs) < pair_count:
            point = candidates.pop(rand.randrange(len(candidates)))
            if any(
                abs(entity.x - point[0]) <= 2 and abs(entity.y - point[1]) <= 2
                for entity in upper.entities
            ):
                continue
            if any(
                abs(entity.x - point[0]) <= 2 and abs(entity.y - point[1]) <= 2
                for entity in lower.entities
            ):
                continue
            upper.field[point[1]][point[0]] = d.CHAR_STAIRS_DOWN
            lower.field[point[1]][point[0]] = d.CHAR_STAIRS_UP
            upper.down_stairs.append(point)
            lower.up_stairs.append(point)
            candidates = [
                candidate
                for candidate in _transition_candidates(
                    upper,
                    lower,
                    upper.down_stairs,
                    allowed_rooms=target_rooms,
                    avoid_stair_rooms=avoid_stair_rooms,
                )
                if candidate != upper.down and candidate != lower.up
            ]


def _place_collapses(floors: List[Floor]) -> None:
    """Place at most one fixed Collapse on a random floor transition."""
    offsets = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]

    def has_wall_neighbors(field: List[List[str]], point: d.Point) -> bool:
        x, y = point
        return any(field[y + dy][x + dx] == d.WALL_CHAR for dx, dy in offsets)

    placement_options: List[Tuple[Floor, Floor, d.Point]] = []
    for upper, lower in zip(floors, floors[1:]):
        occupied_upper = {(entity.x, entity.y) for entity in upper.entities}
        occupied_lower = {(entity.x, entity.y) for entity in lower.entities}
        upper_fixed = {upper.up, upper.down, *upper.up_stairs, *upper.down_stairs}
        lower_fixed = {lower.up, lower.down, *lower.up_stairs, *lower.down_stairs}
        stair_points = upper.down_stairs + lower.up_stairs
        candidates = [
            point
            for point in _transition_candidates(upper, lower, stair_points)
            if point not in occupied_upper
            and point not in occupied_lower
            and point not in upper_fixed
            and point not in lower_fixed
            and point not in upper.collapse_landings
            and point not in lower.collapse_landings
            and not has_wall_neighbors(upper.field, point)
            and not has_wall_neighbors(lower.field, point)
        ]
        placement_options.extend((upper, lower, point) for point in candidates)

    if placement_options:
        upper, lower, point = rand.choice(placement_options)
        upper.entities.append(d.Collapse(*point))
        lower.collapse_landings.add(point)


def _build_single_floor(
    config: GameConfig, stage_num: int
) -> Tuple[List[Floor], d.Player]:
    """Create the Stage 1/2 map inside the shared floor state model."""
    spawn_config = d.STAGE_TO_SPAWN_CONFIGS[stage_num - 1]
    field, entry, treasure_point = create_field(
        config.corridor_h_width,
        config.corridor_v_width,
        d.WALL_CHAR,
        margin_x=d.STAGE1_COLUMN_MARGIN if stage_num == 1 else 0,
    )
    entities: List[d.Entity] = []
    treasure_tribes = [
        spawn.tribe
        for spawn in spawn_config
        if isinstance(spawn.tribe, d.MonsterTribe)
        and spawn.tribe.effect == d.EFFECT_UNLOCK_TREASURE
    ]
    assert len(treasure_tribes) == 1
    entities.append(
        d.Treasure(
            *treasure_point,
            d.CHAR_TREASURE + treasure_tribes[0].char,
        )
    )
    player = d.Player(*entry, 1, d.LP_INIT)
    entities.append(player)
    spawn_entities(entities, field, spawn_config)
    floor = Floor(
        field=field,
        entities=entities,
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=entry,
        down=treasure_point,
        island=None,
    )
    # Legacy update_entities expects the player in the shared entity list.
    floor.entities.append(player)
    return [floor], player
