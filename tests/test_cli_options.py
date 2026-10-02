"""Tests for command-line options controlling GUI input behavior."""

import sys

import pytest

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
