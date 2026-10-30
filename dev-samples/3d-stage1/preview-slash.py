"""Headless mock-up of the sword slash effect: the player stands one cell in
front of (south of) a beatable monster, and the slash arc (heroic/effect-slash.png
from build-slash.py) is added over the monster's cell, at the same scale as
the monster, which is enlarged as the player's neighbour. The player's LP
gauge is left out, as it would cover the slash.

    PYTHONPATH=src .venv/bin/python dev-samples/3d-stage1/preview-slash.py

Writes heroic/preview-slash.jpg (one panel per monster); needs ImageMagick's
`convert`.
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
OUT = HEROIC / 'preview-slash.jpg'
X, ROW = 5, 4
LEFT, RIGHT, TOP, BOTTOM = X - 3, X + 3, ROW - 2, ROW + 2
MONSTERS = [('BISON', 'b'), ('GOLEM', 'g'), ('CHIMERA', 'c')]

ui = SpriteUI(scale=4)
# The player's LP gauge floats over the monster just north of it; leave it
# out here so the slash itself can be judged.
ui._draw_lp_gauge = lambda *args: None
slash = pyglet.image.load(str(HEROIC / 'effect-slash.png'))
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
with tempfile.TemporaryDirectory() as work:
    panels = []
    for name, char in MONSTERS:
        monster = d.Monster(X, ROW, d.CHAR_TO_MONSTER_TRIBE[char])
        player = d.Player(X, ROW + 1, level=60, lp=d.LP_INIT)
        ui.draw_stage(turn=0, player=player, entities=[monster], field=field,
                      cur_torched=seen, torched=seen,
                      known_types={d.monster_type_key(monster)}, show_entities=False,
                      stage_num=1, message='')
        # The slash goes where the monster's sprite went: feet at the cell
        # centre, scaled like it (neighbours of the player are enlarged).
        size = sprite_funcs.NEIGHBOR_SCALE
        padding = max(1, round(ui.scale))
        scale = (size * 1.8 * max(1, ui._sprite_unit() - 2 * padding)
                 / sprite_funcs.SPRITE_REFERENCE_PIXELS)
        cx = ui._field_col_x(X) + ui.cell_size_x / 2
        cy = (ROW + 0.5) * ui.cell_size_y
        effect = pyglet.sprite.Sprite(
            slash, x=cx - slash.width * scale / 2,
            y=ui.window_height - cy - (slash.height / 2
                                       - sprite_funcs.SPRITE_GROUND_OFFSET_PIXELS) * scale,
            blend_src=pyglet.gl.GL_SRC_ALPHA, blend_dest=pyglet.gl.GL_ONE,
            batch=ui.batch, group=pyglet.graphics.Group(order=100000))
        effect.scale = scale
        ui.window.switch_to()
        ui.window.clear()
        ui.batch.draw()
        effect.delete()
        full = Path(work) / ('full-%s.png' % char)
        pyglet.image.get_buffer_manager().get_color_buffer().save(str(full))
        cx, cy = ui.cell_size_x, ui.cell_size_y
        left = round(ui._field_col_x(LEFT))
        width, height = round((RIGHT - LEFT + 1) * cx), round((BOTTOM - TOP + 1) * cy)
        panel = Path(work) / ('panel-%s.png' % char)
        subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (width, height, left,
                                                                         round(TOP * cy)),
                        '+repage', '(', '-size', '%dx52' % width, 'xc:#1e2230', '-fill',
                        'white', '-pointsize', '20', '-gravity', 'center', '-annotate',
                        '+0+0', name, ')', '-append', str(panel)], check=True)
        panels.append(str(panel))
    subprocess.run(['convert', *panels, '+append', '-quality', '90', str(OUT)], check=True)
ui.quit()
print(OUT)
