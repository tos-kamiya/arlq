"""Floor, wall, stair, pit and barrier drawing for the sprite frontend."""

import math
from functools import partial

import pyglet

from . import defs as d
from .pyglet_funcs import (
    CELL_SIZE_Y,
    CI_GREEN,
    CI_YELLOW,
    COLOR_MAP,
    FLOOR,
    REACHABLE_CELL_COLOR,
    VISIBLE_FLOOR,
    VISIBLE_WALL,
    WALL,
)
from .sprite_defs import (
    GROUND_DISC_RADIUS,
    LOW_RESOLUTION_DETAIL_SCALE,
    ROCK_SPRITE,
    SPRITE_CELL_SIZE_X,
    TERRAIN_OVERHANG,
    TERRAIN_SIDE,
    TERRAIN_TINT,
)
from .sprite_images import (
    BARRIER_HEIGHT,
    EDGE_FLOOR_END_FADE,
    EDGE_FLOOR_SIDE_FADE,
    EDGE_FLOOR_TEXELS_PER_CELL,
    edge_floor_bounds,
    edge_floor_shade_data,
)

# Golem rubble outside the current view is darkened like explored walls.
ROCK_EXPLORED_SHADE = 0.6
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
BARRIER_BASE = 0.0
BARRIER_EXPLORED_SHADE = 0.5
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
TERRAIN_EXPLORED_SHADE = 0.55
# Opacity of the yellow ground disc that marks each stair.
STAIR_DISC_OPACITY = 90


class SpriteTerrainMixin:
    """Floor, wall, stair, pit and barrier drawing of SpriteUI."""

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

    def _set_edge_shade_field(self, field):
        key = id(field)
        if key not in self._edge_shade_fields:
            self._edge_shade_fields[key] = (field, edge_floor_bounds(field))
        bounds = self._edge_shade_fields[key][1]
        if bounds != self._edge_shade_bounds:
            self._edge_shade_bounds = bounds
            self._edge_shade_image = None

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
