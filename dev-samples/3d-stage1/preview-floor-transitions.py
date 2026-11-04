"""Headless sample of the sprite GUI's stills between floors
(SpriteUI.draw_floor_transition): down and up stairs, falling
through a pit and climbing out of one, each labelled.

    PYTHONPATH=src .venv/bin/python dev-samples/3d-stage1/preview-floor-transitions.py [OUT]

Writes heroic/preview-floor-transitions.jpg (or OUT); needs ImageMagick's `convert`.
"""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import pyglet

pyglet.options['headless'] = True
# Pyglet's Linux controller module requires X11; no controller in this check.
pyglet.input = SimpleNamespace(get_controllers=lambda: [])

from arlq import defs as d
from arlq import sprite_funcs
from arlq.sprite_funcs import SpriteUI

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parent / 'heroic' / 'preview-floor-transitions.jpg')
SCENES = [('STAIRS DOWN', 'down'), ('STAIRS UP', 'up'), ('FALL', 'fall'),
          ('CLIMB', 'climb')]
# Crop around the field's centre, in cells.
HALF_W, HALF_H = 3, 3

ui = SpriteUI(scale=4)
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
player = d.Player(d.FIELD_WIDTH // 2, d.FIELD_HEIGHT // 2, level=8, lp=d.LP_INIT)
ui.draw_stage(turn=0, player=player, entities=[player], field=field, cur_torched=seen,
              torched=seen, known_types=set(), show_entities=False, stage_num=1, message='')
ui.combat_effect_seconds = 0.01
sprite_funcs.time.sleep = lambda seconds: None

with tempfile.TemporaryDirectory() as work:
    panels = []

    def capture(label):
        full = Path(work) / 'full.png'
        pyglet.image.get_buffer_manager().get_color_buffer().save(str(full))
        width, height = 2 * HALF_W * ui.cell_size_x, 2 * HALF_H * ui.cell_size_y
        left = round(ui.field_pixel_width / 2 - width / 2)
        top = round(d.FIELD_HEIGHT * ui.cell_size_y / 2 - height / 2)
        out = Path(work) / ('panel-%d.png' % len(panels))
        subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (width, height, left, top),
                        '+repage', '(', '-size', '%dx40' % width, 'xc:#1e2230', '-fill', 'white',
                        '-pointsize', '18', '-gravity', 'center', '-annotate', '+0+0', label,
                        ')', '-append', str(out)], check=True)
        panels.append(str(out))

    for label, kind in SCENES:
        ui._flip = lambda label=label: (ui.window.switch_to(), ui.window.clear(),
                                        ui.batch.draw(), capture(label))
        ui.draw_floor_transition(kind, player, (player.x, player.y))
    subprocess.run(['convert', *panels, '+append', '-quality', '90', str(OUT)], check=True)
print(OUT)
