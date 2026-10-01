from typing import Callable, Container, List, Tuple, Optional

import argparse
from dataclasses import dataclass
from importlib import import_module
import math
import sys
from pathlib import Path

from appdirs import user_cache_dir

from .__about__ import __version__

from .utils import rand
from . import defs as d
from .i18n import trp
from .trace import (
    TraceRecorder,
)
from .game_events import ContactEvent, ExpiredEvent, TurnEvents, UpdateResult, WallEvent

MESSAGE_TICKS = 8
GAME_ENGINE_MODULE = "game_engine"
PLAYER_PASSABLE_CELLS = (
    d.CHAR_FLOOR,
    d.CHAR_CALTROP,
    d.CHAR_COLLAPSE,
    *d.STAIR_CHARS,
    d.CHAR_BARRIER,
)


@dataclass(frozen=True)
class GameConfig:
    torch_radius: int = d.TORCH_RADIUS
    corridor_h_width: int = d.CORRIDOR_H_WIDTH
    corridor_v_width: int = d.CORRIDOR_V_WIDTH


def game_config_from_args(args) -> GameConfig:
    torch_adjustment = 1 if args.large_torch else -1 if args.small_torch else 0
    corridor_adjustment = 1 if args.narrower_corridors else 0
    return GameConfig(
        torch_radius=d.TORCH_RADIUS + torch_adjustment,
        corridor_h_width=d.CORRIDOR_H_WIDTH - corridor_adjustment,
        corridor_v_width=d.CORRIDOR_V_WIDTH - corridor_adjustment,
    )


def parse_replay_interval(value: str) -> float:
    """Parse a nonnegative terminal replay delay in seconds."""
    try:
        parsed_interval = float(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("must be a number of seconds") from None
    if not math.isfinite(parsed_interval) or parsed_interval < 0:
        raise argparse.ArgumentTypeError("must be a finite, nonnegative number")
    return parsed_interval


def tick_message(message: Tuple[int, str]) -> Tuple[int, str]:
    ticks, text = message
    if ticks < 0:
        return message
    ticks -= 1
    if ticks < 0:
        return (-1, "")
    return (ticks, text)


def prefer_event_message(
    current: Optional[str], candidate: Optional[str]
) -> Optional[str]:
    """Keep the more important event message when several occur in one turn."""
    if candidate is None:
        return current
    if current is None:
        return candidate

    current_importance = getattr(current, "importance", 0)
    candidate_importance = getattr(candidate, "importance", 0)
    return candidate if candidate_importance >= current_importance else current


def generate_maze(
    width: int, height: int, excluded_tile: Optional[d.Point] = None
) -> Tuple[List[d.Edge], d.Point, d.Point]:
    # Returns a list of neighboring points given a point p
    def neighbor_points(p):
        x, y = p
        return [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]

    # Returns True if the given point p is within the bounds of the maze
    def is_within_bounds(p):
        return 0 <= p[0] < width and 0 <= p[1] < height

    # Initialize the maze generation process
    unconnected_point_set = set((x, y) for y in range(height) for x in range(width))
    if excluded_tile is not None:
        unconnected_point_set.remove(excluded_tile)
    tile_count = len(unconnected_point_set)
    connecting_points = []
    done_points: List[d.Point] = []
    edges = []

    # Choose a random starting point
    unconnected_nps = list(unconnected_point_set)
    first_point = cur_p = rand.choice(unconnected_nps)
    last_point = rand.choice(unconnected_nps)  # dummy
    unconnected_point_set.remove(cur_p)
    connecting_points.append(cur_p)

    # Keep generating until all points have been connected
    while len(done_points) < tile_count:
        # Choose a random connecting point
        i = rand.randrange(len(connecting_points))
        cur_p = connecting_points[i]

        # Find neighboring points that haven't been connected yet
        nps = neighbor_points(cur_p)
        unconnected_nps = [
            np for np in nps if is_within_bounds(np) and np in unconnected_point_set
        ]

        # If there are no unconnected neighboring points, remove this point from the connecting points list
        if not unconnected_nps:
            done_points.append(cur_p)
            del connecting_points[i]
            continue

        # Choose a random unconnected neighboring point and connect it
        last_point = selected_np = rand.choice(unconnected_nps)
        unconnected_point_set.remove(selected_np)
        connecting_points.append(selected_np)

        # Add the edge between the current point and the selected neighboring point to the list of edges
        edges.append((cur_p, selected_np))

    # Return the list of edges that connect all points in the maze
    return edges, first_point, last_point


def place_to_tile(x: int, y: int) -> d.Point:
    return (x - 1) // (d.TILE_WIDTH + 1), (y - 1) // (d.TILE_HEIGHT)


def tile_to_place_range(x: int, y: int) -> Tuple[d.Point, d.Point]:
    lt = (x * (d.TILE_WIDTH + 1) + 1, y * (d.TILE_HEIGHT + 1) + 1)
    rb = (lt[0] + d.TILE_WIDTH, lt[1] + d.TILE_HEIGHT)
    return lt, rb


def find_random_place(
    entities: List[d.Entity],
    field: List[List[str]],
    distance: int = 1,
    *,
    far_from: Optional[d.Point] = None,
    min_manhattan_distance: int = 25,
    far_attempts: int = 10,
    avoid: Optional[Callable[[d.Point], bool]] = None,
) -> d.Point:
    places = [(e.x, e.y) for e in entities]

    def is_valid(x: int, y: int) -> bool:
        point = (x, y)
        return (
            all(c == d.CHAR_FLOOR for c in field[y][x - 1 : x + 2])
            and not any(
                abs(p[0] - x) <= distance and abs(p[1] - y) <= distance for p in places
            )
            and not (avoid is not None and avoid(point))
        )

    if far_from is not None:
        for _ in range(far_attempts):
            x = rand.randrange(d.FIELD_WIDTH - 2) + 1
            y = rand.randrange(d.FIELD_HEIGHT - 2) + 1
            manhattan_distance = abs(x - far_from[0]) + abs(y - far_from[1])
            if is_valid(x, y) and manhattan_distance >= min_manhattan_distance:
                return x, y

    while True:
        x = rand.randrange(d.FIELD_WIDTH - 2) + 1
        y = rand.randrange(d.FIELD_HEIGHT - 2) + 1
        if is_valid(x, y):
            return x, y


def find_marksman_place(
    entities: List[d.Entity],
    field: List[List[str]],
    distance: int = 2,
    *,
    avoid: Optional[Callable[[d.Point], bool]] = None,
) -> d.Point:
    """Choose the best firing position among up to three valid spawn cells."""
    occupied = [(entity.x, entity.y) for entity in entities]
    valid_points = [
        (x, y)
        for y in range(1, len(field) - 1)
        for x in range(1, len(field[0]) - 1)
        if all(cell == d.CHAR_FLOOR for cell in field[y][x - 1 : x + 2])
        and not any(
            abs(px - x) <= distance and abs(py - y) <= distance
            for px, py in occupied
        )
        and not (avoid is not None and avoid((x, y)))
    ]
    if not valid_points:
        return find_random_place(entities, field, distance=distance, avoid=avoid)

    candidates = []
    for _ in range(min(3, len(valid_points))):
        candidates.append(valid_points.pop(rand.randrange(len(valid_points))))
    return max(
        candidates,
        key=lambda point: _marksman_sight_score(entities, field, point),
    )


def _marksman_sight_score(
    entities: List[d.Entity], field: List[List[str]], point: d.Point
) -> int:
    """Count cells a marksman at point could target along clear cardinal rays."""
    blocked_entities = {
        (entity.x, entity.y)
        for entity in entities
        if isinstance(entity, (d.Companion, d.Treasure))
    }
    score = 0
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        x, y = point
        distance = 0
        while True:
            x += dx
            y += dy
            distance += 1
            if not (0 <= y < len(field) and 0 <= x < len(field[0])):
                break
            if field[y][x] in (d.CHAR_WALL, *d.STAIR_CHARS):
                break
            if (x, y) in blocked_entities:
                break
            if distance > 1:
                score += 1
    return score


def spawn_at(
    entities: List[d.Entity],
    x: int,
    y: int,
    tribe: d.Tribe,
    empowered: int = 1,
    origin_floor: Optional[int] = None,
) -> d.Entity:
    entity: d.Entity
    if isinstance(tribe, d.ElfTribe):
        entity = d.Elf(x, y, tribe)
    elif isinstance(tribe, d.MonsterTribe):
        entity = d.Monster(x, y, tribe, empowered=empowered)
    else:
        assert isinstance(tribe, d.CompanionTribe)
        entity = d.Companion(x, y, tribe, origin_floor=origin_floor)
    entities.append(entity)
    return entity


def spawn_entities(
    entities: List[d.Entity],
    field: List[List[str]],
    spawn_configs: List[d.SpawnConfig],
) -> None:
    """Spawn monsters and companions from the stage's spawn configurations.

    A float population is the probability of spawning one entity.
    """
    for config in spawn_configs:
        population = config.population
        if isinstance(population, float):
            population = 1 if rand.randrange(100) / 100 < population else 0
        for _ in range(population):
            if config.tribe.char == "k":
                x, y = find_marksman_place(entities, field, distance=2)
            else:
                x, y = find_random_place(entities, field, distance=2)
            spawn_at(entities, x, y, config.tribe, empowered=config.empowered)


def respawn_entity(
    tribe: d.Tribe,
    entities: List[d.Entity],
    field: List[List[str]],
) -> d.Entity:
    """Place one monster or companion for legacy single-floor callers.

    Companion instances are returned revealed, matching the former respawn
    helper's behavior.
    """
    if tribe.char == "k":
        x, y = find_marksman_place(entities, field, distance=2)
    else:
        x, y = find_random_place(entities, field, distance=2)
    entity = spawn_at(entities, x, y, tribe)
    if isinstance(entity, d.Companion):
        entity.revealed = True
    return entity


def create_field(
    corridor_h_width: int,
    corridor_v_width: int,
    wall_char: str,
    excluded_tile: Optional[d.Point] = None,
    margin_x: int = 0,
    tile_columns: Optional[int] = None,
) -> Tuple[List[List[str]], d.Point, d.Point]:
    def find_empty_cell(
        field: List[List[str]], left_top: d.Point, right_bottom: d.Point
    ) -> d.Point:
        assert left_top[0] < right_bottom[0]
        assert left_top[1] < right_bottom[1]

        while True:
            x = rand.randrange(right_bottom[0] - left_top[0]) + left_top[0]
            y = rand.randrange(right_bottom[1] - left_top[1]) + left_top[1]
            if field[y][x] == d.CHAR_FLOOR:
                return x, y

    # margin_x keeps the existing symmetric crop; tile_columns allows callers
    # to choose an exact active maze width within the fixed-size field.
    tile_num_x = d.TILE_NUM_X - 2 * margin_x
    tile_offset_x = margin_x
    if tile_columns is not None:
        if not 1 <= tile_columns <= d.TILE_NUM_X:
            raise ValueError("tile_columns must fit within the field")
        tile_num_x = tile_columns
        tile_offset_x = (d.TILE_NUM_X - tile_num_x) // 2

    field: List[List[str]] = [
        [d.CHAR_FLOOR for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)
    ]

    # Create walls
    for ty in range(d.TILE_NUM_Y + 1):
        y = ty * (d.TILE_HEIGHT + 1)
        for x in range(0, d.FIELD_WIDTH):
            field[y][x] = wall_char
    for tx in range(d.TILE_NUM_X + 1):
        x = tx * (d.TILE_WIDTH + 1)
        for y in range(0, d.FIELD_HEIGHT):
            field[y][x] = wall_char
    for ty in range(d.TILE_NUM_Y + 1):
        y = ty * (d.TILE_HEIGHT + 1)
        for tx in range(d.TILE_NUM_X + 1):
            x = tx * (d.TILE_WIDTH + 1)
            field[y][x] = wall_char

    c = rand.randrange(17)
    for ty in range(d.TILE_NUM_Y):
        y1 = ty * (d.TILE_HEIGHT + 1) + 1
        y2 = ty * (d.TILE_HEIGHT + 1) + d.TILE_HEIGHT
        for tx in range(d.TILE_NUM_X):
            x1 = tx * (d.TILE_WIDTH + 1) + 1
            x2 = tx * (d.TILE_WIDTH + 1) + d.TILE_WIDTH
            if (c := c + 3) % 17 < 5:
                field[y1][x1] = wall_char
            if (c := c + 3) % 17 < 5:
                field[y1][x2] = wall_char
            if (c := c + 3) % 17 < 5:
                field[y2][x1] = wall_char
            if (c := c + 3) % 17 < 5:
                field[y2][x2] = wall_char

    # Create corridors
    edges, first_p, last_p = generate_maze(tile_num_x, d.TILE_NUM_Y, excluded_tile)
    first_p = (first_p[0] + tile_offset_x, first_p[1])
    last_p = (last_p[0] + tile_offset_x, last_p[1])
    for edge in edges:
        (x1, y1), (x2, y2) = sorted(edge)
        assert x1 <= x2
        assert y1 <= y2
        x1, x2 = x1 + tile_offset_x, x2 + tile_offset_x
        if y1 == y2:
            offset = rand.randrange(d.TILE_HEIGHT + 1 - corridor_h_width) + 1
            for y in range(corridor_h_width):
                field[y1 * (d.TILE_HEIGHT + 1) + offset + y][
                    x2 * (d.TILE_WIDTH + 1)
                ] = d.CHAR_FLOOR
        else:
            assert x1 == x2
            offset = rand.randrange(d.TILE_WIDTH + 1 - corridor_v_width) + 1
            for x in range(corridor_v_width):
                field[y2 * (d.TILE_HEIGHT + 1)][
                    x1 * (d.TILE_WIDTH + 1) + offset + x
                ] = d.CHAR_FLOOR

    # The sealed tile can interrupt a direct route between its neighbors.
    # Rust's stage 3 adds a short bypass on the adjacent row at an outer edge.
    if excluded_tile is not None:
        island_x, island_y = excluded_tile
        if 0 < island_x < tile_num_x - 1:
            bypass_y = (
                1
                if island_y == 0
                else d.TILE_NUM_Y - 2
                if island_y == d.TILE_NUM_Y - 1
                else None
            )
            if bypass_y is not None:
                offset = rand.randrange(d.TILE_HEIGHT + 1 - corridor_h_width) + 1
                for y in range(corridor_h_width):
                    row = bypass_y * (d.TILE_HEIGHT + 1) + offset + y
                    field[row][
                        (island_x + tile_offset_x) * (d.TILE_WIDTH + 1)
                    ] = d.CHAR_FLOOR
                    field[row][
                        (island_x + 1 + tile_offset_x) * (d.TILE_WIDTH + 1)
                    ] = d.CHAR_FLOOR

    # Wall off the margin columns entirely so they read as removed, rather
    # than as a disconnected strip of tiny rooms.
    if tile_offset_x > 0 or tile_offset_x + tile_num_x < d.TILE_NUM_X:
        left_edge = tile_offset_x * (d.TILE_WIDTH + 1)
        right_edge = (tile_offset_x + tile_num_x) * (d.TILE_WIDTH + 1)
        for y in range(d.FIELD_HEIGHT):
            for x in range(0, left_edge):
                field[y][x] = wall_char
            for x in range(right_edge, d.FIELD_WIDTH):
                field[y][x] = wall_char

    r = tile_to_place_range(*first_p)
    first_p = find_empty_cell(field, r[0], r[1])
    r = tile_to_place_range(*last_p)
    last_p = find_empty_cell(field, r[0], r[1])
    return field, first_p, last_p


def iterate_ellipse_points(
    center_x: int,
    center_y: int,
    radius: int,
    width_expansion_ratio: float,
    except_for_center: bool = False,
    except_for_entities: Optional[List[d.Entity]] = None,
):
    entity_coordinates = (
        set((e.x, e.y) for e in except_for_entities) if except_for_entities else set()
    )
    for dy in range(-radius, radius + 1):
        y = center_y + dy
        if 0 <= y < d.FIELD_HEIGHT:
            if radius == 0:
                w = 0
            else:
                horizontal_radius = radius * width_expansion_ratio
                vertical_position = max(
                    0.0,
                    (abs(dy) - d.ELLIPSE_CELL_EDGE_THRESHOLD) / radius,
                )
                w = int(
                    horizontal_radius
                    * math.sqrt(1 - vertical_position**2)
                    + 0.5
                )
            for dx in range(-w, w + 1):
                x = center_x + dx
                if 0 <= x < d.FIELD_WIDTH:
                    if except_for_center and y == center_y and x == center_x:
                        continue
                    if (x, y) not in entity_coordinates:
                        yield x, y


def spread_caltrops(
    field: List[List[str]], origin: d.Point, entities: List[d.Entity]
) -> None:
    ox, oy = origin
    for x, y in iterate_ellipse_points(
        ox,
        oy,
        d.CALTROP_SPREAD_RADIUS,
        d.CALTROP_WIDTH_EXPANSION_RATIO,
        except_for_center=True,
        except_for_entities=entities,
    ):
        if (x + y) % 2 == 0 and field[y][x] in (d.CHAR_FLOOR, d.CHAR_WALL):
            field[y][x] = d.CHAR_CALTROP


def iterate_offsets(
    center_x: int,
    center_y: int,
    offsets: List[d.Point],
    except_for_entities: Optional[List[d.Entity]] = None,
):
    entity_coordinates = (
        set((e.x, e.y) for e in except_for_entities) if except_for_entities else set()
    )
    for dx, dy in offsets:
        x = center_x + dx
        y = center_y + dy
        if 0 <= x < d.FIELD_WIDTH and 0 <= y < d.FIELD_HEIGHT:
            if (x, y) not in entity_coordinates:
                yield x, y


def get_torched(player: d.Player, torch_radius: int) -> List[List[int]]:
    torched: List[List[int]] = [
        [0 for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)
    ]

    has_ocular = player.companion is not None and player.companion.tribe.char == "o"
    if player.item == d.ITEM_SPORES:
        torch_radius = 2 if has_ocular else 1
    elif has_ocular:
        torch_radius += d.OCULAR_TORCH_EXTENSION

    for x, y in iterate_ellipse_points(
        player.x, player.y, torch_radius, d.FOV_WIDTH_EXPANSION_RATIO
    ):
        torched[y][x] = 1

    return torched


def unlock_treasure_for_defeat(
    monster: d.Monster,
    entities: List[d.Entity],
) -> None:
    """Unlock chests whose key is T followed by the defeated tribe's char."""
    treasure_key = d.CHAR_TREASURE + monster.tribe.char
    for entity in entities:
        if isinstance(entity, d.Treasure) and entity.unlock_key == treasure_key:
            entity.unlocked = True


def activate_mimic_for_defeat(
    monster: d.Monster,
    entities: List[d.Entity],
) -> None:
    """Activate mimics disguised as the defeated monster's treasure."""
    boss_char = monster.tribe.char
    for entity in entities:
        if (
            isinstance(entity, d.Monster)
            and entity.tribe.char == "M"
            and entity.mimic_boss_char == boss_char
            and (
                entity.mimic_boss_empowered is None
                or entity.mimic_boss_empowered == monster.empowered
            )
        ):
            entity.active = True


def reveal_entities_in_fov(
    player: d.Player,
    entities: List[d.Entity],
    torch_radius: int = d.TORCH_RADIUS,
    floor_index: int = 0,
) -> None:
    """Reveal active monsters currently inside the player's FOV."""
    if player.companion is None or player.companion.tribe.char != "n":
        return
    torched = get_torched(player, torch_radius)
    for entity in entities:
        if not (0 <= entity.y < d.FIELD_HEIGHT and 0 <= entity.x < d.FIELD_WIDTH):
            continue
        if not torched[entity.y][entity.x]:
            continue
        if isinstance(entity, d.Monster) and entity.active:
            if entity.tribe.is_elf:
                entity.revealed = True
                player.known_elf_floors.add(entity.tribe.char)
            else:
                player.known_monsters.add(d.monster_type_key(entity))
                if entity.tribe.char == "C":
                    player.known_c_floors.add(floor_index + 1)


def move_player(
    direction: d.Point,
    field: List[List[str]],
    player: d.Player,
    passable_cells: Container[str],
) -> Optional[WallEvent]:
    """Move the player and return a traceable wall-interaction result.

    A normal step has no wall result. Blocked movement, a Pegasus phase, and
    a sword-broken wall return the event recorded by the gameplay trace.
    """
    dx, dy = direction
    nx, ny = player.x + dx, player.y + dy
    height = len(field)
    width = len(field[0]) if field else 0

    if not (0 <= ny < height and 0 <= nx < width):
        return WallEvent("blocked")

    cell = field[ny][nx]
    if cell in passable_cells:
        player.x, player.y = nx, ny
        return None

    if player.companion is not None and player.companion.tribe.char == d.CHAR_PEGASUS:
        jump_x = player.x + dx * d.PEGASUS_STEP_X
        jump_y = player.y + dy * d.PEGASUS_STEP_Y
        if (
            0 <= jump_y < height
            and 0 <= jump_x < width
            and field[jump_y][jump_x] in PLAYER_PASSABLE_CELLS
        ):
            player.x, player.y = jump_x, jump_y
            player.karma += 1
            return WallEvent("pegasus_phase")
        return WallEvent("blocked")

    if (
        player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED)
        and player.item_uses > 0
        and cell == d.CHAR_WALL
    ):
        player.x, player.y = nx, ny
        field[ny][nx] = d.CHAR_FLOOR
        if player.item == d.ITEM_SWORD_CURSED:
            player.lp -= d.CURSED_SWORD_LP_COST
        player.item_uses -= 1
        if player.item_uses == 0:
            d.clear_player_item(player)
        return WallEvent("sword_break", player.item_uses)

    return WallEvent("blocked")


def barrier_lp_damage(player: d.Player) -> int:
    """Return the LP cost for entering a barrier cell."""
    return (
        0
        if (
            player.elf_stage_flags & d.ELF_STAGE_H_FLAG
            and player.item != d.ITEM_SWORD_CURSED
        )
        else d.BARRIER_LP_DAMAGE
    )


def apply_barrier_damage(
    field: List[List[str]], player: d.Player, previous: d.Point
) -> bool:
    """Apply the shared barrier cost after movement and report whether it burned."""
    if (player.x, player.y) == previous:
        return False
    if field[player.y][player.x] != d.CHAR_BARRIER:
        return False
    damage = barrier_lp_damage(player)
    if damage == 0:
        return False
    player.lp -= damage
    return True


def update_entities(
    move_direction: d.Point,
    field: List[List[str]],
    player: d.Player,
    entities: List[d.Entity],
    sword_uses: int = d.SWORD_USES,
    respawn_point: Optional[d.Point] = None,
    stage_num: int = 1,
) -> UpdateResult:
    """Run one legacy single-floor turn for direct module callers.

    Player sessions use ``game_engine.run_game()`` for every stage. This
    helper preserves the earlier low-level ``arlq.arlq`` API, including the
    four-value ``UpdateResult`` unpacking contract.
    """
    events = TurnEvents()
    effect = None
    tribes_to_be_respawned = []
    message = None
    previous = (player.x, player.y)
    wall_result = move_player(
        move_direction, field, player, PLAYER_PASSABLE_CELLS
    )

    if wall_result is not None:
        events.wall = wall_result

    # Caltrop damage
    if field[player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= d.CALTROP_LP_DAMAGE
        field[player.y][player.x] = d.CHAR_FLOOR
    if apply_barrier_damage(field, player, previous):
        message = (MESSAGE_TICKS, trp("-- The barrier burns you.", 5))

    # Find encountered entity
    enc_entity_infos: List[Tuple[int, d.Entity]] = []
    for i, e in enumerate(entities):
        if not isinstance(e, d.Player):
            dx = abs(e.x - player.x)
            dy = abs(e.y - player.y)
            if dx == 0 and dy == 0:
                enc_entity_infos.append((i, e))
    assert len(enc_entity_infos) <= 1
    contact_happened = bool(enc_entity_infos)

    # Actions (combats, state changes, etc)
    for eei, ee in enc_entity_infos:
        if isinstance(ee, d.Treasure):
            t: d.Treasure = ee
            collected = t.unlocked
            events.contact = ContactEvent("treasure", t.unlock_key, collected=collected)
            if collected:
                message = (10, trp(">> Treasure chest obtained! <<", 9))
                del entities[eei]
                effect = d.EFFECT_GOT_TREASURE
                player.treasure_collected = True
        elif isinstance(ee, d.Companion):
            c: d.Companion = ee
            c.revealed = True

            del entities[eei]

            events.contact = ContactEvent("companion", c.tribe.char)

            player.companion = c
            player.karma = 0
            if c.tribe.char != "l" and player.elf_stage_flags & d.ELF_STAGE_S_FLAG:
                c.durability = math.ceil(
                    c.tribe.durability * d.SYLVAN_COMPANION_DURATION_MULTIPLIER
                )

            event_message = c.tribe.event_message
            if event_message:
                message = (
                    MESSAGE_TICKS,
                    trp(event_message, c.tribe.event_message_importance),
                )
        elif isinstance(ee, d.Monster):
            m: d.Monster = ee
            if player.item == d.ITEM_SWORD_CURSED:
                player.lp -= d.CURSED_SWORD_LP_COST
            if m.tribe.is_elf:
                m.revealed = True
            else:
                player.known_monsters.add(d.monster_type_key(m))
            contact_key = (0, m.x, m.y)

            # Stage 2's H is a passive decoy: reveal it, but never fight,
            # remove, or respawn from it.
            if m.tribe.char == "H" and stage_num == 2:
                m.revealed = True
                player.known_monsters.add(d.monster_type_key(m))
                events.contact = ContactEvent("monster", "H", outcome="passive")
                message = (
                    MESSAGE_TICKS,
                    trp(
                        "-- It looks powerful, but doesn't seem to intend to attack you.",
                        3,
                    ),
                )
                player.last_contact_monster = contact_key
                continue

            # High Elf is a Stage 3-style gatekeeper. The first refusal only
            # shows a message; later refusals send the player elsewhere.
            if m.tribe.char == "H":
                events.contact = ContactEvent("monster", "H", outcome="refused")
                if player.high_elf_refused:
                    player.x, player.y = find_random_place(entities, field, distance=2)
                    message = (
                        MESSAGE_TICKS,
                        trp("-- You were sent somewhere else.", 3),
                    )
                else:
                    message = (
                        MESSAGE_TICKS,
                        trp("-- The High Elf seems uninterested in you.", 3),
                    )
                    player.high_elf_refused = True
                player.last_contact_monster = contact_key
                continue

            player_attack = d.current_player_attack(player)
            monster_id = d.monster_type_key(m)

            if player_attack < d.monster_level(m):
                # Losing twice in a row to the very same monster (no other
                # monster contact in between) means it is blocking the only
                # way through: send the player somewhere random instead of
                # back to the checkpoint, so a too-strong monster on a bridge
                # corridor cannot soft-lock the map.
                if player.last_contact_monster == contact_key:
                    player.x, player.y = find_random_place(
                        entities, field, distance=2, far_from=(m.x, m.y)
                    )
                    message = (
                        MESSAGE_TICKS,
                        trp("-- Respawned to a random location.", 5),
                    )
                else:
                    if respawn_point is None:
                        player.x, player.y = find_random_place(
                            entities, field, distance=2, far_from=(m.x, m.y)
                        )
                    else:
                        player.x, player.y = respawn_point
                    message = (MESSAGE_TICKS, trp("-- Respawned!", 5))
                events.contact = ContactEvent(
                    "monster",
                    monster_id,
                    outcome="lose",
                    respawn_to=(player.x, player.y),
                )
                old_item, old_source = player.item, player.item_taken_from
                d.clear_player_item(player)
                if old_item:
                    events.expired.append(
                        ExpiredEvent(
                            "item_expired", item=old_source, reason="lost_on_defeat"
                        )
                    )
                d.apply_respawn_penalty(player)
            else:
                del entities[eei]

                events.contact = ContactEvent("monster", monster_id, outcome="win")

                if (
                    d.monster_level(m) > 0
                    and m.tribe.effect != d.EFFECT_UNLOCK_TREASURE
                ):
                    tribes_to_be_respawned.append(m.tribe.char)

                effect = m.tribe.effect
                d.grant_defeat_level(player, effect)
                activate_mimic_for_defeat(m, entities)
                if effect == d.EFFECT_UNLOCK_TREASURE:
                    player.boss_defeated = True
                    unlock_treasure_for_defeat(m, entities)
                elif effect == d.EFFECT_CALTROP_SPREAD:
                    spread_caltrops(field, (player.x, player.y), entities)
                elif effect == d.EFFECT_ROCK_SPREAD:
                    for x, y in iterate_offsets(
                        player.x,
                        player.y,
                        d.ROCK_SPREAD_OFFSETS,
                        except_for_entities=entities,
                    ):
                        if field[y][x] == d.CHAR_FLOOR:
                            field[y][x] = d.CHAR_WALL

                d.apply_feed(player, m.tribe.feed)

                player.karma += 1

                old_item, old_source = player.item, player.item_taken_from
                d.take_monster_item(player, m.tribe.item, m.tribe.char, sword_uses)
                if old_item:
                    events.expired.append(
                        ExpiredEvent(
                            "item_expired", item=old_source, reason="overwritten"
                        )
                    )

                event_message = m.tribe.event_message
                if event_message:
                    message = (
                        MESSAGE_TICKS,
                        trp(event_message, m.tribe.event_message_importance),
                    )

            player.last_contact_monster = contact_key

    reveal_entities_in_fov(player, entities)

    if (
        player.companion is not None
        and player.karma >= player.companion.durability
    ):
        candidate_message = trp("-- The companion vanishes.", 3)
        if prefer_event_message(
            message[1] if message is not None else None, candidate_message
        ) == candidate_message:
            message = (MESSAGE_TICKS, candidate_message)
        char = player.companion.tribe.char
        events.expired.append(ExpiredEvent("companion_departed", event_id=char))
        tribes_to_be_respawned.append(char)
        player.companion = None

    return UpdateResult(
        effect, tribes_to_be_respawned, message, contact_happened, events
    )


def last_seed_path() -> Path:
    return Path(user_cache_dir("arlq")) / "last-seed"


def last_trace_path() -> Path:
    return Path(user_cache_dir("arlq")) / "last-trace.json"


def remember_seed(stage: int, seed: int) -> None:
    try:
        path = last_seed_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{stage} {seed}\n", encoding="utf-8")
    except OSError as error:
        print(f"Warning: cannot save game seed: {error}", file=sys.stderr)


def read_last_seed() -> Tuple[int, int]:
    path = last_seed_path()
    try:
        parts = path.read_text(encoding="utf-8").split()
    except OSError as error:
        raise ValueError(f"cannot read rematch seed from {path}: {error}") from error
    if len(parts) != 2:
        raise ValueError(f"invalid rematch stage or seed in {path}")
    try:
        stage, seed = int(parts[0]), int(parts[1])
    except ValueError as error:
        raise ValueError(f"invalid rematch stage or seed in {path}") from error
    if stage not in d.PUBLIC_STAGE_NUMBERS and stage != 6:
        raise ValueError(f"invalid rematch stage or seed in {path}")
    return stage, seed


def run_game(
    ui,
    seed_str: str,
    stage_num: int,
    debug_show_entities: bool = False,
    seed_value: Optional[int] = None,
    trace: Optional[TraceRecorder] = None,
    config: Optional[GameConfig] = None,
) -> None:
    if config is None:
        config = GameConfig()
    if stage_num == 0:  # if stage is not selected yet
        r = ui.select_stage(d.PUBLIC_STAGE_NUMBERS)
        if r == 0:
            return
        stage_num = r
        # seed_str embeds the stage number (see generate_seed_string()); it
        # was built before interactive selection, so it still shows the
        # placeholder stage 0. Patch it in place so both the in-game "SEED:"
        # display and a recorded trace's params.seed show the stage actually
        # played.
        parts = seed_str.split("-")
        if len(parts) == 4:
            parts[2] = str(stage_num)
            seed_str = "-".join(parts)

    if trace is not None:
        trace.params["stage"] = stage_num
        trace.params["seed"] = seed_str

    if seed_value is not None:
        remember_seed(stage_num, seed_value)

    stage_module = import_module(f".{GAME_ENGINE_MODULE}", package=__package__)
    if stage_num in (1, 2, 4, 6):
        stage_module.run_game(
            ui,
            seed_str,
            debug_show_entities=debug_show_entities,
            trace=trace,
            config=config,
            stage_num=stage_num,
        )
    else:
        stage_module.run_game(
            ui,
            seed_str,
            debug_show_entities=debug_show_entities,
            trace=trace,
            config=config,
        )


def generate_seed_string(args):
    flag_str = ""
    if args.large_torch:
        flag_str += "T"
    elif args.small_torch:
        flag_str += "t"
    if args.narrower_corridors:
        flag_str += "n"
    return f"v{__version__}-{flag_str}-{args.stage}-{args.seed}"


def parse_seed_string(args, seed_str, enforce_version: bool = True):
    parts = seed_str.split("-")
    if len(parts) != 4:
        exit(
            "Error: Seed string format is invalid. Expected format: v<version>-<flags>-<stage>-<seed>"
        )

    version_part, flag_str, stage_str, seed_value_str = parts

    if not version_part.startswith("v"):
        exit("Error: Seed string must start with 'v'.")
    version = version_part[1:]
    if enforce_version and version != __version__:
        exit("Error: Seed string version does not match game version.")

    # Restore flags: set booleans based on whether they are specified.
    # Check that -T and -t flags are mutually exclusive.
    if "T" in flag_str and "t" in flag_str:
        exit(
            "Error: Both large torch and small torch flags are present in seed string."
        )
    elif "T" in flag_str:
        args.large_torch = True
        args.small_torch = False
    elif "t" in flag_str:
        args.large_torch = False
        args.small_torch = True
    else:
        args.large_torch = False
        args.small_torch = False

    args.narrower_corridors = "n" in flag_str

    try:
        args.stage = int(stage_str)
    except ValueError:
        exit("Error: Stage value in seed string is not a valid integer.")
    if args.stage not in d.PUBLIC_STAGE_NUMBERS:
        exit("Error: Stage value in seed string must be 1, 2, 3, or 4.")

    try:
        args.seed = int(seed_value_str)
    except ValueError:
        exit("Error: Seed value in seed string is not a valid integer.")


def main():
    """Run the game from command-line arguments."""
    from .cli import main as cli_main

    cli_main()


def main_cli():
    from .cli import main as cli_main

    cli_main(terminal_only=True)


if __name__ == "__main__":
    main()
