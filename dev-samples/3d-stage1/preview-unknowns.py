"""Headless sample of the sprite GUI's unidentified symbols: an unknown monster
`?`, companion `!` and elf `&`, each standing in its light pillar, then for
comparison an identified companion, drawn as in the game and labelled.

    PYTHONPATH=src .venv/bin/python dev-samples/3d-stage1/preview-unknowns.py

Writes heroic/preview-unknowns.jpg; needs ImageMagick's `convert`.
"""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import pyglet

pyglet.options['headless'] = True
# Pyglet's Linux controller module requires X11; no controller in this check.
pyglet.input = SimpleNamespace(get_controllers=lambda: [])

from arlq import defs as d
from arlq.sprite_funcs import SpriteUI

OUT = Path(__file__).resolve().parent / 'heroic' / 'preview-unknowns.jpg'
ROW = 5
LEFT, RIGHT, TOP, BOTTOM = 1, 18, ROW - 3, ROW + 1

monster = d.Monster(3, ROW, d.CHAR_TO_MONSTER_TRIBE['b'])
companion = d.Companion(7, ROW, d.CHAR_TO_COMPANION_TRIBE['n'])
elf = d.Elf(11, ROW, d.CHAR_TO_MONSTER_TRIBE['S'])
known = d.Companion(16, ROW, d.CHAR_TO_COMPANION_TRIBE['n'])
known.revealed = True
SAMPLES = [('? MONSTER', monster), ('! COMPANION', companion), ('& ELF', elf),
           ('KNOWN COMPANION', known)]

ui = SpriteUI(scale=4)
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
# The player stands outside the cropped area.
player = d.Player(2, d.FIELD_HEIGHT - 2, level=8, lp=d.LP_INIT)
ui.draw_stage(turn=0, player=player, entities=[entity for _, entity in SAMPLES], field=field,
              cur_torched=seen, torched=seen, known_types=set(), show_entities=False,
              stage_num=3, message='')
ui.window.switch_to()
ui.window.clear()
ui.batch.draw()
with tempfile.TemporaryDirectory() as work:
    full = Path(work) / 'full.png'
    pyglet.image.get_buffer_manager().get_color_buffer().save(str(full))
    cx, cy = ui.cell_size_x, ui.cell_size_y
    left = round(ui._field_col_x(LEFT))
    width, height = round((RIGHT - LEFT + 1) * cx), round((BOTTOM - TOP + 1) * cy)
    labels = []
    for label, entity in SAMPLES:
        center = ui._field_col_x(entity.x) + cx / 2 - left
        labels += ['-annotate', '+%d+0' % round(center - width / 2), label]
    subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (width, height, left,
                                                                     round(TOP * cy)),
                    '+repage', '(', '-size', '%dx52' % width, 'xc:#1e2230', '-fill', 'white',
                    '-pointsize', '20', '-gravity', 'center', *labels, ')', '-append',
                    '-quality', '90', str(OUT)], check=True)
ui.quit()
print(OUT)
