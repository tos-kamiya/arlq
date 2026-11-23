"""Tests for command-line options controlling GUI input behavior."""

import sys

import pytest

from arlq import __about__, cli, i18n
from arlq.cli import _prepare_cli_session


def test_sprite_gui_option_and_terminal_conflict(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['arlq', '--sprites', '--seed', '123'])
    args, *_ = _prepare_cli_session()
    assert args.sprites
    monkeypatch.setattr(sys, 'argv', ['arlq', '--sprites', '--terminal'])
    with pytest.raises(SystemExit) as error:
        _prepare_cli_session()
    assert error.value.code == 2


def test_wide_option_is_available_in_terminal_mode(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arlq-cli", "--wide", "--seed", "123"])
    args, *_ = _prepare_cli_session(terminal_only=True)
    assert args.wide and args.terminal
    monkeypatch.setattr(sys, "argv", ["arlq", "--wide", "--seed", "123"])
    with pytest.raises(SystemExit):
        _prepare_cli_session()


@pytest.mark.parametrize("option", ["-n", "--narrower-corridors"])
def test_narrow_corridor_option_is_not_available(monkeypatch, option):
    monkeypatch.setattr(sys, "argv", ["arlq", option])
    with pytest.raises(SystemExit) as error:
        _prepare_cli_session()
    assert error.value.code == 2


def test_legacy_narrow_corridor_seed_still_restores_its_configuration(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", f"v{__about__.__version__}-n-3-123"])
    args, _, _, config, _ = _prepare_cli_session()
    assert args.narrower_corridors
    assert (config.corridor_h_width, config.corridor_v_width) == (1, 2)


@pytest.mark.parametrize(("value", "expected"), [("on", True), ("off", False)])
def test_cli_can_enable_or_disable_automatic_repeat_stop(monkeypatch, value, expected):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", "123", "--auto-repeat-stop", value])

    args, *_ = _prepare_cli_session()

    assert args.auto_repeat_stop is expected


def test_cli_leaves_automatic_repeat_stop_to_saved_setting_when_unspecified(
    monkeypatch,
):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", "123"])

    args, *_ = _prepare_cli_session()

    assert not hasattr(args, "auto_repeat_stop")


def test_trace_replay_uses_environment_language_not_recorded_language(monkeypatch):
    previous_language = i18n.get_language()
    monkeypatch.setattr(sys, "argv", ["arlq", "--trace", "trace.json"])
    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.setattr(
        cli,
        "load_trace",
        lambda _path: {
            "arlq_version": __about__.__version__,
            "params": {"seed": "test-seed", "lang": "ja"},
            "turns": [],
        },
    )
    monkeypatch.setattr(
        cli.game,
        "parse_seed_string",
        lambda args, *_args, **_kwargs: setattr(args, "stage", 1),
    )
    monkeypatch.setattr(cli.game.rand, "set_seed", lambda _seed: None)
    monkeypatch.setattr(cli.game, "generate_seed_string", lambda _args: "test-seed")
    monkeypatch.setattr(cli.game, "game_config_from_args", lambda _args: object())

    try:
        _prepare_cli_session()
        assert i18n.get_language() == "en"
    finally:
        i18n.set_language(previous_language)


@pytest.mark.parametrize(("version", "expected"), [
    ("6.8.0", False), ("6.9.0", False), ("6.9.1", True),
    ("6.10.0", True), ("7.0.0", True), (None, True),
])
def test_trace_roster_version_and_continuation(monkeypatch, version, expected):
    data = {"arlq_version": version, "params": {"seed": "v6.9.0--6-123"}, "turns": []}
    monkeypatch.setattr(cli, "load_trace", lambda _path: data)
    monkeypatch.setattr(sys, "argv", ["arlq", "--trace", "trace.json", "--continue"])
    _, _, _, config, recorder = _prepare_cli_session()
    assert config.include_iris is expected
    if not expected:
        assert recorder.params["seed"] == f"v{__about__.__version__}-none-6.0-123"
        continued = recorder.to_dict()
        assert not cli.trace_includes_iris(continued)


@pytest.mark.parametrize(("seed", "expected", "large_torch"), [
    ("none-6.0-123", False, False), ("none-6.1-123", True, False),
    ("T-6.0-123", False, True), ("-6-123", True, False),
])
def test_seed_rules_round_trip(monkeypatch, seed, expected, large_torch):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", f"v{__about__.__version__}-{seed}"])
    _, _, seed_str, config, _ = _prepare_cli_session()
    assert config.include_iris is expected
    flags = "T" if large_torch else "none"
    assert seed_str == f"v{__about__.__version__}-{flags}-6.{int(expected)}-123"
    assert (config.corridor_h_width, config.corridor_v_width) == (2, 3)


def test_interactive_stage_selection_preserves_seed_rules(monkeypatch):
    from types import SimpleNamespace
    from arlq.trace import TraceRecorder

    recorded = TraceRecorder({})
    monkeypatch.setattr(cli.game, "import_module", lambda *_args, **_kwargs: SimpleNamespace(run_game=lambda *args, **kwargs: None))
    cli.game.run_game(SimpleNamespace(select_stage=lambda _stages: 6),
                      f"v{__about__.__version__}-none-0.1-123", 0, trace=recorded)
    assert recorded.params["seed"] == f"v{__about__.__version__}-none-6.1-123"


def test_seed_without_options_field_is_rejected(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", f"v{__about__.__version__}-6.1-123"])
    with pytest.raises(SystemExit):
        _prepare_cli_session()
