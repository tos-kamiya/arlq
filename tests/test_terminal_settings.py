"""Terminal settings screen and command-line settings options."""

import json
import sys
from collections import deque
from types import SimpleNamespace

import pytest
from blessed.keyboard import Keystroke

from arlq import defs, i18n
from arlq.blessed_funcs import BlessedUI
from arlq.cli import _prepare_cli_session, cli_setting_overrides

DOWN = Keystroke("", name="KEY_DOWN")
UP = Keystroke("", name="KEY_UP")
LEFT = Keystroke("", name="KEY_LEFT")
RIGHT = Keystroke("", name="KEY_RIGHT")
ENTER = Keystroke("\n")
ESC = Keystroke("\x1b", code=27, name="KEY_ESCAPE")


@pytest.fixture(autouse=True)
def english_menu_labels(monkeypatch):
    monkeypatch.setattr(i18n, "_lang", "en")


def _terminal_ui(monkeypatch, tmp_path, keys):
    path = tmp_path / "settings.json"
    monkeypatch.setattr("arlq.blessed_settings.settings_path", lambda: path)
    ui = BlessedUI.__new__(BlessedUI)
    ui.combat_effect_seconds = defs.COMBAT_EFFECT_SECONDS
    ui.term = SimpleNamespace(
        home="", clear="", normal="", KEY_ESCAPE=27,
        move_xy=lambda x, y: f"<{x},{y}>",
        bold=lambda text: text, yellow=lambda text: text,
    )
    ui.setting_overrides = {}
    ui._wait_for_terminal_size = lambda: None
    events = deque(keys)
    ui._read_key = events.popleft
    return ui, path


def test_terminal_settings_rows_match_the_gui(monkeypatch, tmp_path, capsys):
    ui, _ = _terminal_ui(monkeypatch, tmp_path, [ESC])
    ui.settings_menu()
    output = capsys.readouterr().out
    for y, label in enumerate([
        "> Interface scale", "  Movement repeat interval", "  Automatic repeat stop",
        "  Sprite display settings", "  Gamepad button settings",
        "  Reset all settings to defaults",
    ], start=4):
        assert f"<4,{y}>{label}" in output


def test_terminal_settings_save_main_and_submenu_values(monkeypatch, tmp_path):
    keys = [RIGHT, DOWN, LEFT, DOWN, RIGHT]  # scale, repeat, stop
    keys += [DOWN, RIGHT, RIGHT, DOWN, LEFT, DOWN, RIGHT, ENTER]
    ui, path = _terminal_ui(monkeypatch, tmp_path, keys)

    ui.settings_menu()

    saved = json.loads(path.read_text())
    assert saved["scale"] == 1.25
    assert saved["key_repeat_interval"] == 1.0
    assert saved["auto_repeat_stop_enabled"] is False
    assert saved["combat_effect_seconds"] == 0.4
    assert saved["floor_transition_seconds"] == 0.4
    assert saved["idle_bob_enabled"] is False
    assert ui.combat_effect_seconds == 0.4


def test_terminal_gamepad_settings_and_cancel(monkeypatch, tmp_path):
    ui, path = _terminal_ui(monkeypatch, tmp_path, [DOWN] * 4 + [ENTER, RIGHT, ESC, ESC])
    ui.settings_menu()
    assert not path.exists()

    ui, path = _terminal_ui(monkeypatch, tmp_path, [DOWN] * 4 + [ENTER, RIGHT, DOWN, DOWN, RIGHT, ENTER])
    ui.settings_menu()
    saved = json.loads(path.read_text())
    assert (saved["gamepad_help_button"], saved["gamepad_preview_mode"]) == (4, "toggle")


def test_terminal_reset_row_removes_saved_settings(monkeypatch, tmp_path):
    ui, path = _terminal_ui(monkeypatch, tmp_path, [UP, ENTER])
    path.write_text(json.dumps({"scale": 2.0, "idle_bob_enabled": False,
                                "gamepad_help_button": 5}))
    ui.setting_overrides = {"combat_effect_seconds": 0.0}
    ui.settings_menu()
    assert not path.exists()
    assert ui.combat_effect_seconds == defs.COMBAT_EFFECT_SECONDS


def test_terminal_right_on_reset_row_does_nothing(monkeypatch, tmp_path):
    ui, path = _terminal_ui(monkeypatch, tmp_path, [UP, RIGHT, ESC])
    original = json.dumps({"scale": 2.0})
    path.write_text(original)
    ui.settings_menu()
    assert path.read_text() == original


def test_terminal_stage_selection_opens_settings(monkeypatch, tmp_path):
    ui, _ = _terminal_ui(monkeypatch, tmp_path, [Keystroke("s"), Keystroke("2")])
    opened = []
    ui.settings_menu = lambda: opened.append(True)
    assert ui.select_stage() == 2
    assert opened == [True]


@pytest.mark.parametrize("program", ["arlq", "arlq-cli", "arlq-sprites"])
def test_settings_options_are_available_in_every_frontend(monkeypatch, program):
    argv = [program, "--seed", "1", "--scale", "1.5", "--key-repeat-interval", "none",
            "--auto-repeat-stop", "off", "--combat-effect-duration", "0",
            "--floor-transition-duration", "1", "--character-bobbing", "off",
            "--smooth-movement", "ON"]
    monkeypatch.setattr(sys, "argv", argv)
    args, *_ = _prepare_cli_session(terminal_only=program == "arlq-cli",
                                    sprites_only=program == "arlq-sprites")
    assert cli_setting_overrides(args) == {
        "scale": 1.5, "key_repeat_interval": None, "auto_repeat_stop_enabled": False,
        "combat_effect_seconds": 0.0, "floor_transition_seconds": 1.0,
        "idle_bob_enabled": False, "move_glide_enabled": True,
    }


def test_unspecified_settings_options_leave_saved_settings(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", "1"])
    args, *_ = _prepare_cli_session()
    assert cli_setting_overrides(args) == {}


@pytest.mark.parametrize("options", [
    ["--combat-effect-duration", "0.6"],
    ["--combat-effect-duration", "0.25"],
    ["--floor-transition-duration", "1.1"],
    ["--character-bobbing", "yes"],
    ["--no-smooth-movement"],
    ["--reset-settings"],
    ["--gamepad-help-button", "2"],
])
def test_invalid_settings_options_are_rejected(monkeypatch, options):
    monkeypatch.setattr(sys, "argv", ["arlq", "--seed", "1", *options])
    with pytest.raises(SystemExit) as error:
        _prepare_cli_session()
    assert error.value.code == 2


def test_terminal_settings_show_overrides_but_save_only_changes(monkeypatch, tmp_path):
    # Change the scale only; the command-line effect duration stays unsaved.
    ui, path = _terminal_ui(monkeypatch, tmp_path, [RIGHT, ENTER])
    ui.setting_overrides = {"combat_effect_seconds": 0.0}
    ui.combat_effect_seconds = 0.0

    ui.settings_menu()

    assert json.loads(path.read_text()) == {"scale": 1.25}
    assert ui.combat_effect_seconds == 0.0
