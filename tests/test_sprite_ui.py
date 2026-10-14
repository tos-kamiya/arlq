"""Sprite rendering must respect the shared information disclosure rules."""
from types import SimpleNamespace

import pytest

from arlq import defs as d, display
from arlq.pyglet_funcs import PygletUI
from arlq.sprite_funcs import SpriteUI


@pytest.fixture
def sprite_ui(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    image = SimpleNamespace(width=100, height=120)
    ui._sprite_images = dict.fromkeys(('@', 'a', 'A', 'b', 'd'), image)
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
    assert sprite.image.width * sprite.scale == pytest.approx(19.8)
    assert sprite.image.height * sprite.scale == pytest.approx(23.76)
    assert sprite.x + sprite.image.width * sprite.scale / 2 == pytest.approx(58.5)
    assert sprite.y + sprite.image.height * sprite.scale / 2 == pytest.approx(390)
    assert ui.outlines[0][-1] == color
    assert not ui.text_calls


@pytest.mark.parametrize('char', ('?', '&', '$', 'c'))
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
