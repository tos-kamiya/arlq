"""Pyglet frontend with character sprites and the original text fallback."""

from pathlib import Path

import pyglet

from .pyglet_funcs import COLOR_MAP, PygletUI


SPRITE_FILES = {
    '@': 'player.png',
    'a': 'amoeba.png',
    'A': 'rare-amoeba.png',
    'b': 'bison.png',
    'd': 'comodo-dragon.png',
}


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
        self._sprite_group = pyglet.graphics.Group(order=1)

    def _draw_field_text(self, pos, text, color, bold=False):
        images = self._gray_images if self.map_mode else self._sprite_images
        picture = images.get(text)
        if picture is None:
            return super()._draw_field_text(pos, text, color, bold)
        x, y = pos
        padding = max(1, round(self.scale))
        width = max(1, self.cell_size_x - 2 * padding)
        height = max(1, self.cell_size_y - 2 * padding)
        scale = 1.8 * min(width / picture.width, height / picture.height)
        sprite = pyglet.sprite.Sprite(
            picture,
            x=self._field_col_x(x) + (self.cell_size_x - picture.width * scale) / 2,
            y=self.window_height - (y + 1) * self.cell_size_y
            + (self.cell_size_y - picture.height * scale) / 2,
            batch=self.batch,
            group=self._sprite_group,
        )
        sprite.scale = scale
        if color in {self._dim_color(value) for value in COLOR_MAP.values()}:
            sprite.color = (128, 128, 128)
        self._drawables.append(sprite)
        # Keep the original semantic color (strength, poison, etc.) readable.
        self._draw_rect_outline(
            self._field_col_x(x), y * self.cell_size_y,
            self.cell_size_x, self.cell_size_y, color,
        )
