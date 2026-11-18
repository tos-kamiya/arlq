from typing import Sequence, TypeVar

T = TypeVar("T")


def player_spawn_exclusion(point):
    x, y = point
    return {(x + dx, y + dy) for dx in range(-2, 3) for dy in range(-2, 3)}


class MyRandom:
    """MT19937 with 32-bit integer seeds and fixed, unbiased range sampling."""

    def __init__(self, seed=123):
        self.set_seed(seed)

    def get_seed(self):
        return self.seed

    def set_seed(self, seed):
        self.seed = seed
        self._state = [seed & 0xffffffff]
        for i in range(1, 624):
            previous = self._state[-1]
            self._state.append((1812433253 * (previous ^ (previous >> 30)) + i) & 0xffffffff)
        self._index = 624

    def getstate(self):
        return self.seed, tuple(self._state), self._index

    def setstate(self, state):
        self.seed, values, self._index = state
        self._state = list(values)

    def _next_uint32(self):
        if self._index == 624:
            for i in range(624):
                value = (self._state[i] & 0x80000000) | (self._state[(i + 1) % 624] & 0x7fffffff)
                self._state[i] = self._state[(i + 397) % 624] ^ (value >> 1) ^ (0x9908b0df if value & 1 else 0)
            self._index = 0
        value = self._state[self._index]
        self._index += 1
        value ^= value >> 11
        value ^= (value << 7) & 0x9d2c5680
        value ^= (value << 15) & 0xefc60000
        value ^= value >> 18
        return value

    def randrange(self, start: int, stop: int | None = None) -> int:
        if stop is None:
            start, stop = 0, start
        if stop <= start:
            raise ValueError("empty range for randrange()")
        width = stop - start
        bits = (width - 1).bit_length()
        if bits == 0:
            return start
        words = (bits + 31) // 32
        while True:
            value = 0
            for _ in range(words):
                value = (value << 32) | self._next_uint32()
            value >>= words * 32 - bits
            if value < width:
                return start + value

    def choice(self, items: Sequence[T]) -> T:
        i = self.randrange(len(items))
        return items[i]


rand = MyRandom()
