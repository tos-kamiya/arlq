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
    Unicodeの Braille Patterns を用いて進捗バーを生成します。
    """
    # Braille cell の各段階に対応するビットマスク
    # ビットの対応: dot1=0x01, dot2=0x02, dot3=0x04, dot7=0x40, dot4=0x08, dot5=0x10, dot6=0x20, dot8=0x80
    braille_map = [
        0x00,  # 0: 何も埋まっていない
        0x40,  # 1: dot1
        0x40 | 0x04,  # 2: dot1, dot2
        0x40 | 0x04 | 0x02,  # 3: dot1, dot2, dot3
        0x40 | 0x04 | 0x02 | 0x01,  # 4: 左カラム（dot1,2,3,7）完了
        0x40 | 0x04 | 0x02 | 0x01 | 0x80,  # 5: 左カラム + dot4
        0x40 | 0x04 | 0x02 | 0x01 | 0x80 | 0x20,  # 6: 左カラム + dot4, dot5
        0x40 | 0x04 | 0x02 | 0x01 | 0x80 | 0x20 | 0x10,  # 7: 左カラム + dot4, dot5, dot6
        0x40 | 0x04 | 0x02 | 0x01 | 0x80 | 0x20 | 0x10 | 0x08,  # 8: 完全に埋まった状態
    ]

    if maximum <= 0:
        return " " * bar_length

    # 全体を bar_length 文字、各文字8段階で表現
    total_subunits = bar_length * 8
    fraction = current / maximum
    filled_subunits = int(round(fraction * total_subunits))

    cells = []
    for i in range(bar_length):
        # 各セルに割り当てるサブユニット数 (0～8)
        cell_units = min(max(filled_subunits - i * 8, 0), 8)
        # 対応する braille pattern を取得
        cell_char = chr(0x2800 + braille_map[cell_units])
        cells.append(cell_char)

    return "".join(cells) + " " * (bar_length - len(cells))
