"""Pyglet frontend with character sprites and the original text fallback."""

import math
from pathlib import Path

import pyglet

from . import defs as d
from . import display as ui_display
from .pyglet_funcs import COLOR_MAP, PygletUI


SPRITE_FILES = {
    '@': 'player.png',
    'a': 'amoeba.png',
    'A': 'rare-amoeba.png',
    'b': 'bison.png',
    'c': 'chimera.png',
    'd': 'comodo-dragon.png',
    'D': 'dragon.png',
    'T': 'treasure.png',
}
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
        self._disc_image = ground_disc_image()
        self._disc_halves = (ground_disc_image('lower-left'), ground_disc_image('upper-right'))
        self._disc_group = pyglet.graphics.Group(order=1)
        self._sprite_group = pyglet.graphics.Group(order=2)

    def _draw_player(self, pos, player):
        if '@' not in self._sprite_images:
            return super()._draw_player(pos, player)
        # Low/warning LP colors the ground disc instead of filling the cell;
        # poison turns the disc's upper-right half purple.
        _, background = ui_display.player_appearance(player)
        poison = self._tone_color('magenta') if player.item == d.ITEM_POISONED else None
        self._draw_sprite(pos, '@', self._tone_color(background or 'default'), poison)

    def _draw_field_text(self, pos, text, color, bold=False):
        if text not in self._sprite_images:
            return super()._draw_field_text(pos, text, color, bold)
        self._draw_sprite(pos, text, color)

    def _draw_sprite(self, pos, text, color, upper_right_color=None):
        images = self._gray_images if self.map_mode else self._sprite_images
        picture = images[text]
        x, y = pos
        padding = max(1, round(self.scale))
        width = max(1, self.cell_size_x - 2 * padding)
        scale = 1.8 * width / SPRITE_REFERENCE_PIXELS
        sprite = pyglet.sprite.Sprite(
            picture,
            x=self._field_col_x(x) + (self.cell_size_x - picture.width * scale) / 2,
            y=self.window_height - (y + 0.5) * self.cell_size_y
            - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale,
            batch=self.batch,
            group=self._sprite_group,
        )
        sprite.scale = scale
        if color in {self._dim_color(value) for value in COLOR_MAP.values()}:
            sprite.color = (128, 128, 128)
        self._drawables.append(sprite)
        # Keep the original semantic color (strength, poison, etc.) readable
        # as a glowing disc on the ground the character stands on.
        self._draw_ground_disc(
            self._field_col_x(x) + self.cell_size_x / 2,
            (y + 0.5) * self.cell_size_y,
            GROUND_DISC_RADIUS * self.cell_size_x, color, upper_right_color,
        )

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
