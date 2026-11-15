from arlq import defs as d
from arlq.treasure_particles import sparkle_cells, sparkle_frame


def test_sparkles_stay_on_visible_empty_floor_and_avoid_characters():
    player = d.Player(4, 4, 100, 100)
    monster = d.Monster(5, 3, d.CHAR_TO_MONSTER_TRIBE['M'])
    treasure = d.Treasure(2, 4, 'TD')
    field = [[d.CHAR_FLOOR] * 9 for _ in range(9)]
    visible = [[1] * 9 for _ in range(9)]
    decor = [[''] * 9 for _ in range(9)]
    field[2][4] = d.CHAR_BARRIER
    visible[3][4] = 0
    decor[3][3] = d.DECOR_BOSS_ROUTE
    cells = sparkle_cells(player, [player, monster, treasure], field, visible, decor, {(6, 4)})
    assert cells
    assert not set(cells) & {(4, 4), (5, 3), (2, 4), (1, 4), (3, 4),
                             (4, 2), (4, 3), (3, 3), (6, 4)}
    assert set(point for point, _ in sparkle_frame(cells, 0, (4, 4))) <= set(cells)
    assert sparkle_frame(cells, 0, (4, 4)) != sparkle_frame(cells, 1, (4, 4))


def test_sparkle_frames_use_visible_braille_patterns():
    cells = [(x, y) for y in range(5) for x in range(5)
             if max(abs(x - 2), abs(y - 2)) >= 2]
    for tick in range(11):
        frame = sparkle_frame(cells, tick, (2, 2))
        assert all(0x2800 < ord(char) <= 0x28ff for _, char in frame)


def test_sparkle_area_is_one_cell_wide_around_central_three_by_three():
    player = d.Player(5, 5, 100, 100)
    field = [[d.CHAR_FLOOR] * 11 for _ in range(11)]
    visible = [[1] * 11 for _ in range(11)]
    cells = sparkle_cells(player, [player], field, visible)
    assert set(cells) == {(x, y) for y in range(3, 8) for x in range(3, 8)
                          if max(abs(x - 5), abs(y - 5)) >= 2}


def test_each_sparkle_keeps_the_same_dot_position_while_blinking():
    cells = [(x, y) for y in range(5) for x in range(5)
             if max(abs(x - 2), abs(y - 2)) >= 2]
    bits = (1, 2, 4, 8, 16, 32, 64, 128)
    counts = {}
    for tick in range(9):
        for point, char in sparkle_frame(cells, tick, (2, 2)):
            for bit in bits:
                if (ord(char) - 0x2800) & bit:
                    key = (point, bit)
                    counts[key] = counts.get(key, 0) + 1
    assert len(counts) == 16
    assert set(counts.values()) == {3}


def test_sparkle_pixels_use_shortened_bounds_without_corners():
    center = (5, 5)
    cells = [(x, y) for y in range(3, 8) for x in range(3, 8)
             if max(abs(x - 5), abs(y - 5)) >= 2]
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    pixels = set()
    for tick in range(9):
        for (x, y), char in sparkle_frame(cells, tick, center):
            for row, pair in enumerate(bits):
                for column, bit in enumerate(pair):
                    if (ord(char) - 0x2800) & bit:
                        pixels.add(((x - 3) * 2 + column, (y - 3) * 4 + row))
    assert pixels
    assert all(0 <= x <= 9 and 2 <= y <= 16 for x, y in pixels)
    assert not pixels & {(0, 2), (9, 2), (0, 16), (9, 16)}
    assert min(y for _, y in pixels) == 2
    assert max(y for _, y in pixels) == 16


def test_sparkles_never_use_adjacent_pixels_even_across_cell_boundaries():
    center = (5, 5)
    cells = [(x, y) for y in range(3, 8) for x in range(3, 8)
             if max(abs(x - 5), abs(y - 5)) >= 2]
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    pixels = set()
    for tick in range(9):
        for (x, y), char in sparkle_frame(cells, tick, center):
            for row, pair in enumerate(bits):
                for column, bit in enumerate(pair):
                    if (ord(char) - 0x2800) & bit:
                        pixels.add((x * 2 + column, y * 4 + row))
    for x, y in pixels:
        assert all((x + dx, y + dy) not in pixels
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)


def test_sparkle_pattern_repeats_and_does_not_depend_on_absolute_position():
    cells = [(x, y) for y in range(5) for x in range(5)
             if max(abs(x - 2), abs(y - 2)) >= 2]
    shifted = [(x + 10, y + 7) for x, y in cells]
    for tick in range(9):
        frame = sparkle_frame(cells, tick, (2, 2))
        assert frame == sparkle_frame(cells, tick + 9, (2, 2))
        assert [((x + 10, y + 7), char) for (x, y), char in frame] == (
            sparkle_frame(shifted, tick, (12, 9))
        )
