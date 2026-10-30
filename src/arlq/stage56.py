"""Gameplay mechanics shared by Stages 5 and 6."""

from . import defs as d
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


def normalize_parties(current: Floor, party_limit: int = d.MONSTER_PARTY_LIMIT) -> None:
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
        other_is_fixed = isinstance(other, d.Collapse) or _fixed_boss(other)
        mover = golem if other_is_fixed or other.tribe.char == "g" else other

        if not _relocate_isolated_monster(current, mover, include_collapses=True):
            return


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
            first_is_boss = _fixed_boss(first)
            second_is_boss = _fixed_boss(second)
            if first_is_boss and second_is_boss:
                continue
            if (
                first.tribe.char == second.tribe.char == "X"
                and (first.x, first.y) in current.adjacent_monster_exemptions
                and (second.x, second.y) in current.adjacent_monster_exemptions
            ):
                continue
            mover = second if not second_is_boss else first
            break
        if mover is None:
            return

        if not _relocate_isolated_monster(current, mover, include_collapses=False):
            return


def _fixed_boss(monster: d.Monster) -> bool:
    return (monster.tribe.char == "W" and monster.empowered == 1) or (
        monster.tribe.char == "V" and monster.empowered in (1, 2)
    )


def _relocate_isolated_monster(
    current: Floor, mover: d.Monster, *, include_collapses: bool
) -> bool:
    current.entities.remove(mover)
    other_monsters = [
        entity for entity in current.entities
        if isinstance(entity, d.Monster)
        and (include_collapses or not isinstance(entity, d.Collapse))
        and entity.active and not entity.tribe.is_elf
    ]
    candidates = [
        point for point in _open_points(current)
        if all(
            abs(point[0] - other.x) > 1 or abs(point[1] - other.y) > 1
            for other in other_monsters
        )
    ]
    if candidates:
        mover.x, mover.y = rand.choice(candidates)
    current.entities.append(mover)
    return bool(candidates)


def recruit(
    current: Floor,
    player: d.Player,
    member: d.PartyMember,
) -> str:
    player.joined_members.add(member.role)
    player.seen_members.add(member.role)
    if member.origin_floor is not None:
        player.known_member_floors.setdefault(member.role, member.origin_floor + 1)
    departed = player.members.pop(0) if len(player.members) == d.PARTY_LIMIT else None
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
        for point in barrier_cells(current, entity):
            x, y = point
            if (
                point not in occupied
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

    existing_barriers = {
        (x, y) for y, row in enumerate(current.field)
        for x, cell in enumerate(row) if cell == d.CHAR_BARRIER
    }
    clear_monster_barriers(current, existing_barriers, ring_cells)
    for x, y in ring_cells:
        if current.field[y][x] == d.CHAR_FLOOR:
            current.field[y][x] = d.CHAR_BARRIER


def _barrier_offsets(entity: d.Monster, stage_num: int = 5) -> tuple[d.Point, ...]:
    if entity.tribe.char in {"w", "W"}:
        return tuple((dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
    if stage_num in (5, 6) and entity.tribe.char == "f" and entity.empowered == 2:
        return ((0, -1), (1, 0), (0, 1), (-1, 0))
    return ()


def barrier_cells(
    current: Floor, entity: d.Monster, stage_num: int = 5
) -> tuple[d.Point, ...]:
    """Monster barrier footprint clipped to the floor."""
    return tuple(
        (entity.x + dx, entity.y + dy)
        for dx, dy in _barrier_offsets(entity, stage_num)
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
) -> d.Point:
    candidates = [point for point in _open_points(current) if point not in avoid]
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
    point = rand.choice(candidates)
    tribe = d.CHAR_TO_TRIBE[char]
    if isinstance(tribe, d.MonsterTribe):
        entity = d.Monster(*point, tribe, rank)
    else:
        entity = d.Companion(*point, tribe, origin_floor=origin_floor)
    current.entities.append(entity)
    return point
