import pytest

from arlq import defs as d
from arlq.pathfinding import find_path


def test_known_target_uses_only_known_floor_and_detours():
    field = [list('   '), list(' # '), list('   ')]
    seen = [[1] * 3 for _ in field]
    assert find_path(field, seen, (0, 1), (2, 1)) == [
        (0, 1), (0, 0), (1, 0), (2, 0), (2, 1)
    ]
    seen[0][1] = 0
    assert find_path(field, seen, (0, 1), (2, 1))[1] == (0, 2)


def test_known_route_takes_priority_over_shorter_unknown_route():
    field = [list('#######'), list('#     #'), list('#     #'),
             list('#     #'), list('#######')]
    seen = [[1] * 7 for _ in field]
    seen[2][3] = 0
    path = find_path(field, seen, (1, 2), (5, 2))
    assert len(path) == 7
    assert all(seen[y][x] for x, y in path)


def test_known_target_can_be_reached_through_unknown_floor():
    field = [list('#######'), list('#######'), list('#  #  #'),
             list('#######'), list('#######')]
    seen = [[1] * 7 for _ in field]
    seen[2][3] = 0
    assert find_path(field, seen, (1, 2), (5, 2)) == [
        (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)
    ]


def test_blocked_target_uses_unknown_route_to_get_closer():
    field = [list('#######'), list('#######'), list('#  # ##'),
             list('#######'), list('#######')]
    seen = [[1] * 7 for _ in field]
    seen[2][3] = 0
    assert find_path(field, seen, (1, 2), (5, 2))[-1] == (4, 2)


def test_unknown_target_assumes_unknown_terrain_is_floor():
    field = [list('######'), list('# ### '), list('######')]
    seen = [[0] * 6 for _ in field]
    seen[1][1] = 1
    assert find_path(field, seen, (1, 1), (4, 1)) == [
        (1, 1), (2, 1), (3, 1), (4, 1)
    ]
    seen[1][2] = 1
    assert find_path(field, seen, (1, 1), (4, 1)) == [(1, 1)]


@pytest.mark.parametrize('target, endpoint', [
    ((0, 2), (1, 2)), ((4, 2), (3, 2)),
    ((2, 0), (2, 1)), ((2, 4), (2, 3)),
    ((0, 0), (1, 1)),
])
def test_unknown_outer_boundary_is_treated_as_wall(target, endpoint):
    field = [list('     ') for _ in range(5)]
    seen = [[0] * 5 for _ in range(5)]
    seen[2][2] = 1
    assert find_path(field, seen, (2, 2), target)[-1] == endpoint


def test_known_floor_on_boundary_remains_passable():
    field = [list('   ') for _ in range(3)]
    seen = [[1] * 3 for _ in range(3)]
    assert find_path(field, seen, (1, 1), (0, 1)) == [(1, 1), (0, 1)]


def test_blocked_target_selects_closest_then_shortest():
    field = [list('    '), list('  # '), list('    ')]
    seen = [[1] * 4 for _ in field]
    assert find_path(field, seen, (0, 1), (2, 1)) == [(0, 1), (1, 1)]


def test_visible_cells_are_known_and_special_terrain_is_blocked():
    field = [[d.CHAR_FLOOR, d.CHAR_STAIRS_DOWN, d.CHAR_FLOOR]]
    assert find_path(field, [[1, 0, 0]], (0, 0), (2, 0), [[1, 1, 0]]) == [(0, 0)]


@pytest.mark.parametrize('cell', d.HIDDEN_STAIRS_CHARS)
def test_hidden_floor_terrain_does_not_reveal_itself(cell):
    assert find_path([[d.CHAR_FLOOR, cell]], [[1, 1]], (0, 0), (1, 0)) == [
        (0, 0), (1, 0)
    ]


def test_start_can_be_special_terrain_and_is_a_valid_endpoint():
    assert find_path([[d.CHAR_STAIRS_UP, d.CHAR_WALL]], [[1, 1]], (0, 0), (1, 0)) == [(0, 0)]


@pytest.mark.parametrize('field, seen, start, target', [
    ([], [], (0, 0), (0, 0)),
    ([[' ']], [], (0, 0), (0, 0)),
    ([[' ']], [[1]], (0, 0), (1, 0)),
])
def test_invalid_inputs_raise_value_error(field, seen, start, target):
    with pytest.raises(ValueError):
        find_path(field, seen, start, target)
