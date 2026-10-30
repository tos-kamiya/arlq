"""Headless mock-up of the combat effects in the sprite GUI. The player stands
one cell in front of (south of) a monster, for each of a few monsters:

- top row, a win: the monster is beatable, and the slash crescent
  (heroic/effect-slash.png from build-slash.py) is added over the monster's
  cell at the monster's scale (enlarged as the player's neighbour);
- bottom row, a defeat: the monster is too strong, and the blood splash
  (heroic/effect-splash.png from build-splash.py) is drawn over the player's
  cell at the characters' scale.

The player's LP gauge is left out, as it would cover the monster.

    PYTHONPATH=src .venv/bin/python dev-samples/3d-stage1/preview-combat-effects.py

Writes heroic/preview-combat-effects.jpg; needs ImageMagick's `convert`.
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
from arlq import sprite_funcs
from arlq.sprite_funcs import SpriteUI

HEROIC = Path(__file__).resolve().parent / 'heroic'
OUT = HEROIC / 'preview-combat-effects.jpg'
X, ROW = 5, 4
LEFT, RIGHT, TOP, BOTTOM = X - 3, X + 3, ROW - 2, ROW + 2
MONSTERS = [('BISON', 'b'), ('GOLEM', 'g'), ('CHIMERA', 'c')]
# (label, player level, effect image, row of the cell it covers, its size,
# drawn additively)
EFFECTS = [('WIN', 60, 'effect-slash.png', ROW, sprite_funcs.NEIGHBOR_SCALE, True),
           ('DEFEAT', 1, 'effect-splash.png', ROW + 1, 1.0, False)]

ui = SpriteUI(scale=4)
ui._draw_lp_gauge = lambda *args: None
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]


def panel(work, label, level, image, row, size, additive, name, char):
    """Draw one scene with its effect and return the labelled crop's path."""
    monster = d.Monster(X, ROW, d.CHAR_TO_MONSTER_TRIBE[char])
    player = d.Player(X, ROW + 1, level=level, lp=d.LP_INIT)
    ui.draw_stage(turn=0, player=player, entities=[monster], field=field,
                  cur_torched=seen, torched=seen,
                  known_types={d.monster_type_key(monster)}, show_entities=False,
                  stage_num=1, message='')
    # Feet at the cell centre, scaled like a character sprite there.
    padding = max(1, round(ui.scale))
    scale = (size * 1.8 * max(1, ui._sprite_unit() - 2 * padding)
             / sprite_funcs.SPRITE_REFERENCE_PIXELS)
    cx = ui._field_col_x(X) + ui.cell_size_x / 2
    cy = (row + 0.5) * ui.cell_size_y
    blend = {'blend_src': pyglet.gl.GL_SRC_ALPHA, 'blend_dest': pyglet.gl.GL_ONE} if additive else {}
    effect = pyglet.sprite.Sprite(
        image, x=cx - image.width * scale / 2,
        y=ui.window_height - cy - (image.height / 2
                                   - sprite_funcs.SPRITE_GROUND_OFFSET_PIXELS) * scale,
        batch=ui.batch, group=pyglet.graphics.Group(order=100000), **blend)
    effect.scale = scale
    ui.window.switch_to()
    ui.window.clear()
    ui.batch.draw()
    effect.delete()
    full = Path(work) / 'full.png'
    pyglet.image.get_buffer_manager().get_color_buffer().save(str(full))
    cell_x, cell_y = ui.cell_size_x, ui.cell_size_y
    left = round(ui._field_col_x(LEFT))
    width, height = round((RIGHT - LEFT + 1) * cell_x), round((BOTTOM - TOP + 1) * cell_y)
    out = Path(work) / ('panel-%s-%s.png' % (label, char))
    subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (width, height, left,
                                                                     round(TOP * cell_y)),
                    '+repage', '(', '-size', '%dx52' % width, 'xc:#1e2230', '-fill', 'white',
                    '-pointsize', '20', '-gravity', 'center', '-annotate', '+0+0',
                    '%s: %s' % (label, name), ')', '-append', str(out)], check=True)
    return str(out)


with tempfile.TemporaryDirectory() as work:
    rows = []
    for label, level, filename, row, size, additive in EFFECTS:
        image = pyglet.image.load(str(HEROIC / filename))
        panels = [panel(work, label, level, image, row, size, additive, name, char)
                  for name, char in MONSTERS]
        rows.append(Path(work) / ('row-%s.png' % label))
        subprocess.run(['convert', *panels, '+append', str(rows[-1])], check=True)
    subprocess.run(['convert', *map(str, rows), '-append', '-quality', '90', str(OUT)],
                   check=True)
ui.quit()
print(OUT)
