from typing import List, Optional, Set, Tuple

import argparse
import curses
import math
import sys
import time

try:
    from ._version import __version__
except:
    __version__ = "(unknown)"

from .utils import rand
from .defs import *

def gen_maze(width: int, height: int) -> Tuple[List[Edge], Point, Point]:
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


def place_to_tile(x: int, y: int) -> Point:
    return (x - 1) // (TILE_WIDTH + 1), (y - 1) // (TILE_HEIGHT)


def tile_to_place_range(x: int, y: int) -> Tuple[Point, Point]:
    lt = (x * (TILE_WIDTH + 1) + 1, y * (TILE_HEIGHT + 1) + 1)
    rb = (lt[0] + TILE_WIDTH, lt[1] + TILE_HEIGHT)
    return lt, rb


def find_random_place(entities: List[Entity], field: List[List[str]], distance: int = 2) -> Point:
    places = [(e.x, e.y) for e in entities]
    while True:
        x = rand.randrange(FIELD_WIDTH - 2) + 1
        y = rand.randrange(FIELD_HEIGHT - 2) + 1
        if (
            field[y][x] == " "
            and field[y][x + 1] == " "
            and not any(abs(p[0] - x) <= distance and abs(p[1] - y) <= distance for p in places)
        ):
            return x, y


def spawn_monsters(entities: List[Entity], field: List[List[str]]) -> None:
    for tribe in MONSTER_TRIBES:
        p = tribe.population
        if isinstance(p, float):
            p = 1 if rand.randrange(100)/100 < p else 0
        for _ in range(p):
            x, y = find_random_place(entities, field, distance=3)
            m = Monster(x, y, tribe)
            entities.append(m)


def respawn_monster(entities: List[Entity], field: List[List[str]]) -> None:
    chars = []
    for tribe in MONSTER_TRIBES:
        if tribe.population >= 2:
            chars.append(tribe.char)

    c = rand.choice(chars)
    for tribe in MONSTER_TRIBES:
        if tribe.char == c:
            x, y = find_random_place(entities, field, distance=3)
            m = Monster(x, y, tribe)
            entities.append(m)
            break


def create_field(corridor_h_width: int, corridor_v_width: int, wall_chars: str) -> Tuple[List[List[str]], Point, Point]:
    def find_empty_cell(field: List[List[str]], left_top: Point, right_bottom: Point) -> Point:
        assert left_top[0] < right_bottom[0]
        assert left_top[1] < right_bottom[1]

        x = rand.randrange(right_bottom[0] - left_top[0]) + left_top[0]
        y = rand.randrange(right_bottom[1] - left_top[1]) + left_top[1]
        assert field[y][x] == " "

        return x, y

    field: List[List[str]] = [[" " for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]

    # Create walls
    for ty in range(TILE_NUM_Y + 1):
        y = ty * (TILE_HEIGHT + 1)
        for x in range(0, FIELD_WIDTH):
            field[y][x] = wall_chars[1]
    for tx in range(TILE_NUM_X + 1):
        x = tx * (TILE_WIDTH + 1)
        for y in range(0, FIELD_HEIGHT):
            field[y][x] = wall_chars[2]
    for ty in range(TILE_NUM_Y + 1):
        y = ty * (TILE_HEIGHT + 1)
        for tx in range(TILE_NUM_X + 1):
            x = tx * (TILE_WIDTH + 1)
            field[y][x] = wall_chars[0]

    # Create corridors
    edges, first_p, last_p = gen_maze(TILE_NUM_X, TILE_NUM_Y)
    for edge in edges:
        (x1, y1), (x2, y2) = sorted(edge)
        assert x1 <= x2
        assert y1 <= y2
        if y1 == y2:
            d = rand.randrange(TILE_HEIGHT + 1 - corridor_h_width) + 1
            for y in range(corridor_h_width):
                field[y1 * (TILE_HEIGHT + 1) + d + y][x2 * (TILE_WIDTH + 1)] = " "
        else:
            assert x1 == x2
            d = rand.randrange(TILE_WIDTH + 1 - corridor_v_width) + 1
            for x in range(corridor_v_width):
                field[y2 * (TILE_HEIGHT + 1)][x1 * (TILE_WIDTH + 1) + d + x] = " "

    r = tile_to_place_range(*first_p)
    first_p = find_empty_cell(field, r[0], r[1])
    r = tile_to_place_range(*last_p)
    last_p = find_empty_cell(field, r[0], r[1])
    return field, first_p, last_p


def update_torched(torched: List[List[int]], added: List[List[int]]) -> None:
    for y in range(FIELD_HEIGHT):
        for x in range(FIELD_WIDTH):
            torched[y][x] += added[y][x]


def get_torched(player: Player, torch_radius: int) -> List[List[int]]:
    torched: List[List[int]] = [[0 for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]

    if player.companion == COMPANION_FAIRY:
        torch_radius += FAIRY_TORCH_EXTENSION

    for dy in range(-torch_radius, torch_radius + 1):
        y = player.y + dy
        if 0 <= y < FIELD_HEIGHT:
            w = int(math.sqrt((torch_radius * 1.1) ** 2 - dy**2) + 0.5)
            for dx in range(-w, w + 1):
                x = player.x + dx
                if 0 <= x < FIELD_WIDTH:
                    torched[y][x] = 1

    return torched


def update_entities(move_direction, field, player, entities, encountered_types, torched, torch_radius):
    game_over = False
    message = flash_message = None

    # player move
    dx, dy = move_direction
    new_x, new_y = player.x + dx, player.y + dy
    if 0 <= new_x < len(field[0]) and 0 <= new_y < len(field):
        c = field[new_y][new_x]
        if c == " ":
            player.x, player.y = new_x, new_y
        elif player.item == ITEM_SWORD and c in WALL_CHARS:
            # break the wall
            player.x, player.y = new_x, new_y
            field[player.y][player.x] = " "
            player.item = ''
            player.item_taken_from = ''

    # Find encountered entity
    enc_obj_infos: List[Tuple[int, Entity]] = []
    sur_obj_infos: List[Tuple[int, Entity]] = []
    for i, e in enumerate(entities):
        if not isinstance(e, Player):
            dx = abs(e.x - player.x)
            dy = abs(e.y - player.y)
            if dx == 0 and dy == 0:
                enc_obj_infos.append((i, e))
            elif dx <= 1 and dy <= 1:
                sur_obj_infos.append((i, e))
    assert len(enc_obj_infos) <= 1

    # Actions & events (combats, state changes, etc)
    for enc_obj_i, enc_obj in enc_obj_infos:
        if isinstance(enc_obj, Treasure):
            if CHAR_DRAGON in encountered_types:
                encountered_types.add(CHAR_TREASURE)
                message = ">> Won the Treasure! <<"
                game_over = True
                player.item = ITEM_TREASURE
                player.item_taken_from = ''
                break
        elif isinstance(enc_obj, Monster):
            m = enc_obj
            encountered_types.add(m.tribe.char)
            player_attack = player_attack_by_level(player)

            effect = m.tribe.effect
            if player_attack < m.tribe.level:
                if effect == EFFECT_RANDOM_TRANSPORT:
                    player.x, player.y = find_random_place(entities, field, distance=2)
                else:
                    # respawn
                    player.x, player.y = find_random_place(entities, field, distance=2)
                    player.item = ""
                    player.item_taken_from = ""
                    player.food = min(player.food, FOOD_INIT)
            else:
                if effect == EFFECT_RANDOM_TRANSPORT:
                    pass  # do not change player level
                elif effect == EFFECT_SPECIAL_EXP:
                    player.level += 10
                else:
                    player.level += 1

                player.food = max(1, min(FOOD_MAX, player.food + m.tribe.feed))

                if m.tribe.companion:
                    player.companion = m.tribe.companion

                if effect == EFFECT_RANDOM_TRANSPORT:
                    player.x, player.y = find_random_place(entities, field, distance=2)
                    m.x, m.y = player.x + 1, player.y
                else:
                    del entities[enc_obj_i]
                    player.item = m.tribe.item
                    player.item_taken_from = m.tribe.char

                    if effect == EFFECT_CLAIRVOYANCE:
                        cur_torched = get_torched(player, torch_radius * 4)
                        update_torched(torched, cur_torched)
                        flash_message = "-- Clairvoyance."
                    elif effect == EFFECT_TREASURE_POINTER:
                        encountered_types.add(CHAR_TREASURE)
                        flash_message = "-- Sparkle."
                    elif effect == EFFECT_FEED_MUCH:
                        flash_message = "-- Stuffed."
                    elif effect == EFFECT_SPECIAL_EXP:
                        flash_message = "-- Special Exp."

    for sur_obj_i, sur_obj in sur_obj_infos:
        if isinstance(sur_obj, Treasure):
            if CHAR_DRAGON in encountered_types:
                encountered_types.add(CHAR_TREASURE)

    return game_over, message, flash_message


args_box: List[argparse.Namespace] = []


def run_game(ui) -> None:
    args = args_box[0]
    seed = args.seed
    if seed is None:
        seed = int(time.time()) % 100000

    rand.set_seed(seed)

    # Initialize field
    corridor_h_width, corridor_v_width = (1, 2) if args.narrower_corridors else (CORRIDOR_H_WIDTH, CORRIDOR_V_WIDTH)
    field, first_p, last_p = create_field(corridor_h_width, corridor_v_width, WALL_CHARS)

    # Initialize entities
    entities: List[Entity] = []
    player: Player = Player(first_p[0], first_p[1], 1, FOOD_INIT)
    entities.append(player)
    treasure: Treasure = Treasure(last_p[0], last_p[1])
    entities.append(treasure)
    spawn_monsters(entities, field)

    # Initialize view/ui components
    encountered_types: Set[str] = set()
    cur_torched: List[List[int]] = [[0 for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
    torched: List[List[int]] = [[0 for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
    torch_radius: int = 4
    if args.large_torch:
        torch_radius = 5
    elif args.small_torch:
        torch_radius = 3
    flash_message: Optional[str] = None
    message: Optional[str] = None

    # Initialize stage state
    hours: int = -1
    game_over = False
    move_direction = None

    while not game_over:
        hours += 1

        # Starvation check
        player.food -= 1
        if args.eating_frugal and player.food < FOOD_STARVATION and hours % 2 == 0:
            player.food += 1
        if player.food <= 0:
            message = ">> Starved to Death. <<"
            game_over = True
            break

        # Update view / auto mapping
        cur_torched = get_torched(player, torch_radius)
        update_torched(torched, cur_torched)

        # Show the field
        if flash_message:
            flash_message = None

        ui.draw_stage(hours, player, entities, field, cur_torched, torched, encountered_types, args.debug_show_entities, message, flash_message)

        move_direction = ui.input_direction()
        if move_direction is None:
            return

        # Player move, encounting, etc.
        game_over, message, flash_message = update_entities(move_direction, field, player, entities, encountered_types, torched, torch_radius)

        if hours % MONSTER_RESPAWN_RATE == 0:
            respawn_monster(entities, field)

    # Game over display
    show_entities = args.debug_show_entities

    while True:
        ui.draw_stage
        ui.draw_stage(hours, player, entities, field, cur_torched, torched, encountered_types, show_entities, message, flash_message, key_show_map=True)

        c = ui.input_alphabet()
        if c is None:
            return
        if c == "m":
            show_entities = True

        message = "SEED: %d" % rand.get_seed()
        flash_message = ''


def main():
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )

    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)

    g = parser.add_mutually_exclusive_group()
    g.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    g.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")

    parser.add_argument("--curses", action="store_true", help="Use curses as UI framework.")
    parser.add_argument("--debug-show-entities", action="store_true", help="Debug option.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")
    parser.add_argument("-E", '--eating-frugal', action='store_true', help='Decrease rate of consuming food')
    parser.add_argument("--seed", action='store', type=int, help='Seed value')

    args = parser.parse_args()
    args_box.append(args)

    if args.curses:
        from .curses_funcs import CursesUI, TerminalSizeSmall

        def curses_main(stdscr):
            ui = CursesUI(stdscr)
            run_game(ui)

        try:
            curses.wrapper(curses_main)
        except TerminalSizeSmall as e:
            sys.exit("Error: Terminal size too small. Minimum size is: %d x %d" % (FIELD_WIDTH, FIELD_HEIGHT + 2))
    else:
        from .pygame_funcs import PygameUI

        ui = PygameUI()
        run_game(ui)


if __name__ == "__main__":
    main()
