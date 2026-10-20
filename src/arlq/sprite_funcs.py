"""Pyglet frontend with character sprites and the original text fallback."""

import math
from functools import partial
from pathlib import Path

import pyglet

from . import defs as d
from . import display as ui_display
from .arlq import barrier_lp_damage
from .pyglet_funcs import (
    CELL_SIZE_X,
    CELL_SIZE_Y,
    CI_BLUE,
    CI_GREEN,
    CI_YELLOW,
    COLOR_MAP,
    FLOOR,
    FONT_HEIGHT_RATIO,
    MAX_UI_SCALE,
    MIN_UI_SCALE,
    REACHABLE_CELL_COLOR,
    STRENGTH_COLUMN_PADDING,
    VISIBLE_FLOOR,
    VISIBLE_WALL,
    WALL,
    PygletUI,
)

SPRITE_FILES = {
    '@': 'player.png',
    'a': 'amoeba.png',
    'A': 'rare-amoeba.png',
    'b': 'bison.png',
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
    'g': 'golem.png',
    'k': 'marksman.png',
    'V': 'vortex.png',
    'w': 'wyrm.png',
    'W': 'dread-wyrm.png',
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
# A dark translucent backing keeps the elf and treasure progress marks legible
# when the tall field sprites extend behind the bottom status row.
TEXT_PANEL_ALPHA = 112
TEXT_PANEL_PADDING = 4
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
MAX_WINDOW_WIDTH = 32767
STRENGTH_TEXT_SCALE = 0.7
# Keep an integer 26x40 pixel grid per field cell at every window size.
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
# the red "=": a few translucent cone-shaped fires with wide roots rising from
# spots in the lower half of the cell (two variants, laid out as a
# checkerboard), glowing at their roots and added onto the floor, the tallest
# reaching a little into the cell above. While the protective amulet makes
# barriers harmless, the cells within one cell of the player (its own and the
# eight around it) show only faint grey smoke of the same shape. Flames outside the current
# view are darkened like the floor. Sizes are in cell widths/heights.
FLAME_TEXELS = (48, 96)
FLAME_HEIGHT = 1.3
FLAME_BASE = 0.0
FLAME_ALPHA = 0.9
# Opacity of a flame's middle relative to its edges.
FLAME_CORE_ALPHA = 0.55
FLAME_EXPLORED_SHADE = 0.5
# Fires of the second variant: (centre, root centre height as a fraction of
# the lower half, half width, height, brightness); the fires further back are
# dimmer. The first variant is its mirror image.
_FLAME_FIRES = ((0.335, 0.377, 0.28, 0.48, 1.0), (0.716, 0.505, 0.26, 0.40, 1.0),
                (0.269, 0.932, 0.23, 0.40, 0.6), (0.601, 1.313, 0.15, 0.27, 0.6))
FLAME_FIRES = (tuple((1 - centre, *rest) for centre, *rest in _FLAME_FIRES), _FLAME_FIRES)
SMOKE_TINT = (150, 150, 156)
SMOKE_OPACITY = 140
# Stairs and Collapse pits are drawn on the walls' canvas and placed like a
# wall part: near-white marble flights (up: rising north; down: descending
# toward the viewer into a dark opening) and a jagged hole broken through the
# flagstones. They are tinted gold, as their yellow glyphs were, and darkened
# like the floor outside the current view.
TERRAIN_FILES = {d.CHAR_STAIRS_UP: 'stairs/stairs-up.png',
                 d.CHAR_STAIRS_DOWN: 'stairs/stairs-down.png',
                 d.CHAR_COLLAPSE: 'pit/pit.png'}
TERRAIN_TINT = (255, 222, 150)
TERRAIN_EXPLORED_SHADE = 0.55
# Opacity of the yellow ground disc that marks each stair.
STAIR_DISC_OPACITY = 90


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
    """A few fires rising from spots in the lower half of a cell.

    Each fire is a cone seen at the sprites' 60-degree view: its round root
    shows as an ellipse, widest and bright orange, and it narrows to a deep
    red tip, with a soft glow around the root. Its body is translucent,
    thinner inside than along its edges, so the floor shows through, and
    overlapping fires add up so the one behind shows through. The image is
    drawn additively from the cell's bottom; `variant` (0 or 1) places the
    fires differently so neighbouring cells do not repeat.
    """
    width, height = FLAME_TEXELS
    lower_half = 0.5 / FLAME_HEIGHT  # the cell's middle, in image fractions
    # Image heights per image width for a circle on the floor.
    flatten = GROUND_DISC_FLATTEN * CELL_SIZE_X / (FLAME_HEIGHT * CELL_SIZE_Y)
    fires = FLAME_FIRES[variant]
    root, tip = (255, 160, 60), (230, 35, 15)
    rgba = bytearray()
    for row in range(height):
        v = (row + 0.5) / height
        for col in range(width):
            u = (col + 0.5) / width
            # Fires combine like light: each lets the others show through.
            clear, weight, along = 1.0, 0.0, 0.0
            for centre, base, half, tall, bright in fires:
                base *= lower_half
                t = (v - base) / tall
                ry = half * flatten
                # A soft glow on the floor around the root.
                glow = 0.35 * max(0.0, 1 - math.hypot((u - centre) / (half * 1.4),
                                                      (v - base) / (ry * 1.4)))
                value = glow
                depth = 1.0
                if t < 0 and v - base > -ry:
                    # The near half of the root ellipse, thinner toward its rim.
                    depth = math.sqrt(1 - ((v - base) / ry) ** 2)
                    w = half * depth
                    t = 0.0
                elif 0 <= t < 1:
                    # Above the root's centre, narrowing to the tip.
                    w = half * (1 - t) ** 0.9
                else:
                    w = 0.0
                if w > 0:
                    across = abs(u - centre) / w
                    if across < 1:
                        # Hotter near the root, fading softly toward the edges.
                        core = FLAME_CORE_ALPHA + (1 - FLAME_CORE_ALPHA) * 0.5 * max(0.0, 1 - t / 0.25)
                        body = depth * (core + (1 - core) * across ** 2)
                        value = max(value, body * (1 - across ** 2) ** 0.8 * (1 - t) ** 0.6)
                value *= bright
                clear *= 1 - min(1.0, value)
                weight += value
                along += value * max(t, 0.0)
            strength = 1 - clear
            mix = min(1.0, along / weight / 0.7) if weight > 0 else 1.0
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
        self._last_stage_draw = None
        self._resize_redraw_pending = False
        self._render_framebuffer = None
        self._render_texture = None
        self._composite_batch = None
        self._composite_sprite = None
        self._render_target_size = None
        self._failed_render_target_size = None
        super().__init__(scale, key_repeat_interval, resizable=True)
        self._text_batch = pyglet.graphics.Batch()
        self._hud_row_height = self._menu_cell_size_y
        self._drawing_hud = False
        self.window.set_caption(self.window.caption.replace('Pyglet mix', 'Sprite mix'))
        self._update_minimum_window_size()
        directory = Path(__file__).parent / 'assets' / 'characters'
        self._sprite_images = {}
        self._gray_images = {}
        for char, filename in SPRITE_FILES.items():
            path = directory / filename
            if not path.is_file():
                continue
            data = pyglet.image.load(str(path)).get_image_data()
            self._sprite_images[char] = mipmapped(data)
            rgba = bytearray(data.get_data('RGBA', data.width * 4))
            for offset in range(0, len(rgba), 4):
                r, g, b = rgba[offset:offset + 3]
                gray = (299 * r + 587 * g + 114 * b) // 1000
                rgba[offset:offset + 3] = bytes((gray, gray, gray))
            self._gray_images[char] = mipmapped(pyglet.image.ImageData(
                data.width, data.height, 'RGBA', bytes(rgba), pitch=data.width * 4
            ))
        self._mark_images = {mark: mipmapped(pyglet.image.load(str(directory / filename)))
                             for mark, filename in MARK_FILES.items()
                             if (directory / filename).is_file()}
        # Cells where a character sprite was drawn this frame; a rank mark in
        # the next cell belongs to that sprite.
        self._sprite_cells = {}
        self._drawable_cache = {}
        self._frame_drawable_cache = None
        self._drawable_use_counts = None
        self._reused_drawable_ids = set()
        self._disc_image = ground_disc_image()
        self._disc_halves = (ground_disc_image('lower-left'), ground_disc_image('upper-right'))
        self._disc_group = pyglet.graphics.Group(order=1)
        self._pillar_images = {side: pillar_image(side) for side in ('back', 'front')}
        wall_directory = Path(__file__).parent / 'assets' / 'walls'
        paths = [wall_directory / ('wall-' + part + '.png') for part in WALL_PARTS]
        self._wall_images = ({part: mipmapped(pyglet.image.load(str(path)))
                              for part, path in zip(WALL_PARTS, paths)}
                             if all(path.is_file() for path in paths) else None)
        floor_paths = [Path(__file__).parent / 'assets' / 'floor' / ('floor-' + part + '.png')
                       for part in FLOOR_PARTS]
        self._floor_images = ([mipmapped(pyglet.image.load(str(path))) for path in floor_paths]
                              if all(path.is_file() for path in floor_paths) else None)
        assets = Path(__file__).parent / 'assets'
        self._terrain_images = {char: mipmapped(pyglet.image.load(str(assets / filename)))
                                for char, filename in TERRAIN_FILES.items()
                                if (assets / filename).is_file()}
        self._flame_images = [flame_image(variant) for variant in (0, 1)]
        self._smoke_images = [smoke_image(flame) for flame in self._flame_images]
        self._floor_group = pyglet.graphics.Group(order=-1)
        # Rows are painted north to south: a row's walls, then its characters,
        # so walls overlap characters to their north but not to their south.
        self._row_groups = {}
        self._overlay_group = pyglet.graphics.Group(order=10000)
        self._text_panel_group = pyglet.graphics.Group(order=9999)
        self._text_overlay_group = pyglet.graphics.Group(order=10001)
        self._sidebar_bg_group = pyglet.graphics.Group(order=9998)
        self._sidebar_group = pyglet.graphics.Group(order=9999)
        self._floor_tiles = None
        self._floor_cell_tiles = {}
        self._floor_cells = {}
        self._create_floor_tiles()

    def _create_floor_tiles(self):
        """Bake colored 2x2 floors into one nearest-filtered texture atlas."""
        if self._floor_images is None:
            return
        gl = pyglet.gl
        cell_width = round(CELL_SIZE_X * LOW_RESOLUTION_DETAIL_SCALE)
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
                for col, (tile_color, tint) in enumerate(FLOOR_TINTS.items()):
                    left, bottom = col * width, row * height
                    for y in range(2):
                        for x in range(2):
                            odd = (x + y) % 2
                            image = self._floor_images[odd]
                            shade = FLOOR_CHECKER_SHADE if odd else 1
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
        order = 10 + len(self.ROW_LAYERS) * y + self.ROW_LAYERS.index(layer)
        if order not in self._row_groups:
            self._row_groups[order] = pyglet.graphics.Group(order=order)
        return self._row_groups[order]

    def draw_stage(self, *, rock_cells=None, **kwargs):
        self._last_stage_draw = (rock_cells, kwargs.copy())
        self._rock_cells = rock_cells or set()
        self._known_types = kwargs.get('known_types') or set()
        self._cur_torched = kwargs.get('cur_torched')
        player = kwargs.get('player')
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
            if player is not None and not kwargs.get('floor_view') and barrier_lp_damage(player) == 0
            else None
        )
        result = super().draw_stage(rock_cells=rock_cells, **kwargs)
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
        if not self._resize_redraw_pending or not self._stage_input_active:
            return
        self._resize_redraw_pending = False
        if self._last_stage_draw is not None:
            rock_cells, kwargs = self._last_stage_draw
            self.draw_stage(rock_cells=rock_cells, **kwargs)

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
        group = self._row_group(y, 'pillar-back')
        blend_dest = pyglet.gl.GL_ONE_MINUS_SRC_ALPHA if cooled else pyglet.gl.GL_ONE
        scale_x = (self._field_col_width(x) + 1) / image.width
        scale_y = FLAME_HEIGHT * self.cell_size_y / image.height
        tint = (self._display_color(SMOKE_TINT) if cooled else self._display_color(
            (round(255 * (1 if visible else FLAME_EXPLORED_SHADE)),) * 3
        ))
        opacity = SMOKE_OPACITY if cooled else 255
        signature = ('sprite', id(image), self._field_col_x(x), bottom, scale_x, scale_y,
                     id(group), pyglet.gl.GL_SRC_ALPHA, blend_dest, tint, opacity)
        flame = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                image, x=self._field_col_x(x), y=bottom,
                blend_src=pyglet.gl.GL_SRC_ALPHA, blend_dest=blend_dest,
                batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(flame, 'scale_x', scale_x)
        self._set_drawable_attribute(flame, 'scale_y', scale_y)
        self._set_drawable_attribute(flame, 'color', tint)
        self._set_drawable_attribute(flame, 'opacity', opacity)

    def _draw_stairs(self, pos, char):
        if char not in self._terrain_images:
            return super()._draw_stairs(pos, char)
        x, y = pos
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        shade = 1 if visible else TERRAIN_EXPLORED_SHADE
        # A ground disc like the characters', in the respawn point's yellow,
        # so stairs stand out.
        self._draw_ground_disc(self._field_col_x(x) + self.cell_size_x / 2,
                               (y + 0.5) * self.cell_size_y,
                               GROUND_DISC_RADIUS * self.cell_size_x,
                               tuple(round(c * shade) for c in COLOR_MAP[CI_YELLOW]),
                               opacity=STAIR_DISC_OPACITY)
        # The up flight rises into the cell to the north, like a column.
        self._draw_terrain(pos, char, 'column' if char == d.CHAR_STAIRS_UP else 'wall')

    def _draw_pit(self, pos):
        if d.CHAR_COLLAPSE not in self._terrain_images:
            return super()._draw_pit(pos)
        self._draw_terrain(pos, d.CHAR_COLLAPSE, 'wall')

    def _draw_terrain(self, pos, char, layer):
        x, y = pos
        image = self._terrain_images[char]
        visible = self._cur_torched is not None and self._cur_torched[y][x]
        shade = 1 if visible else TERRAIN_EXPLORED_SHADE
        base = (220, 220, 220) if self.map_mode else TERRAIN_TINT
        draw_tint = self._display_color(tuple(round(c * shade) for c in base))
        left = self._field_col_x(x)
        bottom = self.window_height - (y + 1) * self.cell_size_y
        scale_x = (self._field_col_width(x) + 1) / image.width
        scale_y = (1 + WALL_OVERHANG) * self.cell_size_y / image.height
        group = self._row_group(y, layer)
        signature = ('sprite', id(image), left, bottom, scale_x, scale_y, id(group), draw_tint)
        terrain = self._draw_object(
            signature,
            partial(pyglet.sprite.Sprite, image, x=left, y=bottom,
                    batch=self.batch, group=group),
        )
        self._set_drawable_attribute(terrain, 'scale_x', scale_x)
        self._set_drawable_attribute(terrain, 'scale_y', scale_y)
        self._set_drawable_attribute(terrain, 'color', draw_tint)

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
                    group = self._row_group(y, 'column' if part == 'column' else 'wall')
                    bottom = self.window_height - (y + 1) * self.cell_size_y
                    scale_x = width / image.width
                    scale_y = height / image.height
                    draw_tint = self._display_color(tint)
                    signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                                 id(group), draw_tint)
                    piece = self._draw_object(
                        signature,
                        partial(
                            pyglet.sprite.Sprite, image, x=left, y=bottom,
                            batch=self.batch, group=group,
                        ),
                    )
                    self._set_drawable_attribute(piece, 'scale_x', scale_x)
                    self._set_drawable_attribute(piece, 'scale_y', scale_y)
                    self._set_drawable_attribute(piece, 'color', draw_tint)
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
        if getattr(self, '_floor_tiles', None) is not None:
            self._floor_cells[x, y] = tile_color
            return
        if self._floor_images is None:
            return super()._draw_tile(x, y, tile_color, field, discovered_at)
        odd = (x + y) % 2
        image = self._floor_images[odd]
        shade = FLOOR_CHECKER_SHADE if odd else 1
        tint = tuple(round(c * shade) for c in FLOOR_TINTS[tile_color])
        left = self._field_col_x(x)
        bottom = self.window_height - (y + 1) * self.cell_size_y
        scale_x = (self._field_col_width(x) + 1) / image.width
        scale_y = (self.cell_size_y + 1) / image.height
        draw_tint = self._display_color(tint)
        signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                     id(self._floor_group), draw_tint)
        stone = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=self._floor_group,
            ),
        )
        self._set_drawable_attribute(stone, 'scale_x', scale_x)
        self._set_drawable_attribute(stone, 'scale_y', scale_y)
        self._set_drawable_attribute(stone, 'color', draw_tint)

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
        scale = self.scale / LOW_RESOLUTION_DETAIL_SCALE
        signature = ('floor-copy', id(image), left, bottom, scale, id(self._floor_group))
        sprite = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=self._floor_group,
                blend_src=pyglet.gl.GL_ONE, blend_dest=pyglet.gl.GL_ZERO,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)

    def _draw_wall_rect(self, x, y, width, height, color, shade, group):
        color = tuple(min(255, round(c * shade)) for c in color)
        bottom = self.window_height - y - height
        draw_color = self._display_color(color)
        signature = ('rectangle', x, bottom, width, height, draw_color, id(group))
        self._draw_object(
            signature,
            lambda: pyglet.shapes.Rectangle(
                x, bottom, width, height, color=draw_color, batch=self.batch, group=group,
            ),
        )

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
        self._map_pixel_width = self.field_pixel_width
        self.field_pixel_width = self._map_pixel_width
        self.window_width = self._map_pixel_width + self.strength_column_width
        if hasattr(self, '_hud_row_height'):
            self._hud_row_height = self._row_height_for_width(self.window_width)
            self.window_height = round(
                self.field_height * self.cell_size_y + 2 * self._hud_row_height
            )
        self._horizontal_scroll_px = 0
        self._camera_follow_player = True
        self._last_camera_player_pos = None

    def _row_height_for_width(self, width):
        return self._menu_cell_size_y

    def _status_font_scale(self):
        return self._menu_font_size / self.font_size

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
            (2 + STRENGTH_SPRITE_CELLS) * max_cell_width + 2 * max_padding
        )
        minimum_width = math.ceil(max_strength_width + max_cell_width)
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

    def _draw_rect(self, x, y, width, height, color):
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
            return super()._draw_rect(x, y, width, height, color)
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_rect(x, y, width, height, color)
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

    def draw_status_bar(self, *args, **kwargs):
        self._drawing_hud = True
        try:
            return super().draw_status_bar(*args, **kwargs)
        finally:
            self._drawing_hud = False

    def _on_window_resize(self, width, height):
        old_cell_width = self.cell_size_x
        old_scroll_cells = self._horizontal_scroll_px / old_cell_width
        follow_player = self._camera_follow_player
        last_player_pos = self._last_camera_player_pos
        width_changed = width != self.window_width
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
            if self.window_height != height:
                self.window.set_size(width, self.window_height)
        elif width_changed:
            self._hud_row_height = hud_row_height
            resized_height = round(
                self.field_height * self.cell_size_y + 2 * self._hud_row_height
            )
            self._set_resized_dimensions(
                width, resized_height, hud_row_height, field_scale=self.scale
            )
            if resized_height != height:
                self.window.set_size(width, resized_height)
        else:
            self.window_width = width
            self.window_height = height
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

    def _set_resized_dimensions(self, width, height, hud_row_height, field_scale=None):
        field_pixel_height = height - 2 * hud_row_height
        if field_scale is not None:
            self.scale = self._valid_scale(field_scale)
        else:
            self.scale = self._valid_scale(
                field_pixel_height / (self.field_height * CELL_SIZE_Y)
            )
        self.cell_size_x = CELL_SIZE_X * self.scale
        self.cell_size_y = self.scale * CELL_SIZE_Y
        self.font_size = max(1, round(self.cell_size_y * FONT_HEIGHT_RATIO))
        self.strength_column_padding = max(
            1, round(STRENGTH_COLUMN_PADDING * self.scale)
        )
        self.strength_column_width = (
            (2 + STRENGTH_SPRITE_CELLS) * self.cell_size_x
            + 2 * self.strength_column_padding
        )
        self._map_pixel_width = self.field_width * self.cell_size_x
        self.window_width = width
        self._hud_row_height = hud_row_height
        self.window_height = round(
            self.field_height * self.cell_size_y + 2 * self._hud_row_height
        )

    def _field_col_x(self, col):
        return col * self.cell_size_x - getattr(self, '_horizontal_scroll_px', 0)

    def _field_text_x_offset(self):
        return -getattr(self, '_horizontal_scroll_px', 0)

    def _horizontal_scroll_bounds(self):
        if self.field_pixel_width >= self._map_pixel_width:
            return (0, 0)
        margin = self.cell_size_x
        return (
            -margin,
            self._map_pixel_width - self.field_pixel_width + margin,
        )

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
            max(min_scroll, self._horizontal_scroll_px + direction * self.cell_size_x),
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
                        x_offset=left, size_scale=STRENGTH_TEXT_SCALE,
                        group=self._overlay_group)
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
        if self._menu_active:
            self._menu_text_records = []
        # Keep last frame's objects available for exact matches. They remain
        # attached to the batch until _finish_drawables removes stale ones.
        self._frame_drawable_cache = {}
        self._drawable_use_counts = {}
        self._reused_drawable_ids = set()
        self._drawables = []
        self._sprite_cells.clear()
        self._player_cell = None
        self._floor_cells = {}

    def _draw_object(self, signature, factory):
        """Reuse a drawable when its complete render description is unchanged."""
        if getattr(self, '_frame_drawable_cache', None) is None:
            return super()._draw_object(signature, factory)
        index = self._drawable_use_counts.get(signature, 0)
        self._drawable_use_counts[signature] = index + 1
        old_objects = self._drawable_cache.get(signature, ())
        if index < len(old_objects):
            drawable = old_objects[index]
            self._reused_drawable_ids.add(id(drawable))
        else:
            drawable = factory()
        self._frame_drawable_cache.setdefault(signature, []).append(drawable)
        self._drawables.append(drawable)
        return drawable

    def _finish_drawables(self):
        if self._frame_drawable_cache is None:
            return
        if self._floor_cells:
            self._draw_floor_tiles()
        for signature, old_objects in self._drawable_cache.items():
            retained = len(self._frame_drawable_cache.get(signature, ()))
            for drawable in old_objects[retained:]:
                drawable.delete()
        self._drawable_cache = self._frame_drawable_cache
        self._frame_drawable_cache = None
        self._drawable_use_counts = None
        self._reused_drawable_ids = set()

    def _set_drawable_attribute(self, drawable, name, value):
        if id(drawable) not in getattr(self, '_reused_drawable_ids', ()):
            setattr(drawable, name, value)

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
        left = self._field_col_x(x) + (0.5 + dx) * self.cell_size_x - image.width * scale / 2
        bottom = self.window_height - (y + 0.5 - dy) * self.cell_size_y - image.height * scale / 2
        group = self._row_group(y, 'mark')
        # White like the strength column, not the strength color; only the
        # half-bright dimming of the glyph is kept.
        white = COLOR_MAP['default']
        dimmed = color in {self._dim_color(value) for value in COLOR_MAP.values()}
        tint = self._display_color(self._dim_color(white) if dimmed else white)
        signature = ('sprite', id(image), left, bottom, scale, scale, id(group), tint)
        sprite = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)

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
        if self.map_mode and max(color) <= 128 and max(color) - min(color) <= 16:
            # Map sprites use a grey texture. Preserve the half-bright marker
            # for dim neutral colors supplied by callers outside COLOR_MAP.
            dimmed = True
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
        left = cx - picture.width * scale / 2
        bottom = self.window_height - cy - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale
        group = self._row_group(row, layer)
        tint = ((128, 128, 128) if dimmed else
                (round(255 * shade),) * 3 if shade < 1 else (255, 255, 255))
        tint = self._display_color(tint)
        signature = ('sprite', id(picture), left, bottom, scale, scale, id(group), tint)
        sprite = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                picture, x=left, y=bottom, batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)

    def _draw_pillar(self, cx, cy, size, row, color, familiar=False):
        """Additive light cylinder around a companion: far wall behind, near wall over it."""
        radius = size * PILLAR_RADIUS * self.cell_size_x
        for side, layer in (('back', 'pillar-back'), ('front', 'pillar-front')):
            image = self._pillar_images[side]
            left = cx - radius
            bottom = self.window_height - cy - radius * GROUND_DISC_FLATTEN
            scale_x = 2 * radius / image.width
            scale_y = (PILLAR_HEIGHT * size * self.cell_size_x
                       + 2 * radius * GROUND_DISC_FLATTEN) / image.height
            group = self._row_group(row, 'familiar-front' if familiar and side == 'front'
                                    else layer)
            tint = self._display_color(color)
            signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                         id(group), pyglet.gl.GL_SRC_ALPHA, pyglet.gl.GL_ONE, tint)
            pillar = self._draw_object(
                signature,
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
            disc = self._draw_object(
                signature,
                partial(
                    pyglet.sprite.Sprite, image, x=left, y=bottom,
                    batch=self.batch, group=self._disc_group,
                ),
            )
            self._set_drawable_attribute(disc, 'scale_x', scale_x)
            self._set_drawable_attribute(disc, 'scale_y', scale_y)
            self._set_drawable_attribute(disc, 'color', draw_tint)
            self._set_drawable_attribute(disc, 'opacity', opacity)
