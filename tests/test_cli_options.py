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
