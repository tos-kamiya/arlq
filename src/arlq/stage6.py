"""Stage 6 dungeon generation."""

from collections import deque

from . import defs as d, stage56
from .arlq import GameConfig, iterate_ellipse_points
from .stage56 import (
    _open_points,
    normalize_parties,
)
from .stage_maze import generate_floor_field, tile_at as maze_tile_at
from .stage_types import Floor
from .stage_world import (
    _add_filled_room_wall_notches,
    _add_wall_spurs,
    _place_collapses,
    _place_final_floor_barriers,
)
from .utils import rand


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
    current: Floor, room_components: tuple[set[d.Point], ...]
) -> list[d.Monster]:
    detached = next(
        (component for component in room_components if len(component) == 1), None
    )
    if detached is None:
        raise ValueError("Stage 6 floor needs one detached terminal room")
    points = [point for point in _open_points(current) if tile_at(point) in detached]
    if len(points) < 2:
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
        raise RuntimeError("detached Stage 6 room needs two separated open cells")
    points = rand.choice(point_pairs)
    candidates = [("b", 1), ("b", 2), ("A", 1)]
    roster = []
    for _ in range(2):
        choice = rand.choice(candidates)
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
) -> None:
    # Keep parties separate horizontally and vertically. Members of each
    # party are placed vertically; walls and narrow corridors may be blocked.
    occupied = {(entity.x, entity.y) for entity in current.entities}
    monsters = {
        (entity.x, entity.y)
        for entity in current.entities
        if isinstance(entity, d.Monster)
    }
    candidates = {point for point in _open_points(current)
                  if roster[0][0] == "b" or not _in_detached_terminal_room(current, point)}
    if any(char == "W" for char, _ in roster):
        connected_rooms = set().union(
            *(component for component in current.room_components if len(component) > 1)
        )
        candidates = {point for point in candidates if tile_at(point) in connected_rooms}
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
            if any(char == "W" for char, _ in roster):
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
    """Choose the boss layout before reserving its room for ordinary spawns."""
    escort = rand.choice(d.STAGE6_BOSS_ESCORTS)
    if escort != ("w", 2):
        _place_party(current, [*d.STAGE6_BOSS_PARTY, escort], d.STAGE6_FLOORS - 1)
        return current.entities[-3:], set()
    available = set(_open_points(current))
    connected_rooms = set().union(
        *(component for component in current.room_components if len(component) > 1)
    )
    choices = []
    for x, y in sorted(available):
        room = tile_at((x, y))
        if room not in connected_rooms:
            continue
        for direction in (-1, 1):
            cells = ((x, y), (x, y - direction), (x, y + direction))
            entrance = {
                (x, y + 2 * direction),
                (x - 1, y + 2 * direction),
                (x + 1, y + 2 * direction),
                (x, y + 3 * direction),
            }
            footprint = set(cells) | entrance
            if footprint <= available and all(tile_at(point) == room for point in footprint):
                choices.append((cells, entrance))
    if not choices:
        raise RuntimeError("could not place Stage 6 empowered-wyrm boss entrance")
    cells, entrance = rand.choice(choices)
    party = [
        d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[char], rank)
        for (x, y), (char, rank) in zip(cells, [*d.STAGE6_BOSS_PARTY, escort])
    ]
    current.entities.extend(party)
    return party, entrance


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


def build(config: GameConfig | None = None) -> tuple[list[Floor], d.Player]:
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
            current.d_gates[gate] = "."
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
        initial_parties = _place_initial_parties(current, index, boss_room)
        if index < d.STAGE6_FLOORS - 1:
            _place_detached_room_monsters(current, room_components)
        # Retain the former Loop Companion's random draw for seeded generation.
        rand.choice(_open_points(current))
        for char in ("n", "o", "p"):
            current.entities.append(
                d.Companion(
                    *rand.choice(_open_points(current)),
                    d.CHAR_TO_TRIBE[char],
                    origin_floor=index,
                )
            )
        if index == d.STAGE6_FLOORS - 1:
            mimic = d.Monster(
                *rand.choice([point for point in _open_points(current)
                              if not _in_detached_terminal_room(current, point)]),
                d.CHAR_TO_MONSTER_TRIBE["M"],
                mimic_boss_char="W",
            )
            mimic.active = False
            current.entities.append(mimic)
        for char, count, rank in d.STAGE6_ROSTER[index]:
            for _ in range(count - initial_parties.get((char, rank), 0)):
                _place_party(current, _party_roster(char, rank, index), index)
        extra_bison_rank = d.STAGE6_EXTRA_BISON_RANKS[index]
        if extra_bison_rank is not None:
            _place_party(current, [("b", extra_bison_rank)], index)
        if index == d.STAGE6_FLOORS - 1:
            boss = next(
                entity
                for entity in current.entities
                if isinstance(entity, d.Monster) and entity.tribe.char == "W"
            )
            boss_zone = tile_at((boss.x, boss.y))
            treasure_points = [
                point for point in _open_points(current) if tile_at(point) != boss_zone
            ]
            current.entities.append(d.Treasure(*rand.choice(treasure_points), "TW"))
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
    for current in floors:
        if current is floors[-1]:
            for entity in initial_boss_party:
                current.entities.remove(entity)
        normalize_parties(current, d.MEMBER_STAGE_MONSTER_PARTY_LIMIT)
        if current is floors[-1]:
            current.entities.extend(initial_boss_party)
    for x, y in boss_entrance:
        floors[-1].field[y][x] = d.CHAR_FLOOR
    floors[-1].respawn_exclusions.difference_update(boss_reserved)
    player = d.Player(*floors[0].up, 1, d.LP_INIT)
    player.stage6_candidates = True
    for current in floors[:2]:
        _place_tavern(current, current.up)
        horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
        vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
        radius = round(vortex_radius * d.STAGE6_TAVERN_KNOWN_VORTEX_RATIO)
        for x, y in iterate_ellipse_points(
            *current.tavern, radius, d.FOV_WIDTH_EXPANSION_RATIO
        ):
            current.seen[y][x] = 1
    for role in member_roles:
        if role in (d.MEMBER_HEALER, d.MEMBER_DUNGEON_EXPLORER):
            floor_index = 0
        elif role in (d.MEMBER_KNIGHT, d.MEMBER_GUARDIAN):
            floor_index = 1
        else:
            floor_index = rand.randrange(2)
        current = floors[floor_index]
        point = _candidate_near_tavern(current, current.up)
        current.entities.append(d.PartyMember(*point, role, origin_floor=floor_index))
    _mark_boss_route(floors, (player.x, player.y), (boss.x, boss.y))
    for current in floors:
        stage56.initialize_monster_barriers(current)
    player.rescue_stage = True
    player.treasure_stage = True
    return floors, player


def _place_tavern(current: Floor, anchor: d.Point) -> None:
    reachable = _reachable_floor_points(current, anchor)
    open_points = set(_open_points(current)) & reachable
    choices = [
        (x, y) for x, y in open_points
        if all((x + dx, y) in open_points for dx in range(2))
    ]
    if not choices:
        raise RuntimeError("no space for stage 6 tavern")
    x, y = min(choices, key=lambda p: (abs(p[0] - anchor[0]) + abs(p[1] - anchor[1]), p))
    current.tavern = (x, y)
    for dx, char in enumerate("/\\"):
        current.decor[y][x + dx] = d.DECOR_TAVERN_PREFIX + char


def _candidate_near_tavern(
    current: Floor, anchor: d.Point, excluded: d.Point | None = None
) -> d.Point:
    tavern = current.tavern or anchor
    reachable = _reachable_floor_points(current, anchor)
    points = [p for p in _open_points(current) if p in reachable and p != excluded
              and not _in_tavern(current, p)]
    if not points:
        raise RuntimeError("no space near stage 6 tavern")
    nearby = [p for p in points if abs(p[0] - tavern[0]) + abs(p[1] - tavern[1]) <= 7]
    if nearby:
        return rand.choice(nearby)
    return min(points, key=lambda p: (abs(p[0] - tavern[0]) + abs(p[1] - tavern[1]), p))


def _in_tavern(current: Floor, point: d.Point) -> bool:
    if current.tavern is None:
        return False
    x, y = current.tavern
    return x <= point[0] < x + 2 and point[1] == y


def _mark_boss_route(floors: list[Floor], start: d.Point, boss: d.Point) -> None:
    """Mark a shortest initial walking route using ordinary stairs."""
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
        raise RuntimeError("no initial route to the Stage 6 boss")
    route = []
    state = goal
    while state is not None:
        route.append(state)
        link = previous[state]
        state = link[0] if link is not None else None
    route.reverse()
    _balance_route_parties(floors, route)
    for index, (x, y) in route[::3]:
        if index == len(floors) - 1:
            continue
        if floors[index].decor[y][x] == d.DECOR_NONE and not _in_tavern(floors[index], (x, y)):
            floors[index].decor[y][x] = d.DECOR_BOSS_ROUTE



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
            if (not party or any(e.tribe.char in ("W", "V", "M", "c", d.CHAR_COLLAPSE)
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


def relocate_candidates(floors, player, candidates=None, player_floor=None):
    if candidates is None:
        candidates = []
        for current in floors:
            for entity in list(current.entities):
                if isinstance(entity, d.PartyMember):
                    current.entities.remove(entity)
                    candidates.append(entity)
    for member in candidates:
        fixed_floor = {
            d.MEMBER_HEALER: 0, d.MEMBER_DUNGEON_EXPLORER: 0,
            d.MEMBER_KNIGHT: 1, d.MEMBER_GUARDIAN: 1,
        }.get(member.role)
        index = fixed_floor if fixed_floor is not None else rand.randrange(2)
        current = floors[index]
        excluded = (player.x, player.y) if index == player_floor else None
        member.x, member.y = _candidate_near_tavern(current, current.up, excluded)
        member.origin_floor = index
        player.known_member_floors.pop(member.role, None)
        floors[index].entities.append(member)


def record_transition(floors, player, source_floor, source, destination_floor, destination):
    if destination_floor != 0 and not getattr(player, "stage6_candidates_relocated", False):
        relocate_candidates(floors, player, player_floor=destination_floor)
        player.stage6_candidates_relocated = True


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
