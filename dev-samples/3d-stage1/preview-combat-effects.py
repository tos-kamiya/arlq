"""Headless mock-up of the combat effects in the sprite GUI. The player stands
one cell in front of (south of) a monster, for each of a few monsters:

- top row, a win: the monster is beatable, and the slash crescent
  (src/arlq/assets/effects/slash.png from build-slash.py) is added over the monster's
  cell at the monster's scale (enlarged as the player's neighbour);
- middle row, a defeat: the monster is too strong, and the blood splash
  (src/arlq/assets/effects/splash.png from build-splash.py) is drawn over the player's
  cell at the characters' scale;
- bottom row, respawns: the swirling light column around the respawned player,
  around a monster respawned in view, and around one respawned on an explored
  cell outside the view (explored cells show their monsters).

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
EFFECTS_DIR = Path(__file__).resolve().parents[2] / 'src' / 'arlq' / 'assets' / 'effects'
X, ROW = 5, 4
LEFT, RIGHT, TOP, BOTTOM = X - 3, X + 3, ROW - 2, ROW + 2
MONSTERS = [('BISON', 'b'), ('GOLEM', 'g'), ('CHIMERA', 'c')]
# (label, player level, effect image, row of the cell it covers, its size,
# drawn additively)
EFFECTS = [('WIN', 60, 'slash.png', ROW, sprite_funcs.NEIGHBOR_SCALE, True),
           ('DEFEAT', 1, 'splash.png', ROW + 1, 1.0, False)]
# Respawn scenes: (name, respawned monster or None for the player, whether the
# monster's cell is in view). The player stands outside the crop for monsters.
RESPAWNS = [('PLAYER', None, True), ('BISON', 'b', True),
            ('CHIMERA OUT OF VIEW', 'c', False)]

ui = SpriteUI(scale=4)
ui._draw_lp_gauge = lambda *args: None
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]


def draw_scene(player, entities, cur_torched, respawn_glows=None):
    ui.draw_stage(turn=0, player=player, entities=entities, field=field,
                  cur_torched=cur_torched, torched=seen,
                  known_types={d.monster_type_key(e) for e in entities}, show_entities=False,
                  stage_num=1, message='', respawn_glows=respawn_glows)


def save_panel(work, label, name, key):
    """Save the drawn window's scene crop with its label; return its path."""
    ui.window.switch_to()
    ui.window.clear()
    ui.batch.draw()
    full = Path(work) / 'full.png'
    pyglet.image.get_buffer_manager().get_color_buffer().save(str(full))
    cell_x, cell_y = ui.cell_size_x, ui.cell_size_y
    left = round(ui._field_col_x(LEFT))
    width, height = round((RIGHT - LEFT + 1) * cell_x), round((BOTTOM - TOP + 1) * cell_y)
    out = Path(work) / ('panel-%s-%s.png' % (label, key))
    subprocess.run(['convert', str(full), '-crop', '%dx%d+%d+%d' % (width, height, left,
                                                                     round(TOP * cell_y)),
                    '+repage', '(', '-size', '%dx52' % width, 'xc:#1e2230', '-fill', 'white',
                    '-pointsize', '20', '-gravity', 'center', '-annotate', '+0+0',
                    '%s: %s' % (label, name), ')', '-append', str(out)], check=True)
    return str(out)


def respawn_panel(work, name, char, in_view):
    """Draw one respawn scene and return the labelled crop's path."""
    if char is None:
        player = d.Player(X, ROW, level=1, lp=d.LP_INIT)
        draw_scene(player, [], seen, {(X, ROW)})
    else:
        monster = d.Monster(X, ROW, d.CHAR_TO_MONSTER_TRIBE[char])
        player = d.Player(RIGHT + 4, ROW, level=60, lp=d.LP_INIT)
        view = [[int(in_view or abs(x - player.x) <= 3 and abs(y - player.y) <= 2)
                 for x in range(d.FIELD_WIDTH)] for y in range(d.FIELD_HEIGHT)]
        draw_scene(player, [monster], view, {(X, ROW)})
    return save_panel(work, 'RESPAWN', name, name.replace(' ', '-'))


def panel(work, label, level, image, row, size, additive, name, char):
    """Draw one scene with its effect and return the labelled crop's path."""
    monster = d.Monster(X, ROW, d.CHAR_TO_MONSTER_TRIBE[char])
    player = d.Player(X, ROW + 1, level=level, lp=d.LP_INIT)
    draw_scene(player, [monster], seen)
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
    out = save_panel(work, label, name, char)
    effect.delete()
    return out


with tempfile.TemporaryDirectory() as work:
    rows = []
    for label, level, filename, row, size, additive in EFFECTS:
        image = pyglet.image.load(str(EFFECTS_DIR / filename))
        panels = [panel(work, label, level, image, row, size, additive, name, char)
                  for name, char in MONSTERS]
        rows.append(Path(work) / ('row-%s.png' % label))
        subprocess.run(['convert', *panels, '+append', str(rows[-1])], check=True)
    panels = [respawn_panel(work, *scene) for scene in RESPAWNS]
    rows.append(Path(work) / 'row-RESPAWN.png')
    subprocess.run(['convert', *panels, '+append', str(rows[-1])], check=True)
    subprocess.run(['convert', *map(str, rows), '-append', '-quality', '90', str(OUT)],
                   check=True)
ui.quit()
print(OUT)
