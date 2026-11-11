"""Pyglet frontend with character sprites and the original text fallback."""

import json
import math
import random
import time
from functools import partial
from pathlib import Path

import pyglet

from . import defs as d
from . import display as ui_display
from .arlq import barrier_lp_damage
from .i18n import t as tr
from .pyglet_funcs import (
    CELL_SIZE_X,
    CELL_SIZE_Y,
    CI_BLUE,
    CI_GREEN,
    CI_YELLOW,
    COLOR_MAP,
    FIELD_SIDEBAR_GAP,
    FLOOR,
    FONT_HEIGHT_RATIO,
    MAX_UI_SCALE,
    MESSAGE_FONT_SIZE_SCALE,
    MIN_UI_SCALE,
    REACHABLE_CELL_COLOR,
    STRENGTH_COLUMN_PADDING,
    VISIBLE_FLOOR,
    VISIBLE_WALL,
    WALL,
    PygletUI,
    _font_glyph_metrics,
)

SPRITE_FILES = {
    '@': 'player.png',
    'a': 'amoeba.png',
    'A': 'rare-amoeba.png',
    'b': 'bison.png',
    'B': 'buffalo.png',
    'c': 'chimera.png',
    'd': 'comodo-dragon.png',
    'D': 'dragon.png',
    'T': 'treasure.png',
    'M': 'mimic.png',
    'l': 'loop-watch.png',
    'n': 'nomicon.png',
    'o': 'ocular.png',
    'C': 'rare-chimera.png',
    'F': 'fire-drake.png',
    'f': 'flame-cobra.png',
    'g': 'golem.png',
    'k': 'marksman.png',
    'V': 'vortex.png',
    'w': 'wyrm.png',
    'W': 'dread-wyrm.png',
    'm': 'spore.png',
    'e': 'erebus.png',
    'E': 'rare-erebus.png',
    'X': 'caltrop-plant.png',
    'i': 'ivy.png',
    'p': 'pegasus.png',
    'H': 'high-elf.png',
    'I': 'isolated-elf.png',
    'J': 'javelin-elf.png',
    'K': 'collector-elf.png',
    'L': 'lifebringer-elf.png',
    'S': 'sylvan-elf.png',
    # Not a glyph: the rubble drawn on walls a defeated Golem raised.
    'golem rock': 'golem-rock.png',
    # Not glyphs: the player holding a chimera's sword taken from it, or its
    # own sword glowing blue after the Collector Elf's blessing.
    'player sword': 'player-sword.png',
    'player cursed sword': 'player-cursed-sword.png',
    'player blessed': 'player-blessed.png',
    # Not a glyph: the plastic toy chest drawn for 'T' in Stage 5.
    'T-toy': 'treasure-toy.png',
    # Unidentified monsters (and traps), fairies and elves.
    '?': 'unknown-question.png',
    '!': 'unknown-exclamation.png',
    '&': 'unknown-ampersand.png',
}
# The unidentified symbols stand in a light pillar of their text color; the
# near-white symbol takes on only this fraction of that color.
UNKNOWN_SPRITES = ('?', '!', '&')
UNKNOWN_TINT = 0.4
# Their pillar is dimmed to this fraction, so it does not outshine the
# identified characters around it.
UNKNOWN_PILLAR = 0.21
# Their ground disc is darkened, if needed, to no brighter (by luminance) than
# the blue disc of a beatable identified monster.
UNKNOWN_DISC_REFERENCE = CI_BLUE
# Member sprite files are named '<job>-<gender>-<skin>.png': gender f, m, or
# n for a job drawn alike for both; skin l(ight), m(edium) or d(ark).
MEMBER_SPRITES = {'J': ('jester-n',), 'H': ('healer-f', 'healer-m'),
                  'R': ('rogue-n',), 'K': ('knight-n',),
                  'G': ('guardian-n',), 'D': ('explorer-f', 'explorer-m'),
                  'S': ('seer-f', 'seer-m')}
CAT_SPRITE = 'yawning-cat'
SPRITE_FILES[CAT_SPRITE] = 'yawning-cat.png'
MEMBER_SKINS = ('l', 'm', 'd')
SPRITE_FILES.update({f'{name}-{skin}': f'{name}-{skin}.png'
                     for names in MEMBER_SPRITES.values() for name in names
                     for skin in MEMBER_SKINS})
ROCK_SPRITE = 'golem rock'
SPRITE_NAMES = {
    '@': 'Player', 'a': 'Amoeba', 'A': 'Rare Amoeba', 'b': 'Bison',
    'B': 'Buffalo', 'c': 'Chimera', 'C': 'Rare Chimera', 'd': 'Komodo Dragon',
    'D': 'Dragon', 'T': 'Treasure', 'M': 'Mimic', 'l': 'Loop Fairy',
    'n': 'Nomicon', 'o': 'Ocular', 'F': 'Fire Drake', 'f': 'Flame Cobra',
    'g': 'Golem', 'i': 'Ivy', 'k': 'Marksman', 'V': 'Vortex', 'w': 'Wyrm',
    'W': 'Dread Wyrm', 'm': 'Spore', 'e': 'Erebus', 'E': 'Rare Erebus',
    'X': 'Caltrop Plant', 'p': 'Pegasus', 'H': 'High Elf', 'I': 'Isolated Elf',
    'J': 'Javelin Elf', 'K': 'Collector Elf', 'L': 'Lifebringer Elf',
    'S': 'Sylvan Elf', '?': 'Unidentified Monster',
    '!': 'Unidentified Fairy', '&': 'Unidentified Elf',
}
SPRITE_NAMES.update(dict.fromkeys(
    ('player sword', 'player cursed sword', 'player blessed'), 'Player'))
SPRITE_NAMES.update({f'{name}-{skin}': role
                     for role, char in d.MEMBER_GLYPHS.items()
                     for name in MEMBER_SPRITES.get(char, ())
                     for skin in MEMBER_SKINS})
SPRITE_NAMES[CAT_SPRITE] = d.MEMBER_YAWNING_CAT
# Golem rubble outside the current view is darkened like explored walls.
ROCK_EXPLORED_SHADE = 0.6
# An elf the player has met (drawn without bold as text) is shown with its
# sprite and ground disc darkened to this fraction.
MET_ELF_SHADE = 0.6
# A dark translucent backing keeps the elf and treasure progress marks legible
# when the tall field sprites extend behind the bottom status row.
TEXT_PANEL_ALPHA = 112
TEXT_PANEL_PADDING = 4
# A character in one of the four cells next to the player, the one the next
# step would meet, is drawn this much larger (its ground disc keeps its size).
# Followers walking with the player keep their usual size.
NEIGHBOR_SCALE = 1.3
# Field text kept as text (such as "+" and ".") is raised by this fraction of
# a cell, so it stays within its cell above the flagstone joint.
FIELD_TEXT_RAISE = 0.1
# Width of the strength column's sprite area in field cells. Each entry keeps
# its smaller label on the left and, once the
# player has identified that type (as on the field), shows the character's
# sprite to its right, at the same size as on the field (larger ones may
# overflow their row).
STRENGTH_SPRITE_CELLS = 2
MAX_WINDOW_WIDTH = 32767
# Keep the complete field and strength column in the initial window.
HORIZONTAL_VIEW_SCROLL_CELLS = 3
HOVER_SCALE = 2.0
MOUSE_CURSOR_SECONDS = 3.0
STRENGTH_TEXT_SCALE = 0.7
# Field cells are wider than the text GUI's (13) so characters overflow
# their cells less; sprites and their discs keep the CELL_SIZE_X-based size.
SPRITE_CELL_SIZE_X = 15
# Keep an integer 30x40 pixel grid per field cell at every window size.
LOW_RESOLUTION_DETAIL_SCALE = 2.0
MIPMAP_LOD_BIAS = -1.0
# Empowered-rank marks, rendered as raised apostrophes in near-white resin and
# drawn white whatever the monster's strength color. They float at the upper
# right of the sprite instead of in the next cell: centre offset from the
# ground point in cell widths east and cell heights north.
MARK_FILES = {"'": 'mark-rank2.png', '"': 'mark-rank3.png'}
MARK_OFFSET = (0.6, 0.65)
# Every sprite uses one scale: this many source pixels (an amoeba's width
# before the amoebas were shrunk to 0.9) span 1.8 cell widths. Larger models
# therefore give larger sprites.
SPRITE_REFERENCE_PIXELS = 186
# The export camera looks 60 degrees down at a point 0.35 units above each
# model's ground origin, at 256 px per 2.6 units, with crops symmetric about
# that point; the feet are therefore this many source pixels below the image
# centre. Sprites are placed so their feet rest on the cell centre.
SPRITE_GROUND_OFFSET_PIXELS = 0.35 * math.cos(math.radians(60)) * 256 / 2.6
# Ground disc under each sprite: radius in cell widths, vertical squash for
# the same 60-degree view, opacity at the centre, and how quickly it fades
# toward the rim.
GROUND_DISC_RADIUS = 1.3
GROUND_DISC_FLATTEN = math.sin(math.radians(60))
GROUND_DISC_ALPHA = 1.0
GROUND_DISC_FALLOFF = 0.8
GROUND_DISC_TEXELS = 64
# The player's LP gauge, drawn just above its head like a fighting game's:
# this fraction of its ground disc's width, this tall and this far above the
# head (both in cell widths), on a dark backing framed in this color.
# The gauge is fully opaque so its values remain legible over any field.
LP_GAUGE_WIDTH = 0.8
LP_GAUGE_HEIGHT = 0.22
LP_GAUGE_GAP = 0.52
LP_GAUGE_BACKING = (0, 0, 0, 255)
LP_GAUGE_FRAME = (235, 235, 235)
LP_GAUGE_OPACITY = 1.0
# Fairies stand inside a faint green pillar of light: an open cylinder on
# the ground disc's ellipse, seen at the same 60-degree view. Radius and side
# height in cell widths; peak opacity of the far wall (behind the sprite) and
# the near wall (over it); the sides glow brighter, and both fade upward.
PILLAR_RADIUS = 0.8
PILLAR_HEIGHT = 2.0
PILLAR_BACK_ALPHA = 0.9
PILLAR_FRONT_ALPHA = 0.4
PILLAR_EDGE = 0.45
PILLAR_FADE = 1.1
# For the turn after a respawn, the character stands in a taller column of
# light in its ground disc's main color, with helical bands twisting up the
# column. Its near wall (the outside) is brighter than the far wall seen
# through it (the inside). Bands around it, their twist in turns over the full
# height, the angle of one band's foot (0 east, increasing toward the viewer),
# and the brightness between bands. Each band is leaf-shaped: its width (a
# fraction of the band period) peaks halfway up and tapers to a point at both
# ends, the taper exponent shaping its curve.
RESPAWN_COLUMN_RADIUS = 0.7
RESPAWN_COLUMN_HEIGHT = 2.15
RESPAWN_COLUMN_BACK_ALPHA = 0.4
RESPAWN_COLUMN_FRONT_ALPHA = 0.75
RESPAWN_COLUMN_FADE = 0.7
RESPAWN_COLUMN_EDGE = 0.8
RESPAWN_COLUMN_BANDS = 5
RESPAWN_COLUMN_TWIST = 1 / 3
RESPAWN_COLUMN_START = math.radians(360 / 10)
RESPAWN_COLUMN_BAND_WIDTH = 0.6
RESPAWN_COLUMN_BAND_TAPER = 0.7
RESPAWN_COLUMN_GAP_SHADE = 0.15
RESPAWN_COLUMN_TEXELS = 96
# A respawn cell where no character sprite is drawn (a hidden or text-only
# character) lights its column alone, in this neutral color, so the
# character's strength stays unknown.
RESPAWN_COLUMN_UNSEEN_COLOR = COLOR_MAP['default']
# The fairy travelling with the player floats small at its right shoulder:
# size relative to a normal sprite, and its ground point from the player's
# cell centre (cell widths east, cell heights north).
FAMILIAR_SIZE = 0.6
FAMILIAR_OFFSET = (0.7, 0.15)
# Walls are raised blocks seen from the same 60-degree view: the top face is
# lifted this many cells north, so a wall overlaps (and may partly hide) the
# lower part of the cell just north of it. Where the cell south of a wall is
# not wall, its front face shows in that lifted band.
WALL_OVERHANG = 0.25
WALL_TOP_SHADE = 1.25
WALL_FRONT_SHADE = 0.7
# Plain wall boxes, one per cell with floor showing between them: the gap on
# the west and east (cell widths), the footprint's south edge (cell heights
# from the cell's north edge), and the height its top is lifted north. The top
# face is drawn as tall as it is wide on screen, so it reads as a square seen
# from above; it stays within WALL_OVERHANG of the cell so rows still overlap
# in order.
WALL_BLOCK_INSET = 0.12
WALL_BLOCK_SOUTH = 0.92
WALL_BLOCK_HEIGHT = 0.56
# Marble column parts (mid grey, tinted per visible/explored wall color);
# each covers one cell plus the WALL_OVERHANG band north of it.
WALL_PARTS = ('link-west', 'link-east', 'column')
# Explored walls and floor outside the current view are kept clearly darker.
WALL_TINT = {VISIBLE_WALL: 2.4, WALL: 1.75}
# Per terrain theme, the wall parts are brightened by this factor when loaded,
# since a tint can only darken them; explored tints are divided by it, so only
# visible walls get brighter.
WALL_IMAGE_GAIN = {'ruins': 1.3}
# Flagstone floor: two near-white stones laid as a checkerboard, tinted a warm
# dark grey per visible/explored floor, alternate cells slightly darker.
FLOOR_PARTS = ('a', 'b')
FLOOR_TINTS = {VISIBLE_FLOOR: (78, 72, 66), FLOOR: (42, 39, 36)}
FLOOR_CHECKER_SHADE = 0.88
# The floor fades darker toward the field's outer walls so the scrolled view's
# left and right ends read as the end of the map: (shade at the wall's inner
# face, cells until full brightness) for the sides and for the top and bottom.
# Corners take the darker of the two. The fade is a smooth, linearly filtered
# multiply layer over the floor, so walls and characters keep their colors.
EDGE_FLOOR_SIDE_FADE = (0.7, 3.5)
EDGE_FLOOR_END_FADE = (0.7, 1.5)
EDGE_FLOOR_TEXELS_PER_CELL = 4
# Terrain looks: file prefixes of the floor and wall parts, the floor tint and
# checkerboard shade, and the wall tint, per visible/explored color. Stage 5's
# training room lays concrete slabs tinted muted mint, like the flagstones'
# near-white images; other stages use the ruins. A theme without a wall prefix
# draws each wall as a plain marble-colored box (see WALL_BLOCK_*), cheap to
# draw in the room's many walls: the wall entry then gives (top face, front
# face) colors per visible/explored color.
TERRAIN_THEMES = {
    'ruins': ('floor-', 'wall-', FLOOR_TINTS, FLOOR_CHECKER_SHADE,
              {color: tuple(min(255, round(c * scale)) for c in color)
               for color, scale in WALL_TINT.items()}),
    'training': ('training-', None,
                 {VISIBLE_FLOOR: (112, 139, 128), FLOOR: (66, 82, 75)}, 0.91,
                 {VISIBLE_WALL: ((230, 224, 196), (178, 171, 144)),
                  WALL: ((152, 148, 129), (116, 111, 94))}),
}
for _theme, _gain in WALL_IMAGE_GAIN.items():
    _tints = TERRAIN_THEMES[_theme][4]
    _tints[WALL] = tuple(round(c / _gain) for c in _tints[WALL])
STAGE_TERRAIN_THEMES = {5: 'training'}
# Sprites swapped in a terrain theme: the training room's chest is a toy.
THEME_SPRITES = {'training': {'T': 'T-toy'}}
# Barrier cells show a magic barrier on the ordinary floor, in place of the
# red "=": a glowing orange plate laid over the cell and translucent sheets of
# orange light rising from its edges, fading upward, with a few sparks drifting
# inside (two variants with different shimmer and sparks, laid out as a
# checkerboard), added onto the floor; the back sheet reaches a little into the
# cell above. While the amulet or Guardian protects against barriers, the cells
# within one cell of the player (its own and the eight around it) change: with
# the damage reduced (Guardian), a small barrier, its plate half as wide and
# deep in the middle of the cell and its sheets half as high; with no damage,
# only faint grey smoke of the same shape as the full barrier.
# Barriers outside the current view are
# darkened like the floor. Sizes are in cell widths/heights.
BARRIER_TEXELS = (48, 96)
BARRIER_HEIGHT = 1.5
BARRIER_BASE = 0.0
BARRIER_ALPHA = 0.9
BARRIER_EXPLORED_SHADE = 0.5
# Gap between the plate and the cell's edges, and height of the light sheets.
BARRIER_INSET = 0.1
BARRIER_SHEET_HEIGHT = 0.55
# Peak strength of the plate's inside and rim, the front and back sheets, and
# the vertical seams where the sheets meet.
BARRIER_PLATE = (0.22, 0.75)
BARRIER_SHEETS = (0.55, 0.45)
BARRIER_SEAM = 0.6
# Per variant: shimmer phase and sparks as (across, height in sheet heights).
BARRIER_SHIMMER = (0.0, 0.5)
BARRIER_SPARKS = (((0.3, 0.45), (0.62, 0.8), (0.78, 0.3)),
                  ((0.22, 0.7), (0.5, 0.35), (0.72, 0.6)))
# Size of the reduced barrier, relative to the full one.
BARRIER_REDUCED_SCALE = 0.5
SMOKE_TINT = (150, 150, 156)
SMOKE_OPACITY = 140
# Rocks fallen through a pit (d.DECOR_FALLEN_ROCKS) are hidden where the
# cell has since become a wall, pit or stair, or a character stands there.
FALLEN_ROCK_BLOCKERS = (*d.WALL_CHARS, d.CHAR_COLLAPSE,
                        *(char for char in d.STAIR_CHARS if char != d.CHAR_SCHOLAR_STAIRS_UP))
# Stairs and Collapse pits are drawn on the walls' canvas and placed like a
# wall part: near-white marble flights (up: rising north; down: descending
# toward the viewer into a dark opening) and a shapeless hole with rocks lying
# around it. Ordinary stair flights are gold and darkened outside the current
# view; Explorer stairs use a colored text marker instead.
TERRAIN_FILES = {d.CHAR_STAIRS_UP: 'stairs/stairs-up.png',
                 d.CHAR_STAIRS_DOWN: 'stairs/stairs-down.png',
                 d.CHAR_COLLAPSE: 'pit/pit.png',
                 d.DECOR_FALLEN_ROCKS: 'pit/fallen-rocks.png'}
TERRAIN_TINT = (255, 222, 150)
# Stair and pit images reach TERRAIN_SIDE cells past each side of their cell
# and TERRAIN_OVERHANG cells into the cell to the north. A side is drawn only
# where the neighbouring cell is explored plain floor; elsewhere it is
# cropped away.
TERRAIN_SIDE = 0.25
TERRAIN_OVERHANG = {d.CHAR_STAIRS_UP: 0.5, d.CHAR_STAIRS_DOWN: 0.5,
                    d.CHAR_COLLAPSE: 0.25,
                    d.DECOR_FALLEN_ROCKS: 0.25}
TERRAIN_EXPLORED_SHADE = 0.55
# Opacity of the yellow ground disc that marks each stair.
STAIR_DISC_OPACITY = 90
# Between floors (draw_floor_transition): a near-black field with only the
# player, standing on the landing of a floating switchback when taking stairs
# (gold), both the size they are in play and on the cell the player left
# from, where the stairs or pit were on screen. The landing image covers that
# cell like the up stairs' image; the player's feet go LANDING_FEET_HEIGHT cell heights
# above its south edge, the height of the landing's tread. Climbing out of a
# pit, a rope segment ROPE_LENGTH times the player's height, the color of the
# Dungeon Explorer's hemp rope, is drawn over the player: ROPE_WIDTH cell
# widths wide and ROPE_OFFSET right of its centre. Behind the player, a faint
# glow in the green of discovered passages' floor light runs along the rope:
# the ground disc's fading image stretched ROPE_GLOW_WIDTH cell widths wide
# and ROPE_GLOW_LENGTH times the rope's length, at ROPE_GLOW_OPACITY.
LANDING_FILE = 'stairs/stairs-landing.png'
TRANSITION_BACKGROUND = (6, 6, 8)
LANDING_FEET_HEIGHT = 0.725
ROPE_COLOR = (160, 134, 96)
ROPE_WIDTH, ROPE_OFFSET, ROPE_LENGTH = 0.08, 0.1, 2.0
ROPE_GLOW_WIDTH, ROPE_GLOW_LENGTH, ROPE_GLOW_OPACITY = 0.9, 1.3, 90


def _luminance(color):
    r, g, b = color
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pillar_image(side, height=PILLAR_HEIGHT / PILLAR_RADIUS, peaks=None,
                 fade=PILLAR_FADE, band=None, width=GROUND_DISC_TEXELS, edge=PILLAR_EDGE):
    """One wall ('back' or 'front') of an open light cylinder, white with alpha.

    The image spans the cylinder's width and, from the bottom of its ground
    ellipse, the side height (in radii) plus that ellipse; the tint is applied
    when drawn. `band(angle, t)` scales the opacity at an angle around the
    cylinder (0 east, pi/2 nearest the viewer) and height fraction t.
    """
    flatten = GROUND_DISC_FLATTEN
    rows = round(width * (height + 2 * flatten) / 2)
    back, front = peaks or (PILLAR_BACK_ALPHA, PILLAR_FRONT_ALPHA)
    peak = back if side == 'back' else front
    rgba = bytearray()
    for row in range(rows):
        v = (row + 0.5) / rows * (height + 2 * flatten) - flatten
        for col in range(width):
            u = (col + 0.5) / width * 2 - 1
            depth = math.sqrt(max(0.0, 1 - u * u))
            # The far wall rises from the ellipse's upper (northern) arc.
            t = (v - (depth if side == 'back' else -depth) * flatten) / height
            alpha = 0.0
            if 0 <= t <= 1:
                rim = min(1.0, (1 - abs(u)) / 0.06)
                alpha = (peak * rim * min(1.0, edge / math.sqrt(1 - u * u + 0.02))
                         * (1 - t) ** fade)
                if band is not None:
                    angle = math.acos(max(-1.0, min(1.0, u)))
                    alpha *= band(angle if side == 'front' else -angle, t)
            rgba += bytes((255, 255, 255, round(255 * alpha)))
    return pyglet.image.ImageData(width, rows, 'RGBA', bytes(rgba), pitch=width * 4)


def respawn_column_image(side, gaps=False):
    """A respawn column wall: its helical bands, or with `gaps` the space between."""
    def band(angle, t):
        phase = RESPAWN_COLUMN_BANDS * (angle - RESPAWN_COLUMN_START
                                        + 2 * math.pi * RESPAWN_COLUMN_TWIST * t)
        # Distance from the nearest band centre, as a fraction of the period.
        offset = abs((phase / (2 * math.pi) + 0.5) % 1 - 0.5)
        half_width = RESPAWN_COLUMN_BAND_WIDTH / 2 * math.sin(math.pi * t) ** RESPAWN_COLUMN_BAND_TAPER
        value = max(0.0, min(1.0, (half_width - offset) / 0.06 + 0.5))
        return 1 - value if gaps else value
    return pillar_image(
        side, RESPAWN_COLUMN_HEIGHT / RESPAWN_COLUMN_RADIUS,
        (RESPAWN_COLUMN_BACK_ALPHA, RESPAWN_COLUMN_FRONT_ALPHA),
        RESPAWN_COLUMN_FADE, band, RESPAWN_COLUMN_TEXELS, RESPAWN_COLUMN_EDGE,
    )


def smoke_image(barrier):
    """A white copy of `barrier` with the same shape, for the cooled smoke."""
    width, height = barrier.width, barrier.height
    rgba = bytearray(barrier.get_data('RGBA', width * 4))
    for offset in range(0, len(rgba), 4):
        rgba[offset:offset + 3] = b'\xff\xff\xff'
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


def barrier_image(variant, scale=1.0):
    """A magic barrier: a glowing plate on the floor with light rising from it.

    Seen at the sprites' 60-degree view, the plate covers the cell inside a
    small inset, bright along its rim. Sheets of light rise from its near
    (front) and far (back) edges, and the side sheets show edge-on as bright
    seams; the sheets fade upward and shimmer in faint vertical bands. Parts
    combine like light so the back sheet shows through the front one. The
    image is drawn additively from the cell's bottom; `variant` (0 or 1)
    shifts the shimmer and sparks so neighbouring cells do not repeat.
    `scale` shrinks the plate about the cell's centre and the sheets' height.
    """
    width, height = BARRIER_TEXELS
    cell = 1 / BARRIER_HEIGHT  # one cell height, in image fractions
    inset = 0.5 - (0.5 - BARRIER_INSET) * scale
    near, far = inset * cell, (1 - inset) * cell
    sheet = BARRIER_SHEET_HEIGHT * scale * cell
    phase = BARRIER_SHIMMER[variant]
    sparks = [(0.5 + (u - 0.5) * scale, t) for u, t in BARRIER_SPARKS[variant]]
    plate_color, low, high = (255, 125, 30), (255, 150, 45), (255, 85, 10)
    rgba = bytearray()
    for row in range(height):
        v = (row + 0.5) / height
        for col in range(width):
            u = (col + 0.5) / width
            parts = []  # (strength, how far up the sheets, 0..1)
            inside_u = inset <= u <= 1 - inset
            # Distance to the plate's rim, in cell widths (v rescaled to cells).
            rim = min(u - inset, 1 - inset - u, (v - near) / cell, (far - v) / cell)
            if rim >= 0:
                inner, edge = BARRIER_PLATE
                parts.append((inner + (edge - inner) * max(0.0, 1 - rim / 0.06), 0.0))
            elif rim > -0.05:
                parts.append((BARRIER_PLATE[1] * (1 + rim / 0.05) ** 2, 0.0))
            wave_u = 0.5 + (u - 0.5) / scale  # across the full-size plate
            shimmer = 0.75 + 0.25 * math.sin(2 * math.pi * (wave_u * 3 + phase))
            for base, peak in ((near, BARRIER_SHEETS[0]), (far, BARRIER_SHEETS[1])):
                t = (v - base) / sheet
                if inside_u and 0 <= t < 1:
                    parts.append((peak * shimmer * (1 - t) ** 1.6, t))
            # Side sheets seen edge-on: thin seams from the front edge to the
            # top of the back sheet.
            t = (v - near) / (far - near + sheet)
            if 0 <= t < 1:
                for side in (inset, 1 - inset):
                    across = abs(u - side) / 0.03
                    if across < 1:
                        top = max(0.0, (v - far) / sheet)
                        parts.append((BARRIER_SEAM * (1 - across ** 2) * (1 - top) ** 1.6,
                                      top))
            for spark_u, spark_t in sparks:
                d2 = ((u - spark_u) / 0.035) ** 2 + ((v - near - spark_t * sheet) / 0.02) ** 2
                if d2 < 1:
                    parts.append((0.8 * (1 - d2), spark_t))
            clear, weight, along = 1.0, 0.0, 0.0
            for value, t in parts:
                clear *= 1 - min(1.0, value)
                weight += value
                along += value * t
            strength = 1 - clear
            if weight > 0 and along == 0:
                color = plate_color
            else:
                mix = min(1.0, along / weight) if weight > 0 else 1.0
                color = [round(a + (b - a) * mix) for a, b in zip(low, high)]
            rgba += bytes((*color, round(255 * min(1.0, BARRIER_ALPHA * strength))))
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


def ground_disc_image(half=None):
    """White disc whose opacity fades from the centre to a transparent rim.

    `half` keeps only the 'upper-right' or 'lower-left' side of the diagonal.
    """
    size = GROUND_DISC_TEXELS
    rgba = bytearray()
    for row in range(size):
        for col in range(size):
            u, v = (col + 0.5) / size * 2 - 1, (row + 0.5) / size * 2 - 1
            r = math.hypot(u, v)
            alpha = GROUND_DISC_ALPHA * max(0.0, 1 - r) ** GROUND_DISC_FALLOFF
            # Image rows run bottom to top, so v grows upward.
            if half is not None and (u + v > 0) != (half == 'upper-right'):
                alpha = 0
            rgba += bytes((255, 255, 255, round(255 * alpha)))
    return pyglet.image.ImageData(size, size, 'RGBA', bytes(rgba), pitch=size * 4)


def gray_image(data):
    """Grayscale copy of image data, keeping its alpha."""
    rgba = bytearray(data.get_data('RGBA', data.width * 4))
    for offset in range(0, len(rgba), 4):
        r, g, b = rgba[offset:offset + 3]
        gray = (299 * r + 587 * g + 114 * b) // 1000
        rgba[offset:offset + 3] = bytes((gray, gray, gray))
    return pyglet.image.ImageData(data.width, data.height, 'RGBA', bytes(rgba),
                                  pitch=data.width * 4)


def brightened_image(data, gain):
    """Copy of image data with its colors scaled by gain (clipped), alpha kept."""
    rgba = data.get_data('RGBA', data.width * 4)
    table = bytes(min(255, round(value * gain)) for value in range(256))
    bright = bytearray(rgba.translate(table))
    bright[3::4] = rgba[3::4]
    return pyglet.image.ImageData(data.width, data.height, 'RGBA', bytes(bright),
                                  pitch=data.width * 4)


def edge_floor_bounds(field):
    """Find the first non-wall column and row from each edge."""
    points = [(x, y) for y, row in enumerate(field)
              for x, cell in enumerate(row)
              if cell not in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)]
    if not points:
        return (1, 1, len(field[0]) - 1, len(field) - 1)
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points) + 1, max(y for _, y in points) + 1)

def edge_floor_shade(cx, cy, width, height, bounds=None):
    """Floor shade at continuous field coordinates (in cells, origin top-left)."""
    def fade(distance, fade_spec):
        edge, cells = fade_spec
        t = min(1.0, max(0.0, distance / cells))
        return edge + (1 - edge) * t * t * (3 - 2 * t)
    left, top, right, bottom = bounds or (1, 1, width - 1, height - 1)
    side = fade(min(cx - left, right - cx), EDGE_FLOOR_SIDE_FADE)
    end = fade(min(cy - top, bottom - cy), EDGE_FLOOR_END_FADE)
    return min(side, end)


def edge_floor_shade_data(width, height, texels=EDGE_FLOOR_TEXELS_PER_CELL, bounds=None):
    """Top-down RGBA bytes of the field's edge shade, sampled at texel centers."""
    # The shade is the minimum of a per-column and a per-row fade.
    columns = [edge_floor_shade((col + 0.5) / texels, height / 2, width, height, bounds)
               for col in range(width * texels)]
    data = bytearray()
    for row in range(height * texels):
        row_shade = edge_floor_shade(width / 2, (row + 0.5) / texels, width, height, bounds)
        for column_shade in columns:
            value = round(255 * min(column_shade, row_shade))
            data += bytes((value, value, value, 255))
    return bytes(data)


def mipmapped(image):
    """Texture shrunk through mipmaps, so fine details do not flicker away.

    The PNGs carry their edge colors into transparent pixels (see
    dev-samples/3d-stage1/bleed-alpha.py), so the smaller levels get no dark
    fringe. Pyglet's get_mipmapped_texture() builds the levels before
    uploading the image, so they are generated here instead.
    """
    texture = image.get_texture()
    gl = pyglet.gl
    gl.glBindTexture(texture.target, texture.id)
    gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    # Sample one level finer than the default; the outlines blur away otherwise.
    gl.glTexParameterf(texture.target, gl.GL_TEXTURE_LOD_BIAS, MIPMAP_LOD_BIAS)
    gl.glGenerateMipmap(texture.target)
    return texture


class SpriteUI(PygletUI):
    """Reuse input, menus, visibility and glyph selection without duplicating rules."""

    supports_horizontal_view = True
    supports_floor_transition = True
    dim_protected_hazards = False

    # Decorations of the floor being drawn (see draw_stage), and the cells to
    # draw fallen rocks on once the characters of this frame are known.
    _decor = None
    _fallen_rock_draws = ()
    _field_text_cells = frozenset()
    # The player's cell this frame (None while viewing another floor), and
    # whether characters next to it are enlarged (off while drawing followers).
    _player_cell = None
    _enlarge_neighbors = True
    # Monster types the player has identified, for the strength column.
    _known_types = frozenset()
    # Current view and, while barriers are weakened, the player's cell that
    # cools the barrier stones around it.
    _cur_torched = None
    _cooling_center = None
    _cooling_damage = None
    # The field being drawn, for stairs and pits that spread over neighbouring floor.
    _stage_field = None
    _stage_discovered_at = None
    # Terrain look of the stage being drawn (see TERRAIN_THEMES).
    _theme_images = {}
    _terrain_theme = 'ruins'
    _floor_tints = FLOOR_TINTS
    _floor_checker_shade = FLOOR_CHECKER_SHADE
    _wall_tints = TERRAIN_THEMES['ruins'][4]
    _respawn_glows = frozenset()
    # Respawn cells of this frame on known cells, and those whose column a
    # character's sprite has drawn.
    _respawn_draws = ()
    _respawn_columns_drawn = frozenset()
    _show_pit_up_marker = True

    def _initialize_state(self):
        super()._initialize_state()
        self._mouse_position = None
        self._mouse_visible_until = None
        self._edge_shade_fields = {}
        self._horizontal_scroll_px = 0
        self._floor_tiles = None
        self._floor_backdrops = {}
        self._use_floor_backdrop = False
        self._floor_backdrop_pending = False
        self._edge_shade_pending = False
        self._ration_images = None
        self._sprite_images = {}
        self._sprite_head_room = {}
        self._theme_floor_tiles = {}
        self._wall_rect_colors = {}

    def __init__(self, scale=None, key_repeat_interval=None):
        self._member_variants = {char: random.choice(names) for char, names in MEMBER_SPRITES.items()}
        self._member_skins = {char: random.choice(MEMBER_SKINS) for char in MEMBER_SPRITES}
        self._last_stage_draw = None
        self._resize_redraw_pending = False
        self._render_framebuffer = None
        self._render_texture = None
        self._composite_batch = None
        self._composite_sprite = None
        self._render_target_size = None
        self._failed_render_target_size = None
        super().__init__(scale, key_repeat_interval, resizable=True)
        self.window.push_handlers(
            on_mouse_motion=self._on_mouse_motion,
            on_mouse_drag=self._on_mouse_drag,
            on_mouse_leave=self._on_mouse_leave,
        )
        self._text_batch = pyglet.graphics.Batch()
        self._hud_row_height = self._menu_cell_size_y
        self._set_scaled_dimensions()
        self.window.set_size(self.window_width, self.window_height)
        self._drawing_hud = False
        self.window.set_caption(self.window.caption.replace('Pyglet mix', 'Sprite mix'))
        self._update_minimum_window_size()
        directory = Path(__file__).parent / 'assets' / 'characters'
        self._gray_images = {}
        for char, filename in SPRITE_FILES.items():
            path = directory / filename
            if not path.is_file():
                continue
            data = pyglet.image.load(str(path)).get_image_data()
            self._sprite_images[char] = mipmapped(data)
            rgba = data.get_data('RGBA', data.width * 4)
            # Fully transparent rows above the character (rows run bottom
            # to top), so things drawn over its head sit on the head itself.
            row_bytes = data.width * 4
            opaque_rows = [y for y in range(data.height)
                           if any(rgba[y * row_bytes + 3:(y + 1) * row_bytes:4])]
            self._sprite_head_room[char] = data.height - 1 - max(opaque_rows, default=0)
            self._gray_images[char] = mipmapped(gray_image(data))
        self._mark_images = {mark: mipmapped(pyglet.image.load(str(directory / filename)))
                             for mark, filename in MARK_FILES.items()
                             if (directory / filename).is_file()}
        # Cells where a character sprite was drawn this frame; a rank mark in
        # the next cell belongs to that sprite.
        self._sprite_cells = {}
        self._disc_image = ground_disc_image()
        self._disc_halves = (ground_disc_image('lower-left'), ground_disc_image('upper-right'))
        self._disc_group = pyglet.graphics.Group(order=1)
        self._pillar_images = {side: pillar_image(side) for side in ('back', 'front')}
        self._respawn_column_images = {
            (side, gaps): respawn_column_image(side, gaps)
            for side in ('back', 'front') for gaps in (False, True)
        }
        assets = Path(__file__).parent / 'assets'
        # Per theme: wall parts, floor images and their grayscale copies for
        # the map display. A theme whose images are missing uses the ruins'.
        self._theme_images = {}
        for theme, (floor_prefix, wall_prefix, *_) in TERRAIN_THEMES.items():
            walls = None
            if wall_prefix is not None:
                paths = [assets / 'walls' / (wall_prefix + part + '.png') for part in WALL_PARTS]
                if all(path.is_file() for path in paths):
                    walls = {part: mipmapped(brightened_image(
                                 pyglet.image.load(str(path)).get_image_data(),
                                 WALL_IMAGE_GAIN.get(theme, 1)))
                             for part, path in zip(WALL_PARTS, paths)}
            floor_paths = [assets / 'floor' / (floor_prefix + part + '.png')
                           for part in FLOOR_PARTS]
            floors = grays = None
            if all(path.is_file() for path in floor_paths):
                data = [pyglet.image.load(str(path)).get_image_data() for path in floor_paths]
                floors = [mipmapped(image) for image in data]
                grays = [mipmapped(gray_image(image)) for image in data]
            ruins = self._theme_images.get('ruins', (None, None, None))
            if wall_prefix is not None and walls is None:
                walls = ruins[0]
            self._theme_images[theme] = (walls, floors or ruins[1],
                                         grays if floors else ruins[2])
        self._set_terrain_theme('ruins')
        self._terrain_images = {char: mipmapped(pyglet.image.load(str(assets / filename)))
                                for char, filename in TERRAIN_FILES.items()
                                if (assets / filename).is_file()}
        bridgehead_path = assets / 'bridgehead' / 'bridgehead.png'
        if bridgehead_path.is_file():
            placement = json.loads((bridgehead_path.parent / 'bridgehead.json').read_text())
            self._bridgehead_under = placement['under']
            self._bridgehead_height = 1 + placement['under'] + placement['overhang']
            bridgehead = mipmapped(pyglet.image.load(str(bridgehead_path)))
            half = bridgehead.width // 2
            self._bridgehead_images = {part: bridgehead.get_region(i * half, 0, half, bridgehead.height)
                                       for i, part in enumerate(('/', '\\'))}
        else:
            self._bridgehead_images = {}
        self._terrain_regions = {}
        core_path = assets / 'dungeon-core' / 'dungeon-core.png'
        self._dungeon_core_image = None
        self._dungeon_core_under = self._dungeon_core_overhang = 0.0
        if core_path.is_file():
            placement = json.loads(core_path.with_suffix('.json').read_text())
            self._dungeon_core_under = placement['under']
            self._dungeon_core_overhang = placement['overhang']
            self._dungeon_core_image = mipmapped(pyglet.image.load(str(core_path)))
        self._landing_image = (mipmapped(pyglet.image.load(str(assets / LANDING_FILE)))
                               if (assets / LANDING_FILE).is_file() else None)
        self._barrier_images = [barrier_image(variant) for variant in (0, 1)]
        self._reduced_barrier_images = [barrier_image(variant, BARRIER_REDUCED_SCALE)
                                        for variant in (0, 1)]
        self._smoke_images = [smoke_image(barrier) for barrier in self._barrier_images]
        self._floor_group = pyglet.graphics.Group(order=-1)
        self._floor_backdrop_group = pyglet.graphics.Group(order=-2)
        # Between the floor and the ground discs.
        self._edge_shade_group = pyglet.graphics.Group(order=0)
        self._edge_shade_image = None
        self._edge_shade_bounds = None
        # Rows are painted north to south: a row's walls, then its characters,
        # so walls overlap characters to their north but not to their south.
        self._row_groups = {}
        self._overlay_group = pyglet.graphics.Group(order=10000)
        # Above every field row, below the HUD panels.
        self._lp_gauge_group = pyglet.graphics.Group(order=9000)
        self._text_panel_group = pyglet.graphics.Group(order=9999)
        self._text_overlay_group = pyglet.graphics.Group(order=10001)
        self._sidebar_bg_group = pyglet.graphics.Group(order=9998)
        self._sidebar_group = pyglet.graphics.Group(order=9999)
        self._floor_cells = {}
        for theme in TERRAIN_THEMES:
            self._set_terrain_theme(theme)
            self._create_floor_tiles()
            self._theme_floor_tiles[theme] = (self._floor_tiles, self._floor_cell_tiles)
        self._set_terrain_theme('ruins')
        self._use_floor_backdrop = True

    def _set_terrain_theme(self, theme):
        self._terrain_theme = theme
        self._wall_images, self._floor_images, self._gray_floor_images = self._theme_images[theme]
        _, _, self._floor_tints, self._floor_checker_shade, self._wall_tints = (
            TERRAIN_THEMES[theme])
        self._floor_tiles, self._floor_cell_tiles = self._theme_floor_tiles.get(theme, (None, {}))

    def _create_floor_tiles(self):
        """Bake colored 2x2 floors into one nearest-filtered texture atlas."""
        self._floor_tiles, self._floor_cell_tiles = None, {}
        if self._floor_images is None:
            return
        gl = pyglet.gl
        cell_width = round(SPRITE_CELL_SIZE_X * LOW_RESOLUTION_DETAIL_SCALE)
        cell_height = round(CELL_SIZE_Y * LOW_RESOLUTION_DETAIL_SCALE)
        width, height = 2 * cell_width, 2 * cell_height
        texture = pyglet.image.Texture.create(
            2 * width, 2 * height, min_filter=gl.GL_NEAREST, mag_filter=gl.GL_NEAREST,
        )
        framebuffer = pyglet.image.Framebuffer()
        viewport = (gl.GLint * 4)()
        binding = gl.GLint()
        clear_color = (gl.GLfloat * 4)()
        color_mask = (gl.GLboolean * 4)()
        gl.glGetIntegerv(gl.GL_VIEWPORT, viewport)
        gl.glGetIntegerv(gl.GL_FRAMEBUFFER_BINDING, binding)
        gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE, clear_color)
        gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK, color_mask)
        framebuffer.attach_texture(texture)
        projection = self.window.projection
        batch = pyglet.graphics.Batch()
        sprites = []
        tiles, cells = {}, {}
        complete = False
        try:
            framebuffer.bind()
            complete = framebuffer.is_complete
            if not complete:
                return
            gl.glViewport(0, 0, texture.width, texture.height)
            self.window.projection = pyglet.math.Mat4.orthogonal_projection(
                0, texture.width, 0, texture.height, -255, 255,
            )
            gl.glColorMask(True, True, True, True)
            gl.glClearColor(0, 0, 0, 1)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            # Resolve the source transparency against black once; copied floor
            # cells are opaque, while missing cells are never copied.
            gl.glColorMask(True, True, True, False)
            for row, map_mode in enumerate((False, True)):
                for col, (tile_color, tint) in enumerate(self._floor_tints.items()):
                    left, bottom = col * width, row * height
                    for y in range(2):
                        for x in range(2):
                            odd = (x + y) % 2
                            image = (self._gray_floor_images if map_mode
                                     else self._floor_images)[odd]
                            shade = self._floor_checker_shade if odd else 1
                            color = tuple(round(c * shade) for c in tint)
                            if map_mode:
                                value = round(color[0] * .299 + color[1] * .587 + color[2] * .114)
                                color = (value,) * 3
                            sprite = pyglet.sprite.Sprite(
                                image, x=left + x * cell_width,
                                y=bottom + (1 - y) * cell_height, batch=batch,
                            )
                            sprite.scale_x = cell_width / image.width
                            sprite.scale_y = cell_height / image.height
                            sprite.color = color
                            sprites.append(sprite)
                    key = tile_color, map_mode
                    tiles[key] = texture.get_region(left, bottom, width, height)
                    cells[key] = tuple(texture.get_region(
                        left + parity * cell_width, bottom + cell_height,
                        cell_width, cell_height,
                    ) for parity in (0, 1))
            batch.draw()
            self._floor_tiles, self._floor_cell_tiles = tiles, cells
        finally:
            for sprite in sprites:
                sprite.delete()
            self.window.projection = projection
            gl.glColorMask(*color_mask)
            gl.glClearColor(*clear_color)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, binding.value)
            gl.glViewport(*viewport)
            framebuffer.delete()
            if not complete:
                texture.delete()

    ROW_LAYERS = ('wall', 'column', 'pillar-back', 'sprite', 'pillar-front', 'familiar',
                  'familiar-front', 'mark')

    def _row_group(self, y, layer):
        if layer == 'hover':
            order = 9500
        elif layer == 'hover-mark':
            order = 9501
        elif layer == 'hover-name':
            order = 9502
        else:
            order = 10 + len(self.ROW_LAYERS) * y + self.ROW_LAYERS.index(layer)
        if order not in self._row_groups:
            self._row_groups[order] = pyglet.graphics.Group(order=order)
        return self._row_groups[order]

    def _set_edge_shade_field(self, field):
        key = id(field)
        if key not in self._edge_shade_fields:
            self._edge_shade_fields[key] = (field, edge_floor_bounds(field))
        bounds = self._edge_shade_fields[key][1]
        if bounds != self._edge_shade_bounds:
            self._edge_shade_bounds = bounds
            self._edge_shade_image = None

    def draw_stage(self, *, decor=None, **kwargs):
        self._update_strength_column_width()
        self.field_pixel_width = max(
            self.cell_size_x, self.window_width - self.strength_column_width,
        )
        field = kwargs.get('field')
        if field:
            self._set_edge_shade_field(field)
        self._last_stage_draw = (decor, kwargs.copy())
        theme = STAGE_TERRAIN_THEMES.get(kwargs.get('stage_num'), 'ruins')
        if theme != self._terrain_theme and theme in self._theme_images:
            self._set_terrain_theme(theme)
        self._decor = decor
        self._respawn_glows = kwargs.get('respawn_glows') or set()
        self._known_types = kwargs.get('known_types') or set()
        self._cur_torched = kwargs.get('cur_torched')
        player = kwargs.get('player')
        self._show_pit_up_marker = (
            player is not None and d.has_member(player, d.MEMBER_DUNGEON_EXPLORER)
        )
        if player is not None and not kwargs.get('floor_view'):
            player_pos = (player.x, player.y, player.current_floor)
            if (
                self._last_camera_player_pos is not None
                and player_pos != self._last_camera_player_pos
            ):
                self._camera_follow_player = True
            self._last_camera_player_pos = player_pos
            if self._camera_follow_player:
                self._center_camera_on_player(player.x)
        self._cooling_center = (
            (player.x, player.y)
            if player is not None and not kwargs.get('floor_view') and barrier_lp_damage(player) < d.BARRIER_LP_DAMAGE
            else None
        )
        self._cooling_damage = barrier_lp_damage(player) if self._cooling_center else None
        result = super().draw_stage(decor=decor, **kwargs)
        return result

    def _draw_text(
        self,
        pos,
        text,
        color,
        bold=False,
        x_offset=0,
        size_scale=1.0,
        group=None,
        y_offset=0,
    ):
        if self._menu_active:
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )
        x = pos[0] * self.cell_size_x + x_offset
        y = self.window_height - pos[1] * self.cell_size_y + y_offset
        hud_bottom = 2 * self._hud_row_height
        if (
            not self._drawing_hud
            and x < self.field_pixel_width
            and y > hud_bottom
            and group is not self._text_overlay_group
        ):
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )

        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )
        finally:
            self.batch = scene_batch

    def _flip(self):
        self._draw_and_flip()

    def _framebuffer_size(self):
        get_size = getattr(self.window, 'get_framebuffer_size', None)
        if get_size is not None:
            return get_size()
        return self.window.width, self.window.height

    def _render_target_dimensions(self):
        density = LOW_RESOLUTION_DETAIL_SCALE / self.scale
        return (
            max(1, math.ceil(self.window.width * density)),
            max(1, math.ceil(self.window.height * density)),
        )

    def _ensure_render_target(self):
        target_size = self._render_target_dimensions()
        if (target_size == self._render_target_size
                or target_size == self._failed_render_target_size):
            return

        if self._composite_sprite is not None:
            self._composite_sprite.delete()
            self._composite_sprite = None
        self._composite_batch = None
        if self._render_framebuffer is not None:
            self._render_framebuffer.delete()
        if self._render_texture is not None:
            self._render_texture.delete()

        texture = pyglet.image.Texture.create(
            *target_size,
            min_filter=pyglet.gl.GL_LINEAR,
            mag_filter=pyglet.gl.GL_LINEAR,
        )
        framebuffer = pyglet.image.Framebuffer()
        framebuffer.attach_texture(texture, attachment=pyglet.gl.GL_COLOR_ATTACHMENT0)
        framebuffer.bind()
        framebuffer_complete = framebuffer.is_complete
        framebuffer.unbind()
        if not framebuffer_complete:
            framebuffer.delete()
            texture.delete()
            self._render_framebuffer = None
            self._render_texture = None
            self._render_target_size = None
            self._failed_render_target_size = target_size
            return

        self._render_texture = texture
        self._render_framebuffer = framebuffer
        self._render_target_size = target_size
        self._failed_render_target_size = None
        self._composite_batch = pyglet.graphics.Batch()
        # Copy the target as is: its alpha was already blended into the colors,
        # and blending it again would darken translucent parts.
        self._composite_sprite = pyglet.sprite.Sprite(
            texture, x=0, y=0, batch=self._composite_batch,
            blend_src=pyglet.gl.GL_ONE, blend_dest=pyglet.gl.GL_ZERO,
        )
        self._update_composite_scale()

    def _update_composite_scale(self):
        if self._composite_sprite is None:
            return
        unit = self.scale / LOW_RESOLUTION_DETAIL_SCALE
        self._composite_sprite.scale = unit
        self._composite_sprite.y = self.window.height - self._render_texture.height * unit

    def _draw_and_flip(self):
        self.window.switch_to()
        if not self._menu_active:
            self._ensure_render_target()
        self._update_composite_scale()
        use_render_target = self._render_framebuffer is not None and not self._menu_active
        projection = self.window.projection
        if use_render_target:
            self._render_framebuffer.bind()
            pyglet.gl.glViewport(0, 0, *self._render_target_size)
            unit = self.scale / LOW_RESOLUTION_DETAIL_SCALE
            width, height = self._render_target_size
            self.window.projection = pyglet.math.Mat4.orthogonal_projection(
                0, width * unit, self.window_height - height * unit,
                self.window_height, -255, 255,
            )
        try:
            self.window.clear()
            self._finish_drawables()
            self.batch.draw()
        finally:
            if use_render_target:
                self._render_framebuffer.unbind()
                self.window.projection = projection
                pyglet.gl.glViewport(0, 0, *self._framebuffer_size())
        if use_render_target:
            self.window.clear()
            self._composite_batch.draw()
        self._text_batch.draw()
        self.window.flip()

    def _pump(self):
        super()._pump()
        deadline = self._mouse_visible_until
        if deadline is not None and time.monotonic() >= deadline:
            self.window.set_mouse_visible(False)
            self._mouse_visible_until = None
            self._mouse_position = None
            self._resize_redraw_pending = True
        if not self._resize_redraw_pending or not self._stage_input_active:
            return
        self._resize_redraw_pending = False
        if self._last_stage_draw is not None:
            decor, kwargs = self._last_stage_draw
            self.draw_stage(decor=decor, **kwargs)

    def _on_mouse_motion(self, x, y, dx, dy):
        self._mouse_position = (x, y)
        self._mouse_visible_until = time.monotonic() + MOUSE_CURSOR_SECONDS
        self.window.set_mouse_visible(True)
        self._resize_redraw_pending = True

    def _on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._on_mouse_motion(x, y, dx, dy)

    def _on_mouse_leave(self, x, y):
        self._mouse_position = None
        self._mouse_visible_until = None
        self.window.set_mouse_visible(False)
        self._resize_redraw_pending = True

    def _hovered_cell(self):
        mouse = self._mouse_position
        if mouse is None or self._menu_active:
            return None
        x, y = mouse
        field_y = self.window_height - y
        if not (0 <= x < self.field_pixel_width
                and 0 <= field_y < self.field_height * self.cell_size_y):
            return None
        col = math.floor((x + self._horizontal_scroll_px) / self.cell_size_x)
        row = math.floor(field_y / self.cell_size_y)
        if 0 <= col < self.field_width:
            return col, row
        return None

    def _near_cooling_center(self, x, y):
        if self._cooling_center is None:
            return False
        cx, cy = self._cooling_center
        return max(abs(x - cx), abs(y - cy)) <= 1

    def _barrier_look(self, x, y):
        """'light', or near the player while weakened, 'reduced' or 'smoke'."""
        if not self._near_cooling_center(x, y):
            return 'light'
        return 'reduced' if self._cooling_damage else 'smoke'

    def _draw_barrier(self, x, y, field, discovered_at):
        """Orange magic light rising from the floor; near the player while weakened,
        a small barrier (reduced damage) or faint smoke (no damage)."""
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        self._draw_floor(x, y, VISIBLE_FLOOR if visible else FLOOR, field, discovered_at)
        look = self._barrier_look(x, y)
        cooled = look == 'smoke'
        images = (self._smoke_images if cooled else self._reduced_barrier_images
                  if look == 'reduced' else self._barrier_images)
        image = images[(x + y) % 2]
        bottom = self.window_height - (y + 1 - BARRIER_BASE) * self.cell_size_y
        group = self._row_group(y, 'pillar-back')
        blend_dest = pyglet.gl.GL_ONE_MINUS_SRC_ALPHA if cooled else pyglet.gl.GL_ONE
        scale_x = (self._field_col_width(x) + 1) / image.width
        scale_y = BARRIER_HEIGHT * self.cell_size_y / image.height
        tint = (self._display_color(SMOKE_TINT) if cooled else self._display_color(
            (round(255 * (1 if visible else BARRIER_EXPLORED_SHADE)),) * 3
        ))
        opacity = SMOKE_OPACITY if cooled else 255
        signature = ('barrier-cell', x, y, id(image), bottom, scale_x, scale_y,
                     id(group), pyglet.gl.GL_SRC_ALPHA, blend_dest, tint, opacity)
        light = self._draw_bounded_object(
            self._field_col_x(x), image.width * scale_x, signature,
            lambda: pyglet.sprite.Sprite(
                image, x=self._field_col_x(x), y=bottom,
                blend_src=pyglet.gl.GL_SRC_ALPHA, blend_dest=blend_dest,
                batch=self.batch, group=group,
            ),
        )
        if light is not None and light.x != self._field_col_x(x):
            light.x = self._field_col_x(x)
        self._set_drawable_attribute(light, 'scale_x', scale_x)
        self._set_drawable_attribute(light, 'scale_y', scale_y)
        self._set_drawable_attribute(light, 'color', tint)
        self._set_drawable_attribute(light, 'opacity', opacity)

    def _draw_d_gate(self, pos, glyph):
        x, y = pos
        self._draw_ground_disc(self._field_col_x(x) + self.cell_size_x / 2,
                               (y + 0.5) * self.cell_size_y,
                               GROUND_DISC_RADIUS * self._sprite_unit(),
                               COLOR_MAP[CI_GREEN])

    def _draw_stairs(self, pos, char):
        if char == d.CHAR_SCHOLAR_STAIRS_UP:
            if not self._show_pit_up_marker:
                return
            x, y = pos
            self._draw_ground_disc(self._field_col_x(x) + self.cell_size_x / 2,
                                   (y + 0.5) * self.cell_size_y,
                                   GROUND_DISC_RADIUS * self._sprite_unit(),
                                   COLOR_MAP[CI_GREEN])
            return
        if char in d.SCHOLAR_STAIR_CHARS:
            return super()._draw_stairs(pos, char)
        if char not in self._terrain_images:
            return super()._draw_stairs(pos, char)
        x, y = pos
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        shade = 1 if visible else TERRAIN_EXPLORED_SHADE
        stair_color = COLOR_MAP[CI_YELLOW]
        # A ground disc gives stairs a distinct colored marker.
        self._draw_ground_disc(self._field_col_x(x) + self.cell_size_x / 2,
                               (y + 0.5) * self.cell_size_y,
                               GROUND_DISC_RADIUS * self._sprite_unit(),
                               tuple(round(c * shade) for c in stair_color),
                               opacity=STAIR_DISC_OPACITY)
        # The up flight rises into the cell to the north, like a column.
        self._draw_terrain(
            pos, char, 'column' if char == d.CHAR_STAIRS_UP else 'wall'
        )

    def _draw_bridgehead(self, pos, part, visible):
        image = self._bridgehead_images.get(part)
        if image is None:
            return super()._draw_bridgehead(pos, part, visible)
        x, y = pos
        left = self._field_col_x(x)
        bottom = self.window_height - (y + 1 + self._bridgehead_under) * self.cell_size_y
        scale_x = self.cell_size_x / image.width
        scale_y = self._bridgehead_height * self.cell_size_y / image.height
        shade = 1 if visible else TERRAIN_EXPLORED_SHADE
        tint = self._display_color((round(255 * shade),) * 3)
        group = self._row_group(y, 'column')
        signature = ('terrain-cell', 'bridgehead', x, y, id(image), bottom,
                     scale_x, scale_y, id(group), tint)
        sprite = self._draw_bounded_object(
            left, image.width * scale_x, signature,
            partial(pyglet.sprite.Sprite, image, x=left, y=bottom,
                    batch=self.batch, group=group),
        )
        if sprite is not None and sprite.x != left:
            sprite.x = left
        self._set_drawable_attribute(sprite, 'scale_x', scale_x)
        self._set_drawable_attribute(sprite, 'scale_y', scale_y)
        self._set_drawable_attribute(sprite, 'color', tint)

    def _open_floor(self, x, y):
        field = self._stage_field
        return (field is not None and 0 <= y < len(field) and 0 <= x < len(field[y])
                and field[y][x] in (d.CHAR_FLOOR, d.CHAR_PIT_LANDING)
                and self._stage_discovered_at(x, y))

    def _draw_pit(self, pos):
        if d.CHAR_COLLAPSE not in self._terrain_images:
            return super()._draw_pit(pos)
        self._draw_terrain(pos, d.CHAR_COLLAPSE, 'wall')

    def _draw_terrain(self, pos, char, layer, tint=None):
        """Draw a terrain image over its cell, spreading over the explored
        plain floor beside it."""
        x, y = pos
        image = self._terrain_images[char]
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        shade = 1 if visible else TERRAIN_EXPLORED_SHADE
        base = tint or ((220, 220, 220) if self.map_mode else TERRAIN_TINT)
        draw_tint = self._display_color(tuple(round(c * shade) for c in base))
        left = self._field_col_x(x)
        bottom = self.window_height - (y + 1) * self.cell_size_y
        sides = self._open_floor(x - 1, y), self._open_floor(x + 1, y)
        cell_pixels = image.width / (1 + 2 * TERRAIN_SIDE)
        image = self._terrain_region(char, image, sides, round(TERRAIN_SIDE * cell_pixels))
        if sides[0]:
            left -= TERRAIN_SIDE * self.cell_size_x
        scale_x = self.cell_size_x / cell_pixels
        scale_y = (1 + TERRAIN_OVERHANG[char]) * self.cell_size_y / image.height
        group = self._row_group(y, layer)
        signature = ('terrain-cell', x, y, id(image), bottom, scale_x, scale_y, id(group), draw_tint)
        terrain = self._draw_bounded_object(
            left, image.width * scale_x, signature,
            partial(pyglet.sprite.Sprite, image, x=left, y=bottom,
                    batch=self.batch, group=group),
        )
        if terrain is not None and terrain.x != left:
            terrain.x = left
        self._set_drawable_attribute(terrain, 'scale_x', scale_x)
        self._set_drawable_attribute(terrain, 'scale_y', scale_y)
        self._set_drawable_attribute(terrain, 'color', draw_tint)

    def _terrain_region(self, char, image, sides, side_pixels):
        """The terrain image less each side that may not spread, kept for reuse."""
        if all(sides):
            return image
        key = char, sides
        if key not in self._terrain_regions:
            x0 = 0 if sides[0] else side_pixels
            x1 = image.width - (0 if sides[1] else side_pixels)
            self._terrain_regions[key] = image.get_region(x0, 0, x1 - x0, image.height)
        return self._terrain_regions[key]

    def _draw_tile(self, x, y, tile_color, field, discovered_at):
        # Stairs and pits drawn after this cell look at their neighbours through these.
        self._stage_field, self._stage_discovered_at = field, discovered_at
        if (field[y][x] == d.CHAR_BARRIER and discovered_at(x, y)
                and tile_color != REACHABLE_CELL_COLOR and self._floor_images is not None):
            return self._draw_barrier(x, y, field, discovered_at)
        if (self._decor_at(x, y) in (d.DECOR_FALLEN_ROCKS, d.DECOR_BOSS_ROUTE_FALLEN_ROCKS)
                and discovered_at(x, y)
                and field[y][x] not in FALLEN_ROCK_BLOCKERS
                and d.DECOR_FALLEN_ROCKS in self._terrain_images):
            self._fallen_rock_draws += ((x, y),)
        if (x, y) in self._respawn_glows and discovered_at(x, y):
            # Respawns show in the current view and on explored cells outside it.
            self._respawn_draws += ((x, y),)
        if tile_color in FLOOR_TINTS:
            return self._draw_floor(x, y, tile_color, field, discovered_at)
        if (
            field[y][x] not in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
            or tile_color not in (VISIBLE_WALL, WALL)
        ):
            return super()._draw_tile(x, y, tile_color, field, discovered_at)
        if self._decor_at(x, y) in (d.DECOR_OUTER_WALL, d.DECOR_BURIED_WALL):
            self._draw_wall_rect(self._field_col_x(x), y * self.cell_size_y,
                                 self.cell_size_x, self.cell_size_y, tile_color, 1,
                                 self._floor_group)
            return
        floor = VISIBLE_FLOOR if tile_color == VISIBLE_WALL else FLOOR
        self._draw_floor(x, y, floor, field, discovered_at)
        if field[y][x] == d.CHAR_GOLEM_WALL and ROCK_SPRITE in self._sprite_images:
            # A wall raised by a Golem is drawn as its rubble, not a column.
            self._place_sprite(ROCK_SPRITE, self._field_col_x(x) + self.cell_size_x / 2,
                               (y + 0.5) * self.cell_size_y, 1.0, y, 'column', False,
                               1.0 if tile_color == VISIBLE_WALL else ROCK_EXPLORED_SHADE)
            return
        left, width = self._field_col_x(x), self._field_col_width(x) + 1
        top = (y - WALL_OVERHANG) * self.cell_size_y
        height = self.cell_size_y + 1
        group = self._row_group(y, 'wall')
        def wall_at(wx, wy):
            return (0 <= wy < len(field) and 0 <= wx < len(field[wy])
                    and field[wy][wx] in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
                    and discovered_at(wx, wy)
                    and field[wy][wx] != d.CHAR_GOLEM_WALL)

        if self._wall_images is not None:
            tint = self._wall_tints[tile_color]
            height = (1 + WALL_OVERHANG) * self.cell_size_y
            for part, show in (('link-west', wall_at(x - 1, y)),
                               ('link-east', wall_at(x + 1, y)), ('column', True)):
                if show:
                    image = self._wall_images[part]
                    group = self._row_group(y, 'column' if part == 'column' else 'wall')
                    bottom = self.window_height - (y + 1) * self.cell_size_y
                    scale_x = width / image.width
                    scale_y = height / image.height
                    draw_tint = self._display_color(tint)
                    signature = ('wall-cell', x, y, part, id(image), bottom, scale_x, scale_y,
                                 id(group), draw_tint)
                    piece = self._draw_bounded_object(
                        left, image.width * scale_x, signature,
                        partial(
                            pyglet.sprite.Sprite, image, x=left, y=bottom,
                            batch=self.batch, group=group,
                        ),
                    )
                    if piece is not None and piece.x != left:
                        piece.x = left
                    self._set_drawable_attribute(piece, 'scale_x', scale_x)
                    self._set_drawable_attribute(piece, 'scale_y', scale_y)
                    self._set_drawable_attribute(piece, 'color', draw_tint)
            return
        if TERRAIN_THEMES[self._terrain_theme][1] is None:
            return self._draw_wall_block(x, y, tile_color, group)
        south_is_wall = wall_at(x, y + 1)
        self._draw_wall_rect(left, top, width, height, tile_color, WALL_TOP_SHADE, group)
        if not south_is_wall:
            # Front face between the lifted top and the cell's south edge; a
            # southern wall's lifted top covers this band instead.
            front = WALL_OVERHANG * self.cell_size_y
            self._draw_wall_rect(left, (y + 1) * self.cell_size_y - front, width, front + 1,
                                 tile_color, WALL_FRONT_SHADE, group)

    def _draw_wall_block(self, x, y, tile_color, group):
        """A free-standing box a little smaller than its cell: top and front faces."""
        top_color, front_color = self._wall_tints[tile_color]
        cx, cy = self.cell_size_x, self.cell_size_y
        left = self._field_col_x(x) + WALL_BLOCK_INSET * cx
        width = (1 - 2 * WALL_BLOCK_INSET) * cx
        lift = WALL_BLOCK_HEIGHT
        front = (y + WALL_BLOCK_SOUTH - lift) * cy
        top = max(front - width, (y - WALL_OVERHANG) * cy)
        self._draw_wall_rect(left, top, width, front - top, top_color, 1, group)
        self._draw_wall_rect(left, front, width, lift * cy, front_color, 1, group)

    def _decor_at(self, x, y):
        decor = self._decor
        if decor is None or not (0 <= y < len(decor) and 0 <= x < len(decor[y])):
            return d.DECOR_NONE
        return decor[y][x]

    def _draw_floor(self, x, y, tile_color, field, discovered_at):
        self._edge_shade_pending = True
        if self._use_floor_backdrop and self._floor_tiles is not None:
            self._floor_backdrop_pending = True
            return
        if self._floor_tiles is not None:
            self._floor_cells[x, y] = tile_color
            return
        if self._floor_images is None:
            return super()._draw_tile(x, y, tile_color, field, discovered_at)
        odd = (x + y) % 2
        image = self._floor_images[odd]
        shade = self._floor_checker_shade if odd else 1
        tint = tuple(round(c * shade) for c in self._floor_tints[tile_color])
        left = self._field_col_x(x)
        bottom = self.window_height - (y + 1) * self.cell_size_y
        scale_x = (self._field_col_width(x) + 1) / image.width
        scale_y = (self.cell_size_y + 1) / image.height
        draw_tint = self._display_color(tint)
        signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                     id(self._floor_group), draw_tint)
        stone = self._draw_bounded_object(
            left, image.width * scale_x, signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=self._floor_group,
            ),
        )
        self._set_drawable_attribute(stone, 'scale_x', scale_x)
        self._set_drawable_attribute(stone, 'scale_y', scale_y)
        self._set_drawable_attribute(stone, 'color', draw_tint)

    def _draw_floor_backdrop(self):
        key = (self._terrain_theme, self.map_mode, self.field_width, self.field_height)
        image = self._floor_backdrops.get(key)
        if image is None:
            tile = self._floor_tiles[VISIBLE_FLOOR, self.map_mode].get_image_data()
            tile_width, tile_height = tile.width, tile.height
            tile_pixels = tile.get_data('RGBA', tile_width * 4)
            width = self.field_width * tile_width // 2
            height = self.field_height * tile_height // 2
            row_bytes = tile_width * 4
            repeat = (width + tile_width - 1) // tile_width
            rows = []
            for y in range(height):
                source_y = (y - height) % tile_height
                row = tile_pixels[source_y * row_bytes:(source_y + 1) * row_bytes]
                rows.append((row * repeat)[:width * 4])
            image = pyglet.image.ImageData(width, height, 'RGBA', b''.join(rows),
                                           pitch=width * 4).get_texture()
            self._floor_backdrops[key] = image
        left = self._field_col_x(0)
        bottom = self.window_height - self.field_height * self.cell_size_y
        scale_x = self.cell_size_x / (SPRITE_CELL_SIZE_X * LOW_RESOLUTION_DETAIL_SCALE)
        scale_y = self.cell_size_y / (CELL_SIZE_Y * LOW_RESOLUTION_DETAIL_SCALE)
        signature = ('floor-backdrop', id(image), left, bottom, scale_x, scale_y,
                     id(self._floor_backdrop_group))
        sprite = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=self._floor_backdrop_group,
                blend_src=pyglet.gl.GL_ONE, blend_dest=pyglet.gl.GL_ZERO,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale_x', scale_x)
        self._set_drawable_attribute(sprite, 'scale_y', scale_y)

    def _draw_floor_tiles(self):
        cells = self._floor_cells
        self._floor_cells = {}
        blocks = {(x // 2 * 2, y // 2 * 2) for x, y in cells}
        for x, y in sorted(blocks, key=lambda pos: (pos[1], pos[0])):
            positions = ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1))
            colors = [cells.get(pos) for pos in positions]
            if colors[0] is not None and all(color == colors[0] for color in colors):
                image = self._floor_tiles[colors[0], self.map_mode]
                self._copy_floor_tile(x, y, 2, image)
            else:
                # Visibility boundaries, odd field edges and special terrain
                # retain their individual cells without covering neighboring fog.
                for (cx, cy), color in zip(positions, colors):
                    if color is not None:
                        image = self._floor_cell_tiles[color, self.map_mode][(cx + cy) % 2]
                        self._copy_floor_tile(cx, cy, 1, image)

    def _copy_floor_tile(self, x, y, rows, image):
        left = self._field_col_x(x)
        bottom = self.window_height - (y + rows) * self.cell_size_y
        scale_x = self.cell_size_x / (SPRITE_CELL_SIZE_X * LOW_RESOLUTION_DETAIL_SCALE)
        scale_y = self.cell_size_y / (CELL_SIZE_Y * LOW_RESOLUTION_DETAIL_SCALE)
        signature = ('floor-copy', x, y, rows, id(image), bottom, scale_x, scale_y, id(self._floor_group))
        sprite = self._draw_bounded_object(
            left, rows * max(self.cell_size_x, SPRITE_CELL_SIZE_X * self.scale), signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=self._floor_group,
                blend_src=pyglet.gl.GL_ONE, blend_dest=pyglet.gl.GL_ZERO,
            ),
        )
        if sprite is not None and sprite.x != left:
            sprite.x = left
        self._set_drawable_attribute(sprite, 'scale_x', scale_x)
        self._set_drawable_attribute(sprite, 'scale_y', scale_y)

    def _draw_wall_rect(self, x, y, width, height, color, shade, group):
        # Walls use only a few colors; shading them per rectangle was a
        # noticeable share of a wall-heavy stage's drawing time.
        key = (color, shade, self.map_mode)
        draw_color = self._wall_rect_colors.get(key)
        if draw_color is None:
            draw_color = self._display_color(tuple(min(255, round(c * shade)) for c in color))
            self._wall_rect_colors[key] = draw_color
        bottom = self.window_height - y - height
        signature = ('rectangle', x, bottom, width, height, draw_color, id(group))
        self._draw_bounded_object(
            x, width, signature,
            lambda: pyglet.shapes.Rectangle(
                x, bottom, width, height, color=draw_color, batch=self.batch, group=group,
            ),
        )

    def draw_combat_effect(self, pos, won: bool) -> None:
        seconds = self.combat_effect_seconds
        if seconds == 0:
            return
        positions = [pos] if len(pos) == 2 and all(
            isinstance(value, (int, float)) for value in pos
        ) else pos
        name = "slash" if won else "splash"
        image = pyglet.image.load(str(
            Path(__file__).parent / "assets" / "effects" / f"{name}.png"
        ))
        padding = max(1, round(self.scale))
        size = NEIGHBOR_SCALE if won else 1.0
        scale = (size * 1.8 * max(1, self._sprite_unit() - 2 * padding)
                 / SPRITE_REFERENCE_PIXELS)
        blend = ({"blend_src": pyglet.gl.GL_SRC_ALPHA,
                  "blend_dest": pyglet.gl.GL_ONE} if won else {})
        effects = []
        for x, y in positions:
            cx = self._field_col_x(x) + self.cell_size_x / 2
            cy = (y + 0.5) * self.cell_size_y
            effect = pyglet.sprite.Sprite(
                image, x=cx - image.width * scale / 2,
                y=self.window_height - cy - (
                    image.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale,
                batch=self.batch, group=pyglet.graphics.Group(order=100000), **blend,
            )
            effect.scale = scale
            effects.append(effect)
        try:
            self._flip()
            time.sleep(seconds)
        finally:
            for effect in effects:
                effect.delete()

    def draw_floor_transition(self, kind, player, exit_point=None) -> None:
        """Show the moment between floors as a still: on the landing of the
        stairs the player is taking, or alone in the dark falling through or
        climbing out of a pit, on the cell it left from."""
        seconds = self.floor_transition_seconds
        if seconds == 0 or '@' not in self._sprite_images:
            return
        field_height = self.field_height * self.cell_size_y
        shapes = [pyglet.shapes.Rectangle(
            # The whole window's width: the scrolled field can show past
            # field_pixel_width.
            0, self.window_height - field_height,
            max(self.field_pixel_width, self.window_width or 0), field_height,
            color=self._display_color(TRANSITION_BACKGROUND), batch=self.batch,
            group=pyglet.graphics.Group(order=99998),
        )]
        cell_x, cell_y = self.cell_size_x, self.cell_size_y
        column, row = exit_point or (player.x, player.y)
        left = self._field_col_x(column)
        cx, cy = left + cell_x / 2, (row + 0.5) * cell_y
        image = self._landing_image
        if kind in ('down', 'up') and image is not None:
            cell_pixels = image.width / (1 + 2 * TERRAIN_SIDE)
            overhang = TERRAIN_OVERHANG[d.CHAR_STAIRS_UP]
            cell_bottom = (row + 1) * cell_y
            landing = pyglet.sprite.Sprite(
                image, x=left - TERRAIN_SIDE * cell_x,
                y=self.window_height - cell_bottom, batch=self.batch,
                group=pyglet.graphics.Group(order=99999),
            )
            landing.scale_x = cell_x / cell_pixels
            landing.scale_y = (1 + overhang) * cell_y / image.height
            landing.color = self._display_color(TERRAIN_TINT)
            shapes.append(landing)
            cy = cell_bottom - LANDING_FEET_HEIGHT * cell_y
        sprite = self._player_sprite(player)
        picture = self._sprite_images[sprite]
        padding = max(1, round(self.scale))
        scale = 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
        figure = pyglet.sprite.Sprite(
            picture, x=cx - picture.width * scale / 2,
            y=self.window_height - cy - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale,
            batch=self.batch, group=pyglet.graphics.Group(order=100000),
        )
        figure.scale = scale
        shapes.append(figure)
        if kind == 'climb':
            # A rope segment over the player, centred on the figure's height.
            figure_height = (picture.height / 2 + SPRITE_GROUND_OFFSET_PIXELS
                             - self._sprite_head_room.get(sprite, 0)) * scale
            length = ROPE_LENGTH * figure_height
            width = max(2, round(ROPE_WIDTH * cell_x))
            rope_x = cx + ROPE_OFFSET * cell_x
            rope_middle = cy - figure_height / 2
            glow_image = self._disc_image
            glow_width, glow_length = ROPE_GLOW_WIDTH * cell_x, ROPE_GLOW_LENGTH * length
            glow = pyglet.sprite.Sprite(
                glow_image, x=rope_x - glow_width / 2,
                y=self.window_height - rope_middle - glow_length / 2,
                batch=self.batch, group=pyglet.graphics.Group(order=99999),
            )
            glow.scale_x = glow_width / glow_image.width
            glow.scale_y = glow_length / glow_image.height
            glow.color = self._display_color(COLOR_MAP[CI_GREEN])
            glow.opacity = ROPE_GLOW_OPACITY
            shapes.append(glow)
            shapes.append(pyglet.shapes.Rectangle(
                round(rope_x - width / 2),
                self.window_height - (rope_middle + length / 2),
                width, length, color=self._display_color(ROPE_COLOR),
                batch=self.batch, group=pyglet.graphics.Group(order=100001),
            ))
        try:
            self._flip()
            time.sleep(seconds)
        finally:
            for shape in shapes:
                shape.delete()

    def _draw_player(self, pos, player):
        if '@' not in self._sprite_images:
            return super()._draw_player(pos, player)
        # Low/warning LP colors the ground disc instead of filling the cell;
        # poison turns the disc's upper-right half purple.
        self._player_cell = pos
        _, background = ui_display.player_appearance(player)
        poison = self._tone_color('magenta') if player.item == d.ITEM_POISONED else None
        top = self._draw_sprite(pos, self._player_sprite(player),
                                self._tone_color(background or 'default'), poison)
        self._draw_lp_gauge(pos, player, top)

    def _draw_player_wall_break_glyph(self, player):
        return

    def _status_shows_lp_gauge(self):
        # The gauge is drawn over the player instead (see _draw_lp_gauge).
        return '@' not in self._sprite_images

    def _draw_lp_gauge(self, pos, player, head_top):
        """The LP gauge centred just above the player's head (field pixel
        `head_top`), a little narrower than the player's ground disc."""
        unit = self._sprite_unit()
        width = round(LP_GAUGE_WIDTH * 2 * GROUND_DISC_RADIUS * unit)
        height = max(2, round(LP_GAUGE_HEIGHT * unit))
        frame = max(1, round(self.scale))
        cx = self._field_col_x(pos[0]) + self.cell_size_x / 2
        left = round(cx - width / 2)
        top = max(frame, round(head_top - LP_GAUGE_GAP * unit) - height)
        fill = round(width * self._lp_gauge_ratio(player))
        # The frame is four strips, and the fill and empty backing sit side
        # by side so the opaque gauge does not cover any part of itself.
        outer_w = width + 2 * frame
        for x, y, w, h, color in (
                (left - frame, top - frame, outer_w, frame, LP_GAUGE_FRAME),
                (left - frame, top + height, outer_w, frame, LP_GAUGE_FRAME),
                (left - frame, top, frame, height, LP_GAUGE_FRAME),
                (left + width, top, frame, height, LP_GAUGE_FRAME),
                (left, top, fill, height, self._lp_gauge_color(player)),
                (left + fill, top, width - fill, height, LP_GAUGE_BACKING)):
            if w <= 0:
                continue
            bottom = self.window_height - y - h
            alpha = color[3] if len(color) == 4 else 255
            draw_color = self._display_color((*color[:3], round(alpha * LP_GAUGE_OPACITY)))
            signature = ('rectangle', x, bottom, w, h, draw_color, id(self._lp_gauge_group))
            self._draw_bounded_object(
                x, w, signature,
                partial(pyglet.shapes.Rectangle, x, bottom, w, h, color=draw_color,
                        batch=self.batch, group=self._lp_gauge_group),
            )

    def _player_sprite(self, player):
        """The player's image for its sword: a chimera's sword it holds, else
        its own sword, glowing after the Collector Elf's blessing."""
        if player.item == d.ITEM_SWORD_X1_5:
            sprite = 'player sword'
        elif player.item == d.ITEM_SWORD_CURSED:
            sprite = 'player cursed sword'
        elif player.elf_stage_flags & d.ELF_STAGE_K_FLAG:
            sprite = 'player blessed'
        else:
            sprite = '@'
        return sprite if sprite in self._sprite_images else '@'

    def _set_scaled_dimensions(self):
        super()._set_scaled_dimensions()
        self.cell_size_x = max(1, round(SPRITE_CELL_SIZE_X * self.scale))
        self.field_pixel_width = self.field_width * self.cell_size_x
        self._select_font_size()
        self._update_strength_column_width()
        self._map_pixel_width = self.field_pixel_width
        if hasattr(self, '_hud_row_height'):
            self._hud_row_height = self._row_height_for_width(self.window_width)
            self.window_height = round(
                self.field_height * self.cell_size_y + 2 * self._hud_row_height
            )
        self.window_width = (
            self._map_pixel_width + FIELD_SIDEBAR_GAP * self.cell_size_x
            + self.strength_column_width
        )
        self.field_pixel_width = max(
            self.cell_size_x, self.window_width - self.strength_column_width
        )
        self._horizontal_scroll_px = 0
        self._camera_follow_player = True
        self._last_camera_player_pos = None

    def _sprite_unit(self):
        """Width that sizes characters, discs and the sidebar (not field cells)."""
        return CELL_SIZE_X * self.scale

    def _select_font_size(self):
        self.font_size = self._font_size_for_cells(self._sprite_unit(), self.cell_size_y)

    def _row_height_for_width(self, width):
        return self._menu_cell_size_y

    def _status_font_scale(self):
        return self._menu_font_size / self.font_size

    def _strength_text_scale(self):
        hud_font_size = (
            self.font_size if self._menu_font_size is None else self._menu_font_size
        )
        return min(STRENGTH_TEXT_SCALE, hud_font_size / self.font_size)

    def _update_strength_column_width(self):
        try:
            font_size = self.font_size * self._strength_text_scale()
            text_width = 2 * max(
                _font_glyph_metrics(self.font_name, font_size, weight)[0]
                for weight in ('normal', 'bold')
            )
        except (AttributeError, OSError, RuntimeError, ValueError):
            text_width = 2 * self._sprite_unit() * self._strength_text_scale()
        self.strength_column_width = math.ceil(
            text_width + STRENGTH_SPRITE_CELLS * self._sprite_unit()
            + 2 * self.strength_column_padding
        )

    def _status_uses_window_width(self):
        return True

    def _status_row_height(self):
        return self._hud_row_height

    def _status_row_y_offset(self, row):
        return -row * self._hud_row_height

    def _update_minimum_window_size(self):
        max_cell_width = CELL_SIZE_X * MAX_UI_SCALE
        max_padding = max(1, round(STRENGTH_COLUMN_PADDING * MAX_UI_SCALE))
        max_strength_width = (
            (2 * STRENGTH_TEXT_SCALE + STRENGTH_SPRITE_CELLS) * max_cell_width
            + 2 * max_padding
        )
        minimum_width = math.ceil(max_strength_width + SPRITE_CELL_SIZE_X * MAX_UI_SCALE)
        minimum_height = math.ceil(
            self.field_height * CELL_SIZE_Y * MIN_UI_SCALE
            + 2 * self._menu_cell_size_y
        )
        maximum_height = math.floor(
            self.field_height * CELL_SIZE_Y * MAX_UI_SCALE
            + 2 * self._menu_cell_size_y
        )
        self.window.set_minimum_size(
            minimum_width,
            minimum_height,
        )
        self.window.set_maximum_size(MAX_WINDOW_WIDTH, maximum_height)

    def _draw_rect(self, x, y, width, height, color, group=None):
        if (not self._menu_active and not self._drawing_hud
                and not self._intersects_window(x, width)):
            return
        if not self._drawing_hud:
            if (
                x == self.field_pixel_width
                and y == 0
                and width == self.strength_column_width
                and height == self.field_height * self.cell_size_y
            ):
                y_bottom = self.window_height - y - height
                if self.field_pixel_width >= self._map_pixel_width:
                    background = self._display_color((0, 0, 0))
                    signature = ('rectangle', x, y_bottom, width, height,
                                 background, id(self._sidebar_bg_group))
                    self._draw_object(
                        signature,
                        lambda: pyglet.shapes.Rectangle(
                            x, y_bottom, width, height, color=background,
                            batch=self._text_batch, group=self._sidebar_bg_group,
                        ),
                    )

                panel_color = self._display_color((0, 0, 0, TEXT_PANEL_ALPHA))
                signature = ('rectangle', x, y_bottom, width, height,
                             panel_color, id(self._sidebar_group))
                self._draw_object(
                    signature,
                    lambda: pyglet.shapes.Rectangle(
                        x, y_bottom, width, height, color=panel_color,
                        batch=self._text_batch, group=self._sidebar_group,
                    ),
                )
                return
            return super()._draw_rect(x, y, width, height, color, group=group)
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_rect(x, y, width, height, color, group=group)
        finally:
            self.batch = scene_batch

    def _draw_line(self, x1, y1, x2, y2, color, thickness=1):
        if self._drawing_hud:
            scene_batch = self.batch
            self.batch = self._text_batch
            try:
                return super()._draw_line(x1, y1, x2, y2, color, thickness)
            finally:
                self.batch = scene_batch

        if not self._intersects_window(min(x1, x2) - thickness,
                                       abs(x2 - x1) + 2 * thickness):
            return

        # Visibility boundaries and other field lines stay above sprites.
        y1, y2 = self.window_height - y1, self.window_height - y2
        draw_color = self._display_color(color)
        signature = ('line', x1, y1, x2, y2, thickness, draw_color,
                     id(self._overlay_group))
        return self._draw_object(
            signature,
            lambda: pyglet.shapes.Line(
                x1, y1, x2, y2, thickness=thickness, color=draw_color,
                batch=self.batch, group=self._overlay_group,
            ),
        )

    def _draw_ration_image(self, ration, x, y, size, dim=False):
        images = self._ration_images
        if images is None:
            self._ration_images = images = {
                name: pyglet.image.load(str(Path(__file__).parent / 'assets' / 'rations' / f'ration-{name}.png'))
                for name in d.RATIONS
            }
        picture = images[ration]
        scale = size / max(picture.width, picture.height)
        left = x - picture.width * scale / 2
        bottom = self.window_height - y - picture.height * scale / 2
        sprite = self._draw_object(
            ('ration', ration, left, bottom, scale, dim),
            lambda: pyglet.sprite.Sprite(picture, x=left, y=bottom, batch=self.batch,
                                         group=self._text_overlay_group),
        )
        sprite.scale = scale
        sprite.opacity = 60 if dim else 255

    def draw_status_bar(self, turn, player, stage_num, message, extra_keys, game_start_turn=None):
        self._drawing_hud = True
        try:
            result = super().draw_status_bar(
                turn, player, stage_num, message, extra_keys, game_start_turn,
            )
            if d.RATIONS_ENABLED and stage_num != 6 and player is not None:
                size = self._status_row_height() * 1.6
                for index, ration in enumerate(d.RATIONS):
                    self._draw_ration_image(
                        ration, self.window_width - size * (3 - index - .5),
                        self.field_height * self.cell_size_y + self._status_row_height() / 2,
                        size, index < len(d.RATIONS) - player.rations,
                    )
            return result
        finally:
            self._drawing_hud = False

    def _on_window_resize(self, width, height):
        old_cell_width = self.cell_size_x
        old_scroll_cells = self._horizontal_scroll_px / old_cell_width
        follow_player = self._camera_follow_player
        last_player_pos = self._last_camera_player_pos
        height_changed = height != self.window_height
        hud_row_height = self._row_height_for_width(width)
        if height_changed:
            self._set_resized_dimensions(width, height, hud_row_height)
            self._non_ascii_font_result = None
            if self._menu_active:
                self._menu_font_resize_pending = True
            else:
                self._select_font_size()
            self._camera_follow_player = follow_player
            self._last_camera_player_pos = last_player_pos
            self._horizontal_scroll_px = old_scroll_cells * self.cell_size_x
        else:
            self.window_width = width
            self.window_height = height
        self._update_strength_column_width()
        self.field_pixel_width = max(
            self.cell_size_x, width - self.strength_column_width
        )
        if self.field_pixel_width >= self._map_pixel_width:
            self._horizontal_scroll_px = 0
            self._camera_follow_player = True
        else:
            min_scroll, max_scroll = self._horizontal_scroll_bounds()
            self._horizontal_scroll_px = min(
                max_scroll,
                max(min_scroll, self._horizontal_scroll_px),
            )
        if self._camera_follow_player and self._last_camera_player_pos is not None:
            self._center_camera_on_player(self._last_camera_player_pos[0])
        self._resize_redraw_pending = True
        if self._menu_active:
            self._redraw_menu_text()

    def _set_resized_dimensions(self, width, height, hud_row_height):
        field_pixel_height = height - 2 * hud_row_height
        self.scale = self._valid_scale(
            field_pixel_height / (self.field_height * CELL_SIZE_Y)
        )
        self.cell_size_x = SPRITE_CELL_SIZE_X * self.scale
        self.cell_size_y = self.scale * CELL_SIZE_Y
        self.font_size = max(1, round(self.cell_size_y * FONT_HEIGHT_RATIO))
        self.strength_column_padding = max(
            1, round(STRENGTH_COLUMN_PADDING * self.scale)
        )
        self._map_pixel_width = self.field_width * self.cell_size_x
        self.window_width = width
        self._hud_row_height = hud_row_height
        # Keep the WM's actual size even when the drawing scale is clamped.
        # Requesting another size here can overwrite its restore geometry.
        self.window_height = height

    def _intersects_window(self, left, width):
        # The translucent sidebar still reveals the scene behind it.
        window_width = self.window_width
        # Linear enlargement can sample the adjacent render-target texel.
        guard = self.scale / LOW_RESOLUTION_DETAIL_SCALE
        return window_width is None or (left <= window_width + guard
                                        and left + width >= -guard)

    def _draw_bounded_object(self, left, width, signature, factory):
        if not self._intersects_window(left, width):
            return None
        return self._draw_object(signature, factory)

    def _field_draw_columns(self, width):
        window_width = self.window_width
        if window_width is None:
            return range(width)
        scroll = self._horizontal_scroll_px
        # Include terrain overhang, stair discs and the one-pixel seam overlap.
        margin = max(TERRAIN_SIDE, GROUND_DISC_RADIUS) * self.cell_size_x + 1
        rock = self._sprite_images.get(ROCK_SPRITE)
        if rock is not None:
            padding = max(1, round(self.scale))
            rock_scale = 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
            margin = max(margin, rock.width * rock_scale / 2 + 1)
        first = math.floor((scroll - margin) / self.cell_size_x)
        stop = math.ceil((scroll + window_width + margin) / self.cell_size_x)
        return range(max(0, first // 2 * 2), min(width, (stop + 1) // 2 * 2))

    def _field_col_x(self, col):
        return col * self.cell_size_x - self._horizontal_scroll_px

    def _field_text_x_offset(self):
        # Text is sized for a CELL_SIZE_X-wide cell; center it in the wider one.
        return ((self.cell_size_x - self._sprite_unit()) / 2
                - self._horizontal_scroll_px)

    def _horizontal_scroll_bounds(self):
        if self.field_pixel_width >= self._map_pixel_width:
            return (0, 0)
        return (0, max(0, self._map_pixel_width
                       + FIELD_SIDEBAR_GAP * self.cell_size_x - self.field_pixel_width))

    def _center_camera_on_player(self, player_x):
        min_scroll, max_scroll = self._horizontal_scroll_bounds()
        player_center = (player_x + 0.5) * self.cell_size_x
        self._horizontal_scroll_px = min(
            max_scroll,
            max(min_scroll, round(player_center - self.field_pixel_width / 2)),
        )

    def _handle_horizontal_view_key(self, symbol):
        if self.field_pixel_width >= self._map_pixel_width:
            return (0, 0)
        min_scroll, max_scroll = self._horizontal_scroll_bounds()
        direction = -1 if symbol == pyglet.window.key.LEFT else 1
        self._horizontal_scroll_px = min(
            max_scroll,
            max(min_scroll, self._horizontal_scroll_px
                + direction * HORIZONTAL_VIEW_SCROLL_CELLS * self.cell_size_x),
        )
        self._camera_follow_player = False
        return (direction, 0)

    def _draw_strength_entry(self, row, label, is_player):
        # Keep the sidebar at native resolution on top of the composited field.
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return self._draw_strength_entry_content(row, label, is_player)
        finally:
            self.batch = scene_batch

    def _draw_strength_entry_content(self, row, label, is_player):
        """A small label on the left, and the character's sprite to its right.

        Labels such as "b'" show the base character with its rank mark. A
        monster type shows its sprite only once identified, as on the field.
        """
        left = self.field_pixel_width + self.strength_column_padding
        self._draw_text((0, row), label, COLOR_MAP["default"], bold=is_player,
                        x_offset=left, size_scale=self._strength_text_scale(),
                        group=self._overlay_group)
        base, mark = label[0], label[1:]
        type_key = base + {"'": '2', '"': '3'}.get(mark, '')
        if base not in self._sprite_images or not (is_player or type_key in self._known_types):
            return
        images = self._gray_images if self.map_mode else self._sprite_images
        picture = images[base]
        box_width = STRENGTH_SPRITE_CELLS * self._sprite_unit()
        padding = max(1, round(self.scale))
        scale = 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
        cx = (self.field_pixel_width + self.strength_column_width
              - self.strength_column_padding - box_width / 2)
        cy = self.window_height - (row + 0.5) * self.cell_size_y
        left, bottom = cx - picture.width * scale / 2, cy - picture.height * scale / 2
        tint = self._display_color((255, 255, 255))
        signature = ('sprite', id(picture), left, bottom, scale, scale,
                     id(self._overlay_group), tint)
        sprite = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                picture, x=left, y=bottom, batch=self.batch, group=self._overlay_group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)
        if mark in self._mark_images:
            # The rank mark at the sprite's right, at the field's scale, kept
            # within the entry's own row.
            image = self._mark_images[mark]
            badge_scale = scale
            badge_x = cx + min(box_width, picture.width * scale) / 2 - image.width * badge_scale / 2
            badge_y = cy - image.height * badge_scale / 2
            badge_color = self._display_color(COLOR_MAP['default'])
            signature = ('sprite', id(image), badge_x, badge_y, badge_scale, badge_scale,
                         id(self._overlay_group), badge_color)
            badge = self._draw_object(
                signature,
                lambda: pyglet.sprite.Sprite(
                    image, x=badge_x, y=badge_y,
                    batch=self.batch, group=self._overlay_group,
                ),
            )
            self._set_drawable_attribute(badge, 'scale', badge_scale)
            self._set_drawable_attribute(badge, 'color', badge_color)

    def _clear_drawables(self):
        for drawable in getattr(self, '_uncached_drawables', ()):
            drawable.delete()
        self._uncached_drawables = []
        super()._clear_drawables()
        self._sprite_cells.clear()
        self._player_cell = None
        self._fallen_rock_draws = ()
        self._respawn_draws = ()
        self._respawn_columns_drawn = frozenset()
        self._field_text_cells = frozenset()
        self._floor_cells = {}
        self._edge_shade_pending = False
        self._floor_backdrop_pending = False

    def _retain_drawable(self, signature):
        return signature[0] in {
            'tile', 'floor-copy', 'floor-backdrop', 'terrain-cell',
            'wall-cell', 'barrier-cell', 'edge-shade',
        }

    def _draw_object(self, signature, factory):
        if self._retain_drawable(signature):
            return super()._draw_object(signature, factory)
        drawable = factory()
        if not hasattr(self, '_uncached_drawables'):
            self._uncached_drawables = []
        self._uncached_drawables.append(drawable)
        self._drawables.append(drawable)
        return drawable

    def _finish_drawables(self):
        if self._frame_drawable_cache is None:
            return
        occupied = set(self._sprite_cells) | self._field_text_cells | {self._player_cell}
        for pos in self._fallen_rock_draws:
            if pos not in occupied:
                self._draw_terrain(pos, d.DECOR_FALLEN_ROCKS, 'wall')
        for x, y in self._respawn_draws:
            if (x, y) not in self._respawn_columns_drawn:
                self._draw_respawn_column(self._field_col_x(x) + self.cell_size_x / 2,
                                          (y + 0.5) * self.cell_size_y, 1.0, y,
                                          RESPAWN_COLUMN_UNSEEN_COLOR)
        if self._floor_backdrop_pending:
            self._draw_floor_backdrop()
        if self._floor_cells:
            self._draw_floor_tiles()
        if self._edge_shade_pending:
            self._edge_shade_pending = False
            self._draw_edge_shade()
        super()._finish_drawables()

    def _get_edge_shade_image(self):
        if self._edge_shade_image is None:
            width, height = self.field_width, self.field_height
            texels = EDGE_FLOOR_TEXELS_PER_CELL
            self._edge_shade_image = pyglet.image.ImageData(
                width * texels, height * texels, 'RGBA',
                edge_floor_shade_data(width, height, bounds=self._edge_shade_bounds),
                pitch=-width * texels * 4,
            ).get_texture()
        return self._edge_shade_image

    def _edge_shade_strips(self):
        """Texel rectangles (left, top, width, height) of the field that fade.

        The side strips span the full height and the top/bottom strips only the
        columns between them, so no texel is multiplied twice.
        """
        texels = EDGE_FLOOR_TEXELS_PER_CELL
        width, height = self.field_width * texels, self.field_height * texels
        left, top, right, bottom = self._edge_shade_bounds or (
            1, 1, self.field_width - 1, self.field_height - 1,
        )
        left_end = min(width, math.ceil((left + EDGE_FLOOR_SIDE_FADE[1]) * texels))
        right_start = max(0, math.floor((right - EDGE_FLOOR_SIDE_FADE[1]) * texels))
        if left_end > right_start:
            left_end = right_start = (left_end + right_start) // 2
        top_end = min(height, math.ceil((top + EDGE_FLOOR_END_FADE[1]) * texels))
        bottom_start = max(0, math.floor((bottom - EDGE_FLOOR_END_FADE[1]) * texels))
        if top_end > bottom_start:
            top_end = bottom_start = (top_end + bottom_start) // 2
        middle = right_start - left_end
        return (
            (0, 0, left_end, height),
            (right_start, 0, width - right_start, height),
            (left_end, 0, middle, top_end),
            (left_end, bottom_start, middle, height - bottom_start),
        )

    def _draw_edge_shade(self):
        """Multiply only the floor near the outer walls by the smooth edge fade."""
        image = self._get_edge_shade_image()
        texels = EDGE_FLOOR_TEXELS_PER_CELL
        scale_x = self.cell_size_x / texels
        scale_y = self.cell_size_y / texels
        origin_x = self._field_col_x(0)
        for col, row, width, height in self._edge_shade_strips():
            if width <= 0 or height <= 0:
                continue
            left = origin_x + col * scale_x
            bottom = self.window_height - (row + height) * scale_y
            # Texture rows run bottom-up; the shade data was laid out top-down.
            region = (col, image.height - row - height, width, height)
            signature = ('edge-shade', id(image), region, bottom, scale_x, scale_y,
                         id(self._edge_shade_group))
            sprite = self._draw_bounded_object(
                left, width * scale_x, signature,
                lambda region=region, left=left, bottom=bottom: pyglet.sprite.Sprite(
                    image.get_region(*region), x=left, y=bottom, batch=self.batch,
                    group=self._edge_shade_group,
                    blend_src=pyglet.gl.GL_DST_COLOR, blend_dest=pyglet.gl.GL_ZERO,
                ),
            )
            if sprite is not None and sprite.x != left:
                sprite.x = left
            self._set_drawable_attribute(sprite, 'scale_x', scale_x)
            self._set_drawable_attribute(sprite, 'scale_y', scale_y)

    def _progress_mark_group(self):
        return self._text_overlay_group

    def _progress_mark_x_offset(self):
        return max(1, round(TEXT_PANEL_PADDING * self._menu_scale))

    def _field_overlay_font_scale(self):
        return self._status_font_scale()

    def _field_overlay_cell_width(self):
        return self._menu_cell_size_x

    def _draw_progress_panel(self, marks):
        if not marks:
            return
        cells = sum(len(label) + 1 for label, _ in marks) - 1
        self._draw_text_panel('progress', 0, cells * self._menu_cell_size_x)

    def _floor_label_group(self):
        return self._text_overlay_group

    def _draw_floor_label_panel(self, label, x, width):
        self._draw_text_panel('floor', x, width)

    def _draw_dialogue_panel(self, x, y, width, height):
        if width > 0 and height > 0:
            self._draw_rect(
                x,
                y,
                width,
                height,
                (0, 0, 0, TEXT_PANEL_ALPHA),
                group=self._overlay_group,
            )

    def _draw_text_panel(self, kind, x, width):
        padding = max(1, round(TEXT_PANEL_PADDING * self._menu_scale))
        left = max(0, x - padding)
        row = self.field_height - 1
        top = self.window_height - row * self.cell_size_y
        bottom = top - self._menu_font_size - padding
        panel_width = width + 2 * padding
        height = self._menu_font_size + 2 * padding
        color = (0, 0, 0, TEXT_PANEL_ALPHA)
        signature = ('text-panel', kind, left, bottom, panel_width, height, color,
                     id(self._text_panel_group))
        batch = self._text_batch
        self._draw_object(
            signature,
            lambda: pyglet.shapes.Rectangle(
                left, bottom, panel_width, height, color=color, batch=batch,
                group=self._text_panel_group,
            ),
        )

    def _draw_golem_rubble(self, pos, visible):
        pass

    def _draw_member(self, glyph):
        name = self._member_variants.get(glyph.char)
        key = (CAT_SPRITE if glyph.char == 'Y' else
               f'{name}-{self._member_skins[glyph.char]}' if name else None)
        if key not in self._sprite_images:
            return super()._draw_member(glyph)
        color = self._tone_color('default')
        self._draw_sprite((glyph.x, glyph.y), key, color,
                          disc_scale=0.0 if glyph.tone == 'member' else 1.0)

    def _draw_field_text(self, pos, text, color, bold=False):
        x, y = pos
        if text == d.CHAR_DUNGEON_CORE and self._dungeon_core_image is not None:
            self._draw_dungeon_core(pos)
            return
        if text == d.CHAR_BARRIER and self._floor_images is not None:
            return  # shown by the barrier light itself
        if text in self._mark_images and (x - 1, y) in self._sprite_cells:
            return self._draw_rank_mark((x - 1, y), text, color)
        self._field_text_cells = self._field_text_cells | {pos}
        if text not in self._sprite_images:
            if self.window_width is not None:
                left = x * self.cell_size_x + self._field_text_x_offset()
                padding = self.cell_size_x
                if not self._intersects_window(left - padding,
                                               self._text_width(text, bold) + 2 * padding):
                    return
            return super()._draw_field_text((x, y - FIELD_TEXT_RAISE), text, color, bold)
        tribe = d.CHAR_TO_MONSTER_TRIBE.get(text)
        met_elf = tribe is not None and tribe.is_elf and not bold
        self._draw_sprite(pos, text, color, shade=MET_ELF_SHADE if met_elf else 1.0)

    def _draw_dungeon_core(self, pos):
        x, y = pos
        image = self._dungeon_core_image
        left = self._field_col_x(x - 1)
        bottom = self.window_height - (
            y + 1 + self._dungeon_core_under
        ) * self.cell_size_y
        scale_x = 3 * self.cell_size_x / image.width
        scale_y = (
            (1 + self._dungeon_core_under + self._dungeon_core_overhang)
            * self.cell_size_y
            / image.height
        )
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        shade = 1.0 if visible else TERRAIN_EXPLORED_SHADE
        tint = self._display_color(tuple(round(255 * shade) for _ in range(3)))
        group = self._row_group(y, 'wall')
        signature = ('dungeon-core', id(image), left, bottom, scale_x, scale_y,
                     id(group), tint)
        sprite = self._draw_bounded_object(
            left, 3 * self.cell_size_x, signature,
            lambda: pyglet.sprite.Sprite(image, x=left, y=bottom,
                                         batch=self.batch, group=group),
        )
        self._set_drawable_attribute(sprite, 'scale_x', scale_x)
        self._set_drawable_attribute(sprite, 'scale_y', scale_y)
        self._set_drawable_attribute(sprite, 'color', tint)

    def _draw_rank_mark(self, pos, mark, color):
        """Tinted 3D apostrophe(s) at the upper right of the sprite in `pos`."""
        x, y = pos
        image = self._mark_images[mark]
        size = self._sprite_cells[pos]
        padding = max(1, round(self.scale))
        scale = size * 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
        dx, dy = (size * offset for offset in MARK_OFFSET)
        left = (self._field_col_x(x) + 0.5 * self.cell_size_x + dx * self._sprite_unit()
                - image.width * scale / 2)
        bottom = self.window_height - (y + 0.5 - dy) * self.cell_size_y - image.height * scale / 2
        group = self._row_group(y, 'hover-mark' if pos == self._hovered_cell() else 'mark')
        # White like the strength column, not the strength color; only the
        # half-bright dimming of the glyph is kept.
        white = COLOR_MAP['default']
        dimmed = color in {self._dim_color(value) for value in COLOR_MAP.values()}
        tint = self._display_color(self._dim_color(white) if dimmed else white)
        signature = ('sprite', id(image), left, bottom, scale, scale, id(group), tint)
        sprite = self._draw_bounded_object(
            left, image.width * scale, signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)

    def _draw_follower(self, pos, char):
        self._enlarge_neighbors = False
        try:
            if char == 'J' and char in self._sprite_images:
                self._draw_sprite(pos, char, COLOR_MAP['default'], disc_scale=0.0)
            else:
                super()._draw_follower(pos, char)
        finally:
            self._enlarge_neighbors = True

    def _draw_fairy_slot(self, pos, char):
        if char not in self._sprite_images:
            return super()._draw_fairy_slot(pos, char)
        x, y = pos
        dx, dy = FAMILIAR_OFFSET
        cx = self._field_col_x(x - 1) + 0.5 * self.cell_size_x + dx * self._sprite_unit()
        cy = (y + 0.5 - dy) * self.cell_size_y
        self._place_sprite(char, cx, cy, FAMILIAR_SIZE, y, 'familiar', dimmed=False)
        self._draw_pillar(cx, cy, FAMILIAR_SIZE, y, COLOR_MAP[CI_GREEN], familiar=True)

    def _neighbor_of_player(self, pos):
        if not self._enlarge_neighbors or self._player_cell is None:
            return False
        px, py = self._player_cell
        return abs(pos[0] - px) + abs(pos[1] - py) == 1

    def _draw_sprite(self, pos, text, color, upper_right_color=None, shade=1.0, disc_scale=1.0):
        x, y = pos
        cx, cy = self._field_col_x(x) + self.cell_size_x / 2, (y + 0.5) * self.cell_size_y
        dimmed = color in {self._dim_color(value) for value in COLOR_MAP.values()}
        if self.map_mode and max(color) <= 128 and max(color) - min(color) <= 16:
            # Map sprites use a grey texture. Preserve the half-bright marker
            # for dim neutral colors supplied by callers outside COLOR_MAP.
            dimmed = True
        size = NEIGHBOR_SCALE if self._neighbor_of_player(pos) else 1.0
        hovered = pos == self._hovered_cell()
        if hovered:
            size *= HOVER_SCALE
        glow = color if text in UNKNOWN_SPRITES else None
        top = self._place_sprite(text, cx, cy, size, y,
                                 'hover' if hovered else 'sprite', dimmed, shade, glow)
        if hovered:
            self._draw_hover_name(pos, text, top)
        self._sprite_cells[pos] = size
        if text in d.CHAR_TO_FAIRY_TRIBE:
            green = COLOR_MAP[CI_GREEN]
            self._draw_pillar(cx, cy, size, y, self._dim_color(green) if dimmed else green)
        elif text in UNKNOWN_SPRITES:
            self._draw_pillar(cx, cy, size, y,
                              tuple(round(c * shade * UNKNOWN_PILLAR) for c in color))
        tribe = d.CHAR_TO_MONSTER_TRIBE.get(text)
        if (upper_right_color is None and tribe is not None
                and tribe.effect == d.EFFECT_UNLOCK_TREASURE
                and color in (COLOR_MAP[CI_YELLOW], self._dim_color(COLOR_MAP[CI_YELLOW]))):
            # A beatable boss: blue like any beatable monster, with the
            # upper-right half yellow for the treasure it unlocks.
            blue = COLOR_MAP[CI_BLUE]
            color, upper_right_color = self._dim_color(blue) if dimmed else blue, color
        # Keep the original semantic color (strength, poison, etc.) readable
        # as a glowing disc on the ground the character stands on.
        if text in UNKNOWN_SPRITES:
            reference = COLOR_MAP[UNKNOWN_DISC_REFERENCE]
            if dimmed:
                reference = self._dim_color(reference)
            shade *= min(1.0, _luminance(reference) / max(_luminance(color), 1))
        color = tuple(round(c * shade) for c in color)
        if disc_scale:
            self._draw_ground_disc(cx, cy, disc_scale * GROUND_DISC_RADIUS * self._sprite_unit(),
                                   color, upper_right_color)
            if pos in self._respawn_draws:
                self._draw_respawn_column(cx, cy, size, y, color)
                self._respawn_columns_drawn = self._respawn_columns_drawn | {pos}
        return top

    def _draw_hover_name(self, pos, text, head_top):
        if text in UNKNOWN_SPRITES:
            return
        name = tr(SPRITE_NAMES[text]) if text in SPRITE_NAMES else text
        size_scale = self._status_font_scale() * MESSAGE_FONT_SIZE_SCALE
        font_size = self.font_size * size_scale
        font_name = self.font_name
        if not name.isascii():
            font_name, ratio = self._non_ascii_font(self.font_size)
            font_size *= ratio
        cx = self._field_col_x(pos[0]) + self.cell_size_x / 2
        bottom = self.window_height - head_top + LP_GAUGE_GAP * self._sprite_unit()
        anchor_y = 'bottom'
        # The first walkable row sits just below the dungeon's top wall.
        if pos[1] <= 1:
            bottom = (self.window_height - (pos[1] + 0.5) * self.cell_size_y
                      - LP_GAUGE_GAP * self._sprite_unit())
            anchor_y = 'top'
        group = self._row_group(pos[1], 'hover-name')
        color = (*self._display_color(COLOR_MAP['default']), 255)
        signature = ('hover-name', name, font_name, font_size, cx, bottom,
                     anchor_y, color, id(group))
        self._draw_object(
            signature,
            lambda: pyglet.text.Label(
                name, font_name=font_name, font_size=font_size,
                weight='bold',
                x=cx, y=bottom, anchor_x='center', anchor_y=anchor_y,
                color=color, batch=self._text_batch, group=group,
            ),
        )

    def _place_sprite(self, text, cx, cy, size, row, layer, dimmed, shade=1.0, glow=None):
        """Draw a character image with its feet at field pixel (cx, cy); returns
        the field pixel y of the top of the character in it.

        With `glow`, the image is tinted slightly (UNKNOWN_TINT) toward that color.
        """
        images = self._gray_images if self.map_mode else self._sprite_images
        swapped = THEME_SPRITES.get(self._terrain_theme, {}).get(text)
        if swapped in images:
            text = swapped
        picture = images[text]
        padding = max(1, round(self.scale))
        width = max(1, self._sprite_unit() - 2 * padding)
        scale = size * 1.8 * width / SPRITE_REFERENCE_PIXELS
        left = cx - picture.width * scale / 2
        bottom = self.window_height - cy - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale
        group = self._row_group(row, layer)
        tint = ((128, 128, 128) if dimmed else
                (round(255 * shade),) * 3 if shade < 1 else (255, 255, 255))
        if glow is not None:
            peak = max(max(glow), 1)
            tint = tuple(round(t * (1 - UNKNOWN_TINT + UNKNOWN_TINT * g / peak))
                         for t, g in zip(tint, glow))
        tint = self._display_color(tint)
        signature = ('sprite', id(picture), left, bottom, scale, scale, id(group), tint)
        sprite = self._draw_bounded_object(
            left, picture.width * scale, signature,
            lambda: pyglet.sprite.Sprite(
                picture, x=left, y=bottom, batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)
        head_room = self._sprite_head_room.get(text, 0)
        return cy - (picture.height / 2 + SPRITE_GROUND_OFFSET_PIXELS - head_room) * scale

    def _draw_pillar(self, cx, cy, size, row, color, familiar=False):
        """Additive light cylinder around a fairy: far wall behind, near wall over it."""
        for side in ('back', 'front'):
            self._draw_light_wall(self._pillar_images[side], side, cx, cy,
                                  size * PILLAR_RADIUS, size * PILLAR_HEIGHT, row, color,
                                  familiar)

    def _draw_respawn_column(self, cx, cy, size, row, color):
        """Swirled light column of a respawned character, in its ground disc's main color.

        The space between the bands takes a dimmer copy of that color.
        """
        gap_color = tuple(round(c * RESPAWN_COLUMN_GAP_SHADE) for c in color)
        for side in ('back', 'front'):
            for gaps, tint in ((False, color), (True, gap_color)):
                self._draw_light_wall(self._respawn_column_images[side, gaps], side, cx, cy,
                                      size * RESPAWN_COLUMN_RADIUS,
                                      size * RESPAWN_COLUMN_HEIGHT, row, tint)

    def _draw_light_wall(self, image, side, cx, cy, radius, height, row, color,
                         familiar=False):
        """One additive wall of a light cylinder; radius and height in cell widths."""
        unit = self._sprite_unit()
        radius *= unit
        layer = 'pillar-back' if side == 'back' else 'pillar-front'
        left = cx - radius
        bottom = self.window_height - cy - radius * GROUND_DISC_FLATTEN
        scale_x = 2 * radius / image.width
        scale_y = (height * unit + 2 * radius * GROUND_DISC_FLATTEN) / image.height
        group = self._row_group(row, 'familiar-front' if familiar and side == 'front'
                                else layer)
        tint = self._display_color(color)
        signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                     id(group), pyglet.gl.GL_SRC_ALPHA, pyglet.gl.GL_ONE, tint)
        pillar = self._draw_bounded_object(
            left, image.width * scale_x, signature,
            partial(
                pyglet.sprite.Sprite, image, x=left, y=bottom,
                blend_src=pyglet.gl.GL_SRC_ALPHA, blend_dest=pyglet.gl.GL_ONE,
                batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(pillar, 'scale_x', scale_x)
        self._set_drawable_attribute(pillar, 'scale_y', scale_y)
        self._set_drawable_attribute(pillar, 'color', tint)

    def _draw_ground_disc(self, cx, cy, radius, color, upper_right_color=None, opacity=255):
        """A disc seen at the sprites' 60-degree view, fading outward, below the sprite.

        With `upper_right_color`, that half of the disc takes the second color.
        """
        if upper_right_color is None:
            parts = [(self._disc_image, color)]
        else:
            parts = list(zip(self._disc_halves, (color, upper_right_color)))
        ry = radius * GROUND_DISC_FLATTEN
        for image, tint in parts:
            left, bottom = cx - radius, self.window_height - cy - ry
            scale_x = 2 * radius / image.width
            scale_y = 2 * ry / image.height
            draw_tint = self._display_color(tint)
            signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                         id(self._disc_group), draw_tint, opacity)
            disc = self._draw_bounded_object(
                left, image.width * scale_x, signature,
                partial(
                    pyglet.sprite.Sprite, image, x=left, y=bottom,
                    batch=self.batch, group=self._disc_group,
                ),
            )
            self._set_drawable_attribute(disc, 'scale_x', scale_x)
            self._set_drawable_attribute(disc, 'scale_y', scale_y)
            self._set_drawable_attribute(disc, 'color', draw_tint)
            self._set_drawable_attribute(disc, 'opacity', opacity)
