"""Exercise the session without a renderer or input loop."""

import pytest

from arlq import defs as d
from arlq import game_engine as engine
from arlq.game_session import GameSession
from arlq.stage_types import Floor


@pytest.fixture
def session(monkeypatch):
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    floor = Floor(
        field,
        [],
        [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        (1, 1),
        (d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        None,
    )
    player = d.Player(2, 2, 100, 3)
    monkeypatch.setattr(engine, "build_single_floor", lambda *_: ([floor], player))
    return GameSession(1, seed_str="session-test")


def test_session_can_finish_without_ui(session):
    while session.phase == "playing":
        session.view()
        result = session.step((1, 0))
        assert result.consumed
        assert result.floor_before == result.floor_after == 0
        assert session.turn < 10
    assert session.outcome == "lose"
    assert session.player.lp <= 0
    assert session.view()["extra_keys"] is True
    turn = session.turn
    assert not session.step((1, 0)).consumed
    assert session.turn == turn


def test_repeat_precheck_does_not_consume_turn(session):
    floor = session.floors[0]
    floor.field[2][3] = d.CHAR_WALL
    floor.seen[2][3] = 1
    before = session.player.lp
    result = session.step((1, 0), repeat=True)
    assert not result.consumed
    assert result.stop_repeat
    assert session.turn == 0
    assert session.player.lp == before


def test_view_and_zero_input_do_not_tick_message(session):
    message = session.message
    session.view()
    assert not session.step((0, 0)).consumed
    assert session.message == message
    assert session.floor_count == 1
    assert session.floor_index == 0
    assert "session-test" in session.seed_message()


@pytest.mark.parametrize("stage_num", range(1, 7))
def test_fixed_inputs_match_ui_wrapper(stage_num):
    moves = [(1, 0), (0, 1), (-1, 0), (0, -1)] * 3
    engine.rand.set_seed(12345)
    direct = GameSession(stage_num)
    for move in moves:
        direct.step(move)
        if direct.phase != "playing":
            break

    class UI:
        def __init__(self):
            self.moves = iter(moves)
            self.last = None

        def draw_stage(self, **kwargs):
            self.last = (
                kwargs["turn"],
                kwargs["player"].x,
                kwargs["player"].y,
                kwargs["player"].lp,
            )

        def input_direction(self):
            return next(self.moves, None)

        def input_alphabet(self):
            return None

    ui = UI()
    engine.rand.set_seed(12345)
    engine.run_game(ui, "test", stage_num=stage_num)
    assert ui.last == (direct.turn, direct.player.x, direct.player.y, direct.player.lp)


def test_quit_is_distinct_from_game_over(session):
    session.quit()
    assert session.phase == "quit"
    assert session.outcome is None
    assert not session.step((1, 0)).consumed


def test_view_does_not_change_message(session):
    session.player.lp = 0
    message = session.message
    session.view()
    assert session.message == message
    session.step((1, 0))
    assert session.phase == "game_over"
    assert session.game_over_message() == engine.trp(">> Collapsed from hunger! <<", 9)


def test_consumed_turns_report_their_move(session):
    floor = session.floors[0]
    floor.field[2][1] = d.CHAR_WALL
    floor.seen[2][1] = 1
    assert session.step((0, 1)).move == (0, 1)
    # A wall keeps the player in place but still uses the turn and the move.
    assert session.step((-1, 0)).move == (-1, 0)
    assert session.step((0, 0)).move is None


def test_repeat_stop_reports_no_move(session):
    floor = session.floors[0]
    floor.field[2][3] = d.CHAR_WALL
    floor.seen[2][3] = 1
    assert session.step((1, 0), repeat=True).move is None
