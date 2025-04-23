class MyRandom:
    def __init__(self, seed=123):
        self._value = self.seed = seed

    def get_seed(self):
        return self.seed

    def set_seed(self, seed):
        self._value = self.seed = seed

    def randrange(self, r: int) -> int:
        self._value = (1103515245 * self._value + 12345) % (2**32)
        return self._value % r

    def choice(self, items):
        i = self.randrange(len(items))
        return items[i]


rand = MyRandom()


def block_progress_cells(
    current: int,
    maximum: int,
    bar_length: int,
    bar_attr: int,
) -> list[tuple[str, int]]:
    block_chars = {
        0: ".",
        1: "\u258F",
        2: "\u258E",
        3: "\u258D",
        4: "\u258C",
        5: "\u258B",
        6: "\u258A",
        7: "\u2589",
        8: "\u2588",
    }

    if maximum <= 0:
        return [(block_chars[0], bar_attr)] * bar_length

    current = max(0, current)
    frac = max(0.0, min(current / maximum, 1.0))
    total_units = bar_length * 8
    filled = int(round(frac * total_units))

    cells: list[tuple[str, int]] = []
    for i in range(bar_length):
        units = min(max(filled - i * 8, 0), 8)
        ch = block_chars[units]
        cells.append((ch, bar_attr))
    return cells


def draw_block_progress_bar(stdscr, x, y, bar_len, value, attr_thresholds):
    for threshold, color in attr_thresholds:
        if value <= threshold:
            attr = color
            break
    else:
        attr = attr_thresholds[-1][1]
    maximum = attr_thresholds[-1][0]
    cells = block_progress_cells(value, maximum, bar_len, attr)
    for i, (ch, attr) in enumerate(cells):
        stdscr.addstr(y, x + i, ch, attr)
