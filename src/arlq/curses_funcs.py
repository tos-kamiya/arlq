from typing import List, Optional, Set

import curses

from .utils import braille_progress_bar
from . import defs as d


CI_RED = 1
CI_GREEN = 2
CI_YELLOW = 3
CI_BLUE = 4
CI_MAGENTA = 5
CI_CYAN = 6


def curses_draw_stage(
    stdscr: curses.window,
    entities: List[d.Entity],
    field: List[List[str]],
    cur_torched: List[List[int]],
    torched: List[List[int]],
    encountered_types: Set[str],
    show_entities: bool = False,
) -> None:
    """
    Draws the game stage on the provided curses window.

    Parameters:
        stdscr: The curses window to draw on.
        entities: List of game entities (Player, Monster, Treasure, etc.).
        field: 2D list representing the game field.
        cur_torched: 2D list indicating cells that are currently torched.
        torched: 2D list indicating cells that are permanently torched.
        encountered_types: Set of encountered entity types.
        show_entities: Whether to show hidden entities.
    """
    player, px, py = None, None, None
    # Find the player among the entities
    for e in entities:
        if isinstance(e, d.Player):
            player = e
            px, py = player.x, player.y
    assert player is not None and px is not None and py is not None

    # Draw each cell in the field
    for y, row in enumerate(field):
        for x, cell in enumerate(row):
            if cur_torched[y][x]:
                if cell == d.WALL_CHAR:
                    stdscr.addstr(y, x, cell, curses.color_pair(CI_GREEN))
                elif cell == d.CHAR_CALTROP:
                    stdscr.addstr(y, x, cell, curses.color_pair(CI_MAGENTA))
                else:
                    stdscr.addstr(y, x, cell)
            elif torched[y][x] or show_entities:
                if cell == d.WALL_CHAR:
                    stdscr.addstr(y, x, cell, curses.color_pair(CI_GREEN))
                elif cell == " " and (x + y) % 2 == 1:
                    stdscr.addstr(y, x, ".", curses.A_DIM)
                else:
                    stdscr.addstr(y, x, cell)
            else:
                if (x + y) % 2 == 1:
                    stdscr.addstr(y, x, ".", curses.A_DIM)

    # Draw each entity (monsters and treasures)
    player_attack = d.player_attack_by_level(player)
    if show_entities:
        for ei, e in enumerate(entities):
            ch = None
            if isinstance(e, d.Monster):
                m: d.Monster = e
                ch = m.tribe.char
            elif isinstance(e, d.Treasure):
                ch = d.CHAR_TREASURE
            if ch is not None:
                stdscr.addstr(e.y, e.x, ch, curses.A_DIM)

    for ei, e in enumerate(entities):
        if torched[e.y][e.x] == 0 or (e.x, e.y) == (px, py):
            continue
        if isinstance(e, d.Monster):
            m: d.Monster = e
            ch = m.tribe.char
            if ch not in encountered_types:
                if not show_entities:
                    ch = "!" if m.tribe.level == 0 else "?"
                    stdscr.addstr(e.y, e.x, ch, curses.A_BOLD)
            else:
                if m.tribe.level <= player_attack:
                    if m.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
                        ci = CI_YELLOW
                    else:
                        ci = CI_BLUE
                else:
                    ci = CI_RED
                stdscr.addstr(e.y, e.x, ch, curses.A_BOLD | curses.color_pair(ci))
        elif isinstance(e, d.Treasure):
            t: d.Treasure = e
            if t.encounter_type in encountered_types:
                stdscr.addstr(e.y, e.x, d.CHAR_TREASURE, curses.A_BOLD | curses.color_pair(CI_YELLOW))

    # Draw the player character
    stdscr.addstr(py, px, "@", curses.A_BOLD | curses.color_pair(CI_YELLOW))

    # If the player has a companion, draw it right of the player
    if player.companion and px + 1 < d.FIELD_WIDTH:
        ch = d.COMPANION_TO_ATTR_CHAR[player.companion]
        stdscr.addstr(py, px + 1, ch, curses.A_DIM)


def curses_draw_status_bar(
    stdscr: curses.window,
    player: d.Player,
    hours: int,
    stage_num: int = 0,
    message: Optional[str] = None,
    extra_keys: bool = False,
) -> None:
    """
    Draws the status bar at the bottom of the screen. This includes the game hours,
    player level, lp, and a progress bar for lp.

    Parameters:
        stdscr: The curses window to draw on.
        player: The player object.
        hours: The current game hours.
        message: An optional message to display.
        extra_keys: Whether to display extra key hints.
    """
    if player.item == d.ITEM_SWORD_X1_5:
        level_str = "LVL: %d x1.5" % player.level
        item_str = "+%s(%s)" % (player.item, player.item_taken_from)
    elif player.item == d.ITEM_SWORD_CURSED:
        level_str = "LVL: %d x3" % player.level
        item_str = "+%s(%s)" % (player.item, player.item_taken_from)
    elif player.item == d.ITEM_POISONED:
        level_str = "LVL: %d /3" % player.level
        item_str = "+%s(%s)" % (player.item, player.item_taken_from)
    else:
        level_str = "LVL: %d" % player.level
        item_str = ""

    beatable = d.get_max_beatable_monster_tribe(player)

    x, y = 0, d.FIELD_HEIGHT
    def addstr_w_len(s, attr=None):
        nonlocal x, y
        if attr is None:
            stdscr.addstr(y, x, s)
        else:
            stdscr.addstr(y, x, s, attr)
        x += len(s)

    if stage_num != 0:
        addstr_w_len("ST: %d  " % stage_num)
    addstr_w_len("HRS: %d  " % hours)

    addstr_w_len(level_str + "  ")
    addstr_w_len(item_str + "  ")

    if beatable:
        addstr_w_len(">%s  " % ",".join(b.char for b in beatable))

    hp_color = curses.color_pair(CI_RED) if player.lp < 20 else None
    addstr_w_len("HP: ")
    addstr_w_len("%d " % player.lp, hp_color)
    bar_len = 4
    s = braille_progress_bar(player.lp, d.LP_MAX, bar_len)
    addstr_w_len("|")
    addstr_w_len(s, hp_color)
    addstr_w_len("|  ")

    if extra_keys:
        addstr_w_len("/ [q]uit/[m]ap/[s]eed")
    else:
        addstr_w_len("/ [q]uit")

    y += 1
    x = 0
    if message:
        addstr_w_len(message, curses.A_BOLD)


def key_to_dir(key: str) -> Optional[d.Point]:
    """
    Converts a key string to a directional tuple (dx, dy).

    Parameters:
        key: The input key as a string.

    Returns:
        A tuple representing the direction (dx, dy), or None if no valid direction.
    """
    if key in ("w", "W", "KEY_UP"):
        return (0, -1)
    elif key in ("a", "A", "KEY_LEFT"):
        return (-1, 0)
    elif key in ("s", "S", "KEY_DOWN"):
        return (0, 1)
    elif key in ("d", "D", "KEY_RIGHT"):
        return (1, 0)
    return None


class TerminalSizeSmall(ValueError):
    """Exception raised when the terminal size is too small."""

    pass


class CursesUI:
    def __init__(self, stdscr: curses.window):
        """
        Initializes the CursesUI.

        Parameters:
            stdscr: The curses window to be used for display.
        """
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
        curses.init_pair(CI_MAGENTA, curses.COLOR_MAGENTA, -1)
        curses.init_pair(CI_CYAN, curses.COLOR_CYAN, -1)

        stdscr.keypad(True)

        sh, sw = stdscr.getmaxyx()
        if sh < d.FIELD_HEIGHT + 2 or sw < d.FIELD_WIDTH:
            raise TerminalSizeSmall(
                "Terminal size too small. Minimum size is: %d x %d" % (d.FIELD_WIDTH, d.FIELD_HEIGHT + 2)
            )

    def draw_stage(
        self,
        hours,
        player,
        entities,
        field,
        cur_torched,
        torched,
        encountered_types,
        show_entities,
        stage_num=0,
        message=None,
        extra_keys=False,
    ):
        """
        Draws the entire game stage including the status bar.

        Parameters:
            hours: Current game hours.
            player: The player object.
            entities: List of game entities.
            field: 2D list representing the game field.
            cur_torched: 2D list indicating cells that are currently torched.
            torched: 2D list indicating cells that are permanently torched.
            encountered_types: Set of encountered entity types.
            show_entities: Whether to display hidden entities.
            stage_num: Number of stage.
            message: The message to display.
            extra_keys: Whether to display extra key hints.
        """
        stdscr = self.stdscr

        stdscr.erase()
        curses_draw_stage(stdscr, entities, field, cur_torched, torched, encountered_types, show_entities=show_entities)

        curses_draw_status_bar(stdscr, player, hours, stage_num=stage_num, message=message, extra_keys=extra_keys)
        stdscr.refresh()

    def input_direction(self) -> Optional[d.Point]:
        """
        Waits for the user's directional input.

        Returns:
            A tuple (dx, dy) representing the movement direction,
            or None if ESC or 'q' is pressed.
        """
        stdscr = self.stdscr

        # Key input loop
        move_direction = None
        while move_direction is None:
            key = stdscr.getkey()
            if key == 27 or key.lower() == "q":
                return None
            else:
                move_direction = key_to_dir(key)
        assert move_direction is not None

        return move_direction

    def input_alphabet(self) -> Optional[str]:
        """
        Waits for an alphabet key input from the user.

        Returns:
            The lowercase character of the key pressed, or None if ESC or 'q' is pressed.
        """
        stdscr = self.stdscr

        key = stdscr.getkey()
        if key == 27 or key.lower() == "q":
            return None

        return key.lower()

    def select_stage(self) -> int:
        """
        Displays a stage selection menu using curses where the user can navigate with arrow keys and confirm with Enter,
        or directly press 1, 2, ... or Q.

        The selected option is prefixed with ">" (in bold) and non-selected options are prefixed with a blank.

        Returns:
            int: The selected stage number (1, 2, ...), or 0 if "Quit" is chosen.
        """

        num_stages = len(d.STAGE_TO_MONSTER_SPAWN_CONFIGS)
        assert num_stages <= 9

        options = ["[q]uit"]
        for n in range(1, num_stages + 1):
            options.append(f"stage [{n}]")

        current_index = 1
        stdscr = self.stdscr

        while True:
            stdscr.erase()
            stdscr.addstr(2, 2, "Stage Selection", curses.color_pair(CI_YELLOW) | curses.A_BOLD)
            for i, option in enumerate(options):
                # Use ">" for selected, otherwise a blank space.
                prefix = ">" if i == current_index else " "
                if i == current_index:
                    stdscr.addstr(4 + i, 4, f"{prefix} {option}", curses.A_BOLD)
                else:
                    stdscr.addstr(4 + i, 4, f"{prefix} {option}")
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP,):
                current_index = (current_index - 1) % len(options)
            elif key in (curses.KEY_DOWN,):
                current_index = (current_index + 1) % len(options)
            elif key in (10, 13):  # Enter key (LF or CR)
                return current_index
            elif key in (ord("q"), 27):  # 'q' or ESC key
                return 0
            else:
                for n in range(1, num_stages + 1):
                    if key == ord("%d" % n):
                        return n
