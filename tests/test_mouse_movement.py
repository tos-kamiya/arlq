from types import SimpleNamespace

import pytest
from pyglet.window import mouse

from arlq import defs as d
from arlq import game_engine
from arlq.arlq import GameConfig
from arlq.game_session import GameSession, TurnResult
from arlq.pyglet_funcs import PygletUI
from arlq.stage_types import Floor


def mouse_ui(monkeypatch):
    ui = PygletUI.__new__(PygletUI)
    ui._stage_input_active = True
    ui._menu_active = False
    ui._mouse_move_target = None
    ui._mouse_expected_position = None
    ui._next_mouse_move_at = 0
    ui._path_hover_dirty = False
    ui.key_repeat_interval = None
    ui.cell_size_x = ui.cell_size_y = 10
    ui.field_width, ui.field_height = 7, 5
    ui.window_height = 50
    player = SimpleNamespace(x=1, y=2)
    field = [list('#######'), list('#     #'), list('#     #'),
             list('#     #'), list('#######')]
    seen = [[1] * 7 for _ in field]
    ui._path_stage_draw = dict(player=player, field=field, torched=seen, cur_torched=seen)
    monkeypatch.setattr('arlq.pyglet_funcs.time.monotonic', lambda: 1.0)
    return ui, player, field, seen


def test_click_stops_when_revealed_wall_changes_route(monkeypatch):
    ui, player, field, seen = mouse_ui(monkeypatch)
    seen[2][3] = 0
    seen[2][4] = 0
    field[2][3] = '#'
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    assert ui.input_was_repeat and ui.input_was_mouse
    player.x = 2
    ui.finish_mouse_step(TurnResult(True, None, False, 0, 0), player)
    assert ui._mouse_move_step() is None  # movement interval
    seen[2][3] = 1
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() is None
    assert ui._mouse_move_target is None


def test_click_continues_if_exploration_does_not_change_route(monkeypatch):
    ui, player, field, seen = mouse_ui(monkeypatch)
    seen[2][3] = seen[2][4] = 0
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    seen[2][3] = 1
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() == (1, 0)


def test_click_stops_when_newly_known_route_takes_priority(monkeypatch):
    ui, player, field, seen = mouse_ui(monkeypatch)
    seen[2][3] = seen[2][4] = 0
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    seen[2][4] = 1
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() is None
    assert ui._mouse_move_target is None


def test_click_can_restart_with_new_route_after_exploration(monkeypatch):
    ui, player, field, seen = mouse_ui(monkeypatch)
    seen[2][3] = seen[2][4] = 0
    field[2][3] = d.CHAR_WALL
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    seen[2][3] = 1
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() is None
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (0, -1)


def test_mouse_move_stops_on_repeat_stop_failed_step_or_floor_change(monkeypatch):
    ui, player, _, _ = mouse_ui(monkeypatch)
    for result in (TurnResult(True, None, True, 0, 0),
                   TurnResult(False, None, False, 0, 0),
                   TurnResult(True, None, False, 0, 1),
                   TurnResult(True, None, False, 0, 0)):
        ui._mouse_move_target = (4, 2)
        ui._mouse_expected_position = (2, 2)
        ui.finish_mouse_step(result, player)
        assert ui._mouse_move_target is None


def test_click_outside_or_in_other_floor_is_ignored(monkeypatch):
    ui, _, _, _ = mouse_ui(monkeypatch)
    ui._path_mouse_press(75, 25, mouse.LEFT, 0)
    assert ui._mouse_move_target is None
    ui._path_stage_draw['floor_view'] = True
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_target is None


def test_mouse_move_forces_repeat_stop_when_setting_is_off(monkeypatch):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    floor = Floor(field, [], [[1] * d.FIELD_WIDTH for _ in field], (1, 1), (4, 4), None)
    player = d.Player(2, 2, 100, 90)
    monkeypatch.setattr(game_engine, 'build_single_floor', lambda *_: ([floor], player))
    prechecks = []
    monkeypatch.setattr(game_engine, 'should_stop_movement_repeat',
                        lambda *_args, **_kwargs: prechecks.append(True) or True)

    class UI:
        auto_repeat_stop_enabled = False
        input_was_repeat = True
        input_was_mouse = True

        def __init__(self):
            self.moves = iter([(1, 0), None])
            self.results = []

        def draw_stage(self, **kwargs):
            pass

        def input_direction(self):
            return next(self.moves)

        def finish_mouse_step(self, result, player):
            self.results.append(result)

        def stop_movement_repeat(self):
            pass

    ui = UI()
    game_engine.run_game(ui, 'test', config=GameConfig(), stage_num=1)
    assert prechecks == [True]
    assert ui.results[0].stop_repeat and not ui.results[0].consumed
    assert (player.x, player.y) == (2, 2)


@pytest.fixture
def session(monkeypatch):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    floor = Floor(field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (4, 4), None)
    player = d.Player(2, 2, 100, 90)
    monkeypatch.setattr(game_engine, 'build_single_floor', lambda *_: ([floor], player))
    return GameSession(1, seed_str='mouse-test')


@pytest.mark.parametrize('terrain', [d.CHAR_WALL, d.CHAR_GOLEM_WALL, d.CHAR_STAIRS_DOWN,
                                    d.CHAR_CALTROP, d.CHAR_BARRIER, d.CHAR_COLLAPSE])
def test_mouse_stops_before_actual_non_floor_even_if_unexplored(session, terrain):
    session.floors[0].field[2][3] = terrain
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.stop_repeat and not result.consumed
    assert (session.player.x, session.player.y, session.turn) == (2, 2, 0)


def test_mouse_ignores_untriggered_collapse_at_precheck(session, monkeypatch):
    current = session.floors[0]
    current.entities.append(d.Collapse(3, 2))
    current.seen[2][3] = 1
    monkeypatch.setattr(game_engine, '_process_multi_floor_turn',
                        lambda move, floors, player, *_args, **_kwargs: setattr(player, 'x', 3))
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.consumed
    assert session.player.x == 3


@pytest.mark.parametrize('kind', ['treasure', 'mimic'])
def test_mouse_does_not_stop_for_undisplayed_entity(session, monkeypatch, kind):
    entity = (d.Treasure(3, 2, 'W') if kind == 'treasure'
              else d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['M']))
    if kind == 'mimic':
        entity.active = False
    session.floors[0].entities.append(entity)
    monkeypatch.setattr(game_engine, '_process_multi_floor_turn',
                        lambda move, floors, player, *_args, **_kwargs: setattr(player, 'x', 3))
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.consumed and not result.stop_repeat


@pytest.mark.parametrize('damage,stops', [(0, False), (0.5, True)])
def test_mouse_stops_for_damage_but_not_normal_movement_cost(session, monkeypatch, damage, stops):
    def step(move, floors, player, *_args, **_kwargs):
        player.x += 1
        player.lp -= damage

    monkeypatch.setattr(game_engine, '_process_multi_floor_turn', step)
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.consumed and result.stop_repeat is stops


def test_mouse_stop_on_floor_change_even_without_other_stop_reason(session, monkeypatch):
    def step(move, floors, player, floor, *_args, **_kwargs):
        player.x += 1
        floor[0] = 1

    session.floors.append(session.floors[0])
    monkeypatch.setattr(game_engine, '_process_multi_floor_turn', step)
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.consumed and result.stop_repeat


def test_click_known_wall_with_pegasus_approaches_then_jumps(monkeypatch):
    ui, player, field, seen = mouse_ui(monkeypatch)
    player.fairy = SimpleNamespace(tribe=SimpleNamespace(char=d.CHAR_PEGASUS))
    field[2][3] = d.CHAR_WALL
    ui._path_mouse_press(35, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() == (1, 0)
    assert ui.input_mouse_target == (3, 2)
    assert ui._mouse_expected_position == (3, 2)


def test_click_unexplored_wall_uses_the_same_target_handling(monkeypatch):
    ui, player, field, seen = mouse_ui(monkeypatch)
    player.fairy = SimpleNamespace(tribe=SimpleNamespace(char=d.CHAR_PEGASUS))
    field[2][3] = d.CHAR_WALL
    seen[2][3] = 0
    ui._path_mouse_press(35, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() == (1, 0)
    assert ui.input_mouse_target == (3, 2)


def test_mouse_pegasus_jump_uses_game_movement_and_stops(session):
    player = session.player
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_TRIBE[d.CHAR_PEGASUS])
    session.floors[0].field[2][3] = d.CHAR_WALL
    session.floors[0].seen[2][3] = 1
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.consumed and result.stop_repeat
    assert (player.x, player.y) == (2 + d.PEGASUS_STEP_X, 2)


def test_mouse_pegasus_jump_uses_normal_blocked_landing_rules(session):
    player = session.player
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_TRIBE[d.CHAR_PEGASUS])
    session.floors[0].field[2][3] = d.CHAR_WALL
    session.floors[0].field[2][2 + d.PEGASUS_STEP_X] = d.CHAR_WALL
    session.floors[0].seen[2][3] = 1
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.stop_repeat and result.consumed
    assert (player.x, player.y) == (2, 2)


def test_mouse_pegasus_jump_cannot_be_used_without_pegasus(session):
    session.floors[0].field[2][3] = d.CHAR_WALL
    session.floors[0].seen[2][3] = 1
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.stop_repeat and result.consumed


@pytest.mark.parametrize('terrain', [*d.STAIR_CHARS, d.CHAR_COLLAPSE])
def test_mouse_can_enter_clicked_special_terrain_but_not_cross_it(session, monkeypatch, terrain):
    session.floors[0].field[2][3] = terrain
    session.floors[0].seen[2][3] = 1
    monkeypatch.setattr(game_engine, '_process_multi_floor_turn',
                        lambda move, floors, player, *_args, **_kwargs: setattr(player, 'x', 3))
    blocked = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(4, 2))
    assert blocked.stop_repeat and not blocked.consumed
    entered = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert entered.consumed and session.player.x == 3


@pytest.mark.parametrize('kind', ['monster', 'fairy', 'elf', 'member'])
def test_mouse_can_enter_clicked_entity_but_stops_for_other_entity(session, monkeypatch, kind):
    entity = {
        'monster': lambda: d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['a']),
        'fairy': lambda: d.Fairy(3, 2, d.CHAR_TO_FAIRY_TRIBE['l']),
        'elf': lambda: d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['J']),
        'member': lambda: d.PartyMember(3, 2, d.MEMBER_HEALER),
    }[kind]()
    session.floors[0].entities.append(entity)
    session.floors[0].seen[2][3] = 1
    monkeypatch.setattr(game_engine, '_process_multi_floor_turn',
                        lambda move, floors, player, *_args, **_kwargs: setattr(player, 'x', 3))
    blocked = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(4, 2))
    assert blocked.stop_repeat and not blocked.consumed
    entered = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert entered.consumed and session.player.x == 3


def test_explorer_can_walk_through_revealed_passage(session):
    session.player.members.append(d.PartyMember(2, 2, d.MEMBER_DUNGEON_EXPLORER))
    session.floors[0].field[2][3] = d.CHAR_D_GATE
    session.floors[0].seen[2][3] = 1
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.consumed and session.player.x == 3


def test_passage_remains_blocked_without_explorer(session):
    session.floors[0].field[2][3] = d.CHAR_D_GATE
    result = session.step((1, 0), repeat=True, mouse_move=True)
    assert result.stop_repeat and not result.consumed


@pytest.mark.parametrize('kind', ['monster', 'fairy', 'elf', 'member'])
def test_click_marks_visible_entity_as_intended_target(monkeypatch, kind):
    ui, _, _, _ = mouse_ui(monkeypatch)
    player = d.Player(1, 2, 100, 90)
    entity = {
        'monster': lambda: d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['a']),
        'fairy': lambda: d.Fairy(3, 2, d.CHAR_TO_FAIRY_TRIBE['l']),
        'elf': lambda: d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['J']),
        'member': lambda: d.PartyMember(3, 2, d.MEMBER_HEALER),
    }[kind]()
    ui._path_stage_draw.update(player=player, entities=[player, entity], known_types=set())
    ui._path_mouse_press(35, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() == (1, 0)
    assert ui.input_mouse_target == (3, 2)


@pytest.mark.parametrize('terrain', [d.CHAR_STAIRS_DOWN, d.CHAR_COLLAPSE])
def test_click_marks_known_stairs_and_pit_as_intended_target(monkeypatch, terrain):
    ui, player, field, seen = mouse_ui(monkeypatch)
    field[2][3] = terrain
    ui._path_mouse_press(35, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() == (1, 0)
    assert ui.input_mouse_target == (3, 2)


def test_mouse_uses_clicked_stairs_and_stops_on_new_floor(session):
    upper = session.floors[0]
    upper.field[2][3] = d.CHAR_STAIRS_DOWN
    upper.down_stairs = [(3, 2)]
    upper.seen[2][3] = 1
    lower = Floor([[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
                  [], [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
                  (4, 4), (8, 8), None)
    lower.field[4][4] = d.CHAR_STAIRS_UP
    lower.up_stairs = [(4, 4)]
    session.floors.append(lower)
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.consumed and result.stop_repeat
    assert (result.floor_before, result.floor_after) == (0, 1)


def test_clicked_wall_executes_blocked_move_once(session):
    session.floors[0].field[2][3] = d.CHAR_WALL
    session.floors[0].seen[2][3] = 1
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.consumed and result.stop_repeat
    assert (session.player.x, session.player.y) == (2, 2)


def test_clicked_barrier_can_damage_player(session):
    session.floors[0].field[2][3] = d.CHAR_BARRIER
    session.floors[0].seen[2][3] = 1
    old_lp = session.player.lp
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.consumed and result.stop_repeat
    assert session.player.x == 3 and session.player.lp < old_lp - d.movement_lp_cost(session.player)


def test_clicked_stronger_monster_is_contacted(session):
    session.player.level = 1
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['W'])
    session.floors[0].entities.append(monster)
    session.floors[0].seen[2][3] = 1
    result = session.step((1, 0), repeat=True, mouse_move=True, mouse_target=(3, 2))
    assert result.consumed
    assert session.player.last_contact_monster is not None


@pytest.mark.parametrize('kind', ['monster', 'fairy', 'elf', 'member'])
def test_visible_entities_are_path_obstacles_but_click_target_is_allowed(monkeypatch, kind):
    ui, _, field, seen = mouse_ui(monkeypatch)
    player = d.Player(1, 2, 100, 90)
    entity = {
        'monster': lambda: d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['a']),
        'fairy': lambda: d.Fairy(3, 2, d.CHAR_TO_FAIRY_TRIBE['l']),
        'elf': lambda: d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['J']),
        'member': lambda: d.PartyMember(3, 2, d.MEMBER_HEALER),
    }[kind]()
    view = ui._path_stage_draw
    view.update(player=player, entities=[player, entity], known_types=set())
    assert ui._mouse_path_obstacles(view) == {(3, 2)}
    assert (3, 2) not in ui._mouse_path(view, (4, 2))
    assert ui._mouse_path(view, (3, 2))[-1] == (3, 2)


def test_unseen_entities_and_disguises_do_not_change_path(monkeypatch):
    ui, _, field, seen = mouse_ui(monkeypatch)
    player = d.Player(1, 2, 100, 90)
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['a'])
    mimic = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE['M'])
    collapse = d.Collapse(2, 2)
    view = ui._path_stage_draw
    view.update(player=player, entities=[player, monster, mimic, collapse], known_types=set())
    seen[2][3] = 0
    assert ui._mouse_path_obstacles(view) == set()
    seen[2][3] = 1
    assert ui._mouse_path_obstacles(view) == {(3, 2)}


def test_newly_visible_entity_causes_route_change_to_stop(monkeypatch):
    ui, _, field, seen = mouse_ui(monkeypatch)
    player = d.Player(1, 2, 100, 90)
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE['a'])
    view = ui._path_stage_draw
    view.update(player=player, entities=[player, monster], known_types=set())
    seen[2][3] = seen[2][4] = 0
    ui._path_mouse_press(45, 25, mouse.LEFT, 0)
    assert ui._mouse_move_step() == (1, 0)
    player.x = 2
    seen[2][3] = 1
    ui._next_mouse_move_at = 0
    assert ui._mouse_move_step() is None
    assert ui._mouse_move_target is None
