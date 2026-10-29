"""Headless sample of the sprite GUI's terrain: the two floor tiles, a wall
of marble columns, a golem rock, a pit, the rocks fallen from a pit on
the floor above, and the up and down stairs, each drawn as in the game and
labelled.

    PYTHONPATH=src .venv/bin/python dev-samples/3d-stage1/preview-terrain.py [--stage N]

Writes heroic/preview-terrain.jpg (with --stage, preview-terrain-stageN.jpg,
drawn in that stage's terrain look); needs ImageMagick's `convert`.
"""
from pathlib import Path
import argparse
from types import SimpleNamespace
import subprocess
import tempfile
import pyglet

pyglet.options['headless'] = True
# Pyglet's Linux controller module requires X11; no controller in this check.
pyglet.input = SimpleNamespace(get_controllers=lambda: [])

from arlq import defs as d
from arlq.sprite_funcs import SpriteUI

parser = argparse.ArgumentParser()
parser.add_argument('--stage', type=int)
STAGE = parser.parse_args().stage
OUT = Path(__file__).resolve().parent / 'heroic' / (
    'preview-terrain.jpg' if STAGE is None else 'preview-terrain-stage%d.jpg' % STAGE)
ROW = 4
# (label, first column, last column) of each sample along ROW.
SAMPLES = [('FLOOR A / B', 2, 3), ('WALL (COLUMNS)', 6, 8), ('GOLEM ROCK', 11, 11),
           ('PIT', 14, 14), ('FALLEN ROCKS', 17, 17), ('STAIRS UP', 20, 20),
           ('STAIRS DOWN', 23, 23)]
LEFT, RIGHT, TOP, BOTTOM = 1, 25, ROW - 1, ROW + 1

ui = SpriteUI(scale=4)
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
decor = [[d.DECOR_NONE] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
for x in range(6, 9):
    field[ROW][x] = d.CHAR_WALL
field[ROW][11] = d.CHAR_GOLEM_WALL
field[ROW][14] = d.CHAR_COLLAPSE
decor[ROW][17] = d.DECOR_FALLEN_ROCKS
field[ROW][20] = d.CHAR_STAIRS_UP
field[ROW][23] = d.CHAR_STAIRS_DOWN
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
# The player stands outside the cropped area.
player = d.Player(2, d.FIELD_HEIGHT - 2, level=8, lp=d.LP_INIT)
ui.draw_stage(turn=0, player=player, entities=[], field=field, cur_torched=seen,
              torched=seen, known_types=set(), show_entities=False, stage_num=STAGE or 1,
              message='', decor=decor)
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
    for label, first, last in SAMPLES:
        center = (ui._field_col_x(first) + ui._field_col_x(last) + cx) / 2 - left
        labels += ['-annotate', '+%d+0' % round(center - width / 2), label]
    subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (width, height, left,
                                                                     round(TOP * cy)),
                    '+repage', '(', '-size', '%dx52' % width, 'xc:#1e2230', '-fill', 'white',
                    '-pointsize', '20', '-gravity', 'center', *labels, ')', '-append',
                    '-quality', '90', str(OUT)], check=True)
ui.quit()
print(OUT)
