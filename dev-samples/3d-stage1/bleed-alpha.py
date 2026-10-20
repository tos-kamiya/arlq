"""Spread edge colors into the fully transparent pixels of the game PNGs.

Blender writes those pixels as near-black. The GUI shrinks the images with
mipmaps and linear filtering, which average them into the edges as a dark
fringe. Only pixels with alpha 0 change, so the images look the same unscaled.

    .venv/bin/python dev-samples/3d-stage1/bleed-alpha.py [PNG ...]

Without arguments, every PNG under src/arlq/assets is processed.
"""
import sys
from pathlib import Path

from pyglet.extlibs import png

ASSETS = Path(__file__).resolve().parents[2] / 'src' / 'arlq' / 'assets'
# Mipmap levels used in game reach about 1/16 of the image size; pixels
# farther from any edge than this get the mean color of the opaque pixels.
MAX_DISTANCE = 32


def bleed(path):
    width, height, rows, _ = png.Reader(filename=str(path)).asRGBA8()
    pixels = [bytearray(row) for row in rows]
    filled = [[row[x * 4 + 3] > 0 for x in range(width)] for row in pixels]
    frontier = {(x, y) for y in range(height) for x in range(width)
                if not filled[y][x] and any(
                    0 <= x + dx < width and 0 <= y + dy < height and filled[y + dy][x + dx]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
    for _ in range(MAX_DISTANCE):
        if not frontier:
            break
        colors = {}
        for x, y in frontier:
            total = [0, 0, 0]
            count = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and filled[ny][nx]:
                        offset = nx * 4
                        for c in range(3):
                            total[c] += pixels[ny][offset + c]
                        count += 1
            colors[x, y] = [round(value / count) for value in total]
        next_frontier = set()
        for (x, y), color in colors.items():
            pixels[y][x * 4:x * 4 + 3] = bytes(color)
            filled[y][x] = True
        for x, y in colors:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and not filled[ny][nx]:
                        next_frontier.add((nx, ny))
        frontier = next_frontier

    opaque = [row[x * 4:x * 4 + 3] for row in pixels for x in range(width) if row[x * 4 + 3] > 0]
    mean = bytes(round(sum(p[c] for p in opaque) / max(1, len(opaque))) for c in range(3))
    for y in range(height):
        for x in range(width):
            if not filled[y][x]:
                pixels[y][x * 4:x * 4 + 3] = mean
    temporary = path.with_suffix('.tmp')
    with open(temporary, 'wb') as file:
        png.Writer(width, height, greyscale=False, alpha=True, bitdepth=8).write(file, pixels)
    temporary.replace(path)


def main():
    paths = [Path(arg) for arg in sys.argv[1:]] or sorted(ASSETS.rglob('*.png'))
    for path in paths:
        bleed(path)
        print(path)


if __name__ == '__main__':
    main()
