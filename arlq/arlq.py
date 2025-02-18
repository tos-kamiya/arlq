from typing import Dict, List, Optional, Set, Tuple, Union

import argparse
import curses
import math
import sys
import time

try:
    from ._version import __version__
except:
    __version__ = "(unknown)"


CI_RED = 1
CI_GREEN = 2
CI_YELLOW = 3
CI_BLUE = 4
CI_CYAN = 6

TILE_WIDTH = 6
TILE_HEIGHT = 4
TILE_NUM_X = 10
TILE_NUM_Y = 4
FIELD_WIDTH = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
CORRIDOR_V_WIDTH = 3
CORRIDOR_H_WIDTH = 2
WALL_CHARS = "###"  # cross, horizontal, vertical

FOOD_MAX = 100
FOOD_INIT = 90
FOOD_STARVATION = 30

ITEM_SWORD = "Sword"
ITEM_POISONED = "Poisoned"
ITEM_TREASURE = "Treasure"

EFFECT_SPECIAL_EXP = "Special Exp."
EFFECT_FEED_MUCH = "Bison Meat"
EFFECT_RANDOM_TRANSPORT = "Random Trans."
EFFECT_CLAIRVOYANCE = "Sword & Eye"
EFFECT_TREASURE_POINTER = "Treasure Ptr."
EFFECT_STONED = "Stoned"

COMPANION_FAIRY = "Fairy"
FAIRY_TORCH_EXTENSION = 2

CHAR_DRAGON = "D"
CHAR_TREASURE = "T"


Point = Tuple[int, int]
Edge = Tuple[Point, Point]


class MyRandom:
    def __init__(self, seed):
        self._value = self.seed = seed

    def randrange(self, r) -> int:
        self._value = (1103515245 * self._value + 12345) % (2 ** 32)
        return self._value % r

    def choice(self, items):
        i = self.randrange(len(items))
        return items[i]


rand_box: List[Optional[MyRandom]] = [None]


def gen_maze(width: int, height: int) -> Tuple[List[Edge], Point, Point]:
    rand = rand_box[0]
    assert rand is not None

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
    def __init__(self, char, level, feed, item="", effect="", companion=""):
        self.char = char
        self.level = level
        self.item = item
        self.effect = effect
        self.feed = feed
        self.companion = companion


MONSTER_KINDS: List[MonsterKind] = [
    MonsterKind("a", 1, 10),  # Amoeba
    MonsterKind("b", 3, 40, effect=EFFECT_FEED_MUCH),  # Bison
    MonsterKind("c", 6, 10, item=ITEM_SWORD),  # Chimera
    MonsterKind("d", 18, 30, item=ITEM_POISONED),  # Comodo Dragon
    MonsterKind(CHAR_DRAGON, 15, 20, effect=EFFECT_TREASURE_POINTER),  # Dragon
    MonsterKind("E", 24, 0, effect=EFFECT_RANDOM_TRANSPORT),  # Elemental
    MonsterKind("f", 0, 0, companion=COMPANION_FAIRY),  # Fairy
    MonsterKind("A", 1, 10, effect=EFFECT_SPECIAL_EXP),  # Amoeba rare
    MonsterKind("B", 3, 80, effect=EFFECT_FEED_MUCH),  # Bison rare
    MonsterKind("C", 6, 10, item=ITEM_SWORD, effect=EFFECT_CLAIRVOYANCE),  # Chimera rare
    MonsterKind("G", 0, -48, effect=EFFECT_STONED),  # Gorgon
]

MONSTER_KIND_POPULATION: Dict[str, Union[int, float]] = {
    "a": 22,
    "b": 5,
    "c": 4,
    "d": 4,
    "D": 1,
    "E": 1,
    "f": 1,
    "A": 0.25,
    "B": 0.25,
    "C": 0.25,
    "G": 0.25,
}


def place_to_tile(x: int, y: int) -> Point:
    return (x - 1) // (TILE_WIDTH + 1), (y - 1) // (TILE_HEIGHT)


def tile_to_place_range(x: int, y: int) -> Tuple[Point, Point]:
    lt = (x * (TILE_WIDTH + 1) + 1, y * (TILE_HEIGHT + 1) + 1)
    rb = (lt[0] + TILE_WIDTH, lt[1] + TILE_HEIGHT)
    return lt, rb


def find_random_place_in_range(field: List[List[str]], left_top: Point, right_bottom: Point) -> Point:
    rand = rand_box[0]
    assert rand is not None

    assert left_top[0] < right_bottom[0]
    assert left_top[1] < right_bottom[1]

    x = rand.randrange(right_bottom[0] - left_top[0]) + left_top[0]
    y = rand.randrange(right_bottom[1] - left_top[1]) + left_top[1]
    assert field[y][x] == " "

    return x, y


def find_random_place(objects: List[Entity], field: List[List[str]], distance: int = 2, place_range: Optional[Tuple[Point, Point]] = None) -> Point:
    rand = rand_box[0]
    assert rand is not None

    places = [(o.x, o.y) for o in objects]
    while True:
        x = rand.randrange(FIELD_WIDTH - 2) + 1
        y = rand.randrange(FIELD_HEIGHT - 2) + 1
        if (
            field[y][x] == " "
            and field[y][x + 1] == " "
            and not any(abs(p[0] - x) <= distance and abs(p[1] - y) <= distance for p in places)
        ):
            return x, y


def spawn_monsters(objects: List[Entity], field: List[List[str]]) -> None:
    rand = rand_box[0]
    assert rand is not None

    for kind in MONSTER_KINDS:
        p = MONSTER_KIND_POPULATION[kind.char]
        if isinstance(p, int):
            for _ in range(p):
                x, y = find_random_place(objects, field, distance=3)
                m = Monster(x, y, kind)
                objects.append(m)
        else:
            if rand.randrange(100)/100 < p:
                x, y = find_random_place(objects, field, distance=3)
                m = Monster(x, y, kind)
                objects.append(m)


def create_field(corridor_h_width: int, corridor_v_width: int, wall_chars: str) -> Tuple[List[List[str]], Point, Point]:
    rand = rand_box[0]
    assert rand is not None

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
    first_p = find_random_place_in_range(field, r[0], r[1])
    r = tile_to_place_range(*last_p)
    last_p = find_random_place_in_range(field, r[0], r[1])
    return field, first_p, last_p


def draw_stage(
    stdscr: curses.window,
    objects: List[Entity],
    field: List[List[str]],
    torched: List[List[int]],
    encountered_types: Set[str],
    show_entities: Optional[bool] = False,
) -> None:
    player, px, py = None, None, None
    for o in objects:
        if isinstance(o, Player):
            player = o
            px, py = player.x, player.y
    assert player is not None and px is not None and py is not None

    if player.companion:
        stdscr.addstr(py, px + 1, "'", curses.A_BOLD)

    for y, row in enumerate(field):
        for x, cell in enumerate(row):
            if (not show_entities or cell == " ") and torched[y][x] == 0:
                stdscr.addstr(y, x, ".", curses.A_DIM)
            elif cell != " ":
                stdscr.addstr(y, x, cell, curses.color_pair(CI_GREEN))

    stdscr.addstr(py, px, "@", curses.A_BOLD)

    atk = player_attack_by_level(player)
    for o in objects:
        if isinstance(o, Monster):
            m = o
            if torched[m.y][m.x] == 0:
                continue

            ch = m.kind.char
            if m.kind.char not in encountered_types:
                if show_entities:
                    stdscr.addstr(m.y, m.x, ch)
                else:
                    stdscr.addstr(m.y, m.x, "?")
            else:
                attr = curses.A_BOLD if "A" <= ch <= "Z" else 0
                ci = CI_BLUE if m.kind.level <= atk else CI_RED
                stdscr.addstr(m.y, m.x, ch, curses.color_pair(ci) | attr)
        elif isinstance(o, Treasure):
            t = o
            if CHAR_TREASURE in encountered_types:
                stdscr.addstr(t.y, t.x, CHAR_TREASURE, curses.color_pair(CI_YELLOW) | curses.A_BOLD)

    if show_entities:
        attr = curses.A_DIM
        for o in objects:
            if isinstance(o, Monster):
                m = o
                if torched[m.y][m.x] != 0:
                    continue

                ch = m.kind.char
                stdscr.addstr(m.y, m.x, ch, attr)
            elif isinstance(o, Treasure):
                t = o
                if CHAR_TREASURE not in encountered_types:
                    stdscr.addstr(t.y, t.x, CHAR_TREASURE, attr)


def player_attack_by_level(player: Player) -> int:
    if player.item == ITEM_SWORD:
        return player.level * 3
    elif player.item == ITEM_POISONED:
        return (player.level + 2) // 3
    else:
        return player.level


def draw_status_bar(stdscr: curses.window, player: Player, hours: int, message: Optional[str] = None, key_show_map: bool = False) -> None:
    rand = rand_box[0]
    assert rand is not None

    if player.item == ITEM_SWORD:
        level_str = "LVL: %d x3" % player.level
        item_str = "+%s(%s)" % (player.item, player.item_taken_from)
    elif player.item == ITEM_POISONED:
        level_str = "LVL: %d /3" % player.level
        item_str = "+%s(%s)" % (player.item, player.item_taken_from)
    else:
        level_str = "LVL: %d" % player.level
        item_str = ""

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
    if key_show_map:
        buf.append("/[Q]uit/Show [M]ap")
    else:
        buf.append("/[Q]uit")
    stdscr.addstr(FIELD_HEIGHT, 0, "  ".join(buf))

    if player.item == ITEM_TREASURE or player.food <= 0:
        if not message:
            message = ''
        message += "  SEED: %d" % rand.seed

    if message:
        stdscr.addstr(FIELD_HEIGHT + 1, 0, message)


# --- キー入力部分の変更 ---
def key_to_dir(key: str) -> Optional[Point]:
    """
    引数 key は stdscr.getkey() で得られる文字列です。
    矢印キーの場合は "KEY_UP" 等、または w,a,s,d などの文字で判定します。
    """
    if key in ['w', 'W', 'KEY_UP']:
        return (0, -1)
    elif key in ['a', 'A', 'KEY_LEFT']:
        return (-1, 0)
    elif key in ['s', 'S', 'KEY_DOWN']:
        return (0, 1)
    elif key in ['d', 'D', 'KEY_RIGHT']:
        return (1, 0)
    return None
# --- ここまで ---


def update_torched(torched: List[List[int]], player: Player, torch_radius: int) -> None:
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


args_box: List[argparse.Namespace] = []


class TerminalSizeSmall(ValueError):
    pass


def curses_main(stdscr: curses.window) -> bool:
    args = args_box[0]
    seed = args.seed
    if seed is None:
        seed = int(time.time()) % 100000

    rand_box[0] = rand = MyRandom(seed)

    curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(CI_RED, curses.COLOR_RED, -1)
    curses.init_pair(CI_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(CI_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(CI_BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(CI_CYAN, curses.COLOR_CYAN, -1)

    sh, sw = stdscr.getmaxyx()
    if sh < FIELD_HEIGHT + 2 or sw < FIELD_WIDTH:
        raise TerminalSizeSmall()

    assert args_box
    args = args_box[0]

    # Set up the game
    corridor_h_width, corridor_v_width = (1, 2) if args.narrower_corridors else (CORRIDOR_H_WIDTH, CORRIDOR_V_WIDTH)
    field, first_p, last_p = create_field(corridor_h_width, corridor_v_width, WALL_CHARS)
    torched: List[List[int]] = [[0 for _ in range(FIELD_WIDTH)] for _ in range(FIELD_HEIGHT)]
    player: Player = Player(first_p[0], first_p[1], 1, FOOD_INIT)
    objects: List[Entity] = [player]
    treasure: Treasure = Treasure(last_p[0], last_p[1])
    objects.append(treasure)
    spawn_monsters(objects, field)
    encountered_types: Set[str] = set()

    torch_radius: int = 4
    if args.large_torch:
        torch_radius = 5
    elif args.small_torch:
        torch_radius = 3

    stdscr.keypad(True)

    flash_message: Optional[str] = None
    message: Optional[str] = None
    hours: int = -1
    game_ends = False
    while not game_ends:
        hours += 1

        # Starvation check
        player.food -= 1
        if args.eating_frugal and player.food < FOOD_STARVATION and hours % 2 == 0:
            player.food += 1
        if player.food <= 0:
            message = ">> Starved to Death. <<"
            game_ends = True
            break

        # Show the field
        update_torched(torched, player, torch_radius)
        stdscr.clear()
        draw_stage(stdscr, objects, field, torched, encountered_types, show_entities=args.debug_show_entities)
        draw_status_bar(stdscr, player, hours, message=message or flash_message)
        stdscr.refresh()
        if flash_message:
            flash_message = None

        # Move player
        while True:
            key = stdscr.getkey()  # 標準のキー入力 (文字列)
            if key.lower() == 'q':
                return False  # quit
            d = key_to_dir(key)
            if d is None:
                continue  # 不明なキーは無視
            dx, dy = d
            new_x, new_y = player.x + dx, player.y + dy
            if field[new_y][new_x] == " ":  # 壁でなければ移動
                player.x, player.y = new_x, new_y
                break

        # Find encountered object
        enc_obj_infos: List[Tuple[int, Entity]] = []
        sur_obj_infos: List[Tuple[int, Entity]] = []
        for i, o in enumerate(objects):
            if not isinstance(o, Player):
                dx = abs(o.x - player.x)
                dy = abs(o.y - player.y)
                if dx == 0 and dy == 0:
                    enc_obj_infos.append((i, o))
                elif dx <= 1 and dy <= 1:
                    sur_obj_infos.append((i, o))
        assert len(enc_obj_infos) <= 1

        # Actions & events (combats, state changes, etc)
        for enc_obj_i, enc_obj in enc_obj_infos:
            if isinstance(enc_obj, Treasure):
                if CHAR_DRAGON in encountered_types:
                    encountered_types.add(CHAR_TREASURE)
                    message = ">> Won the Treasure! <<"
                    game_ends = True
                    player.item = ITEM_TREASURE
                    player.item_taken_from = ''
                    break
            elif isinstance(enc_obj, Monster):
                m = enc_obj
                encountered_types.add(m.kind.char)
                player_attack = player_attack_by_level(player)

                effect = m.kind.effect
                if player_attack < m.kind.level:
                    if effect == EFFECT_RANDOM_TRANSPORT:
                        player.x, player.y = find_random_place(objects, field, distance=2)
                    else:
                        # respawn
                        player.x, player.y = find_random_place(objects, field, distance=2)
                        player.item = ""
                        player.item_taken_from = ""
                        player.food = min(player.food, FOOD_INIT)
                else:
                    if effect == EFFECT_RANDOM_TRANSPORT:
                        pass  # do not change player level
                    elif effect == EFFECT_SPECIAL_EXP:
                        player.level += 7
                    else:
                        player.level += 1

                    if m.kind.feed < 0:
                        hours += -m.kind.feed
                    player.food = max(1, min(FOOD_MAX, player.food + m.kind.feed))

                    if m.kind.companion:
                        player.companion = m.kind.companion

                    if effect == EFFECT_RANDOM_TRANSPORT:
                        player.x, player.y = find_random_place(objects, field, distance=2)
                        m.x, m.y = player.x + 1, player.y
                    else:
                        del objects[enc_obj_i]
                        player.item = m.kind.item
                        player.item_taken_from = m.kind.char

                        if effect == EFFECT_CLAIRVOYANCE:
                            update_torched(torched, player, torch_radius * 4)
                            flash_message = "-- Clairvoyance."
                        elif effect == EFFECT_TREASURE_POINTER:
                            encountered_types.add(CHAR_TREASURE)
                            flash_message = "-- Sparkle."
                        elif effect == EFFECT_FEED_MUCH:
                            flash_message = "-- Stuffed."
                        elif effect == EFFECT_SPECIAL_EXP:
                            flash_message = "-- Special Exp."
                        elif effect == EFFECT_STONED:
                            flash_message = "-- Stoned."
                            if player.companion == COMPANION_FAIRY:
                                player.companion = ''

        for sur_obj_i, sur_obj in sur_obj_infos:
            if isinstance(sur_obj, Treasure):
                if CHAR_DRAGON in encountered_types:
                    encountered_types.add(CHAR_TREASURE)

    update_torched(torched, player, torch_radius)

    stdscr.clear()
    draw_stage(stdscr, objects, field, torched, encountered_types, show_entities=args.debug_show_entities)
    draw_status_bar(stdscr, player, hours, message=message or flash_message, key_show_map=True)
    stdscr.refresh()

    while True:
        key = stdscr.getkey()  # 標準のキー入力 (文字列)
        if key.lower() == "q":
            return False  # quit
        elif key.lower() == "m":
            stdscr.clear()
            draw_stage(stdscr, objects, field, torched, encountered_types, show_entities=True)
            draw_status_bar(stdscr, player, hours, message=message or flash_message, key_show_map=True)
            stdscr.refresh()


def main():
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )

    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)

    g = parser.add_mutually_exclusive_group()
    g.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    g.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")

    parser.add_argument("--debug-show-entities", action="store_true", help="Debug option.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")
    parser.add_argument("-E", '--eating-frugal', action='store_true', help='Decrease rate of consuming food')
    parser.add_argument("--seed", action='store', type=int, help='Seed value')

    args = parser.parse_args()
    args_box.append(args)

    try:
        curses.wrapper(curses_main)
    except TerminalSizeSmall as e:
        sys.exit("Error: Terminal size too small. Minimum size is: %d x %d" % (FIELD_WIDTH, FIELD_HEIGHT + 2))


if __name__ == "__main__":
    main()
