"""Plan movement using only terrain known to the player."""

from collections import deque
from typing import Optional

from . import defs as d


def find_path(
    field: list[list[str]],
    seen: list[list[int]],
    start: d.Point,
    target: d.Point,
    visible: Optional[list[list[int]]] = None,
    *,
    allow_d_gate: bool = False,
    allow_special_target: bool = False,
    blocked: Optional[set[d.Point]] = None,
) -> list[d.Point]:
    """Return a path including start and the closest reachable cell.

    Prefer a route entirely through known floor if it reaches the target.
    Otherwise, assume unexplored cells are floor, except at the outer edge.
    Hidden floor-like terrain is treated as floor so the result does not reveal
    its underlying identity. Blocked cells are avoided except at the target.
    Ties follow the fixed neighbor order below.
    """
    height = len(field)
    width = len(field[0]) if height else 0
    grids = (field, seen) if visible is None else (field, seen, visible)
    if not width or any(len(grid) != height or any(len(row) != width for row in grid)
                        for grid in grids):
        raise ValueError("terrain and visibility grids must be nonempty and rectangular")

    def in_bounds(point: d.Point) -> bool:
        x, y = point
        return 0 <= x < width and 0 <= y < height

    if not in_bounds(start) or not in_bounds(target):
        raise ValueError("start and target must be within the field")

    def known(x: int, y: int) -> bool:
        return bool(seen[y][x] or (visible is not None and visible[y][x]))

    def search(allow_unknown: bool) -> list[d.Point]:
        parents: dict[d.Point, Optional[d.Point]] = {start: None}
        distances = {start: 0}
        pending = deque([start])
        best = start
        best_key = (abs(start[0] - target[0]) + abs(start[1] - target[1]), 0)
        while pending:
            x, y = pending.popleft()
            for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                point = (x + dx, y + dy)
                if point in parents or not in_bounds(point):
                    continue
                if blocked is not None and point in blocked and point != target:
                    continue
                nx, ny = point
                if known(nx, ny):
                    cell = field[ny][nx]
                    passable = cell in (d.CHAR_FLOOR, *d.HIDDEN_STAIRS_CHARS)
                    passable |= allow_d_gate and cell == d.CHAR_D_GATE
                    passable |= allow_special_target and point == target
                    if not passable:
                        continue
                elif (not allow_unknown or nx in (0, width - 1) or ny in (0, height - 1)) and not (
                    allow_special_target and allow_unknown and point == target
                ):
                    continue
                parents[point] = (x, y)
                distances[point] = distances[(x, y)] + 1
                key = (abs(nx - target[0]) + abs(ny - target[1]), distances[point])
                if key < best_key:
                    best, best_key = point, key
                pending.append(point)

        path = []
        current: Optional[d.Point] = best
        while current is not None:
            path.append(current)
            current = parents[current]
        path.reverse()
        return path

    if known(*target):
        path = search(False)
        if path[-1] == target:
            return path
    return search(True)
