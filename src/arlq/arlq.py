from typing import List, Set, Tuple, Optional

import argparse
import math
import sys
import time

from .__about__ import __version__

from .utils import rand
from . import defs as d


def generate_maze(width: int, height: int) -> Tuple[List[d.Edge], d.Point, d.Point]:
    # Returns a list of neighboring points given a point p
    def neighbor_points(p):
        x, y = p
        return [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]

    # Returns True if the given point p is within the bounds of the maze
    def is_within_bounds(p):
        return 0 <= p[0] < width and 0 <= p[1] < height

    # Initialize the maze generation process
    unconnected_point_set = set((x, y) for y in range(height) for x in range(width))
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
    while len(done_points) < width * height:
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


def spawn_monsters(
    entities: List[d.Entity],
    field: List[List[str]],
    torched: List[List[int]],
    spawn_configs: List[d.MonsterSpawnConfig],
) -> None:
    """
    Spawns monsters on the field based on the provided spawn configurations.

    Args:
        entities: List of current game entities.
        field: 2D list representing the game field.
        torched: 2D list tracking visited or modified locations on the field.
        spawn_configs: List of MonsterSpawnConfig instances for the current stage.
    """
    for config in spawn_configs:
        population = config.population
        # If population is a float, treat it as a probability for spawning one monster.
        if isinstance(population, float):
            population = 1 if rand.randrange(100) / 100 < population else 0
        for _ in range(population):
            x, y = find_random_place(entities, field, distance=2)
            m = d.Monster(x, y, config.tribe)
            entities.append(m)
            # Mark the new monster's position as unvisited (or hidden).
            torched[y][x] = 0


def respawn_monster(
    entities: List[d.Entity],
    field: List[List[str]],
    torched: List[List[int]],
    spawn_configs: List[d.MonsterSpawnConfig],
) -> None:
    """
    Respawns a single monster on the field based on the spawn configurations.

    Args:
        entities: List of current game entities.
        field: 2D list representing the game field.
        torched: 2D list tracking visited or modified locations on the field.
        spawn_configs: List of MonsterSpawnConfig instances for the current stage.
    """
    # Build a list of tribe characters that have a population of at least 2.
    valid_chars = []
    for config in spawn_configs:
        if config.population >= 2:
            valid_chars.append(config.tribe.char)
    # Choose a random tribe character from the valid ones.
    chosen_char = rand.choice(valid_chars)
    for config in spawn_configs:
        if config.tribe.char == chosen_char:
            x, y = find_random_place(entities, field, distance=2)
            m = d.Monster(x, y, config.tribe)
            entities.append(m)
            # Mark the new monster's position as unvisited (or hidden).
            torched[y][x] = 0
            break


def create_field(
    corridor_h_width: int, corridor_v_width: int, wall_char: str
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
    edges, first_p, last_p = generate_maze(d.TILE_NUM_X, d.TILE_NUM_Y)
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

    if player.companion == d.COMPANION_OCULAR:
        torch_radius += d.OCULAR_TORCH_EXTENSION

    for x, y in iterate_ellipse_points(player.x, player.y, torch_radius, d.TORCH_WIDTH_EXPANSION_RATIO):
        torched[y][x] = 1

    return torched


def update_entities(
    move_direction: d.Point,
    field: List[List[str]],
    player: d.Player,
    entities: List[d.Entity],
    encountered_types: Set[str],
) -> Tuple[Optional[str], Optional[Tuple[int, str]]]:
    event = None
    message = None

    # player move
    dx, dy = move_direction

    if 0 <= (nx := player.x + dx) < d.FIELD_WIDTH and 0 <= (ny := player.y + dy) < d.FIELD_HEIGHT:
        c = field[ny][nx]
        if c in (" ", d.CHAR_CALTROP):
            player.x, player.y = nx, ny
        elif (
            player.companion == d.COMPANION_PEGASUS
            and 0 <= (n2x := player.x + dx * d.PEGASUS_STEP_X) < d.FIELD_WIDTH
            and 0 <= (n2y := player.y + dy * d.PEGASUS_STEP_Y) < d.FIELD_HEIGHT
            and field[n2y][n2x] in (" ", d.CHAR_CALTROP)
        ):
            player.x, player.y = n2x, n2y
            player.karma += 1
        elif player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) and c == d.WALL_CHAR:
            # break the wall
            player.x, player.y = nx, ny
            field[player.y][player.x] = " "
            player.item = ""
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

    # Actions & events (combats, state changes, etc)
    for eei, ee in enc_entity_infos:
        if isinstance(ee, d.Treasure):
            t: d.Treasure = ee
            if t.encounter_type in encountered_types:
                message = (10, ">> Treasures collected! <<")
                del entities[eei]
                event = d.EVENT_GOT_TREASURE
        elif isinstance(ee, d.Monster):
            m: d.Monster = ee
            encountered_types.add(m.tribe.char)
            player_attack = d.player_attack_by_level(player)

            if player_attack < m.tribe.level:
                player.x, player.y = find_random_place(entities, field, distance=2)
                player.item = ""
                player.item_taken_from = ""
                player.lp -= d.LP_RESPAWN_COST
                player.lp = max(d.LP_RESPAWN_MIN, min(player.lp, d.LP_INIT))
                message = (3, "-- Respawned!")
            else:
                event = m.tribe.effect
                player.level += 1
                if event == d.EFFECT_SPECIAL_EXP:
                    player.level += 9
                elif event == d.EFFECT_UNLOCK_TREASURE:
                    encountered_types.add(d.CHAR_TREASURE + m.tribe.char)  # Unlock the treasure
                elif event == d.EFFECT_CALTROP_SPREAD:
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
                elif event == d.EFFECT_ROCK_SPREAD:
                    for x, y in iterate_offsets(
                        player.x, player.y, d.ROCK_SPREAD_OFFSETS, except_for_entities=entities
                    ):
                        if field[y][x] == " ":
                            field[y][x] = d.WALL_CHAR

                player.lp = max(1, min(d.LP_MAX, player.lp + m.tribe.feed))

                if m.tribe.companion:
                    player.companion = m.tribe.companion
                    player.karma = 0
                else:
                    player.karma += 1

                del entities[eei]
                player.item = m.tribe.item
                player.item_taken_from = m.tribe.char

                if player.item == d.ITEM_SWORD_CURSED:
                    player.lp = (player.lp + 1) // 2

                if m.tribe.event_message:
                    message = (3, m.tribe.event_message)

    if player.companion == d.COMPANION_NOMICON:
        for eei, ee in sur_entity_infos:
            if isinstance(ee, d.Monster):
                m: d.Monster = ee
                if m.tribe.char not in encountered_types:
                    encountered_types.add(m.tribe.char)
                    player.karma += 1

    if player.companion != "":
        if player.karma >= d.COMPANION_KARMA_LIMIT:
            message = (3, "-- The companion vanishes.")
            player.companion = ""

    return event, message


def run_game(ui, seed_str: str, stage_num: int, debug_show_entities: bool = False) -> None:
    show_entities = debug_show_entities

    if stage_num == 0:  # if stage is not selected yet
        r = ui.select_stage()
        if r == 0:
            return
        stage_num = r

    # Configuration
    stage_config = d.STAGE_TO_MONSTER_SPAWN_CONFIGS[stage_num - 1]

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
    for ms in stage_config.init_spawn_cfg:
        mt = ms.tribe
        if mt.effect == d.EFFECT_UNLOCK_TREASURE:
            assert ms.population == 1
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
    spawn_monsters(entities, field, torched, stage_config.init_spawn_cfg)

    # Initialize stage state
    torch_radius = d.TORCH_RADIUS
    hours: int = -1
    move_direction = None

    message: Tuple[int, str] = (-1, "")

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
        )

        move_direction = ui.input_direction()
        if move_direction is None:
            return

        # Player move, encountering, etc.
        e, m = update_entities(move_direction, field, player, entities, encountered_types)
        if m is not None:
            message = m

        if e == d.EVENT_GOT_TREASURE:
            break

        if hours % stage_config.respawn_rate == 0:
            respawn_monster(entities, field, torched, stage_config.respawn_cfg)

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
        )

        c = ui.input_alphabet()
        if c is None:
            return
        elif c == "m":
            show_entities = not show_entities
        elif c == "s":
            message = (-1, f"SEED: {seed_str}")


def generate_seed_string(args):
    flag_str = ""
    if args.large_field:
        flag_str += "F"
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
    args.large_field = "F" in flag_str

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

    args.stage = int(stage_str)

    try:
        args.seed = int(seed_value_str)
    except ValueError:
        exit("Error: Seed value in seed string is not a valid integer.")


def main():
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )

    parser.add_argument("--stage", action="store", type=int, default=0, help="Stage (1 or 2).")

    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)

    parser.add_argument("-F", "--large-field", action="store_true", help="Large field.")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    g.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")

    parser.add_argument("--seed", action="store", type=int, help="Seed value")
    parser.add_argument("--curses", action="store_true", help="Use curses as UI framework.")
    parser.add_argument("--debug-show-entities", action="store_true", help="Debug option.")

    args = parser.parse_args()

    if args.seed is not None:
        # Check if any conflicting flags are provided
        if any([args.stage, args.large_field, args.large_torch, args.small_torch, args.narrower_corridors]):
            exit("Error: option --seed is mutually exclusive to options --stage, -F, -T, -t, -n")
        parse_seed_string(args, args.seed)
    else:
        args.seed = int(time.time()) % 100000

    if args.large_field:
        d.TILE_NUM_Y += 1
        d.FIELD_HEIGHT = (d.TILE_HEIGHT + 1) * d.TILE_NUM_Y + 1

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
            run_game(ui, seed_str, args.stage, args.debug_show_entities)

        try:
            curses.wrapper(curses_main)
        except TerminalSizeSmall as e:
            sys.exit("Error: " + str(e))
    else:
        from .pygame_funcs import PygameUI

        ui = PygameUI()
        run_game(ui, seed_str, args.stage, args.debug_show_entities)


if __name__ == "__main__":
    main()
