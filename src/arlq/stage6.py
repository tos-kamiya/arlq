"""Stage 6 dungeon generation."""

from collections import deque

from . import defs as d, stage56
from .arlq import GameConfig, iterate_ellipse_points
from .stage56 import _open_points
from .stage_maze import generate_floor_field, tile_at as maze_tile_at
from .stage_types import Floor
from .stage_world import (
    _add_filled_room_wall_notches,
    _add_wall_spurs,
    _place_collapses,
    _place_final_floor_barriers,
)
from .utils import player_spawn_exclusion, rand


MAX_STAGE_GENERATION_RETRIES = 5


class _BossRouteNotFound(RuntimeError):
    pass


def tile_at(point: d.Point) -> d.Point:
    return maze_tile_at(point, d.TILE_WIDTH)


def sample_party_size(floor_index: int) -> int:
    weights = d.STAGE6_PARTY_SIZE_WEIGHTS[floor_index]
    roll = rand.randrange(sum(weights))
    for size, weight in enumerate(weights, 1):
        if roll < weight:
            return size
        roll -= weight
    raise AssertionError("invalid party weights")


def _in_detached_terminal_room(current: Floor, point: d.Point) -> bool:
    return any(
        len(component) == 1 and tile_at(point) in component
        for component in current.room_components
    )


def _place_detached_room_monsters(
    current: Floor, room_components: tuple[set[d.Point], ...], *,
    avoid: set[d.Point] | None = None,
) -> list[d.Monster]:
    detached = next(
        (component for component in room_components if len(component) == 1), None
    )
    if detached is None:
        raise ValueError("Stage 6 floor needs one detached terminal room")
    points = [point for point in _open_points(current)
              if tile_at(point) in detached and point not in (avoid or set())]
    if len(points) < 2:
        if avoid:
            return []
        raise RuntimeError("detached Stage 6 room needs two open cells")
    existing_monsters = [
        entity for entity in current.entities if isinstance(entity, d.Monster)
    ]
    points = [
        point
        for point in points
        if all(
            max(abs(point[0] - monster.x), abs(point[1] - monster.y)) > 1
            for monster in existing_monsters
        )
    ]
    point_pairs = [
        (first, second)
        for index, first in enumerate(points)
        for second in points[index + 1 :]
        if max(abs(first[0] - second[0]), abs(first[1] - second[1])) > 1
    ]
    if not point_pairs:
        if avoid:
            return []
        raise RuntimeError("detached Stage 6 room needs two separated open cells")
    points = rand.choice(point_pairs)
    candidates = [("b", 1), ("b", 2), ("f", 1)]
    if rand.randrange(2) == 0:
        candidates.append(("A", 1))
    if rand.randrange(2) == 0:
        candidates.append(("c", 1))
    roster = []
    for _ in range(2):
        weighted = [variant for variant in candidates
                    for _ in range(1 if variant[0] == "b" else 2)]
        choice = rand.choice(weighted)
        candidates.remove(choice)
        roster.append(choice)
    monsters = [
        d.Monster(*point, d.CHAR_TO_MONSTER_TRIBE[char], empowered=empowered)
        for point, (char, empowered) in zip(points, roster, strict=True)
    ]
    current.entities.extend(monsters)
    return monsters


def _place_party(
    current: Floor,
    roster: list[tuple[str, int]],
    floor_index: int = 0,
    *,
    room: d.Point | None = None,
    respect_spawn_blocks: bool = False,
    avoid: set[d.Point] | None = None,
) -> None:
    # Keep parties separate horizontally and vertically. Members of each
    # party are placed vertically; walls and narrow corridors may be blocked.
    occupied = {(entity.x, entity.y) for entity in current.entities}
    monsters = {
        (entity.x, entity.y)
        for entity in current.entities
        if isinstance(entity, d.Monster)
    }
    candidates = {point for point in _open_points(current) if point not in (avoid or set())
                  if roster[0][0] == "b" or not _in_detached_terminal_room(current, point)}
    if any(char == d.STAGE6_BOSS_PARTY[0][0] for char, _ in roster):
        connected_rooms = set().union(
            *(component for component in current.room_components if len(component) > 1)
        )
        candidates = {point for point in candidates if tile_at(point) in connected_rooms}
    if respect_spawn_blocks:
        candidates = {point for point in candidates
                      if tile_at(point) not in current.monster_spawn_blocked_rooms}
    if room is not None:
        candidates = {point for point in candidates if tile_at(point) == room}
    candidates = {
        point
        for point in candidates
        if all(
            (point[0] + dx, point[1] + dy) not in monsters
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        )
    }
    if floor_index == 1:
        # Marksmen are dangerous enough alone. Do not let this party touch an
        # existing one, and keep later parties out of its cardinal neighbors.
        marksmen = {
            (entity.x, entity.y)
            for entity in current.entities
            if isinstance(entity, d.Monster) and entity.tribe.char == "k"
        }
        if roster[0][0] == "k" and len(roster) != 1:
            raise ValueError("Stage 6 floor-2 marksmen must spawn alone")
        if marksmen:
            candidates = {
                point
                for point in candidates
                if all(
                    (point[0] + dx, point[1] + dy) not in marksmen
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                )
            }
    while candidates:
        seeds = sorted(
            point for point in candidates if room is None or tile_at(point) == room
        )
        if not seeds:
            break
        seed = rand.choice(seeds)
        cells = [seed]
        while len(cells) < len(roster):
            frontier = sorted(
                {(x + dx, y + dy) for x, y in cells for dx, dy in ((0, -1), (0, 1))}
                & candidates - set(cells) - occupied
            )
            if any(char == d.STAGE6_BOSS_PARTY[0][0] for char, _ in roster):
                frontier = [point for point in frontier if tile_at(point) == tile_at(seed)]
            if not frontier:
                break
            cells.append(rand.choice(frontier))
        if len(cells) == len(roster):
            for (x, y), (char, rank) in zip(cells, roster):
                current.entities.append(
                    d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[char], rank)
                )
            return
        # This component cannot fit the party; try another without requiring
        # any clearance from walls.
        candidates.difference_update(cells)
    raise RuntimeError("could not place Stage 6 monster party")


def _party_roster(char: str, rank: int, floor_index: int) -> list[tuple[str, int]]:
    size = (
        1 if char in ("g", "c") or (char == "B" and rank == 3)
        or (floor_index > 0 and char == "k")
        else sample_party_size(floor_index)
    )
    return [(char, rank)] + [
        rand.choice(d.STAGE6_SUPPORT_POOLS[floor_index]) for _ in range(size - 1)
    ]


def _place_initial_boss_party(current: Floor) -> tuple[list[d.Monster], set[d.Point]]:
    """Choose the boss layout before placing other entities."""
    _place_party(current, list(d.STAGE6_BOSS_PARTY), d.STAGE6_FLOORS - 1)
    current.entities[-len(d.STAGE6_BOSS_PARTY)].boss_id = 1
    return current.entities[-len(d.STAGE6_BOSS_PARTY):], set()


def _place_initial_parties(
    current: Floor, floor_index: int, excluded_room: d.Point | None = None
) -> dict[tuple[str, int], int]:
    available = set().union(*current.room_components) - {excluded_room}
    rooms = [
        room for room in d.STAGE6_INITIAL_PARTY_ROOMS
        if room in available or (room[0] + 1, room[1]) in available
    ]
    shuffled = []
    while rooms:
        shuffled.append(rooms.pop(rand.randrange(len(rooms))))
    shuffled.sort(key=lambda room: not any(
        len(component) == 1 and room in component for component in current.room_components
    ))
    leaders = [
        (char, rank)
        for char, rank in d.STAGE6_INITIAL_PARTY_PRIORITY
        for roster_char, count, roster_rank in d.STAGE6_ROSTER[floor_index]
        if (char, rank) == (roster_char, roster_rank)
        for _ in range(min(count, 4 if char == "b" else count))
    ]
    placed = {}
    used_rooms = set()
    for room in shuffled:
        if sum(placed.values()) >= len(leaders):
            break
        char, rank = leaders[sum(placed.values())]
        roster = _party_roster(char, rank, floor_index)
        for candidate in (room, (room[0] + 1, room[1])):
            if candidate not in available or candidate in used_rooms:
                continue
            try:
                _place_party(current, roster, floor_index, room=candidate)
            except RuntimeError:
                continue
            used_rooms.add(candidate)
            placed[(char, rank)] = placed.get((char, rank), 0) + 1
            break
    return placed


def _can_join_at(current: Floor, monster: d.Monster, point: d.Point, *,
                 isolated: bool = False) -> bool:
    positions = stage56.monster_positions(current.entities)
    positions = {pos: other for pos, other in positions.items() if other is not monster}
    x, y = point
    if any((x + dx, y + dy) in positions
           for dx in (-1, 1) for dy in (-1, 0, 1)):
        return False
    party = set()
    for neighbor_point in ((x, y - 1), (x, y + 1)):
        neighbor = positions.get(neighbor_point)
        if neighbor is not None:
            party.update(stage56.monster_party_entities(current.entities, neighbor, positions=positions))
    boss_party = any(other.tribe.char == d.STAGE6_BOSS_PARTY[0][0] for other in party)
    return not party or not (
        isolated or stage56.special_monster(monster)
        or any(stage56.special_monster(other)
               and not (boss_party and other.tribe.char in (d.STAGE6_BOSS_PARTY[0][0], "V"))
               for other in party)
        or len(party) + 1 > d.STAGE6_MONSTER_PARTY_LIMIT
    )


def spawn_monster(current: Floor, floor_index: int, *,
                  avoid: set[d.Point] | None = None,
                  player_position: d.Point | None = None,
                  variant: tuple[str, int] | None = None,
                  isolated: bool = False,
                  prefer_adjacent: bool = True) -> bool:
    """Try distinct positions for one independently drawn monster."""
    if variant is None:
        # Doubling the other weights lets odd weights be halved exactly.
        reduced = set(d.STAGE6_REDUCED_SPAWN_VARIANTS)
        if floor_index == 1:
            reduced.update(d.STAGE6_FLOOR2_REDUCED_SPAWN_VARIANTS)
        pool = [(char, rank) for char, count, rank in d.STAGE6_ROSTER[floor_index]
                for _ in range(count * (1 if (char, rank) in reduced else 2))]
        variant = rand.choice(pool)
    char, rank = variant
    candidates = [point for point in _open_points(current)
                  if point not in (avoid or set()) and not _in_bridgehead(current, point)
                  and tile_at(point) not in current.monster_spawn_blocked_rooms]
    monster = d.Monster(0, 0, d.CHAR_TO_MONSTER_TRIBE[char], rank)
    positions = stage56.monster_positions(current.entities)
    prioritize = (prefer_adjacent and not isolated and not stage56.special_monster(monster)
                  and bool(candidates) and rand.randrange(100) < d.STAGE6_PARTY_SPAWN_PERCENT)
    if prioritize:
        nearby = [point for point in candidates
                  if ((point[0], point[1] - 1) in positions
                      or (point[0], point[1] + 1) in positions)]
        attempts = ((nearby, d.STAGE6_PARTY_SPAWN_ATTEMPTS),
                    (candidates, d.STAGE6_SPAWN_ATTEMPTS - d.STAGE6_PARTY_SPAWN_ATTEMPTS))
    else:
        attempts = ((candidates, d.STAGE6_SPAWN_ATTEMPTS),)
    for choices, limit in attempts:
        for _ in range(min(limit, len(choices))):
            point = choices.pop(rand.randrange(len(choices)))
            if choices is not candidates:
                candidates.remove(point)
            x, y = point
            monster = d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[char], rank)
            if not _can_join_at(current, monster, point, isolated=isolated):
                continue
            current.entities.append(monster)
            if stage56._barrier_offsets(monster):
                stage56.place_monster_barriers(current, monster, player_position)
            return True
    return False


def advance_spawns(
    floors: list[Floor], player: d.Player, floor_index: int, turn: int,
) -> list[tuple[int, d.Monster]]:
    """Attempt one spawn on each floor at fixed intervals."""
    spawned = []
    if (turn + 1) % d.STAGE6_SPAWN_INTERVAL:
        return spawned
    for index, current in enumerate(floors):
        avoid = player_spawn_exclusion((player.x, player.y)) if index == floor_index else set()
        if spawn_monster(current, index, avoid=avoid,
                         player_position=(player.x, player.y) if index == floor_index else None):
            monster = current.entities[-1]
            current.respawn_glows[monster.x, monster.y] = d.RESPAWN_GLOW_TURNS
            spawned.append((index, monster))
    return spawned


def build(config: GameConfig | None = None) -> tuple[list[Floor], d.Player]:
    for _ in range(MAX_STAGE_GENERATION_RETRIES + 1):
        try:
            return _build_once(config)
        except _BossRouteNotFound:
            continue
    raise RuntimeError(
        f"could not generate a Stage 6 route to the boss after {MAX_STAGE_GENERATION_RETRIES} retries"
    )


def _build_once(config: GameConfig | None = None) -> tuple[list[Floor], d.Player]:
    config = config or GameConfig()
    floors = []
    initial_boss_party = []
    boss_entrance = set()
    boss_reserved = set()
    boss_barrier_area = None
    boss_barrier_half_density = set()
    entry = None
    member_roles = list(d.RECRUITABLE_MEMBER_ROLES)
    while len(member_roles) > 4:
        member_roles.pop(rand.randrange(len(member_roles)))
    filled_counts_by_floor = [0] + [
        rand.choice((0, 1, 2)) for _ in range(d.STAGE6_FLOORS - 1)
    ]
    for index in range(d.STAGE6_FLOORS):
        (
            field,
            up,
            down,
            _,
            filled_rooms,
            room_components,
            split_edge,
        ) = generate_floor_field(
            entry,
            None,
            config.corridor_h_width,
            config.corridor_v_width,
            0,
            filled_counts_by_floor[index],
            extra_corridors=d.STAGE6_EXTRA_CORRIDORS,
            split_room_graph=index < d.STAGE6_FLOORS - 1,
            detach_leaf_room=index < d.STAGE6_FLOORS - 1,
            tile_width=d.TILE_WIDTH,
        )
        if index == d.STAGE6_FLOORS - 1:
            room_components = ({(x, y) for y in range(d.TILE_NUM_Y)
                                for x in range(d.TILE_NUM_X)} - set(filled_rooms),)
        if index >= 2:
            _add_wall_spurs(field, up, down, None, filled_rooms, d.TILE_WIDTH)
        _add_filled_room_wall_notches(field, filled_rooms, d.TILE_WIDTH)
        if index:
            field[up[1]][up[0]] = d.CHAR_STAIRS_UP
        if index < d.STAGE6_FLOORS - 1:
            field[down[1]][down[0]] = d.CHAR_STAIRS_DOWN
        current = Floor(
            field,
            [],
            [[0] * len(field[0]) for _ in field],
            up,
            down,
            None,
            up_stairs=[up] if index else [],
            down_stairs=[down] if index < d.STAGE6_FLOORS - 1 else [],
            room_components=room_components,
        )
        if index == 0:
            current.monster_spawn_blocked_rooms.add(tile_at(up))
        if split_edge is not None:
            (x1, y1), (x2, y2) = split_edge
            if y1 == y2:
                gate = (
                    d.FIELD_X_MARGIN + max(x1, x2) * (d.TILE_WIDTH + 1),
                    y1 * (d.TILE_HEIGHT + 1)
                    + 1
                    + (d.TILE_HEIGHT + 1 - config.corridor_h_width) // 2
                    + config.corridor_h_width // 2,
                )
            else:
                gate = (
                    d.FIELD_X_MARGIN + x1 * (d.TILE_WIDTH + 1)
                    + 1
                    + (d.TILE_WIDTH + 1 - config.corridor_v_width) // 2
                    + config.corridor_v_width // 2,
                    max(y1, y2) * (d.TILE_HEIGHT + 1),
                )
            current.field[gate[1]][gate[0]] = d.CHAR_HIDDEN_D_GATE
        boss_room = None
        if index == d.STAGE6_FLOORS - 1:
            initial_boss_party, boss_entrance = _place_initial_boss_party(current)
            boss = initial_boss_party[0]
            horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
            vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
            barrier_radius = round(vortex_radius * d.STAGE6_BARRIER_VORTEX_RADIUS_MULTIPLIER)
            boss_barrier_area = set(iterate_ellipse_points(
                boss.x, boss.y, barrier_radius, d.FOV_WIDTH_EXPANSION_RATIO
            ))
            inner_area = set(iterate_ellipse_points(
                boss.x, boss.y, round(vortex_radius * 0.6), d.FOV_WIDTH_EXPANSION_RATIO
            ))
            middle_area = set(iterate_ellipse_points(
                boss.x, boss.y, round(vortex_radius * 1.2), d.FOV_WIDTH_EXPANSION_RATIO
            ))
            boss_barrier_half_density = middle_area - inner_area
            boss_room = tile_at((boss.x, boss.y))
            boss_reserved = {
                (x, y) for y, row in enumerate(current.field) for x in range(len(row))
                if tile_at((x, y)) == boss_room
            }
            current.respawn_exclusions.update(boss_reserved)
        # Reserve a sword carrier on each floor, then seed the detached room.
        initial_avoid = player_spawn_exclusion(up) if index == 0 else set()
        try:
            _place_party(current, [("c", 1)], index, respect_spawn_blocks=True, avoid=initial_avoid)
        except RuntimeError:
            pass
        if index < d.STAGE6_FLOORS - 1:
            _place_detached_room_monsters(current, room_components, avoid=initial_avoid)
        # Retain the former Loop Fairy's random draw for seeded generation.
        rand.choice(_open_points(current))
        for char in ("n", "o", "p"):
            current.entities.append(
                d.Fairy(
                    *rand.choice(_open_points(current)),
                    d.CHAR_TO_TRIBE[char],
                    origin_floor=index,
                )
            )
        if index == d.STAGE6_FLOORS - 1:
            mimic = d.Monster(
                *rand.choice([point for point in _open_points(current)
                              if not _in_detached_terminal_room(current, point)
                              and tile_at(point) not in current.monster_spawn_blocked_rooms]),
                d.CHAR_TO_MONSTER_TRIBE["M"],
                mimic_boss_char=d.STAGE6_BOSS_PARTY[0][0],
                mimic_boss_empowered=d.STAGE6_BOSS_PARTY[0][1],
                boss_id=1,
            )
            mimic.active = False
            current.entities.append(mimic)
        if index == d.STAGE6_FLOORS - 1:
            boss = next(
                entity
                for entity in current.entities
                if isinstance(entity, d.Monster) and entity.tribe.char == d.STAGE6_BOSS_PARTY[0][0]
            )
            boss_zone = tile_at((boss.x, boss.y))
            treasure_points = [
                point for point in _open_points(current) if tile_at(point) != boss_zone
            ]
            current.entities.append(d.Treasure(*rand.choice(treasure_points), "T" + d.STAGE6_BOSS_PARTY[0][0], boss_id=1))
        for char, count in zip(
            (d.CHAR_CALTROP, d.CHAR_BARRIER), d.STAGE6_HAZARD_COUNTS[index]
        ):
            for _ in range(count):
                candidates = _open_points(current)
                if index == d.STAGE6_FLOORS - 1 and char == d.CHAR_BARRIER:
                    candidates = [point for point in candidates if point in boss_barrier_area]
                if not candidates:
                    break
                x, y = rand.choice(candidates)
                current.field[y][x] = char
                if char == d.CHAR_BARRIER:
                    current.persistent_barriers.add((x, y))
        floors.append(current)
        entry = down
    _place_collapses(floors, d.TILE_WIDTH)
    _place_additional_stairs(floors)
    _place_final_floor_barriers(
        floors[-1], d.STAGE6_FINAL_FLOOR_BARRIER_PERCENT,
        protected_points=boss_entrance, allowed_points=boss_barrier_area,
    )
    for x, y in sorted(floors[-1].persistent_barriers & boss_barrier_half_density):
        if rand.randrange(2):
            floors[-1].persistent_barriers.remove((x, y))
            floors[-1].field[y][x] = d.CHAR_FLOOR
    for x, y in boss_entrance:
        floors[-1].field[y][x] = d.CHAR_FLOOR
    player = d.Player(*floors[0].up, 1, d.LP_INIT)
    player.stage6_candidates = True
    radius = _bridgehead_known_radius()
    current = floors[0]
    _place_bridgehead(current, current.up)
    for x, y in iterate_ellipse_points(
        *current.bridgehead, radius, d.FOV_WIDTH_EXPANSION_RATIO
    ):
        current.seen[y][x] = 1
    for role in member_roles:
        point = _candidate_near_bridgehead(current, current.up)
        current.entities.append(d.PartyMember(*point, role, origin_floor=0))
    _balance_boss_route(floors, (player.x, player.y), (boss.x, boss.y))
    for current in floors:
        stage56.initialize_monster_barriers(current)
    floors[-1].respawn_exclusions.difference_update(boss_reserved)
    for index, current in enumerate(floors):
        for _ in range(d.STAGE6_INITIAL_SPAWN_DRAWS[index]):
            avoid = player_spawn_exclusion((player.x, player.y)) if index == 0 else set()
            spawn_monster(current, index, avoid=avoid, prefer_adjacent=False,
                          player_position=(player.x, player.y) if index == 0 else None)
    for current in floors:
        current.respawn_glows.clear()
    player.rescue_stage = True
    player.treasure_stage = True
    return floors, player


def _bridgehead_known_radius() -> int:
    horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
    vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
    return round(vortex_radius * d.STAGE6_BRIDGEHEAD_KNOWN_VORTEX_RATIO)


def _place_bridgehead(current: Floor, anchor: d.Point) -> None:
    reachable = _reachable_floor_points(current, anchor)
    open_points = set(_open_points(current)) & reachable
    choices = [
        (x, y) for x, y in open_points
        if all((x + dx, y) in open_points for dx in range(2))
    ]
    if not choices:
        raise RuntimeError("no space for stage 6 bridgehead")
    x, y = min(choices, key=lambda p: (abs(p[0] - anchor[0]) + abs(p[1] - anchor[1]), p))
    current.bridgehead = (x, y)
    for dx, char in enumerate("/\\"):
        current.decor[y][x + dx] = d.DECOR_BRIDGEHEAD_PREFIX + char


def _candidate_near_bridgehead(
    current: Floor, anchor: d.Point, excluded: d.Point | None = None
) -> d.Point:
    bridgehead = current.bridgehead or anchor
    reachable = _reachable_floor_points(current, anchor)
    points = [p for p in _open_points(current) if p in reachable and p != excluded
              and not _in_bridgehead(current, p)]
    if not points:
        raise RuntimeError("no space near stage 6 bridgehead")
    nearby = [p for p in points if abs(p[0] - bridgehead[0]) + abs(p[1] - bridgehead[1]) <= 7]
    if nearby:
        return rand.choice(nearby)
    return min(points, key=lambda p: (abs(p[0] - bridgehead[0]) + abs(p[1] - bridgehead[1]), p))


def _in_bridgehead(current: Floor, point: d.Point) -> bool:
    if current.bridgehead is None:
        return False
    x, y = current.bridgehead
    return x <= point[0] < x + 2 and point[1] == y


def recover_at_bridgehead(
    floors: list[Floor], player: d.Player, floor_index: int,
    previous_floor: int, previous_point: d.Point,
) -> bool:
    """Restore LP on entry and report whether the player entered the bridgehead."""
    entered = (floor_index == 0
               and _in_bridgehead(floors[0], (player.x, player.y))
               and (previous_floor != 0 or not _in_bridgehead(floors[0], previous_point)))
    if entered:
        player.lp = max(player.lp, d.STAGE6_BRIDGEHEAD_RECOVERY_LP)
    return entered


def _balance_boss_route(floors: list[Floor], start: d.Point, boss: d.Point) -> None:
    """Balance parties along a shortest initial route using ordinary stairs."""
    origin = (0, start)
    goal = (len(floors) - 1, boss)
    previous = {origin: None}
    pending = deque([origin])
    pits = [
        {(entity.x, entity.y) for entity in floor.entities if isinstance(entity, d.Collapse)}
        for floor in floors
    ]
    while pending and goal not in previous:
        index, (x, y) = pending.popleft()
        current = floors[index]
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            point = (x + dx, y + dy)
            nx, ny = point
            if not (0 <= ny < len(current.field) and 0 <= nx < len(current.field[ny])):
                continue
            if (point in pits[index] or current.field[ny][nx] in (
                    *d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE, d.CHAR_D_GATE, d.CHAR_COLLAPSE)):
                continue
            dest_index, dest = index, point
            if index + 1 < len(floors) and point in current.down_stairs:
                dest_index += 1
                dest = floors[dest_index].up_stairs[current.down_stairs.index(point)]
            elif index > 0 and point in current.up_stairs:
                dest_index -= 1
                dest = floors[dest_index].down_stairs[current.up_stairs.index(point)]
            next_state = (dest_index, dest)
            if next_state not in previous:
                previous[next_state] = ((index, (x, y)), point)
                pending.append(next_state)
    if goal not in previous:
        raise _BossRouteNotFound("no initial route to the Stage 6 boss")
    route = []
    state = goal
    while state is not None:
        route.append(state)
        link = previous[state]
        state = link[0] if link is not None else None
    route.reverse()
    _balance_route_parties(floors, route)

def _balance_route_parties(floors, route):
    """Order equal-sized parties by initial walking progress and detour distance."""
    for index, current in enumerate(floors):
        distances = {}
        pending = deque()
        for step, (floor_index, point) in enumerate(route):
            if floor_index == index:
                distances[point] = (0, step / max(1, len(route) - 1))
                pending.append(point)
        while pending:
            x, y = pending.popleft()
            distance, progress = distances[x, y]
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                point = (x + dx, y + dy)
                px, py = point
                if (point not in distances and 0 <= py < len(current.field)
                        and 0 <= px < len(current.field[py])
                        and current.field[py][px] not in (
                            *d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE, d.CHAR_D_GATE)):
                    distances[point] = (distance + 1, progress)
                    pending.append(point)
        groups = {}
        checked = set()
        for entity in current.entities:
            if not isinstance(entity, d.Monster) or entity in checked:
                continue
            party = stage56.monster_party(current, entity)
            checked.update(party)
            if (not party or any(e.tribe.char in (d.STAGE6_BOSS_PARTY[0][0], "V", "M", "c", d.CHAR_COLLAPSE)
                                 or not e.active for e in party)
                    or any((e.x, e.y) not in distances for e in party)):
                continue
            party.sort(key=lambda e: (e.x, e.y))
            groups.setdefault(len(party), []).append(party)
        for parties in groups.values():
            slots = [[(e.x, e.y) for e in party] for party in parties]
            slots.sort(key=lambda cells: sum(
                distances[p][1] * 180 + min(distances[p][0], 40) * 3
                for p in cells) / len(cells))
            parties.sort(key=lambda party: sum(d.monster_level(e) for e in party))
            for party, cells in zip(parties, slots):
                for entity, (x, y) in zip(party, cells):
                    entity.x, entity.y = x, y


def scatter_members_on_new_route(floors, player, from_floor, from_point, to_floor):
    route = tuple(sorted(((from_floor, from_point), (to_floor, (player.x, player.y)))))
    if route == player.last_member_scatter_route:
        return
    player.last_member_scatter_route = route
    scatter_waiting_members(floors, player, to_floor)


def scatter_waiting_members(floors, player, player_floor):
    waiting = [(index, entity) for index, current in enumerate(floors)
               for entity in current.entities if isinstance(entity, d.PartyMember)]
    for old_index, member in waiting:
        options = []
        for index, current in enumerate(floors):
            reachable = _reachable_floor_points(current, current.up)
            reserved = set(current.up_stairs) | set(current.down_stairs)
            points = [point for point in _open_points(current)
                      if point in reachable and point not in reserved
                      and not _in_bridgehead(current, point)
                      and (index != player_floor or point != (player.x, player.y))]
            if points:
                options.append((index, points))
        if not options:
            continue
        index, points = rand.choice(options)
        floors[old_index].entities.remove(member)
        member.x, member.y = rand.choice(points)
        member.origin_floor = index
        player.known_member_floors.pop(member.role, None)
        floors[index].entities.append(member)


def relocate_candidates(floors, player, candidates, player_floor=None):
    for member in candidates:
        if (member.role == d.MEMBER_JESTER
                and (player.jester_retired or player.level >= d.JESTER_DEPARTURE_LEVEL)):
            player.known_member_floors.pop(member.role, None)
            continue
        current = floors[0]
        excluded = (player.x, player.y) if player_floor == 0 else None
        member.x, member.y = _candidate_near_bridgehead(current, current.up, excluded)
        member.origin_floor = 0
        player.known_member_floors.pop(member.role, None)
        current.entities.append(member)


def _reachable_floor_points(current: Floor, entry: d.Point) -> set[d.Point]:
    reachable = {entry}
    pending = [entry]
    while pending:
        x, y = pending.pop()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            point = (x + dx, y + dy)
            px, py = point
            if (
                point not in reachable
                and 0 <= py < len(current.field)
                and 0 <= px < len(current.field[py])
                and current.field[py][px] not in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
            ):
                reachable.add(point)
                pending.append(point)
    return reachable


def _choose_stair_point(
    candidates: list[d.Point], used_sections: set[d.Point], retries: int = 20
) -> d.Point:
    """Prefer a new room section, retrying random choices before fallback."""
    for _ in range(retries):
        point = rand.choice(candidates)
        if tile_at(point) not in used_sections:
            return point
    distinct_section_candidates = [
        point for point in candidates if tile_at(point) not in used_sections
    ]
    return rand.choice(distinct_section_candidates or candidates)


def _place_additional_stairs(floors: list[Floor]) -> None:
    """Add a second ordinary paired staircase on half of floor transitions."""
    for upper, lower in zip(floors[1:], floors[2:]):
        if rand.randrange(2) == 0:
            continue
        occupied_upper = {(entity.x, entity.y) for entity in upper.entities}
        occupied_lower = {(entity.x, entity.y) for entity in lower.entities}
        fixed = {
            upper.up,
            upper.down,
            *upper.up_stairs,
            *upper.down_stairs,
            *upper.collapse_landings,
            lower.up,
            lower.down,
            *lower.up_stairs,
            *lower.down_stairs,
            *lower.collapse_landings,
        }
        fixed.update(upper.respawn_exclusions | lower.respawn_exclusions)
        fixed.update(
            point
            for current in (upper, lower)
            for entity in current.entities
            if isinstance(entity, d.Collapse)
            for point in d.collapse_footprint((entity.x, entity.y))
        )
        entry = upper.up_stairs[-1] if upper.up_stairs else upper.up
        reachable = _reachable_floor_points(upper, entry)
        lower_reachable = _reachable_floor_points(lower, lower.up)
        candidates = [
            (x, y)
            for y, row in enumerate(upper.field)
            for x, cell in enumerate(row)
            if cell == d.CHAR_FLOOR
            and lower.field[y][x] == d.CHAR_FLOOR
            and (x, y) in reachable
            and (x, y) in lower_reachable
            and not _in_detached_terminal_room(upper, (x, y))
            and not _in_detached_terminal_room(lower, (x, y))
            and (x, y) not in fixed | occupied_upper | occupied_lower
            and all(
                abs(x - sx) + abs(y - sy) > 1
                for current in (upper, lower)
                for sx, sy in current.up_stairs + current.down_stairs
            )
        ]
        used_sections = {tile_at(point) for point in upper.down_stairs}
        point = _choose_stair_point(candidates, used_sections)
        upper.down_stairs.append(point)
        lower.up_stairs.append(point)
        x, y = point
        upper.field[y][x] = d.CHAR_STAIRS_DOWN
        lower.field[y][x] = d.CHAR_STAIRS_UP
