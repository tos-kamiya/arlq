"""Stage 7: a hidden check stage with only the player and an open treasure chest.

It is reachable only with `--stage 7` (not in the stage select) and exists to
look at the treasure-chest win screen without playing a full stage.
"""

from . import defs as d
from .stage_types import Floor

ROOM_WIDTH, ROOM_HEIGHT = 11, 7
CHEST_OFFSET = 3  # cells right of the player


def build(config=None) -> tuple[list[Floor], d.Player]:
    field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    left = (d.FIELD_WIDTH - ROOM_WIDTH) // 2
    top = (d.FIELD_HEIGHT - ROOM_HEIGHT) // 2
    for y in range(top, top + ROOM_HEIGHT):
        for x in range(left, left + ROOM_WIDTH):
            field[y][x] = d.CHAR_FLOOR
    cy = top + ROOM_HEIGHT // 2
    entry = (left + (ROOM_WIDTH - CHEST_OFFSET) // 2, cy)
    chest = d.Treasure(entry[0] + CHEST_OFFSET, cy, d.CHAR_TREASURE, boss_id=1)
    chest.unlocked = True
    floor = Floor(
        field=field,
        entities=[chest],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=entry,
        down=(chest.x, chest.y),
        island=None,
    )
    player = d.Player(*entry, 1, d.LP_INIT)
    return [floor], player
