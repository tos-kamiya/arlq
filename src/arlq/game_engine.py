"""Shared game loop for Stages 1–6."""

import heapq
import math
from collections import Counter
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set, Tuple

from . import defs as d
from . import display as ui_display
from . import stage5
from . import stage56
from . import stage6
from .arlq import (
    MESSAGE_TICKS,
    PLAYER_PASSABLE_CELLS,
    GameConfig,
    activate_mimic_for_defeat,
    apply_barrier_damage,
    barrier_lp_damage,
    find_random_place,
    get_torched,
    iterate_ellipse_points,
    iterate_offsets,
    move_player,
    prefer_event_message,
    reveal_entities_in_fov,
    spawn_at,
    spread_caltrops,
    tick_message,
    unlock_treasure_for_defeat,
)
from .game_events import WallEvent
from .i18n import t as tr
from .i18n import trp
from .stage_replay import rewind as _rewind
from .stage_types import (
    Floor,
    ReplayContext,
    _ContactResult,
    _RewindRequest,
)
from .stage_world import (
    _inside_island,
    _spawn,
    build,
    build_single_floor,
)
from .trace import DIR_TO_KEY, TraceRecorder
from .utils import rand

ELF_REPEAT_MESSAGES = {
    "K": "-- The Collector Elf (K) looks satisfied.",
    "H": "-- Keep the protective amulet close to your skin.",
    "S": "-- The Sylvan Elf replenished your fairy nectar.",
}
STATUS_POPUP_TICKS = 2


def _set_status_popup(player: d.Player, text: str, tone: str = "default") -> None:
    player.status_popup = text
    player.status_popup_tone = tone
    player.status_popup_ticks = STATUS_POPUP_TICKS


def _format_popup_amount(amount: float) -> str:
    return f"{amount:.1f}".rstrip("0").rstrip(".")


def _find_escape_place(current: Floor, far_from: Optional[d.Point] = None) -> d.Point:
    """Find an open destination outside a sealed island room."""
    return find_random_place(
        current.entities,
        current.field,
        distance=2,
        far_from=far_from,
        avoid=lambda point: _inside_island(point, current.island),
    )


def reachable_known_cells(
    field: List[List[str]],
    seen: List[List[int]],
    visible: List[List[int]],
    entities: List[d.Entity],
    player: d.Player,
    phase_walls: Optional[Set[d.Point]] = None,
    terminal_targets: Optional[Set[d.Point]] = None,
    include_unexplored: bool = False,
) -> Set[d.Point]:
    """Find reachable cells, optionally including unexplored terrain for exit checks."""
    height = len(field)
    width = len(field[0]) if field else 0
    if not width or not (0 <= player.x < width and 0 <= player.y < height):
        return set()

    known = [
        [int(include_unexplored or seen[y][x] or visible[y][x]) for x in range(width)]
        for y in range(height)
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
        if point != start and point in (terminal_targets or ()):
            continue
        for dx, dy in neighbors:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if not known[ny][nx] or ((nx, ny) in blocked and (nx, ny) not in (terminal_targets or ())):
                continue

            cell = field[ny][nx]
            if (nx, ny) in (terminal_targets or ()):
                terrain_cost = d.movement_lp_cost(player)
            elif (nx, ny) in (phase_walls or ()) or (
                cell == d.CHAR_GOLEM_WALL and d.has_member(player, d.MEMBER_ROGUE)
            ):
                terrain_cost = d.movement_lp_cost(player)
            elif cell in (d.CHAR_FLOOR, d.CHAR_D_GATE, *d.HIDDEN_STAIRS_CHARS):
                terrain_cost = d.movement_lp_cost(player)
            elif (include_unexplored and cell == d.CHAR_HIDDEN_D_GATE
                  and d.has_member(player, d.MEMBER_DUNGEON_EXPLORER)):
                terrain_cost = d.movement_lp_cost(player)
            elif cell == d.CHAR_CALTROP:
                terrain_cost = d.movement_lp_cost(player) + d.caltrop_lp_damage(player)
            elif cell == d.CHAR_COLLAPSE:
                terrain_cost = d.movement_lp_cost(player)
            elif cell == d.CHAR_BARRIER:
                terrain_cost = d.movement_lp_cost(player) + barrier_lp_damage(player)
            else:
                # Walls, stairs, and unknown/special terrain are not safe
                # walking cells for this estimate.
                continue

            next_cost = cost + terrain_cost
            if next_cost >= player.lp:
                continue
            next_point = (nx, ny)
            if next_cost >= distances.get(next_point, player.lp):
                continue
            distances[next_point] = next_cost
            heapq.heappush(pending, (next_cost, ny, nx))

    return set(distances)



def _ration_available(current: Floor, player: d.Player, visible: List[List[int]]) -> bool:
    """Check for a beatable monster reachable with the emergency LP."""
    targets = {
        (entity.x, entity.y) for entity in current.entities
        if isinstance(entity, d.Monster)
        and not entity.tribe.is_elf and not entity.tribe.passive
        and (entity.tribe.char != "M" or entity.active)
        and any(monster.tribe.feed > 0 for monster in stage56.monster_party(current, entity))
        and d.current_player_attack(player) >= sum(
            d.monster_level(monster)
            for monster in stage56.monster_party(current, entity)
        )
    }
    if not targets:
        return False
    restored = deepcopy(player)
    restored.lp = d.STAGE6_RATION_LP
    phase_walls = {
        (x, y) for y, row in enumerate(current.field)
        for x, cell in enumerate(row) if cell == d.CHAR_D_GATE
    }
    reachable = reachable_known_cells(
        current.field, current.seen, visible, current.entities, restored,
        phase_walls, terminal_targets=targets,
    )
    return bool(targets & reachable)

def _move_player(
    direction: d.Point,
    current: Floor,
    player: d.Player,
    trace: Optional[TraceRecorder] = None,
) -> Optional[WallEvent]:
    """Apply one step of player movement, including sword-breaking and Pegasus jumps."""
    phase_walls = {
        (x, y)
        for y, row in enumerate(current.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_D_GATE
    }
    wall_result = move_player(
        direction,
        current.field,
        player,
        PLAYER_PASSABLE_CELLS,
        phase_walls=phase_walls,
        break_golem_walls=d.has_member(player, d.MEMBER_ROGUE),
    )
    if wall_result is not None and wall_result.result in {
        "sword_break", "golem_wall_break"
    }:
        current.broken_walls.add((player.x, player.y))
    if trace is not None and wall_result is not None:
        trace.record_wall(wall_result)
    return wall_result


def _visible_auto_stop_entities(
    current: Floor,
    player: d.Player,
    show_all_entities: bool,
    known_types: Set[str],
) -> List[d.Entity]:
    """Return entities currently represented on the player's map."""
    visible: List[d.Entity] = []
    height = len(current.field)
    width = len(current.field[0]) if current.field else 0
    player_attack = d.current_player_attack(player)
    for entity in current.entities:
        x, y = entity.x, entity.y
        if (x, y) == (player.x, player.y) or not (0 <= x < width and 0 <= y < height):
            continue
        if show_all_entities:
            glyphs = ui_display.preview_entity_glyphs(
                entity,
                reveal_disguises=True,
                known_types=known_types,
            )
        elif current.seen[y][x]:
            glyphs = ui_display.revealed_entity_glyphs(
                entity,
                known_types,
                False,
                player_attack,
                None,
            )
        else:
            glyphs = []
        if not glyphs:
            continue
        visible.append(entity)
    return visible


def _should_stop_movement_repeat(
    direction: d.Point,
    current: Floor,
    player: d.Player,
    show_all_entities: bool = False,
    known_types: Optional[Set[str]] = None,
) -> bool:
    """Check visible terrain and entities before an automatic repeated step."""
    dx, dy = direction
    nx, ny = player.x + dx, player.y + dy
    height = len(current.field)
    width = len(current.field[0]) if current.field else 0
    if not (0 <= nx < width and 0 <= ny < height):
        return True

    known_cell = bool(current.seen[ny][nx]) or show_all_entities
    cell = current.field[ny][nx]
    next_position = (nx, ny)
    passable_secret = cell == d.CHAR_D_GATE or (
        cell == d.CHAR_GOLEM_WALL and d.has_member(player, d.MEMBER_ROGUE)
    )
    if known_cell and cell in (
        *d.WALL_CHARS,
        d.CHAR_HIDDEN_D_GATE,
        d.CHAR_CALTROP,
        d.CHAR_BARRIER,
        d.CHAR_COLLAPSE,
        *d.STAIR_CHARS,
    ) and not passable_secret:
        return True
    for entity in _visible_auto_stop_entities(
        current, player, show_all_entities, known_types or set()
    ):
        # Stop only when this step would enter a visible entity's cell.
        if (entity.x, entity.y) == next_position:
            return True
    return False


def _stop_movement_repeat(ui: Any) -> None:
    stop_repeat = getattr(ui, "stop_movement_repeat", None)
    if stop_repeat is not None:
        stop_repeat()


def _apply_terrain_hazards(
    current: Floor,
    player: d.Player,
    previous: d.Point,
    trace: Optional[TraceRecorder] = None,
) -> Optional[str]:
    """Apply barrier/caltrop damage for the player's current cell.

    LP damage is summarized by a short popup near the player.
    Barrier damage does not emit a status message.
    """
    field = current.field
    event_message = None
    old_lp = player.lp
    if apply_barrier_damage(field, player, previous):
        damage = max(0, old_lp - player.lp)
        tone = "green" if d.has_member(player, d.MEMBER_GUARDIAN) else "default"
        _set_status_popup(player, f"LP-{_format_popup_amount(damage)}", tone)
        if trace is not None:
            trace.record_damage("barrier")
    if field[player.y][player.x] == d.CHAR_CALTROP:
        old_lp = player.lp
        player.lp -= d.caltrop_lp_damage(player)
        damage = max(0, old_lp - player.lp)
        if damage:
            tone = "green" if d.has_member(player, d.MEMBER_GUARDIAN) else "default"
            _set_status_popup(player, f"LP-{_format_popup_amount(damage)}", tone)
        field[player.y][player.x] = d.CHAR_FLOOR
        if trace is not None:
            trace.record_damage("caltrop")
    return event_message


def _reveal_collapse_pits(
    floors: List[Floor], floor_index: int, collapse: d.Collapse
) -> None:
    """Reveal pits around a Collapse and mark their lower-floor rocks."""
    current = floors[floor_index]
    x_center, y_center = collapse.x, collapse.y
    current.seen[y_center][x_center] = 1
    lower = floors[floor_index + 1] if floor_index + 1 < len(floors) else None
    for dx, dy in d.COLLAPSE_FOOTPRINT_OFFSETS[1:]:
        x, y = x_center + dx, y_center + dy
        if (
            0 <= y < len(current.field)
            and 0 <= x < len(current.field[y])
            and current.field[y][x] not in (*d.WALL_CHARS, *d.HIDDEN_PASSAGE_CHARS)
        ):
            current.field[y][x] = d.CHAR_COLLAPSE
            current.seen[y][x] = 1
            if lower is not None and lower.field[y][x] == d.CHAR_FLOOR:
                lower.decor[y][x] = d.DECOR_FALLEN_ROCKS


def _marksman_shoot(
    current: Floor, player: d.Player, trace: Optional[TraceRecorder] = None
) -> bool:
    """Resolve eligible marksman shots and retain their visible arrow marks."""
    was_shot = False
    player.marksman_damage_prevented = False
    for entity in current.entities:
        if (
            not isinstance(entity, d.Monster)
            or entity.tribe.char != "k"
            or not entity.active
        ):
            continue
        if entity.marksman_cooldown > 0:
            entity.marksman_cooldown -= 1
            if entity.marksman_cooldown > 0:
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
                *d.WALL_CHARS,
                *d.STAIR_CHARS,
                d.CHAR_HIDDEN_D_GATE,
            ):
                blocked = True
                break
            if any(
                (other.x, other.y) == (x, y)
                and (
                    isinstance(other, d.Companion)
                    or isinstance(other, d.PartyMember)
                    or isinstance(other, d.Treasure)
                    or isinstance(other, d.Monster)
                    and other.active
                )
                for other in current.entities
            ):
                blocked = True
                break
        if blocked:
            continue

        entity.marksman_shots_fired += 1
        no_damage = (
            d.has_member(player, d.MEMBER_ROGUE)
            and entity.marksman_shots_fired % 2 == 1
        )
        if no_damage:
            player.marksman_damage_prevented = True
        else:
            player.lp -= d.MARKSMAN_LP_DAMAGE
            if trace is not None:
                trace.record_damage("marksman")
        was_shot = True
        entity.marksman_cooldown = d.MARKSMAN_COOLDOWN_TURNS
        player.known_monsters.add(d.monster_type_key(entity))
        mark = ((player.x - step_x, player.y - step_y), "-" if step_x else "|")
        marks = entity.arrow_marks
        marks[:] = [existing for existing in marks if existing[0] != mark[0]]
        marks.append(mark)
        arrow_limit = d.MARKSMAN_ARROW_LIMIT
        if len(marks) > arrow_limit:
            del marks[0]
    return was_shot


def _vortex_rearrange(
    current: Floor,
    player: d.Player,
    floor_index: int,
    center: d.Point,
    floors: Optional[List[Floor]] = None,
    include_treasures: bool = True,
) -> None:
    """Reposition entities and forget explored floor and barrier cells."""
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
            isinstance(entity, d.Companion)
            or isinstance(entity, d.Treasure) and include_treasures
            or (
                isinstance(entity, d.Monster)
                and entity.active
                and (
                    isinstance(entity, d.Collapse)
                    or (
                        not entity.tribe.is_elf
                        and entity.tribe.effect != d.EFFECT_VORTEX
                    )
                )
            )
        )
    ]
    moved_monster_barrier_cells = {
        point
        for entity in movable
        if isinstance(entity, d.Monster)
        for point in stage56.barrier_cells(current, entity)
    }
    lower = (
        floors[floor_index + 1]
        if floors is not None and floor_index + 1 < len(floors)
        else None
    )
    reserved_collapse_cells = current.collapse_landings | set().union(
        *(
            d.collapse_footprint((entity.x, entity.y))
            for entity in current.entities
            if isinstance(entity, d.Collapse)
        )
    )
    scholar_stairs = set(current.scholar_up_stairs + current.scholar_down_stairs)
    reserved_collapse_cells.update(scholar_stairs)
    if lower is not None:
        reserved_collapse_cells.update(lower.collapse_landings)
    avoid = {(player.x, player.y)} | {(entity.x, entity.y) for entity in movable}
    for entity in movable:
        if isinstance(entity, d.Monster) and entity.tribe.char == "k":
            entity.arrow_marks.clear()
    current.entities[:] = [
        entity for entity in current.entities if entity not in movable
    ]

    # Clear and rebuild only barriers inside the Vortex's affected area.
    for x, y in affected_points:
        if (
            current.field[y][x] == d.CHAR_BARRIER
            and (x, y) not in current.persistent_barriers
        ):
            current.field[y][x] = d.CHAR_FLOOR

    def relocate(char: str, origin_floor: Optional[int], empowered: int = 1) -> None:
        x, y = find_random_place(
            current.entities,
            current.field,
            distance=2,
            avoid=lambda point: point not in affected_points
            or point in avoid
            or point in reserved_collapse_cells
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
        if isinstance(entity, d.Collapse):
            old_footprint = d.collapse_footprint((entity.x, entity.y))
            destination = None
            if lower is not None:
                occupied = {
                    (other.x, other.y)
                    for other in (*current.entities, *lower.entities)
                } | avoid
                fixed = {
                    current.up,
                    current.down,
                    *current.up_stairs,
                    *current.down_stairs,
                    lower.up,
                    lower.down,
                    *lower.up_stairs,
                    *lower.down_stairs,
                    *current.scholar_up_stairs,
                    *current.scholar_down_stairs,
                    *lower.scholar_up_stairs,
                    *lower.scholar_down_stairs,
                }
                for point in sorted(affected_points, key=lambda item: (item[1], item[0])):
                    footprint = d.collapse_footprint(point)
                    if (
                        footprint & reserved_collapse_cells
                        or footprint & occupied
                        or footprint & fixed
                    ):
                        continue
                    if (
                        current.field[point[1]][point[0]] != d.CHAR_FLOOR
                        or lower.field[point[1]][point[0]] != d.CHAR_FLOOR
                    ):
                        continue
                    if not d.collapse_placement_cells_valid(
                        point, current.field, lower.field
                    ):
                        continue
                    destination = point
                    break
            if destination is None:
                current.entities.append(entity)
                continue

            entity.x, entity.y = destination
            current.entities.append(entity)
            new_footprint = d.collapse_footprint(destination)
            reserved_collapse_cells.difference_update(old_footprint)
            reserved_collapse_cells.update(new_footprint)
            avoid.update(new_footprint)
            if lower is not None:
                lower.collapse_landings.difference_update(old_footprint)
                lower.collapse_landings.update(new_footprint)
            continue

        if isinstance(entity, d.Treasure):
            reserved = avoid | set(
                current.up_stairs
                + current.down_stairs
                + current.scholar_up_stairs
                + current.scholar_down_stairs
            )
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

    occupied = {(entity.x, entity.y) for entity in current.entities}
    for current_entity in current.entities:
        if (
            isinstance(current_entity, d.Monster)
            and stage56._barrier_offsets(current_entity)
        ):
            protected = current.collapse_landings | scholar_stairs | set().union(
                *(
                    d.collapse_footprint((fixed.x, fixed.y))
                    for fixed in current.entities
                    if isinstance(fixed, d.Collapse)
                )
            )
            for point in stage56.barrier_cells(current, current_entity):
                x, y = point
                if (
                    point in affected_points
                    and point not in current.broken_walls
                    and point not in occupied
                    and point not in protected
                    and current.field[y][x] == d.CHAR_FLOOR
                ):
                    current.field[y][x] = d.CHAR_BARRIER

    current_monster_barrier_cells = {
        point
        for entity in current.entities
        if isinstance(entity, d.Monster)
        for point in stage56.barrier_cells(current, entity)
    }
    stage56.clear_monster_barriers(
        current, moved_monster_barrier_cells,
        affected_points | current_monster_barrier_cells,
    )

    for x, y in affected_points:
        if (
            current.field[y][x] in (d.CHAR_FLOOR, d.CHAR_BARRIER)
            and (x, y) not in current.persistent_barriers
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
    stage_num: int = 3,
) -> None:
    """Apply the effects of successfully defeating `entity` in combat."""
    ch = entity.tribe.char
    if ch == "w" or (ch == "f" and entity.empowered == 2):
        other_monster_barrier_cells = {
            point
            for other in current.entities
            if other is not entity and isinstance(other, d.Monster)
            for point in stage56.barrier_cells(current, other)
        }
        stage56.clear_monster_barriers(
            current, set(stage56.barrier_cells(current, entity)),
            other_monster_barrier_cells,
        )
    elif ch == "W":
        for x, y in stage56.barrier_cells(current, entity):
            if current.field[y][x] == d.CHAR_BARRIER:
                current.persistent_barriers.add((x, y))
    if ch == "k":
        entity.arrow_marks.clear()
    if ch == "M":
        entity.met = True
        entity.active = False

    # A successful monster defeat establishes the next respawn point.
    if not entity.tribe.is_elf:
        checkpoint[0] = (player.x, player.y)
        if trace is not None:
            trace.record_checkpoint(
                "monster_defeated", (player.x, player.y), floor[0]
            )

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
    if entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
        player.boss_defeated = True
    if ch == "W":
        player.elf_stage_flags |= d.STAGE3_W_FLAG
        player.known_monsters.add(d.monster_type_key(entity))
        player.boss_defeated = True
    elif ch == d.CHAR_FIRE_DRAKE and entity.empowered == 2:
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
    d.apply_feed(
        player,
        entity.tribe.feed,
        d.BISON_LP_OVERCHARGE if entity.tribe.char == "B" else 0,
    )

    if entity.tribe.effect == d.EFFECT_CALTROP_SPREAD:
        spread_caltrops(
            current.field,
            (player.x, player.y),
            current.entities,
            set(current.scholar_up_stairs + current.scholar_down_stairs),
        )
    elif entity.tribe.effect == d.EFFECT_ROCK_SPREAD:
        protected_collapse_cells = current.collapse_landings | set().union(
            *(
                d.collapse_footprint((collapse.x, collapse.y))
                for collapse in current.entities
                if isinstance(collapse, d.Collapse)
            )
        )
        protected_collapse_cells.update(
            current.scholar_up_stairs + current.scholar_down_stairs
        )
        for x, y in iterate_offsets(
            player.x,
            player.y,
            d.ROCK_SPREAD_OFFSETS,
            except_for_entities=current.entities,
        ):
            if (x, y) not in protected_collapse_cells and current.field[y][
                x
            ] == d.CHAR_FLOOR:
                current.field[y][x] = d.CHAR_GOLEM_WALL
    elif entity.tribe.effect == d.EFFECT_VORTEX:
        _vortex_rearrange(
            current, player, floor[0], (entity.x, entity.y), floors=floors,
        )

    if (
        d.monster_level(entity) > 0
        and ch not in d.MONSTERS_EXCLUDED_FROM_RESPAWN
        and entity.tribe.effect != d.EFFECT_UNLOCK_TREASURE
    ):
        type_key = ch if stage_num in (1, 2) else d.monster_type_key(entity)
        spawn_key = (floor[0], type_key)
        queue[spawn_key] = queue.get(spawn_key, 0) + 1


def _resolve_passive_or_repeat_contact(
    hit: int,
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    contact_key: Tuple[int, int, int],
    trace: Optional[TraceRecorder],
) -> Optional[_ContactResult]:
    """Handle passive monsters and elves the player has already met."""
    ch = entity.tribe.char
    if entity.tribe.passive:
        entity.revealed = True
        player.known_monsters.add(d.monster_type_key(entity))
        player.last_contact_monster = contact_key
        if trace is not None:
            trace.record_contact(
                {"type": "monster", "id": ch, "outcome": "passive"}
            )
        return _ContactResult(
            trp("-- It looks powerful, but doesn't seem to intend to attack you.", 3)
        )

    if not entity.tribe.is_elf or not entity.met:
        return None

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
            trp(
                "-- The Isolated Elf wants to be left alone, and sends you elsewhere.",
                3,
            ),
            end_turn=True,
        )
    if ch in ELF_REPEAT_MESSAGES:
        current.entities.append(entity)
        return _ContactResult(
            trp(ELF_REPEAT_MESSAGES[ch], 7 if ch == "H" else 3), end_turn=True
        )
    return _ContactResult(None, end_turn=True)


def _resolve_elf_contact(
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    queue: Counter[Tuple[int, str]],
    trace: Optional[TraceRecorder],
) -> Tuple[bool, Optional[str]]:
    """Apply a first-time elf's reward or refusal, if this elf is eligible."""
    ch = entity.tribe.char
    event_message = None
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
        if player.k_elf_refused:
            player.x, player.y = _find_escape_place(current)
            event_message = trp("-- Respawned to a random location.", 5)
        else:
            event_message = trp("-- Please bring the cursed sword (C).", 7)
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
                | d.ELF_STAGE_S_FLAG
            )
        ).bit_count()
        < 2
    ):
        current.entities.append(entity)
        if player.high_elf_refused:
            player.x, player.y = _find_escape_place(current)
            event_message = trp("-- You were sent somewhere else.", 3)
        else:
            event_message = trp("-- The High Elf does not recognize you yet.", 3)
            player.high_elf_refused = True
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "H", "outcome": "refused"})
    elif ch == "L":
        if player.item == d.ITEM_POISONED:
            poison_source = player.item_taken_from
            d.clear_player_item(player)
            if trace is not None and poison_source is not None:
                trace.add_expired(
                    {
                        "type": "item_expired",
                        "item": poison_source,
                        "reason": "cleansed",
                    }
                )
        old_lp_max = d.player_lp_max(player)
        player.lifebringer_lp_max = min(
            old_lp_max + d.LIFEBRINGER_LP_MAX_INCREASE,
            d.LP_MAX_LIFEBRINGER,
        )
        player.elf_stage_flags |= d.ELF_STAGE_L_FLAG
        player.lp = d.LP_OVERCHARGE_MAX
        if player.lifebringer_lp_max > old_lp_max:
            event_message = trp(
                "-- The Lifebringer Elf restored your health and increased "
                "your LP maximum!",
                7,
            )
        else:
            event_message = trp("-- The Lifebringer Elf restored your health!", 5)
        spawn_key = (floor[0], d.monster_type_key(entity))
        queue[spawn_key] = queue.get(spawn_key, 0) + 1
        if trace is not None:
            trace.record_contact({"type": "elf", "id": "L", "outcome": "granted"})
    elif ch == "S":
        if player.elf_stage_flags & d.ELF_STAGE_S_FLAG:
            event_message = trp(ELF_REPEAT_MESSAGES["S"], 3)
        else:
            player.elf_stage_flags |= d.ELF_STAGE_S_FLAG
            event_message = entity.tribe.event_message
            if event_message:
                event_message = trp(
                    event_message, entity.tribe.event_message_importance
                )
            if trace is not None:
                trace.record_contact(
                    {"type": "elf", "id": "S", "outcome": "granted"}
                )
    else:
        return False, event_message
    return True, event_message


def _resolve_monster_contact(
    hit: int,
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    trace: Optional[TraceRecorder] = None,
    floors: Optional[List[Floor]] = None,
    stage_num: int = 3,
) -> _ContactResult:
    """Resolve contact with a monster, including early-ending elf encounters."""
    ch = entity.tribe.char
    old_level = player.level
    old_lp_max = d.player_lp_max(player)
    event_message = None
    combat_won = False
    if not entity.tribe.is_elf and not entity.tribe.passive:
        player.last_encounter_party = d.monster_variant_label(ch, entity.empowered)
    contact_key = (floor[0], entity.x, entity.y)
    if player.item == d.ITEM_SWORD_CURSED:
        player.lp -= d.CURSED_SWORD_LP_COST
    old_lp = player.lp

    early_contact = _resolve_passive_or_repeat_contact(
        hit, entity, current, player, contact_key, trace
    )
    if early_contact is not None:
        return early_contact

    if entity.tribe.is_elf:
        player.elf_stage_floors.setdefault(ch, floor[0] + 1)
        player.known_elf_floors.add(ch)

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

    handled_elf = False
    if entity.tribe.is_elf:
        handled_elf, event_message = _resolve_elf_contact(
            entity, current, player, floor, queue, trace
        )

    if not handled_elf:
        player.karma += 1

    if not handled_elf and d.current_player_attack(player) < d.monster_level(entity):
        assert ch != "M", "A Mimic must not defeat the player."
        # Losing still identifies the monster, including W. Treasure glyphs
        # remain gated separately by their unlock state in the renderer.
        if not entity.tribe.is_elf:
            player.known_monsters.add(d.monster_type_key(entity))
            if ch == "C":
                player.known_c_floors.add(floor[0] + 1)
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
            player.x, player.y = _find_escape_place(current, (entity.x, entity.y))
            event_message = trp("-- Respawned to a random location.", 5)
        else:
            player.x, player.y = checkpoint[0]
            # Keep the monster that caused this respawn visible for the next
            # frame, even when the checkpoint is outside its FOV.
            current.contact_reveal = (entity.x, entity.y)
            event_message = trp("-- Respawned!", 5)
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
    elif not handled_elf:
        combat_won = True
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
            stage_num=stage_num,
        )
        if ch == "M":
            # Keep the defeated Mimic occupied while choosing the escape
            # destination, then remove it so it cannot be contacted again.
            current.entities.append(entity)
            player.x, player.y = _find_escape_place(current)
            current.entities.remove(entity)
        if ch == "M":
            event_message = trp(
                "-- You defeated the Mimic, but were sent somewhere else.", 5
            )
        if ch == "W" and player.treasure_collected:
            event_message = trp(">> The King's request is complete! <<", 9)
        elif ch == d.CHAR_FIRE_DRAKE and entity.empowered == 2:
            if player.treasure_collected:
                event_message = trp(">> The King's request is complete! <<", 9)
            else:
                event_message = trp(">> Strong Fire Drake (F') defeated! <<", 9)

    if entity.tribe.is_elf and ch not in ("J", "L") and entity not in current.entities:
        entity.met = True
        current.entities.append(entity)
    elif entity.tribe.is_elf and entity not in current.entities:
        entity.met = True

    player.last_contact_monster = contact_key

    if event_message is None:
        tribe_message = entity.tribe.event_message
        if tribe_message:
            event_message = trp(
                tribe_message, entity.tribe.event_message_importance
            )

    popup = None
    if handled_elf and ch == "L":
        popup = "LP FULL"
        if d.player_lp_max(player) > old_lp_max:
            popup = (
                f"LP FULL  MAX+"
                f"{_format_popup_amount(d.player_lp_max(player) - old_lp_max)}"
            )
    elif combat_won:
        if ch == "A":
            popup = f"LVL+{_format_popup_amount(player.level - old_level)}"
        elif ch in ("b", "B"):
            gained_lp = max(0, player.lp - old_lp)
            if gained_lp:
                popup = f"LP+{_format_popup_amount(gained_lp)}"
        elif ch == "c":
            popup = "SWORD x1.5"
        elif ch == "C":
            popup = "CURSED x3"
        elif ch == "e":
            lost_lp = max(0, old_lp - player.lp)
            if lost_lp:
                popup = f"LP-{_format_popup_amount(lost_lp)}"
        elif ch == "E":
            lost_level = max(0, old_level - player.level)
            if lost_level:
                popup = f"LVL-{_format_popup_amount(lost_level)}"
    if popup:
        _set_status_popup(player, popup)

    return _ContactResult(event_message)


def _resolve_party_contact(
    entity: d.Monster,
    current: Floor,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter,
    trace: Optional[TraceRecorder],
    stage_num: int,
) -> _ContactResult:
    party = stage56.monster_party(current, entity)
    enemy_party = [monster for monster in party if not monster.tribe.is_elf]
    composition = "".join(
        d.monster_variant_label(monster.tribe.char, monster.empowered)
        for monster in sorted(enemy_party, key=lambda monster: (monster.y, monster.x))
    )
    if composition:
        player.last_encounter_party = composition
    player.karma += 1
    strength = sum(d.monster_level(monster) for monster in party)
    contact_key = (floor[0], *min((monster.x, monster.y) for monster in party))
    boss = next(
        (monster for monster in party if monster.tribe.char in ("F", "W")), None
    )
    for monster in party:
        player.known_monsters.add(d.monster_type_key(monster))
    if player.item == d.ITEM_SWORD_CURSED:
        player.lp -= d.CURSED_SWORD_LP_COST
    won = d.current_player_attack(player) >= strength
    if trace is not None:
        for monster in party:
            trace.record_contact(
                {
                    "type": "monster",
                    "id": d.monster_type_key(monster),
                    "outcome": "win" if won else "lose",
                }
            )
    if not won:
        if player.last_contact_monster == contact_key:
            player.x, player.y = _find_escape_place(current, (entity.x, entity.y))
        else:
            player.x, player.y = checkpoint[0]
        current.contact_reveal = (entity.x, entity.y)
        d.apply_respawn_penalty(player)
        d.clear_player_item(player)
        player.last_contact_monster = contact_key
        return _ContactResult(trp("-- Your party lost and respawned together.", 5))

    old_level, old_lp = player.level, player.lp
    base_experience = (
        sum(
            10
            if monster.tribe.effect == d.EFFECT_SPECIAL_EXP
            else 0
            if monster.tribe.effect == d.EFFECT_LEVEL_REDUCE
            else 3
            if monster.tribe.char == "f"
            else 1
            for monster in party
        )
        / d.experience_share_count(player)
    )
    experience = base_experience * d.experience_multiplier(player)
    feed = max(monster.tribe.feed for monster in party)
    lp_overcharge = (
        d.BISON_LP_OVERCHARGE
        if any(monster.tribe.char == "B" for monster in party)
        else 0
    )
    # Resolve ordinary drops first, the unique item/effect last. All defeated
    # entities must be removed before V can rearrange the survivors.
    party.sort(key=lambda monster: stage56.special_monster(monster))
    for monster in party:
        current.entities.remove(monster)
    for monster in party:
        _defeat_monster(
            monster,
            current,
            player,
            floor,
            checkpoint,
            queue,
            trace=trace,
            floors=floors,
            stage_num=stage_num,
        )
    player.level = old_level + experience
    if any(monster.tribe.effect == d.EFFECT_LEVEL_REDUCE for monster in party):
        player.level = max(1, math.floor(player.level * 2 / 3))
    knight = next(
        (member for member in player.members if member.role == d.MEMBER_KNIGHT), None
    )
    if knight is not None:
        knight.level += base_experience * d.KNIGHT_EXPERIENCE_RATIO
    player.lp = old_lp
    d.apply_feed(player, feed, lp_overcharge)
    if any(monster.tribe.char == "M" for monster in party):
        player.x, player.y = _find_escape_place(current)
    barrier_source_positions = {
        id(monster): (monster, (monster.x, monster.y))
        for monster in current.entities
        if isinstance(monster, d.Monster)
        and stage56._barrier_offsets(monster)
    }
    stage56.normalize_parties(
        current,
        d.MEMBER_STAGE_MONSTER_PARTY_LIMIT,
    )
    for monster in current.entities:
        previous_source = barrier_source_positions.get(id(monster))
        if (
            isinstance(monster, d.Monster)
            and previous_source is not None
            and previous_source[1] != (monster.x, monster.y)
        ):
            stage56.update_moved_monster_barriers(
                current, monster, previous_source[1],
                (player.x, player.y),
            )
    player.last_contact_monster = contact_key
    party_chars = {monster.tribe.char for monster in party}
    boss_message = (
        trp(boss.tribe.event_message, boss.tribe.event_message_importance)
        if boss is not None and boss.tribe.event_message
        else None
    )
    popup = None
    popup_tone = "default"
    if "A" in party_chars and player.level > old_level:
        popup = f"LVL+{_format_popup_amount(player.level - old_level)}"
        if (
            d.experience_share_count(player) != 1
            or d.experience_multiplier(player) != 1
        ):
            popup_tone = "green"
    elif "E" in party_chars:
        lost_level = max(0, old_level - player.level)
        if lost_level:
            popup = f"LVL-{_format_popup_amount(lost_level)}"
    elif "b" in party_chars or "B" in party_chars:
        gained_lp = max(0, player.lp - old_lp)
        if gained_lp:
            popup = f"LP+{_format_popup_amount(gained_lp)}"
    elif "C" in party_chars:
        popup = "CURSED x3"
    elif "c" in party_chars:
        popup = "SWORD x1.5"
    elif "e" in party_chars:
        lost_lp = max(0, old_lp - player.lp)
        if lost_lp:
            popup = f"LP-{_format_popup_amount(lost_lp)}"
    if popup:
        _set_status_popup(player, popup, popup_tone)
    return _ContactResult(boss_message)


def _resolve_contact(
    hit: int,
    current: Floor,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    trace: Optional[TraceRecorder] = None,
    stage_num: int = 3,
) -> _ContactResult:
    """Resolve contact with the entity at `hit` in current.entities.

    The result explicitly marks encounters that end the turn immediately,
    bypassing the usual end-of-turn processing (Loop Companion rewind and
    repeated elf contact).
    """
    entity = current.entities[hit]

    if isinstance(entity, d.PartyMember):
        result = stage56.recruit(current, player, entity)
        if trace is not None:
            trace.record_contact({"type": "member", "id": entity.role,
                                  "joined": entity in player.members})
        return _ContactResult(result)

    if isinstance(entity, d.Treasure):
        collected = entity.unlocked
        if trace is not None:
            trace.record_contact(
                {"type": "treasure", "id": entity.unlock_key, "collected": collected}
            )
        if collected:
            current.entities.pop(hit)
            player.treasure_collected = True
            if not player.boss_defeated:
                return _ContactResult(
                    trp(
                        "-- You took the treasure chest, but the King's request remains.",
                        7,
                    )
                )
        return _ContactResult(None)

    if isinstance(entity, d.Companion):
        ch = entity.tribe.char
        if trace is not None:
            trace.record_contact({"type": "companion", "id": ch})
        # The game loop handles rewind after this step returns its request.
        if ch == "l":
            entity.revealed = True
            return _ContactResult(
                None, end_turn=True, message_ticks=5, rewind_requested=True
            )
        entity.revealed = True
        current.entities.pop(hit)
        if (
            ch != "l"
            and player.elf_stage_flags & d.ELF_STAGE_S_FLAG
        ):
            entity.durability = math.ceil(
                entity.tribe.durability * d.SYLVAN_COMPANION_DURATION_MULTIPLIER
            )
        player.companion = entity
        player.karma = 0
        tribe_message = entity.tribe.event_message
        return _ContactResult(
            trp(tribe_message, entity.tribe.event_message_importance)
            if tribe_message
            else None
        )

    assert isinstance(entity, d.Monster)
    if entity.tribe.char == "M" and not entity.active:
        return _ContactResult(None)
    if stage_num in (5, 6):
        return _resolve_party_contact(
            entity, current, floors, player, floor, checkpoint, queue, trace, stage_num,
        )
    return _resolve_monster_contact(
        hit,
        entity,
        current,
        player,
        floor,
        checkpoint,
        queue,
        trace=trace,
        floors=floors,
        stage_num=stage_num,
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
    if (
        floor[0] > 0
        and current.field[player.y][player.x] == d.CHAR_SCHOLAR_STAIRS_UP
        and floors[floor[0] - 1].field[player.y][player.x] == d.CHAR_COLLAPSE
    ):
        if not d.has_member(player, d.MEMBER_DUNGEON_EXPLORER):
            return None
        floor[0] -= 1
        player.just_climbed_pit = True
        checkpoint[0] = point
        player.persistent_followers = [
            (player.x, player.y, floor[0], ch)
            for _, _, _, ch in player.persistent_followers
        ]
        return trp("-- Ascended to floor {n}/{total}.", 1).format(
            n=floor[0] + 1, total=len(floors)
        )
    legacy_floors = not any(
        f.up_stairs or f.down_stairs or f.scholar_up_stairs or f.scholar_down_stairs
        for f in floors
    )
    down_stairs = list(
        current.down_stairs or ([current.down] if legacy_floors else [])
    )
    up_stairs = list(current.up_stairs or ([current.up] if legacy_floors else []))
    down_stairs += [
        point for point in current.scholar_down_stairs
        if current.field[point[1]][point[0]] == d.CHAR_SCHOLAR_STAIRS_DOWN
    ]
    up_stairs += [
        point for point in current.scholar_up_stairs
        if current.field[point[1]][point[0]] == d.CHAR_SCHOLAR_STAIRS_UP
    ]
    floor_count = len(floors)
    if floor[0] < floor_count - 1 and point in down_stairs:
        stair_index = down_stairs.index(point)
        secret_stair_index = (
            current.scholar_down_stairs.index(point)
            if point in current.scholar_down_stairs
            else None
        )
        floor[0] += 1
        destination_floor = floors[floor[0]]
        destination_stairs = list(
            destination_floor.up_stairs or [destination_floor.up]
        )
        destination_stairs += destination_floor.scholar_up_stairs
        player.x, player.y = destination_stairs[
            min(stair_index, len(destination_stairs) - 1)
        ]
        if secret_stair_index is not None:
            x, y = destination_floor.scholar_up_stairs[secret_stair_index]
            destination_floor.field[y][x] = d.CHAR_SCHOLAR_STAIRS_UP
            destination_floor.seen[y][x] = 1
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [
            (player.x, player.y, floor[0], ch)
            for _, _, _, ch in player.persistent_followers
        ]
        return trp("-- Descended to floor {n}/{total}.", 1).format(
            n=floor[0] + 1, total=floor_count
        )
    if floor[0] > 0 and point in up_stairs:
        stair_index = up_stairs.index(point)
        secret_stair_index = (
            current.scholar_up_stairs.index(point)
            if point in current.scholar_up_stairs
            else None
        )
        floor[0] -= 1
        destination_floor = floors[floor[0]]
        destination_stairs = list(
            destination_floor.down_stairs or [destination_floor.down]
        )
        destination_stairs += destination_floor.scholar_down_stairs
        player.x, player.y = destination_stairs[
            min(stair_index, len(destination_stairs) - 1)
        ]
        if secret_stair_index is not None:
            x, y = destination_floor.scholar_down_stairs[secret_stair_index]
            destination_floor.field[y][x] = d.CHAR_SCHOLAR_STAIRS_DOWN
            destination_floor.seen[y][x] = 1
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [
            (player.x, player.y, floor[0], ch)
            for _, _, _, ch in player.persistent_followers
        ]
        return trp("-- Ascended to floor {n}/{total}.", 1).format(
            n=floor[0] + 1, total=floor_count
        )
    return None


def _reveal_paired_stair_cells(
    floors: List[Floor], player: Optional[d.Player] = None
) -> None:
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
    stage_num: int = 0,
) -> None:
    if turn % d.MONSTER_RESPAWN_INTERVAL != 0:
        return
    changed_floors = set()
    respawned_barrier_sources = {}
    barrier_source_positions = {}
    for (queued_floor, type_key), count in list(queue.items()):
        if not count:
            continue
        ch = type_key[:-1] if type_key[-1].isdigit() else type_key
        if ch == "k" and turn % d.MARKSMAN_RESPAWN_INTERVAL:
            continue
        tribe = d.CHAR_TO_TRIBE[ch]
        spawn_floor = (
            rand.randrange(len(floors))
            if isinstance(tribe, d.MonsterTribe) and tribe.respawn_on_random_floor
            else queued_floor
        )
        if stage_num in (5, 6) and spawn_floor not in barrier_source_positions:
            barrier_source_positions[spawn_floor] = {
                id(monster): (monster, (monster.x, monster.y))
                for monster in floors[spawn_floor].entities
                if isinstance(monster, d.Monster)
                and stage56._barrier_offsets(monster)
            }
        avoid = {(player.x, player.y)} if spawn_floor == floor[0] else set()
        avoid.update(floors[spawn_floor].collapse_landings)
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
        respawned = None
        if stage_num in (5, 6):
            x, y = stage56.respawn(
                floors[spawn_floor], ch, empowered, spawn_floor, avoid,
                floor_index=spawn_floor,
            )
        elif empowered == 1:
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
        if isinstance(respawned, d.Monster):
            changed_floors.add(spawn_floor)
        if (
            stage_num in (5, 6)
            and isinstance(respawned, d.Monster)
            and stage56._barrier_offsets(respawned)
        ):
            respawned_barrier_sources.setdefault(spawn_floor, []).append(respawned)
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
    if stage_num in (5, 6):
        for changed_floor in changed_floors:
            current = floors[changed_floor]
            stage56.normalize_parties(
                current, d.MEMBER_STAGE_MONSTER_PARTY_LIMIT
            )
            player_position = (
                (player.x, player.y) if changed_floor == floor[0] else None
            )
            for monster in current.entities:
                previous_source = barrier_source_positions.get(
                    changed_floor, {}
                ).get(id(monster))
                if (
                    isinstance(monster, d.Monster)
                    and previous_source is not None
                    and previous_source[1] != (monster.x, monster.y)
                ):
                    stage56.update_moved_monster_barriers(
                        current, monster, previous_source[1],
                        player_position,
                    )
            for entity in respawned_barrier_sources.get(changed_floor, ()):
                if entity in current.entities:
                    stage56.place_monster_barriers(
                        current, entity, player_position
                    )


def _process_multi_floor_turn(
    direction: d.Point,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: Counter[Tuple[int, str]],
    turn: int,
    stage_num: int = 3,
    trace: Optional[TraceRecorder] = None,
    repeat_stop_reasons: Optional[Set[str]] = None,
    combat_effect=None,
    barrier_effect=None,
) -> Optional[Tuple[int, str]] | _RewindRequest:
    if player.status_popup_ticks > 0:
        player.status_popup_ticks -= 1
        if player.status_popup_ticks == 0:
            player.status_popup = None
    current = floors[floor[0]]

    previous = (player.x, player.y)
    just_climbed_pit = player.just_climbed_pit
    player.just_climbed_pit = False
    standing_on_collapse = (
        current.field[previous[1]][previous[0]] == d.CHAR_COLLAPSE
        and not just_climbed_pit
    )
    wall_result = None
    if not standing_on_collapse:
        wall_result = _move_player(direction, current, player, trace=trace)
    if wall_result is not None and repeat_stop_reasons is not None:
        repeat_stop_reasons.add("wall_interaction")
    if standing_on_collapse and repeat_stop_reasons is not None:
        repeat_stop_reasons.add("collapse_transition")

    collapse_contact = next(
        (
            entity
            for entity in current.entities
            if isinstance(entity, d.Collapse)
            and (entity.x, entity.y) == (player.x, player.y)
        ),
        None,
    )
    if (
        not standing_on_collapse
        and collapse_contact is not None
        and previous != (collapse_contact.x, collapse_contact.y)
    ):
        if repeat_stop_reasons is not None:
            repeat_stop_reasons.add("collapse_triggered")
        _reveal_collapse_pits(floors, floor[0], collapse_contact)

    entered_pit = (
        not standing_on_collapse
        and (player.x, player.y) != previous
        and current.field[player.y][player.x] == d.CHAR_COLLAPSE
    )
    if entered_pit and repeat_stop_reasons is not None:
        repeat_stop_reasons.add("collapse_transition")

    movement_destination = (player.x, player.y)
    checkpoint_x, checkpoint_y = checkpoint[0]
    if (
        movement_destination != previous
        and current.field[checkpoint_y][checkpoint_x] == d.CHAR_COLLAPSE
        and current.field[player.y][player.x] != d.CHAR_COLLAPSE
    ):
        checkpoint[0] = movement_destination
        if trace is not None:
            trace.record_checkpoint("left_pit", movement_destination, floor[0])

    # l contact is a control-flow event, not an ordinary gameplay turn. Detect
    # it before terrain hazards, monster actions, follower movement, stairs,
    # and respawn processing can mutate the state.
    hit = next(
        (
            i
            for i, entity in enumerate(current.entities)
            if (entity.x, entity.y) == (player.x, player.y)
        ),
        None,
    )
    if hit is not None and not standing_on_collapse:
        if repeat_stop_reasons is not None:
            repeat_stop_reasons.add("entity_contact")
        entity = current.entities[hit]
        if isinstance(entity, d.Companion) and entity.tribe.char == "l":
            contact = _resolve_contact(
                hit,
                current,
                floors,
                player,
                floor,
                checkpoint,
                queue,
                trace=trace,
                stage_num=stage_num,
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
            and (previous if standing_on_collapse else (player.x, player.y))
            in d.collapse_footprint((entity.x, entity.y))
        ),
        None,
    )
    if standing_on_collapse or entered_pit:
        from_floor = floor[0]
        collapse_point = previous if standing_on_collapse else (player.x, player.y)
        if collapse_hit is not None:
            current.seen[collapse_hit.y][collapse_hit.x] = 1
        current.seen[collapse_point[1]][collapse_point[0]] = 1
        floor[0] += 1
        checkpoint[0] = (player.x, player.y)
        if trace is not None:
            trace.record_checkpoint("trap_fall", (player.x, player.y), floor[0])
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
        event_message = trp(
            "-- The floor gives way! You fall to floor {n}/{total}.", 5
        ).format(n=floor[0] + 1, total=len(floors))
        current = floors[floor[0]]
        collapse_transition = True
    guardian_reduced_hazard = d.has_member(player, d.MEMBER_GUARDIAN) and (
        current.field[player.y][player.x] in (d.CHAR_BARRIER, d.CHAR_CALTROP)
    )
    old_hazard_lp = player.lp
    hazard_message = _apply_terrain_hazards(
        current, player, previous, trace=trace
    )
    if hazard_message is not None:
        event_message = hazard_message
    if (player.lp < old_hazard_lp
            and current.field[player.y][player.x] == d.CHAR_BARRIER
            and barrier_effect is not None):
        barrier_effect()
    player.marksman_damage_prevented = False
    if (player.x, player.y) != previous or collapse_transition:
        marksman_hit = _marksman_shoot(current, player, trace)
        if marksman_hit and repeat_stop_reasons is not None:
            repeat_stop_reasons.add("marksman_hit")
    hazard_damage = max(0, old_hazard_lp - player.lp)
    if hazard_damage or player.marksman_damage_prevented:
        tone = (
            "green"
            if guardian_reduced_hazard or player.marksman_damage_prevented
            else "default"
        )
        _set_status_popup(player, f"LP-{_format_popup_amount(hazard_damage)}", tone)

    hit = next(
        (
            i
            for i, entity in enumerate(current.entities)
            if (entity.x, entity.y) == (player.x, player.y)
        ),
        None,
    )
    if hit is not None:
        if repeat_stop_reasons is not None:
            repeat_stop_reasons.add("entity_contact")
        entity = current.entities[hit]
        if (combat_effect is not None and isinstance(entity, d.Monster)
                and not entity.tribe.is_elf
                and not entity.tribe.passive
                and (entity.tribe.char != "M" or entity.active)):
            enemies = (stage56.monster_party(current, entity)
                       if stage_num in (5, 6) else [entity])
            won = d.current_player_attack(player) >= sum(
                d.monster_level(monster) for monster in enemies
            )
            if stage_num in (5, 6):
                positions = (
                    [(monster.x, monster.y) for monster in enemies]
                    if won
                    else [
                        previous,
                        *((glyph.x + previous[0] - player.x,
                           glyph.y + previous[1] - player.y)
                          for glyph in ui_display.member_glyphs(player)),
                    ]
                )
                combat_effect(positions, won)
            else:
                combat_effect((entity.x, entity.y) if won else previous, won)
        contact = _resolve_contact(
            hit,
            current,
            floors,
            player,
            floor,
            checkpoint,
            queue,
            trace=trace,
            stage_num=stage_num,
        )
        if contact.end_turn:
            end_turn_message = prefer_event_message(event_message, contact.message)
            return (
                (contact.message_ticks, end_turn_message)
                if end_turn_message
                else None
            )
        event_message = prefer_event_message(event_message, contact.message)

    if (
        player.companion is not None
        and player.karma >= player.companion.durability
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
        event_message = prefer_event_message(
            event_message, trp("-- The companion vanishes.", 3)
        )
        if trace is not None:
            trace.add_expired({"type": "companion_departed", "id": ch})

    reveal_entities_in_fov(player, current.entities, floor_index=floor[0])
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
        if repeat_stop_reasons is not None:
            repeat_stop_reasons.add("floor_transition")
        event_message = prefer_event_message(event_message, transition_message)
        if trace is not None:
            trace.record_contact(
                {"type": "stairs", "from_floor": floor_before, "to_floor": floor[0]}
            )
            trace.record_checkpoint("stairs", (player.x, player.y), floor[0])

    _process_respawn_queue(
        floors, player, floor, queue, turn, trace=trace, stage_num=stage_num
    )
    if player.rescue_stage:
        stage56.sync_members(player, previous, direction)
    if (
        stage_num == 5
        and floor[0] == floor_before
        and (player.x, player.y) != previous
        and (player.x, player.y) == movement_destination
    ):
        line = stage5.trial_member_line(floors[floor[0]], player)
        if line is not None:
            if repeat_stop_reasons is not None:
                repeat_stop_reasons.add("member_dialogue")
            return (-2, line)
    return (MESSAGE_TICKS, event_message) if event_message else None


# Keep the old private name for tests and external tooling that imported it.
_step = _process_multi_floor_turn


def observe_world(
    floors: List[Floor], player: d.Player, floor_index: int,
    torch_radius: int,
) -> List[List[int]]:
    """Update exploration and discoveries before the next player input."""
    current = floors[floor_index]
    visible = get_torched(player, torch_radius)
    reveal_entities_in_fov(player, current.entities, floor_index=floor_index)
    if current.contact_reveal is not None:
        x, y = current.contact_reveal
        current.seen[y][x] = 1
    for y, row in enumerate(visible):
        for x, value in enumerate(row):
            current.seen[y][x] |= value
    if d.has_member(player, d.MEMBER_ROGUE):
        for entity in current.entities:
            if (
                isinstance(entity, d.Collapse)
                and 0 <= entity.y < len(visible)
                and 0 <= entity.x < len(visible[entity.y])
                and visible[entity.y][entity.x]
            ):
                _reveal_collapse_pits(floors, floor_index, entity)
    stage56.reveal_rogue_monsters(current, player, visible)
    if d.has_member(player, d.MEMBER_DUNGEON_EXPLORER):
        stage56.reveal_scholar_features(current, current.seen)
        if floor_index > 0:
            upper = floors[floor_index - 1]
            for y, row in enumerate(current.field):
                for x, cell in enumerate(row):
                    if (current.seen[y][x] and cell == d.CHAR_FLOOR
                            and upper.field[y][x] == d.CHAR_COLLAPSE):
                        current.field[y][x] = d.CHAR_SCHOLAR_STAIRS_UP
    _reveal_paired_stair_cells(floors, player)
    return visible


def _stage_draw_options(
    stage_num: int,
    floors: List[Floor],
    view_floor: int,
    single_floor_stage: bool,
    show_floor_label: bool,
) -> dict[str, Any]:
    if single_floor_stage:
        return {}
    if stage_num in (5, 6):
        return {
            "stage_roster": d.MEMBER_STAGE_ROSTER_TRIBES,
            "floor_label": f"{view_floor + 1}/{len(floors)}",
        }
    options: dict[str, Any] = {
        "stage_roster": d.STAGE3_ROSTER_TRIBES
        if stage_num == 3
        else d.STAGE4_ROSTER_TRIBES,
    }
    if show_floor_label or stage_num in d.ELF_STAGES:
        options["floor_label"] = f"{view_floor + 1}/{len(floors)}"
    return options


def run_game(
    ui: Any,
    seed_str: str,
    debug_show_entities: bool = False,
    trace: Optional[TraceRecorder] = None,
    config: Optional[GameConfig] = None,
    stage_num: int = 3,
) -> None:
    if config is None:
        config = GameConfig()
    initial_seed = rand.get_seed()
    single_floor_stage = stage_num in (1, 2)
    if single_floor_stage:
        floors, player = build_single_floor(config, stage_num)
    elif stage_num == 6:
        floors, player = stage6.build(config)
    elif stage_num == 5:
        floors, player = stage5.build_member_trial(config)
    else:
        floors, player = build(
            config.corridor_h_width,
            config.corridor_v_width,
            stage_num,
        )
    if stage_num == 6:
        player.rations = 1
    player.known_monsters = set()
    player.boss_defeated = False
    player.treasure_collected = False
    replay_context = (
        ReplayContext(stage_num, initial_seed, config)
        if not single_floor_stage
        else None
    )
    game_start_turn = 0
    loop_anchor_turn = 0
    has_rewound = False
    floor = [0]
    checkpoint = [floors[0].up]
    player.current_floor = 0
    operation_path: List[Tuple[int, d.Point]] = [
        (floor[0], (player.x, player.y))
    ]
    loop_trail_by_floor: Dict[int, Set[d.Point]] = {}
    loop_trail_expires_at = 0
    if trace is not None:
        trace.set_start_state(player, floor[0])
    trace_seen_recorded = (
        [deepcopy(floor_data.seen) for floor_data in floors]
        if trace is not None
        else []
    )
    trace_known_monsters_recorded = set(player.known_monsters)
    view_floor = 0
    queue: Counter[Tuple[int, str]] = Counter()
    turn = 0
    message_ticks, start_text = d.STAGE_START_MESSAGES[stage_num]
    message: Tuple[int, str] = (
        message_ticks, trp(start_text, 1) if start_text else "",
    )
    while True:
        current = floors[floor[0]]
        display_floor = floors[view_floor]
        cur = observe_world(floors, player, floor[0], config.torch_radius)

        message = tick_message(message)

        floor_view = view_floor != floor[0]
        show_entities = debug_show_entities or getattr(ui, "map_mode", False)
        reachable_cells: Set[d.Point] = set()
        if getattr(ui, "farthest_preview", False) and not floor_view:
            reachable_cells = reachable_known_cells(
                current.field,
                current.seen,
                cur,
                current.entities,
                player,
                {
                    (x, y)
                    for y, row in enumerate(current.field)
                    for x, cell in enumerate(row)
                    if cell == d.CHAR_D_GATE
                },
            )
        # Floor entities exclude the player for every stage. The terminal
        # renderer still discovers it through this render-only combined list.
        render_player = deepcopy(player) if floor_view else player
        render_player.current_floor = view_floor
        render_entities = [render_player, *display_floor.entities]
        known_types = player.known_monsters
        no_current_visibility = [
            [0] * len(display_floor.field[0]) for _ in display_floor.field
        ]
        stage_draw_options = _stage_draw_options(
            stage_num, floors, view_floor, single_floor_stage, show_floor_label=True
        )
        if stage_draw_options:
            stage_draw_options["floor_view"] = floor_view
        if player.lp <= 0:
            message = (-1, trp(">> Collapsed from hunger! <<", 9))
        ui.draw_stage(
            turn=turn,
            game_start_turn=game_start_turn if has_rewound else None,
            player=render_player,
            entities=render_entities,
            field=display_floor.field,
            cur_torched=no_current_visibility if floor_view else cur,
            torched=display_floor.seen,
            known_types=known_types,
            show_entities=show_entities,
            debug_show_entities=debug_show_entities,
            stage_num=stage_num,
            message=message[1],
            checkpoint=checkpoint[0],
            decor=display_floor.decor,
            d_gates=display_floor.d_gates,
            reachable_cells=reachable_cells,
            overshoot_markers=(
                trace.overshoot_rewind_markers(floor[0])
                if trace is not None and not floor_view
                else set()
            ),
            loop_trail_markers=(
                loop_trail_by_floor.get(floor[0], set())
                if not floor_view and turn < loop_trail_expires_at
                else set()
            ),
            **stage_draw_options,
        )

        if player.lp <= 0:
            _stop_movement_repeat(ui)
            confirm = getattr(ui, "confirm_ration", None)
            eligible = (
                _ration_available(current, player, cur) if stage_num == 6
                else d.RATIONS_ENABLED
            )
            if not eligible or not player.rations or confirm is None:
                break
            decision = confirm(player)
            if decision is None:
                if trace is not None:
                    trace.record_quit()
                    trace.set_outcome("quit")
                return
            if not decision:
                break
            if trace is not None:
                trace.turns[-1]["ration_used"] = True
            player.rations -= 1
            player.lp = d.STAGE6_RATION_LP if stage_num == 6 else d.RATION_LP
            if replay_context is not None:
                replay_context.ration_uses.add(len(replay_context.operations))
            message = (-1, "")
            continue

        move = ui.input_direction()
        if move is None:
            if trace is not None:
                trace.record_quit()
                trace.set_outcome(
                    "unfinished" if getattr(ui, "ran_dry", False) else "quit"
                )
            return
        if getattr(ui, "escape_check_requested", False):
            ui.escape_check_requested = False
            active = floors[floor[0]]
            targets = {(entity.x, entity.y) for entity in active.entities
                       if isinstance(entity, (d.Monster, d.Companion, d.PartyMember))
                       and not (isinstance(entity, d.Monster)
                                and entity.tribe.char == "M" and not entity.active)}
            explorer = d.has_member(player, d.MEMBER_DUNGEON_EXPLORER)
            for y, row in enumerate(active.field):
                for x, cell in enumerate(row):
                    if cell in (d.CHAR_STAIRS_UP, d.CHAR_STAIRS_DOWN, d.CHAR_COLLAPSE):
                        targets.add((x, y))
                    if explorer and (cell in d.SCHOLAR_STAIR_CHARS or (
                        floor[0] > 0 and cell == d.CHAR_FLOOR
                        and floors[floor[0] - 1].field[y][x] == d.CHAR_COLLAPSE
                    )):
                        targets.add((x, y))
            reachable = reachable_known_cells(
                active.field, active.seen, cur, active.entities, player,
                terminal_targets=targets,
                include_unexplored=True,
            )
            confirm = getattr(ui, "confirm_game_over", None)
            if not targets.intersection(reachable) and confirm is not None:
                if confirm() is True:
                    _stop_movement_repeat(ui)
                    if trace is not None:
                        trace.record_quit()
                        trace.set_outcome("quit")
                    return
                ui.farthest_preview = True
                view_floor = floor[0]
                continue
        if getattr(ui, "floor_view_reset_requested", False):
            view_floor = floor[0]
            ui.floor_view_reset_requested = False
        if move == (0, 0):
            continue
        if getattr(ui, "farthest_preview", False):
            ui.farthest_preview = False
        if getattr(ui, "shift_direction", False):
            view_floor = max(0, min(len(floors) - 1, view_floor + move[1]))
            continue

        # Dialogue remains visible through non-movement UI actions.
        if message[0] == -2:
            message = (-1, "")
        # A real movement always returns the display to the player's floor.
        view_floor = floor[0]
        rogue_spotted_danger = False
        if d.has_member(player, d.MEMBER_ROGUE):
            destination = (player.x + move[0], player.y + move[1])
            if stage56.rogue_danger(current, destination):
                rogue_spotted_danger = True
                if replay_context is not None:
                    replay_context.rogue_checks.setdefault(
                        len(replay_context.operations), []
                    ).append(destination)
                _stop_movement_repeat(ui)
                message = (5, trp("-- Rogue spotted danger. Movement repeat stopped.", 5))
        repeat_stop_enabled = getattr(ui, "auto_repeat_stop_enabled", True)
        if (
            repeat_stop_enabled
            and not rogue_spotted_danger
            and getattr(ui, "input_was_repeat", False)
            and _should_stop_movement_repeat(
                move,
                current,
                player,
                show_all_entities=show_entities,
                known_types=known_types,
            )
        ):
            _stop_movement_repeat(ui)
            continue

        if trace is not None:
            key = DIR_TO_KEY.get(move)
            if key is None:
                raise RuntimeError(
                    "--trace does not support non-cardinal (e.g. diagonal joystick) movement"
                )
            trace.begin_turn(key)

        if replay_context is not None:
            replay_context.operations.append(move)
            game_start_turn += 1
            replay_context.turn_to_operation[game_start_turn] = len(
                replay_context.operations
            )

        repeat_stop_reasons: Optional[Set[str]] = (
            set() if repeat_stop_enabled or stage_num == 5 else None
        )
        def show_barrier_effect():
            active = floors[floor[0]]
            visible = observe_world(
                floors, player, floor[0], config.torch_radius
            )
            ui.draw_stage(
                turn=turn, player=player, entities=[player, *active.entities],
                field=active.field, cur_torched=visible, torched=active.seen,
                known_types=player.known_monsters,
                show_entities=debug_show_entities or getattr(ui, "map_mode", False),
                debug_show_entities=debug_show_entities, stage_num=stage_num,
                message=None,
                checkpoint=checkpoint[0], decor=active.decor,
                **_stage_draw_options(
                    stage_num, floors, floor[0], single_floor_stage,
                    show_floor_label=True,
                ),
            )
            effect = getattr(ui, "draw_combat_effect", None)
            if effect is not None:
                effect((player.x, player.y), False)

        step_result = _process_multi_floor_turn(
            move,
            floors,
            player,
            floor,
            checkpoint,
            queue,
            turn,
            stage_num=stage_num,
            trace=trace,
            repeat_stop_reasons=repeat_stop_reasons,
            combat_effect=getattr(ui, "draw_combat_effect", None),
            barrier_effect=show_barrier_effect,
        )
        if replay_context is not None:
            operation_path.append((floor[0], (player.x, player.y)))
        if repeat_stop_reasons and (
            repeat_stop_enabled or "member_dialogue" in repeat_stop_reasons
        ):
            _stop_movement_repeat(ui)
        if isinstance(step_result, _RewindRequest):
            assert replay_context is not None, "Loop contact requires recorded inputs"
            operation_count = len(replay_context.operations)
            rewind_turn, rewind_operation = replay_context.prepare_loop_rewind(
                game_start_turn, loop_anchor_turn,
            )
            loop_trail_by_floor.clear()
            loop_trail_expires_at = turn + d.LOOP_TRAIL_TURNS + 1
            for trail_floor, position in operation_path[
                rewind_operation + 1 : operation_count + 1
            ]:
                loop_trail_by_floor.setdefault(trail_floor, set()).add(position)
            transition_message = trp(
                "-- Time folds back to the beginning of the recorded past.", 9
            )
            show_transition = getattr(ui, "draw_rewind_transition", None)
            if show_transition is not None:
                show_transition(transition_message)
            rewind_message = _rewind(
                floors,
                player,
                floor,
                checkpoint,
                queue,
                replay_context,
                operation_count=operation_count,
                loop_floor_index=step_result.floor_index,
            )
            operation_path[operation_count] = (floor[0], (player.x, player.y))
            # Rewind contacts still reach the normal turn-end LP decrement.
            player.lp += d.movement_lp_cost(player)
            replay_context.anchor_loop_rewind(rewind_turn)
            game_start_turn = rewind_turn
            # The turn mapping now points to this contact, preserving its
            # respawn and earlier rewinds when returning to the anchor again.
            loop_anchor_turn = rewind_turn
            has_rewound = True
            event_message: Optional[Tuple[int, str]] = (5, rewind_message)
        else:
            event_message = step_result
        player.current_floor = floor[0]
        # A stair contact can change the player's floor during _step(). Keep
        # the displayed floor in sync so the next frame shows the new floor.
        view_floor = floor[0]
        if event_message is not None:
            if event_message[0] == -2 or prefer_event_message(
                message[1] if message is not None else None, event_message[1]
            ) == event_message[1]:
                message = event_message

        if trace is not None:
            trace.set_player(player, floor_index=floor[0])
            seen_added_count = sum(
                1
                for floor_data, previous_seen in zip(
                    floors, trace_seen_recorded, strict=True
                )
                for y, row in enumerate(floor_data.seen)
                for x, is_seen in enumerate(row)
                if is_seen and not previous_seen[y][x]
            )
            trace.record_state_changes(
                seen_added_count,
                list(player.known_monsters - trace_known_monsters_recorded),
            )
            trace_seen_recorded = [
                deepcopy(floor_data.seen) for floor_data in floors
            ]
            trace_known_monsters_recorded = set(player.known_monsters)

        turn += 1
        player.lp -= d.movement_lp_cost(player)
        if trace is not None:
            trace.set_turn_end_lp(player.lp)
            trace.commit_turn()
            overshoot_target = trace.find_overshoot_rewind_target()
            if overshoot_target is not None and not player.stage_won:
                retained_turns, target_floor, target_position, target_lp = (
                    overshoot_target
                )
                _stop_movement_repeat(ui)
                floor[0] = target_floor
                player.x, player.y = target_position
                player.current_floor = target_floor
                player.lp = target_lp
                view_floor = target_floor

                if replay_context is not None:
                    target_game_turn = max(
                        (
                            game_turn
                            for game_turn, operation_count
                            in replay_context.turn_to_operation.items()
                            if operation_count == retained_turns
                        ),
                        default=retained_turns,
                    )
                    replay_context.operations[:] = replay_context.operations[
                        :retained_turns
                    ]
                    operation_path[:] = operation_path[: retained_turns + 1]
                    for game_turn, operation_count in tuple(
                        replay_context.turn_to_operation.items()
                    ):
                        if (
                            game_turn > target_game_turn
                            or operation_count > retained_turns
                        ):
                            del replay_context.turn_to_operation[game_turn]
                    replay_context.turn_to_operation[target_game_turn] = (
                        retained_turns
                    )
                    for operation_count in tuple(replay_context.rewind_targets):
                        if operation_count > retained_turns:
                            del replay_context.rewind_targets[operation_count]
                    replay_context.rogue_checks = {
                        index: checks
                        for index, checks in replay_context.rogue_checks.items()
                        if index < retained_turns
                    }
                    game_start_turn = target_game_turn

                turn = retained_turns
                trace.truncate_after_turn(retained_turns)
        if player.stage_won:
            break

    won = player.stage_won
    if trace is not None:
        trace.set_outcome("win" if won else "lose")

    if not won:
        message = (-1, trp(">> Collapsed from hunger! <<", 9))
    else:
        message = (-1, trp(">> Treasure chest obtained! <<", 9))
    view_floor = floor[0]
    while True:
        display_floor = floors[view_floor]
        floor_view = view_floor != floor[0]
        cur = get_torched(player, config.torch_radius)
        render_player = deepcopy(player) if floor_view else player
        render_player.current_floor = view_floor
        render_entities = [render_player, *display_floor.entities]
        known_types = player.known_monsters
        stage_draw_options = _stage_draw_options(
            stage_num, floors, view_floor, single_floor_stage, show_floor_label=False
        )
        ui.draw_stage(
            turn=turn,
            game_start_turn=game_start_turn if has_rewound else None,
            player=render_player,
            entities=render_entities,
            field=display_floor.field,
            cur_torched=(
                [[0] * len(display_floor.field[0]) for _ in display_floor.field]
                if floor_view else cur
            ),
            torched=display_floor.seen,
            known_types=known_types,
            show_entities=debug_show_entities or getattr(ui, "map_mode", False),
            debug_show_entities=debug_show_entities,
            stage_num=stage_num,
            message=message[1],
            extra_keys=True,
            checkpoint=checkpoint[0],
            decor=display_floor.decor,
            floor_view=floor_view,
            **stage_draw_options,
        )
        input_game_over = getattr(ui, "input_game_over", None)
        key = input_game_over() if input_game_over is not None else ui.input_alphabet()
        if key is None:
            return
        if key == "m":
            if hasattr(ui, "map_mode"):
                ui.map_mode = True
            else:
                debug_show_entities = True
        elif key == "s":
            message = (-1, tr("SEED: {seed_str}").format(seed_str=seed_str))
        elif isinstance(key, tuple) and len(key) == 3:
            _, dy, shifted = key
            if shifted:
                view_floor = max(0, min(len(floors) - 1, view_floor + dy))
