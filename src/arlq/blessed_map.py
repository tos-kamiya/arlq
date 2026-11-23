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

    def _wide_char(self, char: str) -> str:
        code = ord(char)
        if char == " ":
            return "\u3000"
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
        return "".join(self.effect_cell(
            cell.x, cell.y, cell.char, partial(self._effect_style, cell),
        ) for cell in cells)

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
