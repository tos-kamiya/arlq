"""Shared stage loop with multi-floor rules for Stages 3 and 4."""

import heapq
from collections import Counter, deque
from copy import deepcopy
from typing import Any, Container, Deque, List, Optional, Set, Tuple

from . import defs as d
from .arlq import (
    MESSAGE_TICKS,
    GameConfig,
    activate_mimic_for_defeat,
    find_random_place,
    get_torched,
    iterate_ellipse_points,
    iterate_offsets,
    move_player,
    respawn_entity,
    reveal_entities_in_fov,
    spawn_at,
    spread_caltrops,
    tick_message,
    unlock_treasure_for_defeat,
    update_entities,
)
from .game_events import WorldEvent
from .i18n import t as tr
from .stage_replay import rewind_to_history as _rewind_to_history
from .stage_types import (
    Floor,
    HistoryEntry,
    ReplayContext,
    _ContactResult,
    _RewindRequest,
)
from .stage_world import (
    build_single_floor,
    _inside_island,
    build,
    build_trap_test,
)
from .trace import DIR_TO_KEY, TraceRecorder
from .utils import rand

ELF_REPEAT_MESSAGES = {
    "K": "-- The Collector Elf (K) looks satisfied.",
    "H": "-- Keep the talisman close to your skin.",
}


def _find_escape_place(current: Floor, far_from: Optional[d.Point] = None) -> d.Point:
    """Find an open destination outside a sealed island room."""
    return find_random_place(
        current.entities,
        current.field,
        distance=2,
        far_from=far_from,
        avoid=lambda point: _inside_island(point, current.island),
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
    """Spawn an entity through the shared game helpers."""
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


def _marksman_damage_at(
    field: List[List[str]],
    entities: List[d.Entity],
    known: List[List[int]],
    point: d.Point,
) -> int:
    """Return damage from marksmen whose presence is known to the player."""
    damage = 0
    x, y = point
    blockers = [
        entity
        for entity in entities
        if not isinstance(entity, d.Player)
        and 0 <= entity.x < len(field[0])
        and 0 <= entity.y < len(field)
        and known[entity.y][entity.x]
    ]
    shooters = [
        entity
        for entity in entities
        if isinstance(entity, d.Monster)
        and entity.tribe.char == "k"
        and entity.active
        and 0 <= entity.x < len(field[0])
        and 0 <= entity.y < len(field)
        and (known[entity.y][entity.x] or bool(entity.arrow_marks))
    ]
    for shooter in shooters:
        dx, dy = x - shooter.x, y - shooter.y
        if (dx == 0) == (dy == 0):
            continue
        distance = abs(dx or dy)
        if distance <= 1:
            continue
        step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
        step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
        blocked = False
        for offset in range(1, distance):
            bx, by = shooter.x + step_x * offset, shooter.y + step_y * offset
            if field[by][bx] in (
                d.WALL_CHAR,
                d.CHAR_CALTROP,
                d.CHAR_BARRIER,
                *d.STAIR_CHARS,
            ):
                blocked = True
                break
            if any(
                (other.x, other.y) == (bx, by)
                and (
                    isinstance(other, d.Companion)
                    or isinstance(other, d.Treasure)
                    or isinstance(other, d.Collapse)
                    and not other.revealed
                    or isinstance(other, d.Monster)
                    and other.active
                )
                for other in blockers
            ):
                blocked = True
                break
        if not blocked:
            damage += d.MARKSMAN_LP_DAMAGE
    return damage


def reachable_known_cells(
    field: List[List[str]],
    seen: List[List[int]],
    visible: List[List[int]],
    entities: List[d.Entity],
    player: d.Player,
    stage_num: int,
) -> Set[d.Point]:
    """Find all known cells reachable before the player's LP reaches zero."""
    height = len(field)
    width = len(field[0]) if field else 0
    if not width or not (0 <= player.x < width and 0 <= player.y < height):
        return set()

    known = [
        [int(seen[y][x] or visible[y][x]) for x in range(width)] for y in range(height)
    ]
    blocked = {
        (entity.x, entity.y)
        for entity in entities
        if not isinstance(entity, d.Player)
        and 0 <= entity.x < width
        and 0 <= entity.y < height
        and known[entity.y][entity.x]
    }
    start = (player.x, player.y)
    distances = {start: 0}
    pending = [(0, player.y, player.x)]
    neighbors = ((0, -1), (-1, 0), (1, 0), (0, 1))

    while pending:
        cost, y, x = heapq.heappop(pending)
        point = (x, y)
        if cost != distances[point]:
            continue
        for dx, dy in neighbors:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if not known[ny][nx] or (nx, ny) in blocked:
                continue

            cell = field[ny][nx]
            if cell == d.CHAR_FLOOR:
                terrain_cost = 1
            elif cell == d.CHAR_CALTROP:
                terrain_cost = 1 + d.CALTROP_LP_DAMAGE
            elif cell == d.CHAR_BARRIER and stage_num not in (1, 2):
                damage = (
                    0 if player.elf_stage_flags & d.ELF_STAGE_H_FLAG else d.BARRIER_LP_DAMAGE
                )
                terrain_cost = 1 + damage
            else:
                # Walls, stairs, and unknown/special terrain are not safe
                # walking cells for this estimate.
                continue

            ranged_damage = _marksman_damage_at(field, entities, known, (nx, ny))
            next_cost = cost + terrain_cost + ranged_damage
            if next_cost >= player.lp:
                continue
            next_point = (nx, ny)
            if next_cost >= distances.get(next_point, player.lp):
                continue
            distances[next_point] = next_cost
            heapq.heappush(pending, (next_cost, ny, nx))

    return set(distances)


def _move_player(
    direction: d.Point,
    current: Floor,
    player: d.Player,
    trace: Optional[TraceRecorder] = None,
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


def _apply_terrain_hazards(
    current: Floor, player: d.Player, previous: d.Point
) -> Optional[str]:
    """Apply barrier/caltrop damage for the player's current cell.

    Returns an event message for the barrier case, or None otherwise (caltrop
    damage never produces a message, matching the legacy stages).
    """
    field = current.field
    event_message = None
    if (
        field[player.y][player.x] == d.CHAR_BARRIER
        and not (player.elf_stage_flags & d.ELF_STAGE_H_FLAG)
        and (player.x, player.y) != previous
    ):
        player.lp -= d.BARRIER_LP_DAMAGE
        event_message = tr("-- The barrier burns you.")
    if field[player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= d.CALTROP_LP_DAMAGE
        field[player.y][player.x] = d.CHAR_FLOOR
    return event_message


def _marksman_shoot(current: Floor, player: d.Player) -> None:
    """Resolve Stage 4 marksmen after a player move and retain their arrow marks."""
    for entity in current.entities:
        if (
            not isinstance(entity, d.Monster)
            or entity.tribe.char != "k"
            or not entity.active
        ):
            continue
        dx, dy = player.x - entity.x, player.y - entity.y
        if (dx == 0) == (dy == 0):
            continue
        distance = abs(dx or dy)
        if distance == 1:
            continue

        step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
        step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
        blocked = False
        for offset in range(1, distance):
            x, y = entity.x + step_x * offset, entity.y + step_y * offset
            if current.field[y][x] in (
                d.WALL_CHAR,
                d.CHAR_CALTROP,
                d.CHAR_BARRIER,
                *d.STAIR_CHARS,
            ):
                blocked = True
                break
            if any(
                (other.x, other.y) == (x, y)
                and (
                    isinstance(other, d.Companion)
                    or isinstance(other, d.Treasure)
                    or isinstance(other, d.Collapse)
                    and not other.revealed
                    or isinstance(other, d.Monster)
                    and other.active
                )
                for other in current.entities
            ):
                blocked = True
                break
        if blocked:
            continue

        player.lp -= d.MARKSMAN_LP_DAMAGE
        player.known_monsters.add(d.monster_type_key(entity))
        mark = ((player.x - step_x, player.y - step_y), "-" if step_x else "|")
        marks = entity.arrow_marks
        marks[:] = [existing for existing in marks if existing[0] != mark[0]]
        marks.append(mark)
        arrow_limit = d.MARKSMAN_ARROW_LIMIT
        if len(marks) > arrow_limit:
            del marks[0]


def _vortex_rearrange(
    current: Floor,
    player: d.Player,
    floor_index: int,
    center: d.Point,
) -> None:
    """Reposition entities and forget explored cells near the Vortex."""
    # Keep the horizontal reach while matching the FOV ellipse's proportions.
    horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
    radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
    affected_points = set(
        iterate_ellipse_points(
            center[0], center[1], radius, d.FOV_WIDTH_EXPANSION_RATIO
        )
    )
    movable = [
        entity
        for entity in current.entities
        if (entity.x, entity.y) in affected_points
        and (
            isinstance(entity, (d.Companion, d.Treasure))
            or (
                isinstance(entity, d.Monster)
                and entity.active
                and not entity.tribe.is_elf
                and entity.tribe.effect != d.EFFECT_VORTEX
            )
        )
    ]
    avoid = {(player.x, player.y)} | {(entity.x, entity.y) for entity in movable}
    for entity in movable:
        if isinstance(entity, d.Monster) and entity.tribe.char == "k":
            entity.arrow_marks.clear()
    current.entities[:] = [
        entity for entity in current.entities if entity not in movable
    ]

    # Clear and rebuild only barriers inside the Vortex's affected area.
    for x, y in affected_points:
        if current.field[y][x] == d.CHAR_BARRIER:
            current.field[y][x] = d.CHAR_FLOOR

    def relocate(char: str, origin_floor: Optional[int], empowered: int = 1) -> None:
        x, y = find_random_place(
            current.entities,
            current.field,
            distance=2,
            avoid=lambda point: point not in affected_points
            or point in avoid
            or _inside_island(point, current.island),
        )
        spawn_at(
            current.entities,
            x,
            y,
            d.CHAR_TO_TRIBE[char],
            empowered=empowered,
            origin_floor=origin_floor,
        )

    for entity in movable:
        if isinstance(entity, d.Treasure):
            reserved = avoid | set(current.up_stairs + current.down_stairs)
            entity.x, entity.y = find_random_place(
                current.entities,
                current.field,
                distance=2,
                avoid=lambda point: point not in affected_points
                or point in reserved
                or _inside_island(point, current.island),
            )
            current.entities.append(entity)
        else:
            char = entity.tribe.char
            empowered = entity.empowered if isinstance(entity, d.Monster) else 1
            origin_floor = (
                entity.origin_floor if isinstance(entity, d.Companion) else floor_index
            )
            relocate(char, origin_floor, empowered)

    for current_entity in current.entities:
        if isinstance(current_entity, d.Monster) and current_entity.tribe.char in {"w", "W"}:
            protected = {
                (fixed.x, fixed.y)
                for fixed in current.entities
                if isinstance(fixed, d.Collapse)
            } | current.collapse_landings
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    point = (current_entity.x + dx, current_entity.y + dy)
                    x, y = point
                    if (
                        (dx or dy)
                        and point in affected_points
                        and current.field[y][x] == d.CHAR_FLOOR
                        and point not in protected
                    ):
                        current.field[y][x] = d.CHAR_BARRIER

    known_collapses = {
        (entity.x, entity.y)
        for entity in current.entities
        if isinstance(entity, d.Collapse) and entity.revealed
    }
    for x, y in affected_points:
        if (
            current.field[y][x] in (d.CHAR_FLOOR, d.CHAR_BARRIER)
            and (x, y) not in known_collapses
        ):
            current.seen[y][x] = 0


def _defeat_monster(
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    trace: Optional[TraceRecorder] = None,
    floors: Optional[List[Floor]] = None,
    replay_context: Optional[ReplayContext] = None,
    operation_index: Optional[int] = None,
) -> None:
    """Apply the effects of successfully defeating `entity` in combat."""
    ch = entity.tribe.char
    if ch == "k":
        entity.arrow_marks.clear()
    if ch == "M":
        entity.met = True
        entity.active = False

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
            trace.add_expired(
                {"type": "item_expired", "item": old_source, "reason": "overwritten"}
            )

    unlock_treasure_for_defeat(entity, current.entities)
    activate_mimic_for_defeat(entity, current.entities)
    if ch == "W":
        player.elf_stage_flags |= d.STAGE3_W_FLAG
        player.known_monsters.add(d.monster_type_key(entity))
        player.boss_defeated = True
    if ch == "K":
        player.elf_stage_flags |= d.ELF_STAGE_K_FLAG
        d.clear_player_item(player)
    if ch == "H":
        player.elf_stage_flags |= d.ELF_STAGE_H_FLAG
    if ch == "C":
        player.elf_stage_flags |= d.ELF_STAGE_C_FLAG
    d.grant_defeat_level(player, entity.tribe.effect)
    d.apply_feed(player, entity.tribe.feed)
    player.karma += 1

    if entity.tribe.effect == d.EFFECT_CALTROP_SPREAD:
        spread_caltrops(current.field, (player.x, player.y), current.entities)
    elif entity.tribe.effect == d.EFFECT_ROCK_SPREAD:
        for x, y in iterate_offsets(
            player.x,
            player.y,
            d.ROCK_SPREAD_OFFSETS,
            except_for_entities=current.entities,
        ):
            if (x, y) not in current.collapse_landings and current.field[y][
                x
            ] == d.CHAR_FLOOR:
                current.field[y][x] = d.WALL_CHAR
    elif entity.tribe.effect == d.EFFECT_VORTEX:
        if (
            replay_context is not None
            and floors is not None
            and operation_index is not None
        ):
            replay_context.vortex_maps.append(
                (
                    operation_index,
                    deepcopy([floor_data.seen for floor_data in floors]),
                )
            )
        _vortex_rearrange(current, player, floor[0], (entity.x, entity.y))

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
    floors: Optional[List[Floor]] = None,
    replay_context: Optional[ReplayContext] = None,
    operation_index: Optional[int] = None,
) -> _ContactResult:
    """Resolve contact with a monster, including early-ending elf encounters."""
    ch = entity.tribe.char
    contact_key = (floor[0], entity.x, entity.y)

    if entity.tribe.is_elf:
        player.elf_stage_floors.setdefault(ch, floor[0] + 1)
        player.known_elf_floors.add(ch)

    if entity.tribe.is_elf and entity.met:
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
                tr(
                    "-- The Isolated Elf wants to be left alone, and sends you elsewhere."
                ),
                end_turn=True,
            )
        if ch in ELF_REPEAT_MESSAGES:
            current.entities.append(entity)
            return _ContactResult(tr(ELF_REPEAT_MESSAGES[ch]), end_turn=True)
        return _ContactResult(None, end_turn=True)

    # Stage 3 keeps the W treasure hidden until W is defeated. Other monster
    # identities, including M, are learned by species.
    was_known = d.monster_type_key(entity) in player.known_monsters
    if ch != "W" and not entity.tribe.is_elf:
        player.known_monsters.add(d.monster_type_key(entity))
    if entity.tribe.is_elf:
        entity.revealed = True
        if player.item == d.ITEM_SPORES:
            source = player.item_taken_from
            d.clear_player_item(player)
            if trace is not None and source is not None:
                trace.add_expired(
                    {
                        "type": "item_expired",
                        "item": source,
                        "reason": "cleared_on_contact",
                    }
                )
    if ch == "M" and not was_known and trace is not None:
        trace.record_contact(
            {"type": "trap", "id": d.monster_type_key(entity), "outcome": "triggered"}
        )
    current.entities.pop(hit)

    if ch == "I":
        player.elf_stage_flags |= d.ELF_STAGE_I_FLAG
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "I", "outcome": "granted"})
    elif ch == "J":
        player.elf_stage_flags |= d.ELF_STAGE_J_FLAG
        player.persistent_followers.append((player.x, player.y, floor[0], "J"))
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "J", "outcome": "granted"})
    elif ch == "K" and not (player.elf_stage_flags & d.ELF_STAGE_C_FLAG):
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
    elif (
        ch == "H"
        and (
            player.elf_stage_flags
            & (
                d.ELF_STAGE_I_FLAG
                | d.ELF_STAGE_J_FLAG
                | d.ELF_STAGE_K_FLAG
                | d.ELF_STAGE_L_FLAG
            )
        ).bit_count()
        < 2
    ):
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
    elif ch == "L":
        old_lp_max = d.player_lp_max(player)
        player.lifebringer_lp_max = min(
            old_lp_max + d.LIFEBRINGER_LP_MAX_INCREASE,
            d.LP_MAX_LIFEBRINGER,
        )
        player.elf_stage_flags |= d.ELF_STAGE_L_FLAG
        player.lp = d.LP_OVERCHARGE_MAX
        if player.lifebringer_lp_max > old_lp_max:
            event_message = tr(
                "-- The Lifebringer Elf raised your permanent LP maximum "
                "and restored your LP to 120!"
            )
        else:
            event_message = tr("-- The Lifebringer Elf restored your LP to 120!")
        spawn_key = (floor[0], d.monster_type_key(entity))
        queue[spawn_key] = queue.get(spawn_key, 0) + 1
        if trace is not None:
            trace.record_contact({"type": "elf", "id": "L", "outcome": "granted"})
    elif d.current_player_attack(player) < d.monster_level(entity):
        # Losing still identifies the monster, including W. Treasure glyphs
        # remain gated separately by their unlock state in the renderer.
        if not entity.tribe.is_elf:
            player.known_monsters.add(d.monster_type_key(entity))
        # The encounter remains on the map when the player loses. Rust
        # resolves combat before removing the monster; keeping the entity
        # here prevents a failed attack from deleting it.
        current.entities.append(entity)
        first_mimic_contact = ch == "M" and not was_known
        # Losing twice in a row to the very same monster (no other monster
        # contact in between) means it is blocking the only way through:
        # send the player somewhere random instead of back to the
        # checkpoint, so a too-strong monster on a bridge corridor cannot
        # soft-lock the floor.
        if player.last_contact_monster == contact_key:
            player.x, player.y = _find_escape_place(current, (entity.x, entity.y))
            event_message = tr("-- Respawned to a random location.")
        else:
            player.x, player.y = checkpoint[0]
            # Keep the monster that caused this respawn visible for the next
            # frame, even when the checkpoint is outside its FOV.
            current.contact_reveal = (entity.x, entity.y)
            event_message = tr("-- Respawned!")
        if first_mimic_contact:
            event_message = tr("-- The treasure chest was a Mimic! You respawned.")
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
            trace.add_expired(
                {"type": "item_expired", "item": old_source, "reason": "lost_on_defeat"}
            )
    else:
        if trace is not None:
            trace.record_contact(
                {"type": "monster", "id": d.monster_type_key(entity), "outcome": "win"}
            )
        _defeat_monster(
            entity,
            current,
            player,
            floor,
            checkpoint,
            queue,
            trace=trace,
            floors=floors,
            replay_context=replay_context,
            operation_index=operation_index,
        )
        if ch == "M":
            current.entities.append(entity)
        if ch == "M" and was_known:
            event_message = tr("-- The Mimic was defeated!")
        elif ch == "M":
            event_message = tr("-- The treasure chest was a Mimic!")
        if ch == "W" and player.treasure_collected:
            event_message = tr(">> The King's request is complete! <<")

    if entity.tribe.is_elf and ch not in ("J", "L") and entity not in current.entities:
        entity.met = True
        current.entities.append(entity)
    elif entity.tribe.is_elf and entity not in current.entities:
        entity.met = True

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
    replay_context: Optional[ReplayContext] = None,
    operation_index: Optional[int] = None,
) -> _ContactResult:
    """Resolve contact with the entity at `hit` in current.entities.

    The result explicitly marks encounters that end the turn immediately,
    bypassing the usual end-of-turn processing (Loop Companion rewind and
    repeated elf contact).
    """
    entity = current.entities[hit]

    if isinstance(entity, d.Treasure):
        collected = entity.unlocked
        if trace is not None:
            trace.record_contact(
                {"type": "treasure", "id": entity.unlock_key, "collected": collected}
            )
        if collected:
            current.entities.pop(hit)
            player.treasure_collected = True
            if not (player.elf_stage_flags & d.STAGE3_W_FLAG):
                event_message = tr(
                    "-- You took the treasure chest, but the King's request remains."
                )
        return _ContactResult(event_message)

    if isinstance(entity, d.Companion):
        ch = entity.tribe.char
        if trace is not None:
            trace.record_contact({"type": "companion", "id": ch})
        # The game loop handles rewind after this step returns its request.
        if ch == "l" and history:
            entity.revealed = True
            return _ContactResult(
                None, end_turn=True, message_ticks=5, rewind_requested=True
            )
        entity.revealed = True
        current.entities.pop(hit)
        player.companion = entity
        player.karma = 0
        tribe_message = entity.tribe.event_message
        return _ContactResult(tr(tribe_message) if tribe_message else None)

    assert isinstance(entity, d.Monster)
    if entity.tribe.char == "M" and not entity.active:
        return _ContactResult(event_message)
    return _resolve_monster_contact(
        hit,
        entity,
        current,
        player,
        floor,
        checkpoint,
        queue,
        event_message,
        trace=trace,
        floors=floors,
        replay_context=replay_context,
        operation_index=operation_index,
    )


def _advance_persistent_followers(
    player: d.Player, floor_index: int, moved: bool, previous: d.Point
) -> None:
    """The Javelin Elf follows one step behind; keep its recorded position in sync."""
    for i, follower in enumerate(player.persistent_followers):
        if follower[2] == floor_index and moved:
            player.persistent_followers[i] = (
                previous[0],
                previous[1],
                follower[2],
                follower[3],
            )


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
    floor_count = len(floors)
    if floor[0] < floor_count - 1 and point in down_stairs:
        stair_index = down_stairs.index(point)
        floor[0] += 1
        destination_stairs = floors[floor[0]].up_stairs or [floors[floor[0]].up]
        player.x, player.y = destination_stairs[
            min(stair_index, len(destination_stairs) - 1)
        ]
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [
            (player.x, player.y, floor[0], ch)
            for _, _, _, ch in player.persistent_followers
        ]
        return tr("-- Descended to floor {n}/{total}.").format(
            n=floor[0] + 1, total=floor_count
        )
    if floor[0] > 0 and point in up_stairs:
        stair_index = up_stairs.index(point)
        floor[0] -= 1
        destination_stairs = floors[floor[0]].down_stairs or [floors[floor[0]].down]
        player.x, player.y = destination_stairs[
            min(stair_index, len(destination_stairs) - 1)
        ]
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [
            (player.x, player.y, floor[0], ch)
            for _, _, _, ch in player.persistent_followers
        ]
        return tr("-- Ascended to floor {n}/{total}.").format(
            n=floor[0] + 1, total=floor_count
        )
    return None


def _reveal_paired_stair_cells(floors: List[Floor]) -> None:
    """Mark a stair's matching cell on the adjacent floor as known."""
    for index in range(len(floors) - 1):
        upper = floors[index]
        lower = floors[index + 1]
        down_stairs = upper.down_stairs or [upper.down]
        up_stairs = lower.up_stairs or [lower.up]
        for stair_index, upper_point in enumerate(down_stairs):
            lower_point = up_stairs[min(stair_index, len(up_stairs) - 1)]
            ux, uy = upper_point
            lx, ly = lower_point
            if upper.seen[uy][ux] or lower.seen[ly][lx]:
                upper.seen[uy][ux] = 1
                lower.seen[ly][lx] = 1


def _process_respawn_queue(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    queue: Counter[Tuple[int, str]],
    turn: int,
    trace: Optional[TraceRecorder] = None,
) -> None:
    if turn % d.MONSTER_RESPAWN_INTERVAL != 0:
        return
    for (queued_floor, type_key), count in list(queue.items()):
        if not count:
            continue
        ch = type_key[:-1] if type_key[-1].isdigit() else type_key
        tribe = d.CHAR_TO_TRIBE[ch]
        spawn_floor = (
            rand.randrange(len(floors))
            if getattr(tribe, "respawn_on_random_floor", False)
            else queued_floor
        )
        avoid = {(player.x, player.y)} if spawn_floor == floor[0] else set()
        if type_key[-1].isdigit():
            ch = type_key[:-1]
            empowered = int(type_key[-1])
        else:
            ch = type_key
            empowered = 1
        args = (
            floors[spawn_floor].entities,
            floors[spawn_floor].field,
            ch,
            avoid,
            floors[spawn_floor].island,
            spawn_floor,
        )
        previous_entity_count = len(floors[spawn_floor].entities)
        if empowered == 1:
            x, y = _spawn(*args)
        else:
            x, y = _spawn(*args, empowered)
        if len(floors[spawn_floor].entities) > previous_entity_count:
            respawned = floors[spawn_floor].entities[-1]
            if isinstance(respawned, d.Companion):
                respawned.revealed = True
            elif isinstance(respawned, d.Elf):
                if respawned.tribe.char == "L":
                    # Lifebringer grants its LP restoration on every contact,
                    # so a respawned L must be treated as not yet met.
                    respawned.met = False
                    respawned.revealed = True
                else:
                    respawned.met = True
        queue[(queued_floor, type_key)] -= 1
        if trace is not None:
            if isinstance(respawned, d.Elf):
                kind = "elf"
            elif isinstance(respawned, d.Monster):
                kind = "monster"
            else:
                kind = "companion"
            trace.add_world_event(
                {
                    "type": "respawn",
                    "kind": kind,
                    "id": type_key,
                    "at": [x, y],
                    "floor": spawn_floor,
                }
            )


def _step(
    direction: d.Point,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    history: Deque[HistoryEntry],
    turn: int,
    stage_num: int = 3,
    trace: Optional[TraceRecorder] = None,
    replay_context: Optional[ReplayContext] = None,
    operation_index: Optional[int] = None,
) -> Optional[Tuple[int, str]] | _RewindRequest:
    current = floors[floor[0]]
    history.append(None)
    if len(history) > d.LOOP_TURNS:
        history.popleft()

    previous = (player.x, player.y)
    _move_player(direction, current, player, trace=trace)
    movement_destination = (player.x, player.y)

    # l contact is a control-flow event, not an ordinary gameplay turn. Detect
    # it before terrain hazards, monster actions, follower movement, stairs,
    # and respawn processing can mutate the state.
    hit = next(
        (
            i
            for i, entity in enumerate(current.entities)
            if not isinstance(entity, d.Collapse)
            and (entity.x, entity.y) == (player.x, player.y)
        ),
        None,
    )
    if hit is not None:
        entity = current.entities[hit]
        if isinstance(entity, d.Companion) and entity.tribe.char == "l" and history:
            contact = _resolve_contact(
                hit,
                current,
                floors,
                player,
                floor,
                checkpoint,
                queue,
                history,
                None,
                trace=trace,
                replay_context=replay_context,
                operation_index=operation_index,
            )
            if contact.rewind_requested:
                return _RewindRequest(floor[0])

    event_message: Optional[str] = None
    collapse_transition = False
    collapse_hit = next(
        (
            entity
            for entity in current.entities
            if isinstance(entity, d.Collapse)
            and (entity.x, entity.y) == (player.x, player.y)
        ),
        None,
    )
    if collapse_hit is not None and (player.x, player.y) != previous:
        from_floor = floor[0]
        collapse_hit.revealed = True
        player.known_monsters.add(d.CHAR_COLLAPSE)
        floor[0] += 1
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [
            (player.x, player.y, floor[0], char)
            for _, _, _, char in player.persistent_followers
        ]
        if trace is not None:
            trace.record_contact(
                {
                    "type": "trap",
                    "id": d.CHAR_COLLAPSE,
                    "outcome": "fallen",
                    "from_floor": from_floor,
                    "to_floor": floor[0],
                    "at": [player.x, player.y],
                }
            )
        event_message = tr(
            "-- The floor gives way! You fall to floor {n}/{total}."
        ).format(n=floor[0] + 1, total=len(floors))
        current = floors[floor[0]]
        collapse_transition = True

    hazard_message = _apply_terrain_hazards(current, player, previous)
    if hazard_message is not None:
        event_message = hazard_message
    if (player.x, player.y) != previous or collapse_transition:
        _marksman_shoot(current, player)

    hit = next(
        (
            i
            for i, entity in enumerate(current.entities)
            if not isinstance(entity, d.Collapse)
            and (entity.x, entity.y) == (player.x, player.y)
        ),
        None,
    )
    if hit is not None:
        contact = _resolve_contact(
            hit,
            current,
            floors,
            player,
            floor,
            checkpoint,
            queue,
            history,
            event_message,
            trace=trace,
            replay_context=replay_context,
            operation_index=operation_index,
        )
        if contact.end_turn:
            return (contact.message_ticks, contact.message) if contact.message else None
        event_message = contact.message

    if (
        player.companion is not None
        and player.karma >= player.companion.tribe.durability
    ):
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
    _advance_persistent_followers(
        player, floor[0], (player.x, player.y) != previous, previous
    )

    floor_before = floor[0]
    transition_message = (
        None
        if (
            collapse_transition
            or movement_destination == previous
            or (player.x, player.y) != movement_destination
        )
        else _handle_floor_transition(current, floors, player, floor, checkpoint)
    )
    if transition_message is not None:
        event_message = transition_message
        if trace is not None:
            trace.record_contact(
                {"type": "stairs", "from_floor": floor_before, "to_floor": floor[0]}
            )

    _process_respawn_queue(floors, player, floor, queue, turn, trace=trace)

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
    initial_seed = rand.get_seed()
    legacy_stage = stage_num in (1, 2)
    if legacy_stage:
        floors, player = build_single_floor(config, stage_num)
    elif stage_num == 6:
        floors, player = build_trap_test(
            config.corridor_h_width, config.corridor_v_width
        )
    else:
        floors, player = build(
            config.corridor_h_width,
            config.corridor_v_width,
            stage_num,
        )
    player.known_monsters = set()
    player.boss_defeated = False
    player.treasure_collected = False
    replay_context = (
        ReplayContext(stage_num, initial_seed, config)
        if stage_num in d.ELF_STAGES
        else None
    )
    floor = [0]
    checkpoint = [floors[0].up]
    player.current_floor = 0
    view_floor = 0
    queue: Counter[Tuple[int, str]] = Counter()
    history: Deque[HistoryEntry] = deque()
    turn = 0
    if legacy_stage:
        message: Tuple[int, str] = (-1, "")
    elif stage_num in d.ELF_STAGES:
        message = (5, tr("-- The King has ordered the Dread Wyrm (W) slain."))
    elif stage_num == 6:
        message = (5, "-- Trap test: Mimic, Vortex, W, treasure, b and d.")
    legacy_respawn_queue: Counter[str] = Counter()
    if legacy_stage:
        turn = -1

    while player.lp > 0:
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
        _reveal_paired_stair_cells(floors)

        message = tick_message(message)

        floor_view = view_floor != floor[0]
        show_entities = debug or getattr(ui, "map_mode", False)
        reachable_cells: Set[d.Point] = set()
        if getattr(ui, "farthest_preview", False) and not floor_view:
            reachable_cells = reachable_known_cells(
                current.field,
                current.seen,
                cur,
                current.entities,
                player,
                stage_num,
            )
        # The terminal renderer discovers the player from the entity list, while
        # the pygame renderer receives it separately. Keep the Stage 3 state
        # model separate and provide a render-only combined list.
        render_player = deepcopy(player) if floor_view else player
        render_player.current_floor = view_floor
        render_entities = (
            display_floor.entities
            if legacy_stage
            else [render_player, *display_floor.entities]
        )
        known_types = player.known_monsters
        no_current_visibility = [
            [0] * len(display_floor.field[0]) for _ in display_floor.field
        ]
        stage_draw_options = {}
        if not legacy_stage:
            stage_draw_options = {
                "stage_roster": d.STAGE3_ROSTER_TRIBES
                if stage_num == 3
                else d.STAGE4_ROSTER_TRIBES,
                "floor_view": floor_view,
                "floor_label": f"{view_floor + 1}/{len(floors)}",
            }
        ui.draw_stage(
            turn=turn,
            player=render_player,
            entities=render_entities,
            field=display_floor.field,
            cur_torched=no_current_visibility if floor_view else cur,
            torched=display_floor.seen,
            known_types=known_types,
            show_entities=show_entities,
            debug_show_entities=debug,
            stage_num=stage_num,
            message=message[1],
            checkpoint=checkpoint[0],
            reachable_cells=reachable_cells,
            **stage_draw_options,
        )

        move = ui.input_direction()
        if move is None:
            if trace is not None:
                trace.record_quit()
                trace.set_outcome(
                    "unfinished" if getattr(ui, "ran_dry", False) else "quit"
                )
            return
        if move == (0, 0):
            continue
        if getattr(ui, "farthest_preview", False):
            ui.farthest_preview = False
        if getattr(ui, "shift_direction", False):
            view_floor = max(0, min(len(floors) - 1, view_floor + move[1]))
            continue

        # A real movement always returns the display to the player's floor.
        view_floor = floor[0]

        if trace is not None:
            key = DIR_TO_KEY.get(move)
            if key is None:
                raise RuntimeError(
                    "--trace-record does not support non-cardinal (e.g. diagonal joystick) movement"
                )
            trace.begin_turn(key)

        if replay_context is not None:
            replay_context.operations.append(move)

        if legacy_stage:
            update_result = update_entities(
                move,
                current.field,
                player,
                current.entities,
                respawn_point=checkpoint[0],
            )
            if update_result.message is not None:
                message = update_result.message
            if update_result.tribes_to_be_respawned:
                checkpoint[0] = (player.x, player.y)
            for char in update_result.tribes_to_be_respawned:
                if char not in d.NO_RESPAWN_MONSTERS:
                    legacy_respawn_queue[char] += 1
            if turn % d.MONSTER_RESPAWN_INTERVAL == 0:
                for char in list(legacy_respawn_queue):
                    if legacy_respawn_queue[char] <= 0:
                        continue
                    tribe = d.CHAR_TO_TRIBE[char]
                    spawn_floor = (
                        rand.randrange(len(floors))
                        if getattr(tribe, "respawn_on_random_floor", False)
                        else floor[0]
                    )
                    respawn_target = floors[spawn_floor]
                    entity = respawn_entity(
                        tribe, respawn_target.entities, respawn_target.field
                    )
                    legacy_respawn_queue[char] -= 1
                    if trace is not None:
                        if isinstance(entity, d.Monster):
                            kind, event_id = "monster", d.monster_type_key(entity)
                        elif isinstance(entity, d.Companion):
                            kind, event_id = "companion", entity.tribe.char
                        else:
                            raise TypeError("Respawned entity must be a monster or companion")
                        update_result.events.world.append(
                            WorldEvent(
                                kind,
                                event_id,
                                (entity.x, entity.y),
                                floor=spawn_floor if len(floors) > 1 else None,
                            )
                        )
            if trace is not None:
                trace.record_events(update_result.events)
                trace.set_player(player, stage_num)
                trace.commit_turn()
            if update_result.effect == d.EFFECT_GOT_TREASURE:
                break
            turn += 1
            player.lp -= 1
            continue

        step_result = _step(
            move,
            floors,
            player,
            floor,
            checkpoint,
            queue,
            history,
            turn,
            stage_num=stage_num,
            trace=trace,
            replay_context=replay_context,
            operation_index=len(replay_context.operations) - 1
            if replay_context is not None
            else None,
        )
        if isinstance(step_result, _RewindRequest):
            rewind_message = _rewind_to_history(
                floors,
                player,
                floor,
                checkpoint,
                queue,
                history,
                replay_context,
                operation_count=len(replay_context.operations)
                if replay_context is not None
                else None,
                loop_floor_index=step_result.floor_index,
            )
            event_message: Optional[Tuple[int, str]] = (5, rewind_message)
        else:
            event_message = step_result
        player.current_floor = floor[0]
        # A stair contact can change the player's floor during _step(). Keep
        # the displayed floor in sync so the next frame shows the new floor.
        view_floor = floor[0]
        if event_message is not None:
            message = event_message

        if trace is not None:
            trace.set_player(player, stage_num)
            trace.commit_turn()

        turn += 1
        player.lp -= 1
        if player.stage_won:
            break

    won = player.stage_won
    if trace is not None:
        trace.set_outcome("win" if won else "lose")

    if not won:
        message = (-1, tr(">> Collapsed from hunger! <<"))
    else:
        message = (-1, tr(">> Treasure chest obtained! <<"))
    while True:
        current = floors[floor[0]]
        cur = get_torched(player, config.torch_radius)
        render_entities = (
            current.entities if legacy_stage else [player, *current.entities]
        )
        known_types = player.known_monsters
        stage_draw_options = {}
        if not legacy_stage:
            stage_draw_options = {
                "stage_roster": d.STAGE3_ROSTER_TRIBES
                if stage_num == 3
                else d.STAGE4_ROSTER_TRIBES,
            }
            if stage_num in d.ELF_STAGES:
                stage_draw_options["floor_label"] = f"{floor[0] + 1}/{len(floors)}"
        ui.draw_stage(
            turn=turn,
            player=player,
            entities=render_entities,
            field=current.field,
            cur_torched=cur,
            torched=current.seen,
            known_types=known_types,
            show_entities=debug,
            debug_show_entities=debug,
            stage_num=stage_num,
            message=message[1],
            extra_keys=True,
            checkpoint=checkpoint[0],
            **stage_draw_options,
        )
        key = ui.input_alphabet()
        if key is None:
            return
        if key == "m":
            if legacy_stage:
                debug = True
                if hasattr(ui, "map_mode"):
                    ui.map_mode = True
            else:
                debug = not debug
        elif key == "s":
            message = (-1, tr("SEED: {seed_str}").format(seed_str=seed_str))
