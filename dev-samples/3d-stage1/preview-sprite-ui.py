"""Headless drawing check and a sample of sprites plus text fallbacks."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pyglet

pyglet.options['headless'] = True
# Pyglet's Linux controller module requires X11; no controller in this check.
pyglet.input = SimpleNamespace(get_controllers=lambda: [])

from arlq import defs as d
from arlq.sprite_funcs import SpriteUI

ui = SpriteUI(scale=3)
before = '--before' in sys.argv
if before:
    from arlq.sprite_funcs import SPRITE_FILES

    directory = Path(__file__).resolve().parent / 'sprites-before-outline'
    ui._sprite_images = {char: pyglet.image.load(str(directory / filename))
                         for char, filename in SPRITE_FILES.items()}
field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
current = [[int(5 <= x <= 36 and 5 <= y <= 12) for x in range(d.FIELD_WIDTH)]
           for y in range(d.FIELD_HEIGHT)]
player = d.Player(10, 8, level=8, lp=d.LP_INIT)
entities = [d.Monster(13 + i * 3, 8, d.CHAR_TO_MONSTER_TRIBE[char])
            for i, char in enumerate(('a', 'A', 'b', 'd', 'D', 'c'))]
chest = d.Treasure(34, 8, 'D')
chest.unlocked = True
entities.append(chest)
ui.draw_stage(turn=0, player=player, entities=entities, field=field,
              cur_torched=current, torched=seen, known_types={'a', 'A', 'b', 'd', 'D', 'c'},
              show_entities=False, stage_num=1, message='Sprites + text fallback (c)')
ui.window.switch_to()
ui.window.clear()
ui.batch.draw()
pyglet.image.get_buffer_manager().get_color_buffer().save(
    str(Path(__file__).resolve().parent /
        ('preview-sprite-ui-before-outline.png' if before else 'preview-sprite-ui.png')))
assert set(ui._sprite_images) == {'@', 'a', 'A', 'b', 'd', 'D', 'T'}
ui.quit()
