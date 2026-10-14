"""Sprite rendering must respect the shared information disclosure rules."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from arlq import defs as d, display, sprite_funcs
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
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui.text_calls = []
    ui.outlines = []
    monkeypatch.setattr(PygletUI, '_draw_field_text',
                        lambda self, *args: self.text_calls.append(args))
    monkeypatch.setattr(ui, '_draw_ground_disc', lambda *args: ui.outlines.append(args))
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
    # The feet, a fixed offset below the image centre, rest on the cell centre.
    feet = sprite.y + (sprite.image.height / 2 - sprite_funcs.SPRITE_GROUND_OFFSET_PIXELS) * sprite.scale
    assert feet == pytest.approx(390)
    assert ui.outlines[0][3:] == (color, None)
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
    feet = dragon.y + (dragon.image.height / 2 - sprite_funcs.SPRITE_GROUND_OFFSET_PIXELS) * dragon.scale
    assert feet == pytest.approx(390)



def test_ground_disc_is_tinted_ellipse_fading_outward(monkeypatch):
    image = sprite_funcs.ground_disc_image()
    data = image.get_data('RGBA', image.width * 4)
    alpha = lambda col, row: data[(row * image.width + col) * 4 + 3]
    mid = image.width // 2
    assert alpha(mid, mid) > alpha(mid + mid // 2, mid) > alpha(image.width - 1, mid)
    assert alpha(0, 0) == 0
    ui = SpriteUI.__new__(SpriteUI)
    ui.window_height = 500
    ui.batch = None
    ui._disc_image, ui._disc_group = image, 'disc'
    ui._drawables = []
    ui._display_color = lambda color: color
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    ui._draw_ground_disc(50, 100, 10, (82, 140, 220))
    disc = ui._drawables[0]
    assert disc.group == 'disc' and disc.color == (82, 140, 220)
    assert disc.image.width * disc.scale_x == pytest.approx(20)
    assert disc.image.height * disc.scale_y == pytest.approx(20 * sprite_funcs.GROUND_DISC_FLATTEN)
    assert disc.x == 40



@pytest.mark.parametrize('lp, tone', [(d.LP_WARNING_THRESHOLD, 'yellow'),
                                      (d.LP_LOW_THRESHOLD, 'red')])
def test_low_lp_colors_player_disc_instead_of_cell(sprite_ui, monkeypatch, lp, tone):
    ui = sprite_ui
    rects = []
    monkeypatch.setattr(ui, '_draw_rect', lambda *args: rects.append(args))
    player = d.Player(4, 5, level=8, lp=lp)
    ui._draw_player((4, 5), player)
    assert not rects
    assert ui._drawables[0].image is ui._sprite_images['@']
    assert ui.outlines[0][3:] == (ui._tone_color(tone), None)



@pytest.mark.parametrize('lp, tone', [(d.LP_INIT, 'default'), (d.LP_LOW_THRESHOLD, 'red')])
def test_poison_turns_upper_right_of_player_disc_purple(sprite_ui, lp, tone):
    ui = sprite_ui
    player = d.Player(4, 5, level=8, lp=lp)
    player.item = d.ITEM_POISONED
    ui._draw_player((4, 5), player)
    assert ui._drawables[0].image is ui._sprite_images['@']
    assert ui.outlines[0][3:] == (ui._tone_color(tone), ui._tone_color('magenta'))


def test_disc_halves_split_on_the_diagonal(monkeypatch):
    lower, upper = (sprite_funcs.ground_disc_image(half)
                    for half in ('lower-left', 'upper-right'))
    size = lower.width
    alpha = lambda image, col, row: image.get_data('RGBA', size * 4)[(row * size + col) * 4 + 3]
    q = size // 4
    # Image rows run bottom to top: (3q, 3q) is upper right, (q, q) lower left.
    assert alpha(upper, 3 * q, 3 * q) > 0 and alpha(lower, 3 * q, 3 * q) == 0
    assert alpha(lower, q, q) > 0 and alpha(upper, q, q) == 0
    ui = SpriteUI.__new__(SpriteUI)
    ui.window_height = 500
    ui.batch = None
    ui._disc_halves, ui._disc_group = (lower, upper), 'disc'
    ui._drawables = []
    ui._display_color = lambda color: color
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    ui._draw_ground_disc(50, 100, 10, (230, 230, 230), (200, 80, 200))
    assert [(disc.image, disc.color) for disc in ui._drawables] == [
        (lower, (230, 230, 230)), (upper, (200, 80, 200))]


def test_wall_rises_into_north_cell_between_character_rows(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._wall_images = None  # plain-shape fallback when the parts are missing
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    floors = []
    monkeypatch.setattr(PygletUI, '_draw_tile',
                        lambda self, x, y, color, *args: floors.append((x, y, color)))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs))
    field = [[d.CHAR_FLOOR] * 3 for _ in range(3)]
    field[1][1] = d.CHAR_WALL
    ui._draw_tile(1, 1, sprite_funcs.VISIBLE_WALL, field, lambda x, y: True)
    assert floors == [(1, 1, sprite_funcs.VISIBLE_FLOOR)]
    top, front = ui._drawables
    # The top face starts above the wall's own cell, inside the cell to its north.
    overhang = sprite_funcs.WALL_OVERHANG * ui.cell_size_y
    assert top.args[1] + top.args[3] == pytest.approx(500 - (20 - overhang))
    # The front face reaches down to the wall cell's south edge.
    assert front.args[1] == pytest.approx(500 - 40 - 1)
    assert front.args[1] + front.args[3] == pytest.approx(500 - (40 - overhang))
    order = lambda y, layer: ui._row_group(y, layer).order
    assert order(0, 'sprite') < top.group.order < order(1, 'sprite')



def test_column_wall_links_only_toward_discovered_wall_neighbors(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    ui._wall_images = {part: SimpleNamespace(width=26, height=50, part=part)
                       for part in sprite_funcs.WALL_PARTS}
    monkeypatch.setattr(PygletUI, '_draw_tile', lambda *args: None)
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    field = [[d.CHAR_FLOOR] * 3, [d.CHAR_WALL] * 3, [d.CHAR_FLOOR] * 3]
    # The east neighbour is unexplored, so no link reaches toward it.
    ui._draw_tile(1, 1, sprite_funcs.VISIBLE_WALL, field, lambda x, y: x != 2)
    parts = [piece.image.part for piece in ui._drawables]
    assert parts == ['link-west', 'column']
    column = ui._drawables[-1]
    assert column.image.width * column.scale_x == 14
    assert column.image.height * column.scale_y == pytest.approx(
        (1 + sprite_funcs.WALL_OVERHANG) * 20)
    assert column.y == 500 - 40
    assert ui._drawables[0].group.order < column.group.order < ui._row_group(1, 'sprite').order
