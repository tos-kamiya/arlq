from typing import List, Set, Tuple, Optional

from collections import Counter
import argparse
import math
import sys
import time
from pathlib import Path

from appdirs import user_cache_dir

from .__about__ import __version__

from .utils import rand
from . import defs as d

MESSAGE_TICKS = 8


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
    done_points = []
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


def spawn_entities(
    entities: List[d.Entity],
    field: List[List[str]],
    torched: List[List[int]],
    spawn_configs: List[d.SpawnConfig],
) -> None:
    """
    Spawns monsters on the field based on the provided spawn configurations.

    Args:
        entities: List of current game entities.
        field: 2D list representing the game field.
        torched: 2D list tracking visited or modified locations on the field.
        spawn_configs: List of SpawnConfig instances for the current stage.
    """
    for config in spawn_configs:
        population = config.population
        # If population is a float, treat it as a probability for spawning one monster/companion.
        if isinstance(population, float):
            population = 1 if rand.randrange(100) / 100 < population else 0
        for _ in range(population):
            x, y = find_random_place(entities, field, distance=2)
            if isinstance(config.tribe, d.MonsterTribe):
                m = d.Monster(x, y, config.tribe)
                entities.append(m)
            else:
                assert isinstance(config.tribe, d.CompanionTribe)
                c = d.Companion(x, y, config.tribe)
                entities.append(c)
            # Mark the new spawned's position as unvisited (or hidden).
            # A respawn in an already mapped square remains known to the
            # player; Rust's renderer reveals it immediately in that case.


def respawn_entity(
    tribe: d.Tribe,
    entities: List[d.Entity],
    field: List[List[str]],
    torched: List[List[int]],
) -> None:
    """
    Respawns a single monster/companion on the field based on the spawn configurations.

    Args:
        tribe: tribe of entity being respawned.
        entities: existing entities.
        field: 2D list representing the game field.
        torched: 2D list tracking visited or modified locations on the field.
    """
    x, y = find_random_place(entities, field, distance=2)
    if isinstance(tribe, d.MonsterTribe):
        m = d.Monster(x, y, tribe)
        entities.append(m)
    else:
        assert isinstance(tribe, d.CompanionTribe)
        c = d.Companion(x, y, tribe)
        entities.append(c)

    # Mark the new monster's position as unvisited (or hidden).


def create_field(
    corridor_h_width: int,
    corridor_v_width: int,
    wall_char: str,
    excluded_tile: Optional[d.Point] = None,
) -> Tuple[List[List[str]], d.Point, d.Point]:
    def find_empty_cell(field: List[List[str]], left_top: d.Point, right_bottom: d.Point) -> d.Point:
        assert left_top[0] < right_bottom[0]
        assert left_top[1] < right_bottom[1]

        while True:
            x = rand.randrange(right_bottom[0] - left_top[0]) + left_top[0]
            y = rand.randrange(right_bottom[1] - left_top[1]) + left_top[1]
            if field[y][x] == " ":
                return x, y

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
    edges, first_p, last_p = generate_maze(d.TILE_NUM_X, d.TILE_NUM_Y, excluded_tile)
    for edge in edges:
        (x1, y1), (x2, y2) = sorted(edge)
        assert x1 <= x2
        assert y1 <= y2
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


def update_entities(
    move_direction: d.Point,
    field: List[List[str]],
    player: d.Player,
    entities: List[d.Entity],
    encountered_types: Set[str],
    sword_uses: int = d.SWORD_USES,
    respawn_point: Optional[d.Point] = None,
) -> Tuple[Optional[str], List[str], Optional[Tuple[int, str]], bool]:
    effect = None
    tribes_to_be_respawned = []
    message = None

    # player move
    dx, dy = move_direction

    if 0 <= (nx := player.x + dx) < d.FIELD_WIDTH and 0 <= (ny := player.y + dy) < d.FIELD_HEIGHT:
        ch = field[ny][nx]
        if ch in (" ", d.CHAR_CALTROP):
            player.x, player.y = nx, ny
        elif (
            player.companion is not None
            and player.companion.tribe is d.CHAR_TO_COMPANION_TRIBE["p"]
            and 0 <= (n2x := player.x + dx * d.PEGASUS_STEP_X) < d.FIELD_WIDTH
            and 0 <= (n2y := player.y + dy * d.PEGASUS_STEP_Y) < d.FIELD_HEIGHT
            and field[n2y][n2x] in (" ", d.CHAR_CALTROP)
        ):
            player.x, player.y = n2x, n2y
            player.karma += 1
        elif player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) and ch == d.WALL_CHAR:
            # break the wall
            player.x, player.y = nx, ny
            field[player.y][player.x] = " "
            if player.item_uses > 0:
                player.item_uses -= 1
            if player.item_uses <= 0:
                player.item = ""
                player.item_uses = 0
                player.item_taken_from = ""

    # Caltrop damage
    if field[player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= d.CALTROP_LP_DAMAGE
        field[player.y][player.x] = " "

    # Find encountered entity
    enc_entity_infos: List[Tuple[int, d.Entity]] = []
    sur_entity_infos: List[Tuple[int, d.Entity]] = []
    for i, e in enumerate(entities):
        if not isinstance(e, d.Player):
            dx = abs(e.x - player.x)
            dy = abs(e.y - player.y)
            if dx == 0 and dy == 0:
                enc_entity_infos.append((i, e))
            elif dx <= 1 and dy <= 1:
                sur_entity_infos.append((i, e))
    assert len(enc_entity_infos) <= 1
    contact_happened = bool(enc_entity_infos)

    # Actions (combats, state changes, etc)
    for eei, ee in enc_entity_infos:
        if isinstance(ee, d.Treasure):
            t: d.Treasure = ee
            if t.encounter_type in encountered_types:
                message = (10, ">> Treasures collected! <<")
                del entities[eei]
                effect = d.EFFECT_GOT_TREASURE
        elif isinstance(ee, d.Companion):
            c: d.Companion = ee
            encountered_types.add(c.tribe.char)

            del entities[eei]

            player.companion = c
            player.karma = 0

            if c.tribe.event_message:
                message = (MESSAGE_TICKS, c.tribe.event_message)
        elif isinstance(ee, d.Monster):
            m: d.Monster = ee
            encountered_types.add(m.tribe.char)
            player_attack = d.player_attack_by_level(player)

            if player_attack < m.tribe.level:
                if respawn_point is None:
                    player.x, player.y = find_random_place(entities, field, distance=2)
                else:
                    player.x, player.y = respawn_point
                player.item = ""
                player.item_uses = 0
                player.item_taken_from = ""
                player.lp -= d.LP_RESPAWN_COST
                player.lp = max(d.LP_RESPAWN_MIN, min(player.lp, d.LP_INIT))
                message = (MESSAGE_TICKS, "-- Respawned!")
            else:
                del entities[eei]

                if m.tribe.level > 0 and m.tribe.effect != d.EFFECT_UNLOCK_TREASURE:
                    tribes_to_be_respawned.append(m.tribe.char)

                effect = m.tribe.effect
                player.level += 1
                if effect == d.EFFECT_SPECIAL_EXP:
                    player.level += 9
                elif effect == d.EFFECT_UNLOCK_TREASURE:
                    encountered_types.add(d.CHAR_TREASURE + m.tribe.char)  # Unlock the treasure
                elif effect == d.EFFECT_CALTROP_SPREAD:
                    for x, y in iterate_ellipse_points(
                        player.x,
                        player.y,
                        d.CALTROP_SPREAD_RADIUS,
                        d.CALTROP_WIDTH_EXPANSION_RATIO,
                        except_for_center=True,
                        except_for_entities=entities,
                    ):
                        if (x + y) % 2 == 0 and field[y][x] in (" ", d.WALL_CHAR):
                            field[y][x] = d.CHAR_CALTROP
                elif effect == d.EFFECT_ROCK_SPREAD:
                    for x, y in iterate_offsets(
                        player.x, player.y, d.ROCK_SPREAD_OFFSETS, except_for_entities=entities
                    ):
                        if field[y][x] == " ":
                            field[y][x] = d.WALL_CHAR

                player.lp = max(1, min(d.LP_MAX, player.lp + m.tribe.feed))

                player.karma += 1

                player.item = m.tribe.item
                player.item_uses = sword_uses if player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) else 0
                player.item_taken_from = m.tribe.char
                if player.item == d.ITEM_SWORD_CURSED:
                    player.lp = (player.lp * 3 + 3) // 4

                if m.tribe.event_message:
                    message = (MESSAGE_TICKS, m.tribe.event_message)

    if player.companion is not None and player.companion.tribe is d.CHAR_TO_COMPANION_TRIBE["n"]:
        for eei, ee in sur_entity_infos:
            if isinstance(ee, d.Monster):
                m: d.Monster = ee
                if m.tribe.char not in encountered_types:
                    encountered_types.add(m.tribe.char)
                    player.karma += 1

    if player.companion is not None and player.karma >= player.companion.tribe.durability:
        message = (MESSAGE_TICKS, "-- The companion vanishes.")
        char = player.companion.tribe.char
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


def run_game(ui, seed_str: str, stage_num: int, debug_show_entities: bool = False, seed_value: Optional[int] = None) -> None:
    show_entities = debug_show_entities

    if stage_num == 0:  # if stage is not selected yet
        r = ui.select_stage()
        if r == 0:
            return
        stage_num = r

    if seed_value is not None:
        remember_seed(stage_num, seed_value)

    if stage_num == 3:
        from .stage3 import run_game as run_stage3

        run_stage3(ui, seed_str, debug_show_entities)
        return

    # Configuration
    spawn_config = d.STAGE_TO_SPAWN_CONFIGS[stage_num - 1]

    # Initialize field
    field, first_p, last_p = create_field(d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH, d.WALL_CHAR)

    # Initialize view/ui components
    encountered_types: Set[str] = set()
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
                treasure: d.Treasure = d.Treasure(x, y, d.CHAR_TREASURE + mt.char)
                entities.append(treasure)
    assert treasure_count == 1

    # 2. player
    player: d.Player = d.Player(first_p[0], first_p[1], 1, d.LP_INIT)
    entities.append(player)

    # 3. monsters
    spawn_entities(entities, field, torched, spawn_config)

    # Initialize stage state
    torch_radius = d.TORCH_RADIUS
    hours: int = -1
    move_direction = None

    message: Tuple[int, str] = (-1, "")
    respawn_queue = Counter()
    checkpoint = (player.x, player.y)

    while True:
        # Starvation check
        if player.lp <= 0:
            message = (-1, ">> Starved to Death. <<")
            break

        # Update view / auto mapping
        cur_torched = get_torched(player, torch_radius)
        update_torched(torched, cur_torched)

        # Show the field
        if message[0] >= 0:
            remaining_tick = message[0] - 1
            if remaining_tick < 0:
                message = (-1, "")
            else:
                message = (remaining_tick, message[1])
        show_entities = show_entities or getattr(ui, "map_mode", False)
        ui.draw_stage(
            hours,
            player,
            entities,
            field,
            cur_torched,
            torched,
            encountered_types,
            show_entities,
            stage_num=stage_num,
            message=message[1],
            checkpoint=checkpoint,
        )

        move_direction = ui.input_direction()
        if move_direction is None:
            return
        if move_direction == (0, 0):
            continue

        # Player move, encountering, etc.
        effect, tribes_to_be_respawned, m, _ = update_entities(
            move_direction,
            field,
            player,
            entities,
            encountered_types,
            respawn_point=checkpoint,
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
                    respawn_entity(d.CHAR_TO_TRIBE[t], entities, field, torched)
                    respawn_queue[t] -= 1

        if effect == d.EFFECT_GOT_TREASURE:
            break

        hours += 1
        player.lp -= 1

    # Game over display
    while True:
        ui.draw_stage(
            hours,
            player,
            entities,
            field,
            cur_torched,
            torched,
            encountered_types,
            show_entities,
            stage_num=stage_num,
            message=message[1],
            extra_keys=True,
            checkpoint=checkpoint,
        )

        c = ui.input_alphabet()
        if c is None:
            return
        elif c == "m":
            show_entities = True
            if hasattr(ui, "map_mode"):
                ui.map_mode = True
        elif c == "s":
            message = (-1, f"SEED: {seed_str}")


def generate_seed_string(args):
    flag_str = ""
    if args.large_torch:
        flag_str += "T"
    elif args.small_torch:
        flag_str += "t"
    if args.narrower_corridors:
        flag_str += "n"
    return f"v{__version__}-{flag_str}-{args.stage}-{args.seed}"


def parse_seed_string(args, seed_str):
    parts = seed_str.split("-")
    if len(parts) != 4:
        exit("Error: Seed string format is invalid. Expected format: v<version>-<flags>-<stage>-<seed>")

    version_part, flag_str, stage_str, seed_value_str = parts

    if not version_part.startswith("v"):
        exit("Error: Seed string must start with 'v'.")
    version = version_part[1:]
    if version != __version__:
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
    parser.add_argument("--curses", action="store_true", help="Use curses as UI framework.")
    parser.add_argument("--debug-show-entities", action="store_true", help="Debug option.")

    args = parser.parse_args()

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

    if args.large_torch:
        d.TORCH_RADIUS += 1
    elif args.small_torch:
        d.TORCH_RADIUS -= 1

    if args.narrower_corridors:
        d.CORRIDOR_H_WIDTH -= 1
        d.CORRIDOR_V_WIDTH -= 1

    rand.set_seed(args.seed)
    seed_str = generate_seed_string(args)

    if args.curses:
        import curses

        from .curses_funcs import CursesUI, TerminalSizeSmall

        def curses_main(stdscr):
            ui = CursesUI(stdscr)
            run_game(ui, seed_str, args.stage, args.debug_show_entities, args.seed)

        try:
            curses.wrapper(curses_main)
        except TerminalSizeSmall as e:
            sys.exit("Error: " + str(e))
    else:
        if sys.version_info >= (3, 14):
            sys.exit(
                "Pygame GUI is not supported on Python 3.14 yet; "
                "run arlq with Python 3.13 or use --curses."
            )
        from .pygame_funcs import PygameUI

        ui = PygameUI()
        run_game(ui, seed_str, args.stage, args.debug_show_entities, args.seed)


def main_cli():
    sys.argv.append("--curses")
    main()


if __name__ == "__main__":
    main()
