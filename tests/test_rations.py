"""Emergency continuation and confirmation controls."""
from collections import deque
from types import SimpleNamespace

import pytest
from pyglet.window import key

from arlq import defs as d, game_engine, display
from arlq.pyglet_funcs import PygletUI
from arlq.stage_types import Floor, ReplayContext
from arlq.arlq import GameConfig
from arlq import stage_replay


@pytest.fixture(autouse=True)
def enable_retained_ration_feature(monkeypatch):
    monkeypatch.setattr(d, 'RATIONS_ENABLED', True)


@pytest.mark.parametrize('decision,remaining,lp,commands', [
    (True, 2, 100, 0), (False, 3, 0, 1), (None, 3, 0, 0),
])
def test_collapse_requires_explicit_continuation(monkeypatch, decision, remaining, lp, commands):
    player = d.Player(2, 2, 7, 0)
    field = [[' '] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    floors = [Floor(field, [], [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)], (2, 2), (3, 3), None)]
    monkeypatch.setattr(game_engine, 'build_single_floor', lambda *_: (floors, player))
    prompts, game_over, draws = [], [], []
    ui = SimpleNamespace(
        draw_stage=lambda **kw: draws.append((kw['player'].lp, kw['player'].rations)),
        input_direction=lambda: None,
        confirm_ration=lambda p: prompts.append(p.rations) or decision,
        input_game_over=lambda: game_over.append(True),
    )
    game_engine.run_game(ui, '123', stage_num=1)
    assert prompts == [3]
    assert (player.lp, player.rations, player.level, player.x, player.y) == (lp, remaining, 7, 2, 2)
    assert len(game_over) == commands
    assert draws[0] == (0, 3)


@pytest.mark.parametrize('symbols,expected', [
    ([key.Y], True), ([key.N], False), ([key.RETURN], True),
    ([key.RIGHT, key.RETURN], False),
    ([key.RIGHT, key.LEFT, key.RETURN], True),
    ([key.ESCAPE], None), ([key.Q], None),
])
def test_gui_ration_keys(symbols, expected):
    ui = PygletUI.__new__(PygletUI)
    ui._initialize_state()
    ui._closed = False
    ui._key_queue = []
    ui.field_pixel_width = 800
    ui.field_height = 30
    ui.cell_size_y = 20
    ui.stop_movement_repeat = lambda: None
    ui._clear_drawables = lambda: None
    ui._draw_rect = lambda *a: None
    ui._draw_text = lambda *a, **kw: None
    ui._text_width = lambda text, **kw: len(text) * 8
    ui._flip = lambda: None
    ui._pump = lambda: None
    events = deque((symbol, 0) for symbol in symbols)
    ui._next_key_event = events.popleft
    assert ui.confirm_ration(d.Player(2, 2, 1, 0)) is expected


def test_replay_applies_ration_before_next_operation(monkeypatch):
    player = d.Player(2, 2, 1, 0)
    floor = SimpleNamespace(up=(2, 2))
    monkeypatch.setattr(stage_replay, 'build', lambda *_: ([floor], player))
    monkeypatch.setattr(game_engine, 'observe_world', lambda *_: None)
    observed = []
    monkeypatch.setattr(game_engine, '_step', lambda *a, **kw: observed.append((a[2].lp, a[2].rations)))
    replay = ReplayContext(3, 123, GameConfig(), operations=[(1, 0)], ration_uses={0})
    stage_replay.replay_to_operation(replay, 1)
    assert observed == [(100, 2)]
    assert player.lp == 100 - d.movement_lp_cost(player)


def test_sprite_status_uses_player_argument_and_dims_consumed_food(monkeypatch):
    from arlq.sprite_funcs import SpriteUI
    monkeypatch.setattr(PygletUI, 'draw_status_bar', lambda *a, **kw: None)
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._hud_row_height = 20
    ui.window_width = 800
    ui.field_height = 30
    ui.cell_size_y = 20
    pictures = []
    ui._draw_ration_image = lambda *a: pictures.append(a)
    player = d.Player(2, 2, 1, 0)
    player.rations = 2
    ui.draw_status_bar(17, player, 1, '', False, None)
    assert [picture[0] for picture in pictures] == ['hardtack', 'jerky', 'hyorogan']
    assert [picture[-1] for picture in pictures] == [True, False, False]


@pytest.mark.parametrize('text,expected', [('y', True), ('n', False), ('q', None), ('\x1b', None)])
def test_terminal_ration_direct_keys(text, expected):
    from arlq.blessed_funcs import BlessedUI
    from blessed.keyboard import Keystroke
    ui = BlessedUI.__new__(BlessedUI)
    ui.term = SimpleNamespace(home='', clear='', normal='', width=80, height=30,
                              move_xy=lambda *a: '', length=len, KEY_ESCAPE=27)
    ui._wait_for_terminal_size = lambda: None
    ui._style = lambda text, **kw: text
    ui._read_key = lambda: Keystroke(text, code=27 if text == '\x1b' else None)
    assert ui.confirm_ration(d.Player(2, 2, 1, 0)) is expected


def test_all_three_rations_then_final_game_over(monkeypatch):
    player = d.Player(2, 2, 7, 0)
    field = [[' '] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    floors = [Floor(field, [], [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)], (2, 2), (3, 3), None)]
    monkeypatch.setattr(game_engine, 'build_single_floor', lambda *_: (floors, player))
    prompts = []
    def collapse(*args, **kw):
        player.lp = 0
    monkeypatch.setattr(game_engine, '_step', collapse)
    ui = SimpleNamespace(
        draw_stage=lambda **kw: None, input_direction=lambda: (1, 0),
        confirm_ration=lambda p: prompts.append(d.RATIONS[3 - p.rations]) or True,
        input_game_over=lambda: None,
    )
    game_engine.run_game(ui, '123', stage_num=1)
    assert prompts == ['hardtack', 'jerky', 'hyorogan']
    assert player.rations == 0


def test_disabled_rations_end_game_without_prompt(monkeypatch):
    monkeypatch.setattr(d, 'RATIONS_ENABLED', False)
    player = d.Player(2, 2, 7, 0)
    field = [[' '] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    floors = [Floor(field, [], [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)], (2, 2), (3, 3), None)]
    monkeypatch.setattr(game_engine, 'build_single_floor', lambda *_: (floors, player))
    def unexpected_prompt(*args):
        pytest.fail('Disabled rations must not offer continuation')
    ended = []
    ui = SimpleNamespace(
        draw_stage=lambda **kw: None, confirm_ration=unexpected_prompt,
        input_game_over=lambda: ended.append(True),
    )
    game_engine.run_game(ui, '123', stage_num=1)
    assert ended == [True]
    assert player.lp == 0
    assert player.rations == 3


def test_disabled_rations_hide_sprite_images(monkeypatch):
    from arlq.sprite_funcs import SpriteUI
    monkeypatch.setattr(d, 'RATIONS_ENABLED', False)
    monkeypatch.setattr(PygletUI, 'draw_status_bar', lambda *a, **kw: None)
    ui = SpriteUI.__new__(SpriteUI)
    ui._initialize_state()
    ui._draw_ration_image = lambda *a: pytest.fail('Disabled ration image displayed')
    ui.draw_status_bar(0, d.Player(2, 2, 1, 100), 1, '', False)
