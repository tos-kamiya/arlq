from typing import Optional, Tuple, List, Set

import pygame

from .__about__ import __version__
from . import defs

# RGB colors corresponding to curses color numbers
CI_RED = 1
CI_GREEN = 2
CI_YELLOW = 3
CI_BLUE = 4
CI_CYAN = 6

# Color mapping for Pygame
COLOR_MAP = {
    CI_RED: (255, 80, 100),
    CI_GREEN: (80, 255, 80),
    CI_YELLOW: (240, 240, 0),
    CI_BLUE: (80, 100, 255),
    CI_CYAN: (0, 240, 240),
    "default": (255, 255, 255),
}

CELL_SIZE_Y = 20
CELL_SIZE_X = 13


# PygameUI is designed to have the same API as CursesUI.
class PygameUI:
    def __init__(self):
        pygame.init()

        # Hide mouse cursor
        pygame.mouse.set_visible(False)

        # Pixel size per cell
        self.field_width = defs.FIELD_WIDTH
        self.field_height = defs.FIELD_HEIGHT

        # Window size to draw the stage plus the status bar (+2 rows)
        self.window_width = self.field_width * CELL_SIZE_X
        self.window_height = (self.field_height + 2) * CELL_SIZE_Y
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption(f"Arlq (Pygame mix) v{__version__}")

        # Prepare monospace fonts (including a bold version)
        self.font = pygame.font.SysFont("Courier", CELL_SIZE_Y)
        self.font_bold = pygame.font.SysFont("Courier", CELL_SIZE_Y, bold=True)

        # Auxiliary clock for controlling FPS
        self.clock = pygame.time.Clock()

    def _draw_text(
        self,
        pos: Tuple[int, int],
        text: str,
        color: Tuple[int, int, int],
        bold: bool = False,
    ):
        """
        Draws the given text at the grid cell pos=(x, y).
        If bold is True, a bold font is used.
        """
        font = self.font_bold if bold else self.font
        surface = font.render(text, True, color)
        pixel_pos = (pos[0] * CELL_SIZE_X, pos[1] * CELL_SIZE_Y)
        self.screen.blit(surface, pixel_pos)

    def _dim_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """
        Returns a dimmed version of the given color (half brightness, similar to curses A_DIM).
        """
        return (color[0] // 2, color[1] // 2, color[2] // 2)

    def draw_stage(
        self,
        hours: int,
        player: defs.Player,
        entities: List[defs.Entity],
        field: List[List[str]],
        cur_torched: List[List[int]],
        torched: List[List[int]],
        encountered_types: Set[str],
        show_entities: bool,
        message: Optional[str],
        extra_keys: bool = False,
    ):
        # Clear the entire screen with black
        self.screen.fill((0, 0, 0))

        # Determine the player's position
        px, py = player.x, player.y

        # If the player has a companion, draw it right of the player
        if player.companion:
            ch = defs.COMPANION_TO_ATTR_CHAR[player.companion]
            self._draw_text((px + 1, py), ch, self._dim_color(COLOR_MAP["default"]), bold=True)

        # Draw each cell of the field
        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                if torched[y][x] and cell in defs.WALL_CHARS:
                    self._draw_text((x, y), cell, COLOR_MAP[CI_GREEN])
                elif (not show_entities) or cell == " ":
                    if cur_torched[y][x] == 0:
                        if (x + y) % 2 == 1:
                            self._draw_text((x, y), ".", self._dim_color(COLOR_MAP["default"]))
                else:
                    self._draw_text((x, y), cell, COLOR_MAP["default"])

        # Draw the player as "@" (bold and yellow)
        self._draw_text((px, py), "@", COLOR_MAP[CI_YELLOW], bold=True)

        # Calculate the player's attack power
        atk = defs.player_attack_by_level(player)

        # Draw each entity (monster, treasure)
        for e in entities:
            if isinstance(e, defs.Monster):
                m: defs.Monster = e
                if torched[m.y][m.x] == 0:
                    continue
                ch = m.tribe.char
                if ch not in encountered_types:
                    if show_entities:
                        self._draw_text((m.x, m.y), ch, COLOR_MAP["default"])
                    else:
                        ch = "!" if m.tribe.level == 0 else "?"
                        self._draw_text((m.x, m.y), ch, COLOR_MAP["default"])
                else:
                    # Use bold if the character is between A and Z
                    bold_attr = "A" <= ch <= "Z"
                    col = COLOR_MAP[CI_BLUE] if m.tribe.level <= atk else COLOR_MAP[CI_RED]
                    self._draw_text((m.x, m.y), ch, col, bold=bold_attr)
            elif isinstance(e, defs.Treasure):
                t: defs.Treasure = e
                if defs.CHAR_TREASURE in encountered_types:
                    self._draw_text((t.x, t.y), defs.CHAR_TREASURE, COLOR_MAP[CI_YELLOW], bold=True)

        if show_entities:
            # Draw entities that are not torched (torched == 0) in a dimmed style
            for e in entities:
                if isinstance(e, defs.Monster):
                    m: defs.Monster = e
                    if torched[m.y][m.x] != 0:
                        continue
                    self._draw_text((m.x, m.y), m.tribe.char, self._dim_color(COLOR_MAP["default"]))
                elif isinstance(e, defs.Treasure):
                    t: defs.Treasure = e
                    if defs.CHAR_TREASURE not in encountered_types:
                        self._draw_text((t.x, t.y), defs.CHAR_TREASURE, self._dim_color(COLOR_MAP["default"]))

        # Draw the status bar (handled by draw_status_bar)
        self.draw_status_bar(hours, player, message, extra_keys)

        pygame.display.flip()
        # Control the FPS
        self.clock.tick(30)

    def draw_status_bar(
        self, hours: int, player: defs.Player, message: Optional[str], extra_keys: bool
    ):
        # Draw the existing status string
        if player.item == defs.ITEM_SWORD_X2:
            level_str = "LVL: %d x2" % player.level
            item_str = "+%s(%s)" % (player.item, player.item_taken_from)
        elif player.item == defs.ITEM_SWORD_X3:
            level_str = "LVL: %d x3" % player.level
            item_str = "+%s(%s)" % (player.item, player.item_taken_from)
        elif player.item == defs.ITEM_POISONED:
            level_str = "LVL: %d /3" % player.level
            item_str = "+%s(%s)" % (player.item, player.item_taken_from)
        else:
            level_str = "LVL: %d" % player.level
            item_str = ""

        beatable = defs.get_max_beatable_monster_tribe(player)

        status_parts = []
        status_parts.append("HRS: %d" % hours)
        status_parts.append(level_str)
        if beatable is not None:
            status_parts.append("> %s" % beatable.char)
        status_parts.append("FOOD: %d" % player.food)
        status_str = "  ".join(status_parts)

        # Draw the status string at the left edge
        self._draw_text((0, self.field_height), status_str, COLOR_MAP["default"])

        # Get the exact width of the drawn status string
        text_width, _ = self.font.size(status_str)
        x_offset = text_width + 10  # Start drawing the progress bar from this position

        # Draw the graphical progress bar
        bar_cells = 4
        bar_width = bar_cells * CELL_SIZE_X
        bar_height = CELL_SIZE_Y // 2

        y_offset = self.field_height * CELL_SIZE_Y + (CELL_SIZE_Y - bar_height) // 2

        # Calculate the progress ratio for food
        progress_ratio = player.food / defs.FOOD_MAX
        fill_width = int(bar_width * progress_ratio)

        # Use red if food is less than 20, otherwise use the default color
        food_color = COLOR_MAP[CI_RED] if player.food < 20 else COLOR_MAP["default"]

        border_rect = pygame.Rect(x_offset, y_offset, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLOR_MAP["default"], border_rect, 1)

        fill_rect = pygame.Rect(x_offset, y_offset, fill_width, bar_height)
        pygame.draw.rect(self.screen, food_color, fill_rect)

        extra = "/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit"
        item_status = "  ".join([item_str, extra])
        item_x_offset = x_offset + bar_width + 10
        self._draw_text((item_x_offset // CELL_SIZE_X, self.field_height), item_status, COLOR_MAP["default"])

        if message:
            self._draw_text((0, self.field_height + 1), message, COLOR_MAP["default"], bold=True)

    def input_direction(self) -> Optional[Tuple[int, int]]:
        """
        Waits for the user's directional input.
        Returns the movement direction (dx, dy) when an arrow key or WASD key is pressed.
        Returns None if ESC or 'q' is pressed.
        """
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        return None
                    if event.key in (pygame.K_UP, pygame.K_w):
                        return (0, -1)
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        return (0, 1)
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        return (-1, 0)
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        return (1, 0)
            self.clock.tick(30)

    def input_alphabet(self) -> Optional[str]:
        """
        Waits for an alphabet key input from the user.
        Returns None if ESC or 'q' is pressed.
        Otherwise, returns the key in lowercase.
        """
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        return None
                    # Get the key name using pygame.key.name()
                    key_name = pygame.key.name(event.key)
                    return key_name.lower()
            self.clock.tick(30)

    def quit(self):
        """Terminates Pygame."""
        pygame.quit()
