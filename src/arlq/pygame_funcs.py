from typing import Optional, Tuple, List, Set

import pygame

from .__about__ import __version__
from . import defs as d

# RGB colors corresponding to curses color numbers
CI_RED = 1
CI_GREEN = 2
CI_YELLOW = 3
CI_BLUE = 4
CI_MAGENTA = 5
CI_CYAN = 6

# Color mapping for Pygame
COLOR_MAP = {
    CI_RED: (255, 80, 120),
    CI_GREEN: (80, 255, 80),
    CI_YELLOW: (240, 240, 0),
    CI_BLUE: (80, 120, 255),
    CI_MAGENTA: (240, 0, 240),
    CI_CYAN: (0, 240, 240),
    "default": (255, 255, 255),
}

CELL_SIZE_Y = 20
CELL_SIZE_X = 13


class PygameUI:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(210)
        pygame.mouse.set_visible(False)

        if pygame.joystick.get_count() > 0:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
        else:
            joystick = None
        self.joystick = joystick

        # Field dimensions from defs
        self.field_width = d.FIELD_WIDTH
        self.field_height = d.FIELD_HEIGHT

        # Calculate window dimensions (including status bar area)
        self.window_width = self.field_width * CELL_SIZE_X
        self.window_height = (self.field_height + 2) * CELL_SIZE_Y
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption(f"Arlq (Pygame mix) v{__version__}")

        # Prepare monospace fonts (normal and bold)
        self.font = pygame.font.SysFont("Courier", CELL_SIZE_Y)
        self.font_bold = pygame.font.SysFont("Courier", CELL_SIZE_Y, bold=True)

        self.clock = pygame.time.Clock()
        self.joystick_interval_timer = 0
        self.joystick_previous_direction = None

    def _draw_text(
        self,
        pos: d.Point,
        text: str,
        color: Tuple[int, int, int],
        bold: bool = False,
    ):
        """
        Draws text at the grid cell defined by pos.
        """
        font = self.font_bold if bold else self.font
        surface = font.render(text, True, color)
        pixel_pos = (pos[0] * CELL_SIZE_X, pos[1] * CELL_SIZE_Y)
        self.screen.blit(surface, pixel_pos)

    def _dim_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """
        Returns a dimmed version of the provided color.
        """
        DIM_FACTOR = 2  # You may adjust this factor for different dimming levels
        return (color[0] // DIM_FACTOR, color[1] // DIM_FACTOR, color[2] // DIM_FACTOR)

    def draw_stage(
        self,
        hours: int,
        player: d.Player,
        entities: List[d.Entity],
        field: List[List[str]],
        cur_torched: List[List[int]],
        torched: List[List[int]],
        encountered_types: Set[str],
        show_entities: bool,
        stage_num: int = 0,
        message: Optional[str] = None,
        extra_keys: bool = False,
    ):
        """
        Renders the game stage:
        - Clears the screen.
        - Draws the field and its cells.
        - Draws the player and entities with appropriate colors.
        - Draws the status bar at the bottom.
        """
        self.screen.fill((0, 0, 0))
        px, py = player.x, player.y

        # Draw player's companion if present
        if player.companion is not None and px + 1 < d.FIELD_WIDTH:
            char = player.companion.tribe.char
            self._draw_text(
                (px + 1, py),
                char,
                self._dim_color(COLOR_MAP["default"]),
                bold=True,
            )

        # Draw field cells
        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                pos = x, y
                if cur_torched[y][x]:
                    if cell == d.WALL_CHAR:
                        self._draw_text(pos, cell, COLOR_MAP[CI_GREEN])
                    elif cell == d.CHAR_CALTROP:
                        self._draw_text(pos, cell, COLOR_MAP[CI_MAGENTA])
                    else:
                        self._draw_text(pos, cell, COLOR_MAP["default"])
                elif torched[y][x] or show_entities:
                    if cell == d.WALL_CHAR:
                        self._draw_text(pos, cell, COLOR_MAP[CI_GREEN])
                    elif cell == " " and (x + y) % 2 == 1:
                        self._draw_text(pos, ".", self._dim_color(COLOR_MAP["default"]))
                    else:
                        self._draw_text(pos, cell, COLOR_MAP["default"])
                else:
                    if (x + y) % 2 == 1:
                        self._draw_text(pos, ".", self._dim_color(COLOR_MAP["default"]))

        # Draw the player character
        self._draw_text((px, py), "@", COLOR_MAP[CI_YELLOW], bold=True)

        # Draw entities (monster and treasures)
        player_attack = d.player_attack_by_level(player)

        if show_entities:
            for ei, e in enumerate(entities):
                pos = e.x, e.y
                ch = None
                if isinstance(e, (d.Companion, d.Monster)):
                    ch = e.tribe.char
                elif isinstance(e, d.Treasure):
                    ch = d.CHAR_TREASURE
                if ch is not None:
                    self._draw_text(pos, ch, self._dim_color(COLOR_MAP["default"]))

        for ei, e in enumerate(entities):
            pos = e.x, e.y
            if torched[e.y][e.x] == 0 or pos == (px, py):
                continue
            if isinstance(e, d.Companion):
                c: d.Companion = e
                ch = c.tribe.char
                if ch not in encountered_types and not show_entities:
                    ch = "!"
                self._draw_text(pos, ch, COLOR_MAP["default"], bold=True)
            elif isinstance(e, d.Monster):
                m: d.Monster = e
                ch = m.tribe.char
                if ch not in encountered_types:
                    if not show_entities:
                        ch = "!" if m.tribe.level == 0 else "?"
                        self._draw_text(pos, ch, COLOR_MAP["default"], bold=True)
                else:
                    if m.tribe.level <= player_attack:
                        if m.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
                            ci = CI_YELLOW
                        else:
                            ci = CI_BLUE
                    else:
                        ci = CI_RED
                    self._draw_text(pos, ch, COLOR_MAP[ci], bold=True)
            elif isinstance(e, d.Treasure):
                t: d.Treasure = e
                if t.encounter_type in encountered_types:
                    self._draw_text(pos, d.CHAR_TREASURE, COLOR_MAP[CI_YELLOW], bold=True)

        # Draw the status bar
        self.draw_status_bar(hours, player, stage_num, message, extra_keys)

        pygame.display.flip()
        self.clock.tick(30)

    def draw_status_bar(
        self,
        hours: int,
        player: d.Player,
        stage_num: int,
        message: Optional[str],
        extra_keys: bool,
    ):
        """
        Draws the status bar at the bottom of the screen similar to the curses version.
        This includes stage, hours, level (with item modifiers), item info,
        beatable monsters, LP value, and a rectangular LP bar (using original pygame drawing).
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

        status_line = ""
        if stage_num != 0:
            status_line += "ST: %d  " % stage_num
        status_line += "HRS: %d  " % hours
        status_line += level_str + "  "
        status_line += item_str + "  "
        if beatable:
            status_line += ">%s  " % ",".join(b.char for b in beatable)
        status_line += "LP: "

        self._draw_text((0, self.field_height), status_line, COLOR_MAP["default"])
        text_width, _ = self.font.size(status_line)
        x_offset = text_width + 10

        lp_str = "%d " % player.lp
        lp_x_cell = x_offset // CELL_SIZE_X
        self._draw_text((lp_x_cell, self.field_height), lp_str, COLOR_MAP["default"])
        lp_width, _ = self.font.size(lp_str)
        x_offset += lp_width

        bar_cells = 4
        bar_width = bar_cells * CELL_SIZE_X
        bar_height = CELL_SIZE_Y // 2
        y_offset = self.field_height * CELL_SIZE_Y + (CELL_SIZE_Y - bar_height) // 2
        progress_ratio = player.lp / d.LP_MAX
        fill_width = int(bar_width * progress_ratio)
        lp_color = COLOR_MAP[CI_RED] if player.lp < 20 else COLOR_MAP["default"]

        border_rect = pygame.Rect(x_offset, y_offset, bar_width, bar_height)
        pygame.draw.rect(self.screen, COLOR_MAP["default"], border_rect, 1)
        fill_rect = pygame.Rect(x_offset, y_offset, fill_width, bar_height)
        pygame.draw.rect(self.screen, lp_color, fill_rect)

        extra = "/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit"
        item_status = "  ".join([item_str, extra])
        item_x_offset = x_offset + bar_width + 10
        self._draw_text((item_x_offset // CELL_SIZE_X, self.field_height), item_status, COLOR_MAP["default"])

        if message:
            self._draw_text((0, self.field_height + 1), message, COLOR_MAP["default"], bold=True)

    def input_direction(self) -> Optional[Tuple[int, int]]:
        """
        Waits for a directional input.
        Returns a tuple (dx, dy) if an arrow key, WASD key, or D-pad.
        Returns if ESC or 'q' is pressed.
        """
        while True:
            # Scan keyboard
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

            if self.joystick:
                # Scan joystick
                hat = self.joystick.get_hat(0)
                current_direction: Tuple[int, int] = (int(hat[0]), int(-hat[1]))

                if current_direction != self.joystick_previous_direction:
                    self.joystick_previous_direction = current_direction
                    self.joystick_interval_timer = 0
                else:
                    self.joystick_interval_timer = (self.joystick_interval_timer + 1) % 7
                if self.joystick_interval_timer == 0 and current_direction != (0, 0):
                    return current_direction

            self.clock.tick(30)

    def input_alphabet(self) -> Optional[str]:
        """
        Waits for an alphabetic key input.
        Returns the key in lowercase, or None if ESC or 'q' is pressed.
        """
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        return None
                    key_name = pygame.key.name(event.key)
                    return key_name.lower()
            self.clock.tick(30)

    def quit(self):
        """Terminates the Pygame session."""
        pygame.quit()

    def select_stage(self) -> int:
        """
        Displays a stage selection menu using Pygame where the user can navigate with arrow keys or D-pad,
        and confirm with Enter (or gamepad button 0), or directly press numeric keys or Q/ESC.

        The selected option is shown with a leading ">" and non-selected options with a blank.

        Returns:
            int: The selected stage number (1, 2, ...), or 0 if "Quit" is chosen.
        """
        # Determine the number of stages from defs
        num_stages = len(d.STAGE_TO_SPAWN_CONFIGS)
        assert num_stages <= 9

        # Build options list; index 0 is "Quit"
        options = ["[q]uit"]
        for n in range(1, num_stages + 1):
            options.append(f"stage [{n}]")

        current_index = 1  # Initial selection: stage 1

        while True:
            # Clear screen and draw menu background
            self.screen.fill((0, 0, 0))
            # Draw title
            self._draw_text((10, 5), "Stage Selection", COLOR_MAP[CI_YELLOW], bold=True)

            base_x = 10
            base_y = 8
            # Draw each option with prefix ">" for the current selection
            for i, option in enumerate(options):
                prefix = ">" if i == current_index else " "
                self._draw_text(
                    (base_x, base_y + i),
                    f"{prefix} {option}",
                    COLOR_MAP["default"],
                    bold=(i == current_index),
                )

            pygame.display.flip()

            # Wait for an event
            event = pygame.event.wait()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    current_index = (current_index - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    current_index = (current_index + 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return current_index  # Index 0 means Quit; 1,2,... correspond to stages.
                elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return 0
                # Check if a numeric key (1～9) is pressed.
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    n = event.key - pygame.K_0  # Convert key code to corresponding number.
                    if n <= num_stages:
                        return n

            elif event.type == pygame.JOYHATMOTION:
                hat = event.value  # (x, y)
                if hat[1] != 0:
                    current_index = (current_index - hat[1]) % len(options)

            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    return current_index
