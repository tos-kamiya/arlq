"""Sprite rendering must respect the shared information disclosure rules."""
from pathlib import Path
from types import SimpleNamespace

import pyglet
import pytest

from arlq import defs as d, display, sprite_funcs
from arlq.pyglet_funcs import PygletUI
from arlq.sprite_funcs import SPRITE_FILES, SPRITE_REFERENCE_PIXELS, SpriteUI


@pytest.fixture
def sprite_ui(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._sprite_images = {char: SimpleNamespace(width=100, height=120) for char in SPRITE_FILES}
    ui._gray_images = dict.fromkeys(ui._sprite_images, SimpleNamespace(width=100, height=120))
    ui._mark_images = {mark: SimpleNamespace(width=30, height=40) for mark in ("'", '"')}
    ui._sprite_cells = {}
    ui._pillar_images = {side: SimpleNamespace(width=64, height=96) for side in ('back', 'front')}
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


@pytest.mark.parametrize('char', ('?', '&', '$', '%'))
def test_unavailable_glyph_uses_original_text(sprite_ui, char):
    sprite_ui._draw_field_text((4, 5), char, (220, 82, 82), True)
    assert sprite_ui.text_calls[0][1] == char
    # Raised a little so it stays inside its cell.
    assert sprite_ui.text_calls[0][0] == (4, pytest.approx(5 - sprite_funcs.FIELD_TEXT_RAISE))
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


@pytest.mark.parametrize('level, outline', [(8, ('red', None)), (40, ('blue', 'yellow'))])
def test_beatable_boss_disc_is_blue_with_yellow_upper_right(sprite_ui, level, outline):
    ui = sprite_ui
    boss = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['D'])
    for glyph in display.revealed_entity_glyphs(boss, {'D'}, False, level, None):
        ui._draw_field_text((glyph.x, glyph.y), glyph.char, ui._tone_color(glyph.tone))
    base, upper = outline
    assert ui.outlines[0][3:] == (ui._tone_color(base),
                                  upper and ui._tone_color(upper))


def test_treasure_disc_stays_yellow(sprite_ui):
    ui = sprite_ui
    ui._draw_field_text((4, 5), d.CHAR_TREASURE, ui._tone_color('yellow'))
    assert ui.outlines[0][3:] == (ui._tone_color('yellow'), None)


@pytest.mark.parametrize('empowered, mark', [(2, "'"), (3, '"')])
def test_rank_mark_floats_tinted_at_sprite_upper_right(sprite_ui, empowered, mark):
    ui = sprite_ui
    ui._display_color = lambda color: color
    bison = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=empowered)
    key = d.monster_type_key(bison)
    for glyph in display.revealed_entity_glyphs(bison, {key}, False, 8, None):
        ui._draw_field_text((glyph.x, glyph.y), glyph.char, ui._tone_color(glyph.tone))
    sprite, badge = ui._drawables
    assert sprite.image is ui._sprite_images['b']
    assert badge.image is ui._mark_images[mark]
    assert badge.color == ui._tone_color('red')
    # Up and to the right of the bison's ground point, not in the next cell.
    feet_x, feet_y = 58.5, 500 - 110
    centre_x = badge.x + badge.image.width * badge.scale / 2
    centre_y = badge.y + badge.image.height * badge.scale / 2
    assert feet_x < centre_x < feet_x + ui.cell_size_x
    assert centre_y > feet_y
    assert not ui.text_calls


def test_rank_mark_without_sprite_stays_text(sprite_ui):
    sprite_ui._sprite_images.pop('g')
    sprite_ui._draw_field_text((4, 5), 'g', (220, 82, 82), True)
    sprite_ui._draw_field_text((5, 5), "'", (220, 82, 82), True)
    assert [call[1] for call in sprite_ui.text_calls] == ['g', "'"]
    assert not sprite_ui._drawables


def test_companion_stands_in_green_light_pillar(sprite_ui):
    ui = sprite_ui
    ui._display_color = lambda color: color
    ui._draw_field_text((4, 5), 'n', ui._tone_color('companion'), True)
    sprite, back, front = ui._drawables
    assert sprite.image is ui._sprite_images['n']
    assert (back.image, front.image) == (ui._pillar_images['back'], ui._pillar_images['front'])
    assert back.color == front.color == ui._tone_color('companion')
    assert back.group.order < sprite.group.order < front.group.order
    ui._drawables.clear()
    ui._draw_field_text((4, 5), 'b', ui._tone_color('blue'), True)
    assert len(ui._drawables) == 1


@pytest.mark.parametrize('met', (False, True))
def test_met_elf_sprite_and_disc_are_darker(sprite_ui, met):
    ui = sprite_ui
    elf = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['H'])
    elf.revealed, elf.met = True, met
    for glyph in display.revealed_entity_glyphs(elf, {'H'}, False, 8, None, stage_num=3):
        ui._draw_field_text((glyph.x, glyph.y), glyph.char, ui._tone_color(glyph.tone), glyph.bold)
    sprite = ui._drawables[0]
    white = ui._tone_color('default')
    shade = sprite_funcs.MET_ELF_SHADE if met else 1.0
    assert sprite.image is ui._sprite_images['H']
    assert getattr(sprite, 'color', (255, 255, 255)) == ((round(255 * shade),) * 3)
    assert ui.outlines[0][3] == tuple(round(c * shade) for c in white)


@pytest.mark.parametrize('pos, size', [((4, 5), sprite_funcs.NEIGHBOR_SCALE), ((3, 6), sprite_funcs.NEIGHBOR_SCALE),
                                       ((5, 5), 1.0), ((4, 4), 1.0)])
def test_character_next_to_player_is_enlarged_with_disc_unchanged(sprite_ui, pos, size):
    ui = sprite_ui
    ui._player_cell = (4, 6)
    ui._draw_field_text(pos, 'b', ui._tone_color('blue'), True)
    sprite = ui._drawables[0]
    assert sprite.scale == pytest.approx(size * 1.8 * 11 / SPRITE_REFERENCE_PIXELS)
    assert ui.outlines[0][2] == pytest.approx(sprite_funcs.GROUND_DISC_RADIUS * ui.cell_size_x)


def test_follower_next_to_player_keeps_its_size(sprite_ui):
    ui = sprite_ui
    ui._player_cell = (4, 6)
    ui._draw_follower((4, 5), 'J')
    assert ui._drawables[0].image is ui._sprite_images['J']
    assert ui._drawables[0].scale == pytest.approx(1.8 * 11 / SPRITE_REFERENCE_PIXELS)


def test_rank_mark_grows_with_an_enlarged_neighbor(sprite_ui):
    ui = sprite_ui
    ui._display_color = lambda color: color
    ui._player_cell = (4, 6)
    bison = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=2)
    for glyph in display.revealed_entity_glyphs(bison, {'b2'}, False, 8, None):
        ui._draw_field_text((glyph.x, glyph.y), glyph.char, ui._tone_color(glyph.tone))
    sprite, badge = ui._drawables
    assert badge.scale == pytest.approx(sprite.scale)


def _strength_column_ui(monkeypatch, known_types):
    ui = SpriteUI.__new__(SpriteUI)
    ui._sprite_images = {char: SimpleNamespace(width=100, height=120) for char in SPRITE_FILES}
    ui._mark_images = {mark: SimpleNamespace(width=30, height=40) for mark in ("'", '"')}
    ui._known_types = known_types
    ui.map_mode = False
    ui.scale = 1
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.field_pixel_width, ui.strength_column_width, ui.strength_column_padding = 500, 60, 4
    ui.window_height = 500
    ui.batch = None
    ui._overlay_group = 'overlay'
    ui._drawables = []
    ui._display_color = lambda color: color
    texts = []
    monkeypatch.setattr(ui, '_draw_text', lambda pos, text, *args, **kwargs: texts.append(text))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    return ui, texts


@pytest.mark.parametrize('label, known, images', [
    ('b', {'b'}, ['b']), ('b', set(), []), ("b'", {'b2'}, ['b', "'"]), ("b'", {'b'}, []),
    ('@', set(), ['@']), ('M', {'M'}, [])])
def test_strength_column_shows_sprites_of_identified_types_only(monkeypatch, label, known, images):
    ui, texts = _strength_column_ui(monkeypatch, known)
    ui._draw_strength_entry(3, label, label == '@')
    assert texts == [label]
    expected = [ui._sprite_images.get(name) or ui._mark_images[name] for name in images]
    assert [piece.image for piece in ui._drawables] == expected
    # Sprites keep the field's common scale, so their sizes match the field.
    for piece in ui._drawables:
        assert piece.scale == pytest.approx(1.8 * 11 / SPRITE_REFERENCE_PIXELS)


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
    ui._floor_images = None
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



def test_golem_rock_cell_is_rubble_and_breaks_column_links(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._wall_images = {part: SimpleNamespace(width=26, height=50) for part in sprite_funcs.WALL_PARTS}
    ui._floor_images = None
    ui._sprite_images = {sprite_funcs.ROCK_SPRITE: SimpleNamespace(width=95, height=103)}
    ui.map_mode = False
    ui.scale = 1
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    monkeypatch.setattr(PygletUI, '_draw_tile', lambda *args: None)
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    field = [[d.CHAR_FLOOR] * 3 for _ in range(3)]
    field[1][0] = field[1][1] = d.CHAR_WALL
    ui._rock_cells = {(1, 1)}
    ui._draw_tile(1, 1, sprite_funcs.VISIBLE_WALL, field, lambda x, y: True)
    assert [piece.image for piece in ui._drawables] == [ui._sprite_images[sprite_funcs.ROCK_SPRITE]]
    ui._drawables.clear()
    ui._draw_tile(1, 1, sprite_funcs.WALL, field, lambda x, y: True)
    shade = round(255 * sprite_funcs.ROCK_EXPLORED_SHADE)
    assert ui._drawables[0].color == (shade, shade, shade)
    # The ordinary wall beside the rubble does not link toward it.
    ui._drawables.clear()
    ui._draw_tile(0, 1, sprite_funcs.VISIBLE_WALL, field, lambda x, y: True)
    assert [piece.image for piece in ui._drawables] == [ui._wall_images['column']]


def _barrier_ui(monkeypatch, cooling_center):
    ui = SpriteUI.__new__(SpriteUI)
    image = lambda name: SimpleNamespace(name=name, width=48, height=96)
    ui._floor_images = [image('floor-a'), image('floor-b')]
    ui._flame_images = [image('flame-a'), image('flame-b')]
    ui._smoke_images = [image('smoke-a'), image('smoke-b')]
    ui._cooling_center = cooling_center
    ui._cur_torched = [[1] * 5 for _ in range(5)]
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._floor_group = 'floor'
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    ui._field_col_x = lambda x: x * ui.cell_size_x
    ui._field_col_width = lambda x: ui.cell_size_x
    field = [[d.CHAR_BARRIER] * 5 for _ in range(5)]
    return ui, field


@pytest.mark.parametrize('center, pos, cooled', [
    (None, (2, 2), False), ((2, 2), (2, 2), True), ((2, 2), (3, 3), True), ((2, 2), (4, 2), False)])
def test_barrier_burns_on_the_floor_and_only_smokes_near_a_protected_player(
        monkeypatch, center, pos, cooled):
    ui, field = _barrier_ui(monkeypatch, center)
    ui._draw_tile(*pos, sprite_funcs.VISIBLE_FLOOR, field, lambda x, y: True)
    stone, flame = ui._drawables
    assert stone.image.name.startswith('floor')
    assert flame.image.name.startswith('smoke' if cooled else 'flame')
    if cooled:
        assert flame.color == sprite_funcs.SMOKE_TINT
        assert flame.blend_dest != pyglet.gl.GL_ONE
    else:
        assert flame.blend_dest == pyglet.gl.GL_ONE  # additive glow
    # Flames rise above the cell into the one to its north.
    assert flame.scale_y * 96 > ui.cell_size_y


def test_flame_image_is_bright_at_the_root_and_clear_at_the_top():
    image = sprite_funcs.flame_image(0)
    width, height = sprite_funcs.FLAME_TEXELS
    data = image.get_data('RGBA', width * 4)
    alpha = lambda col, row: data[(row * width + col) * 4 + 3]
    assert alpha(width // 2, height // 8) > 150
    assert alpha(width // 2, height - 1) == 0 and alpha(0, 2) < 20


def test_barrier_glyph_is_left_to_the_flames(sprite_ui):
    sprite_ui._floor_images = ['floor-a', 'floor-b']
    sprite_ui._draw_field_text((4, 5), d.CHAR_BARRIER, (220, 82, 82), True)
    assert not sprite_ui.text_calls and not sprite_ui._drawables


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
    ui._floor_images = None
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



def test_floor_is_a_checkerboard_of_two_tinted_stones(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._floor_group = 'floor'
    ui._drawables = []
    ui._display_color = lambda color: color
    ui._floor_images = [SimpleNamespace(width=130, height=200, part=part)
                        for part in sprite_funcs.FLOOR_PARTS]
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    field = [[d.CHAR_FLOOR] * 2 for _ in range(2)]
    for x, y in ((0, 0), (1, 0), (1, 1)):
        ui._draw_tile(x, y, sprite_funcs.VISIBLE_FLOOR, field, lambda *_: True)
    even, odd, even_again = ui._drawables
    assert (even.image.part, odd.image.part, even_again.image.part) == ('a', 'b', 'a')
    assert even.color == even_again.color == sprite_funcs.FLOOR_TINTS[sprite_funcs.VISIBLE_FLOOR]
    assert sum(odd.color) < sum(even.color)
    assert even.image.width * even.scale_x == 14 and even.image.height * even.scale_y == 21
    # Explored-but-not-visible floor stays darker than visible floor.
    ui._draw_tile(0, 1, sprite_funcs.FLOOR, field, lambda *_: True)
    assert sum(ui._drawables[-1].color) < sum(odd.color)
