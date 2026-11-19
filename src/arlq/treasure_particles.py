"""Safe cells and animation frames for the character-mode victory sparkle."""

from . import defs as d

SPARKLE_TICKS_PER_SECOND = 2.5


def sparkle_cells(player, entities, field, visible, decor=None, blocked=()):
    occupied = set(blocked)
    occupied.add((player.x, player.y))
    for entity in entities:
        occupied.add((entity.x, entity.y))
        if isinstance(entity, d.Monster):
            occupied.update(point for point, _ in getattr(entity, "arrow_marks", ()))
            occupied.update(((entity.x - 1, entity.y), (entity.x + 1, entity.y)))
        if isinstance(entity, d.Treasure):
            occupied.update(((entity.x - 1, entity.y), (entity.x + 1, entity.y)))
    occupied.update((member.x, member.y) for member in player.members)
    cells = []
    for y in range(max(0, player.y - 2), min(len(field), player.y + 3)):
        for x in range(max(0, player.x - 2), min(len(field[y]), player.x + 3)):
            if abs(x - player.x) <= 1 and abs(y - player.y) <= 1:
                continue
            if (field[y][x] != d.CHAR_FLOOR or not visible[y][x]
                    or (x, y) in occupied or (decor and decor[y][x])):
                continue
            cells.append((x, y))
    return cells


# Fixed pixel positions and starting ticks for the selected victory animation.
_SPARKLES = (
    (1, 2, 0), (3, 2, 5), (5, 2, 2), (7, 2, 7),
    (0, 5, 6), (0, 8, 1), (0, 11, 4), (0, 14, 8),
    (9, 5, 3), (9, 8, 8), (9, 11, 5), (9, 14, 1),
    (1, 16, 7), (3, 16, 3), (5, 16, 0), (7, 16, 4),
)


def sparkle_frame(cells, tick, center):
    """Show a fixed nine-frame twinkle, clipped to available floor cells."""
    cx, cy = center
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    available = set(cells)
    frame = {}
    for pixel_x, pixel_y, start in _SPARKLES:
        point = (cx - 2 + pixel_x // 2, cy - 2 + pixel_y // 4)
        if point in available and (tick - start) % 9 < 3:
            bit = bits[pixel_y % 4][pixel_x % 2]
            frame[point] = frame.get(point, 0) | bit
    return [(point, chr(0x2800 + mask)) for point, mask in frame.items()]
