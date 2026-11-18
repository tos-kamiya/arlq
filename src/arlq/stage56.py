"""Gameplay mechanics shared by Stages 5 and 6."""

from . import defs as d
from .arlq import iterate_ellipse_points
from .i18n import t, trp
from .stage_types import Floor
from .utils import rand


def monster_party(current: Floor, first: d.Monster) -> list[d.Monster]:
    return monster_party_entities(current.entities, first)


def monster_party_entities(
    entities: list[d.Entity],
    first: d.Monster,
    *,
    positions: dict[d.Point, d.Monster] | None = None,
) -> list[d.Monster]:
    """Return the active vertically connected party containing ``first``."""
    if first.tribe.char == d.CHAR_DUNGEON_CORE:
        return [first]
    candidates = monster_positions(entities) if positions is None else positions
    candidates = {
        point: monster for point, monster in candidates.items()
        if monster.tribe.char != d.CHAR_DUNGEON_CORE
    }
    party = []
    pending = [first]
    visited = set()
    while pending:
        entity = pending.pop()
        point = (entity.x, entity.y)
        if point in visited:
            continue
        visited.add(point)
        party.append(entity)
        for dx, dy in ((0, -1), (0, 1)):
            neighbor = candidates.get((entity.x + dx, entity.y + dy))
            if neighbor is not None:
                pending.append(neighbor)
    return party


def monster_positions(entities: list[d.Entity]) -> dict[d.Point, d.Monster]:
    return {
        (entity.x, entity.y): entity
        for entity in entities
        if isinstance(entity, d.Monster) and entity.active and not entity.tribe.is_elf
    }


def special_monster(entity: d.Monster) -> bool:
    # Unlocking the objective is not a combat ability; W can accompany V.
    return entity.tribe.char == d.CHAR_DUNGEON_CORE or bool(
        entity.tribe.item or entity.tribe.effect not in (None, d.EFFECT_UNLOCK_TREASURE)
    )


def recruit(
    current: Floor,
    player: d.Player,
    member: d.PartyMember,
) -> str:
    player.joined_members.add(member.role)
    player.seen_members.add(member.role)
    if member.origin_floor is not None:
        player.known_member_floors.setdefault(member.role, member.origin_floor + 1)
    departed = player.members.pop(1) if len(player.members) == d.PARTY_LIMIT else None
    if departed is not None:
        player.seen_members.add(departed.role)
        player.known_member_floors.pop(departed.role, None)
    current.entities.remove(member)
    member.x, member.y = player.x, player.y
    player.members.append(member)
    member.exploration_turns = 0
    if departed is not None:
        return trp("-- {joined} joined; {departed} left the party.", 5).format(
            joined=t(member.role), departed=t(departed.role)
        )
    return trp("-- {joined} joined your party.", 5).format(joined=t(member.role))


def set_scholar_stairs(floors: list[Floor], active: bool) -> None:
    """Set every hidden stair marker; retained for stage setup utilities."""
    for current in floors:
        for point in current.scholar_up_stairs:
            x, y = point
            current.field[y][x] = (
                d.CHAR_SCHOLAR_STAIRS_UP if active else d.CHAR_HIDDEN_STAIRS_UP
            )
            if active:
                current.seen[y][x] = 1
        for point in current.scholar_down_stairs:
            x, y = point
            current.field[y][x] = (
                d.CHAR_SCHOLAR_STAIRS_DOWN if active else d.CHAR_HIDDEN_STAIRS_DOWN
            )
            if active:
                current.seen[y][x] = 1


def reveal_scholar_features(current: Floor, known: list[list[int]]) -> None:
    """Reveal Explorer secrets anywhere in the explored part of the floor."""
    for points, hidden, revealed in (
        (
            current.scholar_up_stairs,
            d.CHAR_HIDDEN_STAIRS_UP,
            d.CHAR_SCHOLAR_STAIRS_UP,
        ),
        (
            current.scholar_down_stairs,
            d.CHAR_HIDDEN_STAIRS_DOWN,
            d.CHAR_SCHOLAR_STAIRS_DOWN,
        ),
    ):
        for x, y in points:
            if known[y][x] and current.field[y][x] == hidden:
                current.field[y][x] = revealed
    gate_changed = False
    for x, y in current.d_gates:
        if known[y][x] and current.field[y][x] == d.CHAR_HIDDEN_D_GATE:
            current.field[y][x] = d.CHAR_D_GATE
            gate_changed = True
    if gate_changed:
        current.update_outer_wall_decor()


def sync_members(player: d.Player, previous: d.Point, direction: d.Point, *, reset: bool = False,
                 current: Floor | None = None, floor_index: int = 0) -> None:
    if (player.x, player.y) != previous:
        player.facing = direction
    if reset:
        for member in player.members:
            member.x, member.y = player.x, player.y
        return
    if (player.x, player.y) == previous:
        return
    for member in player.members[:]:
        position = (member.x, member.y)
        if (current is not None and position == (player.x, player.y)
                and current.field[previous[1]][previous[0]] == d.CHAR_BARRIER):
            previous = position
            continue
        if (current is not None and member.role in d.MEMBERS_BLOCKED_BY_BARRIERS
                and current.field[previous[1]][previous[0]] == d.CHAR_BARRIER
                and position != previous):
            player.members.remove(member)
            member.origin_floor = floor_index
            player.known_member_floors[member.role] = floor_index + 1
            current.entities.append(member)
            continue
        member.x, member.y = previous
        previous = position


def reveal_rogue_monsters(
    current: Floor, player: d.Player, visible: list[list[int]]
) -> None:
    """Identify active Rogue targets that are in the player's field of view."""
    if not d.has_member(player, d.MEMBER_ROGUE):
        return
    for entity in current.entities:
        if (
            isinstance(entity, d.Monster)
            and entity.active
            and entity.tribe.char in ("E", "M", "g", "X")
            and 0 <= entity.y < len(visible)
            and 0 <= entity.x < len(visible[entity.y])
            and visible[entity.y][entity.x]
        ):
            player.known_monsters.add(d.monster_type_key(entity))


def rogue_danger(current: Floor, destination: d.Point) -> str | None:
    """Check whether the destination is a pit or Rare Erebus."""
    x, y = destination
    if not (0 <= y < len(current.field) and 0 <= x < len(current.field[y])):
        return None
    if current.field[y][x] == d.CHAR_COLLAPSE:
        current.seen[y][x] = 1
        return "O"
    collapse = next(
        (
            entity
            for entity in current.entities
            if isinstance(entity, d.Collapse)
            and destination in d.collapse_footprint((entity.x, entity.y))
        ),
        None,
    )
    if collapse is not None:
        for dx, dy in d.COLLAPSE_FOOTPRINT_OFFSETS[1:]:
            pit_x, pit_y = collapse.x + dx, collapse.y + dy
            if (
                0 <= pit_y < len(current.field)
                and 0 <= pit_x < len(current.field[pit_y])
                and current.field[pit_y][pit_x]
                not in (*d.WALL_CHARS, *d.HIDDEN_PASSAGE_CHARS)
            ):
                current.field[pit_y][pit_x] = d.CHAR_COLLAPSE
                current.seen[pit_y][pit_x] = 1
        current.seen[y][x] = 1
        return "O"
    if any(
        isinstance(entity, d.Monster)
        and entity.active
        and entity.tribe.char == "E"
        and (entity.x, entity.y) == destination
        for entity in current.entities
    ):
        return "E"
    return None


def _open_points(
    current: Floor, *, include_barriers: bool = False, include_caltrops: bool = False,
) -> list[d.Point]:
    occupied = {(entity.x, entity.y) for entity in current.entities}
    reserved = {
        current.up,
        current.down,
        *current.collapse_landings,
        *current.respawn_exclusions,
        *current.scholar_up_stairs,
        *current.scholar_down_stairs,
    }
    for entity in current.entities:
        if isinstance(entity, d.Collapse):
            reserved.update(d.collapse_footprint((entity.x, entity.y)))
    unavailable = occupied | reserved
    return [
        (x, y)
        for y, row in enumerate(current.field)
        for x, cell in enumerate(row)
        if (
            cell == d.CHAR_FLOOR
            or (include_barriers and cell == d.CHAR_BARRIER)
            or (include_caltrops and cell == d.CHAR_CALTROP)
        )
        and (x, y) not in unavailable
    ]


def initialize_monster_barriers(current: Floor) -> None:
    """Place the initial rings around barrier-bearing monsters on a floor."""
    occupied = {(entity.x, entity.y) for entity in current.entities}
    reserved = {
        current.up,
        current.down,
        *current.up_stairs,
        *current.down_stairs,
        *current.scholar_up_stairs,
        *current.scholar_down_stairs,
        *current.collapse_landings,
        *current.d_gates,
    }
    ring_cells = set()
    for entity in current.entities:
        if not isinstance(entity, d.Monster) or not entity.active:
            continue
        for point in barrier_cells(current, entity):
            x, y = point
            if (
                point not in occupied
                and point not in reserved
                and point not in current.broken_walls
                and (
                    current.field[y][x] == d.CHAR_FLOOR
                    or current.field[y][x] == d.CHAR_BARRIER
                )
            ):
                ring_cells.add(point)

    existing_barriers = {
        (x, y) for y, row in enumerate(current.field)
        for x, cell in enumerate(row) if cell == d.CHAR_BARRIER
    }
    clear_monster_barriers(current, existing_barriers, ring_cells)
    for x, y in ring_cells:
        if current.field[y][x] == d.CHAR_FLOOR:
            current.field[y][x] = d.CHAR_BARRIER


def place_monster_barriers(
    current: Floor,
    entity: d.Monster,
    player_position: d.Point | None = None,
) -> None:
    """Place the barrier ring for one newly placed monster."""
    if not entity.active or not _barrier_offsets(entity):
        return
    occupied = {(other.x, other.y) for other in current.entities}
    if player_position is not None:
        occupied.add(player_position)
    reserved = {
        current.up,
        current.down,
        *current.up_stairs,
        *current.down_stairs,
        *current.scholar_up_stairs,
        *current.scholar_down_stairs,
        *current.collapse_landings,
        *current.d_gates,
    }
    for point in barrier_cells(current, entity):
        x, y = point
        if (
            point in occupied
            or point in reserved
            or point in current.broken_walls
            or current.field[y][x] not in (d.CHAR_FLOOR, d.CHAR_BARRIER)
        ):
            continue
        if current.field[y][x] == d.CHAR_FLOOR:
            current.field[y][x] = d.CHAR_BARRIER


def _barrier_offsets(entity: d.Monster) -> tuple[d.Point, ...]:
    if entity.tribe.char in {"w", "W"}:
        return tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
    if entity.tribe.char == "f":
        if entity.empowered == 2:
            return ((0, -1), (1, 0), (0, 1), (-1, 0))
        return ((1, 0), (-1, 0))
    return ()


def barrier_cells(current: Floor, entity: d.Monster) -> tuple[d.Point, ...]:
    """Monster barrier footprint clipped to the floor."""
    return tuple(
        (entity.x + dx, entity.y + dy)
        for dx, dy in _barrier_offsets(entity)
        if 0 <= entity.y + dy < len(current.field)
        and 0 <= entity.x + dx < len(current.field[entity.y + dy])
    )


def clear_monster_barriers(
    current: Floor, cells: set[d.Point], protected: set[d.Point]
) -> None:
    """Remove transient barriers while retaining fixed and overlapping ones."""
    for x, y in cells - protected - current.persistent_barriers:
        if current.field[y][x] == d.CHAR_BARRIER:
            current.field[y][x] = d.CHAR_FLOOR


def respawn(
    current: Floor,
    char: str,
    rank: int,
    origin_floor: int,
    avoid: set[d.Point],
    floor_index: int = 0,
) -> d.Point | None:
    is_monster = isinstance(d.CHAR_TO_TRIBE[char], d.MonsterTribe)
    candidates = [
        point for point in _open_points(
            current, include_barriers=is_monster, include_caltrops=is_monster,
        ) if point not in avoid
    ]
    monsters = [entity for entity in current.entities if isinstance(entity, d.Monster)]
    if isinstance(d.CHAR_TO_TRIBE[char], d.MonsterTribe):
        monster_positions = {(entity.x, entity.y) for entity in monsters}
        candidates = [
            (x, y)
            for x, y in candidates
            if (x - 1, y) not in monster_positions
            and (x + 1, y) not in monster_positions
        ]
    golem_positions = {
        (entity.x, entity.y) for entity in monsters if entity.tribe.char == "g"
    }
    if char == "g":
        # Golems stay separate from every other monster.
        isolated_positions = {(entity.x, entity.y) for entity in monsters}
    else:
        isolated_positions = golem_positions
    if isolated_positions:
        candidates = [
            point
            for point in candidates
            if all(
                (point[0] + dx, point[1] + dy) not in isolated_positions
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            )
        ]
    if floor_index == 1:
        marksmen = {
            (entity.x, entity.y)
            for entity in current.entities
            if isinstance(entity, d.Monster) and entity.tribe.char == "k"
        }
        candidates = [
            point
            for point in candidates
            if all(
                (point[0] + dx, point[1] + dy) not in marksmen
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            )
        ]
        if char == "k":
            candidates = [
                point
                for point in candidates
                if all(
                    (point[0] + dx, point[1] + dy)
                    not in {
                        (entity.x, entity.y)
                        for entity in current.entities
                        if isinstance(entity, d.Monster)
                    }
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                )
            ]
    if not candidates:
        return None
    point = rand.choice(candidates)
    tribe = d.CHAR_TO_TRIBE[char]
    if isinstance(tribe, d.MonsterTribe):
        entity = d.Monster(*point, tribe, rank)
        if current.field[point[1]][point[0]] in (d.CHAR_CALTROP, d.CHAR_BARRIER):
            current.field[point[1]][point[0]] = d.CHAR_FLOOR
            current.persistent_barriers.discard(point)
    else:
        entity = d.Fairy(*point, tribe, origin_floor=origin_floor)
    current.entities.append(entity)
    return point


def explore_with_cat(current: Floor, player: d.Player) -> None:
    """Let the cat explore a small patch every twenty accompanying turns."""
    cat = next((member for member in player.members
                if member.role == d.MEMBER_YAWNING_CAT), None)
    if cat is None:
        return
    cat.exploration_turns += 1
    if cat.exploration_turns < d.CAT_EXPLORE_INTERVAL:
        return
    cat.exploration_turns = 0
    candidates = [
        (x, y) for x, y in iterate_ellipse_points(
            player.x, player.y, d.CAT_EXPLORE_RADIUS, d.FOV_WIDTH_EXPANSION_RATIO
        )
        if (0 <= y < len(current.field) and 0 <= x < len(current.field[y])
            and current.field[y][x] == d.CHAR_FLOOR and not current.seen[y][x])
    ]
    if not candidates:
        return
    cx, cy = rand.choice(candidates)
    size = d.CAT_EXPLORE_SIZE
    top = max(0, min(cy, len(current.field) - size))
    left = max(0, min(cx, len(current.field[cy]) - size))
    for y in range(top, min(len(current.field), top + size)):
        for x in range(left, min(len(current.field[y]), left + size)):
            current.seen[y][x] = 1
