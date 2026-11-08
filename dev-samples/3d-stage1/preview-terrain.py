"""Headless sample of the sprite GUI's terrain, each drawn as in the game and
labelled, in three rows: the two floor tiles, a wall of marble columns, and
the up and down stairs; a golem rock, a pit, and the rocks fallen from a pit
on the floor above; the barrier (both checkerboard variants), the reduced
barrier shown near the player while Guardian lowers its damage, and the
Stage 6 tavern. The tavern image is laid over its two cells here, at the
game's scale, placed by tavern.json.

    PYTHONPATH=src .venv/bin/python dev-samples/3d-stage1/preview-terrain.py [--stage N]

Writes heroic/preview-terrain.jpg (with --stage, preview-terrain-stageN.jpg,
drawn in that stage's terrain look); needs ImageMagick's `convert`.
"""
from pathlib import Path
import argparse
import json
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
# Field row of each preview row, and (label, first column, last column) of
# each sample along it.
ROWS = [
    (4, [('FLOOR A / B', 2, 3), ('WALL (COLUMNS)', 6, 8), ('STAIRS UP', 11, 11),
         ('STAIRS DOWN', 14, 14)]),
    (7, [('GOLEM ROCK', 2, 2), ('PIT', 5, 5), ('FALLEN ROCKS', 8, 8)]),
    (10, [('BARRIER', 2, 3), ('BARRIER (GUARDIAN)', 6, 7), ('TAVERN', 10, 11)]),
]
LEFT, RIGHT = 1, 15
TAVERN_ROW, TAVERN_COLUMN = 10, 10
# Barrier cells drawn as when Guardian reduces their damage near the player.
REDUCED_BARRIERS = {(6, 10), (7, 10)}
TAVERN = Path(__file__).resolve().parents[2] / 'src' / 'arlq' / 'assets' / 'tavern'

ui = SpriteUI(scale=4)
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
decor = [[d.DECOR_NONE] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
for x in range(6, 9):
    field[4][x] = d.CHAR_WALL
field[4][11] = d.CHAR_STAIRS_UP
field[4][14] = d.CHAR_STAIRS_DOWN
field[7][2] = d.CHAR_GOLEM_WALL
field[7][5] = d.CHAR_COLLAPSE
decor[7][8] = d.DECOR_FALLEN_ROCKS
for x in (2, 3, 6, 7):
    field[10][x] = d.CHAR_BARRIER
ui._barrier_look = lambda x, y: 'reduced' if (x, y) in REDUCED_BARRIERS else 'light'
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
    placing = json.loads((TAVERN / 'tavern.json').read_text())
    tavern_left = round(ui._field_col_x(TAVERN_COLUMN))
    tavern_bottom = round((TAVERN_ROW + 1 + placing['under']) * cy)
    tavern_width = round(placing['cells'] * cx)
    tavern_height = round((placing['under'] + 1 + placing['overhang']) * cy)
    subprocess.run(['convert', str(full), '(', str(TAVERN / 'tavern.png'), '-resize',
                    '%dx%d!' % (tavern_width, tavern_height), ')', '-geometry',
                    '+%d+%d' % (tavern_left, tavern_bottom - tavern_height), '-composite',
                    str(full)], check=True)
    left = round(ui._field_col_x(LEFT))
    width, height = round((RIGHT - LEFT + 1) * cx), round(3 * cy)
    strips = []
    for index, (row, samples) in enumerate(ROWS):
        labels = []
        for label, first, last in samples:
            center = (ui._field_col_x(first) + ui._field_col_x(last) + cx) / 2 - left
            labels += ['-annotate', '+%d+0' % round(center - width / 2), label]
        strip = Path(work) / ('strip%d.png' % index)
        subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (
                            width, height, left, round((row - 1) * cy)),
                        '+repage', '(', '-size', '%dx52' % width, 'xc:#1e2230', '-fill',
                        'white', '-pointsize', '20', '-gravity', 'center', *labels, ')',
                        '-append', str(strip)], check=True)
        strips.append(str(strip))
    subprocess.run(['convert', *strips, '-append', '-quality', '90', str(OUT)], check=True)
ui.quit()
print(OUT)
