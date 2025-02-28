from typing import List, Set, Tuple

import argparse
import math
import sys
import time

from .__about__ import __version__

from .utils import rand
from . import defs


def gen_maze(width: int, height: int) -> Tuple[List[defs.Edge], defs.Point, defs.Point]:
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


def place_to_tile(x: int, y: int) -> defs.Point:
    return (x - 1) // (defs.TILE_WIDTH + 1), (y - 1) // (defs.TILE_HEIGHT)


def tile_to_place_range(x: int, y: int) -> Tuple[defs.Point, defs.Point]:
    lt = (x * (defs.TILE_WIDTH + 1) + 1, y * (defs.TILE_HEIGHT + 1) + 1)
    rb = (lt[0] + defs.TILE_WIDTH, lt[1] + defs.TILE_HEIGHT)
    return lt, rb


def find_random_place(entities: List[defs.Entity], field: List[List[str]], distance: int = 1) -> defs.Point:
    places = [(e.x, e.y) for e in entities]
    while True:
        x = rand.randrange(defs.FIELD_WIDTH - 2) + 1
        y = rand.randrange(defs.FIELD_HEIGHT - 2) + 1
        if (
            field[y][x] == " "
            and field[y][x + 1] == " "
            and not any(abs(p[0] - x) <= distance and abs(p[1] - y) <= distance for p in places)
        ):
            return x, y


def spawn_monsters(entities: List[defs.Entity], field: List[List[str]]) -> None:
    for tribe in defs.MONSTER_TRIBES:
        p = tribe.population
        if isinstance(p, float):
            p = 1 if rand.randrange(100) / 100 < p else 0
        for _ in range(p):
            x, y = find_random_place(entities, field, distance=2)
            m = defs.Monster(x, y, tribe)
            entities.append(m)


def respawn_monster(entities: List[defs.Entity], field: List[List[str]], torched: List[List[int]]) -> None:
    chars = []
    for tribe in defs.MONSTER_TRIBES:
        if tribe.population >= 2:
            chars.append(tribe.char)

    c = rand.choice(chars)
    for tribe in defs.MONSTER_TRIBES:
        if tribe.char == c:
            x, y = find_random_place(entities, field, distance=2)
            m = defs.Monster(x, y, tribe)
            entities.append(m)
            torched[y][x] = 0  # Visited places are marked as 1 in torched elements. To hide new monsters until revisited, set the corresponding place to 0.
            break


def create_field(
    corridor_h_width: int, corridor_v_width: int, wall_chars: str
) -> Tuple[List[List[str]], defs.Point, defs.Point]:
    def find_empty_cell(field: List[List[str]], left_top: defs.Point, right_bottom: defs.Point) -> defs.Point:
        assert left_top[0] < right_bottom[0]
        assert left_top[1] < right_bottom[1]

        x = rand.randrange(right_bottom[0] - left_top[0]) + left_top[0]
        y = rand.randrange(right_bottom[1] - left_top[1]) + left_top[1]
        assert field[y][x] == " "

        return x, y

    field: List[List[str]] = [[" " for _ in range(defs.FIELD_WIDTH)] for _ in range(defs.FIELD_HEIGHT)]

    # Create walls
    for ty in range(defs.TILE_NUM_Y + 1):
        y = ty * (defs.TILE_HEIGHT + 1)
        for x in range(0, defs.FIELD_WIDTH):
            field[y][x] = wall_chars[1]
    for tx in range(defs.TILE_NUM_X + 1):
        x = tx * (defs.TILE_WIDTH + 1)
        for y in range(0, defs.FIELD_HEIGHT):
            field[y][x] = wall_chars[2]
    for ty in range(defs.TILE_NUM_Y + 1):
        y = ty * (defs.TILE_HEIGHT + 1)
        for tx in range(defs.TILE_NUM_X + 1):
            x = tx * (defs.TILE_WIDTH + 1)
            field[y][x] = wall_chars[0]

    # Create corridors
    edges, first_p, last_p = gen_maze(defs.TILE_NUM_X, defs.TILE_NUM_Y)
    for edge in edges:
        (x1, y1), (x2, y2) = sorted(edge)
        assert x1 <= x2
        assert y1 <= y2
        if y1 == y2:
            d = rand.randrange(defs.TILE_HEIGHT + 1 - corridor_h_width) + 1
            for y in range(corridor_h_width):
                field[y1 * (defs.TILE_HEIGHT + 1) + d + y][x2 * (defs.TILE_WIDTH + 1)] = " "
        else:
            assert x1 == x2
            d = rand.randrange(defs.TILE_WIDTH + 1 - corridor_v_width) + 1
            for x in range(corridor_v_width):
                field[y2 * (defs.TILE_HEIGHT + 1)][x1 * (defs.TILE_WIDTH + 1) + d + x] = " "

    r = tile_to_place_range(*first_p)
    first_p = find_empty_cell(field, r[0], r[1])
    r = tile_to_place_range(*last_p)
    last_p = find_empty_cell(field, r[0], r[1])
    return field, first_p, last_p


def update_torched(torched: List[List[int]], added: List[List[int]]) -> None:
    for y in range(defs.FIELD_HEIGHT):
        for x in range(defs.FIELD_WIDTH):
            torched[y][x] += added[y][x]


def get_torched(player: defs.Player, torch_radius: int) -> List[List[int]]:
    torched: List[List[int]] = [[0 for _ in range(defs.FIELD_WIDTH)] for _ in range(defs.FIELD_HEIGHT)]

    if player.companion == defs.COMPANION_FAIRY:
        torch_radius += defs.FAIRY_TORCH_EXTENSION

    for dy in range(-torch_radius, torch_radius + 1):
        y = player.y + dy
        if 0 <= y < defs.FIELD_HEIGHT:
            w = int(math.sqrt((torch_radius * defs.TORCH_WIDTH_EXPANSION_RATIO) ** 2 - dy**2) + 0.5)
            for dx in range(-w, w + 1):
                x = player.x + dx
                if 0 <= x < defs.FIELD_WIDTH:
                    torched[y][x] = 1

    return torched


def update_entities(
    move_direction: Tuple[int, int],
    field: List[List[str]],
    player: defs.Player,
    entities: List[defs.Entity],
    encountered_types: Set[str],
):
    game_over = False
    message = (-1, "")

    # player move
    dx, dy = move_direction

    if 0 <= (nx := player.x + dx) < defs.FIELD_WIDTH and 0 <= (ny := player.y + dy) < defs.FIELD_HEIGHT:
        c = field[ny][nx]
        if c == " ":
            player.x, player.y = nx, ny
        elif (
            player.companion == defs.COMPANION_HIPPOGRIFF 
            and 0 <= (n2x := player.x + dx * defs.HIPPOGRIFF_FLY_STEP) < defs.FIELD_WIDTH 
            and 0 <= (n2y := player.y + dy * defs.HIPPOGRIFF_FLY_STEP) < defs.FIELD_HEIGHT
            and field[n2y][n2x] == " "
        ):
            player.x, player.y = n2x, n2y
            player.karma += 1
        elif player.item in [defs.ITEM_SWORD_X2, defs.ITEM_SWORD_X3] and c in defs.WALL_CHARS:
            # break the wall
            player.x, player.y = nx, ny
            field[player.y][player.x] = " "
            player.item = ""
            player.item_taken_from = ""

    # Find encountered entity
    enc_entity_infos: List[Tuple[int, defs.Entity]] = []
    sur_entity_infos: List[Tuple[int, defs.Entity]] = []
    for i, e in enumerate(entities):
        if not isinstance(e, defs.Player):
            dx = abs(e.x - player.x)
            dy = abs(e.y - player.y)
            if dx == 0 and dy == 0:
                enc_entity_infos.append((i, e))
            elif dx <= 1 and dy <= 1:
                sur_entity_infos.append((i, e))
    assert len(enc_entity_infos) <= 1

    # Actions & events (combats, state changes, etc)
    for eei, ee in enc_entity_infos:
        if isinstance(ee, defs.Treasure):
            if defs.CHAR_DRAGON in encountered_types:
                encountered_types.add(defs.CHAR_TREASURE)
                message = (-1, ">> Won the Treasure! <<")
                game_over = True
                player.item = defs.ITEM_TREASURE
                player.item_taken_from = ""
                break
        elif isinstance(ee, defs.Monster):
            m: defs.Monster = ee
            encountered_types.add(m.tribe.char)
            player_attack = defs.player_attack_by_level(player)

            effect = m.tribe.effect
            if player_attack < m.tribe.level:
                player.x, player.y = find_random_place(entities, field, distance=2)
                player.item = ""
                player.item_taken_from = ""
                player.lp = max(defs.LP_RESPAWN_MIN, min(player.lp, defs.LP_INIT))
                message = (3, "-- Respawned.")
            else:
                if effect == defs.EFFECT_SPECIAL_EXP:
                    player.level += 10
                else:
                    player.level += 1
                if effect == defs.EFFECT_TREASURE_POINTER:
                    encountered_types.add(defs.CHAR_TREASURE)

                player.lp = max(1, min(defs.LP_MAX, player.lp + m.tribe.feed))

                if m.tribe.companion:
                    player.companion = m.tribe.companion
                    player.karma = 0
                else:
                    player.karma += 1

                del entities[eei]
                player.item = m.tribe.item
                player.item_taken_from = m.tribe.char

                if effect == defs.EFFECT_TREASURE_POINTER:
                    message = (3, "-- Sparkle.")
                elif effect == defs.EFFECT_FEED_MUCH:
                    message = (3, "-- Stuffed.")
                elif effect == defs.EFFECT_SPECIAL_EXP:
                    message = (3, "-- Exp. Boost.")
                elif effect == defs.EFFECT_ENERGY_DRAIN:
                    message = (3, "-- Energy Drained.")

    if player.companion == defs.COMPANION_GOBLIN:
        for eei, ee in sur_entity_infos:
            if isinstance(ee, defs.Monster):
                m: defs.Monster = ee
                if m.tribe.char not in encountered_types:
                    encountered_types.add(m.tribe.char)
                    player.karma += 1

    if player.companion != "":
        if player.karma >= defs.COMPANION_KARMA_LIMIT:
            message = (3, "-- The companion vanishes.")
            player.companion = ""

    return game_over, message


def run_game(ui, seed_str: str, debug_show_entities: bool = False) -> None:
    # Initialize field
    field, first_p, last_p = create_field(defs.CORRIDOR_H_WIDTH, defs.CORRIDOR_V_WIDTH, defs.WALL_CHARS)

    # Initialize entities
    entities: List[defs.Entity] = []
    player: defs.Player = defs.Player(first_p[0], first_p[1], 1, defs.LP_INIT)
    entities.append(player)
    treasure: defs.Treasure = defs.Treasure(last_p[0], last_p[1])
    entities.append(treasure)
    spawn_monsters(entities, field)

    # Initialize view/ui components
    encountered_types: Set[str] = set()
    cur_torched: List[List[int]] = [[0 for _ in range(defs.FIELD_WIDTH)] for _ in range(defs.FIELD_HEIGHT)]
    torched: List[List[int]] = [[0 for _ in range(defs.FIELD_WIDTH)] for _ in range(defs.FIELD_HEIGHT)]

    message: Tuple[int, str] = (-1, "")

    # Initialize stage state
    torch_radius = defs.TORCH_RADIUS
    hours: int = -1
    game_over = False
    move_direction = None

    while not game_over:
        hours += 1

        # Starvation check
        player.lp -= 1
        if player.lp <= 0:
            message = (-1, ">> Starved to Death. <<")
            game_over = True
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
            hours, player, entities, field, cur_torched, torched, encountered_types, debug_show_entities, message[1]
        )

        move_direction = ui.input_direction()
        if move_direction is None:
            return

        # Player move, encounting, etc.
        game_over, m = update_entities(move_direction, field, player, entities, encountered_types)
        if m is not None:
            message = m

        if hours % defs.MONSTER_RESPAWN_RATE == 0:
            respawn_monster(entities, field, torched)

    # Game over display
    show_entities = debug_show_entities

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
            message[1],
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
    return f"v{__version__}-{flag_str}-{args.seed}"


def parse_seed_string(args, seed_str):
    parts = seed_str.split("-")
    if len(parts) != 3:
        exit("Error: Seed string format is invalid. Expected format: v<version>-<flags>-<seed>")
    
    version_part, flag_str, seed_value_str = parts

    if not version_part.startswith("v"):
        exit("Error: Seed string must start with 'v'.")
    version = version_part[1:]
    if version != __version__:
        exit("Error: Seed string version does not match game version.")

    # フラグの復元：指定されているかどうかで真偽値を設定する
    args.large_field = ("F" in flag_str)

    # -T と -t は排他的であることをチェック
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

    args.narrower_corridors = ("n" in flag_str)

    try:
        args.seed = int(seed_value_str)
    except ValueError:
        exit("Error: Seed value in seed string is not a valid integer.")


def main():
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )

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
        if any(o is not None for o in [args.large_field, args.large_torch, args.small_torch, args.narrow_corridors]):
            exit("Error: option --seed is mutually exclusive to options -F, -T, -t, -n")
        parse_seed_string(args, args.seed)
    else:
        args.seed = int(time.time()) % 100000

    if args.large_field:
        defs.TILE_NUM_Y += 1
        defs.FIELD_HEIGHT = (defs.TILE_HEIGHT + 1) * defs.TILE_NUM_Y + 1

    if args.large_torch:
        defs.TORCH_RADIUS += 1
    elif args.small_torch:
        defs.TORCH_RADIUS -= 1

    if args.narrower_corridors:
        defs.CORRIDOR_H_WIDTH -= 1
        defs.CORRIDOR_V_WIDTH -= 1

    rand.set_seed(args.seed)
    seed_str = generate_seed_string(args)

    if args.curses:
        import curses

        from .curses_funcs import CursesUI, TerminalSizeSmall

        def curses_main(stdscr):
            ui = CursesUI(stdscr)
            run_game(ui, seed_str, args.debug_show_entities)

        try:
            curses.wrapper(curses_main)
        except TerminalSizeSmall as e:
            sys.exit("Error: " + str(e))
    else:
        from .pygame_funcs import PygameUI

        ui = PygameUI()
        run_game(ui, seed_str, args.debug_show_entities)
    


if __name__ == "__main__":
    main()
