from types import SimpleNamespace

from arlq.pyglet_funcs import PygletUI


def make_ui():
    ui = PygletUI.__new__(PygletUI)
    ui._stage_input_active = True
    ui._menu_active = False
    ui._path_hover_cell = None
    ui._path_hover_dirty = False
    ui._path_mouse_deadline = None
    ui.cell_size_x, ui.cell_size_y = 10, 20
    ui.field_width, ui.field_height = 3, 2
    ui.window_height = 80
    ui.window = SimpleNamespace(set_mouse_visible=lambda value: None)
    return ui


def test_hover_bounds_and_leave():
    ui = make_ui()
    ui._path_mouse_motion(15, 50, 0, 0)
    assert ui._path_hover_cell == (1, 1)
    assert ui._path_hover_dirty
    ui._path_hover_dirty = False
    ui._path_mouse_motion(30, 50, 0, 0)
    assert ui._path_hover_cell is None
    assert ui._path_hover_dirty
    ui._path_mouse_motion(15, 70, 0, 0)
    ui._path_mouse_leave(15, 70)
    assert ui._path_hover_cell is None


def test_hover_path_uses_directions_and_marks_reachable_endpoint():
    ui = make_ui()
    ui._path_hover_cell = (2, 0)
    calls = []
    ui._draw_object = lambda signature, factory: calls.append(signature)
    ui._draw_hover_path([list('  #'), list('   ')], [[1] * 3 for _ in range(2)],
                        [[1] * 3 for _ in range(2)], SimpleNamespace(x=0, y=0))
    assert [call[0] for call in calls] == ['path_triangle', 'path_endpoint']
    _, tip_x, tip_y, *_ = calls[0]
    assert tip_x > 5 and tip_y == 70
    assert calls[1][1:3] == (15, 70)


def test_hover_ignored_outside_game_input():
    ui = make_ui()
    ui._stage_input_active = False
    ui._path_mouse_motion(15, 70, 0, 0)
    assert ui._path_hover_cell is None


def test_unexplored_path_arrows_are_outlined():
    ui = make_ui()
    ui._path_hover_cell = (3, 1)
    calls = []
    ui._draw_object = lambda signature, factory: calls.append(signature)
    ui._draw_hover_path([list('     ')] * 3, [[0] * 5, [0, 1, 0, 0, 0], [0] * 5],
                        [[0] * 5, [0, 1, 0, 0, 0], [0] * 5],
                        SimpleNamespace(x=1, y=1))
    assert [call[0] for call in calls] == [
        'path_triangle', 'path_triangle_outline', 'path_triangle_outline',
        'path_triangle_outline', 'path_endpoint',
    ]


def test_mouse_motion_refreshes_cursor_deadline(monkeypatch):
    ui = make_ui()
    now = [10.0]
    monkeypatch.setattr('arlq.pyglet_funcs.time.monotonic', lambda: now[0])
    ui._path_mouse_motion(15, 70, 0, 0)
    assert ui._path_mouse_deadline == 13.0
    now[0] = 12.0
    ui._path_mouse_motion(16, 70, 1, 0)
    assert ui._path_mouse_deadline == 15.0
    ui._path_mouse_leave(16, 70)
    assert ui._path_mouse_deadline is None
    assert ui._path_hover_cell is None
