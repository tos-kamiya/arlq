"""Placement and recovery rules for optional floor bridgeheads."""

from . import defs as d
from .stage56 import _open_points
from .stage_types import Floor


def reachable_floor_points(current: Floor, entry: d.Point) -> set[d.Point]:
    reachable = {entry}
    pending = [entry]
    while pending:
        x, y = pending.pop()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            point = (x + dx, y + dy)
            px, py = point
            if (
                point not in reachable
                and 0 <= py < len(current.field)
                and 0 <= px < len(current.field[py])
                and current.field[py][px] not in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
            ):
                reachable.add(point)
                pending.append(point)
    return reachable


def place_bridgehead(current: Floor, anchor: d.Point) -> d.Point:
    open_points = set(_open_points(current)) & reachable_floor_points(current, anchor)
    choices = [
        (x, y) for x, y in open_points
        if all((x + dx, y) in open_points for dx in range(2))
    ]
    if not choices:
        raise RuntimeError("no space for bridgehead")
    x, y = min(choices, key=lambda p: (abs(p[0] - anchor[0]) + abs(p[1] - anchor[1]), p))
    current.bridgehead = (x, y)
    for dx, char in enumerate("/\\"):
        current.decor[y][x + dx] = d.DECOR_BRIDGEHEAD_PREFIX + char
    return x, y


def in_bridgehead(current: Floor, point: d.Point) -> bool:
    if current.bridgehead is None:
        return False
    x, y = current.bridgehead
    return x <= point[0] < x + 2 and point[1] == y


def recover_at_bridgehead(
    floors: list[Floor], player: d.Player, floor_index: int,
    previous_floor: int, previous_point: d.Point,
) -> bool:
    """Restore LP when entering a bridgehead on any floor."""
    current = floors[floor_index]
    entered = (in_bridgehead(current, (player.x, player.y))
               and (previous_floor != floor_index or not in_bridgehead(current, previous_point)))
    if entered:
        player.lp = max(player.lp, d.BRIDGEHEAD_RECOVERY_LP)
    return entered
