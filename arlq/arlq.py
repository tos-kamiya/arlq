from typing import Dict, List, Optional, Set, Tuple

import argparse
import curses
import math
import platform
import random
import sys

try:
    from ._version import __version__
except:
    __version__ = '(unknown)'

ROOM_WIDTH = 5
ROOM_HEIGHT = 4
ROOM_NUM_X = 12
ROOM_NUM_Y = 4
FIELD_WIDTH = (ROOM_WIDTH + 1) * ROOM_NUM_X + 1
FIELD_HEIGHT = (ROOM_HEIGHT + 1) * ROOM_NUM_Y + 1

FOOD_MAX = 120
FOOD_INIT = 90
FOOD_BISON = 40
FOOD_SPECIAL_BISON = 80
FOOD_AMOEBA = 8
FOOD_CHIMERA = 8
FOOD_COMODO_DRAGON = 30
FOOD_DRAGON = 10
FOOD_ELEMENTAL = 0

ITEM_BISON_MEAT = 'Bison Meat'
ITEM_SWORD = 'Sword'
ITEM_POISONED = 'Poisoned'
ITEM_RANDOM_TRANSPORT = 'Random Trans.'
ITEM_SPECIAL_EXP = 'Special Exp.'
ITEM_SPECIAL_BISON_MEAT = 'Bison Meat++'
ITEM_SWORD_AND_CLAIRVOYANCE = 'Sword & Eye'
ITEM_TREASURE_POINTER = 'Treasure Ptr.'

COMPANION_FAIRY = 'Fairy'

CHAR_DRAGON = 'D'
CHAR_TREASURE = 'T'


Point = Tuple[int, int]
Edge = Tuple[Point, Point]


def gen_maze(width: int, height: int) -> List[Edge]:
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
    cur_p = random.choice(list(unconnected_point_set))
    unconnected_point_set.remove(cur_p)
    connecting_points.append(cur_p)

    # Keep generating until all points have been connected
    while len(done_points) < width * height:
        # Choose a random connecting point
        i = random.randrange(len(connecting_points))
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
        selected_np = random.choice(unconnected_nps)
        unconnected_point_set.remove(selected_np)
        connecting_points.append(selected_np)

        # Add the edge between the current point and the selected neighboring point to the list of edges
        edges.append((cur_p, selected_np))

    # Return the list of edges that connect all points in the maze
    return edges


# The following visualization function has been generated by ChatGPT 3.5, Mar23 Version. Thanks.
#
# def visualize_maze(width, height, edges):
#     maze = [['#' for _ in range(2 * width + 1)] for _ in range(2 * height + 1)]
#
#     for (x1, y1), (x2, y2) in edges:
#         maze[2 * y1 + 1][2 * x1 + 1] = ' '
#         maze[2 * y2 + 1][2 * x2 + 1] = ' '
#         maze[y1 + y2 + 1][x1 + x2 + 1] = ' '
#
#     for row in maze:
#         print(''.join(row))
#
# # Example usage
# width, height = 10, 10
# edges = gen_maze(width, height)
# visualize_maze(width, height, edges)


class Entity:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    def __init__(self, x, y):
        super().__init__(x, y)


class Player(Entity):
    def __init__(self, x, y, level, food):
        super().__init__(x, y)
        self.level = level
        self.food = food
        self.item = ""
        self.item_taken_from = ""
        self.companion = ""


class Monster(Entity):
    def __init__(self, x, y, kind):
        super().__init__(x, y)
        self.kind = kind


class MonsterKind:
    def __init__(self, char, level, feed, item = '', companion = ''):
        self.char = char
        self.level = level
        self.item = item
        self.feed = feed
        self.companion = companion


# Combine monster_data and item_data into a single dict
MONSTER_KINDS: List[MonsterKind] = [
    MonsterKind('a', 1, FOOD_AMOEBA),  # Amoeba
    MonsterKind('b', 3, FOOD_BISON, item=ITEM_BISON_MEAT),  # Bison
    MonsterKind('c', 6, FOOD_CHIMERA, item=ITEM_SWORD),  # Chimera
    MonsterKind('d', 15, FOOD_COMODO_DRAGON, item=ITEM_POISONED),  # Comodo Dragon
    MonsterKind(CHAR_DRAGON, 15, FOOD_DRAGON, item=ITEM_TREASURE_POINTER),  # Dragon
    MonsterKind('E', 20, FOOD_ELEMENTAL, item=ITEM_RANDOM_TRANSPORT),  # Elemental
    MonsterKind('f', 0, 0, companion=COMPANION_FAIRY),  # Fairy
]

RARE_MONSTER_KINDS: List[MonsterKind] = [
    MonsterKind('A', 1, FOOD_AMOEBA, item=ITEM_SPECIAL_EXP),  # Amoeba rare
    MonsterKind('B', 3, FOOD_SPECIAL_BISON, item=ITEM_SPECIAL_BISON_MEAT),  # Bison rare
    MonsterKind('C', 6, FOOD_CHIMERA, item=ITEM_SWORD_AND_CLAIRVOYANCE),  # Chimera rare
]

MONSTER_KIND_POPULATION: Dict[str, int] = {
    'a': 20,
    'b': 4,
    'c': 4,
    'd': 4,
    'D': 1,
    'E': 2,
    'f': 1,
}


def find_random_place(objects: List[Entity], field: List[List[str]], distance: int) -> Point:
    places = [(o.x, o.y) for o in objects]
    while True:
        x = random.randint(1, FIELD_WIDTH - 2)
        y = random.randint(1, FIELD_HEIGHT - 2)
        if field[y][x] == ' ' and field[y][x + 1] == ' ' and not any(abs(p[0] - x) <= distance and abs(p[1] - y) <= distance for p in places):
            return x, y


def spawn_monsters(objects: List[Entity], field: List[List[str]]) -> None:
    """
    Spawn monsters in the game by finding random places on the field.
    
    Args:
    - objects: a list of objects in the game
    - field: the game field
    
    This function modifies the objects list by adding newly spawned monsters.
    """

    for kind in MONSTER_KINDS:
        for _ in range(MONSTER_KIND_POPULATION[kind.char]):
            x, y = find_random_place(objects, field, 2)
            m = Monster(x, y, kind)
            objects.append(m)
    kind = random.choice(RARE_MONSTER_KINDS)
    x, y = find_random_place(objects, field, 2)
    m = Monster(x, y, kind)
    objects.append(m)


def create_field() -> List[List[str]]:
    # Create field filled with spaces
    field = [[' ' for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]

    # Create walls
    for ry in range(ROOM_NUM_Y + 1):
        y = ry * (ROOM_HEIGHT + 1)
        for x in range(0, FIELD_WIDTH):
            field[y][x] = '#'
    for rx in range(ROOM_NUM_X + 1):
        x = rx * (ROOM_WIDTH + 1)
        for y in range(0, FIELD_HEIGHT):
            field[y][x] = '#'

    # Create corridors
    edges = gen_maze(ROOM_NUM_X, ROOM_NUM_Y)
    for edge in edges:
        (x1, y1), (x2, y2) = sorted(edge)
        assert x1 <= x2
        assert y1 <= y2
        d = random.randrange(3) + 1  # 1, 2, 3
        if y1 == y2:
            for y in range(ROOM_HEIGHT - 2):
                field[y1 * (ROOM_HEIGHT + 1) + d + y][x2 * (ROOM_WIDTH + 1)] = ' '
        else:
            assert x1 == x2
            for x in range(ROOM_WIDTH - 2):
                field[y2 * (ROOM_HEIGHT + 1)][x1 * (ROOM_WIDTH + 1) + d + x] = ' '

    return field


def draw_stage(stdscr: curses.window, objects: List[Entity], field: List[List[str]], torched: List[List[int]], encountered_types: Set[str], no_hide: Optional[bool] = False) -> None:
    hide_on = not no_hide
    for y, row in enumerate(field):
        for x, cell in enumerate(row):
            if (hide_on or cell == ' ') and torched[y][x] == 0:
                stdscr.addstr(y, x, '.', curses.A_DIM)
            else:
                if cell == '#':
                    stdscr.addstr(y, x, '#', curses.color_pair(1))
                else:
                    assert cell == ' '
                    stdscr.addstr(y, x, ' ')

    for o in objects:
        if isinstance(o, Player):
            player = o
            stdscr.addstr(player.y, player.x, '@', curses.color_pair(2) | curses.A_BOLD)
            if player.companion:
                stdscr.addstr(player.y, player.x + 1, "'", curses.color_pair(2) | curses.A_BOLD)

    for o in objects:
        if isinstance(o, Monster):
            m = o
            if hide_on and torched[m.y][m.x] == 0:
                continue

            ch = m.kind.char
            if hide_on and m.kind.char not in encountered_types:
                stdscr.addstr(m.y, m.x, '?', curses.color_pair(3))
            else:
                attr = curses.A_BOLD if 'A' <= ch <= 'Z' else 0
                stdscr.addstr(m.y, m.x, ch, curses.color_pair(3) | attr)
        elif isinstance(o, Treasure):
            t = o
            if CHAR_TREASURE in encountered_types:
                stdscr.addstr(t.y, t.x, CHAR_TREASURE, curses.color_pair(4) | curses.A_BOLD)


def player_attack_by_level(player: Player) -> int:
    if player.item == ITEM_SWORD:
        return player.level * 3
    elif player.item == ITEM_POISONED:
        return (player.level + 2) // 3
    else:
        return player.level


def draw_status_bar(stdscr: curses.window, player: Player, hours: int, message: Optional[str] = None) -> None:
    if player.item == ITEM_SWORD:
        level_str = "LVL: %d x3" % player.level
        item_str = "ITEM: %s(%s)" % (player.item, player.item_taken_from)
    elif player.item == ITEM_POISONED:
        level_str = "LVL: %d /3" % player.level
        item_str = "ITEM: %s(%s)" % (player.item, player.item_taken_from)
    else:
        level_str = "LVL: %d" % player.level
        item_str = "ITEM: -"

    beatable = None
    atk = player_attack_by_level(player)
    for mk in MONSTER_KINDS:
        if mk.level == 0:
            continue
        if mk.level > atk:
            break
        beatable = mk
    assert beatable is None or beatable.level <= player_attack_by_level(player)

    buf = []
    buf.append("HRS: %d" % hours)
    buf.append(level_str)
    if beatable is not None:
        buf.append("> %s" % beatable.char)
    buf.append("FOOD: %d" % player.food)
    buf.append(item_str)
    buf.append('/ Press [Q] to exit')
    stdscr.addstr(FIELD_HEIGHT, 0, "  ".join(buf))

    if message:
        stdscr.addstr(FIELD_HEIGHT + 1, 0, message)


def key_to_dir(key: int) -> Optional[Point]:
    dx, dy = 0, 0
    if key in [ord('w'), curses.KEY_UP]:
        dy = -1
    elif key in [ord('a'), curses.KEY_LEFT]:
        dx = -1
    elif key in [ord('s'), curses.KEY_DOWN]:
        dy = 1
    elif key in [ord('d'), curses.KEY_RIGHT]:
        dx = 1
    else:
        return None
    return dx, dy


def update_torched(torched: List[List[int]], player: Player, torch_radius: int) -> None:
    if player.companion == COMPANION_FAIRY:
        torch_radius += 1

    for dy in range(-torch_radius, torch_radius + 1):
        y = player.y + dy
        if 0 <= y < FIELD_HEIGHT:
            w = int(math.sqrt((torch_radius*1.2)**2 - dy**2) + 0.5)
            for dx in range(-w, w + 1):
                x = player.x + dx
                if 0 <= x < FIELD_WIDTH:
                    torched[y][x] = 1


args_box: List[argparse.Namespace] = []


class TerminalSizeSmall(ValueError):
    pass


def curses_main(stdscr: curses.window) -> None:
    sh, sw = stdscr.getmaxyx()
    if sh < FIELD_HEIGHT + 2 or sw < FIELD_WIDTH:
        raise TerminalSizeSmall()

    assert args_box
    args = args_box[0]

    # Set up the game
    field: List[List[str]] = create_field()
    torched: List[List[int]] = [[0 for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
    x, y = find_random_place([], field, 2)
    player: Player = Player(x, y, 1, FOOD_INIT)
    objects: List[Entity] = [player]
    treasure: Treasure = Treasure(*find_random_place(objects, field, 2))
    objects.append(treasure)
    spawn_monsters(objects, field)
    encountered_types: Set[str] = set()

    torch_radius: int = 4
    if args.large_torch:
        torch_radius = 5
    elif args.small_torch:
        torch_radius = 3

    def consume_player_item(player: Player) -> str:
        item = player.item
        message = ''
        if item in [ITEM_BISON_MEAT, ITEM_SPECIAL_BISON_MEAT]:
            message = "-- Stuffed."
            player.item = ''
        elif item == ITEM_TREASURE_POINTER:
            message = "-- Sparkle."
            player.item = ''
        elif item == ITEM_SPECIAL_EXP:
            message = "-- Special Exp."
            player.item = ''
        elif item == ITEM_SWORD_AND_CLAIRVOYANCE:
            message = "-- Clairvoyance."
            player.item = ITEM_SWORD
        return message

    stdscr.keypad(True)

    message: Optional[str] = None
    hours: int = -1
    while True:
        hours += 1

        # Starvation check
        player.food -= 1
        if player.food <= 0:
            message = ">> Starved to Death. <<"
            break  # end game

        # Show the field
        update_torched(torched, player, torch_radius)
        temp_message = consume_player_item(player)
        stdscr.clear()
        draw_stage(stdscr, objects, field, torched, encountered_types, no_hide=args.debug_no_hide)
        draw_status_bar(stdscr, player, hours, message=message or temp_message)
        stdscr.refresh()

        # Move player
        while True:
            key = stdscr.getch()
            d = key_to_dir(key)
            if d is None:
                return

            dx, dy = d
            new_x, new_y = player.x + dx, player.y + dy
            if field[new_y][new_x] == ' ':  # if the cell is not a wall
                player.x, player.y = new_x, new_y
                break

        # Find encountered object
        enc_obj: Optional[Entity] = None
        enc_obj_i: int = -1
        for enc_obj_i, o in enumerate(objects):
            if (not isinstance(o, Player)) and o.x == player.x and o.y == player.y:
                enc_obj = o
                break
        if enc_obj is None:
            continue  # while True

        if isinstance(enc_obj, Treasure):
            if CHAR_DRAGON in encountered_types:
                encountered_types.add(CHAR_TREASURE)
                message = ">> Won the Treasure! <<"
                break  # end game
        elif isinstance(enc_obj, Monster):
            m = enc_obj
            encountered_types.add(m.kind.char)
            player_attak = player_attack_by_level(player)

            if player_attak < m.kind.level:
                # respawn
                player.x, player.y = find_random_place(objects, field, 2)
                player.item = ''
                player.item_taken_from = ''
                player.food = min(player.food, FOOD_INIT)
            else:
                if m.kind.item == ITEM_RANDOM_TRANSPORT:
                    pass
                elif m.kind.item == ITEM_SPECIAL_EXP:
                    player.level += 7
                else:
                    player.level += 1

                if m.kind.item == ITEM_SWORD_AND_CLAIRVOYANCE:
                    update_torched(torched, player, torch_radius * 4)

                if m.kind.item == ITEM_TREASURE_POINTER:
                    encountered_types.add(CHAR_TREASURE)

                player.food = min(FOOD_MAX, player.food + m.kind.feed)

                if m.kind.companion:
                    player.companion = m.kind.companion

                if m.kind.item == ITEM_RANDOM_TRANSPORT:
                    player.x, player.y = find_random_place(objects, field, 2)
                    m.x, m.y = player.x + 1, player.y
                else:
                    del objects[enc_obj_i]
                    player.item = m.kind.item
                    player.item_taken_from = m.kind.char

    update_torched(torched, player, torch_radius)

    temp_message = consume_player_item(player)
    stdscr.clear()
    draw_stage(stdscr, objects, field, torched, encountered_types, no_hide=args.debug_no_hide)
    draw_status_bar(stdscr, player, hours, message=message or temp_message)
    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key == ord('q'):
            break


def main():
    parser = argparse.ArgumentParser(
        description='A Rogue-Like game.',
    )

    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        '-l', '--large-torch',
        action='store_true',
        help='Large torch.'
    )
    g.add_argument(
        '-s', '--small-torch',
        action='store_true',
        help='Small torch.'
    )
    g.add_argument(
        '--debug-no-hide',
        action='store_true',
        help='Debug option.'
    )

    args = parser.parse_args()
    args_box.append(args)

    curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # wall
    curses.init_pair(2, curses.COLOR_BLUE, -1)  # player
    curses.init_pair(3, curses.COLOR_RED, -1)  # monster
    curses.init_pair(4, curses.COLOR_YELLOW, -1)  # treasure

    try:
        curses.wrapper(curses_main)
    except TerminalSizeSmall as e:
        sys.exit("Error: Terminal size too small. Minimum size is: %d x %d" % (FIELD_WIDTH, FIELD_HEIGHT + 2))
    finally:
        curses.endwin()


if __name__ == "__main__":
    main()
