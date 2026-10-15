"""Headless drawing check and a sample of sprites plus text fallbacks."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pyglet

pyglet.options['headless'] = True
# Pyglet's Linux controller module requires X11; no controller in this check.
pyglet.input = SimpleNamespace(get_controllers=lambda: [])

from arlq import defs as d
from arlq.sprite_funcs import SPRITE_FILES, SpriteUI

ui = SpriteUI(scale=3)
before = '--before' in sys.argv
if before:
    directory = Path(__file__).resolve().parent / 'sprites-before-outline'
    ui._sprite_images = {char: pyglet.image.load(str(directory / filename))
                         for char, filename in SPRITE_FILES.items()}
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
# Walls north and south of the characters, a vertical wall, and a lone block
# to show the raised walls overlapping the cell to their north.
for x in range(4, 40):
    field[6][x] = field[9][x] = d.CHAR_WALL
for y in range(4, 13):
    field[y][4] = field[y][39] = d.CHAR_WALL
field[11][20] = d.CHAR_WALL
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
current = [[int(5 <= x <= 38 and 5 <= y <= 12) for x in range(d.FIELD_WIDTH)]
           for y in range(d.FIELD_HEIGHT)]
player = d.Player(10, 8, level=8, lp=d.LP_INIT)
entities = [d.Monster(13 + i * 3, 8, d.CHAR_TO_MONSTER_TRIBE[char])
            for i, char in enumerate(('a', 'A', 'b', 'c', 'd', 'D', 'C'))]
chest = d.Treasure(36, 8, 'D')
chest.unlocked = True
entities.append(chest)
# Companions in the room below, and Ocular travelling with the player.
for i, char in enumerate(('n', 'o')):
    companion = d.Companion(14 + i * 4, 11, d.CHAR_TO_COMPANION_TRIBE[char])
    companion.revealed = True
    entities.append(companion)
player.companion = d.Companion(0, 0, d.CHAR_TO_COMPANION_TRIBE['o'])
# Stage 2 additions: rank 2 and rank 3 bison, and the fire drake.
entities += [d.Monster(23, 11, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=2),
             d.Monster(27, 11, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=3),
             d.Monster(33, 11, d.CHAR_TO_MONSTER_TRIBE['F']),
             d.Monster(37, 11, d.CHAR_TO_MONSTER_TRIBE['g'])]
ui.draw_stage(turn=0, player=player, entities=entities, field=field,
              cur_torched=current, torched=seen, known_types={'a', 'A', 'b', 'b2', 'b3', 'c', 'd', 'D', 'C', 'F', 'g'},
              show_entities=False, stage_num=1, message='Sprites + text fallback (c)')
ui.window.switch_to()
ui.window.clear()
ui.batch.draw()
pyglet.image.get_buffer_manager().get_color_buffer().save(
    str(Path(__file__).resolve().parent /
        ('preview-sprite-ui-before-outline.png' if before else 'preview-sprite-ui.png')))
assert set(ui._sprite_images) == set(SPRITE_FILES)
ui.quit()
