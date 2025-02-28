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


def braille_progress_bar(current: int, maximum: int, bar_length: int = 20) -> str:
    """
    Generates a progress bar using Unicode Braille Patterns.

    Args:
        current (int): The current progress value.
        maximum (int): The maximum progress value.
        bar_length (int): The length of the progress bar in characters (default is 20).

    Returns:
        str: A string representing the progress bar using Braille characters.
    """
    # Bit masks corresponding to different fill levels of a Braille cell.
    # Bit mapping: dot1=0x01, dot2=0x02, dot3=0x04, dot7=0x40,
    #              dot4=0x08, dot5=0x10, dot6=0x20, dot8=0x80.
    braille_map = [
        0x00,  # 0: cell is completely empty.
        0x40,  # 1: dot1
        0x40 | 0x04,  # 2: dots 1 and 2.
        0x40 | 0x04 | 0x02,  # 3: dots 1, 2, and 3.
        0x40 | 0x04 | 0x02 | 0x01,  # 4: left column complete (dots 1, 2, 3, 7).
        0x40 | 0x04 | 0x02 | 0x01 | 0x80,  # 5: left column + dot4.
        0x40 | 0x04 | 0x02 | 0x01 | 0x80 | 0x20,  # 6: left column + dots4 and 5.
        0x40 | 0x04 | 0x02 | 0x01 | 0x80 | 0x20 | 0x10,  # 7: left column + dots4, 5, and 6.
        0x40 | 0x04 | 0x02 | 0x01 | 0x80 | 0x20 | 0x10 | 0x08,  # 8: fully filled.
    ]

    if maximum <= 0:
        return " " * bar_length

    # Total number of subunits (each cell has 8 levels of fill)
    total_subunits = bar_length * 8
    fraction = current / maximum
    filled_subunits = int(round(fraction * total_subunits))

    cells = []
    for i in range(bar_length):
        # Determine the number of subunits to fill in this cell (0 to 8)
        cell_units = min(max(filled_subunits - i * 8, 0), 8)
        # Retrieve the corresponding Braille character based on the fill level.
        cell_char = chr(0x2800 + braille_map[cell_units])
        cells.append(cell_char)

    return "".join(cells) + " " * (bar_length - len(cells))
