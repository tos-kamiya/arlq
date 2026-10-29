"""Boss dungeon, member trial, and party rules."""

from . import defs as d
from .arlq import GameConfig, create_field
from .i18n import t, trp
from .stage_maze import generate_floor_field, tile_at
from .stage_types import Floor
from .stage_world import (
    _add_filled_room_wall_notches,
    _add_wall_spurs,
    _place_collapses,
    _place_final_floor_barriers,
)
from .utils import rand


STAGE5_MEMBER_TRIAL_MAP = """##################################################
#         #     #g    E #            ===   X     #
#       f #   f #       #            ===    X    #
# @  f  f   K f      R ?    v  G b b ===   X     #
#         #     #       #            ===    X    #
#         #     # X     #            ===   X     #
################################################ #
################################################ #
#                                                #
# ####################################           #
#                                    #  b  b  H  #
#################################### #           #
#                                    #           #
# ################################################
# ################################################
#          #####  A A A #     A A A #            #
#          #####        #           #            #
#   b   D  .  ?   A A A   J   A A A       F  T   #
#          #####        #           #            #
#          #####    A A #       A A #            #
##################################################
##################################################"""
STAGE5_MEMBER_TRIAL_LOWER_MAP = """##################################################
####################            ##################
####################            ##################
####################        ^   ##################
####################            ##################
####################            ##################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
###########       ################################
###########       ################################
###########       ################################
###########       ################################
###########       ################################
##################################################
##################################################"""


def monster_party(current: Floor, first: d.Monster) -> list[d.Monster]:
    return monster_party_entities(current.entities, first)


def monster_party_entities(
    entities: list[d.Entity], first: d.Monster,
    *, positions: dict[d.Point, d.Monster] | None = None,
) -> list[d.Monster]:
    """Return the active vertically connected party containing ``first``."""
    candidates = monster_positions(entities) if positions is None else positions
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
    return bool(
        entity.tribe.item or entity.tribe.effect not in (None, d.EFFECT_UNLOCK_TREASURE)
    )


def normalize_parties(
    current: Floor, party_limit: int = d.MONSTER_PARTY_LIMIT
) -> None:
    """Enforce party limits after spawning or rearranging; retain W and V."""
    _separate_golems(current)
    positions = monster_positions(current.entities)
    checked = set()
    for entity in list(current.entities):
        if not isinstance(entity, d.Monster) or not entity.active or entity in checked:
            continue
        party = monster_party_entities(current.entities, entity, positions=positions)
        checked.update(party)
        party.sort(
            key=lambda monster: (
                0
                if monster.tribe.char == "W"
                else 1
                if monster.tribe.char == "V" and monster.empowered in (1, 2)
                else 2,
                monster.y,
                monster.x,
            )
        )
        kept = 0
        special = False
        for monster in party:
            is_special = special_monster(monster)
            if kept >= party_limit or (special and is_special):
                current.entities.remove(monster)
                positions = monster_positions(current.entities)
            else:
                kept += 1
                special |= is_special
    _separate_diagonal_monsters(current)
    _sync_wyrm_barriers(current)


def _neighbor_pairs(monsters: list[d.Monster], offsets: tuple[d.Point, ...]):
    """Visit adjacent pairs in entity order, preserving relocation choices."""
    positions: dict[d.Point, list[int]] = {}
    for index, monster in enumerate(monsters):
        positions.setdefault((monster.x, monster.y), []).append(index)
    for index, first in enumerate(monsters):
        neighbors = sorted(
            other
            for dx, dy in offsets
            for other in positions.get((first.x + dx, first.y + dy), ())
            if other > index
        )
        for other in neighbors:
            yield first, monsters[other]


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
                for first, second in _neighbor_pairs(
                    monsters, ((0, -1), (1, 0), (0, 1), (-1, 0))
                )
                if (first.tribe.char == "g" or second.tribe.char == "g")
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
            or (other.tribe.char == "V" and other.empowered in (1, 2))
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
    """Move non-boss monsters away from horizontal and diagonal neighbors."""
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
        for first, second in _neighbor_pairs(
            monsters, ((-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))
        ):
            first_is_boss = (first.tribe.char == "W" and first.empowered == 1) or (
                first.tribe.char == "V" and first.empowered in (1, 2)
            )
            second_is_boss = (
                second.tribe.char == "W" and second.empowered == 1
            ) or (second.tribe.char == "V" and second.empowered in (1, 2))
            if first_is_boss and second_is_boss:
                continue
            if (
                first.tribe.char == second.tribe.char == "X"
                and first.x in (43, 44)
                and second.x in (43, 44)
                and first.y in range(1, 6)
                and second.y in range(1, 6)
            ):
                continue
            mover = second if not second_is_boss else first
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


class TrialDialogue(str):
    """A tutorial line drawn in a small speech bubble."""


def trial_dialogue_lines(text: str, width: int, *, on_left: bool = False) -> list[str]:
    """Wrap dialogue into a one-line bubble or a two-line speech balloon."""
    width = max(8, width)
    words = text.split()
    lines = [""]
    for word in words:
        candidate = f"{lines[-1]} {word}".strip()
        if len(candidate) <= width or not lines[-1]:
            lines[-1] = candidate
        elif len(lines) == 1:
            lines.append(word)
        else:
            lines[-1] += f" {word}"
    if on_left:
        if len(lines) == 1:
            return [f"{lines[0]} >"]
        return [lines[0] + " " + chr(92), lines[1] + " /"]
    if len(lines) == 1:
        return [f"< {lines[0]}"]
    return [f"/ {lines[0]}", f"\\ {lines[1]}"]


TRIAL_MEMBER_LINES = {
    d.MEMBER_KNIGHT: "K: Two at once can be a lot. I can lend a hand.",
    d.MEMBER_ROGUE: "R: I can see through most traps.",
    d.MEMBER_GUARDIAN: "G: My enchanted shield can protect against barriers and spikes.",
    d.MEMBER_HEALER: "H: Take a healer on a long journey.",
    d.MEMBER_DUNGEON_EXPLORER: "D: I know caves. I can climb out of pits.",
    d.MEMBER_JESTER: "J: Here's a curious dance to help you gain experience.",
}


def trial_member_line(current: Floor, player: d.Player) -> str | None:
    for entity in current.entities:
        if (
            isinstance(entity, d.PartyMember)
            and entity.role not in player.joined_members
            and abs(entity.x - player.x) + abs(entity.y - player.y) == 1
            and entity.role in TRIAL_MEMBER_LINES
        ):
            return TrialDialogue(t(TRIAL_MEMBER_LINES[entity.role]))
    return None


def recruit(
    current: Floor,
    player: d.Player,
    member: d.PartyMember,
) -> str:
    player.joined_members.add(member.role)
    player.seen_members.add(member.role)
    if member.origin_floor is not None:
        player.known_member_floors.setdefault(member.role, member.origin_floor + 1)
    departed = (
        player.members.pop(0)
        if len(player.members) == d.PARTY_LIMIT
        else None
    )
    if departed is not None:
        player.seen_members.add(departed.role)
        player.known_member_floors.pop(departed.role, None)
    current.entities.remove(member)
    player.members.append(member)
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
                d.CHAR_SCHOLAR_STAIRS_UP
                if active
                else d.CHAR_HIDDEN_STAIRS_UP
            )
            if active:
                current.seen[y][x] = 1
        for point in current.scholar_down_stairs:
            x, y = point
            current.field[y][x] = (
                d.CHAR_SCHOLAR_STAIRS_DOWN
                if active
                else d.CHAR_HIDDEN_STAIRS_DOWN
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
    for x, y in current.d_gates:
        if known[y][x] and current.field[y][x] == d.CHAR_HIDDEN_D_GATE:
            current.field[y][x] = d.CHAR_D_GATE


def sync_members(player: d.Player, previous: d.Point, direction: d.Point) -> None:
    if (player.x, player.y) != previous:
        player.facing = direction
    for member in player.members:
        member.x, member.y = player.x, player.y


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


def rogue_danger(current: Floor, player: d.Player, destination: d.Point) -> str | None:
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
    if current.field[y][x] in (*d.WALL_CHARS, *d.STAIR_CHARS) or any(
        (entity.x, entity.y) == destination
        and (
            isinstance(entity, (d.Companion, d.Treasure))
            or isinstance(entity, d.Monster) and entity.active
        )
        for entity in current.entities
    ):
        return None
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
        *current.respawn_exclusions,
        *current.scholar_up_stairs,
        *current.scholar_down_stairs,
    }
    for entity in current.entities:
        if isinstance(entity, d.Collapse):
            reserved.update(d.collapse_footprint((entity.x, entity.y)))
    return [
        (x, y)
        for y, row in enumerate(current.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_FLOOR and (x, y) not in occupied | reserved
    ]


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
    candidates = [("b", 1), ("b", 2), ("c", 1), ("A", 1)]
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


def _sync_wyrm_barriers(current: Floor) -> None:
    """Keep monster barriers centered on the surviving w/W and f' monsters."""
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
        if not isinstance(entity, d.Monster) or not entity.active:
            continue
        offsets = _barrier_offsets(entity)
        for dx, dy in offsets:
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


def _barrier_offsets(
    entity: d.Monster, stage_num: int = 5
) -> tuple[d.Point, ...]:
    if entity.tribe.char in {"w", "W"}:
        return tuple(
            (dx, dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if dx or dy
        )
    if stage_num in (5, 6) and entity.tribe.char == "f" and entity.empowered == 2:
        return ((0, -1), (1, 0), (0, 1), (-1, 0))
    return ()


def _place_party(
    current: Floor, roster: list[tuple[str, int]], floor_index: int = 0
) -> None:
    # Keep parties separate horizontally and vertically. Members of each
    # party are placed vertically; walls and narrow corridors may be blocked.
    occupied = {(entity.x, entity.y) for entity in current.entities}
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
        seed = rand.choice(sorted(candidates))
        cells = [seed]
        while len(cells) < len(roster):
            frontier = sorted(
                {
                    (x + dx, y + dy)
                    for x, y in cells
                    for dx, dy in ((0, -1), (0, 1))
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
    raise RuntimeError("could not place Stage 6 monster party")


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
    if isinstance(d.CHAR_TO_TRIBE[char], d.MonsterTribe):
        monster_positions = {(entity.x, entity.y) for entity in monsters}
        candidates = [
            (x, y) for x, y in candidates
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
    member_roles = list(d.STAGE5_MEMBER_FLOORS[0])
    while len(member_roles) > 4:
        member_roles.pop(rand.randrange(len(member_roles)))
    member_floors = [(role, rand.randrange(3)) for role in member_roles]
    filled_counts_by_floor = [0] + [
        rand.choice((0, 1, 2)) for _ in range(d.STAGE5_FLOORS - 1)
    ]
    for index in range(d.STAGE5_FLOORS):
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
            split_room_graph=True,
            detach_leaf_room=True,
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
        if split_edge is not None:
            (x1, y1), (x2, y2) = split_edge
            if y1 == y2:
                gate = (
                    max(x1, x2) * (d.TILE_WIDTH + 1),
                    y1 * (d.TILE_HEIGHT + 1)
                    + 1
                    + (d.TILE_HEIGHT + 1 - config.corridor_h_width) // 2
                    + config.corridor_h_width // 2,
                )
            else:
                gate = (
                    x1 * (d.TILE_WIDTH + 1)
                    + 1
                    + (d.TILE_WIDTH + 1 - config.corridor_v_width) // 2
                    + config.corridor_v_width // 2,
                    max(y1, y2) * (d.TILE_HEIGHT + 1),
                )
            current.d_gates[gate] = "."
            current.field[gate[1]][gate[0]] = d.CHAR_HIDDEN_D_GATE
        _place_detached_room_monsters(current, room_components)
        for role, member_floor in member_floors:
            if member_floor != index:
                continue
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
            boss_party = list(d.STAGE5_BOSS_PARTY)
            boss_party.append(rand.choice(d.STAGE5_BOSS_ESCORTS))
            _place_party(current, boss_party, index)
            mimic = d.Monster(
                *rand.choice(_open_points(current)),
                d.CHAR_TO_MONSTER_TRIBE["M"],
                mimic_boss_char="W",
            )
            mimic.active = False
            current.entities.append(mimic)
        for char, count, rank in d.STAGE5_ROSTER[index]:
            for _ in range(count):
                party_size = (
                    1
                    if char == "g"
                    or (index > 0 and char == "k")
                    else sample_party_size(index)
                )
                roster = [(char, rank)] + [
                    rand.choice(d.STAGE5_SUPPORT_POOLS[index])
                    for _ in range(party_size - 1)
                ]
                _place_party(current, roster, index)
        if index == d.STAGE5_FLOORS - 1:
            boss = next(
                entity
                for entity in current.entities
                if isinstance(entity, d.Monster) and entity.tribe.char == "W"
            )
            boss_zone = tile_at((boss.x, boss.y))
            treasure_points = [
                point for point in _open_points(current) if tile_at(point) != boss_zone
            ]
            current.entities.append(
                d.Treasure(*rand.choice(treasure_points), "TW")
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
    _place_additional_stairs(floors)
    _place_final_floor_barriers(
        floors[-1], d.STAGE5_FINAL_FLOOR_BARRIER_PERCENT
    )
    for current in floors:
        normalize_parties(current, d.STAGE5_PARTY_LIMIT)
    player = d.Player(*floors[0].up, d.STAGE5_START_LEVEL, d.LP_INIT)
    player.rescue_stage = True
    player.treasure_stage = True
    return floors, player


def build_member_trial(config: GameConfig | None = None) -> tuple[list[Floor], d.Player]:
    """Build both Stage 5 tutorial floors from their in-code ASCII maps."""
    member_roles = {glyph: role for role, glyph in d.MEMBER_GLYPHS.items()}

    def check_map(rows: list[str], label: str) -> None:
        if len(rows) != d.FIELD_HEIGHT or any(len(row) > d.FIELD_WIDTH for row in rows):
            raise ValueError(f"{label} ASCII map dimensions do not match the field")

    upper_rows = STAGE5_MEMBER_TRIAL_MAP.splitlines()
    lower_rows = STAGE5_MEMBER_TRIAL_LOWER_MAP.splitlines()
    check_map(upper_rows, "Stage 5 floor 1")
    check_map(lower_rows, "Stage 5 floor 2")

    def blank_field() -> list[list[str]]:
        return [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]

    upper_field = blank_field()
    upper_seen = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    upper_entities: list[d.Entity] = []
    upper_barriers: set[d.Point] = set()
    upper_gates: dict[d.Point, str] = {}
    start = upper_stair = None
    upper_pits: list[d.Point] = []

    for y, row in enumerate(upper_rows):
        for x, glyph in enumerate(row):
            point = (x, y)
            if glyph == d.CHAR_WALL:
                continue
            if glyph == "=":
                upper_field[y][x] = d.CHAR_BARRIER
                upper_barriers.add(point)
                continue
            if glyph == d.CHAR_CALTROP:
                upper_field[y][x] = d.CHAR_CALTROP
                continue
            upper_field[y][x] = d.CHAR_FLOOR
            if glyph == "@":
                start = point
            elif glyph == d.CHAR_STAIRS_DOWN:
                upper_stair = point
                upper_field[y][x] = d.CHAR_STAIRS_DOWN
            elif glyph == ".":
                upper_field[y][x] = d.CHAR_HIDDEN_D_GATE
                upper_gates[point] = d.CHAR_D_GATE
            elif glyph == "?":
                upper_pits.append(point)
                upper_entities.append(d.Collapse(x, y))
            elif glyph in member_roles:
                upper_entities.append(
                    d.PartyMember(x, y, member_roles[glyph], origin_floor=0)
                )
            elif glyph == "T":
                upper_entities.append(d.Treasure(x, y, "TF"))
            elif glyph in d.CHAR_TO_MONSTER_TRIBE:
                upper_entities.append(
                    d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[glyph])
                )
            elif glyph != d.CHAR_FLOOR:
                raise ValueError(f"Unsupported Stage 5 floor 1 glyph: {glyph!r}")

    if start is None or upper_stair is None or not upper_pits or not upper_gates:
        raise ValueError("Stage 5 floor 1 needs @, v, ?, and . markers")

    lower_field = blank_field()
    lower_seen = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    lower_barriers: set[d.Point] = set()
    lower_gates: dict[d.Point, str] = {}
    lower_stair = None
    for y, row in enumerate(lower_rows):
        for x, glyph in enumerate(row):
            point = (x, y)
            if glyph == d.CHAR_WALL:
                continue
            if glyph == "=":
                lower_field[y][x] = d.CHAR_BARRIER
                lower_barriers.add(point)
            elif glyph == d.CHAR_CALTROP:
                lower_field[y][x] = d.CHAR_CALTROP
            elif glyph == "^":
                lower_stair = point
                lower_field[y][x] = d.CHAR_STAIRS_UP
            elif glyph == ".":
                lower_field[y][x] = d.CHAR_HIDDEN_D_GATE
                lower_gates[point] = d.CHAR_D_GATE
            elif glyph == d.CHAR_FLOOR:
                lower_field[y][x] = d.CHAR_FLOOR
            else:
                raise ValueError(f"Unsupported Stage 5 floor 2 glyph: {glyph!r}")

    if lower_stair is None or any(
        lower_field[y][x] != d.CHAR_FLOOR for x, y in upper_pits
    ):
        raise ValueError("Stage 5 floor 2 needs ^ and open floor below every pit")

    upper = Floor(
        upper_field, upper_entities, upper_seen, start, upper_stair, None,
        up_stairs=[start], down_stairs=[upper_stair],
        d_gates=upper_gates, persistent_barriers=upper_barriers,
    )
    lower = Floor(
        lower_field, [], lower_seen, upper_pits[0], lower_stair, None,
        up_stairs=[lower_stair],
        collapse_landings=set().union(
            *(d.collapse_footprint(point) for point in upper_pits)
        ),
        d_gates=lower_gates, persistent_barriers=lower_barriers,
    )
    player = d.Player(*start, 25, d.LP_INIT)
    player.rescue_stage = True
    player.treasure_stage = True
    return [upper, lower], player


def _add_trial_detached_room(current: Floor, config: GameConfig) -> None:
    """Add a fixed isolated room to the right of Stage 5's bottom-right tile."""
    active_tile_columns = 3
    tile_offset_x = (d.TILE_NUM_X - active_tile_columns) // 2
    room_x = tile_offset_x + active_tile_columns
    room_y = d.TILE_NUM_Y - 1
    left = room_x * (d.TILE_WIDTH + 1) + 1
    top = room_y * (d.TILE_HEIGHT + 1) + 1
    for y in range(top, top + d.TILE_HEIGHT):
        for x in range(left, left + d.TILE_WIDTH):
            current.field[y][x] = d.CHAR_FLOOR

    gate = (
        room_x * (d.TILE_WIDTH + 1),
        room_y * (d.TILE_HEIGHT + 1)
        + 1
        + (d.TILE_HEIGHT + 1 - config.corridor_h_width) // 2
        + config.corridor_h_width // 2,
    )
    current.field[gate[1]][gate[0]] = d.CHAR_HIDDEN_D_GATE
    current.d_gates[gate] = d.CHAR_D_GATE


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
                and current.field[py][px]
                not in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
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
    """Add a second ordinary paired staircase on each floor transition."""
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
        upper.scholar_down_stairs.append(point)
        lower.scholar_up_stairs.append(point)
        x, y = point
        upper.field[y][x] = d.CHAR_HIDDEN_STAIRS_DOWN
        lower.field[y][x] = d.CHAR_HIDDEN_STAIRS_UP
