"""Tests for command-line options controlling GUI input behavior."""

import sys

import pytest

from arlq import __about__, cli, i18n
from arlq.cli import _prepare_cli_session


@pytest.mark.parametrize(
    ("option", "expected"),
    [("--auto-repeat-stop", True), ("--no-auto-repeat-stop", False)],
)
def test_cli_can_enable_or_disable_automatic_repeat_stop(monkeypatch, option, expected):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", "123", option])

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
