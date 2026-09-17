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
    CI_RED: (220, 82, 82),
    CI_GREEN: (104, 196, 128),
    CI_YELLOW: (244, 190, 78),
    CI_BLUE: (92, 154, 224),
    CI_MAGENTA: (188, 104, 174),
    CI_CYAN: (92, 190, 196),
    "default": (226, 230, 238),
}

BACKGROUND = (12, 14, 18)
FOG = (22, 25, 31)
FLOOR = (31, 38, 48)
WALL = (67, 73, 84)
VISIBLE_FLOOR = (43, 52, 65)
VISIBLE_WALL = (86, 96, 111)

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
        self.map_mode = False

    def _display_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        if not self.map_mode:
            return color
        value = int(color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114)
        return (value, value, value)

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
        surface = font.render(text, True, self._display_color(color))
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
        checkpoint: Optional[d.Point] = None,
    ):
        """
        Renders the game stage:
        - Clears the screen.
        - Draws the field and its cells.
        - Draws the player and entities with appropriate colors.
        - Draws the status bar at the bottom.
        """
        show_entities = show_entities or self.map_mode
        self.screen.fill(BACKGROUND)
        px, py = player.x, player.y

        # Rust GUI uses a dark tile map: unexplored cells are nearly black,
        # explored floor is blue-gray, and walls are solid blocks.
        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                discovered = bool(torched[y][x] or show_entities)
                if cur_torched[y][x]:
                    tile_color = VISIBLE_WALL if cell == d.WALL_CHAR else VISIBLE_FLOOR
                elif discovered:
                    tile_color = WALL if cell == d.WALL_CHAR else FLOOR
                else:
                    tile_color = FOG
                if cell == d.CHAR_CALTROP and discovered:
                    tile_color = (132, 70, 60)
                if cell == d.CHAR_BARRIER and discovered:
                    tile_color = (67, 42, 45)
                pygame.draw.rect(
                    self.screen,
                    self._display_color(tile_color),
                    pygame.Rect(x * CELL_SIZE_X, y * CELL_SIZE_Y, CELL_SIZE_X + 1, CELL_SIZE_Y + 1),
                )

                # Glyph-like stage markers remain text, as in the Rust GUI.
                if discovered and cell in ("^", "v"):
                    self._draw_text((x, y), cell, COLOR_MAP[CI_YELLOW], bold=True)
                elif discovered and cell == d.CHAR_BARRIER:
                    pygame.draw.line(
                        self.screen,
                        self._display_color(COLOR_MAP[CI_RED]),
                        (x * CELL_SIZE_X + 2, y * CELL_SIZE_Y + CELL_SIZE_Y // 2),
                        (x * CELL_SIZE_X + CELL_SIZE_X - 2, y * CELL_SIZE_Y + CELL_SIZE_Y // 2),
                        2,
                    )

        self._draw_visibility_boundary(cur_torched)

        if checkpoint is not None and checkpoint != (px, py):
            self._draw_text(checkpoint, "+", COLOR_MAP[CI_YELLOW], bold=True)

        # Draw the player character
        player_color = COLOR_MAP[CI_MAGENTA] if player.item == d.ITEM_POISONED else COLOR_MAP["default"]
        self._draw_text((px, py), "@", player_color, bold=True)

        if player.companion is not None and px + 1 < d.FIELD_WIDTH:
            self._draw_text((px + 1, py), player.companion.tribe.char, COLOR_MAP[CI_GREEN], bold=True)

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
                self._draw_text(pos, ch, COLOR_MAP[CI_GREEN], bold=True)
            elif isinstance(e, d.Monster):
                m: d.Monster = e
                ch = m.tribe.char
                if ch not in encountered_types:
                    if not show_entities:
                        self._draw_text(pos, "?", COLOR_MAP[CI_YELLOW], bold=True)
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

        # Stage 3 followers persist across floor changes and are rendered
        # independently of the temporary companion slot.
        for fx, fy, ffloor, fchar in getattr(player, "persistent_followers", []):
            if ffloor == getattr(player, "stage3_floor", 0) and 0 <= fy < len(torched) and 0 <= fx < len(torched[0]) and torched[fy][fx] and (fx, fy) != (px, py):
                self._draw_text((fx, fy), fchar, COLOR_MAP[CI_GREEN], bold=True)

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
        if stage_num == 3:
            status_line += "ST: 3 F:%d  " % (getattr(player, "stage3_floor", 0) + 1)
        elif stage_num != 0:
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
        item_status = extra if stage_num == 3 else "  ".join([item_str, extra])
        item_x_offset = x_offset + bar_width + 10
        self._draw_text((item_x_offset // CELL_SIZE_X, self.field_height), item_status, COLOR_MAP["default"])

        if stage_num == 3:
            progress = (("C", 1), ("I", 2), ("J", 64), ("K", 4), ("H", 8), ("W", 16))
            for index, (label, bit) in enumerate(progress):
                color = COLOR_MAP["default"] if player.stage3_flags & bit else (100, 106, 118)
                self._draw_text((index * 2, self.field_height + 1), label, color, bold=True)
            treasure_collected = getattr(player, "stage3_won", False)
            self._draw_text(
                (len(progress) * 2, self.field_height + 1),
                "T",
                COLOR_MAP["default"] if treasure_collected else (100, 106, 118),
                bold=True,
            )
            if message:
                self._draw_text((16, self.field_height + 1), message, COLOR_MAP[CI_YELLOW], bold=True)
        elif message:
            self._draw_text((0, self.field_height + 1), message, COLOR_MAP["default"], bold=True)

    def _draw_visibility_boundary(self, visibility: List[List[int]]) -> None:
        """Draw the Rust-style outline around the currently visible area."""
        if not visibility:
            return
        height = len(visibility)
        width = len(visibility[0])
        boundary_color = self._display_color((125, 180, 235))
        line_width = 2
        for y in range(height):
            for x in range(width):
                if not visibility[y][x]:
                    continue
                left = x * CELL_SIZE_X
                top = y * CELL_SIZE_Y
                right = left + CELL_SIZE_X
                bottom = top + CELL_SIZE_Y
                if y == 0 or not visibility[y - 1][x]:
                    pygame.draw.line(self.screen, boundary_color, (left, top), (right, top), line_width)
                if y + 1 == height or not visibility[y + 1][x]:
                    pygame.draw.line(self.screen, boundary_color, (left, bottom), (right, bottom), line_width)
                if x == 0 or not visibility[y][x - 1]:
                    pygame.draw.line(self.screen, boundary_color, (left, top), (left, bottom), line_width)
                if x + 1 == width or not visibility[y][x + 1]:
                    pygame.draw.line(self.screen, boundary_color, (right, top), (right, bottom), line_width)

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
                    if event.key == pygame.K_m:
                        self.map_mode = True
                        return (0, 0)
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
