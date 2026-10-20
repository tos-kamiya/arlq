"""Headless drawing check and a sample of sprites plus text fallbacks."""
from pathlib import Path
from types import SimpleNamespace
import pyglet

pyglet.options['headless'] = True
# Pyglet's Linux controller module requires X11; no controller in this check.
pyglet.input = SimpleNamespace(get_controllers=lambda: [])

from arlq import defs as d
from arlq.sprite_funcs import SPRITE_FILES, SpriteUI

ui = SpriteUI(scale=3)
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
# Walls north and south of the characters, a vertical wall, and a lone block
# to show the raised walls overlapping the cell to their north.
for x in range(4, 40):
    field[6][x] = field[9][x] = field[13][x] = d.CHAR_WALL
for y in range(4, 17):
    field[y][4] = field[y][39] = d.CHAR_WALL
field[11][20] = d.CHAR_WALL
# Rocks a defeated Golem raised beside the golem: walls drawn as rubble.
rock_cells = {(35, 10), (38, 10), (35, 12)}
for rx, ry in rock_cells:
    field[ry][rx] = d.CHAR_WALL
# Scattered caltrops beside the caltrop plant, to compare their colors.
for cx, cy in ((7, 10), (5, 12), (8, 12)):
    field[cy][cx] = d.CHAR_CALTROP
# Up and down stairs in view, and a pair explored outside the view.
for sx, sy, char in ((6, 7, d.CHAR_STAIRS_UP), (8, 7, d.CHAR_STAIRS_DOWN),
                     (1, 8, d.CHAR_STAIRS_UP), (2, 10, d.CHAR_STAIRS_DOWN)):
    field[sy][sx] = char
# A triggered Collapse: pits around its "?", and a pit explored outside the view.
for px, py in ((35, 14), (34, 15), (36, 15), (35, 16), (1, 12)):
    field[py][px] = d.CHAR_COLLAPSE
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
current = [[int(5 <= x <= 38 and 5 <= y <= 16) for x in range(d.FIELD_WIDTH)]
           for y in range(d.FIELD_HEIGHT)]
player = d.Player(10, 8, level=8, lp=d.LP_INIT)
entities = [d.Monster(13 + i * 3, 8, d.CHAR_TO_MONSTER_TRIBE[char])
            for i, char in enumerate(('a', 'A', 'b', 'c', 'd', 'D', 'C'))]
chest = d.Treasure(36, 8, 'D')
chest.unlocked = True
entities.append(chest)
# Companions in the room below, and Pegasus travelling with the player.
for i, char in enumerate(('n', 'o', 'p')):
    companion = d.Companion(14 + i * 4, 11, d.CHAR_TO_COMPANION_TRIBE[char])
    companion.revealed = True
    entities.append(companion)
player.companion = d.Companion(0, 0, d.CHAR_TO_COMPANION_TRIBE['p'])
# Stage 2 additions: rank 2 and rank 3 bison, and the fire drake.
entities += [d.Monster(25, 11, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=2),
             d.Monster(29, 11, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=3),
             d.Monster(33, 11, d.CHAR_TO_MONSTER_TRIBE['F']),
             d.Monster(37, 11, d.CHAR_TO_MONSTER_TRIBE['g'])]
# Elves in the bottom room: one not met yet, and one met (drawn darker).
for ex, char, met in ((8, 'H', False), (12, 'H', True), (16, 'I', False), (20, 'J', False),
                         (24, 'K', False), (28, 'L', False),
                         (32, 'S', False)):
    elf = d.Monster(ex, 15, d.CHAR_TO_MONSTER_TRIBE[char])
    elf.revealed, elf.met = True, met
    entities.append(elf)
# The rare Erebus belongs to Stage 4; shown here beside the Erebus.
entities += [d.Monster(8, 11, d.CHAR_TO_MONSTER_TRIBE['e']),
             d.Monster(11, 11, d.CHAR_TO_MONSTER_TRIBE['E']),
             d.Monster(6, 11, d.CHAR_TO_MONSTER_TRIBE['X'])]
entities.append(d.Collapse(35, 15))
ui.draw_stage(turn=0, player=player, entities=entities, field=field,
              cur_torched=current, torched=seen, known_types={'a', 'A', 'b', 'b2', 'b3', 'c', 'd', 'D', 'C', 'F', 'g', 'e', 'E', 'X'},
              show_entities=False, stage_num=1, message='Sprites + text fallback (c)',
              rock_cells=rock_cells)
ui.window.switch_to()
ui.window.clear()
ui.batch.draw()
pyglet.image.get_buffer_manager().get_color_buffer().save(
    str(Path(__file__).resolve().parent / 'preview-sprite-ui.png'))
assert set(ui._sprite_images) == set(SPRITE_FILES)
ui.quit()
