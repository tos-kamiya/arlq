from typing import List, Optional, Set

import curses

from .utils import braille_progress_bar
from .defs import *


CI_RED = 1
CI_GREEN = 2
CI_YELLOW = 3
CI_BLUE = 4
CI_CYAN = 6


def player_attack_by_level(player: Player) -> int:
    if player.item == ITEM_SWORD:
        return player.level * 3
    elif player.item == ITEM_POISONED:
        return (player.level + 2) // 3
    else:
        return player.level


def draw_stage(
    stdscr: curses.window,
    entities: List[Entity],
    field: List[List[str]],
    cur_torched: List[List[int]],
    torched: List[List[int]],
    encountered_types: Set[str],
    show_entities: bool = False,
) -> None:
    player, px, py = None, None, None
    for e in entities:
        if isinstance(e, Player):
            player = e
            px, py = player.x, player.y
    assert player is not None and px is not None and py is not None

    if player.companion:
        stdscr.addstr(py, px + 1, "'", curses.A_BOLD)

    for y, row in enumerate(field):
        for x, cell in enumerate(row):
            if torched[y][x] and cell in WALL_CHARS:
                stdscr.addstr(y, x, cell, curses.color_pair(CI_GREEN))
            elif not show_entities or cell == " ":
                if cur_torched[y][x] == 0:
                    if (x + y) % 2 == 1:
                        stdscr.addstr(y, x, ".", curses.A_DIM)
            else:
                stdscr.addstr(y, x, cell)

    stdscr.addstr(py, px, "@", curses.A_BOLD | curses.color_pair(CI_YELLOW))

    atk = player_attack_by_level(player)
    for e in entities:
        if isinstance(e, Monster):
            m = e
            if torched[m.y][m.x] == 0:
                continue

            ch = m.tribe.char
            if m.tribe.char not in encountered_types:
                if show_entities:
                    stdscr.addstr(m.y, m.x, ch)
                else:
                    stdscr.addstr(m.y, m.x, "?")
            else:
                attr = curses.A_BOLD if "A" <= ch <= "Z" else 0
                ci = CI_BLUE if m.tribe.level <= atk else CI_RED
                stdscr.addstr(m.y, m.x, ch, curses.color_pair(ci) | attr)
        elif isinstance(e, Treasure):
            t = e
            if CHAR_TREASURE in encountered_types:
                stdscr.addstr(t.y, t.x, CHAR_TREASURE, curses.color_pair(CI_YELLOW) | curses.A_BOLD)

    if show_entities:
        attr = curses.A_DIM
        for e in entities:
            if isinstance(e, Monster):
                m = e
                if torched[m.y][m.x] != 0:
                    continue

                ch = m.tribe.char
                stdscr.addstr(m.y, m.x, ch, attr)
            elif isinstance(e, Treasure):
                t = e
                if CHAR_TREASURE not in encountered_types:
                    stdscr.addstr(t.y, t.x, CHAR_TREASURE, attr)



def draw_status_bar(stdscr: curses.window, player: Player, hours: int, message: Optional[str] = None, key_show_map: bool = False) -> None:
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
    for mk in MONSTER_TRIBES:
        if mk.level == 0:
            continue
        if mk.level > atk:
            break
        beatable = mk
    assert beatable is None or beatable.level <= player_attack_by_level(player)

    x = 0
    buf = []
    buf.append("HRS: %d" % hours)
    buf.append(level_str)
    if beatable is not None:
        buf.append("> %s" % beatable.char)
    buf.append("FOOD: %d" % player.food)
    s = "  ".join(buf)
    stdscr.addstr(FIELD_HEIGHT, x, s)
    x += len(s)

    x += 1
    bar_len = 4
    s = braille_progress_bar(player.food, FOOD_MAX, bar_len)
    if player.food < 20:
        stdscr.addstr(FIELD_HEIGHT, x, s, curses.color_pair(CI_RED))
    else:
        stdscr.addstr(FIELD_HEIGHT, x, s)
    stdscr.addstr(FIELD_HEIGHT, x + 1 + bar_len, "|")
    x += 1 + len(s) + 1

    x += 2
    buf = []
    buf.append(item_str)
    if key_show_map:
        buf.append("/[Q]uit/Show [M]ap")
    else:
        buf.append("/[Q]uit")
    s = "  ".join(buf)
    stdscr.addstr(FIELD_HEIGHT, x, s)
    x += len(s)

    if message:
        stdscr.addstr(FIELD_HEIGHT + 1, 0, message)


def key_to_dir(key: str) -> Optional[Point]:
    if key in ['w', 'W', 'KEY_UP']:
        return (0, -1)
    elif key in ['a', 'A', 'KEY_LEFT']:
        return (-1, 0)
    elif key in ['s', 'S', 'KEY_DOWN']:
        return (0, 1)
    elif key in ['d', 'D', 'KEY_RIGHT']:
        return (1, 0)
    return None


class TerminalSizeSmall(ValueError):
    pass


class CursesUI:
    def __init__(self, stdscr: curses.window):
        self.stdscr: curses.window = stdscr

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

        stdscr.keypad(True)

        sh, sw = stdscr.getmaxyx()
        if sh < FIELD_HEIGHT + 2 or sw < FIELD_WIDTH:
            raise TerminalSizeSmall()

    def draw_stage(self, hours, player, entities, field, cur_torched, torched, encountered_types, show_entities, message, flash_message, key_show_map=False):
        stdscr = self.stdscr

        stdscr.clear()
        draw_stage(stdscr, entities, field, cur_torched, torched, encountered_types, show_entities=show_entities)
        draw_status_bar(stdscr, player, hours, message=message or flash_message, key_show_map=key_show_map)
        stdscr.refresh()

    def input_direction(self) -> Optional[Point]:
        stdscr = self.stdscr

        # Key input
        move_direction = None
        while move_direction is None:
            key = stdscr.getkey()
            if key == 27 or key.lower() == 'q':
                return None
            else:
                move_direction = key_to_dir(key)
        assert move_direction is not None

        return move_direction

    def input_alphabet(self) -> Optional[str]:
        stdscr = self.stdscr

        key = stdscr.getkey()
        if key == 27 or key.lower() == "q":
            return None

        return key.lower()

