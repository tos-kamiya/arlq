"""Presentation keeps input queued and cleans up effects on every exit path."""

from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq.game_events import BarrierHit, Combat, EntityRef, FloorChanged, Rewound
from arlq.game_session import TurnResult
from arlq.sprites.sprite_fx import Presenter


class Clock:
    def __init__(self):
        self.now = 0
        self.waits = []

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


def fake_ui():
    ui = SimpleNamespace(
        _stage_input_active=False,
        _closed=False,
        _key_queue=[],
        scale=1,
        window_width=800,
        window_height=500,
    )
    ui.frames = []
    ui._flip = lambda: ui.frames.append(ui.scale)
    ui._pump = lambda: None
    return ui


def test_hold_pumps_input_and_keeps_keys_for_next_turn():
    ui = fake_ui()
    clock = Clock()
    presenter = Presenter(clock=clock, wait=clock.wait)
    deleted = []

    def pump():
        assert ui._stage_input_active
        if not ui._key_queue:
            ui._key_queue.append(("right", 0))

    ui._pump = pump
    presenter.hold(
        ui, 0.1, lambda: [SimpleNamespace(delete=lambda: deleted.append(True))]
    )
    assert len(ui.frames) > 1
    assert ui._key_queue == [("right", 0)]
    assert deleted == [True]
    assert clock.now == pytest.approx(0.1)
    assert all(0 < seconds <= 1 / 60 for seconds in clock.waits)
    assert not ui._stage_input_active


def test_hold_rebuilds_effect_on_resize():
    ui = fake_ui()
    clock = Clock()
    presenter = Presenter(clock=clock, wait=clock.wait)
    created, deleted = [], []

    def create():
        size = ui.scale
        created.append(size)
        return [SimpleNamespace(delete=lambda: deleted.append(size))]

    ui._pump = lambda: setattr(ui, "scale", 2)
    presenter.hold(ui, 0.05, create)
    assert created == [1, 2]
    assert deleted == [1, 2]
    assert ui.frames[0] == 1
    assert ui.frames[-1] == 2


@pytest.mark.parametrize("fail", [False, True])
def test_hold_cleans_up_when_closed_or_pump_fails(fail):
    ui = fake_ui()
    clock = Clock()
    presenter = Presenter(clock=clock, wait=clock.wait)
    deleted = []

    def pump():
        if fail:
            raise RuntimeError("pump failed")
        ui._closed = True

    ui._pump = pump
    create = lambda: [SimpleNamespace(delete=lambda: deleted.append(True))]
    if fail:
        with pytest.raises(RuntimeError, match="pump failed"):
            presenter.hold(ui, 1, create)
    else:
        presenter.hold(ui, 1, create)
    assert deleted == [True]
    assert ui.frames == [1]
    assert not ui._stage_input_active
    assert clock.waits == []


def test_disabled_effect_does_not_allocate_draw_or_wait():
    ui = fake_ui()
    presenter = Presenter(wait=lambda _: pytest.fail("waited"))
    presenter.hold(ui, 0, lambda: pytest.fail("created an effect"))
    assert ui.frames == []


def test_play_filters_hidden_targets_without_mutating_events():
    ui = fake_ui()
    view = {
        "cur_torched": [[1, 0], [0, 0]],
        "player": d.Player(0, 0, 10, 90),
        "stage_num": 5,
    }
    targets = [
        (EntityRef(1, "a", "monster"), (0, 0)),
        (EntityRef(2, "b", "monster"), (1, 0)),
    ]
    combat = Combat(0, (0, 0), targets, True, 0)
    result = TurnResult(
        True,
        None,
        True,
        0,
        0,
        [BarrierHit(1, (0, 0), 5), BarrierHit(0, (1, 0), 5), combat],
    )
    calls = []
    ui.draw_combat_effect = lambda *args: calls.append(args)
    assert Presenter().play(ui, result, view) is True
    assert calls == [([(0, 0)], True)]
    assert len(combat.targets) == 2
    assert not ui._stage_input_active


def test_visibility_tracks_floor_change_using_both_views():
    ui = fake_ui()
    ui._last_stage_draw = (None, {"cur_torched": [[1, 0]]})
    transition = FloorChanged(0, "down", 1, (0, 0))
    before, after = BarrierHit(0, (0, 0), 5), BarrierHit(1, (1, 0), 5)
    result = TurnResult(
        True,
        None,
        True,
        0,
        1,
        [
            before,
            BarrierHit(1, (1, 0), 5),
            transition,
            BarrierHit(0, (0, 0), 5),
            after,
            BarrierHit(1, (0, 0), 5),
        ],
    )
    assert Presenter.visible_events(ui, result, {"cur_torched": [[0, 1]]}) == [
        before,
        transition,
        after,
    ]


def test_play_stops_remaining_effects_when_closed():
    ui = fake_ui()
    calls = []
    view = {"cur_torched": [[1]], "player": d.Player(0, 0, 10, 90), "stage_num": 1}
    result = TurnResult(
        True, None, True, 0, 0, [BarrierHit(0, (0, 0), 5), Rewound(0, "rewind", {})]
    )

    def combat(*args):
        calls.append(args)
        ui._closed = True

    ui.draw_combat_effect = combat
    ui.draw_rewind_transition = lambda _: pytest.fail("played after close")
    assert Presenter().play(ui, result, view) is False
    assert calls == [((0, 0), False)]
    assert not ui._stage_input_active


def test_play_preserves_input_state_when_effect_raises():
    ui = fake_ui()
    ui._stage_input_active = True
    result = TurnResult(True, None, True, 0, 0, [BarrierHit(0, (0, 0), 5)])
    view = {"cur_torched": [[1]], "player": d.Player(0, 0, 10, 90), "stage_num": 1}

    def fail(*_):
        raise RuntimeError("draw failed")

    ui.draw_combat_effect = fail
    with pytest.raises(RuntimeError, match="draw failed"):
        Presenter().play(ui, result, view)
    assert ui._stage_input_active


def test_loss_only_flashes_visible_party_members():
    ui = fake_ui()
    combat = Combat(
        0,
        (0, 0),
        [(EntityRef(1, "a", "monster"), (0, 0))],
        False,
        -5,
        [(0, 0), (1, 0), (-1, 0)],
    )
    result = TurnResult(True, None, True, 0, 0, [combat])
    filtered = Presenter.visible_events(ui, result, {"cur_torched": [[1, 0]]})
    assert filtered[0].party_positions == [(0, 0)]
    assert combat.party_positions == [(0, 0), (1, 0), (-1, 0)]


@pytest.mark.parametrize("attacker, target, facing", [
    ((3, 4), (3, 3), "up"), ((3, 2), (3, 3), "down"),
    ((4, 3), (3, 3), "left"), ((2, 3), (3, 3), "right"),
])
def test_attack_facing_points_from_player_to_monster(attacker, target, facing):
    from arlq.sprites.sprite_fx import attack_facing

    combat = Combat(0, attacker, [(EntityRef(1, "a", "monster"), target)], True, 0)
    assert attack_facing(combat) == facing


def test_attack_facing_uses_the_monster_run_into_for_a_party():
    from arlq.sprites.sprite_fx import attack_facing

    party = [(EntityRef(1, "a", "monster"), (4, 3)), (EntityRef(2, "b", "monster"), (4, 2))]
    assert attack_facing(Combat(0, (3, 3), party, True, 0)) == "right"
    assert attack_facing(Combat(0, (3, 3), [], False, 0)) is None


def test_play_sets_the_attack_facing_before_each_fight():
    ui = fake_ui()
    view = {"cur_torched": [[1] * 5 for _ in range(5)],
            "player": d.Player(2, 2, 10, 90), "stage_num": 1}
    seen = []
    ui.draw_combat_effect = lambda *args: seen.append(ui._attack_facing)
    fights = [Combat(0, (2, 2), [(EntityRef(1, "a", "monster"), (1, 2))], True, 0),
              Combat(0, (2, 2), [(EntityRef(2, "a", "monster"), (2, 3))], True, 0)]
    Presenter().play(ui, TurnResult(True, None, False, 0, 0, fights), view)
    assert seen == ["left", "down"]


def test_hold_reports_progress_before_each_frame():
    ui = fake_ui()
    clock = Clock()
    progresses = []
    Presenter(clock=clock, wait=clock.wait).hold(
        ui, 0.05, lambda: [], update=lambda progress: progresses.append(round(progress, 3)))
    assert progresses[0] == 0
    assert progresses[-1] == 1
    assert progresses == sorted(progresses)
    assert len(progresses) == len(ui.frames)


def test_hold_without_update_adds_no_final_frame():
    ui = fake_ui()
    clock = Clock()
    Presenter(clock=clock, wait=clock.wait).hold(ui, 0.05, lambda: [])
    assert len(ui.frames) == 4
