"""Capture the actual sprite effects and convert their pixels to double-width braille.

Run: PYGLET_HEADLESS=1 .venv/bin/python dev-samples/braille-effects-preview/build_wide.py
"""
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('PYGLET_HEADLESS', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
import pyglet
from arlq.sprites.sprite_effects import SpriteEffectsMixin
from arlq.sprites.sprite_images import ground_disc_image

COLS, ROWS = 21, 15
WIDTH, HEIGHT = COLS * 48, ROWS * 48
BG = (36, 40, 44)
BITS = ((1, 8), (2, 16), (4, 32), (64, 128))
OUT = Path(__file__).parent

class Capture(SpriteEffectsMixin):
    combat_effect_seconds = 1.0
    cell_size_x = 48
    cell_size_y = 48
    window_height = HEIGHT
    def __init__(self, name):
        self.name = name
        self.batch = pyglet.graphics.Batch()
        self._disc_image = ground_disc_image()
        self._dome_images = None
        self._pillar_image = None
        self.frames = []
    def _field_col_x(self, x):
        return x * self.cell_size_x
    def _display_color(self, color):
        return color
    def _play_effect(self, seconds, create, update=None):
        objects = create()
        for index in range(12):
            if update:
                update((index + 1) / 14)
            pyglet.gl.glClearColor(*(v / 255 for v in BG), 1)
            window.clear()
            self.batch.draw()
            image = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
            pixels = image.get_data('RGBA', WIDTH * 4)
            self.frames.append(convert(pixels, self.name, (index + 1) / 14))
        for obj in objects:
            obj.delete()

def convert(pixels, name, progress):
    # Sample each braille dot's area; compare against the actual
    # background so both dark smoke and light are represented.
    lines = []
    for cy in range(ROWS):
        line = []
        for cx in range(COLS * 2):
            mask = 0
            colors = []
            for dy in range(4):
                for dx in range(2):
                    px = (cx * 2 + dx + .5) * WIDTH / (COLS * 4)
                    py = (cy * 4 + dy + .5) * HEIGHT / (ROWS * 4)
                    x, y = int(px), HEIGHT - 1 - int(py)
                    i = (y * WIDTH + x) * 4
                    rgb = tuple(pixels[i:i+3])
                    difference = max(abs(rgb[k] - BG[k]) for k in range(3))
                    # Suppress faint, isolated motes late in the core burst.
                    threshold = 13 if name == 'Vortex' else 6
                    if name == 'Dungeon Core' and progress > .45:
                        threshold = 25 + int(35 * (progress - .45))
                        if ((cx * 17 + cy * 31 + dx * 7 + dy * 11) % 4 == 0):
                            threshold += 20
                    if difference >= threshold:
                        mask |= BITS[dy][dx]
                        colors.append(rgb)
            if mask:
                color = tuple(round(sum(c[k] for c in colors) / len(colors)) for k in range(3))
                # The calamity's whitish arms: mostly pale, unsaturated dots.
                pale = [c for c in colors if min(c) >= 95 and max(c) - min(c) <= 25]
                if name == 'Core Calamity' and len(pale) * 2 >= len(colors):
                    color = (225, 222, 232)
                # Preview the storm's dark marks in grey while retaining
                # the violet and other colors of its brighter details.
                elif name == 'Vortex' and max(color) < 65:
                    color = (170, 170, 170)
                elif max(color) < 55:
                    color = (130, 125, 145)
                elif name == 'Dungeon Core':
                    color = tuple(min(255, round(v * 1.7)) for v in color)
                elif name == 'Boss':
                    color = tuple(min(255, round(v * 1.8)) for v in color)
                line.append((chr(0x2800 + mask), '#%02x%02x%02x' % color))
            else:
                line.append((' ', ''))
        lines.append(line)
    return lines

window = pyglet.window.Window(WIDTH, HEIGHT, visible=False)
window.switch_to()
all_frames = {}
for name, method in [("Vortex", "draw_vortex_effect"), ("Dungeon Core", "draw_core_burst"),
                     ("Boss", "draw_boss_afterglow"), ("Core Calamity", "draw_core_calamity")]:
    capture = Capture(name)
    getattr(capture, method)((10, 9))
    all_frames[name] = capture.frames
window.close()
path = Path(__file__).resolve().parents[2] / "src/arlq/assets/effects/braille-frames-wide.json"
path.write_text(json.dumps(all_frames, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(path)
