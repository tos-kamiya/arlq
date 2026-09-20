import time
from typing import Optional, Tuple, List, Set

import pyglet
from pyglet.window import key as pgkey

from .__about__ import __version__
from . import defs as d

# RGB colors corresponding to terminal color names
CI_RED = 1
CI_GREEN = 2
CI_YELLOW = 3
CI_BLUE = 4
CI_MAGENTA = 5
CI_CYAN = 6

# Color mapping for the GUI renderer
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

# Keys that map to a movement direction, shared by input_direction().
_DIRECTION_KEYS = {
    pgkey.UP: (0, -1),
    pgkey.W: (0, -1),
    pgkey.DOWN: (0, 1),
    pgkey.S: (0, 1),
    pgkey.LEFT: (-1, 0),
    pgkey.A: (-1, 0),
    pgkey.RIGHT: (1, 0),
    pgkey.D: (1, 0),
}

# Digit key constants are named "_1".."_9" in pyglet.window.key; build a
# lookup from key symbol to the digit character.
_DIGIT_KEYS = {getattr(pgkey, "_%d" % n): "%d" % n for n in range(1, 10)}


class PygletUI:
    def __init__(self):
        # Field dimensions from defs
        self.field_width = d.FIELD_WIDTH
        self.field_height = d.FIELD_HEIGHT

        # Calculate window dimensions (including status bar area and the
        # right-edge strength column, one extra cell wide)
        self.window_width = (self.field_width + 1) * CELL_SIZE_X
        self.window_height = (self.field_height + 2) * CELL_SIZE_Y

        self.window = pyglet.window.Window(
            width=self.window_width,
            height=self.window_height,
            caption=f"Arlq (Pyglet mix) v{__version__}",
        )
        self.window.set_mouse_visible(False)

        self.font_name = "Courier New"
        self.font_size = int(CELL_SIZE_Y * 0.82)

        self.batch = pyglet.graphics.Batch()
        self._drawables: list = []

        self._closed = False
        self._key_queue: list = []

        window = self.window

        @window.event
        def on_close():
            self._closed = True

        @window.event
        def on_key_press(symbol, modifiers):
            self._key_queue.append(symbol)

        joysticks = pyglet.input.get_joysticks()
        joystick = None
        if joysticks:
            joystick = joysticks[0]
            try:
                joystick.open()
            except Exception:
                joystick = None
        self.joystick = joystick

        self.joystick_interval_timer = 0
        self.joystick_previous_direction = None
        self.map_mode = False

    def _display_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        if not self.map_mode:
            return color
        value = int(color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114)
        return (value, value, value)

    def _dim_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        DIM_FACTOR = 2
        return (color[0] // DIM_FACTOR, color[1] // DIM_FACTOR, color[2] // DIM_FACTOR)

    def _clear_drawables(self):
        for obj in self._drawables:
            obj.delete()
        self._drawables = []

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
        label = pyglet.text.Label(
            text,
            font_name=self.font_name,
            font_size=self.font_size,
            weight="bold" if bold else "normal",
            x=pos[0] * CELL_SIZE_X,
            y=self.window_height - pos[1] * CELL_SIZE_Y,
            anchor_x="left",
            anchor_y="top",
            color=(*self._display_color(color), 255),
            batch=self.batch,
        )
        self._drawables.append(label)

    def _draw_rect(self, x: int, y: int, width: int, height: int, color: Tuple[int, int, int]):
        rect = pyglet.shapes.Rectangle(
            x,
            self.window_height - y - height,
            width,
            height,
            color=self._display_color(color),
            batch=self.batch,
        )
        self._drawables.append(rect)

    def _draw_line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Tuple[int, int, int],
        thickness: int = 1,
    ):
        line = pyglet.shapes.Line(
            x1,
            self.window_height - y1,
            x2,
            self.window_height - y2,
            thickness=thickness,
            color=self._display_color(color),
            batch=self.batch,
        )
        self._drawables.append(line)

    def draw_stage(
        self,
        hours: int,
        player: d.Player,
        entities: List[d.Entity],
        field: List[List[str]],
        cur_torched: List[List[int]],
        torched: List[List[int]],
        known_types: Set[str],
        show_entities: bool,
        stage_num: int = 0,
        message: Optional[str] = None,
        extra_keys: bool = False,
        checkpoint: Optional[d.Point] = None,
        unlocked_treasures: Optional[Set[str]] = None,
        dim_types: Optional[Set[str]] = None,
        stage_roster: Optional[List[d.MonsterTribe]] = None,
    ):
        """
        Renders the game stage:
        - Clears the screen.
        - Draws the field and its cells.
        - Draws the player and entities with appropriate colors.
        - Draws the status bar at the bottom.
        """
        show_entities = show_entities or self.map_mode
        self._clear_drawables()
        px, py = player.x, player.y

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
                self._draw_rect(
                    x * CELL_SIZE_X,
                    y * CELL_SIZE_Y,
                    CELL_SIZE_X + 1,
                    CELL_SIZE_Y + 1,
                    tile_color,
                )

                if discovered and cell in ("^", "v"):
                    self._draw_text((x, y), cell, COLOR_MAP[CI_YELLOW], bold=True)
                elif discovered and cell == d.CHAR_BARRIER:
                    self._draw_line(
                        x * CELL_SIZE_X + 2,
                        y * CELL_SIZE_Y + CELL_SIZE_Y // 2,
                        x * CELL_SIZE_X + CELL_SIZE_X - 2,
                        y * CELL_SIZE_Y + CELL_SIZE_Y // 2,
                        COLOR_MAP[CI_RED],
                        thickness=2,
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
                    if isinstance(e, d.Monster) and e.empowered > 1:
                        self._draw_text((e.x + 1, e.y), "'", self._dim_color(COLOR_MAP["default"]))

        for ei, e in enumerate(entities):
            pos = e.x, e.y
            if torched[e.y][e.x] == 0 or pos == (px, py):
                continue
            if isinstance(e, d.Companion):
                c: d.Companion = e
                ch = c.tribe.char
                if ch not in known_types and not show_entities:
                    ch = "!"
                self._draw_text(pos, ch, COLOR_MAP[CI_GREEN], bold=True)
            elif isinstance(e, d.Monster):
                m: d.Monster = e
                ch = m.tribe.char
                type_key = d.monster_type_key(m)
                if type_key not in known_types:
                    if not show_entities:
                        self._draw_text(pos, "?", COLOR_MAP[CI_YELLOW], bold=True)
                else:
                    if d.monster_level(m) <= player_attack:
                        if m.tribe.effect == d.EFFECT_UNLOCK_TREASURE:
                            ci = CI_YELLOW
                        else:
                            ci = CI_BLUE
                    else:
                        ci = CI_RED
                    color = self._dim_color(COLOR_MAP[ci]) if dim_types and ch in dim_types else COLOR_MAP[ci]
                    self._draw_text(pos, ch, color, bold=True)
                    if m.empowered > 1:
                        self._draw_text((m.x + 1, m.y), "'", color, bold=True)
            elif isinstance(e, d.Treasure):
                t: d.Treasure = e
                treasure_unlocked = unlocked_treasures is not None and t.unlock_key in unlocked_treasures
                if treasure_unlocked:
                    self._draw_text(pos, d.CHAR_TREASURE, COLOR_MAP[CI_YELLOW], bold=True)

        # Stage 3 followers persist across floor changes and are rendered
        # independently of the temporary companion slot.
        for fx, fy, ffloor, fchar in getattr(player, "persistent_followers", []):
            if ffloor == player.stage3_floor and 0 <= fy < len(torched) and 0 <= fx < len(torched[0]) and torched[fy][fx] and (fx, fy) != (px, py):
                self._draw_text((fx, fy), fchar, COLOR_MAP[CI_GREEN], bold=True)

        # Draw the right-edge strength column: the stage's monster tribes and
        # the player, ranked strongest-first.
        tribes = stage_roster if stage_roster is not None else (
            d.get_stage_roster_tribes(stage_num) if stage_num in (1, 2) else []
        )
        ranking_attack = d.player_attack_by_level(player, include_stage3_bonuses=stage_num == 3)
        for y, (char, is_player) in enumerate(d.build_strength_column(tribes, ranking_attack, self.field_height)):
            if char is None:
                continue
            self._draw_text((self.field_width, y), char, COLOR_MAP["default"], bold=is_player)

        # Draw the status bar
        self.draw_status_bar(hours, player, stage_num, message, extra_keys)

        self._flip()

    def draw_status_bar(
        self,
        hours: int,
        player: d.Player,
        stage_num: int,
        message: Optional[str],
        extra_keys: bool,
    ):
        """
        Draws the status bar at the bottom of the screen similar to the terminal version.
        This includes stage, hours, level (with item modifiers), item info,
        beatable monsters, LP value, and a rectangular LP bar.
        """
        has_stage3_k = stage_num == 3 and getattr(player, "stage3_flags", 0) & d.STAGE3_K_FLAG
        has_stage3_j = stage_num == 3 and any(
            follower[3] == "J" for follower in getattr(player, "persistent_followers", [])
        )
        if player.item == d.ITEM_SWORD_X1_5:
            level_str = "LVL: %d x1.5" % player.level
            item_str = "+%s(%s)" % (player.item, player.item_taken_from)
        elif player.item == d.ITEM_SWORD_CURSED:
            level_str = "LVL: %d x3" % player.level
            item_str = "+%s(%s)" % (player.item, player.item_taken_from)
        elif player.item == d.ITEM_POISONED:
            level_str = "LVL: %d /2" % player.level
            if has_stage3_k:
                level_str += " x1.2"
            item_str = "+%s(%s)" % (player.item, player.item_taken_from)
        else:
            level_str = "LVL: %d" % player.level
            if has_stage3_k:
                level_str += " x1.2"
            item_str = ""
        if has_stage3_j:
            level_str += " +25%"

        status_line = ""
        if stage_num == 3:
            status_line += "ST: 3 F:%d  " % (player.stage3_floor + 1)
        elif stage_num != 0:
            status_line += "ST: %d  " % stage_num
        status_line += "HRS: %d  " % hours
        status_line += level_str + "  "
        status_line += item_str + "  "
        status_line += "LP: "

        self._draw_text((0, self.field_height), status_line, COLOR_MAP["default"])
        text_width = self._text_width(status_line)
        x_offset = text_width + 10

        lp_str = "%d " % player.lp
        lp_x_cell = x_offset // CELL_SIZE_X
        self._draw_text((lp_x_cell, self.field_height), lp_str, COLOR_MAP["default"])
        lp_width = self._text_width(lp_str)
        x_offset += lp_width

        bar_cells = 8
        bar_width = bar_cells * CELL_SIZE_X
        bar_height = CELL_SIZE_Y // 2
        y_offset = self.field_height * CELL_SIZE_Y + (CELL_SIZE_Y - bar_height) // 2
        progress_ratio = player.lp / d.LP_MAX
        fill_width = int(bar_width * progress_ratio)
        lp_color = COLOR_MAP[CI_RED] if player.lp < 20 else COLOR_MAP["default"]

        self._draw_rect_outline(x_offset, y_offset, bar_width, bar_height, COLOR_MAP["default"])
        if fill_width > 0:
            self._draw_rect(x_offset, y_offset, fill_width, bar_height, lp_color)

        extra = "/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit"
        item_status = extra if stage_num == 3 else "  ".join([item_str, extra])
        item_x_offset = x_offset + bar_width + 10
        self._draw_text((item_x_offset // CELL_SIZE_X, self.field_height), item_status, COLOR_MAP["default"])

        if stage_num == 3:
            progress = (("C", 1), ("I", 2), ("J", 64), ("K", 4), ("H", 8), ("W", 16))
            elf_floors = getattr(player, "stage3_elf_floors", {})
            show_elf_floors = getattr(player, "stage3_flags", 0) & d.STAGE3_I_FLAG
            progress_x = 0
            for label, bit in progress:
                color = COLOR_MAP["default"] if player.stage3_flags & bit else (100, 106, 118)
                progress_label = label
                if show_elf_floors and label in elf_floors:
                    progress_label += str(elf_floors[label])
                self._draw_text((progress_x, self.field_height + 1), progress_label, color, bold=True)
                progress_x += len(progress_label) + 1
            treasure_collected = player.stage3_won
            self._draw_text(
                (progress_x, self.field_height + 1),
                "T",
                COLOR_MAP["default"] if treasure_collected else (100, 106, 118),
                bold=True,
            )
            if message:
                self._draw_text((16, self.field_height + 1), message, COLOR_MAP[CI_YELLOW], bold=True)
        elif message:
            self._draw_text((0, self.field_height + 1), message, COLOR_MAP["default"], bold=True)

    def _text_width(self, text: str) -> int:
        label = pyglet.text.Label(text, font_name=self.font_name, font_size=self.font_size)
        width = label.content_width
        label.delete()
        return width

    def _draw_rect_outline(self, x: int, y: int, width: int, height: int, color: Tuple[int, int, int]):
        self._draw_line(x, y, x + width, y, color)
        self._draw_line(x, y + height, x + width, y + height, color)
        self._draw_line(x, y, x, y + height, color)
        self._draw_line(x + width, y, x + width, y + height, color)

    def _draw_visibility_boundary(self, visibility: List[List[int]]) -> None:
        """Draw the outline around the currently visible area."""
        if not visibility:
            return
        height = len(visibility)
        width = len(visibility[0])
        boundary_color = (125, 180, 235)
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
                    self._draw_line(left, top, right, top, boundary_color, thickness=line_width)
                if y + 1 == height or not visibility[y + 1][x]:
                    self._draw_line(left, bottom, right, bottom, boundary_color, thickness=line_width)
                if x == 0 or not visibility[y][x - 1]:
                    self._draw_line(left, top, left, bottom, boundary_color, thickness=line_width)
                if x + 1 == width or not visibility[y][x + 1]:
                    self._draw_line(right, top, right, bottom, boundary_color, thickness=line_width)

    def _flip(self):
        self.window.switch_to()
        self.window.clear()
        self.batch.draw()
        self.window.flip()

    def _pump(self):
        self.window.dispatch_events()

    def _next_key(self) -> Optional[int]:
        """Pops the oldest queued key symbol, or None if no key is queued."""
        if self._key_queue:
            return self._key_queue.pop(0)
        return None

    def input_direction(self) -> Optional[Tuple[int, int]]:
        """
        Waits for a directional input.
        Returns a tuple (dx, dy) if an arrow key, WASD key, or D-pad.
        Returns None if ESC or 'q' is pressed, or the window is closed.
        """
        while True:
            self._pump()
            if self._closed:
                return None

            while self._key_queue:
                symbol = self._next_key()
                if symbol == pgkey.M:
                    self.map_mode = True
                    return (0, 0)
                if symbol in (pgkey.ESCAPE, pgkey.Q):
                    return None
                if symbol in _DIRECTION_KEYS:
                    return _DIRECTION_KEYS[symbol]

            if self.joystick:
                hat_x = int(self.joystick.hat_x)
                hat_y = int(self.joystick.hat_y)
                current_direction: Tuple[int, int] = (hat_x, -hat_y)

                if current_direction != self.joystick_previous_direction:
                    self.joystick_previous_direction = current_direction
                    self.joystick_interval_timer = 0
                else:
                    self.joystick_interval_timer = (self.joystick_interval_timer + 1) % 7
                if self.joystick_interval_timer == 0 and current_direction != (0, 0):
                    return current_direction

            time.sleep(1 / 30)

    def input_alphabet(self) -> Optional[str]:
        """
        Waits for an alphabetic key input.
        Returns the key in lowercase, or None if ESC or 'q' is pressed.
        """
        while True:
            self._pump()
            if self._closed:
                return None

            while self._key_queue:
                symbol = self._key_queue.pop(0)
                if symbol in (pgkey.ESCAPE, pgkey.Q):
                    return None
                if symbol in _DIGIT_KEYS:
                    return _DIGIT_KEYS[symbol]
                key_name = pgkey.symbol_string(symbol)
                return key_name.lower()

            time.sleep(1 / 30)

    def quit(self):
        """Closes the game window."""
        self.window.close()

    def select_stage(self) -> int:
        """
        Displays a stage selection menu where the user can navigate with arrow keys or D-pad,
        and confirm with Enter (or gamepad button 0), or directly press numeric keys or Q/ESC.

        The selected option is shown with a leading ">" and non-selected options with a blank.

        Returns:
            int: The selected stage number (1, 2, ...), or 0 if "Quit" is chosen.
        """
        num_stages = len(d.STAGE_TO_SPAWN_CONFIGS)
        assert num_stages <= 9

        options = ["[q]uit"]
        for n in range(1, num_stages + 1):
            options.append(f"stage [{n}]")

        current_index = 1  # Initial selection: stage 1

        while True:
            self._clear_drawables()
            self._draw_text((10, 5), "Stage Selection", COLOR_MAP[CI_YELLOW], bold=True)

            base_x = 10
            base_y = 8
            for i, option in enumerate(options):
                prefix = ">" if i == current_index else " "
                self._draw_text(
                    (base_x, base_y + i),
                    f"{prefix} {option}",
                    COLOR_MAP["default"],
                    bold=(i == current_index),
                )

            self._flip()

            while True:
                self._pump()
                if self._closed:
                    return 0

                if self.joystick and self.joystick.buttons and self.joystick.buttons[0]:
                    return current_index

                symbol = self._next_key()
                if symbol is not None:
                    if symbol == pgkey.UP:
                        current_index = (current_index - 1) % len(options)
                    elif symbol == pgkey.DOWN:
                        current_index = (current_index + 1) % len(options)
                    elif symbol in (pgkey.RETURN, pgkey.NUM_ENTER):
                        return current_index
                    elif symbol in (pgkey.Q, pgkey.ESCAPE):
                        return 0
                    elif symbol in _DIGIT_KEYS:
                        n = int(_DIGIT_KEYS[symbol])
                        if n <= num_stages:
                            return n
                    break

                if self.joystick:
                    hat_y = int(self.joystick.hat_y)
                    if hat_y != self.joystick_previous_direction:
                        self.joystick_previous_direction = hat_y
                        if hat_y != 0:
                            current_index = (current_index - hat_y) % len(options)
                            break

                time.sleep(1 / 30)
