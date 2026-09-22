from typing import Container, Dict, List, Set, Tuple, Optional

from collections import Counter
import argparse
from dataclasses import dataclass
import math
import sys
import time
from pathlib import Path

from appdirs import user_cache_dir

from .__about__ import __version__

from .utils import rand
from . import defs as d
from .i18n import t as tr, set_language, get_language
from .trace import DIR_TO_KEY, ReplayUI, TraceRecorder, default_replay_output_path, load_trace

MESSAGE_TICKS = 8


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


def tick_message(message: Tuple[int, str]) -> Tuple[int, str]:
    ticks, text = message
    if ticks < 0:
        return message
    ticks -= 1
    if ticks < 0:
        return (-1, "")
    return (ticks, text)


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
        unconnected_nps = [np for np in nps if is_within_bounds(np) and np in unconnected_point_set]

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


def find_random_place(entities: List[d.Entity], field: List[List[str]], distance: int = 1) -> d.Point:
    places = [(e.x, e.y) for e in entities]
    while True:
        x = rand.randrange(d.FIELD_WIDTH - 2) + 1
        y = rand.randrange(d.FIELD_HEIGHT - 2) + 1
        if all(
            c == " " for c in field[y][x - 1 : x + 1 + 1]
        ) and not any(  # both left and right cells are spaces (not walls)
            abs(p[0] - x) <= distance and abs(p[1] - y) <= distance for p in places
        ):
            return x, y


def spawn_at(
    entities: List[d.Entity],
    x: int,
    y: int,
    tribe: d.Tribe,
    empowered: int = 1,
    origin_floor: Optional[int] = None,
) -> d.Entity:
    if isinstance(tribe, d.MonsterTribe):
        entity: d.Entity = d.Monster(x, y, tribe, empowered=empowered)
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
            x, y = find_random_place(entities, field, distance=2)
            spawn_at(entities, x, y, config.tribe, empowered=config.empowered)


def respawn_entity(
    tribe: d.Tribe,
    entities: List[d.Entity],
    field: List[List[str]],
) -> d.Entity:
    """Place one monster or companion."""
    x, y = find_random_place(entities, field, distance=2)
    return spawn_at(entities, x, y, tribe)


def create_field(
    corridor_h_width: int,
    corridor_v_width: int,
    wall_char: str,
    excluded_tile: Optional[d.Point] = None,
    margin_x: int = 0,
) -> Tuple[List[List[str]], d.Point, d.Point]:
    def find_empty_cell(field: List[List[str]], left_top: d.Point, right_bottom: d.Point) -> d.Point:
        assert left_top[0] < right_bottom[0]
        assert left_top[1] < right_bottom[1]

        while True:
            x = rand.randrange(right_bottom[0] - left_top[0]) + left_top[0]
            y = rand.randrange(right_bottom[1] - left_top[1]) + left_top[1]
            if field[y][x] == " ":
                return x, y

    # margin_x walls off that many tile columns on each of the left and
    # right edges, leaving a narrower maze centered in the same field size.
    tile_num_x = d.TILE_NUM_X - 2 * margin_x

    field: List[List[str]] = [[" " for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]

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
    first_p = (first_p[0] + margin_x, first_p[1])
    last_p = (last_p[0] + margin_x, last_p[1])
    for edge in edges:
        (x1, y1), (x2, y2) = sorted(edge)
        assert x1 <= x2
        assert y1 <= y2
        x1, x2 = x1 + margin_x, x2 + margin_x
        if y1 == y2:
            offset = rand.randrange(d.TILE_HEIGHT + 1 - corridor_h_width) + 1
            for y in range(corridor_h_width):
                field[y1 * (d.TILE_HEIGHT + 1) + offset + y][x2 * (d.TILE_WIDTH + 1)] = " "
        else:
            assert x1 == x2
            offset = rand.randrange(d.TILE_WIDTH + 1 - corridor_v_width) + 1
            for x in range(corridor_v_width):
                field[y2 * (d.TILE_HEIGHT + 1)][x1 * (d.TILE_WIDTH + 1) + offset + x] = " "

    # The sealed tile can interrupt a direct route between its neighbors.
    # Rust's stage 3 adds a short bypass on the adjacent row at an outer edge.
    if excluded_tile is not None:
        island_x, island_y = excluded_tile
        if 0 < island_x < d.TILE_NUM_X - 1:
            bypass_y = 1 if island_y == 0 else d.TILE_NUM_Y - 2 if island_y == d.TILE_NUM_Y - 1 else None
            if bypass_y is not None:
                offset = rand.randrange(d.TILE_HEIGHT + 1 - corridor_h_width) + 1
                for y in range(corridor_h_width):
                    row = bypass_y * (d.TILE_HEIGHT + 1) + offset + y
                    field[row][island_x * (d.TILE_WIDTH + 1)] = " "
                    field[row][(island_x + 1) * (d.TILE_WIDTH + 1)] = " "

    # Wall off the margin columns entirely so they read as removed, rather
    # than as a disconnected strip of tiny rooms.
    if margin_x > 0:
        left_edge = margin_x * (d.TILE_WIDTH + 1)
        right_edge = (d.TILE_NUM_X - margin_x) * (d.TILE_WIDTH + 1)
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


def update_torched(torched: List[List[int]], added: List[List[int]]) -> None:
    for y in range(d.FIELD_HEIGHT):
        for x in range(d.FIELD_WIDTH):
            torched[y][x] += added[y][x]


def iterate_ellipse_points(
    center_x: int,
    center_y: int,
    radius: int,
    width_expansion_ratio: float,
    except_for_center: bool = False,
    except_for_entities: Optional[List[d.Entity]] = None,
):
    entity_coordinates = set((e.x, e.y) for e in except_for_entities) if except_for_entities else set()
    for dy in range(-radius, radius + 1):
        y = center_y + dy
        if 0 <= y < d.FIELD_HEIGHT:
            w = int(math.sqrt((radius * width_expansion_ratio) ** 2 - dy**2) + 0.5)
            for dx in range(-w, w + 1):
                x = center_x + dx
                if 0 <= x < d.FIELD_WIDTH:
                    if except_for_center and y == center_y and x == center_x:
                        continue
                    if (x, y) not in entity_coordinates:
                        yield x, y


def spread_caltrops(field: List[List[str]], origin: d.Point, entities: List[d.Entity]) -> None:
    ox, oy = origin
    for x, y in iterate_ellipse_points(
        ox,
        oy,
        d.CALTROP_SPREAD_RADIUS,
        d.CALTROP_WIDTH_EXPANSION_RATIO,
        except_for_center=True,
        except_for_entities=entities,
    ):
        if (x + y) % 2 == 0 and field[y][x] in (" ", d.WALL_CHAR):
            field[y][x] = d.CHAR_CALTROP


def iterate_offsets(
    center_x: int, center_y: int, offsets: List[d.Point], except_for_entities: Optional[List[d.Entity]] = None
):
    entity_coordinates = set((e.x, e.y) for e in except_for_entities) if except_for_entities else set()
    for dx, dy in offsets:
        x = center_x + dx
        y = center_y + dy
        if 0 <= x < d.FIELD_WIDTH and 0 <= y < d.FIELD_HEIGHT:
            if (x, y) not in entity_coordinates:
                yield x, y


def get_torched(player: d.Player, torch_radius: int) -> List[List[int]]:
    torched: List[List[int]] = [[0 for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]

    has_ocular = player.companion is not None and player.companion.tribe.char == "o"
    if player.stage3_spores:
        torch_radius = 2 if has_ocular else 1
    elif has_ocular:
        torch_radius += d.OCULAR_TORCH_EXTENSION

    for x, y in iterate_ellipse_points(player.x, player.y, torch_radius, d.FOV_WIDTH_EXPANSION_RATIO):
        torched[y][x] = 1

    return torched


def unlock_treasure_for_defeat(
    monster: d.Monster,
    unlocked_treasures: Set[str],
) -> None:
    """Record the treasure unlocked by defeating a monster."""
    treasure_key = monster.tribe.treasure_key
    if treasure_key is None:
        return
    unlocked_treasures.add(treasure_key)


def reveal_entities_in_fov(
    player: d.Player,
    entities: List[d.Entity],
    torch_radius: int = d.TORCH_RADIUS,
) -> None:
    """Reveal every monster currently inside the player's FOV."""
    if player.companion is None or player.companion.tribe.char != "n":
        return
    torched = get_torched(player, torch_radius)
    for entity in entities:
        if not (0 <= entity.y < d.FIELD_HEIGHT and 0 <= entity.x < d.FIELD_WIDTH):
            continue
        if not torched[entity.y][entity.x]:
            continue
        if isinstance(entity, d.Monster):
            player.known_monsters.add(d.monster_type_key(entity))


def move_player(
    direction: d.Point,
    field: List[List[str]],
    player: d.Player,
    passable_cells: Container[str],
) -> Optional[Dict[str, object]]:
    """Move the player and return a traceable wall-interaction result.

    A normal step has no wall result. Blocked movement, a Pegasus phase, and
    a sword-broken wall return the event recorded by the gameplay trace.
    """
    dx, dy = direction
    nx, ny = player.x + dx, player.y + dy
    height = len(field)
    width = len(field[0]) if field else 0

    if not (0 <= ny < height and 0 <= nx < width):
        return {"result": "blocked"}

    cell = field[ny][nx]
    if cell in passable_cells:
        player.x, player.y = nx, ny
        return None

    if player.companion is not None and player.companion.tribe is d.CHAR_TO_COMPANION_TRIBE["p"]:
        jump_x = player.x + dx * d.PEGASUS_STEP_X
        jump_y = player.y + dy * d.PEGASUS_STEP_Y
        if (
            0 <= jump_y < height
            and 0 <= jump_x < width
            and field[jump_y][jump_x] in (" ", d.CHAR_CALTROP)
        ):
            player.x, player.y = jump_x, jump_y
            player.karma += 1
            return {"result": "pegasus_phase"}
        return {"result": "blocked"}

    if (
        player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED)
        and player.item_uses > 0
        and cell == d.WALL_CHAR
    ):
        player.x, player.y = nx, ny
        field[ny][nx] = " "
        player.item_uses -= 1
        if player.item_uses == 0:
            d.clear_player_item(player)
        return {"result": "sword_break", "item_uses_left": player.item_uses}

    return {"result": "blocked"}


def update_entities(
    move_direction: d.Point,
    field: List[List[str]],
    player: d.Player,
    entities: List[d.Entity],
    unlocked_treasures: Set[str],
    sword_uses: int = d.SWORD_USES,
    respawn_point: Optional[d.Point] = None,
    trace: Optional[TraceRecorder] = None,
) -> Tuple[Optional[str], List[str], Optional[Tuple[int, str]], bool]:
    effect = None
    tribes_to_be_respawned = []
    message = None
    wall_result = move_player(move_direction, field, player, (" ", d.CHAR_CALTROP))

    if trace is not None and wall_result is not None:
        trace.record_wall(wall_result)

    # Caltrop damage
    if field[player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= d.CALTROP_LP_DAMAGE
        field[player.y][player.x] = " "

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
            collected = t.unlock_key in unlocked_treasures
            if trace is not None:
                trace.record_contact({"type": "treasure", "id": t.unlock_key, "collected": collected})
            if collected:
                message = (10, tr(">> Treasure chest obtained! <<"))
                del entities[eei]
                effect = d.EFFECT_GOT_TREASURE
        elif isinstance(ee, d.Companion):
            c: d.Companion = ee
            player.known_companions.add(c.tribe.char)

            del entities[eei]

            if trace is not None:
                trace.record_contact({"type": "companion", "id": c.tribe.char})

            player.companion = c
            player.karma = 0

            event_message = c.tribe.event_message
            if event_message:
                message = (MESSAGE_TICKS, tr(event_message))
        elif isinstance(ee, d.Monster):
            m: d.Monster = ee
            player.known_monsters.add(d.monster_type_key(m))
            contact_key = (0, m.x, m.y)

            # High Elf is a Stage 3-style gatekeeper in Stage 2 as well. It
            # remains in place until the required elf progress is available,
            # and must not establish a respawn checkpoint on contact. The
            # first refusal only shows a message; any later refusal sends the
            # player elsewhere, like repeat contact with the Isolated Elf.
            if m.tribe.char == "H":
                if trace is not None:
                    trace.record_contact({"type": "monster", "id": "H", "outcome": "refused"})
                if player.high_elf_refused:
                    player.x, player.y = find_random_place(entities, field, distance=2)
                    message = (MESSAGE_TICKS, tr("-- Respawned to a random location."))
                else:
                    message = (MESSAGE_TICKS, tr("-- The High Elf does not recognize you yet."))
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
                    player.x, player.y = find_random_place(entities, field, distance=2)
                    message = (MESSAGE_TICKS, tr("-- Respawned to a random location."))
                else:
                    if respawn_point is None:
                        player.x, player.y = find_random_place(entities, field, distance=2)
                    else:
                        player.x, player.y = respawn_point
                    message = (MESSAGE_TICKS, tr("-- Respawned!"))
                if trace is not None:
                    trace.record_contact(
                        {"type": "monster", "id": monster_id, "outcome": "lose", "respawn_to": [player.x, player.y]}
                    )
                old_item, old_source = player.item, player.item_taken_from
                d.clear_player_item(player)
                if trace is not None and old_item:
                    trace.add_expired({"type": "item_expired", "item": old_source, "reason": "lost_on_defeat"})
                d.apply_respawn_penalty(player)
            else:
                del entities[eei]

                if trace is not None:
                    trace.record_contact({"type": "monster", "id": monster_id, "outcome": "win"})

                if d.monster_level(m) > 0 and m.tribe.effect != d.EFFECT_UNLOCK_TREASURE:
                    tribes_to_be_respawned.append(m.tribe.char)

                effect = m.tribe.effect
                d.grant_defeat_level(player, effect)
                if effect == d.EFFECT_UNLOCK_TREASURE:
                    unlock_treasure_for_defeat(m, unlocked_treasures)
                elif effect == d.EFFECT_CALTROP_SPREAD:
                    spread_caltrops(field, (player.x, player.y), entities)
                elif effect == d.EFFECT_ROCK_SPREAD:
                    for x, y in iterate_offsets(
                        player.x, player.y, d.ROCK_SPREAD_OFFSETS, except_for_entities=entities
                    ):
                        if field[y][x] == " ":
                            field[y][x] = d.WALL_CHAR

                d.apply_feed(player, m.tribe.feed)

                player.karma += 1

                old_item, old_source = player.item, player.item_taken_from
                d.take_monster_item(player, m.tribe.item, m.tribe.char, sword_uses)
                if trace is not None and old_item:
                    trace.add_expired({"type": "item_expired", "item": old_source, "reason": "overwritten"})

                event_message = m.tribe.event_message
                if event_message:
                    message = (MESSAGE_TICKS, tr(event_message))

            player.last_contact_monster = contact_key

    reveal_entities_in_fov(player, entities)

    if player.companion is not None and player.karma >= player.companion.tribe.durability:
        message = (MESSAGE_TICKS, tr("-- The companion vanishes."))
        char = player.companion.tribe.char
        if trace is not None:
            trace.add_expired({"type": "companion_departed", "id": char})
        tribes_to_be_respawned.append(char)
        player.companion = None

    return effect, tribes_to_be_respawned, message, contact_happened


def last_seed_path() -> Path:
    return Path(user_cache_dir("arlq")) / "last-seed"


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
    if stage not in (1, 2, 3):
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
    show_entities = debug_show_entities

    if stage_num == 0:  # if stage is not selected yet
        r = ui.select_stage()
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

    if stage_num == 3:
        from .stage3 import run_game as run_stage3

        run_stage3(ui, seed_str, debug_show_entities, trace=trace, config=config)
        return

    # Configuration
    spawn_config = d.STAGE_TO_SPAWN_CONFIGS[stage_num - 1]

    # Initialize field
    margin_x = d.STAGE1_COLUMN_MARGIN if stage_num == 1 else 0
    field, first_p, last_p = create_field(
        config.corridor_h_width,
        config.corridor_v_width,
        d.WALL_CHAR,
        margin_x=margin_x,
    )

    # Initialize view/ui components
    cur_torched: List[List[int]] = [[0 for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]
    torched: List[List[int]] = [[0 for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]

    # Initialize entities
    entities: List[d.Entity] = []

    # 1. treasure
    treasure_count = 0
    for sc in spawn_config:
        if isinstance(sc.tribe, d.MonsterTribe):
            mt: d.MonsterTribe = sc.tribe
            if mt.effect == d.EFFECT_UNLOCK_TREASURE:
                assert sc.population == 1
                assert treasure_count == 0
                treasure_count += 1
                x, y = last_p[0], last_p[1]
                treasure: d.Treasure = d.Treasure(x, y, mt.treasure_key)
                entities.append(treasure)
    assert treasure_count == 1

    # 2. player
    player: d.Player = d.Player(first_p[0], first_p[1], 1, d.LP_INIT)
    entities.append(player)

    # 3. monsters
    spawn_entities(entities, field, spawn_config)

    # Initialize stage state
    torch_radius = config.torch_radius
    hours: int = -1
    move_direction = None

    message: Tuple[int, str] = (-1, "")
    respawn_queue: Counter[str] = Counter()
    checkpoint = (player.x, player.y)

    while True:
        # Starvation check
        if player.lp <= 0:
            message = (-1, tr(">> Collapsed from hunger! <<"))
            if trace is not None:
                trace.set_outcome("lose")
            break

        # Update view / auto mapping
        cur_torched = get_torched(player, torch_radius)
        update_torched(torched, cur_torched)

        # Show the field
        message = tick_message(message)
        show_entities = show_entities or getattr(ui, "map_mode", False)
        ui.draw_stage(
            hours=hours,
            player=player,
            entities=entities,
            field=field,
            cur_torched=cur_torched,
            torched=torched,
            known_types=player.known_monsters | player.known_companions,
            show_entities=show_entities,
            stage_num=stage_num,
            message=message[1],
            checkpoint=checkpoint,
            unlocked_treasures=player.unlocked_treasures,
        )

        move_direction = ui.input_direction()
        if move_direction is None:
            if trace is not None:
                trace.record_quit()
                trace.set_outcome("unfinished" if getattr(ui, "ran_dry", False) else "quit")
            return
        if move_direction == (0, 0):
            continue

        if trace is not None:
            key = DIR_TO_KEY.get(move_direction)
            if key is None:
                raise RuntimeError("--trace-record does not support non-cardinal (e.g. diagonal joystick) movement")
            trace.begin_turn(key)

        # Player move, encountering, etc.
        effect, tribes_to_be_respawned, m, _ = update_entities(
            move_direction,
            field,
            player,
            entities,
            player.unlocked_treasures,
            respawn_point=checkpoint,
            trace=trace,
        )
        if m is not None:
            message = m

        if tribes_to_be_respawned:
            checkpoint = (player.x, player.y)

        for t in tribes_to_be_respawned:
            if t not in d.NO_RESPAWN_MONSTERS:
                respawn_queue[t] += 1

        if hours % d.MONSTER_RESPAWN_INTERVAL == 0:
            for t in list(respawn_queue.keys()):
                if respawn_queue[t] > 0:
                    respawned = respawn_entity(d.CHAR_TO_TRIBE[t], entities, field)
                    respawn_queue[t] -= 1
                    if trace is not None:
                        if isinstance(respawned, d.Monster):
                            kind = "monster"
                            rid = d.monster_type_key(respawned)
                        else:
                            assert isinstance(respawned, d.Companion)
                            kind = "companion"
                            rid = respawned.tribe.char
                        trace.add_world_event(
                            {"type": "respawn", "kind": kind, "id": rid, "at": [respawned.x, respawned.y]}
                        )

        if trace is not None:
            trace.set_player(player, stage_num)
            trace.commit_turn()

        if effect == d.EFFECT_GOT_TREASURE:
            if trace is not None:
                trace.set_outcome("win")
            break

        hours += 1
        player.lp -= 1

    # Game over display
    while True:
        ui.draw_stage(
            hours=hours,
            player=player,
            entities=entities,
            field=field,
            cur_torched=cur_torched,
            torched=torched,
            known_types=player.known_monsters | player.known_companions,
            show_entities=show_entities,
            stage_num=stage_num,
            message=message[1],
            extra_keys=True,
            checkpoint=checkpoint,
            unlocked_treasures=player.unlocked_treasures,
        )

        c = ui.input_alphabet()
        if c is None:
            return
        elif c == "m":
            show_entities = True
            if hasattr(ui, "map_mode"):
                ui.map_mode = True
        elif c == "s":
            message = (-1, tr("SEED: {seed_str}").format(seed_str=seed_str))


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
        exit("Error: Seed string format is invalid. Expected format: v<version>-<flags>-<stage>-<seed>")

    version_part, flag_str, stage_str, seed_value_str = parts

    if not version_part.startswith("v"):
        exit("Error: Seed string must start with 'v'.")
    version = version_part[1:]
    if enforce_version and version != __version__:
        exit("Error: Seed string version does not match game version.")

    # Restore flags: set booleans based on whether they are specified.
    # Check that -T and -t flags are mutually exclusive.
    if "T" in flag_str and "t" in flag_str:
        exit("Error: Both large torch and small torch flags are present in seed string.")
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
    if args.stage not in (1, 2, 3):
        exit("Error: Stage value in seed string must be 1, 2, or 3.")

    try:
        args.seed = int(seed_value_str)
    except ValueError:
        exit("Error: Seed value in seed string is not a valid integer.")


def main():
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )

    parser.add_argument("--stage", action="store", type=int, default=0, help="Stage (1, 2, or 3).")

    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)

    g = parser.add_mutually_exclusive_group()
    g.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    g.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")

    parser.add_argument("--seed", action="store", help="Seed value or seed string")
    parser.add_argument("--rematch", action="store_true", help="Replay the last stage with the same seed.")
    parser.add_argument(
        "--terminal", "--curses", dest="terminal", action="store_true",
        help="Use the Blessed terminal UI (--curses is a deprecated alias).",
    )
    parser.add_argument("--debug-show-entities", action="store_true", help="Debug option.")
    parser.add_argument(
        "--lang", choices=["auto", "en", "ja"], default="auto",
        help="UI message language ('auto' detects it from the locale; default: auto).",
    )
    parser.add_argument(
        "--trace-record", metavar="PATH",
        help="Internal/testing: record inputs and results of this session to a gameplay trace JSON file.",
    )
    parser.add_argument(
        "--trace-replay", metavar="PATH",
        help="Internal/testing: replay a gameplay trace JSON file headlessly and write a new trace file.",
    )
    parser.add_argument(
        "--trace-replay-output", metavar="OUT_PATH",
        help="Output path for --trace-replay (default: PATH with '.replay' inserted before its extension).",
    )
    parser.add_argument(
        "--trace-replay-watch", action="store_true",
        help="With --trace-replay, also render the replay to the real UI (pyglet/blessed) as it runs.",
    )

    args = parser.parse_args()

    set_language(args.lang)

    if args.trace_record and args.trace_replay:
        parser.error("--trace-record cannot be combined with --trace-replay")
    if args.trace_replay_output and not args.trace_replay:
        parser.error("--trace-replay-output requires --trace-replay")
    if args.trace_replay_watch and not args.trace_replay:
        parser.error("--trace-replay-watch requires --trace-replay")

    trace_data = None
    if args.trace_replay:
        if args.rematch or args.seed is not None or args.stage or args.large_torch or args.small_torch or args.narrower_corridors:
            parser.error("--trace-replay cannot be combined with --seed, --stage, --rematch, -T, -t, or -n")

        try:
            trace_data = load_trace(Path(args.trace_replay))
        except (OSError, ValueError) as error:
            sys.exit(f"Error: cannot load trace file {args.trace_replay}: {error}")

        if trace_data.get("arlq_version") != __version__:
            print(
                f"Warning: trace was recorded with arlq {trace_data.get('arlq_version')}, "
                f"current version is {__version__}.",
                file=sys.stderr,
            )

        params = trace_data["params"]
        args.seed = params["seed"]
        parse_seed_string(args, args.seed, enforce_version=False)
        if args.lang == "auto":
            set_language(params.get("lang", "auto"))
    else:
        if args.rematch and (args.seed is not None or args.stage):
            parser.error("--rematch cannot be combined with --seed or --stage")

        if args.rematch:
            try:
                args.stage, args.seed = read_last_seed()
            except ValueError as error:
                parser.error(str(error))
        elif args.seed is not None:
            # Check if any conflicting flags are provided
            if any([args.stage, args.large_torch, args.small_torch, args.narrower_corridors]):
                exit("Error: option --seed is mutually exclusive to options --stage, -T, -t, -n")
            if isinstance(args.seed, str) and args.seed.startswith("v"):
                parse_seed_string(args, args.seed)
            else:
                try:
                    args.seed = int(args.seed)
                except (TypeError, ValueError):
                    parser.error("--seed must be an integer or a versioned seed string")
        else:
            args.seed = int(time.time()) % 100000

    rand.set_seed(args.seed)
    seed_str = generate_seed_string(args)
    game_config = game_config_from_args(args)

    trace_recorder: Optional[TraceRecorder] = None
    if args.trace_record or args.trace_replay:
        trace_recorder = TraceRecorder(
            params={
                "stage": args.stage,
                "seed": seed_str,
                "large_torch": args.large_torch,
                "narrower_corridors": args.narrower_corridors,
                "lang": get_language(),
            }
        )

    def play(ui) -> None:
        if args.trace_replay:
            replay_ui = ReplayUI(trace_data["turns"], args.stage, ui if args.trace_replay_watch else None)
            run_game(
                replay_ui,
                seed_str,
                args.stage,
                args.debug_show_entities,
                None,
                trace=trace_recorder,
                config=game_config,
            )
        else:
            run_game(
                ui,
                seed_str,
                args.stage,
                args.debug_show_entities,
                args.seed,
                trace=trace_recorder,
                config=game_config,
            )

    if args.trace_replay and not args.trace_replay_watch:
        play(None)
    elif args.terminal:
        from blessed import Terminal

        from .blessed_funcs import BlessedUI

        term = Terminal()
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            play(BlessedUI(term))
    else:
        from .pyglet_funcs import PygletUI

        play(PygletUI())

    if trace_recorder is not None:
        if args.trace_replay:
            output_path = (
                Path(args.trace_replay_output)
                if args.trace_replay_output
                else default_replay_output_path(Path(args.trace_replay))
            )
        else:
            output_path = Path(args.trace_record)
        trace_recorder.write(output_path)


def main_cli():
    sys.argv.append("--terminal")
    main()


if __name__ == "__main__":
    main()
