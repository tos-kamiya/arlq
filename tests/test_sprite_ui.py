"""Sprite rendering must respect the shared information disclosure rules."""
from pathlib import Path
from types import SimpleNamespace

import pyglet
import pytest

from arlq import defs as d
from arlq import display, pyglet_funcs, sprite_defs, sprite_effects, sprite_funcs
from arlq import sprite_images, sprite_terrain
from arlq import i18n
from arlq.game_events import FloorChanged, Rewound
from arlq.pyglet_funcs import PygletUI
from arlq.sprite_defs import SPRITE_REFERENCE_PIXELS
from arlq.sprite_funcs import SPRITE_FILES, SpriteUI


@pytest.fixture
def sprite_ui(monkeypatch):
    monkeypatch.setattr(i18n, '_lang', 'en')
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._sprite_images = {char: SimpleNamespace(width=100, height=120) for char in SPRITE_FILES}
    ui._gray_images = dict.fromkeys(ui._sprite_images, SimpleNamespace(width=100, height=120))
    ui._mark_images = {mark: SimpleNamespace(width=30, height=40) for mark in ("'", '"')}
    ui._sprite_cells = {}
    ui._pillar_images = {side: SimpleNamespace(width=64, height=96) for side in ('back', 'front')}
    ui.map_mode = False
    ui.scale = 1
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui._menu_cell_size_y = 20
    ui._menu_font_size = 12
    ui.font_size = 12
    ui.font_name = 'Courier New'
    ui._non_ascii_font_result = (ui.font_name, 1.0)
    ui._menu_non_ascii_font_result = (ui.font_name, 1.0)
    ui._menu_active = False
    ui.window_height = 500
    ui.batch = None
    ui._text_batch = None
    ui._row_groups = {}
    ui._lp_gauge_group = None
    ui._drawables = []
    ui.text_calls = []
    ui.outlines = []
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        lambda x, y, width, height, **kwargs: SimpleNamespace(
                            x=x, y=y, width=width, height=height, **kwargs))
    monkeypatch.setattr(PygletUI, '_draw_field_text',
                        lambda self, *args: self.text_calls.append(args))
    monkeypatch.setattr(ui, '_draw_ground_disc', lambda *args: ui.outlines.append(args))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.text.Label',
                        lambda text, **kwargs: SimpleNamespace(text=text, **kwargs))
    return ui


def test_known_sprite_enlarges_around_cell_center_and_retains_color(sprite_ui):
    ui = sprite_ui
    color = (220, 82, 82)
    ui._draw_field_text((4, 5), 'b', color, True)
    sprite = ui._drawables[0]
    assert sprite.scale == pytest.approx(1.8 * 11 / SPRITE_REFERENCE_PIXELS)
    assert sprite.x + sprite.image.width * sprite.scale / 2 == pytest.approx(58.5)
    # The feet, a fixed offset below the image centre, rest on the cell centre.
    feet = sprite.y + (sprite.image.height / 2 - sprite_defs.SPRITE_GROUND_OFFSET_PIXELS) * sprite.scale
    assert feet == pytest.approx(390)
    assert ui.outlines[0][3:] == (color, None)
    assert not ui.text_calls


def test_hover_enlarges_sprite_with_fixed_feet_and_original_cell_hitbox(sprite_ui):
    ui = sprite_ui
    ui.field_pixel_width = 260
    ui.field_width, ui.field_height = 79, 22
    ui._horizontal_scroll_px = 26
    ui._mouse_position = (33, 390)
    assert ui._hovered_cell() == (4, 5)
    ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    sprite = ui._drawables[0]
    assert sprite.scale == pytest.approx(2 * 1.8 * 11 / SPRITE_REFERENCE_PIXELS)
    feet = sprite.y + (sprite.image.height / 2 - sprite_defs.SPRITE_GROUND_OFFSET_PIXELS) * sprite.scale
    assert feet == pytest.approx(390)
    assert sprite.group.order > ui._row_group(21, 'wall').order
    assert sprite.group.order > pyglet.graphics.Group(order=9000).order
    assert ui._row_group(5, 'hover-mark').order > sprite.group.order
    label = ui._drawables[1]
    assert label.text == 'Bison'
    assert label.anchor_x == 'center'
    assert label.anchor_y == 'bottom'
    assert label.font_size == pytest.approx(
        ui.font_size * ui._status_font_scale() * sprite_funcs.MESSAGE_FONT_SIZE_SCALE)
    assert label.font_name == ui.font_name
    assert label.weight == 'bold'
    head_top = sprite.y + sprite.image.height * sprite.scale
    assert label.y == pytest.approx(head_top + sprite_funcs.LP_GAUGE_GAP * ui._sprite_unit())
    assert label.group.order > sprite.group.order
    ui._mouse_position = (39, 390)
    assert ui._hovered_cell() == (5, 5)
    ui._mouse_position = (260, 390)
    assert ui._hovered_cell() is None
    ui._mouse_position = (33, 50)
    assert ui._hovered_cell() is None
    ui._mouse_position = (33, 390)
    ui._menu_active = True
    assert ui._hovered_cell() is None


@pytest.mark.parametrize('key,name', [
    ('player sword', 'Player'),
    ('k', 'Marksman(k)'),
    ('d', 'Komodo Dragon(d)'),
    ('knight-n-l', 'Knight'), ('explorer-m-d', 'Dungeon Explorer'),
    ('seer-f-l', 'Fairy Seer'), ('seer-m-d', 'Fairy Seer'),
])
def test_hover_names_preserve_identity_and_member_roles(sprite_ui, key, name):
    sprite_ui._draw_hover_name((4, 5), key, 100)
    assert sprite_ui._drawables[0].text == name


@pytest.mark.parametrize('key', sprite_funcs.UNKNOWN_SPRITES)
def test_hover_unknown_character_has_no_name(sprite_ui, key):
    sprite_ui._draw_hover_name((4, 5), key, 100)
    assert not sprite_ui._drawables


@pytest.mark.parametrize('row', [0, 1, 2, 5])
def test_hover_name_is_below_only_at_dungeon_top(sprite_ui, row):
    ui = sprite_ui
    ui._draw_hover_name((4, row), 'b', -10)
    label = ui._drawables[0]
    if row <= 1:
        assert label.anchor_y == 'top'
        feet = ui.window_height - (row + 0.5) * ui.cell_size_y
        assert label.y == pytest.approx(feet - sprite_funcs.LP_GAUGE_GAP * ui._sprite_unit())
        assert 0 < label.y < ui.window_height
    else:
        assert label.anchor_y == 'bottom'


@pytest.mark.parametrize('key,name', [
    ('c', 'キメラ(c)'), ('k', '射手(k)'), ('@', 'プレイヤー(@)'),
    ('d', 'コモドドラゴン(d)'),
    ('player blessed', 'プレイヤー(@)'), ('knight-n-l', '騎士(K)'),
    ('K', 'コレクターエルフ(K)'), ('D', 'ドラゴン(D)'),
    ('explorer-m-d', 'ダンジョン探検家(D)'),
])
def test_japanese_hover_names_include_glyph(sprite_ui, monkeypatch, key, name):
    monkeypatch.setattr(i18n, '_lang', 'ja')
    monkeypatch.setattr(sprite_ui, '_non_ascii_font', lambda size: ('sans-serif', 1.0))
    sprite_ui._draw_hover_name((4, 5), key, 100)
    assert sprite_ui._drawables[0].text == name


def test_mouse_cursor_timeout_restarts_on_motion(sprite_ui, monkeypatch):
    ui = sprite_ui
    visible = []
    ui.window = SimpleNamespace(set_mouse_visible=visible.append)
    ui._stage_input_active = False
    monkeypatch.setattr(PygletUI, '_pump', lambda self: None)
    now = [10.0]
    monkeypatch.setattr(sprite_funcs.time, 'monotonic', lambda: now[0])
    ui._on_mouse_motion(20, 30, 1, 0)
    now[0] = 12.0
    ui._on_mouse_motion(21, 30, 1, 0)
    now[0] = 14.0
    ui._pump()
    assert visible == [True, True]
    now[0] = 15.0
    ui._pump()
    assert visible == [True, True, False]
    assert ui._mouse_position is None
    assert ui._resize_redraw_pending
    ui._on_mouse_motion(21, 30, 1, 0)
    assert ui._mouse_position == (21, 30)
    ui._on_mouse_leave(21, 30)
    assert ui._mouse_position is None


@pytest.mark.parametrize('char', ('+', '$', '%'))
def test_unavailable_glyph_uses_original_text(sprite_ui, char):
    sprite_ui._draw_field_text((4, 5), char, (220, 82, 82), True)
    assert sprite_ui.text_calls[0][1] == char
    # Raised a little so it stays inside its cell.
    assert sprite_ui.text_calls[0][0] == (4, pytest.approx(5 - sprite_funcs.FIELD_TEXT_RAISE))
    assert not sprite_ui._drawables


def test_unknown_amoeba_does_not_disclose_model(sprite_ui, monkeypatch):
    pillars = []
    monkeypatch.setattr(sprite_ui, '_draw_pillar', lambda *args: pillars.append(args))
    entity = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['a'])
    glyphs = display.revealed_entity_glyphs(entity, set(), False, 8, None)
    for glyph in glyphs:
        sprite_ui._draw_field_text((glyph.x, glyph.y), glyph.char, (244, 190, 78))
    assert not sprite_ui.text_calls
    assert sprite_ui._drawables[0].image is sprite_ui._sprite_images['?']
    # The symbol stands in a dimmed pillar of its text color.
    assert [args[-1] for args in pillars] == [
        tuple(round(c * sprite_funcs.UNKNOWN_PILLAR) for c in (244, 190, 78))]
    # Its ground disc keeps the hue but is no brighter than a blue disc.
    disc = sprite_ui.outlines[0][3]
    blue = sprite_funcs.COLOR_MAP[sprite_funcs.CI_BLUE]
    assert sprite_images._luminance(disc) == pytest.approx(sprite_images._luminance(blue), abs=1)
    assert disc[0] > disc[1] > disc[2]



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


@pytest.mark.parametrize('char,name', [
    (char, name) for char, names in sprite_funcs.MEMBER_SPRITES.items() for name in names
])
def test_member_sprite_uses_stable_skin_without_pillar(sprite_ui, monkeypatch, char, name):
    ui = sprite_ui
    ui._member_variants = {char: name}
    ui._member_skins = dict.fromkeys(sprite_funcs.MEMBER_SPRITES, 'm')
    pillars = []
    monkeypatch.setattr(ui, '_draw_pillar', lambda *args: pillars.append(args))
    for tone in ('member_waiting', 'member'):
        ui._draw_member(display.FieldGlyph(4, 5, char, tone))
    assert [obj.image for obj in ui._drawables] == [ui._sprite_images[f'{name}-m']] * 2
    assert not pillars
    assert len(ui.outlines) == 1
    assert ui.outlines[0][2] == pytest.approx(sprite_defs.GROUND_DISC_RADIUS * ui.cell_size_x)


def test_buffalo_has_bundled_sprite():
    assert SPRITE_FILES['B'] == 'buffalo.png'


def test_flame_cobra_has_bundled_sprite():
    assert SPRITE_FILES['f'] == 'flame-cobra.png'


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
    feet = dragon.y + (dragon.image.height / 2 - sprite_defs.SPRITE_GROUND_OFFSET_PIXELS) * dragon.scale
    assert feet == pytest.approx(390)



def test_ground_disc_is_tinted_ellipse_fading_outward(monkeypatch):
    image = sprite_images.ground_disc_image()
    data = image.get_data('RGBA', image.width * 4)
    alpha = lambda col, row: data[(row * image.width + col) * 4 + 3]
    mid = image.width // 2
    assert alpha(mid, mid) > alpha(mid + mid // 2, mid) > alpha(image.width - 1, mid)
    assert alpha(0, 0) == 0
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
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
    assert disc.image.height * disc.scale_y == pytest.approx(20 * sprite_images.GROUND_DISC_FLATTEN)
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


@pytest.mark.parametrize('level, outline', [(8, ('red', None)), (40, ('blue', None))])
def test_boss_disc_color_reflects_attack_without_upper_right_marker(sprite_ui, level, outline):
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


def test_shift_horizontal_view_scrolls_only_when_field_overflows():
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.field_pixel_width = 50
    ui._map_pixel_width = 100
    ui._horizontal_scroll_px = 20
    ui.cell_size_x = 10
    ui._camera_follow_player = True

    assert ui._handle_horizontal_view_key(pyglet.window.key.RIGHT) == (1, 0)
    assert ui._horizontal_scroll_px == 50
    assert not ui._camera_follow_player

    ui._handle_horizontal_view_key(pyglet.window.key.LEFT)
    assert ui._horizontal_scroll_px == 20

    ui._horizontal_scroll_px = 50
    ui._handle_horizontal_view_key(pyglet.window.key.RIGHT)
    assert ui._horizontal_scroll_px == 60
    ui._handle_horizontal_view_key(pyglet.window.key.RIGHT)
    assert ui._horizontal_scroll_px == 60

    ui.field_pixel_width = 100
    ui._horizontal_scroll_px = 0
    assert ui._handle_horizontal_view_key(pyglet.window.key.LEFT) == (0, 0)
    assert ui._horizontal_scroll_px == 0


def test_sprite_camera_centers_player_and_clamps_at_field_edges():
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.field_pixel_width = 40
    ui._map_pixel_width = 100
    ui.cell_size_x = 10

    ui._center_camera_on_player(5)
    assert ui._horizontal_scroll_px == 35
    ui._center_camera_on_player(0)
    assert ui._horizontal_scroll_px == 0
    ui._center_camera_on_player(9)
    assert ui._horizontal_scroll_px == 70


def test_sprite_vertical_resize_scales_field_and_preserves_horizontal_view():
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.field_width = 10
    ui.field_height = 2
    ui.window_width = 200
    ui.window_height = 80
    ui.scale = 1
    ui.cell_size_x = 13
    ui.cell_size_y = 20
    ui._menu_cell_size_y = 20
    ui._menu_active = False
    ui._menu_font_size = 17
    ui.font_size = 17
    ui.strength_column_padding = 4
    ui.strength_column_width = 60
    ui._map_pixel_width = 130
    ui._horizontal_scroll_px = 13
    ui._camera_follow_player = False
    ui._last_camera_player_pos = None
    ui._non_ascii_font_result = None
    ui._select_font_size = lambda: None

    ui._on_window_resize(200, 120)

    assert (ui.window_width, ui.window_height) == (200, 120)
    assert ui.scale == pytest.approx(2)
    assert ui.cell_size_x == pytest.approx(30)
    assert ui.cell_size_y == pytest.approx(40)
    assert ui.field_pixel_width == pytest.approx(106)
    assert ui._horizontal_scroll_px == pytest.approx(30)


@pytest.mark.parametrize('maximized_height', [1080, 2160])
@pytest.mark.parametrize('menu_active', [False, True])
def test_sprite_maximize_restore_accepts_window_manager_size(
    sprite_ui, maximized_height, menu_active,
):
    ui = sprite_ui
    ui.field_width, ui.field_height = d.FIELD_WIDTH, d.FIELD_HEIGHT
    ui._select_font_size = lambda: None
    ui._redraw_menu_text = lambda: None
    ui._set_scaled_dimensions()
    original_size = ui.window_width, ui.window_height
    original_scale = ui.scale
    ui._menu_active = menu_active
    size_requests = []
    ui.window = SimpleNamespace(set_size=lambda *size: size_requests.append(size))

    ui._on_window_resize(3840, maximized_height)
    assert (ui.window_width, ui.window_height) == (3840, maximized_height)
    # Some window managers report changed dimensions separately.
    ui._on_window_resize(original_size[0], maximized_height)
    ui._on_window_resize(*original_size)

    assert (ui.window_width, ui.window_height) == original_size
    assert ui.scale == pytest.approx(original_scale)
    assert size_requests == []


def test_sprite_default_window_fits_field_and_sidebar():
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.field_width, ui.field_height = d.FIELD_WIDTH, d.FIELD_HEIGHT
    ui.scale = 1
    ui._hud_row_height = ui._menu_cell_size_y = 20
    ui._select_font_size = lambda: setattr(ui, 'font_size', 17)
    ui._update_strength_column_width = lambda: setattr(ui, 'strength_column_width', 60)

    ui._set_scaled_dimensions()

    assert ui.window_height == d.FIELD_HEIGHT * 20 + 2 * 20
    assert ui._map_pixel_width == d.FIELD_WIDTH * 15
    assert ui.field_pixel_width == ui._map_pixel_width + sprite_funcs.FIELD_SIDEBAR_GAP * ui.cell_size_x
    assert ui.window_width == ui.field_pixel_width + 60
    assert ui._horizontal_scroll_px == 0 and ui._camera_follow_player


def test_sprite_resize_constraints_allow_zoom_range():
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    size_constraints = []
    ui.window = SimpleNamespace(
        set_minimum_size=lambda width, height: size_constraints.append(
            ('minimum', width, height)
        ),
        set_maximum_size=lambda width, height: size_constraints.append(
            ('maximum', width, height)
        ),
    )
    ui.field_height = 21
    ui._menu_cell_size_y = 20

    ui._update_minimum_window_size()

    assert size_constraints[0][0:2] == ('minimum', 269)
    assert size_constraints[0][2] == 250
    assert size_constraints[1] == ('maximum', sprite_funcs.MAX_WINDOW_WIDTH, 1720)


@pytest.mark.parametrize(
    'view_width, expected_move',
    [(50, (1, 0)), (100, (0, 0))],
)
def test_shift_right_input_is_consumed_as_view_only(view_width, expected_move, monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.field_pixel_width = view_width
    ui._map_pixel_width = 100
    ui._horizontal_scroll_px = 0
    ui.cell_size_x = 10
    ui._camera_follow_player = True
    ui._closed = False
    ui._key_queue = [(pyglet.window.key.RIGHT, pyglet.window.key.MOD_SHIFT)]
    ui._gamepad_help_button = None
    ui._gamepad_pressed_buttons = set()
    ui._gamepad_preview_changed = False
    ui._held_direction_keys = set()
    ui._held_shift_direction_keys = set()
    ui._held_direction = None
    ui._next_repeat_at = 0
    ui.key_repeat_interval = None
    ui.controller = None
    monkeypatch.setattr(ui, '_pump', lambda: None)

    move = ui.input_direction()

    assert move == expected_move
    assert ui.shift_direction


@pytest.mark.parametrize('empowered, mark', [(2, "'"), (3, '"')])
def test_rank_mark_floats_white_at_sprite_upper_right(sprite_ui, empowered, mark):
    ui = sprite_ui
    ui._display_color = lambda color: color
    bison = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['b'], empowered=empowered)
    key = d.monster_type_key(bison)
    for glyph in display.revealed_entity_glyphs(bison, {key}, False, 8, None):
        ui._draw_field_text((glyph.x, glyph.y), glyph.char, ui._tone_color(glyph.tone))
    sprite, badge = ui._drawables
    assert sprite.image is ui._sprite_images['b']
    assert badge.image is ui._mark_images[mark]
    # White, not the bison's red strength color.
    assert badge.color == ui._tone_color('default')
    # Up and to the right of the bison's ground point, not in the next cell.
    feet_x, feet_y = 58.5, 500 - 110
    centre_x = badge.x + badge.image.width * badge.scale / 2
    centre_y = badge.y + badge.image.height * badge.scale / 2
    assert feet_x < centre_x < feet_x + ui.cell_size_x
    assert centre_y > feet_y
    assert not ui.text_calls


def test_dimmed_rank_mark_is_half_bright_white(sprite_ui):
    ui = sprite_ui
    ui._display_color = lambda color: color
    ui._draw_field_text((4, 5), 'b', ui._tone_color('red', True))
    ui._draw_field_text((5, 5), "'", ui._tone_color('red', True))
    _sprite, badge = ui._drawables
    assert badge.color == ui._tone_color('default', True)


def test_rank_mark_without_sprite_stays_text(sprite_ui):
    sprite_ui._sprite_images.pop('g')
    sprite_ui._draw_field_text((4, 5), 'g', (220, 82, 82), True)
    sprite_ui._draw_field_text((5, 5), "'", (220, 82, 82), True)
    assert [call[1] for call in sprite_ui.text_calls] == ['g', "'"]
    assert not sprite_ui._drawables


def test_fairy_stands_in_green_light_pillar(sprite_ui):
    ui = sprite_ui
    ui._display_color = lambda color: color
    ui._draw_field_text((4, 5), 'n', ui._tone_color('fairy'), True)
    sprite, back, front = ui._drawables
    assert sprite.image is ui._sprite_images['n']
    assert (back.image, front.image) == (ui._pillar_images['back'], ui._pillar_images['front'])
    assert back.color == front.color == ui._tone_color('fairy')
    assert back.group.order < sprite.group.order < front.group.order
    ui._drawables.clear()
    ui._draw_field_text((4, 5), 'b', ui._tone_color('blue'), True)
    assert len(ui._drawables) == 1


def _respawn_ui(ui, glows, known_cells):
    ui._display_color = lambda color: color
    ui._respawn_column_images = {
        (side, gaps): SimpleNamespace(width=96, height=200)
        for side in ('back', 'front') for gaps in (False, True)
    }
    ui._respawn_glows = glows
    ui._draw_floor = lambda *args: None
    field = [[d.CHAR_FLOOR] * 10 for _ in range(10)]
    for y in range(10):
        for x in range(10):
            ui._draw_tile(x, y, pyglet_funcs.FLOOR, field, lambda x, y: (x, y) in known_cells)
    return ui


def test_respawned_character_stands_in_swirled_column_of_its_disc_color(sprite_ui):
    ui = _respawn_ui(sprite_ui, {(4, 5)}, {(4, 5)})
    color = ui._tone_color('blue')
    ui._draw_field_text((4, 5), 'b', color, True)
    sprite, *walls = ui._drawables
    images = ui._respawn_column_images
    assert [wall.image for wall in walls] == [
        images['back', False], images['back', True],
        images['front', False], images['front', True],
    ]
    gap = tuple(round(c * sprite_images.RESPAWN_COLUMN_GAP_SHADE) for c in color)
    assert [wall.color for wall in walls] == [color, gap, color, gap]
    assert ui.outlines[0][3] == color
    assert walls[0].group.order < sprite.group.order < walls[2].group.order


@pytest.mark.parametrize('glows, known', (({(4, 5)}, set()), (set(), {(4, 5)})))
def test_respawn_column_needs_a_respawn_on_a_known_cell(sprite_ui, glows, known):
    ui = _respawn_ui(sprite_ui, glows, known)
    ui._draw_field_text((4, 5), 'b', ui._tone_color('blue'), True)
    assert len(ui._drawables) == 1


def test_hidden_respawn_on_explored_cell_lights_a_neutral_column_alone(sprite_ui, monkeypatch):
    ui = _respawn_ui(sprite_ui, {(4, 5), (6, 2), (8, 8)}, {(4, 5), (6, 2)})
    columns = []
    monkeypatch.setattr(ui, '_draw_respawn_column',
                        lambda cx, cy, size, row, color: columns.append((row, color)))
    monkeypatch.setattr(ui, '_field_col_x', lambda x: x * ui.cell_size_x)
    monkeypatch.setattr(PygletUI, '_finish_drawables', lambda self: None)
    # A character drawn at (4, 5) already stands in its own column.
    ui._draw_field_text((4, 5), 'b', ui._tone_color('blue'), True)
    ui._frame_drawable_cache = {}
    ui._floor_cells = {}
    ui._floor_backdrop_pending = ui._edge_shade_pending = False
    ui._finish_drawables()
    assert columns == [(5, ui._tone_color('blue')),
                       (2, sprite_funcs.RESPAWN_COLUMN_UNSEEN_COLOR)]


@pytest.mark.parametrize('met', (False, True))
def test_met_elf_sprite_and_disc_are_darker(sprite_ui, met):
    ui = sprite_ui
    elf = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE['H'])
    elf.revealed, elf.met = True, met
    for glyph in display.revealed_entity_glyphs(elf, {'H'}, False, 8, None):
        ui._draw_field_text((glyph.x, glyph.y), glyph.char, ui._tone_color(glyph.tone), glyph.bold)
    sprite = ui._drawables[0]
    white = ui._tone_color('default')
    shade = sprite_funcs.MET_ELF_SHADE if met else 1.0
    assert sprite.image is ui._sprite_images['H']
    assert getattr(sprite, 'color', (255, 255, 255)) == ((round(255 * shade),) * 3)
    assert ui.outlines[0][3] == tuple(round(c * shade) for c in white)


@pytest.mark.parametrize('pos, size', [((4, 5), sprite_defs.NEIGHBOR_SCALE), ((3, 6), sprite_defs.NEIGHBOR_SCALE),
                                       ((5, 5), 1.0), ((4, 4), 1.0)])
def test_character_next_to_player_is_enlarged_with_disc_unchanged(sprite_ui, pos, size):
    ui = sprite_ui
    ui._player_cell = (4, 6)
    ui._draw_field_text(pos, 'b', ui._tone_color('blue'), True)
    sprite = ui._drawables[0]
    assert sprite.scale == pytest.approx(size * 1.8 * 11 / SPRITE_REFERENCE_PIXELS)
    assert ui.outlines[0][2] == pytest.approx(sprite_defs.GROUND_DISC_RADIUS * ui.cell_size_x)


@pytest.mark.parametrize('char, role', [('J', d.MEMBER_JAVELIN_ELF), ('H', d.MEMBER_HEALER)])
def test_follower_next_to_player_is_drawn_smaller_not_enlarged(sprite_ui, char, role):
    ui = sprite_ui
    ui._member_variants = {char: sprite_funcs.MEMBER_SPRITES[char][0]}
    ui._member_skins = dict.fromkeys(sprite_funcs.MEMBER_SPRITES, 'm')
    ui._player_cell = (4, 6)
    ui._draw_member(display.FieldGlyph(4, 5, char, 'member', member_role=role))
    assert ui._drawables[0].scale == pytest.approx(
        sprite_images.FOLLOWER_SCALE * 1.8 * 11 / SPRITE_REFERENCE_PIXELS)
    assert not ui.outlines


def test_waiting_member_next_to_player_is_still_enlarged(sprite_ui):
    ui = sprite_ui
    ui._member_variants = {'H': sprite_funcs.MEMBER_SPRITES['H'][0]}
    ui._member_skins = dict.fromkeys(sprite_funcs.MEMBER_SPRITES, 'm')
    ui._player_cell = (4, 6)
    ui._draw_member(display.FieldGlyph(4, 5, 'H', 'member_waiting', member_role=d.MEMBER_HEALER))
    assert ui._drawables[0].scale == pytest.approx(
        sprite_defs.NEIGHBOR_SCALE * 1.8 * 11 / SPRITE_REFERENCE_PIXELS)


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
    ui._initialize_state()
    ui._sprite_images = {char: SimpleNamespace(width=100, height=120) for char in SPRITE_FILES}
    ui._mark_images = {mark: SimpleNamespace(width=30, height=40) for mark in ("'", '"')}
    ui._known_types = known_types
    ui.map_mode = False
    ui.scale = 1
    ui.font_size = ui._menu_font_size = 17
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui._text_batch = None
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


# 'Z' stands for an identified type that has no sprite.
@pytest.mark.parametrize('label, known, images', [
    ('b', {'b'}, ['b']), ('b', set(), []), ("b'", {'b2'}, ['b', "'"]), ("b'", {'b'}, []),
    ('@', set(), ['@']), ('M', {'M'}, ['M']), ('Z', {'Z'}, [])])
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
    lower, upper = (sprite_images.ground_disc_image(half)
                    for half in ('lower-left', 'upper-right'))
    size = lower.width
    alpha = lambda image, col, row: image.get_data('RGBA', size * 4)[(row * size + col) * 4 + 3]
    q = size // 4
    # Image rows run bottom to top: (3q, 3q) is upper right, (q, q) lower left.
    assert alpha(upper, 3 * q, 3 * q) > 0 and alpha(lower, 3 * q, 3 * q) == 0
    assert alpha(lower, q, q) > 0 and alpha(upper, q, q) == 0
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
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
    ui._initialize_state()
    ui._wall_images = None  # plain-shape fallback when the parts are missing
    ui._floor_images = None
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    ui.map_mode = False
    floors = []
    monkeypatch.setattr(PygletUI, '_draw_tile',
                        lambda self, x, y, color, *args: floors.append((x, y, color)))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs))
    field = [[d.CHAR_FLOOR] * 3 for _ in range(3)]
    field[1][1] = d.CHAR_WALL
    ui._draw_tile(1, 1, pyglet_funcs.VISIBLE_WALL, field, lambda x, y: True)
    assert floors == [(1, 1, pyglet_funcs.VISIBLE_FLOOR)]
    top, front = ui._drawables
    # The top face starts above the wall's own cell, inside the cell to its north.
    overhang = sprite_terrain.WALL_OVERHANG * ui.cell_size_y
    assert top.args[1] + top.args[3] == pytest.approx(500 - (20 - overhang))
    # The front face reaches down to the wall cell's south edge.
    assert front.args[1] == pytest.approx(500 - 40 - 1)
    assert front.args[1] + front.args[3] == pytest.approx(500 - (40 - overhang))
    order = lambda y, layer: ui._row_group(y, layer).order
    assert order(0, 'sprite') < top.group.order < order(1, 'sprite')


@pytest.mark.parametrize('tile_color', [pyglet_funcs.VISIBLE_WALL, pyglet_funcs.WALL])
def test_training_room_walls_are_boxes_smaller_than_the_cell(monkeypatch, tile_color):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._terrain_theme = 'training'
    ui._wall_images = None
    ui._wall_tints = sprite_terrain.TERRAIN_THEMES['training'][4]
    ui._floor_images = None
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    ui.map_mode = False
    monkeypatch.setattr(PygletUI, '_draw_tile', lambda *args: None)
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs))
    field = [[d.CHAR_WALL] * 3 for _ in range(3)]
    ui._draw_tile(1, 1, tile_color, field, lambda x, y: True)
    top, front = ui._drawables
    assert (top.color, front.color) == ui._wall_tints[tile_color]
    # Narrower than the cell, with floor showing at both sides.
    assert 13 < top.args[0] and top.args[0] + top.args[2] < 26
    assert front.args[0] == top.args[0] and front.args[2] == top.args[2]
    # The front face shows even with a wall to the south, ends above the
    # cell's south edge, and the top reaches no further north than the overhang.
    assert front.args[1] > 500 - 40
    assert top.args[1] == pytest.approx(front.args[1] + front.args[3])
    # The top face is as tall as it is wide on screen: a square seen from above.
    assert top.args[3] == pytest.approx(top.args[2])
    assert top.args[1] + top.args[3] <= 500 - (20 - sprite_terrain.WALL_OVERHANG * 20) + 1e-9


@pytest.mark.parametrize('tile_color', [pyglet_funcs.VISIBLE_WALL, pyglet_funcs.WALL])
def test_outer_wall_is_a_flat_cell_without_column(sprite_ui, monkeypatch, tile_color):
    ui = sprite_ui
    ui._decor = [[d.DECOR_OUTER_WALL]]
    ui._floor_group = 'floor'
    rectangles = []
    monkeypatch.setattr(ui, '_draw_wall_rect', lambda *args: rectangles.append(args))
    ui._draw_tile(0, 0, tile_color, [[d.CHAR_WALL]], lambda *_: True)
    assert rectangles == [(0, 0, ui.cell_size_x, ui.cell_size_y,
                           tile_color, 1, 'floor')]
    assert not ui._drawables


@pytest.mark.parametrize('tile_color', [pyglet_funcs.VISIBLE_WALL, pyglet_funcs.WALL])
def test_buried_wall_is_a_flat_wall_colored_cell(sprite_ui, monkeypatch, tile_color):
    ui = sprite_ui
    ui._decor = [[d.DECOR_BURIED_WALL]]
    ui._floor_group = 'floor'
    rectangles = []
    monkeypatch.setattr(ui, '_draw_wall_rect', lambda *args: rectangles.append(args))
    ui._draw_tile(0, 0, tile_color, [[d.CHAR_WALL]], lambda *_: True)
    assert rectangles == [(0, 0, ui.cell_size_x, ui.cell_size_y,
                           tile_color, 1, 'floor')]
    assert not ui._drawables



def test_golem_rock_cell_is_rubble_and_breaks_column_links(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._wall_images = {part: SimpleNamespace(width=26, height=50) for part in sprite_terrain.WALL_PARTS}
    ui._floor_images = None
    ui._sprite_images = {sprite_defs.ROCK_SPRITE: SimpleNamespace(width=95, height=103)}
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
    field[1][0] = d.CHAR_WALL
    field[1][1] = d.CHAR_GOLEM_WALL
    ui._decor = [[d.DECOR_NONE] * 3 for _ in range(3)]
    ui._draw_tile(1, 1, pyglet_funcs.VISIBLE_WALL, field, lambda x, y: True)
    assert [piece.image for piece in ui._drawables] == [ui._sprite_images[sprite_defs.ROCK_SPRITE]]
    ui._draw_golem_rubble((1, 1), True)
    assert len(ui._drawables) == 1
    ui._drawables.clear()
    ui._draw_tile(1, 1, pyglet_funcs.WALL, field, lambda x, y: True)
    shade = round(255 * sprite_terrain.ROCK_EXPLORED_SHADE)
    assert ui._drawables[0].color == (shade, shade, shade)
    # The ordinary wall beside the rubble does not link toward it.
    ui._drawables.clear()
    ui._draw_tile(0, 1, pyglet_funcs.VISIBLE_WALL, field, lambda x, y: True)
    assert [piece.image for piece in ui._drawables] == [ui._wall_images['column']]


def _barrier_ui(monkeypatch, cooling_center):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    image = lambda name: SimpleNamespace(name=name, width=48, height=96)
    ui._floor_images = [image('floor-a'), image('floor-b')]
    ui._barrier_images = [image('barrier-a'), image('barrier-b')]
    ui._reduced_barrier_images = [image('reduced-a'), image('reduced-b')]
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
def test_barrier_glows_on_the_floor_and_only_smokes_near_a_protected_player(
        monkeypatch, center, pos, cooled):
    ui, field = _barrier_ui(monkeypatch, center)
    ui._draw_tile(*pos, pyglet_funcs.VISIBLE_FLOOR, field, lambda x, y: True)
    stone, light = ui._drawables
    assert stone.image.name.startswith('floor')
    assert light.image.name.startswith('smoke' if cooled else 'barrier')
    if cooled:
        assert light.color == sprite_terrain.SMOKE_TINT
        assert light.blend_dest != pyglet.gl.GL_ONE
    else:
        assert light.blend_dest == pyglet.gl.GL_ONE  # additive glow
    # The light rises above the cell into the one to its north.
    assert light.scale_y * 96 > ui.cell_size_y


@pytest.mark.parametrize('guardian, amulet, floor_view, barrier_look, caltrop_cooled', [
    (False, False, False, 'barrier', False),
    (False, True, False, 'smoke', False),
    (True, False, False, 'reduced', False),
    (True, True, False, 'smoke', False),
    (True, False, True, 'barrier', False),
])
def test_guardian_cools_barriers_but_not_caltrops_near_player(
    monkeypatch, guardian, amulet, floor_view, barrier_look, caltrop_cooled,
):
    ui, field = _barrier_ui(monkeypatch, None)
    ui.window_width = 300
    ui._update_strength_column_width = lambda: setattr(ui, 'strength_column_width', 50)
    ui._camera_follow_player = False
    ui._last_camera_player_pos = None
    player = d.Player(2, 2, 1, 100)
    if guardian:
        player.members.append(d.PartyMember(2, 2, d.MEMBER_GUARDIAN))
    if amulet:
        player.elf_stage_flags |= d.ELF_STAGE_H_FLAG
    monkeypatch.setattr(PygletUI, 'draw_stage', lambda self, **kwargs: None)
    ui.draw_stage(player=player, floor_view=floor_view)
    ui._draw_tile(2, 2, pyglet_funcs.VISIBLE_FLOOR, field, lambda x, y: True)
    light = ui._drawables[-1]
    assert light.image.name.startswith(barrier_look)
    if barrier_look == 'reduced':
        assert light.blend_dest == pyglet.gl.GL_ONE  # glows like the full barrier

    field[2][3] = field[2][4] = d.CHAR_CALTROP
    drawn = []
    monkeypatch.setattr(ui, '_draw_barrier', lambda x, y, *_: drawn.append((x, y)))
    monkeypatch.setattr(PygletUI, '_draw_tile', lambda *args: None)
    for x in (3, 4):
        ui._draw_tile(x, 2, (132, 70, 60), field, lambda x, y: True)
    assert drawn == ([(3, 2)] if caltrop_cooled else [])


def test_barrier_image_glows_from_the_floor_and_fades_upward():
    image = sprite_images.barrier_image(0)
    width, height = sprite_images.BARRIER_TEXELS
    data = image.get_data('RGBA', width * 4)
    alpha = lambda col, row: data[(row * width + col) * 4 + 3]
    pixel = lambda col, row: data[(row * width + col) * 4:(row * width + col) * 4 + 3]
    near = round(sprite_images.BARRIER_INSET / sprite_images.BARRIER_HEIGHT * height)
    # The front sheet is bright where it leaves the floor and orange.
    r, g, b = pixel(width // 2, near + 1)
    assert alpha(width // 2, near + 1) > 120 and r > g > b
    # The plate is translucent inside, and the sheets fade before the top.
    assert alpha(width // 2, height // 3) < 200
    assert alpha(width // 2, height - 1) == 0 and alpha(0, 2) < 20


def test_reduced_barrier_image_is_a_smaller_barrier_in_the_middle():
    width, height = sprite_images.BARRIER_TEXELS
    alpha = lambda image: image.get_data('RGBA', width * 4)[3::4]
    full = alpha(sprite_images.barrier_image(0))
    reduced = alpha(sprite_images.barrier_image(0, sprite_terrain.BARRIER_REDUCED_SCALE))
    lit = lambda data: [(i % width, i // width) for i, a in enumerate(data) if a > 20]
    full_cols = [col for col, _ in lit(full)]
    cols, rows = zip(*lit(reduced))
    # Narrower, centred across the cell, and lower than the full barrier.
    assert max(cols) - min(cols) < (max(full_cols) - min(full_cols)) * 0.6
    assert abs((max(cols) + min(cols)) / 2 - (width - 1) / 2) <= 1
    assert max(rows) < max(row for _, row in lit(full)) * 0.75


def test_barrier_glyph_is_left_to_the_barrier_light(sprite_ui):
    sprite_ui._floor_images = ['floor-a', 'floor-b']
    sprite_ui._draw_field_text((4, 5), d.CHAR_BARRIER, (220, 82, 82), True)
    assert not sprite_ui.text_calls and not sprite_ui._drawables


def test_column_wall_links_only_toward_discovered_wall_neighbors(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._row_groups = {}
    ui._drawables = []
    ui._display_color = lambda color: color
    ui._wall_images = {part: SimpleNamespace(width=26, height=50, part=part)
                       for part in sprite_terrain.WALL_PARTS}
    ui._floor_images = None
    monkeypatch.setattr(PygletUI, '_draw_tile', lambda *args: None)
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    field = [[d.CHAR_FLOOR] * 3, [d.CHAR_WALL] * 3, [d.CHAR_FLOOR] * 3]
    # The east neighbour is unexplored, so no link reaches toward it.
    ui._draw_tile(1, 1, pyglet_funcs.VISIBLE_WALL, field, lambda x, y: x != 2)
    parts = [piece.image.part for piece in ui._drawables]
    assert parts == ['link-west', 'column']
    column = ui._drawables[-1]
    assert column.image.width * column.scale_x == 14
    assert column.image.height * column.scale_y == pytest.approx(
        (1 + sprite_terrain.WALL_OVERHANG) * 20)
    assert column.y == 500 - 40
    assert ui._drawables[0].group.order < column.group.order < ui._row_group(1, 'sprite').order



def test_floor_is_a_checkerboard_of_two_tinted_stones(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui._floor_group = 'floor'
    ui._drawables = []
    ui._display_color = lambda color: color
    ui._floor_images = [SimpleNamespace(width=130, height=200, part=part)
                        for part in sprite_terrain.FLOOR_PARTS]
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    field = [[d.CHAR_FLOOR] * 2 for _ in range(2)]
    for x, y in ((0, 0), (1, 0), (1, 1)):
        ui._draw_tile(x, y, pyglet_funcs.VISIBLE_FLOOR, field, lambda *_: True)
    even, odd, even_again = ui._drawables
    assert (even.image.part, odd.image.part, even_again.image.part) == ('a', 'b', 'a')
    assert even.color == even_again.color == sprite_terrain.FLOOR_TINTS[pyglet_funcs.VISIBLE_FLOOR]
    assert sum(odd.color) < sum(even.color)
    assert even.image.width * even.scale_x == 14 and even.image.height * even.scale_y == 21
    # Explored-but-not-visible floor stays darker than visible floor.
    ui._draw_tile(0, 1, pyglet_funcs.FLOOR, field, lambda *_: True)
    assert sum(ui._drawables[-1].color) < sum(odd.color)


@pytest.mark.parametrize('char, layer', ((d.CHAR_STAIRS_UP, 'column'), (d.CHAR_STAIRS_DOWN, 'wall')))
def test_stairs_are_gold_marble_flights_darker_outside_the_view(monkeypatch, char, layer):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.scale = 1
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui.map_mode = False
    ui._row_groups = {}
    ui._drawables = []
    ui._frame_drawable_cache = None
    ui._reused_drawable_ids = set()
    ui._display_color = lambda color: color
    ui._terrain_images = {char: SimpleNamespace(width=450, height=600, char=char)
                          for char in sprite_terrain.TERRAIN_FILES}
    ui._terrain_regions = {}
    ui._stage_field = [[' ', ' ']]
    ui._stage_discovered_at = lambda x, y: True
    ui._cur_torched = [[1, 0]]
    ui._disc_image = SimpleNamespace(width=64, height=64, char='disc')
    ui._disc_group = object()
    for image in ui._terrain_images.values():
        image.get_region = lambda x, y, w, h, image=image: SimpleNamespace(
            width=w, height=h, char=image.char, region=(x, x + w))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    ui._draw_stairs((0, 0), char)
    ui._draw_stairs((1, 0), char)
    visible_disc, visible, explored_disc, explored = ui._drawables
    # A ground disc in the respawn point's yellow sits under the flight.
    assert visible_disc.image is ui._disc_image and visible_disc.group is ui._disc_group
    assert visible_disc.color == sprite_funcs.COLOR_MAP[sprite_funcs.CI_YELLOW]
    assert visible_disc.opacity == sprite_terrain.STAIR_DISC_OPACITY
    assert visible_disc.scale_x * 64 == pytest.approx(2 * sprite_defs.GROUND_DISC_RADIUS * 13)
    assert sum(explored_disc.color) < sum(visible_disc.color)
    assert visible.image.char == char
    assert visible.color == sprite_defs.TERRAIN_TINT
    assert sum(explored.color) < sum(visible.color)
    # One cell plus half a cell into the north band. Each flight spreads a
    # quarter cell over the explored floor beside it and is cropped at the
    # map edge on its other side.
    assert visible.y == 480 and visible.image.height * visible.scale_y == pytest.approx(30)
    assert visible.image.region == (75, 450) and visible.x == 0
    assert visible.image.width * visible.scale_x == pytest.approx(13 * 1.25)
    assert explored.image.region == (0, 375)
    assert explored.x == pytest.approx(13 - 13 * sprite_defs.TERRAIN_SIDE)
    assert visible.group is ui._row_group(0, layer)


@pytest.mark.parametrize('neighbour, discovered, spreads', [
    (' ', True, True), (' ', False, False), ('#', True, False), ('^', True, False)])
def test_stairs_spread_only_over_explored_plain_floor(neighbour, discovered, spreads):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._stage_field = [[neighbour, '^', ' ']]
    ui._stage_discovered_at = lambda x, y: discovered or x != 0
    assert ui._open_floor(0, 0) == spreads
    assert ui._open_floor(2, 0)
    assert not ui._open_floor(3, 0)


def test_stairs_without_images_stay_yellow_text(sprite_ui):
    sprite_ui._terrain_images = {}
    sprite_ui._draw_stairs((4, 5), d.CHAR_STAIRS_DOWN)
    assert sprite_ui.text_calls[0][1] == d.CHAR_STAIRS_DOWN
    assert not sprite_ui._drawables


def test_scholar_stairs_use_green_direction_glyph_without_background(sprite_ui):
    sprite_ui._terrain_images = {d.CHAR_SCHOLAR_STAIRS_DOWN: object()}
    sprite_ui._draw_rect = lambda *args: pytest.fail("Explorer stairs have no background")
    sprite_ui._draw_stairs((4, 5), d.CHAR_SCHOLAR_STAIRS_DOWN)
    assert sprite_ui.text_calls[0][1] == d.CHAR_STAIRS_DOWN
    assert sprite_ui.text_calls[0][2] == sprite_funcs.COLOR_MAP[sprite_funcs.CI_GREEN]
    assert not sprite_ui._drawables


def test_pit_up_marker_is_a_green_disc_and_allows_fallen_rocks(sprite_ui, monkeypatch):
    discs = []
    monkeypatch.setattr(sprite_ui, '_draw_ground_disc', lambda *args: discs.append(args))
    sprite_ui._draw_stairs((4, 5), d.CHAR_SCHOLAR_STAIRS_UP)
    assert len(discs) == 1
    assert discs[0][3] == sprite_funcs.COLOR_MAP[sprite_funcs.CI_GREEN]
    assert not sprite_ui.text_calls
    assert d.CHAR_SCHOLAR_STAIRS_UP not in sprite_terrain.FALLEN_ROCK_BLOCKERS

    sprite_ui._show_pit_up_marker = False
    sprite_ui._draw_stairs((4, 5), d.CHAR_SCHOLAR_STAIRS_UP)
    assert len(discs) == 1


def test_discovered_passage_uses_same_light_as_pit_entrance_without_text(sprite_ui):
    sprite_ui._draw_stairs((4, 5), d.CHAR_SCHOLAR_STAIRS_UP)
    entrance_light = sprite_ui.outlines[-1]
    sprite_ui._show_pit_up_marker = False
    sprite_ui._draw_d_gate((4, 5), '.')
    assert sprite_ui.outlines[-1] == entrance_light
    assert len(sprite_ui.outlines) == 2
    assert not sprite_ui.text_calls


def test_collapse_pit_is_a_gold_tinted_hole_under_the_characters(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui.map_mode = False
    ui._row_groups = {}
    ui._drawables = []
    ui._frame_drawable_cache = None
    ui._reused_drawable_ids = set()
    ui._display_color = lambda color: color
    ui._terrain_images = {char: SimpleNamespace(width=450, height=500, char=char)
                          for char in sprite_terrain.TERRAIN_FILES}
    ui._terrain_regions = {}
    ui._stage_field = [[' ', d.CHAR_COLLAPSE, ' ']]
    ui._stage_discovered_at = lambda x, y: True
    ui._cur_torched = [[1, 1, 1]]
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    ui._draw_pit((1, 0))
    pit, = ui._drawables
    assert pit.image.char == d.CHAR_COLLAPSE
    assert pit.color == sprite_defs.TERRAIN_TINT
    assert pit.group is ui._row_group(0, 'wall')
    # Spread a quarter cell over the floor on both sides, and a quarter cell
    # into the band to the north, like a wall part.
    assert pit.x == pytest.approx(13 - 13 * sprite_defs.TERRAIN_SIDE)
    assert pit.image.width * pit.scale_x == pytest.approx(13 * 1.5)
    assert pit.y == 480 and pit.image.height * pit.scale_y == pytest.approx(25)


def test_collapse_pit_without_image_stays_yellow_text(sprite_ui):
    sprite_ui._terrain_images = {}
    sprite_ui._draw_pit((4, 5))
    assert sprite_ui.text_calls[0][1] == d.CHAR_COLLAPSE
    assert not sprite_ui._drawables


@pytest.mark.parametrize('scale, pixel_ratio, expected', [
    (1, 1, (1600, 1200)),
    (2, 1, (800, 600)),
    (4, 1, (400, 300)),
    (1, 2, (1600, 1200)),
    (2, 2, (800, 600)),
    (4, 2, (400, 300)),
    (3.37, 1, (475, 357)),
    (3.37, 2, (475, 357)),
])
def test_render_target_detail_is_independent_of_pixel_ratio(scale, pixel_ratio, expected):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui.scale = scale
    ui.window = SimpleNamespace(
        width=800, height=600,
        get_framebuffer_size=lambda: (800 * pixel_ratio, 600 * pixel_ratio),
    )
    assert ui._render_target_dimensions() == expected


@pytest.fixture
def cached_floor_ui(sprite_ui):
    ui = sprite_ui
    ui.scale = 2
    ui.cell_size_x, ui.cell_size_y = 26, 40
    ui._horizontal_scroll_px = 0
    ui._floor_group = 'floor'
    ui._floor_cells = {}
    ui._floor_tiles, ui._floor_cell_tiles = {}, {}
    for color in sprite_terrain.FLOOR_TINTS:
        for map_mode in (False, True):
            key = color, map_mode
            ui._floor_tiles[key] = SimpleNamespace(color=color, map_mode=map_mode)
            ui._floor_cell_tiles[key] = tuple(
                SimpleNamespace(color=color, map_mode=map_mode, parity=parity)
                for parity in (0, 1)
            )
    return ui


def test_matching_floor_cells_are_copied_as_one_checkerboard(cached_floor_ui):
    ui = cached_floor_ui
    for y in range(2):
        for x in range(2):
            ui._draw_floor(x, y, pyglet_funcs.VISIBLE_FLOOR, None, None)
    ui._draw_floor_tiles()
    assert len(ui._drawables) == 1
    sprite = ui._drawables[0]
    assert sprite.image is ui._floor_tiles[pyglet_funcs.VISIBLE_FLOOR, False]
    assert (sprite.x, sprite.y) == (0, 420)
    assert sprite.scale_x == pytest.approx(26 / 30)
    assert sprite.scale_y == 1
    assert sprite.blend_src == pyglet.gl.GL_ONE
    assert sprite.blend_dest == pyglet.gl.GL_ZERO


def test_floor_backdrop_is_reused_and_follows_scroll(cached_floor_ui, monkeypatch):
    ui = cached_floor_ui
    ui._use_floor_backdrop = True
    ui.field_width, ui.field_height = 5, 3
    ui._terrain_theme = 'ruins'
    ui._floor_backdrop_group = 'backdrop'
    data = bytes(range(16))
    tile = SimpleNamespace(width=2, height=2, get_data=lambda *args: data)
    ui._floor_tiles[pyglet_funcs.VISIBLE_FLOOR, False].get_image_data = lambda: tile
    uploads = []
    def image_data(width, height, fmt, pixels, pitch):
        uploads.append((width, height, pixels, pitch))
        return SimpleNamespace(get_texture=lambda: SimpleNamespace(width=width, height=height))
    monkeypatch.setattr(sprite_funcs.pyglet.image, 'ImageData', image_data)
    ui._draw_floor(0, 0, pyglet_funcs.FLOOR, None, None)
    assert ui._floor_backdrop_pending and not ui._floor_cells
    ui._draw_floor_backdrop()
    assert len(uploads) == 1
    width, height, pixels, pitch = uploads[0]
    assert (width, height, pitch) == (5, 3, 20)
    assert pixels[:20] == (data[8:16] * 3)[:20]
    ui._horizontal_scroll_px = 26
    ui._draw_floor_backdrop()
    assert len(uploads) == 1
    assert [sprite.x for sprite in ui._drawables] == [0, -26]
    assert all(sprite.scale_x == pytest.approx(26 / 30) for sprite in ui._drawables)
    assert all(sprite.scale_y == 1 for sprite in ui._drawables)


def test_floor_visibility_boundary_preserves_each_cells_shade_and_parity(cached_floor_ui):
    ui = cached_floor_ui
    ui.map_mode = True
    for y in range(2):
        for x in range(2):
            color = pyglet_funcs.VISIBLE_FLOOR if x == 0 else pyglet_funcs.FLOOR
            ui._draw_floor(x, y, color, None, None)
    ui._draw_floor_tiles()
    assert len(ui._drawables) == 4
    for sprite, (x, y) in zip(ui._drawables, ((0, 0), (1, 0), (0, 1), (1, 1))):
        color = pyglet_funcs.VISIBLE_FLOOR if x == 0 else pyglet_funcs.FLOOR
        assert sprite.image is ui._floor_cell_tiles[color, True][(x + y) % 2]


def test_floor_copies_do_not_cover_fog_special_cells_or_the_odd_field_edge(cached_floor_ui):
    ui = cached_floor_ui
    last_x = d.FIELD_WIDTH - 1
    for x, y in ((0, 0), (1, 1), (last_x, 0), (last_x, 1)):
        ui._draw_floor(x, y, pyglet_funcs.VISIBLE_FLOOR, None, None)
    ui._draw_floor_tiles()
    assert len(ui._drawables) == 4
    assert {(sprite.x, sprite.y) for sprite in ui._drawables} == {
        (0, 460), (26, 420), (last_x * 26, 460), (last_x * 26, 420),
    }


@pytest.mark.parametrize('left,width,visible', [
    (-101, 100, False), (-100, 100, True), (-10, 20, True),
    (90, 20, True), (100, 10, True), (100.25, 10, True), (101, 10, False),
])
def test_horizontal_culling_preserves_edge_overlap(sprite_ui, left, width, visible):
    ui = sprite_ui
    ui.window_width = 100
    ui.field_pixel_width = 70  # The sidebar is translucent.
    calls = []
    result = ui._draw_bounded_object(left, width, ('test',), lambda: calls.append(1) or 42)
    assert bool(calls) == visible
    assert result == (42 if visible else None)


def test_offscreen_body_keeps_visible_rank_mark(sprite_ui):
    ui = sprite_ui
    ui.window_width = 100
    # A small body just beyond the left edge, with a rank mark reaching inside.
    ui._horizontal_scroll_px = 13 * 4 + 6.5 + 3
    ui._sprite_images['b'] = SimpleNamespace(width=10, height=20)
    ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    assert not ui._drawables
    assert (4, 5) in ui._sprite_cells
    ui._draw_field_text((5, 5), "'", (220, 82, 82), True)
    assert len(ui._drawables) == 1
    assert ui._drawables[0].image is ui._mark_images["'"]
    assert not ui.text_calls


def test_large_sprite_with_offscreen_cell_is_retained(sprite_ui):
    ui = sprite_ui
    ui.window_width = 100
    ui._horizontal_scroll_px = 80
    ui._sprite_images['D'] = SimpleNamespace(width=600, height=220)
    ui._draw_field_text((4, 5), 'D', (220, 82, 82), True)
    assert len(ui._drawables) == 1
    assert ui._drawables[0].x < 0
    assert ui._drawables[0].x + 600 * ui._drawables[0].scale > 0


def test_tile_columns_keep_checkerboard_alignment_and_terrain_margin(sprite_ui):
    ui = sprite_ui
    ui.window_width = 100
    ui._horizontal_scroll_px = 200.5
    columns = ui._field_draw_columns(79)
    assert columns.start % 2 == columns.stop % 2 == 0
    assert 0 < columns.start < columns.stop < 79
    # Include a stair disc whose centre lies outside either window edge.
    for x in range(79):
        centre = ui._field_col_x(x) + ui.cell_size_x / 2
        radius = sprite_defs.GROUND_DISC_RADIUS * ui._sprite_unit()
        if centre + radius >= 0 and centre - radius <= ui.window_width:
            assert x in columns
    assert list(PygletUI._field_draw_columns(ui, 79)) == list(range(79))


def test_culled_cached_objects_are_removed_and_created_on_return(sprite_ui):
    ui = sprite_ui
    ui.window_width = 100
    ui._drawable_cache = {}
    ui._floor_cells = {}
    objects = []

    def create():
        obj = SimpleNamespace(deleted=False)
        obj.delete = lambda: setattr(obj, 'deleted', True)
        objects.append(obj)
        return obj

    for left in (10, 200, 10):
        ui._clear_drawables()
        ui._draw_bounded_object(left, 20, ('test', left), create)
        ui._finish_drawables()
    assert len(objects) == 2
    assert objects[0].deleted
    assert not objects[1].deleted
    assert ui._drawables == [objects[1]]


@pytest.mark.parametrize('ui_type', [PygletUI, SpriteUI])
def test_shared_drawable_cache_retains_duplicates_and_deletes_stale_objects(ui_type):
    ui = ui_type.__new__(ui_type)
    ui._menu_active = False
    ui._drawable_cache = {}
    ui._frame_drawable_cache = None
    ui._sprite_cells = {}
    created = []

    def create():
        obj = SimpleNamespace(deleted=False)
        obj.delete = lambda: setattr(obj, 'deleted', True)
        created.append(obj)
        return obj

    ui._clear_drawables()
    first = ui._draw_object(('tile',), create)
    second = ui._draw_object(('tile',), create)
    ui._finish_drawables()
    assert first is not second

    ui._clear_drawables()
    assert ui._draw_object(('tile',), create) is first
    ui._finish_drawables()
    assert not first.deleted and second.deleted

    ui._clear_drawables()
    ui._finish_drawables()
    assert first.deleted and ui._drawable_cache == {}
    assert len(created) == 2


def test_sprite_ui_recreates_uncached_objects_and_retains_floor():
    ui = SpriteUI.__new__(SpriteUI)
    ui._menu_active = False
    ui._drawable_cache = {}
    ui._sprite_cells = {}

    def create():
        obj = SimpleNamespace(deleted=False)
        obj.delete = lambda: setattr(obj, 'deleted', True)
        return obj

    ui._clear_drawables()
    floor = ui._draw_object(('floor-copy', 1, 1), create)
    label = ui._draw_object(('label', 'status'), create)
    ui._finish_drawables()

    ui._clear_drawables()
    assert label.deleted
    assert ui._draw_object(('floor-copy', 1, 1), create) is floor
    replacement = ui._draw_object(('label', 'status'), create)
    ui._finish_drawables()
    assert replacement is not label
    assert not replacement.deleted and not floor.deleted
    assert all(key[0] != 'label' for key in ui._drawable_cache)


def test_pyglet_tile_color_changes_keep_the_same_background_object(monkeypatch):
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui._menu_active = False
    ui._drawable_cache = {}
    ui._tile_group = None
    ui.cell_size_x, ui.cell_size_y = 13, 20
    ui.window_height = 500
    ui.batch = None
    ui.map_mode = False
    monkeypatch.setattr('arlq.pyglet_funcs.pyglet.shapes.Rectangle',
                        lambda *args, **kwargs: SimpleNamespace(**kwargs, delete=lambda: None))
    objects = []
    for color in ((20, 20, 20), (100, 100, 100), (20, 20, 20)):
        ui._clear_drawables()
        ui._draw_tile(1, 1, color, [], lambda x, y: True)
        ui._finish_drawables()
        obj, = ui._drawables
        assert obj.color == color
        objects.append(obj)
    assert objects[0] is objects[1] is objects[2]


def test_visible_disc_is_kept_when_body_is_offscreen(sprite_ui):
    ui = sprite_ui
    ui.window_width = 100
    ui._horizontal_scroll_px = 70
    ui._sprite_images['b'] = SimpleNamespace(width=10, height=20)
    ui._disc_image = SimpleNamespace(width=64, height=64)
    ui._disc_group = 'disc'
    # Restore the implementation replaced by the fixture.
    ui._draw_ground_disc = SpriteUI._draw_ground_disc.__get__(ui)
    ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    assert len(ui._drawables) == 1
    assert ui._drawables[0].image is ui._disc_image


def test_floor_culling_keeps_full_blocks_at_window_edges(cached_floor_ui):
    ui = cached_floor_ui
    ui.window_width = 65
    ui._horizontal_scroll_px = 100.5
    for y in range(2):
        for x in ui._field_draw_columns(79):
            ui._draw_floor(x, y, pyglet_funcs.VISIBLE_FLOOR, None, None)
    ui._draw_floor_tiles()
    assert len(ui._drawables) == 3
    assert all(obj.image is ui._floor_tiles[pyglet_funcs.VISIBLE_FLOOR, False]
               for obj in ui._drawables)
    assert ui._drawables[0].x < 0
    assert ui._drawables[-1].x + 52 > ui.window_width


def test_offscreen_terrain_still_reads_neighbors(sprite_ui):
    ui = sprite_ui
    ui.window_width = 100
    ui._horizontal_scroll_px = 31
    ui._terrain_images = {d.CHAR_COLLAPSE: SimpleNamespace(width=450, height=500)}
    ui._terrain_regions = {}
    ui._stage_field = [[d.CHAR_FLOOR, d.CHAR_COLLAPSE, d.CHAR_FLOOR]]
    ui._stage_discovered_at = lambda x, y: True
    ui._cur_torched = [[1, 1, 1]]
    # The pit's own cell ends offscreen, but its right overhang reaches inside.
    ui._draw_pit((1, 0))
    assert len(ui._drawables) == 0  # right edge 29.25 is still left of 31
    ui._horizontal_scroll_px = 28
    ui._draw_pit((1, 0))
    assert len(ui._drawables) == 1
    assert ui._drawables[0].image is ui._terrain_images[d.CHAR_COLLAPSE]


def test_fallen_rocks_are_hidden_under_characters_and_text(monkeypatch):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._frame_drawable_cache = {}
    ui._drawable_cache = {}
    ui._floor_cells = {}
    ui._fallen_rock_draws = ((1, 1), (2, 1), (3, 1), (4, 1))
    ui._sprite_cells = {(1, 1): 1.0}
    ui._field_text_cells = frozenset({(2, 1)})
    ui._player_cell = (3, 1)
    drawn = []
    monkeypatch.setattr(ui, '_draw_terrain', lambda pos, key, layer: drawn.append((pos, key)))
    ui._finish_drawables()
    assert drawn == [((4, 1), d.DECOR_FALLEN_ROCKS)]


@pytest.mark.parametrize(
    "item, k_blessed, sprite",
    [
        (None, False, '@'),
        (d.ITEM_POISONED, False, '@'),
        (None, True, 'player blessed'),
        (d.ITEM_SWORD_X1_5, False, 'player sword'),
        (d.ITEM_SWORD_X1_5, True, 'player sword'),
        (d.ITEM_SWORD_CURSED, True, 'player cursed sword'),
    ],
)
def test_player_sprite_shows_its_sword(item, k_blessed, sprite):
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._sprite_images = dict.fromkeys(sprite_funcs.SPRITE_FILES)
    player = d.Player(1, 1, 10, d.LP_INIT)
    player.item = item
    if k_blessed:
        player.elf_stage_flags |= d.ELF_STAGE_K_FLAG
    assert ui._player_sprite(player) == sprite
    # Without the variant images, the plain player is drawn.
    ui._sprite_images = {'@': None}
    assert ui._player_sprite(player) == '@'


@pytest.mark.parametrize('lp, tone', [(90, 'default'), (d.LP_INIT, 'magenta'), (d.LP_LOW_THRESHOLD, 'red')])
def test_lp_gauge_sits_over_player_head_scaled_to_its_disc(sprite_ui, lp, tone):
    ui = sprite_ui
    ui._display_color = lambda color: color
    ui._sprite_head_room = {'@': 10}
    player = d.Player(4, 5, level=8, lp=lp)
    ui._draw_player((4, 5), player)
    sprite = ui._drawables[0]
    top_frame, bottom_frame, left_frame, right_frame, fill = ui._drawables[1:6]
    backing = ui._drawables[6] if lp < d.LP_MAX else None
    width = round(sprite_funcs.LP_GAUGE_WIDTH * 2 * sprite_defs.GROUND_DISC_RADIUS
                  * ui._sprite_unit())
    assert fill.width + (backing.width if backing else 0) == width
    assert fill.width == round(width * min(lp, d.LP_MAX) / d.LP_MAX)
    if backing:
        assert backing.x == fill.x + fill.width
    assert fill.color[:3] == ui._lp_gauge_color(player)
    assert (fill.color[:3] == sprite_funcs.COLOR_MAP['default']) == (tone == 'default')
    assert top_frame.width == bottom_frame.width == width + 2
    # The whole gauge is translucent.
    assert fill.color[3] == top_frame.color[3] == round(255 * sprite_funcs.LP_GAUGE_OPACITY)
    if backing:
        assert backing.color[3] == round(sprite_funcs.LP_GAUGE_BACKING[3]
                                         * sprite_funcs.LP_GAUGE_OPACITY)
    # The gauge floats above the opaque top of the player's image, about
    # two gauge heights clear of it.
    head_top = sprite.y + (sprite.image.height - 10) * sprite.scale
    assert 2 * fill.height <= fill.y - head_top < ui._sprite_unit()
    # Its centre is the player's cell centre, and the status row drops it.
    assert fill.x + width / 2 == pytest.approx(ui._field_col_x(4) + ui.cell_size_x / 2, abs=1)
    assert not ui._status_shows_lp_gauge()


def test_edge_floor_shade_fades_smoothly_from_the_outer_walls():
    shade = sprite_images.edge_floor_shade
    width, height = d.FIELD_WIDTH, d.FIELD_HEIGHT
    middle_y = height / 2
    side_edge, side_cells = sprite_images.EDGE_FLOOR_SIDE_FADE
    end_edge, end_cells = sprite_images.EDGE_FLOOR_END_FADE
    assert shade(1, middle_y, width, height) == pytest.approx(side_edge)
    assert shade(width - 1, middle_y, width, height) == pytest.approx(side_edge)
    assert shade(1 + side_cells, middle_y, width, height) == 1
    assert shade(width / 2, 1, width, height) == pytest.approx(end_edge)
    assert shade(width / 2, height - 1 - end_cells, width, height) == 1
    # Monotonic and without large steps between neighboring texels.
    samples = [shade(1 + i / 8, middle_y, width, height) for i in range(40)]
    assert samples == sorted(samples)
    assert max(b - a for a, b in zip(samples, samples[1:])) < 0.06
    # Corners take the darker fade rather than multiplying both.
    assert shade(1, 1, width, height) == pytest.approx(min(side_edge, end_edge))


def edge_shade_ui(ui, scroll):
    ui.field_width, ui.field_height = d.FIELD_WIDTH, d.FIELD_HEIGHT
    ui.window_width = 26 * 30
    ui._horizontal_scroll_px = scroll
    ui._edge_shade_group = 'edge-shade'
    ui._edge_shade_bounds = None
    texels = sprite_images.EDGE_FLOOR_TEXELS_PER_CELL
    image = SimpleNamespace(width=d.FIELD_WIDTH * texels, height=d.FIELD_HEIGHT * texels)
    image.get_region = lambda *region: SimpleNamespace(region=region, width=region[2],
                                                       height=region[3])
    ui._edge_shade_image = image
    ui._fallen_rock_draws = ()
    ui._sprite_cells, ui._field_text_cells, ui._player_cell = {}, frozenset(), None
    ui._frame_drawable_cache = {}
    ui._drawable_cache, ui._drawable_use_counts = {}, {}
    ui._reused_drawable_ids = set()
    return ui


def test_edge_shade_strips_cover_each_fading_texel_once(cached_floor_ui):
    ui = edge_shade_ui(cached_floor_ui, 0)
    texels = sprite_images.EDGE_FLOOR_TEXELS_PER_CELL
    width, height = d.FIELD_WIDTH * texels, d.FIELD_HEIGHT * texels
    covered = {}
    for col, row, w, h in ui._edge_shade_strips():
        for y in range(row, row + h):
            for x in range(col, col + w):
                covered[x, y] = covered.get((x, y), 0) + 1
    assert set(covered.values()) == {1}
    shade = sprite_images.edge_floor_shade
    for y in range(height):
        for x in range(width):
            if (x, y) not in covered:
                assert shade((x + 0.5) / texels, (y + 0.5) / texels,
                             d.FIELD_WIDTH, d.FIELD_HEIGHT) == 1


def test_edge_shade_multiplies_only_visible_strips_once_floor_is_drawn(cached_floor_ui):
    ui = edge_shade_ui(cached_floor_ui, 0)
    ui._finish_drawables()
    assert ui._drawables == []
    ui = edge_shade_ui(ui, 0)
    ui._draw_floor(4, 4, pyglet_funcs.VISIBLE_FLOOR, None, None)
    ui._finish_drawables()
    strips = [obj for obj in ui._drawables if obj.group == 'edge-shade']
    # At the left end: the left strip and the top/bottom strips, not the right one.
    assert len(strips) == 3
    assert all((obj.blend_src, obj.blend_dest) == (pyglet.gl.GL_DST_COLOR, pyglet.gl.GL_ZERO)
               for obj in strips)
    left = strips[0]
    assert (left.x, left.image.region[0]) == (0, 0)
    assert left.image.width * left.scale_x == pytest.approx(
        (1 + sprite_images.EDGE_FLOOR_SIDE_FADE[1]) * ui.cell_size_x)
    assert left.image.height * left.scale_y == d.FIELD_HEIGHT * ui.cell_size_y
    assert left.y == ui.window_height - d.FIELD_HEIGHT * ui.cell_size_y

    # In the middle of the field only the top and bottom strips remain.
    ui = edge_shade_ui(ui, 26 * 30)
    ui._drawables = []
    ui._draw_floor(40, 4, pyglet_funcs.VISIBLE_FLOOR, None, None)
    ui._finish_drawables()
    strips = [obj for obj in ui._drawables if obj.group == 'edge-shade']
    assert len(strips) == 2
    assert {obj.y for obj in strips} == {
        ui.window_height - ui.cell_size_y * (1 + sprite_images.EDGE_FLOOR_END_FADE[1]),
        ui.window_height - d.FIELD_HEIGHT * ui.cell_size_y,
    }


def test_edge_floor_shade_uses_first_non_wall_from_each_edge():
    field = [[d.CHAR_WALL] * 18 for _ in range(12)]
    for y in range(3, 9):
        for x in range(4, 15):
            field[y][x] = d.CHAR_FLOOR
    bounds = sprite_images.edge_floor_bounds(field)
    assert bounds == (4, 3, 15, 9)
    shade = sprite_images.edge_floor_shade
    side, side_width = sprite_images.EDGE_FLOOR_SIDE_FADE
    end, end_width = sprite_images.EDGE_FLOOR_END_FADE
    assert shade(0, 6, 18, 12, bounds) == side
    assert shade(4, 6, 18, 12, bounds) == side
    assert shade(4 + side_width, 6, 18, 12, bounds) == 1
    assert shade(18, 6, 18, 12, bounds) == side
    assert shade(9, 0, 18, 12, bounds) == end
    assert shade(9, 3, 18, 12, bounds) == end
    assert shade(9, 3 + end_width, 18, 12, bounds) == 1
    assert shade(9, 12, 18, 12, bounds) == end


def test_edge_shade_keeps_initial_bounds_when_returning_to_changed_floor(sprite_ui):
    ui = sprite_ui
    ui._edge_shade_bounds = None
    ui._edge_shade_image = None
    field = [[d.CHAR_WALL] * 8 for _ in range(6)]
    field[2][3] = d.CHAR_FLOOR
    other = [[d.CHAR_FLOOR] * 8 for _ in range(6)]
    ui._set_edge_shade_field(field)
    assert ui._edge_shade_bounds == (3, 2, 4, 3)
    field[0][0] = d.CHAR_FLOOR
    ui._set_edge_shade_field(other)
    assert ui._edge_shade_bounds == (0, 0, 8, 6)
    ui._set_edge_shade_field(field)
    assert ui._edge_shade_bounds == (3, 2, 4, 3)


def test_edge_shade_strips_cover_shifted_fades(cached_floor_ui):
    ui = edge_shade_ui(cached_floor_ui, 0)
    ui._edge_shade_bounds = (3, 2, d.FIELD_WIDTH - 4, d.FIELD_HEIGHT - 3)
    texels = sprite_images.EDGE_FLOOR_TEXELS_PER_CELL
    covered = set()
    for col, row, width, height in ui._edge_shade_strips():
        for y in range(row, row + height):
            for x in range(col, col + width):
                assert (x, y) not in covered
                covered.add((x, y))
    for y in range(d.FIELD_HEIGHT * texels):
        for x in range(d.FIELD_WIDTH * texels):
            if (x, y) not in covered:
                assert sprite_images.edge_floor_shade(
                    (x + .5) / texels, (y + .5) / texels,
                    d.FIELD_WIDTH, d.FIELD_HEIGHT, ui._edge_shade_bounds,
                ) == 1


@pytest.fixture
def instant_effects(sprite_ui, monkeypatch):
    durations = []

    def play(seconds, create, update=None):
        # Checks the scene as built; the animation is tested on its own.
        durations.append(seconds)
        objects = create()
        try:
            sprite_ui._flip()
        finally:
            for obj in objects:
                obj.delete()

    monkeypatch.setattr(sprite_ui, '_play_effect', play)
    return durations


@pytest.mark.parametrize('kind, tint', [
    ('down', sprite_defs.TERRAIN_TINT),
    ('up', sprite_defs.TERRAIN_TINT),
    ('fall', None),
    ('climb', None),
])
def test_floor_transition_shows_only_the_players_landing(sprite_ui, monkeypatch,
                                                         kind, tint, instant_effects):
    ui = sprite_ui
    ui._disc_image = SimpleNamespace(width=64, height=64)
    ui.combat_effect_seconds = 0.3
    ui.field_height = 20
    ui.field_pixel_width = 26 * 13
    ui._landing_image = SimpleNamespace(width=450, height=600)
    shown, deleted = [], []
    monkeypatch.setattr(ui, '_flip', lambda: shown.extend(made))
    made = []

    def track(factory):
        def make(*args, **kwargs):
            obj = factory(*args, **kwargs)
            obj.delete = lambda: deleted.append(obj)
            made.append(obj)
            return obj
        return make

    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        track(lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs)))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        track(lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs)))
    player = d.Player(3, 4, level=1, lp=d.LP_INIT)

    ui.draw_floor_transition(kind, player)

    landings = [obj for obj in shown if getattr(obj, 'image', None) is ui._landing_image]
    assert [landing.color for landing in landings] == ([] if tint is None else [tint])
    assert any(getattr(obj, 'image', None) is ui._sprite_images['@'] for obj in shown)
    ropes = [obj for obj in shown if getattr(obj, 'color', None) == sprite_effects.ROPE_COLOR]
    assert len(ropes) == (kind == 'climb')
    glows = [obj for obj in shown if getattr(obj, 'image', None) is ui._disc_image]
    assert [glow.opacity for glow in glows] == (
        [sprite_effects.ROPE_GLOW_OPACITY] if kind == 'climb' else [])
    assert deleted == shown
    assert instant_effects == [d.FLOOR_TRANSITION_SECONDS]


def test_floor_transition_is_skipped_at_zero_seconds(sprite_ui, monkeypatch):
    ui = sprite_ui
    ui.combat_effect_seconds = 0.3
    ui.floor_transition_seconds = 0
    monkeypatch.setattr(ui, '_flip', lambda: pytest.fail('drew a transition'))
    ui.draw_floor_transition('down', d.Player(3, 4, level=1, lp=d.LP_INIT))


def test_floor_transition_is_drawn_on_the_stairs_cell(sprite_ui, monkeypatch, instant_effects):
    ui = sprite_ui
    ui.combat_effect_seconds = 0.3
    ui.field_height = 20
    ui.field_pixel_width = 26 * 13
    ui._horizontal_scroll_px = 26
    ui._landing_image = SimpleNamespace(width=450, height=600)
    made = []
    monkeypatch.setattr(ui, '_flip', lambda: None)
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: made.append(SimpleNamespace(
                            image=picture, delete=lambda: None, **kwargs)) or made[-1])
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        lambda *args, **kwargs: SimpleNamespace(delete=lambda: None))

    ui.draw_floor_transition('down', d.Player(3, 4, level=1, lp=d.LP_INIT), (7, 2))

    landing = next(obj for obj in made if obj.image is ui._landing_image)
    figure = next(obj for obj in made if obj.image is ui._sprite_images['@'])
    left = 7 * 13 - 26
    assert landing.x == left - sprite_defs.TERRAIN_SIDE * 13
    assert landing.y == ui.window_height - 3 * 20
    assert figure.x + figure.image.width * figure.scale / 2 == left + 13 / 2





def test_boss_route_stays_yellow_dot_beside_player(sprite_ui):
    ui = sprite_ui
    ui._draw_boss_route_marker((2, 3), True, True)
    assert ui.text_calls == []
    ui._draw_boss_route_marker((2, 3), True, False)
    assert len(ui.text_calls) == 1 and ui.text_calls[0][1] == '.'


def test_cat_member_uses_its_sprite(sprite_ui):
    ui = sprite_ui
    ui._member_skins = {}
    ui._member_variants = {}
    for tone in ('member_waiting', 'member'):
        ui._draw_member(display.FieldGlyph(4, 5, 'Y', tone))
    assert [obj.image for obj in ui._drawables] == [ui._sprite_images['yawning-cat']] * 2
    assert len(ui.outlines) == 1


def test_ivy_uses_its_sprite(sprite_ui):
    assert SPRITE_FILES['i'] == 'ivy.png'
    sprite_ui._draw_field_text((4, 5), 'i', (220, 82, 82), True)
    assert sprite_ui._drawables[0].image is sprite_ui._sprite_images['i']


def test_bridgehead_parts_are_aligned_and_dim_when_explored(sprite_ui):
    ui = sprite_ui
    ui._bridgehead_under = 0.4
    ui._bridgehead_height = 1.75
    ui._bridgehead_images = {part: SimpleNamespace(width=300, height=620) for part in ('/', '\\')}
    ui._draw_bridgehead((4, 5), '/', True)
    ui._draw_bridgehead((5, 5), '\\', False)
    left, right = ui._drawables
    assert right.x == left.x + ui.cell_size_x
    assert left.scale_y * left.image.height == pytest.approx(1.75 * ui.cell_size_y)
    assert left.y == pytest.approx(ui.window_height - 6.4 * ui.cell_size_y)
    assert left.color == (255, 255, 255)
    assert right.color == (140, 140, 140)


@pytest.fixture
def bob_ui(sprite_ui):
    ui = sprite_ui
    ui._cur_torched = [[1] * 10 for _ in range(10)]
    ui._stage_input_active = True
    ui.idle_bob_enabled = True
    ui.flips = 0
    ui._flip = lambda: setattr(ui, 'flips', ui.flips + 1)
    ui.now = 0.0
    ui._bob_clock = lambda: ui.now
    return ui


def _bobbing_ys(ui):
    return [sprite.y for sprite, _ in ui._bobbing]


@pytest.mark.parametrize('text, bobs', [
    ('b', True),    # monster
    ('K', True),    # elf waiting on the map
    ('J', True),    # Javelin Elf before it joins
    ('l', True),    # fairy on the map
    ('?', True),    # unidentified character
    ('T', False),   # treasure chest
])
def test_characters_in_view_hop_but_treasure_stays(bob_ui, text, bobs):
    bob_ui._draw_field_text((4, 5), text, (220, 82, 82), True)
    assert bool(bob_ui._bobbing) is bobs


def test_characters_outside_view_or_on_the_map_stay_still(bob_ui):
    bob_ui._cur_torched[5][4] = 0
    bob_ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    assert not bob_ui._bobbing
    bob_ui._cur_torched[5][4] = 1
    bob_ui.map_mode = True
    bob_ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    assert not bob_ui._bobbing


@pytest.mark.parametrize('tone, role, bobs', [
    ('member_waiting', d.MEMBER_HEALER, True),
    ('member', d.MEMBER_HEALER, False),
    ('member', d.MEMBER_JAVELIN_ELF, False),
])
def test_waiting_members_hop_and_followers_stay(bob_ui, tone, role, bobs):
    char = 'J' if role == d.MEMBER_JAVELIN_ELF else d.MEMBER_GLYPHS[role]
    bob_ui._member_variants = {char: sprite_funcs.MEMBER_SPRITES[char][0]}
    bob_ui._member_skins = dict.fromkeys(sprite_funcs.MEMBER_SPRITES, 'm')
    bob_ui._draw_member(display.FieldGlyph(4, 5, char, tone, member_role=role))
    assert bool(bob_ui._bobbing) is bobs


def test_player_hops_but_following_fairy_stays(bob_ui, monkeypatch):
    monkeypatch.setattr(bob_ui, '_player_sprite', lambda player: '@')
    monkeypatch.setattr(bob_ui, '_draw_lp_gauge', lambda *args: None)
    bob_ui._draw_player((4, 5), d.Player(4, 5, 100, 90))
    assert len(bob_ui._bobbing) == 1
    bob_ui._draw_fairy_slot((5, 5), 'l')
    assert len(bob_ui._bobbing) == 1


def test_hop_switches_every_interval_in_whole_texels(bob_ui):
    bob_ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    base = bob_ui._bobbing[0][1]
    interval = sprite_funcs.IDLE_BOB_INTERVAL
    hop = sprite_funcs.IDLE_BOB_TEXELS / sprite_defs.LOW_RESOLUTION_DETAIL_SCALE
    bob_ui._update_idle_bob()
    assert (_bobbing_ys(bob_ui), bob_ui.flips) == ([base], 0)
    bob_ui.now = interval * 1.1
    bob_ui._update_idle_bob()
    assert (_bobbing_ys(bob_ui), bob_ui.flips) == ([base + hop], 1)
    bob_ui.now = interval * 1.9
    bob_ui._update_idle_bob()
    assert bob_ui.flips == 1  # no redraw within one height
    bob_ui.now = interval * 2.1
    bob_ui._update_idle_bob()
    assert (_bobbing_ys(bob_ui), bob_ui.flips) == ([base], 2)


def test_redraw_while_raised_keeps_the_raised_height(bob_ui):
    bob_ui.now = sprite_funcs.IDLE_BOB_INTERVAL * 1.5
    bob_ui._update_idle_bob()
    bob_ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    sprite, base = bob_ui._bobbing[0]
    assert sprite.y == base + bob_ui._bob_offset()


@pytest.mark.parametrize('change', ['disabled', 'not_waiting', 'map'])
def test_hop_returns_to_ground_when_off_or_not_waiting(bob_ui, change):
    bob_ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    base = bob_ui._bobbing[0][1]
    bob_ui.now = sprite_funcs.IDLE_BOB_INTERVAL * 1.5
    bob_ui._update_idle_bob()
    if change == 'disabled':
        bob_ui.idle_bob_enabled = False
    elif change == 'not_waiting':
        bob_ui._stage_input_active = False
    else:
        bob_ui.map_mode = True
    bob_ui._update_idle_bob()
    assert _bobbing_ys(bob_ui) == [base]


def test_menu_leaves_hopping_sprites_untouched(bob_ui):
    bob_ui._draw_field_text((4, 5), 'b', (220, 82, 82), True)
    base = bob_ui._bobbing[0][1]
    bob_ui._menu_active = True
    bob_ui.now = sprite_funcs.IDLE_BOB_INTERVAL * 1.5
    bob_ui._update_idle_bob()
    assert (_bobbing_ys(bob_ui), bob_ui.flips) == ([base], 0)


def _turn(move=None, events=()):
    from arlq.game_session import TurnResult

    return TurnResult(move is not None, None, False, 0, 0, list(events), move)


@pytest.mark.parametrize('move, facing', [
    ((0, -1), 'up'), ((0, 1), 'down'), ((-1, 0), 'left'), ((1, 0), 'right'),
])
def test_player_faces_its_last_move(sprite_ui, move, facing):
    sprite_ui._update_player_facing(_turn(move))
    assert sprite_ui._player_facing == facing
    sprite_ui._update_player_facing(_turn())
    assert sprite_ui._player_facing == facing


@pytest.mark.parametrize('event', [
    FloorChanged(0, 'down', 1, (3, 3)), FloorChanged(0, 'fall', 1, (3, 3)),
    Rewound(0, 'rewind', {}),
])
def test_player_faces_the_camera_after_stairs_falls_and_rewinds(sprite_ui, event):
    sprite_ui._update_player_facing(_turn((-1, 0), [event]))
    assert sprite_ui._player_facing == 'down'


@pytest.mark.parametrize('item, flags, base', [
    (None, 0, '@'),
    (d.ITEM_SWORD_X1_5, 0, 'player sword'),
    (d.ITEM_SWORD_CURSED, 0, 'player cursed sword'),
    (None, d.ELF_STAGE_K_FLAG, 'player blessed'),
])
@pytest.mark.parametrize('facing', ['down', 'up', 'left', 'right'])
def test_player_sprite_matches_sword_and_facing(sprite_ui, item, flags, base, facing):
    player = d.Player(2, 2, 100, 90)
    player.item = item
    player.elf_stage_flags = flags
    sprite_ui._player_facing = facing
    expected = base if facing == 'down' else f'{base} {facing}'
    assert sprite_ui._player_sprite(player) == expected
    assert SPRITE_FILES[expected].startswith('player')


def test_player_sprite_falls_back_to_facing_the_camera(sprite_ui):
    del sprite_ui._sprite_images['@ left']
    sprite_ui._player_facing = 'left'
    assert sprite_ui._player_sprite(d.Player(2, 2, 100, 90)) == '@'


def test_turned_player_sprites_are_bundled():
    directory = Path(sprite_funcs.__file__).parent / 'assets' / 'characters'
    for key, filename in SPRITE_FILES.items():
        if key.split(' ')[-1] in sprite_funcs.PLAYER_FACINGS and filename.startswith('player'):
            assert (directory / filename).is_file(), filename


def test_stage_start_faces_the_camera(sprite_ui, monkeypatch):
    monkeypatch.setattr(PygletUI, 'draw_stage', lambda self, **kwargs: None)
    monkeypatch.setattr(sprite_ui, '_update_strength_column_width', lambda: None)
    sprite_ui.window_width = 400
    sprite_ui.strength_column_width = 0
    sprite_ui._player_facing = 'left'
    sprite_ui.draw_stage(turn=3, stage_num=1)
    assert sprite_ui._player_facing == 'left'
    sprite_ui.draw_stage(turn=0, stage_num=1)
    assert sprite_ui._player_facing == 'down'


def _image(rows):
    """ImageData from rows of RGBA tuples, bottom row first."""
    height, width = len(rows), len(rows[0])
    data = bytes(value for row in rows for pixel in row for value in pixel)
    return pyglet.image.ImageData(width, height, 'RGBA', data, pitch=width * 4)


def test_soft_outline_fades_only_dark_pixels_near_the_edge(monkeypatch):
    monkeypatch.setattr(sprite_images, 'FOLLOWER_OUTLINE_BAND', 1)
    ink, cloth, clear = (20, 20, 30, 255), (200, 150, 100, 255), (0, 0, 0, 0)
    size = 7
    rows = [[clear] * size for _ in range(size)]
    for y in range(1, size - 1):
        for x in range(1, size - 1):
            edge = x in (1, size - 2) or y in (1, size - 2)
            rows[y][x] = ink if edge else cloth
    rows[3][3] = ink  # a dark detail away from the edge
    soft = sprite_images.soft_outline_image(_image(rows))
    alpha = soft.get_data('RGBA', size * 4)[3::4]
    at = lambda x, y: alpha[y * size + x]
    assert at(1, 1) == at(1, 3) == round(255 * sprite_images.FOLLOWER_OUTLINE_KEEP)
    assert at(2, 2) == 255   # colored pixel near the edge
    assert at(3, 3) == 255   # dark pixel away from the edge
    assert at(0, 0) == 0


def test_follower_image_is_made_once_per_map_mode(sprite_ui, monkeypatch):
    made = []
    monkeypatch.setattr(sprite_funcs, 'mipmapped', lambda data: made.append(data) or data)
    monkeypatch.setattr(sprite_funcs, 'soft_outline_image', lambda data: ('soft', data))
    monkeypatch.setattr(sprite_funcs, 'gray_image', lambda data: ('gray', data))
    sprite_ui._sprite_data = {'J': 'raw'}
    first = sprite_ui._follower_image('J')
    assert first == ('soft', 'raw')
    assert sprite_ui._follower_image('J') is first
    sprite_ui.map_mode = True
    assert sprite_ui._follower_image('J') == ('gray', ('soft', 'raw'))
    assert len(made) == 2


def test_follower_image_falls_back_without_image_data(sprite_ui):
    assert sprite_ui._follower_image('J') is sprite_ui._sprite_images['J']


@pytest.mark.parametrize('facing, won, filename', [
    ('up', True, 'slash.png'), ('down', True, 'slash-down.png'),
    ('left', True, 'slash-left.png'), ('right', True, 'slash-right.png'),
    ('left', False, 'splash.png'),
])
def test_combat_effect_slashes_the_way_the_player_attacked(sprite_ui, monkeypatch,
                                                           facing, won, filename):
    loaded = []
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.image.load',
                        lambda path: loaded.append(Path(path).name))
    monkeypatch.setattr(sprite_ui, '_play_effect', lambda seconds, create: None)
    sprite_ui.combat_effect_seconds = 0.3
    sprite_ui._attack_facing = facing
    sprite_ui.draw_combat_effect((4, 5), won)
    assert loaded == [filename]


def test_directional_slashes_are_bundled():
    effects = Path(sprite_funcs.__file__).parent / 'assets' / 'effects'
    for filename in sprite_effects.SLASH_FILES.values():
        assert (effects / filename).is_file(), filename


@pytest.fixture
def transition_ui(sprite_ui, monkeypatch):
    ui = sprite_ui
    ui._disc_image = SimpleNamespace(width=64, height=64)
    ui.field_height = 20
    ui.field_pixel_width = 26 * 13
    ui._landing_image = SimpleNamespace(width=450, height=600)
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.sprite.Sprite',
                        lambda picture, **kwargs: SimpleNamespace(image=picture, **kwargs))
    monkeypatch.setattr('arlq.sprite_funcs.pyglet.shapes.Rectangle',
                        lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs))
    return ui


def _figure_after(ui, kind, progress, fade_out=True):
    ui._create_floor_transition(kind, d.Player(3, 4, level=1, lp=d.LP_INIT), None)
    figure, cx, cy, picture, scale = ui._transition_parts['figure']
    base_y = ui.window_height - cy - (picture.height / 2
                                      - sprite_defs.SPRITE_GROUND_OFFSET_PIXELS) * scale
    ui._animate_floor_transition(kind, progress, fade_out)
    return figure, base_y, scale


STEP = sprite_effects.FLOOR_TRANSITION_STEP


@pytest.mark.parametrize('kind, start, end', [
    ('down', 0, -STEP), ('up', -STEP, 0), ('climb', -STEP, 0),
])
def test_floor_transition_moves_at_a_steady_speed(transition_ui, kind, start, end):
    ui = transition_ui
    fade = sprite_effects.FLOOR_TRANSITION_FADE
    for progress, moved in ((0.0, 0.0), (fade, 0.0), (0.5, 0.5), (1 - fade, 1.0), (1.0, 1.0)):
        figure, base_y, _ = _figure_after(ui, kind, progress)
        offset = (figure.y - base_y) / ui.cell_size_y
        assert offset == pytest.approx(start + (end - start) * moved)


@pytest.mark.parametrize('kind, sides', [
    ('down', (0, 0.5, 1, 0.5, 0)), ('up', (0, 0.5, 1, 0.5, 0)), ('climb', (0,) * 5),
    ('fall', (0,) * 5),
])
def test_stairs_go_right_then_left_like_ku(transition_ui, kind, sides):
    ui = transition_ui
    fade = sprite_effects.FLOOR_TRANSITION_FADE
    side = sprite_effects.FLOOR_TRANSITION_STAIRS_SIDE
    for moved, expected in zip((0, 0.25, 0.5, 0.75, 1), sides):
        progress = fade + (1 - 2 * fade) * moved
        figure, _, scale = _figure_after(ui, kind, progress)
        _, cx, _, picture, _ = ui._transition_parts['figure']
        centre = figure.x + picture.width * figure.scale / 2
        assert (centre - cx) / ui.cell_size_x == pytest.approx(expected * side)


def test_fall_keeps_its_feet_on_the_falling_point(transition_ui):
    ui = transition_ui
    figure, base_y, scale = _figure_after(ui, 'fall', 0.5)
    picture = ui._transition_parts['figure'][3]
    feet = figure.y + (picture.height / 2 - sprite_defs.SPRITE_GROUND_OFFSET_PIXELS) * figure.scale
    base_feet = base_y + (picture.height / 2 - sprite_defs.SPRITE_GROUND_OFFSET_PIXELS) * scale
    assert feet - base_feet == pytest.approx(
        -0.5 * sprite_effects.FLOOR_TRANSITION_FALL * ui.cell_size_y)
    # The fall covers twice the stairs' distance in the same time.
    assert sprite_effects.FLOOR_TRANSITION_FALL == 2 * sprite_effects.FLOOR_TRANSITION_STEP
    fade = sprite_effects.FLOOR_TRANSITION_FADE
    figure, _, scale = _figure_after(ui, 'fall', 1 - fade)
    assert figure.scale == pytest.approx(scale * sprite_effects.FLOOR_TRANSITION_FALL_SHRINK)


@pytest.mark.parametrize('progress, fade_out, opacity', [
    (0.0, True, 0), (0.075, True, 128), (0.5, True, 255),
    (0.925, True, 128), (1.0, True, 0), (1.0, False, 255),
])
def test_floor_transition_fades_in_and_out_over_fifteen_percent(transition_ui, progress,
                                                                 fade_out, opacity):
    ui = transition_ui
    _figure_after(ui, 'down', progress, fade_out)
    background = ui._transition_parts['fading'][0][0]
    assert abs(background.opacity - opacity) <= 1


def test_floor_transition_draws_the_new_floor_once_before_fading_out(transition_ui,
                                                                    monkeypatch):
    ui = transition_ui
    drawn, progresses = [], []
    monkeypatch.setattr(ui, 'draw_stage', lambda **view: drawn.append(view))
    monkeypatch.setattr(ui, '_animate_floor_transition',
                        lambda kind, progress, fade_out: progresses.append(fade_out))

    def play(seconds, create, update):
        create()
        for progress in (0.0, 0.5, 0.84, 0.86, 0.95, 1.0):
            update(progress)

    monkeypatch.setattr(ui, '_play_effect', play)
    ui._next_view = {'turn': 7}
    ui.draw_floor_transition('down', d.Player(3, 4, level=1, lp=d.LP_INIT))
    assert drawn == [{'turn': 7}]
    assert progresses == [False, False, False, True, True, True]


def test_floor_transition_without_a_next_view_keeps_the_scene(transition_ui, monkeypatch):
    ui = transition_ui
    fade_outs = []
    monkeypatch.setattr(ui, 'draw_stage', lambda **view: pytest.fail('no next view'))
    monkeypatch.setattr(ui, '_animate_floor_transition',
                        lambda kind, progress, fade_out: fade_outs.append(fade_out))
    monkeypatch.setattr(ui, '_play_effect',
                        lambda seconds, create, update: (create(), update(0.95)))
    ui.draw_floor_transition('down', d.Player(3, 4, level=1, lp=d.LP_INIT))
    assert fade_outs == [False]


def test_present_turn_offers_the_next_view_only_while_playing(sprite_ui, monkeypatch):
    seen = []
    monkeypatch.setattr(sprite_ui._presenter, 'play',
                        lambda ui, result, view: seen.append(ui._next_view) or True)
    sprite_ui.present_turn(_turn((0, 1)), {'turn': 3})
    assert seen == [{'turn': 3}]
    assert sprite_ui._next_view is None
