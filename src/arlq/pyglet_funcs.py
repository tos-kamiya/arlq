import locale
import json
import math
import sys
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple

from appdirs import user_config_dir


def _prepare_x11_locale() -> None:
    """Keep Pyglet's X11 window properties usable in the C locale.

    Pyglet selects its X11 title-property encoding from the process locale.
    With ``LC_ALL=C`` it uses the legacy STRING property, which some window
    managers display as an empty title.  The C.UTF-8 locale is sufficient for
    Pyglet's X11 UTF-8 property path and does not change the UI language
    selected by :mod:`arlq.i18n` (that is resolved before this module loads).
    """
    if sys.platform != "linux":
        return

    try:
        encoding = locale.getlocale(locale.LC_CTYPE)[1]
        if encoding and encoding.upper().replace("-", "") == "UTF8":
            return
        for candidate in ("C.UTF-8", "C.utf8"):
            try:
                locale.setlocale(locale.LC_CTYPE, candidate)
                return
            except locale.Error:
                continue
    except (locale.Error, IndexError):
        pass


_prepare_x11_locale()

import pyglet
from pyglet.window import key as pgkey

from .__about__ import __version__
from . import defs as d
from . import display as ui_display
from .arlq import barrier_lp_damage
from .i18n import t as tr

# "Courier New" (the game's normal font) has no Japanese glyphs, so a label
# containing translated text would render as tofu boxes. Rather than
# hardcoding specific Japanese font names (which assumes a particular OS and
# language), non-ASCII text is requested by generic family name instead:
# "monospace", then "sans-serif". The OS's own font-substitution logic (e.g.
# fontconfig on Linux) resolves these based on the current locale, so a
# Japanese-locale system already tends to substitute a Japanese-capable font
# with no locale-specific names needed here. If neither resolves, the game's
# normal font is used unchanged (no fonts are bundled with the package).
NON_ASCII_FONT_CANDIDATES = ["monospace", "sans-serif"]

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
_TONE_INDEX = {
    "red": CI_RED,
    "green": CI_GREEN,
    "yellow": CI_YELLOW,
    "blue": CI_BLUE,
    "magenta": CI_MAGENTA,
}

BACKGROUND = (12, 14, 18)
FOG = (22, 25, 31)
FLOOR = (31, 38, 48)
WALL = (67, 73, 84)
VISIBLE_FLOOR = (43, 52, 65)
VISIBLE_WALL = (86, 96, 111)
REACHABLE_CELL_COLOR = (91, 129, 180)
STRENGTH_COLUMN_BG = (30, 34, 48)
STRENGTH_COLUMN_PADDING = 4

CELL_SIZE_Y = 20
CELL_SIZE_X = 13
FONT_WIDTH_RATIO = 0.95
FONT_HEIGHT_RATIO = 0.87
MESSAGE_FONT_SIZE_SCALE = 0.95
MENU_ROW_SPACING = 1.2

MIN_UI_SCALE = 0.5
MAX_UI_SCALE = 4.0
UI_SCALE_CHOICES = tuple(n / 100 for n in range(50, 401, 25))
KEY_REPEAT_CHOICES = tuple(n / 10 for n in range(1, 11)) + (None,)


def _settings_path() -> Path:
    return Path(user_config_dir("arlq")) / "settings.json"


def _load_settings() -> dict:
    try:
        value = json.loads(_settings_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def load_ui_scale() -> float:
    """Load the saved GUI scale, falling back safely to the default."""
    try:
        value = _load_settings().get("scale", 1.0)
        value = float(value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, AttributeError):
        return 1.0
    return min(MAX_UI_SCALE, max(MIN_UI_SCALE, value))


def save_ui_scale(scale: float) -> None:
    """Persist the GUI scale in the user's platform configuration directory."""
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        settings = _load_settings()
        settings["scale"] = scale
        path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError:
        # A read-only or unusual environment should not prevent the game from
        # starting; the setting simply will not persist in that case.
        pass


def save_key_repeat_interval(interval: Optional[float]) -> None:
    """Persist the GUI key repeat interval without discarding other settings."""
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        settings = _load_settings()
        settings["key_repeat_interval"] = PygletUI._valid_repeat_interval(interval)
        path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def load_auto_repeat_stop_enabled() -> bool:
    """Load whether automatic movement repeat should stop at game events."""
    value = _load_settings().get("auto_repeat_stop_enabled", True)
    return value if isinstance(value, bool) else True


def save_auto_repeat_stop_enabled(enabled: bool) -> None:
    """Persist the automatic repeat stop setting without discarding other settings."""
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        settings = _load_settings()
        settings["auto_repeat_stop_enabled"] = bool(enabled)
        path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass

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
    def __init__(self, scale: Optional[float] = None, key_repeat_interval: Optional[float] = None) -> None:
        # Field dimensions from defs
        self.field_width = d.FIELD_WIDTH
        self.field_height = d.FIELD_HEIGHT

        self.scale = self._valid_scale(load_ui_scale() if scale is None else scale)
        self.font_name = "Courier New"
        self._set_scaled_dimensions()

        self.window = pyglet.window.Window(
            width=self.window_width,
            height=self.window_height,
            caption=f"Arlq (Pyglet mix) v{__version__}",
        )
        self.window.set_mouse_visible(False)

        self._select_font_size()

        # Lazily resolved (font_name, size_scale) for non-ASCII text; see
        # _non_ascii_font(). None until first computed.
        self._non_ascii_font_result: Optional[Tuple[str, float]] = None

        self.batch = pyglet.graphics.Batch()
        self._drawables: list = []

        self._closed = False
        self._key_queue: list = []
        self._stage_input_active = False
        self._keyboard_farthest_preview = False
        self._gamepad_preview_held = False
        self._gamepad_preview_changed = False
        self.floor_view_reset_requested = False
        self._f_key_held = False
        self._escape_key_held = False
        self.key_repeat_interval = self._valid_repeat_interval(
            _load_settings().get("key_repeat_interval", None)
            if key_repeat_interval is None else key_repeat_interval
        )
        self.auto_repeat_stop_enabled = load_auto_repeat_stop_enabled()
        self._held_direction: Optional[Tuple[int, int]] = None
        self._held_direction_keys: Set[int] = set()
        self._next_repeat_at = 0.0
        self.input_was_repeat = False

        window = self.window

        @window.event
        def on_close():
            self._closed = True

        @window.event
        def on_key_press(symbol, modifiers):
            if symbol == pgkey.ESCAPE:
                if self._escape_key_held:
                    return pyglet.event.EVENT_HANDLED
                self._escape_key_held = True
            if self._stage_input_active and symbol in _DIRECTION_KEYS:
                if symbol in self._held_direction_keys:
                    return
                self._held_direction_keys.add(symbol)
            if self._stage_input_active and symbol == pgkey.F:
                if self._f_key_held:
                    return
                self._f_key_held = True
            self._key_queue.append((symbol, modifiers))
            if symbol == pgkey.ESCAPE:
                return pyglet.event.EVENT_HANDLED

        @window.event
        def on_key_release(symbol, modifiers):
            if symbol == pgkey.ESCAPE:
                self._escape_key_held = False
            if symbol == pgkey.F:
                self._f_key_held = False
            was_held = symbol in self._held_direction_keys
            self._held_direction_keys.discard(symbol)
            if was_held and symbol in _DIRECTION_KEYS and not any(
                _DIRECTION_KEYS[key] == self._held_direction for key in self._held_direction_keys
            ):
                self._held_direction = None
                self._next_repeat_at = 0.0

        controllers = pyglet.input.get_controllers()
        controller = None
        if controllers:
            controller = controllers[0]
            try:
                controller.open()
            except Exception:
                controller = None
        self.controller = controller

        self.gamepad_previous_direction: Optional[Tuple[int, int]] = None
        self._next_gamepad_repeat_at = 0.0
        self._gamepad_held_buttons: Set[int] = set()
        self._gamepad_pressed_buttons: Set[int] = set()
        self.map_mode = False
        self.shift_direction = False

    @staticmethod
    def _valid_scale(scale: float) -> float:
        scale = float(scale)
        if not math.isfinite(scale):
            return 1.0
        return min(MAX_UI_SCALE, max(MIN_UI_SCALE, scale))

    @staticmethod
    def _valid_repeat_interval(interval: Optional[float]) -> Optional[float]:
        if interval is None:
            return None
        try:
            interval = float(interval)
        except (ValueError, TypeError):
            return 0.2
        if not math.isfinite(interval):
            return 0.2
        return min(1.0, max(0.1, interval))

    def set_key_repeat_interval(self, interval: Optional[float]) -> None:
        self.key_repeat_interval = self._valid_repeat_interval(interval)
        save_key_repeat_interval(self.key_repeat_interval)

    def set_auto_repeat_stop_enabled(self, enabled: bool) -> None:
        self.auto_repeat_stop_enabled = bool(enabled)
        save_auto_repeat_stop_enabled(self.auto_repeat_stop_enabled)

    @staticmethod
    def _controller_direction(controller) -> Tuple[int, int]:
        """Return a cardinal direction from a controller D-pad or left stick."""
        if controller is None:
            return (0, 0)

        dpad_x = getattr(controller, "dpadx", None)
        dpad_y = getattr(controller, "dpady", None)
        if dpad_x is None or dpad_y is None:
            dpad_x = int(bool(getattr(controller, "dpright", False))) - int(
                bool(getattr(controller, "dpleft", False))
            )
            dpad_y = int(bool(getattr(controller, "dpup", False))) - int(
                bool(getattr(controller, "dpdown", False))
            )
        dpad_x = float(dpad_x or 0.0)
        dpad_y = float(dpad_y or 0.0)
        if abs(dpad_x) > 0.5 or abs(dpad_y) > 0.5:
            if abs(dpad_x) > 0.5 and abs(dpad_y) > 0.5:
                return (0, 0)
            if abs(dpad_x) > 0.5:
                return (1 if dpad_x > 0 else -1, 0)
            return (0, -1 if dpad_y > 0 else 1)

        # Pyglet normalizes controller axes to [-1, 1]. Ignore small values so
        # stick drift does not move the player, and choose one axis for the
        # game's four-direction movement.
        x = float(getattr(controller, "leftx", 0.0) or 0.0)
        y = float(getattr(controller, "lefty", 0.0) or 0.0)
        if max(abs(x), abs(y)) < 0.5:
            return (0, 0)
        if abs(x) > abs(y):
            return (1 if x > 0 else -1, 0)
        return (0, -1 if y > 0 else 1)

    def _set_scaled_dimensions(self) -> None:
        self.cell_size_x = max(1, round(CELL_SIZE_X * self.scale))
        self.cell_size_y = max(1, round(CELL_SIZE_Y * self.scale))
        self.font_size = max(1, round(self.cell_size_y * FONT_HEIGHT_RATIO))
        self.strength_column_padding = max(1, round(STRENGTH_COLUMN_PADDING * self.scale))
        self.strength_column_width = 2 * self.cell_size_x + 2 * self.strength_column_padding
        self.field_pixel_width = self.field_width * self.cell_size_x
        self.window_width = self.field_pixel_width + self.strength_column_width
        self.window_height = (self.field_height + 2) * self.cell_size_y

    def _select_font_size(self) -> None:
        """Choose a font size that best fits measured glyphs inside a cell."""
        target_size_x = self.cell_size_x / FONT_WIDTH_RATIO
        target_size_y = self.cell_size_y / FONT_HEIGHT_RATIO
        target_font_size = (target_size_x + target_size_y) / 2
        nominal_size = max(1, round(target_font_size))
        candidate_sizes = range(max(1, nominal_size - 8), nominal_size + 9)
        sample = "".join(chr(codepoint) for codepoint in range(32, 127))
        candidates = []
        try:
            for size in candidate_sizes:
                glyph_width = 0
                glyph_height = 0
                for weight in ("normal", "bold"):
                    font = pyglet.font.load(
                        self.font_name, size=size, weight=weight
                    )
                    glyphs, _ = font.get_glyphs(sample)
                    glyph_width = max(
                        glyph_width,
                        *(max(glyph.advance, glyph.width) for glyph in glyphs),
                    )
                    glyph_height = max(
                        glyph_height, *(glyph.height for glyph in glyphs)
                    )
                fits = (
                    glyph_width <= self.cell_size_x
                    and glyph_height <= self.cell_size_y
                )
                candidates.append(
                    (
                        not fits,
                        abs(size - target_font_size),
                        size,
                    )
                )
        except Exception:
            # Keep the nominal size if this platform cannot expose glyph metrics.
            return

        if candidates:
            self.font_size = min(candidates)[-1]

    def set_scale(self, scale: float, save: bool = True) -> None:
        """Resize the GUI and its grid cells without changing gameplay."""
        self.scale = self._valid_scale(scale)
        self._set_scaled_dimensions()
        self._non_ascii_font_result = None
        self._select_font_size()
        self.window.set_size(self.window_width, self.window_height)
        # Process the resize immediately.  Otherwise the stage-selection
        # screen can be drawn with the old viewport until the next key event.
        self.window.dispatch_events()
        if save:
            save_ui_scale(self.scale)

    def _display_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        if not self.map_mode:
            return color
        value = int(color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114)
        return (value, value, value)

    def _dim_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        DIM_FACTOR = 2
        return (color[0] // DIM_FACTOR, color[1] // DIM_FACTOR, color[2] // DIM_FACTOR)

    def _tone_color(self, tone: str, dim: bool = False) -> Tuple[int, int, int]:
        if tone == "black":
            color = (0, 0, 0)
        elif tone == "companion":
            color = COLOR_MAP[CI_GREEN]
        elif tone == "stair":
            color = COLOR_MAP[CI_YELLOW]
        elif tone == "default":
            color = COLOR_MAP["default"]
        else:
            color = COLOR_MAP[_TONE_INDEX[tone]]
        if dim:
            color = self._dim_color(color)
        return color

    def _clear_drawables(self):
        for obj in self._drawables:
            obj.delete()
        self._drawables = []

    def _draw_text(
        self,
        pos: Tuple[float, float],
        text: str,
        color: Tuple[int, int, int],
        bold: bool = False,
        x_offset: int = 0,
        size_scale: float = 1.0,
    ):
        """
        Draws text at the grid cell defined by pos, optionally nudged by
        `x_offset` pixels (used to inset text within a cell).
        """
        font_size: float
        if text.isascii():
            font_name, font_size = self.font_name, self.font_size * size_scale
        else:
            non_ascii_font_name, non_ascii_size_scale = self._non_ascii_font()
            font_name, font_size = (
                non_ascii_font_name,
                self.font_size * non_ascii_size_scale * size_scale,
            )
        label = pyglet.text.Label(
            text,
            font_name=font_name,
            font_size=font_size,
            weight="bold" if bold else "normal",
            x=pos[0] * self.cell_size_x + x_offset,
            y=self.window_height - pos[1] * self.cell_size_y,
            anchor_x="left",
            anchor_y="top",
            color=(*self._display_color(color), 255),
            batch=self.batch,
        )
        self._drawables.append(label)

    def _non_ascii_font(self) -> Tuple[str, float]:
        """Resolve the font (and a matching font-size scale) for non-ASCII
        text, trying generic family names in order: "monospace", then
        "sans-serif". These are resolved by the OS's own font substitution
        (e.g. fontconfig on Linux), which already accounts for the current
        locale, so no specific Japanese font names are hardcoded here.

        Falls back to the game's normal font unscaled if neither resolves.
        The size scale corrects for common Japanese fonts rendering
        noticeably taller than Courier New at the same nominal size; it is
        computed from actual font metrics rather than a fixed constant, so
        it adapts to whichever font actually gets resolved.
        """
        if self._non_ascii_font_result is not None:
            return self._non_ascii_font_result

        result = (self.font_name, 1.0)
        try:
            base_ascent = pyglet.font.load(self.font_name, size=self.font_size).ascent
        except Exception:
            base_ascent = None

        if base_ascent:
            for candidate in NON_ASCII_FONT_CANDIDATES:
                try:
                    font = pyglet.font.load(candidate, size=self.font_size)
                except Exception:
                    continue
                scale = base_ascent / font.ascent if font.ascent else 1.0
                result = (candidate, scale)
                break

        self._non_ascii_font_result = result
        return result

    def _field_col_x(self, col: int) -> int:
        """Pixel x-start of field column `col`."""
        return col * self.cell_size_x

    def _field_col_width(self, _col: int) -> int:
        return self.cell_size_x

    def _draw_field_text(self, pos: d.Point, text: str, color: Tuple[int, int, int], bold: bool = False):
        """Draws text at a field grid cell (never an edge column), applying
        the same grid alignment as the other field columns."""
        self._draw_text(pos, text, color, bold=bold)

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
        *,
        turn: int,
        game_start_turn: Optional[int] = None,
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
        debug_show_entities: bool = False,
        checkpoint: Optional[d.Point] = None,
        dim_types: Optional[Set[str]] = None,
        stage_roster: Optional[List[d.MonsterTribe]] = None,
        floor_view: bool = False,
        floor_label: Optional[str] = None,
        reachable_cells: Optional[Set[d.Point]] = None,
    ):
        """
        Renders the game stage:
        - Clears the screen.
        - Draws the field and its cells.
        - Draws the player and entities with appropriate colors.
        - Draws the status bar at the bottom.
        """
        show_entities = show_entities or self.map_mode
        reveal_disguises = debug_show_entities or self.map_mode
        self._clear_drawables()
        px, py = player.x, player.y

        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                discovered = bool(torched[y][x] or show_entities)
                if cur_torched[y][x]:
                    tile_color = VISIBLE_WALL if cell == d.CHAR_WALL else VISIBLE_FLOOR
                elif discovered:
                    tile_color = WALL if cell == d.CHAR_WALL else FLOOR
                else:
                    tile_color = FOG
                if cell == d.CHAR_CALTROP and discovered:
                    tile_color = (132, 70, 60)
                if (
                    cell == d.CHAR_BARRIER
                    and discovered
                    and barrier_lp_damage(player) > 0
                ):
                    tile_color = (67, 42, 45)
                if reachable_cells and (x, y) in reachable_cells and not floor_view:
                    tile_color = REACHABLE_CELL_COLOR
                self._draw_rect(
                    self._field_col_x(x),
                    y * self.cell_size_y,
                    self._field_col_width(x) + 1,
                    self.cell_size_y + 1,
                    tile_color,
                )

                if discovered and cell in d.STAIR_CHARS:
                    self._draw_field_text((x, y), cell, COLOR_MAP[CI_YELLOW], bold=True)
                elif discovered and cell == d.CHAR_BARRIER:
                    self._draw_field_text((x, y), d.CHAR_BARRIER, COLOR_MAP[CI_RED], bold=True)
                elif discovered and cell == d.CHAR_COLLAPSE:
                    self._draw_field_text(
                        (x, y), d.CHAR_COLLAPSE, COLOR_MAP[CI_YELLOW]
                    )

        for entity in entities:
            if not isinstance(entity, d.Monster) or entity.tribe.char != "k":
                continue
            for (x, y), char in entity.arrow_marks:
                if (show_entities or torched[y][x]) and (x, y) != (px, py):
                    self._draw_field_text((x, y), char, COLOR_MAP[CI_RED], bold=True)

        if not floor_view:
            self._draw_visibility_boundary(cur_torched)

        if not floor_view and checkpoint is not None and checkpoint != (px, py):
            self._draw_field_text(checkpoint, "+", COLOR_MAP[CI_YELLOW], bold=True)

        foreground, background = ui_display.player_appearance(player)
        if not floor_view and background is not None:
            self._draw_rect(
                self._field_col_x(px),
                py * self.cell_size_y,
                self.cell_size_x + 1,
                self.cell_size_y + 1,
                COLOR_MAP[_TONE_INDEX[background]],
            )
        if not floor_view:
            self._draw_field_text((px, py), "@", self._tone_color(foreground), bold=True)

        if not floor_view and player.companion is not None and px + 1 < d.FIELD_WIDTH:
            self._draw_field_text((px + 1, py), player.companion.tribe.char, COLOR_MAP[CI_GREEN], bold=True)

        # Draw entities (monster and treasures)
        player_attack = d.current_player_attack(player, stage_num)

        def paint(glyph: ui_display.FieldGlyph) -> None:
            self._draw_field_text(
                (glyph.x, glyph.y), glyph.char, self._tone_color(glyph.tone, glyph.dim), bold=glyph.bold
            )

        if show_entities:
            for entity in entities:
                for glyph in ui_display.preview_entity_glyphs(
                    entity,
                    reveal_disguises=reveal_disguises,
                    known_types=known_types,
                    stage_num=stage_num,
                ):
                    paint(glyph)

        for entity in entities:
            if torched[entity.y][entity.x] == 0 or (entity.x, entity.y) == (px, py):
                continue
            for glyph in ui_display.revealed_entity_glyphs(
                entity, known_types, show_entities, player_attack, dim_types,
                reveal_disguises=reveal_disguises,
                debug_show_entities=debug_show_entities,
                stage_num=stage_num,
            ):
                paint(glyph)

        # Stage 3 followers persist across floor changes and are rendered
        # independently of the temporary companion slot.
        for fx, fy, ffloor, fchar in getattr(player, "persistent_followers", []):
            if not floor_view and ffloor == player.current_floor and 0 <= fy < len(torched) and 0 <= fx < len(torched[0]) and torched[fy][fx] and (fx, fy) != (px, py):
                self._draw_field_text((fx, fy), fchar, COLOR_MAP["default"])

        # Draw the right-edge strength column: the stage's monster tribes and
        # the player, ranked strongest-first. A tinted background (full
        # column width) sets it apart from the field; the characters are
        # padded in from its left/right edges.
        self._draw_rect(
            self.field_pixel_width,
            0,
            self.strength_column_width,
            self.field_height * self.cell_size_y,
            STRENGTH_COLUMN_BG,
        )
        tribes = stage_roster if stage_roster is not None else (
            d.get_stage_roster_tribes(stage_num) if stage_num in (1, 2) else []
        )
        ranking_attack = d.current_player_attack(player, stage_num)
        for y, (strength_char, is_player) in enumerate(ui_display.build_strength_column(tribes, ranking_attack, self.field_height)):
            if strength_char is None:
                continue
            text_width = self._text_width(strength_char, bold=is_player)
            self._draw_text(
                (0, y), strength_char, COLOR_MAP["default"], bold=is_player,
                x_offset=(
                    self.field_pixel_width
                    + self.strength_column_width
                    - self.strength_column_padding
                    - text_width
                ),
            )

        if stage_num in d.ELF_STAGES:
            progress_x = 0
            for label, achieved in ui_display.elf_stage_progress_marks(player, stage_num):
                color = COLOR_MAP["default"] if achieved else (100, 106, 118)
                self._draw_text(
                    (progress_x, self.field_height - 1), label, color, bold=True
                )
                progress_x += len(label) + 1

        if floor_label:
            label_width = self._text_width(floor_label)
            label_x = max(
                0, self.field_pixel_width - label_width - 2 * self.cell_size_x
            )
            self._draw_text(
                (0, self.field_height - 1), floor_label, COLOR_MAP["default"], x_offset=label_x
            )

        # Draw the status bar
        self.draw_status_bar(
            turn, player, stage_num, message, extra_keys, game_start_turn
        )

        self._flip()

    def draw_status_bar(
        self,
        turn: int,
        player: d.Player,
        stage_num: int,
        message: Optional[str],
        extra_keys: bool,
        game_start_turn: Optional[int] = None,
    ):
        """
        Draws the status bar at the bottom of the screen similar to the terminal version.
        This includes stage, turn, level (with item modifiers), item info,
        beatable monsters, LP value, and a rectangular LP bar.
        """
        status_line = (
            ui_display.status_prefix(player, stage_num, turn, game_start_turn) + "LP: "
        )

        self._draw_text((0, self.field_height), status_line, COLOR_MAP["default"])
        text_width = self._text_width(status_line)
        x_offset = text_width + 10

        lp_str = "%d " % player.lp
        lp_x_cell = x_offset // self.cell_size_x
        self._draw_text((lp_x_cell, self.field_height), lp_str, COLOR_MAP["default"])
        lp_width = self._text_width(lp_str)
        x_offset += lp_width

        bar_cells = 8
        bar_width = bar_cells * self.cell_size_x
        bar_height = self.cell_size_y // 2
        y_offset = self.field_height * self.cell_size_y + (self.cell_size_y - bar_height) // 2
        lp_max = d.player_lp_max(player)
        progress_ratio = min(player.lp, lp_max) / lp_max
        fill_width = int(bar_width * progress_ratio)
        lp_color = (
            COLOR_MAP[CI_MAGENTA]
            if player.lp > lp_max
            else COLOR_MAP[CI_RED]
            if player.lp <= d.LP_LOW_THRESHOLD
            else COLOR_MAP["default"]
        )

        self._draw_rect_outline(x_offset, y_offset, bar_width, bar_height, COLOR_MAP["default"])
        if fill_width > 0:
            self._draw_rect(x_offset, y_offset, fill_width, bar_height, lp_color)

        extra = "/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit"
        item_status = extra
        item_x_offset = x_offset + bar_width + 10
        self._draw_text((item_x_offset // self.cell_size_x, self.field_height), item_status, COLOR_MAP["default"])

        if message:
            self._draw_text(
                (0, self.field_height + 1),
                message,
                COLOR_MAP[CI_YELLOW],
                size_scale=MESSAGE_FONT_SIZE_SCALE,
            )

    def _text_width(self, text: str, bold: bool = False) -> int:
        font_name: str
        font_size: float
        if text.isascii():
            font_name, font_size = self.font_name, self.font_size
        else:
            non_ascii_font_name, size_scale = self._non_ascii_font()
            font_name, font_size = non_ascii_font_name, self.font_size * size_scale
        label = pyglet.text.Label(
            text,
            font_name=font_name,
            font_size=font_size,
            weight="bold" if bold else "normal",
        )
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
                left = self._field_col_x(x)
                top = y * self.cell_size_y
                right = left + self._field_col_width(x)
                bottom = top + self.cell_size_y
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
        # Pyglet's regular app loop polls open input devices (including
        # controllers) from the platform event loop. This UI has its own loop,
        # so perform a non-blocking step here to keep device state current.
        pyglet.app.platform_event_loop.step(0)
        button_names = ("a", "b", "x", "y")
        held_buttons = {
            index
            for index, name in enumerate(button_names)
            if self.controller and bool(getattr(self.controller, name, False))
        }
        was_preview_held = 2 in self._gamepad_held_buttons
        self._gamepad_pressed_buttons = held_buttons - self._gamepad_held_buttons
        self._gamepad_held_buttons = held_buttons
        self._gamepad_preview_held = 2 in held_buttons
        if self._gamepad_preview_held != was_preview_held:
            self._gamepad_preview_changed = True
            if was_preview_held and not self._gamepad_preview_held:
                self.floor_view_reset_requested = True

    @property
    def farthest_preview(self) -> bool:
        return self._keyboard_farthest_preview or self._gamepad_preview_held

    @farthest_preview.setter
    def farthest_preview(self, enabled: bool) -> None:
        self._keyboard_farthest_preview = bool(enabled)

    def poll_events(self) -> bool:
        """Process pending window events and report whether the window closed."""
        self._pump()
        return self._closed

    def _next_key(self) -> Optional[int]:
        """Pops the oldest queued key symbol, or None if no key is queued."""
        if self._key_queue:
            key = self._key_queue.pop(0)
            return key[0] if isinstance(key, tuple) else key
        return None

    def _next_key_event(self):
        if self._key_queue:
            key = self._key_queue.pop(0)
            return key if isinstance(key, tuple) else (key, 0)
        return None

    def _discard_queued_key(self, symbol: int) -> None:
        self._key_queue = [
            event for event in self._key_queue
            if (event[0] if isinstance(event, tuple) else event) != symbol
        ]

    def input_direction(self) -> Optional[Tuple[int, int]]:
        self._stage_input_active = True
        try:
            return self._input_direction()
        finally:
            self._stage_input_active = False

    def stop_movement_repeat(self) -> None:
        """Require held movement controls to be released before repeating again."""
        self._held_direction = None
        self._next_repeat_at = 0.0
        if getattr(self, "gamepad_previous_direction", None) not in (None, (0, 0)):
            self._next_gamepad_repeat_at = float("inf")

    def _input_direction(self) -> Optional[Tuple[int, int]]:
        """
        Waits for a directional input.
        Returns a tuple (dx, dy) if an arrow key, WASD key, controller D-pad,
        or left stick is used.
        Returns None if ESC or 'q' is pressed, or the window is closed.
        """
        self.shift_direction = False
        self.input_was_repeat = False
        while True:
            self._pump()
            if self._closed:
                return None

            if self._gamepad_preview_changed:
                self._gamepad_preview_changed = False
                return (0, 0)

            if 3 in self._gamepad_pressed_buttons:
                self.controls_menu()
                return (0, 0)

            while self._key_queue:
                event = self._next_key_event()
                if event is None:
                    symbol = None
                    modifiers = 0
                else:
                    symbol, modifiers = event
                if symbol == pgkey.F:
                    self._keyboard_farthest_preview = not self._keyboard_farthest_preview
                    return (0, 0)
                if symbol == pgkey.M:
                    self.map_mode = True
                    return (0, 0)
                if symbol == pgkey.H:
                    self.controls_menu()
                    return (0, 0)
                if symbol in (pgkey.ESCAPE, pgkey.Q):
                    return None
                if symbol in _DIRECTION_KEYS:
                    self.shift_direction = bool(modifiers & pgkey.MOD_SHIFT)
                    if symbol in self._held_direction_keys:
                        self._held_direction = _DIRECTION_KEYS[symbol]
                        self._next_repeat_at = (
                            time.monotonic() + self.key_repeat_interval
                            if self.key_repeat_interval is not None else float("inf")
                        )
                    return _DIRECTION_KEYS[symbol]

            repeat_interval = self.key_repeat_interval
            if (
                self._held_direction is not None
                and repeat_interval is not None
                and time.monotonic() >= self._next_repeat_at
            ):
                self._next_repeat_at = time.monotonic() + repeat_interval
                self.input_was_repeat = True
                return self._held_direction

            controller = getattr(self, "controller", None)
            if controller:
                current_direction = self._controller_direction(controller)

                if current_direction != self.gamepad_previous_direction:
                    self.gamepad_previous_direction = current_direction
                    if current_direction != (0, 0):
                        if self._gamepad_preview_held:
                            if current_direction[0] != 0:
                                self._next_gamepad_repeat_at = float("inf")
                                time.sleep(1 / 30)
                                continue
                            self.shift_direction = True
                        self._next_gamepad_repeat_at = (
                            time.monotonic() + self.key_repeat_interval
                            if self.key_repeat_interval is not None else float("inf")
                        )
                        return current_direction
                    self._next_gamepad_repeat_at = 0.0
                elif (
                    current_direction != (0, 0)
                    and self.key_repeat_interval is not None
                    and time.monotonic() >= self._next_gamepad_repeat_at
                ):
                    if self._gamepad_preview_held:
                        if current_direction[0] != 0:
                            time.sleep(1 / 30)
                            continue
                        self.shift_direction = True
                    self._next_gamepad_repeat_at = time.monotonic() + self.key_repeat_interval
                    self.input_was_repeat = True
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
                event = self._next_key_event()
                symbol = event[0]
                if symbol in (pgkey.ESCAPE, pgkey.Q):
                    return None
                if symbol in _DIGIT_KEYS:
                    return _DIGIT_KEYS[symbol]
                if symbol == pgkey.H:
                    self.controls_menu()
                    return "h"
                key_name = pgkey.symbol_string(symbol)
                return key_name.lower()
            if 3 in self._gamepad_pressed_buttons:
                self.controls_menu()
                return "h"

            time.sleep(1 / 30)

    def input_game_over(self):
        """Wait for a game-over command or a shifted floor-view direction."""
        while True:
            self._pump()
            if self._closed:
                return None

            if 3 in self._gamepad_pressed_buttons:
                self.controls_menu()
                return (0, 0, False)

            while self._key_queue:
                event = self._next_key_event()
                symbol, modifiers = event
                if symbol in (pgkey.ESCAPE, pgkey.Q):
                    return None
                if symbol == pgkey.M:
                    return "m"
                if symbol == pgkey.S:
                    return "s"
                if symbol == pgkey.H:
                    self.controls_menu()
                    return (0, 0, False)
                if symbol in _DIRECTION_KEYS:
                    return (*_DIRECTION_KEYS[symbol], bool(modifiers & pgkey.MOD_SHIFT))

            time.sleep(1 / 30)

    def quit(self):
        """Closes the game window."""
        self.window.close()

    def controls_menu(self) -> None:
        """Show controls until the player dismisses the help screen."""
        self._clear_drawables()
        self._draw_text((8, 4), tr("Controls"), COLOR_MAP[CI_YELLOW], bold=True)
        controls = (
            "Arrow keys / WASD: move",
            "Gamepad: D-pad / left stick move, button 0 confirm, hold button 2 to preview",
            "Gamepad button 3: open / close this help",
            "F: toggle reachable-area preview",
            "M: enter map and entity display mode (cannot be undone)",
            "Shift + Up/Down: view another floor (Stages 3 and 4)",
            "Hold gamepad button 2 + Up/Down: view another floor (Stages 3 and 4)",
            "S: show the seed",
            "Q / Esc: quit the stage",
        )
        for index, line in enumerate(controls):
            self._draw_text(
                (8, 7 + MENU_ROW_SPACING * index), tr(line), COLOR_MAP["default"]
            )
        return_y = 7 + MENU_ROW_SPACING * (len(controls) - 1) + 2
        self._draw_text(
            (8, return_y),
            tr("Press any key or gamepad button 3 to return"),
            (145, 150, 160),
        )
        self._flip()
        while not self._closed:
            self._pump()
            if self._next_key_event() is not None:
                return
            if 3 in self._gamepad_pressed_buttons:
                return
            time.sleep(1 / 30)

    def settings_menu(self) -> None:
        """Show GUI settings and persist the selected display and input options."""
        current_index = min(
            range(len(UI_SCALE_CHOICES)),
            key=lambda index: abs(UI_SCALE_CHOICES[index] - self.scale),
        )

        repeat_index = KEY_REPEAT_CHOICES.index(self.key_repeat_interval) if self.key_repeat_interval in KEY_REPEAT_CHOICES else 0
        auto_repeat_stop_enabled = self.auto_repeat_stop_enabled
        row = 0
        while True:
            self._clear_drawables()
            self._draw_text(
                (8, 5),
                tr("Settings"),
                COLOR_MAP[CI_YELLOW],
                bold=True,
            )
            scale_label = tr("Interface scale")
            scale_heading = f"{'>' if row == 0 else ' '} {scale_label}"
            self._draw_text(
                (8, 8),
                scale_heading,
                COLOR_MAP["default"],
                bold=row == 0,
            )
            self._draw_text(
                (8, 8),
                f"<  {int(UI_SCALE_CHOICES[current_index] * 100)}%  >",
                COLOR_MAP["default"],
                bold=row == 0,
                x_offset=self._text_width(
                    scale_heading,
                    bold=row == 0,
                ) + self.cell_size_x,
            )
            repeat_label = tr("Movement repeat interval")
            repeat_heading = f"{'>' if row == 1 else ' '} {repeat_label}"
            self._draw_text(
                (8, 10),
                repeat_heading,
                COLOR_MAP["default"],
                bold=row == 1,
            )
            self._draw_text(
                (8, 10),
                f"<  {'None' if KEY_REPEAT_CHOICES[repeat_index] is None else format(KEY_REPEAT_CHOICES[repeat_index], '.1f') + 's'}  >",
                COLOR_MAP["default"],
                bold=row == 1,
                x_offset=self._text_width(
                    repeat_heading,
                    bold=row == 1,
                ) + self.cell_size_x,
            )
            stop_label = tr("Automatic repeat stop")
            stop_heading = f"{'>' if row == 2 else ' '} {stop_label}"
            self._draw_text(
                (8, 12),
                stop_heading,
                COLOR_MAP["default"],
                bold=row == 2,
            )
            self._draw_text(
                (8, 12),
                f"<  {tr('On') if auto_repeat_stop_enabled else tr('Off')}  >",
                COLOR_MAP["default"],
                bold=row == 2,
                x_offset=self._text_width(
                    stop_heading,
                    bold=row == 2,
                ) + self.cell_size_x,
            )
            help_color = (145, 150, 160)
            self._draw_text(
                (8, 15),
                tr("Up/Down: item   Left/Right: value"),
                help_color,
            )
            self._draw_text(
                (8, 17),
                tr("Enter / Gamepad button 0: apply   Esc / Gamepad button 1: cancel"),
                help_color,
            )
            self._flip()

            while True:
                self._pump()
                if self._closed:
                    return
                event = self._next_key_event()
                if event is not None:
                    symbol, _ = event
                    if symbol == pgkey.UP:
                        row = (row - 1) % 3
                        break
                    if symbol == pgkey.DOWN:
                        row = (row + 1) % 3
                        break
                    if symbol == pgkey.LEFT:
                        if row == 0:
                            current_index = max(0, current_index - 1)
                        elif row == 1:
                            repeat_index = max(0, repeat_index - 1)
                        else:
                            auto_repeat_stop_enabled = not auto_repeat_stop_enabled
                        break
                    if symbol == pgkey.RIGHT:
                        if row == 0:
                            current_index = min(len(UI_SCALE_CHOICES) - 1, current_index + 1)
                        elif row == 1:
                            repeat_index = min(len(KEY_REPEAT_CHOICES) - 1, repeat_index + 1)
                        else:
                            auto_repeat_stop_enabled = not auto_repeat_stop_enabled
                        break
                    if symbol in (pgkey.RETURN, pgkey.NUM_ENTER):
                        self.set_scale(UI_SCALE_CHOICES[current_index])
                        self.set_key_repeat_interval(KEY_REPEAT_CHOICES[repeat_index])
                        self.set_auto_repeat_stop_enabled(auto_repeat_stop_enabled)
                        return
                    if symbol in (pgkey.ESCAPE, pgkey.Q):
                        return

                # Use the same navigation and value changes for the gamepad
                # as for the keyboard. Gamepad button 0 applies; button 1
                # cancels.
                direction = self._controller_direction(getattr(self, "controller", None))
                if direction != getattr(self, "gamepad_previous_direction", None):
                    self.gamepad_previous_direction = direction
                    if direction == (0, -1):
                        row = (row - 1) % 2
                        break
                    if direction == (0, 1):
                        row = (row + 1) % 2
                        break
                    if direction == (-1, 0):
                        if row == 0:
                            current_index = max(0, current_index - 1)
                        elif row == 1:
                            repeat_index = max(0, repeat_index - 1)
                        else:
                            auto_repeat_stop_enabled = not auto_repeat_stop_enabled
                        break
                    if direction == (1, 0):
                        if row == 0:
                            current_index = min(len(UI_SCALE_CHOICES) - 1, current_index + 1)
                        elif row == 1:
                            repeat_index = min(len(KEY_REPEAT_CHOICES) - 1, repeat_index + 1)
                        else:
                            auto_repeat_stop_enabled = not auto_repeat_stop_enabled
                        break
                if 0 in getattr(self, "_gamepad_pressed_buttons", ()):
                    self.set_scale(UI_SCALE_CHOICES[current_index])
                    self.set_key_repeat_interval(KEY_REPEAT_CHOICES[repeat_index])
                    self.set_auto_repeat_stop_enabled(auto_repeat_stop_enabled)
                    return
                if 1 in getattr(self, "_gamepad_pressed_buttons", ()):
                    return

    def select_stage(self, stage_numbers: Tuple[int, ...] = d.PUBLIC_STAGE_NUMBERS) -> int:
        """
        Displays a stage selection menu where the user can navigate with arrow keys or D-pad,
        and confirm with Enter (or gamepad button 0), or directly press numeric keys or Q/ESC.

        The selected option is shown with a leading ">" and non-selected options with a blank.

        Returns:
            int: The selected stage number (1, 2, ...), or 0 if "Quit" is chosen.
        """
        assert len(stage_numbers) <= 9

        options = [tr("[q]uit")]
        for n in stage_numbers:
            options.append(tr("stage [{n}]").format(n=n))
        options.append(tr("[s]ettings"))

        current_index = 1  # Initial selection: stage 1
        settings_index = len(options) - 1

        while True:
            self._clear_drawables()
            self._draw_text(
                (8, 5),
                tr("Stage Selection"),
                COLOR_MAP[CI_YELLOW],
                bold=True,
            )

            base_x = 8
            base_y = 8
            for i, option in enumerate(options):
                prefix = ">" if i == current_index else " "
                self._draw_text(
                    (base_x, base_y + MENU_ROW_SPACING * i),
                    f"{prefix} {option}",
                    COLOR_MAP["default"],
                    bold=(i == current_index),
                )
            self._draw_text(
                (8, base_y + MENU_ROW_SPACING * (len(options) - 1) + 2),
                tr("[h]elp / Gamepad button 3: controls"),
                (145, 150, 160),
            )

            self._flip()

            while True:
                self._pump()
                if self._closed:
                    return 0

                if 0 in getattr(self, "_gamepad_pressed_buttons", ()):
                    if current_index == 0:
                        return 0
                    if current_index == settings_index:
                        self.settings_menu()
                        self._discard_queued_key(pgkey.ESCAPE)
                        break
                    return current_index
                if 3 in getattr(self, "_gamepad_pressed_buttons", ()):
                    self.controls_menu()
                    break

                event = self._next_key_event()
                if event is not None:
                    symbol, _ = event
                    if symbol == pgkey.UP:
                        current_index = (current_index - 1) % len(options)
                    elif symbol == pgkey.DOWN:
                        current_index = (current_index + 1) % len(options)
                    elif symbol in (pgkey.RETURN, pgkey.NUM_ENTER):
                        if current_index == 0:
                            return 0
                        if current_index == settings_index:
                            self.settings_menu()
                            self._discard_queued_key(pgkey.ESCAPE)
                            break
                        return current_index
                    elif symbol == pgkey.S:
                        self.settings_menu()
                        self._discard_queued_key(pgkey.ESCAPE)
                        break
                    elif symbol == pgkey.H:
                        self.controls_menu()
                        break
                    elif symbol in (pgkey.Q, pgkey.ESCAPE):
                        return 0
                    elif symbol in _DIGIT_KEYS:
                        n = int(_DIGIT_KEYS[symbol])
                        if n in stage_numbers:
                            return n
                    break

                controller = getattr(self, "controller", None)
                if controller:
                    direction = self._controller_direction(controller)
                    if direction != self.gamepad_previous_direction:
                        self.gamepad_previous_direction = direction
                        if direction[1]:
                            current_index = (current_index + direction[1]) % len(options)
                            break

                time.sleep(1 / 30)
