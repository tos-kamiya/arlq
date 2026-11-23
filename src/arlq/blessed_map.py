"""Terminal drawing primitives for one- or two-column map cells.

This adapter leaves input, terminal dimensions, and other Blessed operations
to the underlying terminal. Coordinates passed to map methods are map cells;
coordinates passed to screen_text are ordinary terminal columns and rows.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import partial
from typing import Callable

from blessed import Terminal


@dataclass(frozen=True)
class EffectCell:
    x: int
    y: int
    char: str
    color: str | tuple[int, int, int] | None = None
    background: str | None = None
    bold: bool = False
    fallback_color: str | None = None
    subcell: int | None = None


@dataclass(frozen=True)
class EffectAnimation:
    frames: list[list[EffectCell]]
    frame_seconds: float


class BlessedMap:
    def __init__(self, terminal: Terminal, cell_width: int = 1):
        if cell_width not in (1, 2):
            raise ValueError("cell_width must be 1 or 2")
        self.terminal = terminal
        self.cell_width = cell_width

    def __getattr__(self, name):
        return getattr(self.terminal, name)

    def map_x(self, x: int) -> int:
        return x * self.cell_width

    def rank_text(self, text: str) -> str:
        """Select the wide-mode glyphs used for monster rank marks."""
        return text.translate(str.maketrans({"'": "❜", '"': "❞"})) if self.cell_width == 2 else text

    def _wide_char(self, char: str) -> str:
        code = ord(char)
        if char == " ":
            return "  "
        if 0x21 <= code <= 0x7e:
            return chr(code + 0xfee0)
        width = self.terminal.length(char)
        if width == 1:
            return char + " "
        if width == 2:
            return char
        raise ValueError(f"unsupported map character width: {char!r}")

    def map_text(self, x: int, y: int, text: str,
                 style: Callable[[str], str] | None = None) -> str:
        """Draw map-aligned characters, with each character occupying a cell."""
        if self.cell_width == 2:
            text = "".join(self._wide_char(char) for char in text)
        if style is not None:
            text = style(text)
        return self.terminal.move_xy(self.map_x(x), y) + text

    def map_cell(self, x: int, y: int, char: str,
                 style: Callable[[str], str] | None = None) -> str:
        if len(char) != 1:
            raise ValueError("a map cell must contain one character")
        return self.map_text(x, y, char, style)

    def effect_cell(self, x: int, y: int, char: str,
                    style: Callable[[str], str] | None = None) -> str:
        """Draw an effect cell, including padding in its styled background."""
        return self.map_cell(x, y, char, style)

    def _effect_style(self, cell: EffectCell, text: str) -> str:
        color = cell.color
        if isinstance(color, tuple) and self.terminal.number_of_colors < 256:
            color = cell.fallback_color
        color_name = color if isinstance(color, str) else None
        attr = (f"{color_name}_on_{cell.background}" if color_name and cell.background
                else f"on_{cell.background}" if cell.background else color_name)
        if attr:
            text = getattr(self.terminal, attr)(text)
        if cell.bold:
            text = self.terminal.bold(text)
        if isinstance(color, tuple):
            text = self.terminal.color_rgb(*color)(text)
        return text

    def effect_frame(self, cells: list[EffectCell]) -> str:
        """Render a frame of positioned effect cells."""
        output = []
        for cell in cells:
            if cell.subcell is None:
                output.append(self.effect_cell(
                    cell.x, cell.y, cell.char, partial(self._effect_style, cell)))
            else:
                output.append(self.screen_text(
                    self.map_x(cell.x) + cell.subcell, cell.y, cell.char,
                    partial(self._effect_style, cell)))
        return "".join(output)

    def play_effect(self, animation: EffectAnimation, snapshot: str,
                    wait_for_size: Callable[[], None]) -> None:
        """Play frames over a snapshot and restore it after the final frame."""
        for cells in animation.frames:
            wait_for_size()
            print(snapshot + self.effect_frame(cells) + self.terminal.normal,
                  end="", flush=True)
            time.sleep(animation.frame_seconds)
        print(snapshot, end="", flush=True)

    def screen_text(self, x: int, y: int, text: str,
                    style: Callable[[str], str] | None = None) -> str:
        """Draw unchanged text at terminal coordinates."""
        if style is not None:
            text = style(text)
        return self.terminal.move_xy(x, y) + text

    def dialogue(self, x: int, y: int, text: str, field_width: int,
                 field_height: int, monochrome: bool = False) -> str:
        """Place unscaled dialogue beside a map cell, within the field."""
        from .stage5 import trial_dialogue_lines

        term = self.terminal
        field_columns = self.map_x(field_width)
        player_x = self.map_x(x)
        right_x = self.map_x(x + 1)
        lines = trial_dialogue_lines(text, 30, measure=term.length)
        on_left = right_x + max(term.length(line) for line in lines) > field_columns
        if on_left:
            lines = trial_dialogue_lines(text, 30, on_left=True, measure=term.length)
        bubble_width = max(term.length(line) for line in lines)
        bx = max(0, player_x - bubble_width) if on_left else right_x
        by = y - len(lines) if y >= len(lines) else min(y + 1, field_height - len(lines))

        def style(value):
            return term.bold(value if monochrome else term.yellow(value))

        return "".join(self.screen_text(bx, by + i, line, style)
                       for i, line in enumerate(lines))

    def status_popup(self, x: int, y: int, text: str, tone: str,
                     field_width: int, field_height: int, monochrome: bool = False) -> str:
        """Place unscaled status text above right or below left of a map cell."""
        term = self.terminal
        width = term.length(text)
        right_x = self.map_x(x + 1)
        if y > 0 and right_x + width <= self.map_x(field_width):
            popup_x, popup_y = right_x, y - 1
        else:
            popup_x = max(0, self.map_x(x) - width)
            popup_y = min(y + 1, field_height - 1)

        def style(value):
            if not monochrome and tone != "default":
                value = getattr(term, tone)(value)
            return term.bold(value)

        return self.screen_text(popup_x, popup_y, text, style)

    def rewind_transition(self, message: str, field_width: int, field_height: int) -> str:
        """Darken the map and center an unscaled transition message."""
        term = self.terminal
        width = self.map_x(max(0, field_width - 3))
        height = min(field_height, term.height)
        dark_row = term.on_black(" " * width)
        output = [term.move_xy(0, y) + dark_row for y in range(height)]
        x = max(0, (width - term.length(message)) // 2)
        y = min(field_height // 2, term.height - 1)
        output.append(self.screen_text(x, y, message,
                                       lambda value: term.bold(term.white_on_black(value))))
        return "".join(output) + term.normal
