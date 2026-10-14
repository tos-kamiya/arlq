"""Sprite rendering must respect the shared information disclosure rules."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from arlq import defs as d, display
from arlq.pyglet_funcs import PygletUI
from arlq.sprite_funcs import SPRITE_FILES, SPRITE_REFERENCE_PIXELS, SpriteUI


@pytest.fixture
def sprite_ui(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._sprite_images = {char: SimpleNamespace(width=100, height=120) for char in SPRITE_FILES}
    ui._gray_images = dict.fromkeys(ui._sprite_images, SimpleNamespace(width=100, height=120))
    ui.map_mode = False
    ui.scale = 1
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = ui._sprite_group = None
    ui._drawables = []
    ui.text_calls = []
    ui.outlines = []
    monkeypatch.setattr(PygletUI, '_draw_field_text',
                        lambda self, *args: self.text_calls.append(args))
    monkeypatch.setattr(ui, '_draw_rect_outline', lambda *args: ui.outlines.append(args))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    return ui


def test_known_sprite_enlarges_around_cell_center_and_retains_color(sprite_ui):
    ui = sprite_ui
    color = (220, 82, 82)
    ui._draw_field_text((4, 5), 'b', color, True)
    sprite = ui._drawables[0]
    assert sprite.scale == pytest.approx(1.8 * 11 / SPRITE_REFERENCE_PIXELS)
    assert sprite.x + sprite.image.width * sprite.scale / 2 == pytest.approx(58.5)
    assert sprite.y + sprite.image.height * sprite.scale / 2 == pytest.approx(390)
    assert ui.outlines[0][-1] == color
    assert not ui.text_calls


@pytest.mark.parametrize('char', ('?', '&', '$', 'C'))
def test_unavailable_glyph_uses_original_text(sprite_ui, char):
    sprite_ui._draw_field_text((4, 5), char, (220, 82, 82), True)
    assert sprite_ui.text_calls[0][1] == char
    assert not sprite_ui._drawables


def test_unknown_amoeba_does_not_disclose_model(sprite_ui):
    entity = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['a'])
    glyphs = display.revealed_entity_glyphs(entity, set(), False, 8, None)
    for glyph in glyphs:
        sprite_ui._draw_field_text((glyph.x, glyph.y), glyph.char, (244, 190, 78))
    assert sprite_ui.text_calls[0][1] == '?'
    assert not sprite_ui._drawables


def test_map_uses_gray_texture_and_dim_sprite_remains_dim(sprite_ui):
    ui = sprite_ui
    ui.map_mode = True
    ui._draw_field_text((4, 5), 'a', ui._dim_color((226, 230, 238)))
    assert ui._drawables[0].image is ui._gray_images['a']
    assert ui._drawables[0].color == (128, 128, 128)


def test_bundled_sprites_cover_stage1_characters():
    directory = Path(d.__file__).parent / 'assets' / 'characters'
    assert {'@', 'a', 'A', 'b', 'c', 'd', 'D', d.CHAR_TREASURE} <= set(SPRITE_FILES)
    for filename in SPRITE_FILES.values():
        assert (directory / filename).is_file()


def test_unknown_mimic_uses_treasure_sprite(sprite_ui):
    entity = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['M'], mimic_boss_char='D')
    entity.active = True
    glyphs = display.revealed_entity_glyphs(entity, set(), False, 8, None)
    assert [glyph.char for glyph in glyphs] == [d.CHAR_TREASURE]
    sprite_ui._draw_field_text((4, 5), glyphs[0].char, (244, 190, 78))
    assert sprite_ui._drawables[0].image is sprite_ui._sprite_images[d.CHAR_TREASURE]


def test_larger_sprite_image_is_drawn_larger_at_the_same_scale(sprite_ui):
    ui = sprite_ui
    ui._sprite_images['a'] = SimpleNamespace(width=186, height=140)
    ui._sprite_images['D'] = SimpleNamespace(width=290, height=220)
    ui._draw_field_text((4, 5), 'a', (220, 82, 82), True)
    ui._draw_field_text((4, 5), 'D', (220, 82, 82), True)
    amoeba, dragon = ui._drawables
    assert dragon.scale == amoeba.scale
    assert amoeba.image.width * amoeba.scale == pytest.approx(19.8)
    assert dragon.image.width * dragon.scale > 1.5 * 19.8
    assert dragon.x + dragon.image.width * dragon.scale / 2 == pytest.approx(58.5)
    assert dragon.y + dragon.image.height * dragon.scale / 2 == pytest.approx(390)
