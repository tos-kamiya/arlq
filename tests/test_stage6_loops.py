from arlq.stage_maze import _add_long_loop_edges


def test_adds_longest_available_loop_without_joining_isolated_room():
    # A six-room path around a rectangle; closing its ends makes the largest loop.
    path = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)]
    isolated = (3, 0)
    edges = list(zip(path, path[1:]))
    _add_long_loop_edges(edges, set(path) | {isolated}, 1)
    assert edges[-1] == ((0, 0), (0, 1))
    assert all(isolated not in edge for edge in edges)


def test_additional_loops_use_updated_distances_and_stop_when_full():
    rooms = {(0, 0), (1, 0), (0, 1), (1, 1)}
    edges = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1))]
    _add_long_loop_edges(edges, rooms, 10)
    assert len(edges) == 4


def test_zero_extra_corridors_preserves_tree():
    edges = [((0, 0), (1, 0))]
    original = edges.copy()
    _add_long_loop_edges(edges, {(0, 0), (1, 0)}, 0)
    assert edges == original
