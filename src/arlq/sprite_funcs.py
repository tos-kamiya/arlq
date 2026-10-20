"""Pyglet frontend with character sprites and the original text fallback."""

import math
import os
import sys
import time
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
TEXT_PANEL_ALPHA = 176
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
# Low-resolution rendering keeps twice the 100% pixel density for readability.
LOW_RESOLUTION_DETAIL_SCALE = 2.0
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
        self._profile_enabled = os.environ.get('ARLQ_SPRITES_PROFILE') == '1'
        self._low_res_enabled = os.environ.get('ARLQ_SPRITES_LOW_RES') == '1'
        self._profile_flip_times = None
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
        self._wall_images = ({part: pyglet.image.load(str(path))
                              for part, path in zip(WALL_PARTS, paths)}
                             if all(path.is_file() for path in paths) else None)
        floor_paths = [Path(__file__).parent / 'assets' / 'floor' / ('floor-' + part + '.png')
                       for part in FLOOR_PARTS]
        self._floor_images = ([pyglet.image.load(str(path)) for path in floor_paths]
                              if all(path.is_file() for path in floor_paths) else None)
        assets = Path(__file__).parent / 'assets'
        self._terrain_images = {char: pyglet.image.load(str(assets / filename))
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
        self._sidebar_group = pyglet.graphics.Group(order=9999)

    ROW_LAYERS = ('wall', 'column', 'pillar-back', 'sprite', 'pillar-front', 'familiar',
                  'familiar-front', 'mark')

    def _row_group(self, y, layer):
        order = 10 + len(self.ROW_LAYERS) * y + self.ROW_LAYERS.index(layer)
        if order not in self._row_groups:
            self._row_groups[order] = pyglet.graphics.Group(order=order)
        return self._row_groups[order]

    def draw_stage(self, *, rock_cells=None, **kwargs):
        started = time.perf_counter() if self._profile_enabled else None
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
        if started is not None:
            total = time.perf_counter() - started
            cache, batch, present, flip, setup = self._profile_flip_times or (0, 0, 0, 0, 0)
            build = max(0, total - cache - batch - present - flip - setup)
            player = kwargs.get('player')
            render_size = (
                f'{self._render_target_size[0]}x{self._render_target_size[1]}'
                if self._render_target_size else 'window'
            )
            print(
                '[arlq-sprites-profile] '
                f"turn={kwargs.get('turn', '?')} "
                f"size={self.window_width}x{self.window_height} "
                f"render_size={render_size} "
                f"scale={self.scale:.2f} "
                f"floor_view={bool(kwargs.get('floor_view'))} "
                f"drawables={len(self._drawables)} "
                f"build_ms={build * 1000:.2f} "
                f"cache_ms={cache * 1000:.2f} "
                f"batch_ms={batch * 1000:.2f} "
                f"present_ms={present * 1000:.2f} "
                f"flip_ms={flip * 1000:.2f} "
                f"setup_ms={setup * 1000:.2f} "
                f"total_ms={total * 1000:.2f} "
                f"player=({getattr(player, 'x', '?')},{getattr(player, 'y', '?')})",
                file=sys.stderr,
                flush=True,
            )
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
        if not self._low_res_enabled:
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )

        x = pos[0] * self.cell_size_x + x_offset
        y = self.window_height - pos[1] * self.cell_size_y + y_offset
        hud_bottom = 2 * self._hud_row_height
        if x < self.field_pixel_width and y > hud_bottom:
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
        if not self._profile_enabled:
            return self._draw_and_flip()
        setup_start = time.perf_counter()
        self.window.switch_to()
        if self._low_res_enabled and not self._menu_active:
            self._ensure_render_target()
        self._update_composite_scale()
        cache_start = time.perf_counter()
        use_render_target = self._render_framebuffer is not None and not self._menu_active
        if use_render_target:
            self._render_framebuffer.bind()
            pyglet.gl.glViewport(0, 0, *self._render_target_size)
        self.window.clear()
        self._finish_drawables()
        batch_start = time.perf_counter()
        self.batch.draw()
        present_start = time.perf_counter()
        if use_render_target:
            self._render_framebuffer.unbind()
            framebuffer_size = self._framebuffer_size()
            pyglet.gl.glViewport(0, 0, *framebuffer_size)
            self.window.clear()
            self._composite_batch.draw()
        self._text_batch.draw()
        flip_start = time.perf_counter()
        self.window.flip()
        finished = time.perf_counter()
        self._profile_flip_times = (
            batch_start - cache_start,
            present_start - batch_start,
            flip_start - present_start,
            finished - flip_start,
            cache_start - setup_start,
        )

    def _framebuffer_size(self):
        get_size = getattr(self.window, 'get_framebuffer_size', None)
        if get_size is not None:
            return get_size()
        return self.window.width, self.window.height

    def _ensure_render_target(self):
        framebuffer_width, framebuffer_height = self._framebuffer_size()
        divisor = max(1.0, self.scale / LOW_RESOLUTION_DETAIL_SCALE)
        target_size = (
            max(1, round(framebuffer_width / divisor)),
            max(1, round(framebuffer_height / divisor)),
        )
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
        self._composite_sprite = pyglet.sprite.Sprite(
            texture, x=0, y=0, batch=self._composite_batch,
        )
        self._update_composite_scale()

    def _update_composite_scale(self):
        if self._composite_sprite is None:
            return
        self._composite_sprite.scale_x = self.window.width / self._render_texture.width
        self._composite_sprite.scale_y = self.window.height / self._render_texture.height

    def _draw_and_flip(self):
        self.window.switch_to()
        if self._low_res_enabled and not self._menu_active:
            self._ensure_render_target()
        self._update_composite_scale()
        use_render_target = self._render_framebuffer is not None and not self._menu_active
        if use_render_target:
            self._render_framebuffer.bind()
            pyglet.gl.glViewport(0, 0, *self._render_target_size)
        self.window.clear()
        self._finish_drawables()
        self.batch.draw()
        if use_render_target:
            self._render_framebuffer.unbind()
            pyglet.gl.glViewport(0, 0, *self._framebuffer_size())
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

    def _draw_rect(self, x, y, width, height, color):
        if (
            x == self.field_pixel_width
            and y == 0
            and width == self.strength_column_width
            and height == self.field_height * self.cell_size_y
        ):
            y_bottom = self.window_height - y - height
            draw_color = self._display_color(color)
            signature = ('rectangle', x, y_bottom, width, height,
                         draw_color, id(self._sidebar_group))
            self._draw_object(
                signature,
                lambda: pyglet.shapes.Rectangle(
                    x, y_bottom, width, height, color=draw_color,
                    batch=self.batch, group=self._sidebar_group,
                ),
            )
            return
        return super()._draw_rect(x, y, width, height, color)

    def _draw_line(self, x1, y1, x2, y2, color, thickness=1):
        # Visibility boundaries and other lines stay above walls and sprites.
        y1, y2 = self.window_height - y1, self.window_height - y2
        draw_color = self._display_color(color)
        signature = ('line', x1, y1, x2, y2, thickness, draw_color,
                     id(self._overlay_group))
        self._draw_object(
            signature,
            lambda: pyglet.shapes.Line(
                x1, y1, x2, y2, thickness=thickness, color=draw_color,
                batch=self.batch, group=self._overlay_group,
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
        if not (self._low_res_enabled and self._drawing_hud):
            return super()._draw_rect(x, y, width, height, color)
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_rect(x, y, width, height, color)
        finally:
            self.batch = scene_batch

    def _draw_line(self, x1, y1, x2, y2, color, thickness=1):
        if not (self._low_res_enabled and self._drawing_hud):
            return super()._draw_line(x1, y1, x2, y2, color, thickness)
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_line(x1, y1, x2, y2, color, thickness)
        finally:
            self.batch = scene_batch

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
        return TEXT_PANEL_PADDING

    def _draw_progress_panel(self, marks):
        if not marks:
            return
        cells = sum(len(label) + 1 for label, _ in marks) - 1
        self._draw_text_panel('progress', 0, cells * self.cell_size_x)

    def _floor_label_group(self):
        return self._text_overlay_group

    def _draw_floor_label_panel(self, label, x, width):
        self._draw_text_panel('floor', x, width)

    def _draw_text_panel(self, kind, x, width):
        padding = TEXT_PANEL_PADDING
        left = max(0, x - padding)
        row = self.field_height - 1
        top = self.window_height - row * self.cell_size_y
        bottom = top - self.font_size - padding
        panel_width = width + 2 * padding
        height = self.font_size + 2 * padding
        color = (0, 0, 0, TEXT_PANEL_ALPHA)
        signature = ('text-panel', kind, left, bottom, panel_width, height, color,
                     id(self._text_panel_group))
        self._draw_object(
            signature,
            lambda: pyglet.shapes.Rectangle(
                left, bottom, panel_width, height, color=color, batch=self.batch,
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
