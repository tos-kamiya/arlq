from collections import Counter

from arlq import arlq, defs as d, game_engine, stage56, stage_maze, stage_world
from arlq.stage_types import Floor


def test_generate_maze_initial_choices_have_stable_order(monkeypatch):
    choices = []

    def choice(candidates):
        choices.append(candidates.copy())
        return candidates[0]

    monkeypatch.setattr(arlq.rand, "choice", choice)
    monkeypatch.setattr(arlq.rand, "randrange", lambda _: 0)
    edges, first, _ = arlq.generate_maze(3, 3, excluded_tile=(1, 1))
    expected = [(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
    assert choices[:2] == [expected, expected]
    assert first == expected[0]
    assert len(edges) == len(expected) - 1


def test_filled_room_notches_visit_rooms_in_stable_order(monkeypatch):
    visited = []
    monkeypatch.setattr(stage_world, "_is_wall_notch_point", lambda point: visited.append(point) or False)
    field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    rooms = [(2, 1), (0, 1), (1, 1)]
    stage_world._add_filled_room_wall_notches(field, rooms)
    first_visit = visited.copy()
    visited.clear()
    stage_world._add_filled_room_wall_notches(field, reversed(rooms))
    assert visited == first_visit


def test_maze_random_candidates_have_stable_room_order(monkeypatch):
    monkeypatch.setattr(stage_maze.rand, "_state", stage_maze.rand._state[:])
    monkeypatch.setattr(stage_maze.rand, "_index", stage_maze.rand._index)
    original_choice = stage_maze.rand.choice
    room_choices = []
    edge_choices = []

    def choice(candidates):
        import inspect

        if inspect.currentframe().f_back.f_code.co_name == "generate_floor_field":
            first = candidates[0]
            if isinstance(first[0], int):
                room_choices.append(candidates)
                assert candidates == sorted(candidates)
            else:
                edge_choices.append(candidates)
                rooms = [room for room, _ in candidates]
                assert rooms == sorted(rooms)
        return original_choice(candidates)

    monkeypatch.setattr(stage_maze.rand, "choice", choice)
    stage_maze.generate_floor_field(None, None, 1, 1, 1, 1)
    assert room_choices and edge_choices


def test_vortex_random_candidates_have_stable_order(monkeypatch):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    enemy = d.Monster(10, 8, d.CHAR_TO_MONSTER_TRIBE["a"])
    current = Floor(field, [enemy], [[0] * d.FIELD_WIDTH for _ in field],
                    (1, 1), (2, 2), None)
    player = d.Player(1, 1, 1, d.LP_INIT)
    points = [(10, 8), (15, 10), (12, 9), (18, 11)]
    choices = []
    monkeypatch.setattr(game_engine, "iterate_ellipse_points", lambda *_: points)

    def choice(candidates):
        choices.append(candidates)
        assert candidates == sorted(candidates)
        return candidates[0]

    monkeypatch.setattr(game_engine.rand, "choice", choice)
    game_engine._vortex_rearrange(current, player, 0, (10, 8))
    assert choices
