"""Display constants shared by the sprite frontend's modules."""

import math

from . import defs as d

# A character in one of the four cells next to the player, the one the next
# step would meet, is drawn this much larger (its ground disc keeps its size).
NEIGHBOR_SCALE = 1.3
# Every sprite uses one scale: this many source pixels (an amoeba's width
# before the amoebas were shrunk to 0.9) span 1.8 cell widths. Larger models
# therefore give larger sprites.
SPRITE_REFERENCE_PIXELS = 186
# The export camera looks 60 degrees down at a point 0.35 units above each
# model's ground origin, at 256 px per 2.6 units, with crops symmetric about
# that point; the feet are therefore this many source pixels below the image
# centre. Sprites are placed so their feet rest on the cell centre.
SPRITE_GROUND_OFFSET_PIXELS = 0.35 * math.cos(math.radians(60)) * 256 / 2.6
# Gold tint of ordinary stair flights and the floor transition's landing.
TERRAIN_TINT = (255, 222, 150)
# Stair and pit images reach TERRAIN_SIDE cells past each side of their cell
# and TERRAIN_OVERHANG cells into the cell to the north. A side is drawn only
# where the neighbouring cell is explored plain floor; elsewhere it is
# cropped away.
TERRAIN_SIDE = 0.25
TERRAIN_OVERHANG = {d.CHAR_STAIRS_UP: 0.5, d.CHAR_STAIRS_DOWN: 0.5,
                    d.CHAR_COLLAPSE: 0.25,
                    d.DECOR_FALLEN_ROCKS: 0.25}
