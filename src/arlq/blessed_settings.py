"""Settings screens for the Blessed terminal frontend.

The rows and submenus match the Pyglet frontends, so every setting can be
changed here even when it only affects the GUI.
"""

from . import defs as d
from .i18n import t as tr
from .settings import (
    KEY_REPEAT_CHOICES,
    UI_SCALE_CHOICES,
    clear_default_settings,
    combat_effect_seconds,
    current_settings,
    default_settings,
    gamepad_bindings_settings,
    gamepad_button_label,
    load_settings,
    next_gamepad_button,
    save_settings,
    settings_path,
)


def _step_choice(choices, value, step):
    index = choices.index(value) if value in choices else 0
    return choices[min(len(choices) - 1, max(0, index + step))]


def _nearest_scale(scale):
    return min(UI_SCALE_CHOICES, key=lambda choice: abs(choice - scale))


def _on_off(enabled):
    return tr("On") if enabled else tr("Off")


class BlessedSettingsMixin:
    def _settings_key(self):
        """Read one key and return a menu command name, or None."""
        key = self._read_key()
        if key.name == "KEY_UP":
            return "up"
        if key.name == "KEY_DOWN":
            return "down"
        if key.name == "KEY_LEFT":
            return "left"
        if key.name == "KEY_RIGHT":
            return "right"
        if str(key) in ("\n", "\r") or key.name == "KEY_ENTER":
            return "enter"
        if str(key).lower() == "q" or key.code == self.term.KEY_ESCAPE:
            return "cancel"
        return None

    def _draw_settings_screen(self, title, rows, row, help_lines):
        self._wait_for_terminal_size()
        output = [self.term.home + self.term.clear]
        output.append(self.term.move_xy(4, 2) + self.term.bold(self.term.yellow(title)))
        for index, (label, value) in enumerate(rows):
            text = f"{'>' if index == row else ' '} {label}"
            if value:
                text += f"  {value}"
            output.append(self.term.move_xy(4, 4 + index)
                          + (self.term.bold(text) if index == row else text))
        for offset, text in enumerate(help_lines):
            output.append(self.term.move_xy(4, 5 + len(rows) + offset) + text)
        print("".join(output) + self.term.normal, end="", flush=True)

    def settings_menu(self) -> None:
        """Show the settings shared with the GUI and save confirmed changes."""
        path = settings_path()
        values = current_settings(load_settings(path))
        values.update(self.setting_overrides)
        values["scale"] = _nearest_scale(values["scale"])
        initial = dict(values)
        reset_all = False
        names = ["scale", "repeat", "stop", "sprites", "gamepad", "reset"]
        row = 0

        def apply():
            # Save only what was changed here (or everything after a reset),
            # so command-line settings for this run are not saved by accident.
            save_settings({
                name: value for name, value in values.items()
                if reset_all or value != initial[name]
            }, path)
            if reset_all:
                clear_default_settings(path)
            self.combat_effect_seconds = combat_effect_seconds(values)
            self.setting_overrides = {name: values[name] for name in self.setting_overrides}

        while True:
            repeat = values["key_repeat_interval"]
            rows = [
                (tr("Interface scale") + " *", f"<  {int(values['scale'] * 100)}%  >"),
                (tr("Movement repeat interval") + " *",
                 f"<  {tr('No repeat') if repeat is None else format(repeat, '.1f') + 's'}  >"),
                (tr("Automatic repeat stop") + " *",
                 f"<  {_on_off(values['auto_repeat_stop_enabled'])}  >"),
                (tr("Sprite display settings"), "->"),
                (tr("Gamepad button settings") + " *", "->"),
                (tr("Reset all settings to defaults"), ""),
            ]
            self._draw_settings_screen(tr("Settings"), rows, row, [
                tr("Up/Down: item   Left/Right: value   Enter / Right: open submenu"),
                tr("Enter: apply or open   Esc: cancel"),
                tr("* These settings have no effect in arlq-cli."),
            ])
            command = self._settings_key()
            selected = names[row]
            if command == "up":
                row = (row - 1) % len(names)
            elif command == "down":
                row = (row + 1) % len(names)
            elif command == "cancel":
                return
            elif command in ("left", "right", "enter"):
                step = -1 if command == "left" else 1
                if selected == "scale" and command != "enter":
                    values["scale"] = _step_choice(UI_SCALE_CHOICES, values["scale"], step)
                elif selected == "repeat" and command != "enter":
                    values["key_repeat_interval"] = _step_choice(
                        KEY_REPEAT_CHOICES, repeat, step)
                elif selected == "stop" and command != "enter":
                    values["auto_repeat_stop_enabled"] = not values["auto_repeat_stop_enabled"]
                elif selected == "sprites" and step > 0:
                    result = self.sprite_settings_menu(values)
                    if result is not None:
                        values.update(result)
                        apply()
                        return
                elif selected == "gamepad" and step > 0:
                    result = self.gamepad_button_settings_menu(values)
                    if result is not None:
                        values.update(result)
                        apply()
                        return
                elif selected == "reset":
                    if command == "enter":
                        values = default_settings()
                        reset_all = True
                        apply()
                        return
                elif command == "enter":
                    apply()
                    return

    def sprite_settings_menu(self, values):
        """Edit sprite display options, returning confirmed changes."""
        values = dict(values)
        row = 0
        while True:
            rows = [
                (tr("Combat effect duration"), f"<  {values['combat_effect_seconds']:.1f}s  >"),
                (tr("Floor transition duration") + " *",
                 f"<  {values['floor_transition_seconds']:.1f}s  >"),
                (tr("Character bobbing") + " *", f"<  {_on_off(values['idle_bob_enabled'])}  >"),
            ]
            self._draw_settings_screen(tr("Sprite display settings"), rows, row, [
                tr("Up/Down: item   Left/Right: value"),
                tr("Enter: apply   Esc: cancel"),
                tr("* These settings have no effect in arlq-cli."),
            ])
            command = self._settings_key()
            if command == "enter":
                return values
            if command == "cancel":
                return None
            if command == "up":
                row = (row - 1) % len(rows)
            elif command == "down":
                row = (row + 1) % len(rows)
            elif command in ("left", "right"):
                step = -1 if command == "left" else 1
                if row == 0:
                    values["combat_effect_seconds"] = _step_choice(
                        d.COMBAT_EFFECT_SECONDS_CHOICES, values["combat_effect_seconds"], step)
                elif row == 1:
                    values["floor_transition_seconds"] = _step_choice(
                        d.FLOOR_TRANSITION_SECONDS_CHOICES,
                        values["floor_transition_seconds"], step)
                elif row == 2:
                    values["idle_bob_enabled"] = not values["idle_bob_enabled"]

    def gamepad_button_settings_menu(self, values):
        """Edit gamepad mode buttons, returning confirmed changes."""
        help_button = values["gamepad_help_button"]
        preview_button = values["gamepad_preview_button"]
        preview_mode = values["gamepad_preview_mode"]
        defaults = default_settings()
        row = 0
        while True:
            rows = [
                (tr("Help button") + " *", gamepad_button_label(help_button)),
                (tr("Range / floor preview button") + " *", gamepad_button_label(preview_button)),
                (tr("Range / floor preview behavior") + " *",
                 tr("Hold") if preview_mode == "hold" else tr("Toggle")),
                (f"{tr('Load default settings')} ->", ""),
            ]
            self._draw_settings_screen(tr("Gamepad button settings"), rows, row, [
                tr("Up/Down: item   Left/Right: change / load defaults with Right"),
                tr("Enter: apply and exit   Esc: cancel"),
                tr("* These settings have no effect in arlq-cli."),
            ])
            command = self._settings_key()
            if command == "enter":
                return gamepad_bindings_settings(help_button, preview_button, preview_mode)
            if command == "cancel":
                return None
            if command == "up":
                row = (row - 1) % len(rows)
            elif command == "down":
                row = (row + 1) % len(rows)
            elif command in ("left", "right"):
                step = -1 if command == "left" else 1
                if row == 3 and step > 0:
                    help_button = defaults["gamepad_help_button"]
                    preview_button = defaults["gamepad_preview_button"]
                    preview_mode = defaults["gamepad_preview_mode"]
                elif row == 0:
                    help_button = next_gamepad_button(help_button, step, preview_button)
                elif row == 1:
                    preview_button = next_gamepad_button(preview_button, step, help_button)
                elif row == 2:
                    preview_mode = "toggle" if preview_mode == "hold" else "hold"
