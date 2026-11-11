from arlq import defs as d, game_engine, stage_maze
from arlq.stage_types import Floor


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
    game_engine._vortex_rearrange(current, player, 0, (10, 8), bounded_relocation=True)
    assert choices
