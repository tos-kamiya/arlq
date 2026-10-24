"""Stage 5 rescue stage, member trial, and party rules."""

from . import defs as d
from .arlq import GameConfig, create_field
from .i18n import trp
from .stage_maze import generate_floor_field
from .stage_types import Floor
from .stage_world import (
    _add_filled_room_wall_notches,
    _add_wall_spurs,
    _place_collapses,
    _place_final_floor_barriers,
)
from .utils import rand


def monster_party(current: Floor, first: d.Monster) -> list[d.Monster]:
    return monster_party_entities(current.entities, first)


def monster_party_entities(
    entities: list[d.Entity], first: d.Monster
) -> list[d.Monster]:
    """Return the active cardinally connected party containing ``first``."""
    candidates = {
        (entity.x, entity.y): entity
        for entity in entities
        if isinstance(entity, d.Monster) and entity.active and not entity.tribe.is_elf
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
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            neighbor = candidates.get((entity.x + dx, entity.y + dy))
            if neighbor is not None:
                pending.append(neighbor)
    return party


def special_monster(entity: d.Monster) -> bool:
    # Unlocking the objective is not a combat ability; W can accompany V'.
    return bool(
        entity.tribe.item or entity.tribe.effect not in (None, d.EFFECT_UNLOCK_TREASURE)
    )


def normalize_parties(current: Floor) -> None:
    """Enforce party limits after spawning or rearranging; retain W and V'."""
    _separate_golems(current)
    checked = set()
    for entity in list(current.entities):
        if not isinstance(entity, d.Monster) or not entity.active or entity in checked:
            continue
        party = monster_party(current, entity)
        checked.update(party)
        party.sort(
            key=lambda monster: (
                0
                if monster.tribe.char == "W"
                else 1
                if monster.tribe.char == "V" and monster.empowered == 2
                else 2,
                monster.y,
                monster.x,
            )
        )
        kept = 0
        special = False
        for monster in party:
            is_special = special_monster(monster)
            if kept >= d.MONSTER_PARTY_LIMIT or (special and is_special):
                current.entities.remove(monster)
            else:
                kept += 1
                special |= is_special
    _separate_diagonal_monsters(current)
    _sync_wyrm_barriers(current)


def _separate_golems(current: Floor) -> None:
    """Keep each Golem out of every other monster's cardinal adjacency."""
    while True:
        monsters = [
            entity
            for entity in current.entities
            if isinstance(entity, d.Monster)
            and entity.active
            and not entity.tribe.is_elf
        ]
        conflict = next(
            (
                (first, second)
                for index, first in enumerate(monsters)
                for second in monsters[index + 1 :]
                if (first.tribe.char == "g" or second.tribe.char == "g")
                and abs(first.x - second.x) + abs(first.y - second.y) == 1
            ),
            None,
        )
        if conflict is None:
            return
        first, second = conflict
        golem = first if first.tribe.char == "g" else second
        other = second if golem is first else first
        other_is_fixed = isinstance(other, d.Collapse) or (
            (other.tribe.char == "W" and other.empowered == 1)
            or (other.tribe.char == "V" and other.empowered == 2)
        )
        mover = golem if other_is_fixed or other.tribe.char == "g" else other

        current.entities.remove(mover)
        other_monsters = [
            entity
            for entity in current.entities
            if isinstance(entity, d.Monster)
            and entity.active
            and not entity.tribe.is_elf
        ]
        candidates = [
            point
            for point in _open_points(current)
            if all(
                abs(point[0] - entity.x) > 1 or abs(point[1] - entity.y) > 1
                for entity in other_monsters
            )
        ]
        if not candidates:
            current.entities.append(mover)
            return
        mover.x, mover.y = rand.choice(candidates)
        current.entities.append(mover)


def _separate_diagonal_monsters(current: Floor) -> None:
    """Move non-boss monsters away from diagonal neighbors."""
    while True:
        monsters = [
            entity
            for entity in current.entities
            if isinstance(entity, d.Monster)
            and not isinstance(entity, d.Collapse)
            and entity.active
            and not entity.tribe.is_elf
        ]
        mover = None
        for index, first in enumerate(monsters):
            for second in monsters[index + 1 :]:
                if abs(first.x - second.x) != 1 or abs(first.y - second.y) != 1:
                    continue
                first_is_boss = (first.tribe.char == "W" and first.empowered == 1) or (
                    first.tribe.char == "V" and first.empowered == 2
                )
                second_is_boss = (
                    second.tribe.char == "W" and second.empowered == 1
                ) or (second.tribe.char == "V" and second.empowered == 2)
                if first_is_boss and second_is_boss:
                    continue
                mover = second if not second_is_boss else first
                break
            if mover is not None:
                break
        if mover is None:
            return

        current.entities.remove(mover)
        other_monsters = [
            entity
            for entity in current.entities
            if isinstance(entity, d.Monster)
            and not isinstance(entity, d.Collapse)
            and entity.active
            and not entity.tribe.is_elf
        ]
        candidates = [
            point
            for point in _open_points(current)
            if all(
                abs(point[0] - other.x) > 1 or abs(point[1] - other.y) > 1
                for other in other_monsters
            )
        ]
        if not candidates:
            current.entities.append(mover)
            return
        mover.x, mover.y = rand.choice(candidates)
        current.entities.append(mover)


def recruit(
    current: Floor,
    player: d.Player,
    member: d.PartyMember,
    recycle_departed: bool = False,
    floors: list[Floor] | None = None,
) -> str:
    if len(player.members) == d.PARTY_LIMIT and player.members[0].role == "Noble":
        return trp("-- Noble cannot leave. No more members can join.", 5)
    player.joined_members.add(member.role)
    if member.origin_floor is not None:
        player.known_member_floors.setdefault(member.role, member.origin_floor + 1)
    departed = player.members.pop(0) if len(player.members) == d.PARTY_LIMIT else None
    current.entities.remove(member)
    player.members.append(member)
    if departed is not None and recycle_departed:
        target = current
        if (
            floors is not None
            and departed.origin_floor is not None
            and 0 <= departed.origin_floor < len(floors)
        ):
            target = floors[departed.origin_floor]
        choices = [
            point
            for point in _open_points(target)
            if target is not current or point != (player.x, player.y)
        ]
        departed.x, departed.y = rand.choice(choices)
        target.entities.append(departed)
    if departed is not None:
        return trp("-- {joined} joined; {departed} left the party.", 5).format(
            joined=member.role, departed=departed.role
        )
    return trp("-- {joined} joined your party.", 5).format(joined=member.role)


def set_scholar_stairs(floors: list[Floor], active: bool) -> None:
    """Reveal or conceal the paired stairs known to the Dangeon Scholar."""
    for current in floors:
        for point in current.scholar_up_stairs:
            x, y = point
            current.field[y][x] = d.CHAR_STAIRS_UP if active else d.CHAR_FLOOR
            if active:
                current.seen[y][x] = 1
        for point in current.scholar_down_stairs:
            x, y = point
            current.field[y][x] = d.CHAR_STAIRS_DOWN if active else d.CHAR_FLOOR
            if active:
                current.seen[y][x] = 1


def sync_members(player: d.Player, previous: d.Point, direction: d.Point) -> None:
    if (player.x, player.y) != previous:
        player.facing = direction
    for member in player.members:
        member.x, member.y = player.x, player.y


def reveal_mimics(current: Floor, player: d.Player) -> None:
    if not d.has_member(player, "Rogue"):
        return
    for entity in current.entities:
        if (
            isinstance(entity, d.Monster)
            and entity.active
            and entity.tribe.char == "M"
            and max(abs(player.x - entity.x), abs(player.y - entity.y)) <= 1
        ):
            player.known_monsters.add(d.monster_type_key(entity))
            current.seen[entity.y][entity.x] = 1


def reveal_rogue_traps(current: Floor, player: d.Player) -> None:
    """Identify adjacent Golems and Caltrop Plants for a Rogue."""
    if not d.has_member(player, "Rogue"):
        return
    for entity in current.entities:
        if (
            isinstance(entity, d.Monster)
            and entity.active
            and entity.tribe.char in ("g", "X")
            and abs(player.x - entity.x) + abs(player.y - entity.y) == 1
        ):
            player.known_monsters.add(d.monster_type_key(entity))
            current.seen[entity.y][entity.x] = 1


def rogue_danger(current: Floor, player: d.Player, destination: d.Point) -> str | None:
    """Inspect the destination using the same blockers as marksman arrows."""
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
                and current.field[pit_y][pit_x] not in d.WALL_CHARS
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
    if current.field[y][x] in (*d.WALL_CHARS, *d.STAIR_CHARS) or any(
        (entity.x, entity.y) == destination
        and (
            isinstance(entity, (d.Companion, d.Treasure))
            or isinstance(entity, d.Monster) and entity.active
        )
        for entity in current.entities
    ):
        return None
    for entity in current.entities:
        if (
            not isinstance(entity, d.Monster)
            or not entity.active
            or entity.tribe.char != "k"
        ):
            continue
        dx, dy = x - entity.x, y - entity.y
        if (dx == 0) == (dy == 0) or abs(dx or dy) <= 1:
            continue
        sx = (dx > 0) - (dx < 0)
        sy = (dy > 0) - (dy < 0)
        for offset in range(1, abs(dx or dy)):
            point = (entity.x + sx * offset, entity.y + sy * offset)
            if current.field[point[1]][point[0]] in (*d.WALL_CHARS, *d.STAIR_CHARS):
                break
            if any(
                (other.x, other.y) == point
                and (
                    isinstance(other, (d.Companion, d.Treasure))
                    or isinstance(other, d.Monster)
                    and other.active
                )
                for other in current.entities
            ):
                break
        else:
            char = "-" if sx else "|"
            entity.warning_arrow_marks[:] = [
                mark for mark in entity.warning_arrow_marks if mark[0] != destination
            ]
            entity.warning_arrow_marks.append((destination, char))
            current.seen[y][x] = 1
            return char
    return None


def sample_party_size(floor_index: int) -> int:
    weights = d.STAGE5_PARTY_SIZE_WEIGHTS[floor_index]
    roll = rand.randrange(sum(weights))
    for size, weight in enumerate(weights, 1):
        if roll < weight:
            return size
        roll -= weight
    raise AssertionError("invalid party weights")


def _open_points(current: Floor) -> list[d.Point]:
    occupied = {(entity.x, entity.y) for entity in current.entities}
    reserved = {
        current.up,
        current.down,
        *current.collapse_landings,
        *current.scholar_up_stairs,
        *current.scholar_down_stairs,
    }
    return [
        (x, y)
        for y, row in enumerate(current.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_FLOOR and (x, y) not in occupied | reserved
    ]


def _sync_wyrm_barriers(current: Floor) -> None:
    """Keep non-persistent barrier rings centered on the surviving w/W."""
    occupied = {(entity.x, entity.y) for entity in current.entities}
    reserved = {
        current.up,
        current.down,
        *current.up_stairs,
        *current.down_stairs,
        *current.scholar_up_stairs,
        *current.scholar_down_stairs,
        *current.collapse_landings,
    }
    ring_cells = set()
    for entity in current.entities:
        if (
            not isinstance(entity, d.Monster)
            or not entity.active
            or entity.tribe.char not in {"w", "W"}
        ):
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                point = (entity.x + dx, entity.y + dy)
                x, y = point
                if (
                    0 <= y < len(current.field)
                    and 0 <= x < len(current.field[y])
                    and point not in occupied
                    and point not in reserved
                    and (
                        current.field[y][x] == d.CHAR_FLOOR
                        or (
                            current.field[y][x] == d.CHAR_BARRIER
                            and point not in current.persistent_barriers
                        )
                    )
                ):
                    ring_cells.add(point)

    for y, row in enumerate(current.field):
        for x, cell in enumerate(row):
            point = (x, y)
            if (
                cell == d.CHAR_BARRIER
                and point not in current.persistent_barriers
                and point not in ring_cells
            ):
                current.field[y][x] = d.CHAR_FLOOR
    for x, y in ring_cells:
        if current.field[y][x] == d.CHAR_FLOOR:
            current.field[y][x] = d.CHAR_BARRIER


def _place_party(
    current: Floor, roster: list[tuple[str, int]], floor_index: int = 0
) -> None:
    # Only keep distinct parties from merging. Walls and narrow corridors do
    # not exclude a spawn cell; a party may completely block a passage.
    occupied = {(entity.x, entity.y) for entity in current.entities}
    boss_pair = set(roster) == {("W", 1), ("V", 2)} and len(roster) == 2
    if any(rank == 2 for _, rank in roster) and not boss_pair and len(roster) != 1:
        raise ValueError("rank-2 Stage 5 monsters must spawn alone")
    monsters = {
        (entity.x, entity.y)
        for entity in current.entities
        if isinstance(entity, d.Monster)
    }
    candidates = set(_open_points(current))
    candidates = {
        point
        for point in candidates
        if all(
            (point[0] + dx, point[1] + dy) not in monsters
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
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
        if any(char == "k" for char, _ in roster) and len(roster) != 1:
            raise ValueError("Stage 5 floor-2 marksmen must spawn alone")
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
        seed = rand.choice(sorted(candidates))
        cells = [seed]
        while len(cells) < len(roster):
            frontier = sorted(
                {
                    (x + dx, y + dy)
                    for x, y in cells
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                }
                & candidates - set(cells) - occupied
            )
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
    raise RuntimeError("could not place Stage 5 monster party")


def respawn(
    current: Floor,
    char: str,
    rank: int,
    origin_floor: int,
    avoid: set[d.Point],
    floor_index: int = 0,
) -> d.Point:
    candidates = [point for point in _open_points(current) if point not in avoid]
    monsters = [entity for entity in current.entities if isinstance(entity, d.Monster)]
    empowered_positions = {
        (entity.x, entity.y) for entity in monsters if entity.empowered == 2
    }
    golem_positions = {
        (entity.x, entity.y) for entity in monsters if entity.tribe.char == "g"
    }
    if rank == 2 or char == "g":
        # Rank-2 monsters and Golems stay separate from every other monster.
        isolated_positions = {(entity.x, entity.y) for entity in monsters}
    else:
        isolated_positions = empowered_positions | golem_positions
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
    point = rand.choice(candidates)
    tribe = d.CHAR_TO_TRIBE[char]
    if isinstance(tribe, d.MonsterTribe):
        entity = d.Monster(*point, tribe, rank)
    else:
        entity = d.Companion(*point, tribe, origin_floor=origin_floor)
    current.entities.append(entity)
    return point


def build(config: GameConfig | None = None) -> tuple[list[Floor], d.Player]:
    config = config or GameConfig()
    floors = []
    entry = None
    filled_counts = list(d.STAGE4_FILLED_ROOM_COUNTS)
    filled_counts.remove(0)
    filled_counts_by_floor = [0]
    while filled_counts:
        filled_counts_by_floor.append(
            filled_counts.pop(rand.randrange(len(filled_counts)))
        )
    split_floor_index = rand.randrange(1, d.STAGE5_FLOORS)
    for index in range(d.STAGE5_FLOORS):
        field, up, down, _, filled_rooms, room_components = generate_floor_field(
            entry,
            None,
            config.corridor_h_width,
            config.corridor_v_width,
            0,
            filled_counts_by_floor[index],
            split_room_graph=index == split_floor_index,
        )
        if index >= 2:
            _add_wall_spurs(field, up, down, None, filled_rooms)
        _add_filled_room_wall_notches(field, filled_rooms)
        if index:
            field[up[1]][up[0]] = d.CHAR_STAIRS_UP
        if index < d.STAGE5_FLOORS - 1:
            field[down[1]][down[0]] = d.CHAR_STAIRS_DOWN
        current = Floor(
            field,
            [],
            [[0] * len(field[0]) for _ in field],
            up,
            down,
            None,
            up_stairs=[up] if index else [],
            down_stairs=[down] if index < d.STAGE5_FLOORS - 1 else [],
            room_components=room_components,
        )
        for role in d.STAGE5_MEMBER_FLOORS[index]:
            current.entities.append(
                d.PartyMember(
                    *rand.choice(_open_points(current)), role, origin_floor=index
                )
            )
        for char in ("l", "n", "o", "p"):
            current.entities.append(
                d.Companion(
                    *rand.choice(_open_points(current)),
                    d.CHAR_TO_TRIBE[char],
                    origin_floor=index,
                )
            )
        if index == d.STAGE5_FLOORS - 1:
            _place_party(current, list(d.STAGE5_BOSS_PARTY), index)
        for char, count, rank in d.STAGE5_ROSTER[index]:
            for _ in range(count):
                party_size = (
                    1
                    if rank == 2
                    or char == "g"
                    or (index > 0 and char == "k")
                    else sample_party_size(index)
                )
                roster = [(char, rank)] + [
                    rand.choice(d.STAGE5_SUPPORT_POOLS[index])
                    for _ in range(party_size - 1)
                ]
                _place_party(current, roster, index)
        if index == d.STAGE5_FLOORS - 1:
            current.entities.append(
                d.Treasure(*rand.choice(_open_points(current)), "TW")
            )
        for char, count in zip(
            (d.CHAR_CALTROP, d.CHAR_BARRIER), d.STAGE5_HAZARD_COUNTS[index]
        ):
            for _ in range(count):
                x, y = rand.choice(_open_points(current))
                current.field[y][x] = char
                if char == d.CHAR_BARRIER:
                    current.persistent_barriers.add((x, y))
        floors.append(current)
        entry = down
    _place_collapses(floors)
    _place_scholar_stairs(floors)
    _place_final_floor_barriers(
        floors[-1], d.STAGE5_FINAL_FLOOR_BARRIER_PERCENT
    )
    for current in floors:
        normalize_parties(current)
    player = d.Player(*floors[0].up, d.STAGE5_START_LEVEL, d.LP_INIT)
    player.rescue_stage = True
    return floors, player


def build_member_trial(config: GameConfig | None = None) -> tuple[list[Floor], d.Player]:
    """Build a compact two-floor area for trying every Stage 5 member."""
    config = config or GameConfig()
    field, up, down = create_field(
        config.corridor_h_width,
        config.corridor_v_width,
        d.CHAR_WALL,
        tile_columns=3,
    )
    lower_field = [row.copy() for row in field]
    field[down[1]][down[0]] = d.CHAR_STAIRS_DOWN
    lower_field[down[1]][down[0]] = d.CHAR_STAIRS_UP
    upper = Floor(
        field,
        [],
        [[0] * len(field[0]) for _ in field],
        up,
        down,
        None,
        down_stairs=[down],
    )
    lower = Floor(
        lower_field,
        [],
        [[0] * len(lower_field[0]) for _ in lower_field],
        down,
        down,
        None,
        up_stairs=[down],
    )
    for role in ("Bard", "Healer", "Rogue", "Knight", "Dangeon Scholar"):
        upper.entities.append(
            d.PartyMember(*rand.choice(_open_points(upper)), role, origin_floor=0)
        )

    for char, count in (("g", 1), ("a", 1), ("b", 3)):
        for _ in range(count):
            _place_party(upper, [(char, 1)])
    for char, count in (("g", 1), ("k", 1), ("b", 3), ("d", 1)):
        for _ in range(count):
            _place_party(lower, [(char, 1)], floor_index=1)

    occupied = {
        (entity.x, entity.y)
        for current in (upper, lower)
        for entity in current.entities
    }
    collapse_points = [
        point
        for point in _open_points(upper)
        if not d.collapse_footprint(point) & occupied
        if d.collapse_placement_cells_valid(point, upper.field, lower.field)
    ]
    collapse_point = rand.choice(collapse_points)
    upper.entities.append(d.Collapse(*collapse_point))
    lower.collapse_landings.update(d.collapse_footprint(collapse_point))
    for hazard, current in ((d.CHAR_CALTROP, upper), (d.CHAR_BARRIER, lower)):
        x, y = rand.choice(_open_points(current))
        current.field[y][x] = hazard
        if hazard == d.CHAR_BARRIER:
            current.persistent_barriers.add((x, y))

    floors = [upper, lower]
    _place_scholar_stairs(floors)
    for current in floors:
        normalize_parties(current)
    player = d.Player(*upper.up, 30, d.LP_INIT)
    player.rescue_stage = True
    return floors, player


def _place_scholar_stairs(floors: list[Floor]) -> None:
    """Reserve one concealed matching stair pair on each floor transition."""
    for upper, lower in zip(floors, floors[1:]):
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
        fixed.update(
            point
            for current in (upper, lower)
            for entity in current.entities
            if isinstance(entity, d.Collapse)
            for point in d.collapse_footprint((entity.x, entity.y))
        )
        entry = upper.scholar_up_stairs[-1] if upper.scholar_up_stairs else upper.up
        reachable = {entry}
        pending = [entry]
        while pending:
            x, y = pending.pop()
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                point = (x + dx, y + dy)
                px, py = point
                if (
                    point not in reachable
                    and 0 <= py < len(upper.field)
                    and 0 <= px < len(upper.field[py])
                    and upper.field[py][px] not in d.WALL_CHARS
                ):
                    reachable.add(point)
                    pending.append(point)
        candidates = [
            (x, y)
            for y, row in enumerate(upper.field)
            for x, cell in enumerate(row)
            if cell == d.CHAR_FLOOR
            and lower.field[y][x] == d.CHAR_FLOOR
            and (x, y) in reachable
            and (x, y) not in fixed | occupied_upper | occupied_lower
            and all(
                abs(x - sx) + abs(y - sy) > 1
                for current in (upper, lower)
                for sx, sy in current.up_stairs + current.down_stairs
            )
        ]
        point = rand.choice(candidates)
        upper.scholar_down_stairs.append(point)
        lower.scholar_up_stairs.append(point)
