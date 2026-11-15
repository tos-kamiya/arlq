"""Settings screens for the Pyglet frontends."""

from pyglet.window import key as pgkey

from . import defs as d
from .i18n import t as tr


class PygletSettingsMixin:
    def settings_menu(self) -> None:
        """Show GUI settings and persist the selected display and input options."""
        from . import pyglet_funcs as gui
        current_index = min(
            range(len(gui.UI_SCALE_CHOICES)),
            key=lambda index: abs(gui.UI_SCALE_CHOICES[index] - self._menu_scale),
        )

        repeat_index = gui.KEY_REPEAT_CHOICES.index(self.key_repeat_interval) if self.key_repeat_interval in gui.KEY_REPEAT_CHOICES else 0
        auto_repeat_stop_enabled = self.auto_repeat_stop_enabled
        effect_index = d.COMBAT_EFFECT_SECONDS_CHOICES.index(
            self.combat_effect_seconds
        )
        transition_index = d.FLOOR_TRANSITION_SECONDS_CHOICES.index(
            self.floor_transition_seconds
        )
        bob_enabled = self.idle_bob_enabled
        glide_enabled = self.move_glide_enabled
        rows = ["scale", "repeat", "stop"]
        rows.append("sprites" if self.supports_floor_transition else "effect")
        rows.append("gamepad")
        rows.append("reset")
        # Set by the reset row: also restore the gamepad buttons on apply.
        reset_gamepad = False
        row = 0

        def reset():
            nonlocal current_index, repeat_index, auto_repeat_stop_enabled
            nonlocal effect_index, transition_index, bob_enabled, glide_enabled
            nonlocal reset_gamepad
            current_index = gui.UI_SCALE_CHOICES.index(gui.DEFAULT_UI_SCALE)
            repeat_index = gui.KEY_REPEAT_CHOICES.index(gui.DEFAULT_KEY_REPEAT_INTERVAL)
            auto_repeat_stop_enabled = gui.DEFAULT_AUTO_REPEAT_STOP_ENABLED
            effect_index = d.COMBAT_EFFECT_SECONDS_CHOICES.index(d.COMBAT_EFFECT_SECONDS)
            transition_index = d.FLOOR_TRANSITION_SECONDS_CHOICES.index(
                d.FLOOR_TRANSITION_SECONDS
            )
            bob_enabled = d.IDLE_BOB_ENABLED
            glide_enabled = d.MOVE_GLIDE_ENABLED
            reset_gamepad = True

        def apply():
            self.set_scale(gui.UI_SCALE_CHOICES[current_index])
            self.set_key_repeat_interval(gui.KEY_REPEAT_CHOICES[repeat_index])
            self.set_auto_repeat_stop_enabled(auto_repeat_stop_enabled)
            self.set_combat_effect_seconds(d.COMBAT_EFFECT_SECONDS_CHOICES[effect_index])
            if self.supports_floor_transition:
                self.set_floor_transition_seconds(
                    d.FLOOR_TRANSITION_SECONDS_CHOICES[transition_index]
                )
            if self.supports_idle_bob:
                self.set_idle_bob_enabled(bob_enabled)
            if self.supports_move_glide:
                self.set_move_glide_enabled(glide_enabled)
            if reset_gamepad:
                self.set_gamepad_bindings(
                    gui.DEFAULT_GAMEPAD_HELP_BUTTON,
                    gui.DEFAULT_GAMEPAD_PREVIEW_BUTTON,
                    gui.DEFAULT_GAMEPAD_PREVIEW_MODE,
                )

        while True:
            controller_connected = self._gamepad_is_connected()
            selectable_rows = [
                name for name in rows if name != "gamepad" or controller_connected
            ]
            selectable = len(selectable_rows)
            row = min(row, selectable - 1)
            selected = selectable_rows[row]
            self._clear_drawables()
            self._draw_text(
                (8, 5),
                tr("Settings"),
                gui.COLOR_MAP[gui.CI_YELLOW],
                bold=True,
            )
            values = {
                "scale": (
                    tr("Interface scale"),
                    f"<  {int(gui.UI_SCALE_CHOICES[current_index] * 100)}%  >",
                ),
                "repeat": (
                    tr("Movement repeat interval"),
                    f"<  {tr('No repeat') if gui.KEY_REPEAT_CHOICES[repeat_index] is None else format(gui.KEY_REPEAT_CHOICES[repeat_index], '.1f') + 's'}  >",
                ),
                "stop": (
                    tr("Automatic repeat stop"),
                    f"<  {tr('On') if auto_repeat_stop_enabled else tr('Off')}  >",
                ),
                "effect": (
                    tr("Combat effect duration"),
                    f"<  {d.COMBAT_EFFECT_SECONDS_CHOICES[effect_index]:.1f}s  >",
                ),
                "transition": (
                    tr("Floor transition duration"),
                    f"<  {d.FLOOR_TRANSITION_SECONDS_CHOICES[transition_index]:.1f}s  >",
                ),
                "bob": (
                    tr("Character bobbing"),
                    f"<  {tr('On') if bob_enabled else tr('Off')}  >",
                ),
                "gamepad": (tr("Gamepad button settings"), "->"),
                "sprites": (tr("Sprite display settings"), "->"),
                "reset": (tr("Reset all settings to defaults"), ""),
            }
            for index, name in enumerate(rows):
                label, value = values[name]
                heading = f"{'>' if selected == name else ' '} {label}"
                color = (
                    (112, 116, 124)
                    if name == "gamepad" and not controller_connected
                    else gui.COLOR_MAP["default"]
                )
                y = 8 + 1.5 * index
                self._draw_text((8, y), heading, color, bold=selected == name)
                self._draw_text(
                    (8, y),
                    value,
                    color,
                    bold=selected == name,
                    x_offset=self._text_width(heading, bold=selected == name)
                    + self._menu_cell_size_x,
                )
            help_y = 8 + 1.5 * len(rows) + 1.5
            help_color = (145, 150, 160)
            self._draw_text(
                (8, help_y),
                tr("Up/Down: item   Left/Right: value   Enter / Right: open submenu"),
                help_color,
            )
            self._draw_text(
                (8, help_y + 2),
                tr("Enter / Gamepad button 0: apply or open   Esc / Gamepad button 1: cancel"),
                help_color,
            )
            self._flip()

            def change(step):
                nonlocal current_index, repeat_index, auto_repeat_stop_enabled
                nonlocal effect_index, transition_index, bob_enabled, glide_enabled
                nonlocal row, reset_gamepad
                if selected == "scale":
                    current_index = min(len(gui.UI_SCALE_CHOICES) - 1, max(0, current_index + step))
                elif selected == "repeat":
                    repeat_index = min(len(gui.KEY_REPEAT_CHOICES) - 1, max(0, repeat_index + step))
                elif selected == "stop":
                    auto_repeat_stop_enabled = not auto_repeat_stop_enabled
                elif selected == "effect":
                    effect_index = min(
                        len(d.COMBAT_EFFECT_SECONDS_CHOICES) - 1, max(0, effect_index + step)
                    )
                elif selected == "transition":
                    transition_index = min(
                        len(d.FLOOR_TRANSITION_SECONDS_CHOICES) - 1,
                        max(0, transition_index + step),
                    )
                elif selected == "bob":
                    bob_enabled = not bob_enabled
                elif selected == "sprites" and step > 0:
                    result = self.sprite_settings_menu(
                        effect_index, transition_index, bob_enabled, glide_enabled,
                    )
                    if result is not None:
                        effect_index, transition_index, bob_enabled, glide_enabled = result
                elif selected == "gamepad" and step > 0 and controller_connected:
                    self.gamepad_button_settings_menu()
                    # Buttons set there are saved there; keep them.
                    reset_gamepad = False
                elif selected == "reset" and step > 0:
                    # Show the defaults; Enter on another row applies them.
                    reset()
                    row = 0

            while True:
                self._pump()
                if self._closed:
                    return
                event = self._next_key_event()
                if event is not None:
                    symbol, _ = event
                    if symbol == pgkey.UP:
                        row = (row - 1) % selectable
                        break
                    if symbol == pgkey.DOWN:
                        row = (row + 1) % selectable
                        break
                    if symbol == pgkey.LEFT:
                        change(-1)
                        break
                    if symbol == pgkey.RIGHT:
                        change(1)
                        break
                    if symbol in (pgkey.RETURN, pgkey.NUM_ENTER):
                        if selected in ("sprites", "gamepad", "reset"):
                            change(1)
                            break
                        apply()
                        return
                    if symbol in (pgkey.ESCAPE, pgkey.Q):
                        return

                # Use the same navigation and value changes for the gamepad
                # as for the keyboard. Gamepad button 0 applies; button 1
                # cancels.
                direction = self._controller_direction(self.controller)
                if direction != self.gamepad_previous_direction:
                    self.gamepad_previous_direction = direction
                    if direction == (0, -1):
                        row = (row - 1) % selectable
                        break
                    if direction == (0, 1):
                        row = (row + 1) % selectable
                        break
                    if direction == (-1, 0):
                        change(-1)
                        break
                    if direction == (1, 0):
                        change(1)
                        break
                if 0 in self._gamepad_pressed_buttons:
                    if selected in ("sprites", "gamepad", "reset"):
                        change(1)
                        break
                    apply()
                    return
                if 1 in self._gamepad_pressed_buttons:
                    return

    def sprite_settings_menu(self, effect_index, transition_index, bob_enabled,
                             glide_enabled=True):
        """Edit sprite display options, returning changes to the parent menu."""
        from . import pyglet_funcs as gui

        row = 0
        while True:
            self._clear_drawables()
            self._draw_text((8, 5), tr("Sprite display settings"),
                            gui.COLOR_MAP[gui.CI_YELLOW], bold=True)
            values = (
                (tr("Combat effect duration"), f"{d.COMBAT_EFFECT_SECONDS_CHOICES[effect_index]:.1f}s"),
                (tr("Floor transition duration"), f"{d.FLOOR_TRANSITION_SECONDS_CHOICES[transition_index]:.1f}s"),
                (tr("Character bobbing"), tr("On") if bob_enabled else tr("Off")),
                (tr("Smooth movement"), tr("On") if glide_enabled else tr("Off")),
            )
            for index, (label, value) in enumerate(values):
                heading = f"{'>' if row == index else ' '} {label}"
                pos = (8, 8 + 1.5 * index)
                self._draw_text(pos, heading, gui.COLOR_MAP["default"], bold=row == index)
                self._draw_text(pos, f"<  {value}  >", gui.COLOR_MAP["default"],
                                bold=row == index,
                                x_offset=self._text_width(heading, bold=row == index)
                                + self._menu_cell_size_x)
            help_y = 8 + 1.5 * len(values) + 1.5
            self._draw_text((8, help_y), tr("Up/Down: item   Left/Right: value"), (145, 150, 160))
            self._draw_text((8, help_y + 2), tr("Enter / Gamepad button 0: apply   Esc / Gamepad button 1: cancel"),
                            (145, 150, 160))
            self._flip()

            while True:
                self._pump()
                if self._closed:
                    return None
                event = self._next_key_event()
                symbol = event[0] if event is not None else None
                if symbol in (pgkey.RETURN, pgkey.NUM_ENTER) or 0 in self._gamepad_pressed_buttons:
                    return effect_index, transition_index, bob_enabled, glide_enabled
                if symbol in (pgkey.ESCAPE, pgkey.Q) or 1 in self._gamepad_pressed_buttons:
                    return None
                direction = self._controller_direction(self.controller)
                gamepad_move = (0, 0)
                if direction != self.gamepad_previous_direction:
                    self.gamepad_previous_direction = direction
                    gamepad_move = direction
                if symbol == pgkey.UP or gamepad_move == (0, -1):
                    row = (row - 1) % len(values)
                    break
                if symbol == pgkey.DOWN or gamepad_move == (0, 1):
                    row = (row + 1) % len(values)
                    break
                step = (-1 if symbol == pgkey.LEFT or gamepad_move == (-1, 0)
                        else 1 if symbol == pgkey.RIGHT or gamepad_move == (1, 0) else 0)
                if step:
                    if row == 0:
                        effect_index = min(len(d.COMBAT_EFFECT_SECONDS_CHOICES) - 1,
                                           max(0, effect_index + step))
                    elif row == 1:
                        transition_index = min(len(d.FLOOR_TRANSITION_SECONDS_CHOICES) - 1,
                                               max(0, transition_index + step))
                    elif row == 2:
                        bob_enabled = not bob_enabled
                    else:
                        glide_enabled = not glide_enabled
                    break

    def gamepad_button_settings_menu(self) -> None:
        """Configure gamepad mode buttons while keeping menu controls fixed."""
        from . import pyglet_funcs as gui
        if not self._gamepad_is_connected():
            return
        help_button = self.gamepad_help_button
        preview_button = self.gamepad_preview_button
        preview_mode = self.gamepad_preview_mode
        row = 0

        while True:
            self._clear_drawables()
            self._draw_text(
                (8, 5), tr("Gamepad button settings"), gui.COLOR_MAP[gui.CI_YELLOW], bold=True
            )
            rows = (
                ("Help button", gui._gamepad_button_label(help_button)),
                (
                    "Range / floor preview button",
                    gui._gamepad_button_label(preview_button),
                ),
                (
                    "Range / floor preview behavior",
                    tr("Hold") if preview_mode == "hold" else tr("Toggle"),
                ),
                (f"{tr('Load default settings')} ->", ""),
            )
            for index, (label, value) in enumerate(rows):
                y = 8 + index * 2
                heading = f"{'>' if row == index else ' '} {tr(label)}"
                self._draw_text(
                    (8, y), heading, gui.COLOR_MAP["default"], bold=row == index
                )
                if value:
                    self._draw_text(
                        (8, y),
                        value,
                        gui.COLOR_MAP["default"],
                        bold=row == index,
                        x_offset=self._text_width(heading, bold=row == index)
                        + self._menu_cell_size_x,
                    )
            help_color = (145, 150, 160)
            self._draw_text(
                (8, 18),
                tr("Up/Down: item   Left/Right: change / load defaults with Right"),
                help_color,
            )
            self._draw_text(
                (8, 20),
                tr("Buttons 2-12: assign   Enter / button 0: apply and exit   Esc / button 1: cancel"),
                help_color,
            )
            self._flip()

            while True:
                self._pump()
                if self._closed or not self._gamepad_is_connected():
                    return

                event = self._next_key_event()
                if event is not None:
                    symbol, _ = event
                    if symbol == pgkey.UP:
                        row = (row - 1) % len(rows)
                        break
                    if symbol == pgkey.DOWN:
                        row = (row + 1) % len(rows)
                        break
                    if symbol in (pgkey.LEFT, pgkey.RIGHT):
                        step = -1 if symbol == pgkey.LEFT else 1
                        if row == 3 and symbol == pgkey.RIGHT:
                            help_button = gui.DEFAULT_GAMEPAD_HELP_BUTTON
                            preview_button = gui.DEFAULT_GAMEPAD_PREVIEW_BUTTON
                            preview_mode = gui.DEFAULT_GAMEPAD_PREVIEW_MODE
                        elif row == 0:
                            help_button = gui._next_gamepad_button(
                                help_button, step, preview_button
                            )
                        elif row == 1:
                            preview_button = gui._next_gamepad_button(
                                preview_button, step, help_button
                            )
                        elif row == 2:
                            preview_mode = (
                                "toggle" if preview_mode == "hold" else "hold"
                            )
                        break
                    if symbol in (pgkey.RETURN, pgkey.NUM_ENTER):
                        self.set_gamepad_bindings(
                            help_button, preview_button, preview_mode
                        )
                        return
                    if symbol in (pgkey.ESCAPE, pgkey.Q):
                        return

                pressed_buttons = self._gamepad_pressed_buttons
                assign_button = next(
                    (button for button in gui.GAMEPAD_BUTTONS if button >= 2 and button in pressed_buttons),
                    None,
                )
                if assign_button is not None and row in (0, 1):
                    if row == 0:
                        if assign_button != preview_button:
                            help_button = assign_button
                    else:
                        if assign_button != help_button:
                            preview_button = assign_button
                    break

                direction = self._controller_direction(self.controller)
                if direction != self.gamepad_previous_direction:
                    self.gamepad_previous_direction = direction
                    if direction == (0, -1):
                        row = (row - 1) % len(rows)
                        break
                    if direction == (0, 1):
                        row = (row + 1) % len(rows)
                        break
                    if direction in ((-1, 0), (1, 0)):
                        step = direction[0]
                        if row == 3 and step > 0:
                            help_button = gui.DEFAULT_GAMEPAD_HELP_BUTTON
                            preview_button = gui.DEFAULT_GAMEPAD_PREVIEW_BUTTON
                            preview_mode = gui.DEFAULT_GAMEPAD_PREVIEW_MODE
                        elif row == 0:
                            help_button = gui._next_gamepad_button(
                                help_button, step, preview_button
                            )
                        elif row == 1:
                            preview_button = gui._next_gamepad_button(
                                preview_button, step, help_button
                            )
                        elif row == 2:
                            preview_mode = (
                                "toggle" if preview_mode == "hold" else "hold"
                            )
                        break
                if 0 in pressed_buttons:
                    self.set_gamepad_bindings(
                        help_button, preview_button, preview_mode
                    )
                    return
                if 1 in pressed_buttons:
                    return
