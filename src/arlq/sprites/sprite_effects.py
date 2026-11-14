"""Combat and floor transition effects for the sprite frontend."""

from pathlib import Path

import pyglet

from .. import defs as d
from ..pyglet_funcs import CI_GREEN, COLOR_MAP
from .sprite_defs import (
    NEIGHBOR_SCALE,
    SPRITE_REFERENCE_PIXELS,
    SPRITE_GROUND_OFFSET_PIXELS,
    TERRAIN_TINT,
    TERRAIN_SIDE,
    TERRAIN_OVERHANG,
)

# The slash of a won fight, cut the way the player attacked: slash.png is
# the cut of an attack up the screen (see build-slash.py).
SLASH_FILES = {'up': 'slash.png', 'down': 'slash-down.png',
               'left': 'slash-left.png', 'right': 'slash-right.png'}
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
TRANSITION_BACKGROUND = (6, 6, 8)
# The floor transition's timeline, as fractions of its set time: the old
# floor fades to black over the first FLOOR_TRANSITION_FADE, the player then
# moves at a steady speed, and over the last FLOOR_TRANSITION_FADE the new
# floor, already drawn underneath, fades in from black. On stairs and the
# rope the player moves FLOOR_TRANSITION_STEP cells up or down (down a
# staircase it dims to FLOOR_TRANSITION_STAIRS_DIM, up one it brightens from
# it). The stairs turn back at the landing like a "く", so on them the
# player first goes up or down to the right, out to
# FLOOR_TRANSITION_STAIRS_SIDE cells, and then back to the left. A fall
# covers FLOOR_TRANSITION_FALL cells in the same time, so it looks fast, and
# the player shrinks to FLOOR_TRANSITION_FALL_SHRINK and fades out.
FLOOR_TRANSITION_FADE = 0.15
FLOOR_TRANSITION_STEP = 0.25
FLOOR_TRANSITION_STAIRS_SIDE = 0.125
FLOOR_TRANSITION_FALL = 0.5
FLOOR_TRANSITION_STAIRS_DIM = 0.4
FLOOR_TRANSITION_FALL_SHRINK = 0.7
LANDING_FEET_HEIGHT = 0.725
ROPE_COLOR = (160, 134, 96)
ROPE_WIDTH, ROPE_OFFSET, ROPE_LENGTH = 0.08, 0.1, 2.0
ROPE_GLOW_WIDTH, ROPE_GLOW_LENGTH, ROPE_GLOW_OPACITY = 0.9, 1.3, 90


class SpriteEffectsMixin:
    """Combat and floor transition effects of SpriteUI."""

    def _play_effect(self, seconds, create, update=None):
        self._presenter.hold(self, seconds, create, update)

    def draw_combat_effect(self, pos, won: bool) -> None:
        seconds = self.combat_effect_seconds
        if seconds == 0:
            return
        positions = [pos] if len(pos) == 2 and all(
            isinstance(value, (int, float)) for value in pos
        ) else pos
        effects = Path(__file__).parent.parent / "assets" / "effects"
        path = effects / (SLASH_FILES.get(self._attack_facing, "slash.png") if won
                          else "splash.png")
        if not path.is_file():
            path = effects / "slash.png"
        image = pyglet.image.load(str(path))

        def create():
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
            return effects

        self._play_effect(seconds, create)

    def draw_floor_transition(self, kind, player, exit_point=None) -> None:
        """Show the moment between floors: on the landing of the stairs the
        player is taking, or alone in the dark falling through or climbing
        out of a pit, on the cell it left from. The scene fades in over the
        old floor, the player moves, and the new floor fades in from black
        (see FLOOR_TRANSITION_FADE)."""
        seconds = self.floor_transition_seconds
        if seconds == 0 or '@' not in self._sprite_images:
            return
        revealed = []

        def update(progress):
            # Draw the new floor under the scene once, as the fade out begins;
            # without it (no next view), the scene stays until the cut.
            if (not revealed and progress >= 1 - FLOOR_TRANSITION_FADE
                    and self._next_view is not None):
                revealed.append(True)
                self.draw_stage(**self._next_view)
            self._animate_floor_transition(kind, progress, bool(revealed))

        self._play_effect(
            seconds, lambda: self._create_floor_transition(kind, player, exit_point), update,
        )

    def _animate_floor_transition(self, kind, progress, fade_out):
        parts = self._transition_parts
        fade = min(1.0, progress / FLOOR_TRANSITION_FADE)
        if fade_out:
            fade = min(fade, (1 - progress) / FLOOR_TRANSITION_FADE)
        move = min(1.0, max(0.0, (progress - FLOOR_TRANSITION_FADE)
                            / (1 - 2 * FLOOR_TRANSITION_FADE)))
        size, alpha, side = 1.0, 1.0, 0.0
        if kind in ('down', 'up'):
            # Out to the right over the first half, back over the second.
            side = FLOOR_TRANSITION_STAIRS_SIDE * (1 - abs(2 * move - 1))
        if kind == 'down':
            offset = -FLOOR_TRANSITION_STEP * move
            alpha = 1 - (1 - FLOOR_TRANSITION_STAIRS_DIM) * move
        elif kind == 'up':
            offset = -FLOOR_TRANSITION_STEP * (1 - move)
            alpha = FLOOR_TRANSITION_STAIRS_DIM + (1 - FLOOR_TRANSITION_STAIRS_DIM) * move
        elif kind == 'climb':
            offset = -FLOOR_TRANSITION_STEP * (1 - move)
        else:
            offset = -FLOOR_TRANSITION_FALL * move
            size = 1 - (1 - FLOOR_TRANSITION_FALL_SHRINK) * move
            alpha = 1 - move
        # Offsets are in cells (up the screen, and to the right for `side`);
        # the feet stay the anchor.
        figure, cx, cy, picture, scale = parts['figure']
        scale *= size
        figure.scale = scale
        figure.x = cx + side * self.cell_size_x - picture.width * scale / 2
        figure.y = (self.window_height - cy + offset * self.cell_size_y
                    - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale)
        figure.opacity = round(255 * alpha * fade)
        for obj, opacity in parts['fading']:
            obj.opacity = round(opacity * fade)

    def _create_floor_transition(self, kind, player, exit_point):
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
        # The parts the animation moves and fades (see
        # _animate_floor_transition), with each one's full opacity.
        self._transition_parts = {
            'figure': (figure, cx, cy, picture, scale),
            'fading': [(shape, 255) for shape in shapes[:-1]],
        }
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
            rope = pyglet.shapes.Rectangle(
                round(rope_x - width / 2),
                self.window_height - (rope_middle + length / 2),
                width, length, color=self._display_color(ROPE_COLOR),
                batch=self.batch, group=pyglet.graphics.Group(order=100001),
            )
            shapes.append(rope)
            self._transition_parts['fading'] += [(glow, ROPE_GLOW_OPACITY), (rope, 255)]
        return shapes
