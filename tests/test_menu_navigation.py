"""Keyboard navigation checks for the GUI menus."""

import json
from types import SimpleNamespace

import pytest
from collections import deque

from pyglet.window import key

from arlq import defs, i18n
from arlq.pyglet_funcs import PygletUI
from arlq.blessed_funcs import BlessedUI
from blessed.keyboard import Keystroke


@pytest.fixture(autouse=True)
def english_menu_labels(monkeypatch):
    monkeypatch.setattr(i18n, '_lang', 'en')


def _menu_ui(monkeypatch, events):
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui._closed = False
    ui._menu_active = False
    ui._menu_font_resize_pending = False
    ui._menu_scale = 1.0
    ui._menu_cell_size_x = 13
    ui._key_queue = []
    ui._escape_key_held = False
    ui.joystick = None
    ui.scale = 1.0
    ui.key_repeat_interval = None
    ui.auto_repeat_stop_enabled = True
    ui.cell_size_x = 13
    ui._events = deque(events)
    ui._pump = lambda: None
    ui._next_key_event = lambda: ui._events.popleft() if ui._events else None
    ui._discard_queued_key = lambda _symbol: None
    ui._clear_drawables = lambda: None
    ui._draw_text = lambda *_args, **_kwargs: None
    ui._text_width = lambda *_args, **_kwargs: 0
    ui._flip = lambda: None
    ui.quit_called = False
    ui.quit = lambda: setattr(ui, "quit_called", True)
    monkeypatch.setattr("arlq.pyglet_funcs.time.sleep", lambda *_args: None)
    return ui


def test_escape_from_settings_returns_to_stage_selection(monkeypatch):
    """Esc cancels Settings and leaves the app ready for a stage choice."""
    ui = _menu_ui(
        monkeypatch,
        [(key.S, 0), (key.ESCAPE, 0), (key._1, 0)],
    )

    selected_stage = ui.select_stage()

    assert selected_stage == 1
    assert ui.quit_called is False
    assert ui._closed is False


def test_entering_settings_from_stage_list_and_escape_keeps_app_open(monkeypatch):
    """Arrow navigation and Enter reach Settings; Esc returns to the list."""
    events = [(key.DOWN, 0)] * ((len(defs.PUBLIC_STAGE_NUMBERS) + 1) // 2)
    events.extend([(key.RETURN, 0), (key.ESCAPE, 0), (key._1, 0)])
    ui = _menu_ui(monkeypatch, events)

    selected_stage = ui.select_stage()

    assert selected_stage == 1
    assert ui.quit_called is False
    assert ui._closed is False


def test_stage_menu_places_six_stages_in_two_columns(monkeypatch):
    ui = _menu_ui(monkeypatch, [(key.ESCAPE, 0)])
    drawn = {}
    ui._draw_text = lambda pos, text, *args, **kwargs: drawn.setdefault(text.strip(), pos)
    assert ui.select_stage() == 0
    for left, right in ((1, 2), (3, 4), (5, 6)):
        left_pos = drawn['> Stage 1' if left == 1 else f'Stage {left}']
        right_pos = drawn[f'Stage {right}']
        assert left_pos[1] == right_pos[1]
        assert left_pos[0] < right_pos[0]
    assert drawn['> Stage 1'][1] < drawn['Stage 3'][1] < drawn['Stage 5'][1]


@pytest.mark.parametrize('arrows,expected', [
    ([key.RIGHT], 2), ([key.DOWN], 3),
    ([key.RIGHT, key.DOWN, key.DOWN], 6),
    ([key.DOWN, key.RIGHT, key.LEFT], 3),
    ([key.LEFT], 1),
])
def test_stage_grid_arrow_navigation(monkeypatch, arrows, expected):
    ui = _menu_ui(monkeypatch, [(symbol, 0) for symbol in arrows + [key.RETURN]])
    assert ui.select_stage() == expected


def test_stage_grid_gamepad_moves_right(monkeypatch):
    ui = _menu_ui(monkeypatch, [None, (key.RETURN, 0)])
    ui.controller = object()
    ui.gamepad_previous_direction = None
    ui._controller_direction = lambda controller: (1, 0)
    assert ui.select_stage() == 2


@pytest.mark.parametrize('arrows,expected', [
    (['KEY_RIGHT'], 2), (['KEY_DOWN'], 3),
    (['KEY_RIGHT', 'KEY_DOWN', 'KEY_DOWN'], 6),
    (['KEY_DOWN', 'KEY_RIGHT', 'KEY_LEFT'], 3),
    (['KEY_UP'], 0),
])
def test_terminal_stage_grid_layout_and_navigation(capsys, arrows, expected):
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(
        home='', clear='', normal='', bold=lambda text: text, yellow=lambda text: text,
        move_xy=lambda x, y: f'<{x},{y}>', KEY_ESCAPE=27,
    )
    ui._wait_for_terminal_size = lambda: None
    events = deque([Keystroke('', name=name) for name in arrows] + [Keystroke('\n')])
    ui._read_key = events.popleft
    assert ui.select_stage() == expected
    output = capsys.readouterr().out
    for x, y, label in [(4, 6, '> Stage 1'), (26, 6, '  Stage 2'),
                         (4, 7, '  Stage 3'), (26, 7, '  Stage 4'),
                         (4, 8, '  Stage 5'), (26, 8, '  Stage 6')]:
        assert f'<{x},{y}>{label}' in output


def test_settings_can_disable_and_persist_automatic_repeat_stop(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: settings_path)
    ui = _menu_ui(
        monkeypatch,
        [(key.DOWN, 0), (key.DOWN, 0), (key.RIGHT, 0), (key.RETURN, 0)],
    )
    ui.set_scale = lambda scale: setattr(ui, "scale", scale)

    ui.settings_menu()

    assert ui.auto_repeat_stop_enabled is False
    assert json.loads(settings_path.read_text()) == {
        "key_repeat_interval": None,
        "auto_repeat_stop_enabled": False,
        "combat_effect_seconds": 0.3,
    }


@pytest.mark.parametrize("seconds", defs.COMBAT_EFFECT_SECONDS_CHOICES)
def test_settings_select_and_reload_combat_effect_duration(monkeypatch, tmp_path, seconds):
    from arlq.settings import combat_effect_seconds, load_settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"scale": 1.5}))
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    events = [(key.DOWN, 0)] * 3 + [(key.LEFT, 0)] * 5
    events += [(key.RIGHT, 0)] * round(seconds * 10) + [(key.RETURN, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert ui.combat_effect_seconds == seconds
    assert combat_effect_seconds(load_settings(path)) == seconds
    assert load_settings(path)["scale"] == 1.5


def test_cancel_combat_effect_duration_keeps_saved_value(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    original = '{"combat_effect_seconds": 0.3}'
    path.write_text(original)
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    ui = _menu_ui(monkeypatch, [(key.DOWN, 0)] * 3 + [(key.RIGHT, 0), (key.ESCAPE, 0)])
    ui.combat_effect_seconds = 0.3

    ui.settings_menu()

    assert ui.combat_effect_seconds == 0.3
    assert path.read_text() == original


@pytest.mark.parametrize("submenu", ["sprites", "gamepad"])
@pytest.mark.parametrize("use_gamepad", [False, True])
def test_settings_opens_submenus_with_confirm(monkeypatch, submenu, use_gamepad):
    events = [(key.DOWN, 0)] * (3 if submenu == "sprites" else 4)
    events += [None if use_gamepad else (key.RETURN, 0), (key.ESCAPE, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.supports_floor_transition = True
    ui.controller = object()
    ui._gamepad_is_connected = lambda: True
    ui._controller_direction = lambda controller: (0, 0)
    opened = []
    ui.sprite_settings_menu = lambda *args: opened.append("sprites")
    ui.gamepad_button_settings_menu = lambda: opened.append("gamepad")
    if use_gamepad:
        original_next = ui._next_key_event

        def next_event():
            event = original_next()
            ui._gamepad_pressed_buttons = {0} if event is None else set()
            return event

        ui._next_key_event = next_event

    ui.settings_menu()

    assert opened == [submenu]


@pytest.mark.parametrize("cancel_submenu,cancel_parent,expected", [
    (False, False, 0.4), (True, False, 0.3), (False, True, 0.3),
])
def test_sprite_effect_submenu_applies_or_cancels(monkeypatch, tmp_path, cancel_submenu,
                                                 cancel_parent, expected):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    events = [(key.DOWN, 0)] * 3 + [(key.RETURN, 0), (key.RIGHT, 0)]
    events += [(key.ESCAPE if cancel_submenu else key.RETURN, 0)]
    if not cancel_parent:
        events.append((key.UP, 0))
    events += [(key.ESCAPE if cancel_parent else key.RETURN, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.supports_floor_transition = True
    ui.supports_idle_bob = True
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert ui.combat_effect_seconds == expected
    if cancel_parent:
        assert not path.exists()
    else:
        assert json.loads(path.read_text())["combat_effect_seconds"] == expected


@pytest.mark.parametrize("value", [None, True, "0.1", -0.1, 0.6, 0.25, float("nan")])
def test_invalid_combat_effect_duration_uses_default(value):
    from arlq.settings import combat_effect_seconds

    assert combat_effect_seconds({"combat_effect_seconds": value}) == 0.3


@pytest.mark.parametrize("presses, seconds", [(0, 0.5), (-5, 0.0), (5, 1.0), (-2, 0.3)])
def test_sprite_settings_select_and_reload_floor_transition_duration(
    monkeypatch, tmp_path, presses, seconds
):
    from arlq.settings import floor_transition_seconds, load_settings

    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    arrow = key.RIGHT if presses > 0 else key.LEFT
    events = [(key.DOWN, 0)] * 3 + [(key.RIGHT, 0), (key.DOWN, 0)]
    events += [(arrow, 0)] * abs(presses) + [(key.RETURN, 0), (key.UP, 0), (key.RETURN, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.supports_floor_transition = True
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert ui.floor_transition_seconds == seconds
    assert floor_transition_seconds(load_settings(path)) == seconds
    assert load_settings(path)["combat_effect_seconds"] == 0.3


def test_plain_gui_settings_have_no_floor_transition_row(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    # Five Downs (past the reset row) wrap back to the scale row without a gamepad.
    ui = _menu_ui(monkeypatch, [(key.DOWN, 0)] * 5 + [(key.RIGHT, 0), (key.RETURN, 0)])
    scales = []
    ui.set_scale = scales.append

    ui.settings_menu()

    assert scales == [1.25]
    assert "floor_transition_seconds" not in json.loads(path.read_text())


CHANGED_SETTINGS = {
    "scale": 2.0,
    "key_repeat_interval": 0.3,
    "auto_repeat_stop_enabled": False,
    "combat_effect_seconds": 0.5,
    "floor_transition_seconds": 1.0,
    "idle_bob_enabled": False,
    "move_glide_enabled": False,
    "gamepad_help_button": 5,
    "gamepad_preview_button": 4,
    "gamepad_preview_mode": "toggle",
}


def _changed_sprite_menu_ui(monkeypatch, tmp_path, events, controller=False):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(CHANGED_SETTINGS))
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    ui = _menu_ui(monkeypatch, events)
    ui.supports_floor_transition = True
    ui.supports_idle_bob = True
    ui.supports_move_glide = True
    ui.scale = ui._menu_scale = 2.0
    ui.key_repeat_interval = 0.3
    ui.auto_repeat_stop_enabled = False
    ui.combat_effect_seconds = 0.5
    ui.floor_transition_seconds = 1.0
    ui.idle_bob_enabled = False
    ui.move_glide_enabled = False
    ui.gamepad_help_button, ui.gamepad_preview_button = 5, 4
    ui.gamepad_preview_mode = "toggle"
    ui._gamepad_preview_held = False
    if controller:
        ui.controller = object()
        ui._gamepad_is_connected = lambda: True
        ui._controller_direction = lambda controller: (0, 0)
    scales = []
    ui.set_scale = lambda scale: (scales.append(scale), setattr(ui, "scale", scale))
    return ui, path, scales


@pytest.mark.parametrize("controller", [False, True])
def test_reset_row_restores_every_setting_to_its_default(monkeypatch, tmp_path, controller):
    from arlq import pyglet_funcs
    from arlq.settings import (combat_effect_seconds, floor_transition_seconds,
                               idle_bob_enabled, load_settings, move_glide_enabled)

    # The reset row is last; it shows the defaults and returns to the top
    # row, where Enter applies them.
    downs = 5 if controller else 4
    events = [(key.DOWN, 0)] * downs + [(key.RETURN, 0), (key.RETURN, 0)]
    ui, path, scales = _changed_sprite_menu_ui(monkeypatch, tmp_path, events, controller)

    ui.settings_menu()

    saved = load_settings(path)
    assert scales == [pyglet_funcs.DEFAULT_UI_SCALE]
    assert ui.key_repeat_interval is None and saved["key_repeat_interval"] is None
    assert ui.auto_repeat_stop_enabled is True and saved["auto_repeat_stop_enabled"] is True
    assert ui.combat_effect_seconds == combat_effect_seconds(saved) == defs.COMBAT_EFFECT_SECONDS
    assert (ui.floor_transition_seconds == floor_transition_seconds(saved)
            == defs.FLOOR_TRANSITION_SECONDS)
    assert ui.idle_bob_enabled is idle_bob_enabled(saved) is True
    assert ui.move_glide_enabled is move_glide_enabled(saved) is True
    assert (ui.gamepad_help_button, ui.gamepad_preview_button, ui.gamepad_preview_mode) == (
        pyglet_funcs.DEFAULT_GAMEPAD_HELP_BUTTON,
        pyglet_funcs.DEFAULT_GAMEPAD_PREVIEW_BUTTON,
        pyglet_funcs.DEFAULT_GAMEPAD_PREVIEW_MODE,
    )
    assert pyglet_funcs.load_gamepad_bindings() == (
        pyglet_funcs.DEFAULT_GAMEPAD_HELP_BUTTON,
        pyglet_funcs.DEFAULT_GAMEPAD_PREVIEW_BUTTON,
        pyglet_funcs.DEFAULT_GAMEPAD_PREVIEW_MODE,
    )


def test_cancel_after_reset_keeps_saved_settings(monkeypatch, tmp_path):
    events = [(key.DOWN, 0)] * 4 + [(key.RETURN, 0), (key.ESCAPE, 0)]
    ui, path, scales = _changed_sprite_menu_ui(monkeypatch, tmp_path, events)
    original = path.read_text()

    ui.settings_menu()

    assert path.read_text() == original
    assert scales == []
    assert (ui.key_repeat_interval, ui.move_glide_enabled, ui.gamepad_help_button) == (
        0.3, False, 5)


@pytest.mark.parametrize("value", [None, True, "0.1", -0.1, 1.1, 0.25, float("nan")])
def test_invalid_floor_transition_duration_uses_default(value):
    from arlq.settings import floor_transition_seconds

    assert floor_transition_seconds({"floor_transition_seconds": value}) == 0.5


def test_zero_duration_skips_effect_in_all_frontends():
    from arlq.blessed_funcs import BlessedUI
    from arlq.sprites.sprite_funcs import SpriteUI

    for frontend in (PygletUI, SpriteUI, BlessedUI):
        ui = frontend.__new__(frontend)
        ui.combat_effect_seconds = 0
        # No window or terminal is available; zero must return before rendering.
        ui.draw_combat_effect((0, 0), True)
        ui.draw_combat_effect((0, 0), False)


def test_terminal_strength_labels_are_outside_field(monkeypatch):
    from types import SimpleNamespace
    from arlq import defs as d, display
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(home='', clear='', normal='', move_xy=lambda x, y: f'<{x},{y}>')
    ui.dots = False
    ui._style = lambda text, *args, **kwargs: text
    monkeypatch.setattr(display, 'build_strength_column', lambda *_: [('b\u0027', False), ('@', True)])
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    seen = [[0] * d.FIELD_WIDTH for _ in field]
    player = d.Player(2, 2, 1, 100)
    output = ui._draw_stage([player], field, seen, seen, set(), stage_roster=[])
    assert f'<{d.FIELD_WIDTH + d.FIELD_SIDEBAR_GAP},0>b\u0027' in output
    assert f'<{d.FIELD_WIDTH + d.FIELD_SIDEBAR_GAP + 1},1>@' in output


def test_terminal_boss_route_only_marks_explored_floor(monkeypatch):
    from arlq import defs as d, display
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(home='', clear='', normal='', move_xy=lambda x, y: f'<{x},{y}>')
    ui.dots = False
    ui._style = lambda text, color=None, *args, **kwargs: f'[{color}:{text}]'
    monkeypatch.setattr(display, 'build_strength_column', lambda *_: [])
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    seen = [[0] * d.FIELD_WIDTH for _ in field]
    seen[2][3] = 1
    player = d.Player(2, 2, 1, 100)
    decor = [[d.DECOR_NONE] * d.FIELD_WIDTH for _ in field]
    decor[2][3] = decor[2][4] = d.DECOR_BOSS_ROUTE
    output = ui._draw_stage([player], field, seen, seen, set(), stage_roster=[],
                            decor=decor)
    assert '<3,2>[yellow:.]' in output
    assert '<4,2>[yellow:.]' not in output


@pytest.mark.parametrize('dots', [False, True])
@pytest.mark.parametrize('monochrome', [False, True])
def test_terminal_marks_explored_golem_rubble(monkeypatch, dots, monochrome):
    from arlq import defs as d, display
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(home='', clear='', normal='', move_xy=lambda x, y: f'<{x},{y}>')
    ui.dots = dots
    ui._style = lambda text, *args, **kwargs: text
    monkeypatch.setattr(display, 'build_strength_column', lambda *_: [])
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[2][3] = field[2][4] = d.CHAR_GOLEM_WALL
    field[2][5] = d.CHAR_WALL
    seen = [[0] * d.FIELD_WIDTH for _ in field]
    seen[2][3] = seen[2][5] = 1
    player = d.Player(2, 2, 1, 100)
    output = ui._draw_stage([player], field, seen, seen, set(), stage_roster=[],
                            monochrome=monochrome)
    assert '<3,2>+' in output
    assert '<4,2>+' not in output
    assert f'<5,2>{d.CHAR_WALL}' in output


@pytest.mark.parametrize('visible', [False, True])
def test_gui_marks_explored_golem_rubble(visible):
    from arlq import defs as d
    from arlq import pyglet_funcs
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui.map_mode = False
    ui._clear_drawables = lambda: None
    ui._field_draw_columns = lambda width: range(width)
    tiles, labels = [], []
    ui._draw_tile = lambda x, y, color, *_: tiles.append(color)

    class Drawn(Exception):
        pass

    def capture(pos, char, color, bold=False):
        labels.append((pos, char, color))
        raise Drawn

    ui._draw_field_text = capture
    player = d.Player(0, 0, 1, 100)
    with pytest.raises(Drawn):
        ui.draw_stage(turn=0, player=player, entities=[], field=[[d.CHAR_GOLEM_WALL]],
                      cur_torched=[[int(visible)]], torched=[[1]], known_types=set(),
                      show_entities=False)
    color = pyglet_funcs.COLOR_MAP[pyglet_funcs.CI_GREEN]
    assert labels == [((0, 0), '+', color if visible else ui._dim_color(color))]
    assert tiles == [pyglet_funcs.VISIBLE_WALL if visible else pyglet_funcs.WALL]


@pytest.mark.parametrize('dots', [False, True])
@pytest.mark.parametrize('protection,expected', [
    ('none', ('black', False, 'red')),
    ('amulet', ('red', True, None)),
    ('cursed_amulet', ('black', False, 'red')),
    ('guardian', ('red', False, None)),
    ('guardian_amulet', ('red', True, None)),
    ('guardian_cursed', ('red', False, None)),
])
def test_terminal_dims_protected_barriers(monkeypatch, dots, protection, expected):
    from arlq import defs as d, display
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(home='', clear='', normal='', move_xy=lambda x, y: f'<{x},{y}>')
    ui.dots = dots
    ui._style = lambda text, color=None, bold=False, dim=False, bg=None: f'[{text}:{color}:{dim}:{bg}]'
    monkeypatch.setattr(display, 'build_strength_column', lambda *_: [])
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[2][3], field[2][4] = d.CHAR_BARRIER, d.CHAR_CALTROP
    seen = [[1] * d.FIELD_WIDTH for _ in field]
    player = d.Player(2, 2, 1, 100)
    if protection in ('amulet', 'cursed_amulet', 'guardian_amulet', 'guardian_cursed'):
        player.elf_stage_flags |= d.ELF_STAGE_H_FLAG
    if protection in ('cursed_amulet', 'guardian_cursed'):
        player.item = d.ITEM_SWORD_CURSED
    if protection in ('guardian', 'guardian_amulet', 'guardian_cursed'):
        player.members.append(d.PartyMember(2, 2, d.MEMBER_GUARDIAN))
    output = ui._draw_stage([player], field, seen, seen, set(), stage_roster=[])
    assert f'<3,2>[=:{expected[0]}:{expected[1]}:{expected[2]}]' in output
    assert f'<4,2>[x:magenta:False:' in output

@pytest.mark.parametrize('protection,background,foreground,dimmed', [
    ('none', (220, 82, 82), (0, 0, 0), False),
    ('guardian', None, (220, 82, 82), False),
    ('amulet', None, (110, 41, 41), True),
])
def test_gui_barrier_colors(monkeypatch, protection, background, foreground, dimmed):
    from arlq import defs as d
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui.map_mode = False
    ui._clear_drawables = lambda: None
    ui._field_draw_columns = lambda width: range(width)
    tiles, labels = [], []
    ui._draw_tile = lambda x, y, color, *_: tiles.append(color)

    class Drawn(Exception):
        pass

    def capture(pos, char, color, bold=False):
        labels.append((color, bold))
        raise Drawn

    ui._draw_field_text = capture
    player = d.Player(0, 0, 1, 100)
    if protection == 'guardian':
        player.members.append(d.PartyMember(0, 0, d.MEMBER_GUARDIAN))
    if protection == 'amulet':
        player.elf_stage_flags |= d.ELF_STAGE_H_FLAG
    with pytest.raises(Drawn):
        ui.draw_stage(turn=0, player=player, entities=[], field=[[d.CHAR_BARRIER]],
                      cur_torched=[[1]], torched=[[1]], known_types=set(),
                      show_entities=False)
    if background is not None:
        assert tiles[0] == background
    else:
        assert tiles[0] != (220, 82, 82)
    assert labels == [(foreground, not dimmed)]


@pytest.mark.parametrize("presses, enabled", [(0, True), (1, False), (2, True)])
def test_sprite_settings_toggle_and_reload_character_bobbing(
    monkeypatch, tmp_path, presses, enabled
):
    from arlq.settings import idle_bob_enabled, load_settings

    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    events = [(key.DOWN, 0)] * 3 + [(key.RIGHT, 0)] + [(key.DOWN, 0)] * 2
    events += [(key.RIGHT, 0)] * presses + [(key.RETURN, 0), (key.UP, 0), (key.RETURN, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.supports_floor_transition = True
    ui.supports_idle_bob = True
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert ui.idle_bob_enabled is enabled
    assert idle_bob_enabled(load_settings(path)) is enabled


@pytest.mark.parametrize("presses, enabled", [(0, True), (1, False), (2, True)])
def test_sprite_settings_toggle_and_reload_smooth_movement(
    monkeypatch, tmp_path, presses, enabled
):
    from arlq.settings import load_settings, move_glide_enabled

    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    events = [(key.DOWN, 0)] * 3 + [(key.RIGHT, 0)] + [(key.DOWN, 0)] * 3
    events += [(key.RIGHT, 0)] * presses + [(key.RETURN, 0), (key.UP, 0), (key.RETURN, 0)]
    ui = _menu_ui(monkeypatch, events)
    ui.supports_floor_transition = True
    ui.supports_idle_bob = True
    ui.supports_move_glide = True
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert ui.move_glide_enabled is enabled
    assert ui.idle_bob_enabled is True
    assert move_glide_enabled(load_settings(path)) is enabled


def test_plain_gui_settings_do_not_save_character_bobbing(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.pyglet_funcs._settings_path", lambda: path)
    ui = _menu_ui(monkeypatch, [(key.RETURN, 0)])
    ui.set_scale = lambda scale: None

    ui.settings_menu()

    assert "idle_bob_enabled" not in json.loads(path.read_text())
    assert "move_glide_enabled" not in json.loads(path.read_text())


@pytest.mark.parametrize("value", [None, 0, 1, "true", "off"])
def test_invalid_smooth_movement_uses_default(value):
    from arlq.settings import move_glide_enabled

    assert move_glide_enabled({"move_glide_enabled": value}) is True


@pytest.mark.parametrize("value", [None, 0, 1, "true", "off"])
def test_invalid_character_bobbing_uses_default(value):
    from arlq.settings import idle_bob_enabled

    assert idle_bob_enabled({"idle_bob_enabled": value}) is True
