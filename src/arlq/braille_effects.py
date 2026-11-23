"""Sprite effect frames sampled into character-cell braille patterns."""

import json
from functools import lru_cache
from pathlib import Path

from . import defs as d

_ORIGIN = (10, 9)
_DURATIONS = {"Vortex": 4 / 3, "Dungeon Core": 1.0, "Boss": 14 / 15, "Core Calamity": 1.5}


@lru_cache(maxsize=1)
def _frames():
    path = Path(__file__).parent / "assets" / "effects" / "braille-frames.json"
    return json.loads(path.read_text(encoding="utf-8"))


def effect_frames(name, pos, combat_seconds):
    """Return the duration and visible, positioned cells for an effect."""
    if combat_seconds <= 0:
        return 0, []
    seconds = (_DURATIONS[name] * combat_seconds if name == "Vortex"
               else _DURATIONS[name])
    frames = []
    for rows in _frames()[name]:
        cells = []
        for y, row in enumerate(rows):
            for x, (char, color) in enumerate(row):
                px = pos[0] + x - _ORIGIN[0]
                py = pos[1] + y - _ORIGIN[1]
                if color and 0 <= px < d.FIELD_WIDTH and 0 <= py < d.FIELD_HEIGHT:
                    cells.append(((px, py), char, tuple(bytes.fromhex(color[1:]))))
        frames.append(cells)
    if name == "Vortex":
        frames = frames[:1]
    return seconds, frames


@lru_cache(maxsize=1)
def _wide_frames():
    path = Path(__file__).parent / "assets" / "effects" / "braille-frames-wide.json"
    return json.loads(path.read_text(encoding="utf-8"))


def wide_effect_frames(name, pos, combat_seconds):
    """Return frames with two braille characters per map cell."""
    if combat_seconds <= 0:
        return 0, []
    seconds = (_DURATIONS[name] * combat_seconds if name == "Vortex"
               else _DURATIONS[name])
    frames = []
    for rows in _wide_frames()[name]:
        cells = []
        for y, row in enumerate(rows):
            for column, (char, color) in enumerate(row):
                px = pos[0] + column // 2 - _ORIGIN[0]
                py = pos[1] + y - _ORIGIN[1]
                if color and 0 <= px < d.FIELD_WIDTH and 0 <= py < d.FIELD_HEIGHT:
                    cells.append(((px, py), column % 2, char, tuple(bytes.fromhex(color[1:]))))
        frames.append(cells)
    return seconds, frames[:1] if name == "Vortex" else frames
