"""Pyglet frontend with character sprites and the original text fallback."""

import math
from pathlib import Path

import pyglet

from . import defs as d
from . import display as ui_display
from .arlq import barrier_lp_damage
from .pyglet_funcs import (CI_BLUE, CI_GREEN, CI_YELLOW, COLOR_MAP, FLOOR, REACHABLE_CELL_COLOR,
                           VISIBLE_FLOOR, VISIBLE_WALL, WALL, PygletUI)


SPRITE_FILES = {
    '@': 'player.png',
    'a': 'amoeba.png',
    'A': 'rare-amoeba.png',
    'b': 'bison.png',
    'c': 'chimera.png',
    'd': 'comodo-dragon.png',
    'D': 'dragon.png',
    'T': 'treasure.png',
    'l': 'loop-watch.png',
    'n': 'nomicon.png',
    'o': 'ocular.png',
    'C': 'rare-chimera.png',
    'F': 'fire-drake.png',
    'g': 'golem.png',
    'k': 'marksman.png',
    'm': 'spore.png',
    'e': 'erebus.png',
    'E': 'rare-erebus.png',
    'X': 'caltrop-plant.png',
    'p': 'pegasus.png',
    'H': 'high-elf.png',
    'I': 'isolated-elf.png',
    'J': 'javelin-elf.png',
    'K': 'collector-elf.png',
    'L': 'lifebringer-elf.png',
    'S': 'sylvan-elf.png',
    # Not a glyph: the rubble drawn on walls a defeated Golem raised.
    'golem rock': 'golem-rock.png',
}
ROCK_SPRITE = 'golem rock'
# Golem rubble outside the current view is darkened like explored walls.
ROCK_EXPLORED_SHADE = 0.6
# An elf the player has met (drawn without bold as text) is shown with its
# sprite and ground disc darkened to this fraction.
MET_ELF_SHADE = 0.6
# A character in one of the four cells next to the player, the one the next
# step would meet, is drawn this much larger (its ground disc keeps its size).
# Followers walking with the player keep their usual size.
NEIGHBOR_SCALE = 1.3
# Field text kept as text (such as "?" and "!") is raised by this fraction of
# a cell, so it stays within its cell above the flagstone joint.
FIELD_TEXT_RAISE = 0.1
# The strength column on the right is this many cells wider than in the
# original GUI: each entry keeps its label, smaller, on the left and, once the
# player has identified that type (as on the field), shows the character's
# sprite to its right, at the same size as on the field (larger ones may
# overflow their row).
STRENGTH_SPRITE_CELLS = 2
STRENGTH_TEXT_SCALE = 0.7
# Empowered-rank marks, rendered as raised apostrophes in near-white resin and
# tinted with the monster's color. They float at the upper right of the
# sprite instead of in the next cell: centre offset from the ground point in
# cell widths east and cell heights north.
MARK_FILES = {"'": 'mark-rank2.png', '"': 'mark-rank3.png'}
MARK_OFFSET = (0.6, 0.65)
# Every sprite uses one scale: this many source pixels (an amoeba's width)
# span 1.8 cell widths. Larger models therefore give larger sprites.
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
# Companions stand inside a faint green pillar of light: an open cylinder on
# the ground disc's ellipse, seen at the same 60-degree view. Radius and side
# height in cell widths; peak opacity of the far wall (behind the sprite) and
# the near wall (over it); the sides glow brighter, and both fade upward.
PILLAR_RADIUS = 0.8
PILLAR_HEIGHT = 2.0
PILLAR_BACK_ALPHA = 0.9
PILLAR_FRONT_ALPHA = 0.4
PILLAR_EDGE = 0.45
PILLAR_FADE = 1.1
# The companion travelling with the player floats small at its right shoulder:
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
# Marble column parts (near-white, tinted per visible/explored wall color);
# each covers one cell plus the WALL_OVERHANG band north of it.
WALL_PARTS = ('link-west', 'link-east', 'column')
# Explored walls and floor outside the current view are kept clearly darker.
WALL_TINT = {VISIBLE_WALL: 2.4, WALL: 1.75}
# Flagstone floor: two near-white stones laid as a checkerboard, tinted a warm
# dark grey per visible/explored floor, alternate cells slightly darker.
FLOOR_PARTS = ('a', 'b')
FLOOR_TINTS = {VISIBLE_FLOOR: (78, 72, 66), FLOOR: (42, 39, 36)}
FLOOR_CHECKER_SHADE = 0.88
# Barrier cells show red flames burning on the ordinary floor, in place of
# the red "=": small fires rising from several spots in the lower half of the
# cell (two variants, laid out as a checkerboard), glowing at their roots and
# added onto the floor, the tallest reaching a little into the cell above. While the protective amulet makes barriers harmless,
# the cells within one cell of the player (its own and the eight around it)
# show only faint grey smoke of the same shape. Flames outside the current
# view are darkened like the floor. Sizes are in cell widths/heights.
FLAME_TEXELS = (48, 96)
FLAME_HEIGHT = 1.3
FLAME_BASE = 0.0
FLAME_ALPHA = 1.0
FLAME_EXPLORED_SHADE = 0.5
SMOKE_TINT = (150, 150, 156)
SMOKE_OPACITY = 140


def pillar_image(side):
    """One wall ('back' or 'front') of an open light cylinder, white with alpha.

    The image spans the cylinder's width and, from the bottom of its ground
    ellipse, the side height plus that ellipse; the tint is applied when drawn.
    """
    flatten, height = GROUND_DISC_FLATTEN, PILLAR_HEIGHT / PILLAR_RADIUS
    width = GROUND_DISC_TEXELS
    rows = round(width * (height + 2 * flatten) / 2)
    peak = PILLAR_BACK_ALPHA if side == 'back' else PILLAR_FRONT_ALPHA
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
                alpha = (peak * rim * min(1.0, PILLAR_EDGE / math.sqrt(1 - u * u + 0.02))
                         * (1 - t) ** PILLAR_FADE)
            rgba += bytes((255, 255, 255, round(255 * alpha)))
    return pyglet.image.ImageData(width, rows, 'RGBA', bytes(rgba), pitch=width * 4)


def smoke_image(flame):
    """A white copy of `flame` with the same shape, for the cooled smoke."""
    width, height = flame.width, flame.height
    rgba = bytearray(flame.get_data('RGBA', width * 4))
    for offset in range(0, len(rgba), 4):
        rgba[offset:offset + 3] = b'\xff\xff\xff'
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


def flame_image(variant):
    """Small fires rising from several spots in the lower half of a cell.

    Each fire is a teardrop tongue, round and bright orange at its root,
    narrowing to a deep red tip, with a soft glow around the root. The image
    is drawn additively from the cell's bottom; `variant` (0 or 1) places the
    fires differently so neighbouring cells do not repeat.
    """
    width, height = FLAME_TEXELS
    lower_half = 0.5 / FLAME_HEIGHT  # the cell's middle, in image fractions
    # (centre, root height as a fraction of the lower half, half width, height).
    fires = (((0.20, 0.15, 0.13, 0.42), (0.50, 0.05, 0.16, 0.55), (0.80, 0.20, 0.12, 0.40),
              (0.35, 0.80, 0.11, 0.34), (0.68, 0.90, 0.10, 0.30)),
             ((0.28, 0.08, 0.15, 0.50), (0.62, 0.25, 0.14, 0.46), (0.88, 0.05, 0.10, 0.32),
              (0.14, 0.85, 0.10, 0.30), (0.48, 0.95, 0.11, 0.36)))[variant]
    root, tip = (255, 160, 60), (230, 35, 15)
    rgba = bytearray()
    for row in range(height):
        v = (row + 0.5) / height
        for col in range(width):
            u = (col + 0.5) / width
            strength, along = 0.0, 1.0
            for centre, base, half, tall in fires:
                base *= lower_half
                t = (v - base) / tall
                # A soft glow around the root, slightly flattened.
                glow = 0.45 * max(0.0, 1 - math.hypot((u - centre) / (half * 1.6),
                                                      (v - base) / (half * 0.9)))
                value = glow
                if 0 <= t < 1:
                    # Teardrop: widest a little above the root, pointed at the tip.
                    w = half * min(1.0, 0.55 + t * 3) * (1 - t) ** 0.7
                    across = abs(u - centre) / w if w > 0 else 1
                    if across < 1:
                        value = max(value, (1 - across ** 2) * (1 - t) ** 0.5)
                if value > strength:
                    strength, along = value, max(t, 0.0)
            mix = min(1.0, along / 0.7)
            color = [round(a + (b - a) * mix) for a, b in zip(root, tip)]
            rgba += bytes((*color, round(255 * min(1.0, FLAME_ALPHA * strength))))
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


class SpriteUI(PygletUI):
    """Reuse input, menus, visibility and glyph selection without duplicating rules."""

    # Walls a defeated Golem raised on the floor being drawn (see draw_stage).
    _rock_cells = frozenset()
    # The player's cell this frame (None while viewing another floor), and
    # whether characters next to it are enlarged (off while drawing followers).
    _player_cell = None
    _enlarge_neighbors = True
    # Monster types the player has identified, for the strength column.
    _known_types = frozenset()
    # Current view and, while barriers are harmless, the player's cell that
    # cools the barrier stones around it.
    _cur_torched = None
    _cooling_center = None

    def __init__(self, scale=None, key_repeat_interval=None):
        super().__init__(scale, key_repeat_interval)
        self.window.set_caption(self.window.caption.replace('Pyglet mix', 'Sprite mix'))
        directory = Path(__file__).parent / 'assets' / 'characters'
        self._sprite_images = {}
        self._gray_images = {}
        for char, filename in SPRITE_FILES.items():
            path = directory / filename
            if not path.is_file():
                continue
            picture = pyglet.image.load(str(path))
            self._sprite_images[char] = picture
            data = picture.get_image_data()
            rgba = bytearray(data.get_data('RGBA', data.width * 4))
            for offset in range(0, len(rgba), 4):
                r, g, b = rgba[offset:offset + 3]
                gray = (299 * r + 587 * g + 114 * b) // 1000
                rgba[offset:offset + 3] = bytes((gray, gray, gray))
            self._gray_images[char] = pyglet.image.ImageData(
                data.width, data.height, 'RGBA', bytes(rgba), pitch=data.width * 4
            )
        self._mark_images = {mark: pyglet.image.load(str(directory / filename))
                             for mark, filename in MARK_FILES.items()
                             if (directory / filename).is_file()}
        # Cells where a character sprite was drawn this frame; a rank mark in
        # the next cell belongs to that sprite.
        self._sprite_cells = {}
        self._disc_image = ground_disc_image()
        self._disc_halves = (ground_disc_image('lower-left'), ground_disc_image('upper-right'))
        self._disc_group = pyglet.graphics.Group(order=1)
        self._pillar_images = {side: pillar_image(side) for side in ('back', 'front')}
        wall_directory = Path(__file__).parent / 'assets' / 'walls'
        paths = [wall_directory / ('wall-' + part + '.png') for part in WALL_PARTS]
        self._wall_images = ({part: pyglet.image.load(str(path))
                              for part, path in zip(WALL_PARTS, paths)}
                             if all(path.is_file() for path in paths) else None)
        floor_paths = [Path(__file__).parent / 'assets' / 'floor' / ('floor-' + part + '.png')
                       for part in FLOOR_PARTS]
        self._floor_images = ([pyglet.image.load(str(path)) for path in floor_paths]
                              if all(path.is_file() for path in floor_paths) else None)
        self._flame_images = [flame_image(variant) for variant in (0, 1)]
        self._smoke_images = [smoke_image(flame) for flame in self._flame_images]
        self._floor_group = pyglet.graphics.Group(order=-1)
        # Rows are painted north to south: a row's walls, then its characters,
        # so walls overlap characters to their north but not to their south.
        self._row_groups = {}
        self._overlay_group = pyglet.graphics.Group(order=10000)

    ROW_LAYERS = ('wall', 'column', 'pillar-back', 'sprite', 'pillar-front', 'familiar',
                  'familiar-front', 'mark')

    def _row_group(self, y, layer):
        order = 10 + len(self.ROW_LAYERS) * y + self.ROW_LAYERS.index(layer)
        if order not in self._row_groups:
            self._row_groups[order] = pyglet.graphics.Group(order=order)
        return self._row_groups[order]

    def draw_stage(self, *, rock_cells=None, **kwargs):
        self._rock_cells = rock_cells or set()
        self._known_types = kwargs.get('known_types') or set()
        self._cur_torched = kwargs.get('cur_torched')
        player = kwargs.get('player')
        self._cooling_center = (
            (player.x, player.y)
            if player is not None and not kwargs.get('floor_view') and barrier_lp_damage(player) == 0
            else None
        )
        return super().draw_stage(rock_cells=rock_cells, **kwargs)

    def _draw_barrier(self, x, y, field, discovered_at):
        """Thin red flames on the floor, or faint smoke near the player while harmless."""
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        self._draw_floor(x, y, VISIBLE_FLOOR if visible else FLOOR, field, discovered_at)
        cooled = False
        if self._cooling_center is not None:
            cx, cy = self._cooling_center
            cooled = max(abs(x - cx), abs(y - cy)) <= 1
        image = (self._smoke_images if cooled else self._flame_images)[(x + y) % 2]
        bottom = self.window_height - (y + 1 - FLAME_BASE) * self.cell_size_y
        flame = pyglet.sprite.Sprite(
            image, x=self._field_col_x(x), y=bottom,
            blend_src=pyglet.gl.GL_SRC_ALPHA,
            blend_dest=pyglet.gl.GL_ONE_MINUS_SRC_ALPHA if cooled else pyglet.gl.GL_ONE,
            batch=self.batch, group=self._row_group(y, 'pillar-back'),
        )
        flame.scale_x = (self._field_col_width(x) + 1) / image.width
        flame.scale_y = FLAME_HEIGHT * self.cell_size_y / image.height
        if cooled:
            flame.color = self._display_color(SMOKE_TINT)
            flame.opacity = SMOKE_OPACITY
        else:
            shade = round(255 * (1 if visible else FLAME_EXPLORED_SHADE))
            flame.color = self._display_color((shade, shade, shade))
        self._drawables.append(flame)

    def _draw_tile(self, x, y, tile_color, field, discovered_at):
        if (field[y][x] == d.CHAR_BARRIER and discovered_at(x, y)
                and tile_color != REACHABLE_CELL_COLOR and self._floor_images is not None):
            return self._draw_barrier(x, y, field, discovered_at)
        if tile_color in FLOOR_TINTS:
            return self._draw_floor(x, y, tile_color, field, discovered_at)
        if field[y][x] != d.CHAR_WALL or tile_color not in (VISIBLE_WALL, WALL):
            return super()._draw_tile(x, y, tile_color, field, discovered_at)
        floor = VISIBLE_FLOOR if tile_color == VISIBLE_WALL else FLOOR
        self._draw_floor(x, y, floor, field, discovered_at)
        if (x, y) in self._rock_cells and ROCK_SPRITE in self._sprite_images:
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
                    and field[wy][wx] == d.CHAR_WALL and discovered_at(wx, wy)
                    and (wx, wy) not in self._rock_cells)

        if self._wall_images is not None:
            tint = tuple(min(255, round(c * WALL_TINT[tile_color])) for c in tile_color)
            height = (1 + WALL_OVERHANG) * self.cell_size_y
            for part, show in (('link-west', wall_at(x - 1, y)),
                               ('link-east', wall_at(x + 1, y)), ('column', True)):
                if show:
                    image = self._wall_images[part]
                    piece = pyglet.sprite.Sprite(
                        image, x=left, y=self.window_height - (y + 1) * self.cell_size_y,
                        batch=self.batch,
                        group=self._row_group(y, 'column' if part == 'column' else 'wall'),
                    )
                    piece.scale_x = width / image.width
                    piece.scale_y = height / image.height
                    piece.color = self._display_color(tint)
                    self._drawables.append(piece)
            return
        south_is_wall = wall_at(x, y + 1)
        self._draw_wall_rect(left, top, width, height, tile_color, WALL_TOP_SHADE, group)
        if not south_is_wall:
            # Front face between the lifted top and the cell's south edge; a
            # southern wall's lifted top covers this band instead.
            front = WALL_OVERHANG * self.cell_size_y
            self._draw_wall_rect(left, (y + 1) * self.cell_size_y - front, width, front + 1,
                                 tile_color, WALL_FRONT_SHADE, group)

    def _draw_floor(self, x, y, tile_color, field, discovered_at):
        if self._floor_images is None:
            return super()._draw_tile(x, y, tile_color, field, discovered_at)
        odd = (x + y) % 2
        image = self._floor_images[odd]
        shade = FLOOR_CHECKER_SHADE if odd else 1
        tint = tuple(round(c * shade) for c in FLOOR_TINTS[tile_color])
        stone = pyglet.sprite.Sprite(
            image, x=self._field_col_x(x), y=self.window_height - (y + 1) * self.cell_size_y,
            batch=self.batch, group=self._floor_group,
        )
        stone.scale_x = (self._field_col_width(x) + 1) / image.width
        stone.scale_y = (self.cell_size_y + 1) / image.height
        stone.color = self._display_color(tint)
        self._drawables.append(stone)

    def _draw_wall_rect(self, x, y, width, height, color, shade, group):
        color = tuple(min(255, round(c * shade)) for c in color)
        rect = pyglet.shapes.Rectangle(
            x, self.window_height - y - height, width, height,
            color=self._display_color(color), batch=self.batch, group=group,
        )
        self._drawables.append(rect)

    def _draw_line(self, x1, y1, x2, y2, color, thickness=1):
        # Visibility boundaries and other lines stay above walls and sprites.
        line = pyglet.shapes.Line(
            x1, self.window_height - y1, x2, self.window_height - y2,
            thickness=thickness, color=self._display_color(color),
            batch=self.batch, group=self._overlay_group,
        )
        self._drawables.append(line)

    def _draw_player(self, pos, player):
        if '@' not in self._sprite_images:
            return super()._draw_player(pos, player)
        # Low/warning LP colors the ground disc instead of filling the cell;
        # poison turns the disc's upper-right half purple.
        self._player_cell = pos
        _, background = ui_display.player_appearance(player)
        poison = self._tone_color('magenta') if player.item == d.ITEM_POISONED else None
        self._draw_sprite(pos, '@', self._tone_color(background or 'default'), poison)

    def _set_scaled_dimensions(self):
        super()._set_scaled_dimensions()
        self.strength_column_width += STRENGTH_SPRITE_CELLS * self.cell_size_x
        self.window_width = self.field_pixel_width + self.strength_column_width

    def _draw_strength_entry(self, row, label, is_player):
        """A small label on the left, and the character's sprite to its right.

        Labels such as "b'" show the base character with its rank mark. A
        monster type shows its sprite only once identified, as on the field.
        """
        left = self.field_pixel_width + self.strength_column_padding
        self._draw_text((0, row), label, COLOR_MAP["default"], bold=is_player,
                        x_offset=left, size_scale=STRENGTH_TEXT_SCALE)
        base, mark = label[0], label[1:]
        type_key = base + {"'": '2', '"': '3'}.get(mark, '')
        if base not in self._sprite_images or not (is_player or type_key in self._known_types):
            return
        images = self._gray_images if self.map_mode else self._sprite_images
        picture = images[base]
        box_width = STRENGTH_SPRITE_CELLS * self.cell_size_x
        padding = max(1, round(self.scale))
        scale = 1.8 * max(1, self.cell_size_x - 2 * padding) / SPRITE_REFERENCE_PIXELS
        cx = (self.field_pixel_width + self.strength_column_width
              - self.strength_column_padding - box_width / 2)
        cy = self.window_height - (row + 0.5) * self.cell_size_y
        sprite = pyglet.sprite.Sprite(
            picture, x=cx - picture.width * scale / 2, y=cy - picture.height * scale / 2,
            batch=self.batch, group=self._overlay_group,
        )
        sprite.scale = scale
        self._drawables.append(sprite)
        if mark in self._mark_images:
            # The rank mark at the sprite's right, at the field's scale, kept
            # within the entry's own row.
            image = self._mark_images[mark]
            badge_scale = scale
            badge = pyglet.sprite.Sprite(
                image, x=cx + min(box_width, picture.width * scale) / 2 - image.width * badge_scale / 2,
                y=cy - image.height * badge_scale / 2,
                batch=self.batch, group=self._overlay_group,
            )
            badge.scale = badge_scale
            badge.color = self._display_color(COLOR_MAP['default'])
            self._drawables.append(badge)

    def _clear_drawables(self):
        super()._clear_drawables()
        self._sprite_cells.clear()
        self._player_cell = None

    def _draw_field_text(self, pos, text, color, bold=False):
        x, y = pos
        if text == d.CHAR_BARRIER and self._floor_images is not None:
            return  # shown by the flames themselves
        if text in self._mark_images and (x - 1, y) in self._sprite_cells:
            return self._draw_rank_mark((x - 1, y), text, color)
        if text not in self._sprite_images:
            return super()._draw_field_text((x, y - FIELD_TEXT_RAISE), text, color, bold)
        tribe = d.CHAR_TO_MONSTER_TRIBE.get(text)
        met_elf = tribe is not None and tribe.is_elf and not bold
        self._draw_sprite(pos, text, color, shade=MET_ELF_SHADE if met_elf else 1.0)

    def _draw_rank_mark(self, pos, mark, color):
        """Tinted 3D apostrophe(s) at the upper right of the sprite in `pos`."""
        x, y = pos
        image = self._mark_images[mark]
        size = self._sprite_cells[pos]
        padding = max(1, round(self.scale))
        scale = size * 1.8 * max(1, self.cell_size_x - 2 * padding) / SPRITE_REFERENCE_PIXELS
        dx, dy = (size * offset for offset in MARK_OFFSET)
        sprite = pyglet.sprite.Sprite(
            image,
            x=self._field_col_x(x) + (0.5 + dx) * self.cell_size_x - image.width * scale / 2,
            y=self.window_height - (y + 0.5 - dy) * self.cell_size_y - image.height * scale / 2,
            batch=self.batch, group=self._row_group(y, 'mark'),
        )
        sprite.scale = scale
        sprite.color = self._display_color(color)
        self._drawables.append(sprite)

    def _draw_follower(self, pos, char):
        self._enlarge_neighbors = False
        try:
            super()._draw_follower(pos, char)
        finally:
            self._enlarge_neighbors = True

    def _draw_companion_slot(self, pos, char):
        if char not in self._sprite_images:
            return super()._draw_companion_slot(pos, char)
        x, y = pos
        dx, dy = FAMILIAR_OFFSET
        cx = self._field_col_x(x - 1) + (0.5 + dx) * self.cell_size_x
        cy = (y + 0.5 - dy) * self.cell_size_y
        self._place_sprite(char, cx, cy, FAMILIAR_SIZE, y, 'familiar', dimmed=False)
        self._draw_pillar(cx, cy, FAMILIAR_SIZE, y, COLOR_MAP[CI_GREEN], familiar=True)

    def _neighbor_of_player(self, pos):
        if not self._enlarge_neighbors or self._player_cell is None:
            return False
        px, py = self._player_cell
        return abs(pos[0] - px) + abs(pos[1] - py) == 1

    def _draw_sprite(self, pos, text, color, upper_right_color=None, shade=1.0):
        x, y = pos
        cx, cy = self._field_col_x(x) + self.cell_size_x / 2, (y + 0.5) * self.cell_size_y
        dimmed = color in {self._dim_color(value) for value in COLOR_MAP.values()}
        size = NEIGHBOR_SCALE if self._neighbor_of_player(pos) else 1.0
        self._place_sprite(text, cx, cy, size, y, 'sprite', dimmed, shade)
        self._sprite_cells[pos] = size
        if text in d.CHAR_TO_COMPANION_TRIBE:
            green = COLOR_MAP[CI_GREEN]
            self._draw_pillar(cx, cy, size, y, self._dim_color(green) if dimmed else green)
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
        color = tuple(round(c * shade) for c in color)
        self._draw_ground_disc(cx, cy, GROUND_DISC_RADIUS * self.cell_size_x, color,
                               upper_right_color)

    def _place_sprite(self, text, cx, cy, size, row, layer, dimmed, shade=1.0):
        """Draw a character image with its feet at field pixel (cx, cy)."""
        images = self._gray_images if self.map_mode else self._sprite_images
        picture = images[text]
        padding = max(1, round(self.scale))
        width = max(1, self.cell_size_x - 2 * padding)
        scale = size * 1.8 * width / SPRITE_REFERENCE_PIXELS
        sprite = pyglet.sprite.Sprite(
            picture,
            x=cx - picture.width * scale / 2,
            y=self.window_height - cy - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale,
            batch=self.batch,
            group=self._row_group(row, layer),
        )
        sprite.scale = scale
        if dimmed:
            sprite.color = (128, 128, 128)
        elif shade < 1:
            sprite.color = (round(255 * shade),) * 3
        self._drawables.append(sprite)

    def _draw_pillar(self, cx, cy, size, row, color, familiar=False):
        """Additive light cylinder around a companion: far wall behind, near wall over it."""
        radius = size * PILLAR_RADIUS * self.cell_size_x
        for side, layer in (('back', 'pillar-back'), ('front', 'pillar-front')):
            image = self._pillar_images[side]
            pillar = pyglet.sprite.Sprite(
                image, x=cx - radius,
                y=self.window_height - cy - radius * GROUND_DISC_FLATTEN,
                blend_src=pyglet.gl.GL_SRC_ALPHA, blend_dest=pyglet.gl.GL_ONE,
                batch=self.batch,
                group=self._row_group(row, 'familiar-front' if familiar and side == 'front'
                                      else layer),
            )
            pillar.scale_x = 2 * radius / image.width
            pillar.scale_y = (PILLAR_HEIGHT * size * self.cell_size_x
                              + 2 * radius * GROUND_DISC_FLATTEN) / image.height
            pillar.color = self._display_color(color)
            self._drawables.append(pillar)

    def _draw_ground_disc(self, cx, cy, radius, color, upper_right_color=None):
        """A disc seen at the sprites' 60-degree view, fading outward, below the sprite.

        With `upper_right_color`, that half of the disc takes the second color.
        """
        if upper_right_color is None:
            parts = [(self._disc_image, color)]
        else:
            parts = list(zip(self._disc_halves, (color, upper_right_color)))
        ry = radius * GROUND_DISC_FLATTEN
        for image, tint in parts:
            disc = pyglet.sprite.Sprite(
                image, x=cx - radius, y=self.window_height - cy - ry,
                batch=self.batch, group=self._disc_group,
            )
            disc.scale_x = 2 * radius / image.width
            disc.scale_y = 2 * ry / image.height
            disc.color = self._display_color(tint)
            self._drawables.append(disc)
