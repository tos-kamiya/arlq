from typing import Any, List, Optional, Set, Tuple

from blessed import Terminal

from . import defs as d
from .i18n import t as tr


MIN_TERMINAL_WIDTH = 80
MIN_TERMINAL_HEIGHT = 24
TERMINAL_SIZE_MESSAGE = "Please resize the terminal to at least 80x24."


def key_to_dir(key: str) -> Optional[d.Point]:
    if key in ("w", "W", "KEY_UP"):
        return (0, -1)
    if key in ("a", "A", "KEY_LEFT"):
        return (-1, 0)
    if key in ("s", "S", "KEY_DOWN"):
        return (0, 1)
    if key in ("d", "D", "KEY_RIGHT"):
        return (1, 0)
    return None


class BlessedUI:
    def __init__(self, term: Terminal, dots: bool = False):
        self.term = term
        self.dots = dots
        self.map_mode = False
        self.shift_direction = False
        self._last_stage: Optional[Tuple[Any, Any]] = None

    def _terminal_is_large_enough(self) -> bool:
        return self.term.width >= MIN_TERMINAL_WIDTH and self.term.height >= MIN_TERMINAL_HEIGHT

    def _wait_for_terminal_size(self) -> None:
        was_too_small = False
        while not self._terminal_is_large_enough():
            was_too_small = True
            print(
                self.term.clear
                + self.term.home
                + self.term.bold(tr(TERMINAL_SIZE_MESSAGE)),
                end="",
                flush=True,
            )
            self.term.inkey(timeout=0.5)
        if was_too_small and self._last_stage is not None:
            self._render_last_stage()

    def _render_last_stage(self) -> None:
        if self._last_stage is None:
            return
        print(
            self._draw_stage(*self._last_stage[0]) + self._draw_status_bar(*self._last_stage[1]),
            end="",
            flush=True,
        )

    def _read_key(self):
        while True:
            self._wait_for_terminal_size()
            key = self.term.inkey(timeout=0.5)
            if key:
                return key

    def _style(
        self, text: str, color: Optional[str] = None, bold: bool = False, dim: bool = False, bg: Optional[str] = None
    ) -> str:
        attr_name = f"{color}_on_{bg}" if color and bg else (f"on_{bg}" if bg else color)
        if dim:
            text = self.term.dim(text)
        if bold and attr_name:
            return self.term.bold(getattr(self.term, attr_name)(text))
        if bold:
            return self.term.bold(text)
        if attr_name:
            return getattr(self.term, attr_name)(text)
        return text

    def _draw_stage(
        self,
        entities: List[d.Entity],
        field: List[List[str]],
        cur_torched: List[List[int]],
        torched: List[List[int]],
        known_types: Set[str],
        show_entities: bool = False,
        checkpoint: Optional[d.Point] = None,
        monochrome: bool = False,
        unlocked_treasures: Optional[Set[str]] = None,
        dim_types: Optional[Set[str]] = None,
        stage_num: int = 0,
        stage_roster: Optional[List[d.MonsterTribe]] = None,
        floor_view: bool = False,
        floor_label: Optional[str] = None,
        arrow_marks=(),
        mimic_marks=(),
    ) -> str:
        output = [self.term.home + self.term.clear]

        def put(
            x: int,
            y: int,
            text: str,
            color: Optional[str] = None,
            bold: bool = False,
            dim: bool = False,
            bg: Optional[str] = None,
        ):
            output.append(
                self.term.move_xy(x, y)
                + self._style(text, None if monochrome else color, bold, dim, None if monochrome else bg)
            )

        player, px, py = None, None, None
        for entity in entities:
            if isinstance(entity, d.Player):
                player = entity
                px, py = entity.x, entity.y
        assert player is not None and px is not None and py is not None

        def cell_background(x: int, y: int) -> Optional[str]:
            if self.dots or not (0 <= y < len(field) and 0 <= x < len(field[y])):
                return None
            discovered = torched[y][x] or show_entities
            return "black" if discovered else None

        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                discovered = bool(torched[y][x] or show_entities)
                visible = bool(cur_torched[y][x])
                if self.dots:
                    if visible:
                        put(
                            x,
                            y,
                            cell,
                            "green" if cell == d.WALL_CHAR else "magenta" if cell == d.CHAR_CALTROP else None,
                        )
                    elif discovered:
                        if cell == d.WALL_CHAR:
                            put(x, y, cell, "green")
                        elif cell == d.CHAR_FLOOR and (x + y) % 2 == 1:
                            put(x, y, ".", dim=True)
                        else:
                            put(x, y, cell)
                    elif (x + y) % 2 == 1:
                        put(x, y, ".", dim=True)
                else:
                    color = "green" if cell == d.WALL_CHAR else "magenta" if cell == d.CHAR_CALTROP else None
                    put(x, y, cell if discovered else " ", color, bg="black" if discovered else None)

        for x, y in mimic_marks:
            if (show_entities or torched[y][x]) and (x, y) != (px, py):
                put(x, y, "M", dim=True, bg=cell_background(x, y))

        if (
            not floor_view
            and checkpoint is not None
            and checkpoint != (px, py)
            and field[checkpoint[1]][checkpoint[0]] not in d.STAIR_CHARS
        ):
            put(
                checkpoint[0],
                checkpoint[1],
                "+",
                "yellow",
                bold=True,
                bg=cell_background(checkpoint[0], checkpoint[1]),
            )

        for (x, y), char in arrow_marks:
            if (show_entities or torched[y][x]) and (x, y) != (px, py):
                put(x, y, char, "red", bold=True, bg=cell_background(x, y))

        player_attack = d.current_player_attack(player, stage_num)

        def paint(glyph: d.FieldGlyph) -> None:
            color = None if glyph.tone in ("companion", "default") else glyph.tone
            put(
                glyph.x,
                glyph.y,
                glyph.char,
                color,
                bold=glyph.bold,
                dim=glyph.dim,
                bg=cell_background(glyph.x, glyph.y),
            )

        if show_entities:
            for entity in entities:
                for glyph in d.preview_entity_glyphs(entity):
                    paint(glyph)

        for entity in entities:
            if torched[entity.y][entity.x] == 0 or (entity.x, entity.y) == (px, py):
                continue
            for glyph in d.revealed_entity_glyphs(
                entity, known_types, show_entities, player_attack, unlocked_treasures, dim_types
            ):
                paint(glyph)

        for fx, fy, ffloor, fchar in getattr(player, "persistent_followers", []):
            if (
                not floor_view
                and ffloor == player.stage3_floor
                and 0 <= fy < len(torched)
                and 0 <= fx < len(torched[fy])
                and torched[fy][fx]
                and (fx, fy) != (px, py)
            ):
                put(fx, fy, fchar, "green", bold=True, bg=cell_background(fx, fy))

        foreground, background = d.player_appearance(player)
        if not floor_view:
            put(
                px,
                py,
                "@",
                None if foreground == "default" else foreground,
                bold=True,
                bg=background or cell_background(px, py),
            )
        if not floor_view and player.companion and px + 1 < d.FIELD_WIDTH:
            put(
                px + 1,
                py,
                player.companion.tribe.char,
                "green" if not self.dots else None,
                dim=self.dots,
                bg=cell_background(px + 1, py),
            )

        tribes = stage_roster if stage_roster is not None else (
            d.get_stage_roster_tribes(stage_num) if stage_num in (1, 2) else []
        )
        ranking_attack = d.current_player_attack(player, stage_num)
        for y, (char, is_player) in enumerate(d.build_strength_column(tribes, ranking_attack, d.FIELD_HEIGHT)):
            if char is None:
                continue
            put(d.FIELD_WIDTH, y, char, bold=is_player)

        if floor_label:
            put(d.FIELD_WIDTH - len(floor_label), d.FIELD_HEIGHT - 1, floor_label)

        return "".join(output) + self.term.normal

    def _draw_status_bar(
        self,
        player: d.Player,
        hours: int,
        stage_num: int = 0,
        message: Optional[str] = None,
        extra_keys: bool = False,
    ) -> str:
        output = []
        x, y = 0, d.FIELD_HEIGHT

        def add(text: str, color: Optional[str] = None, bold: bool = False, dim: bool = False):
            nonlocal x
            output.append(self.term.move_xy(x, y) + self._style(text, color, bold, dim))
            x += self.term.length(text)

        add(d.status_prefix(player, stage_num, hours))
        add(f"LP: {player.lp} [")
        bar_len = 8
        filled = round(max(0, min(player.lp, d.LP_MAX)) / d.LP_MAX * bar_len)
        bar_color = "red" if player.lp <= d.LP_LOW_THRESHOLD else None
        add("#" * filled + "-" * (bar_len - filled), bar_color)
        add("]  ")
        add("/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit")

        y += 1
        x = 0
        if stage_num in (3, 4):
            marks = d.stage3_progress_marks(player)
            for index, (label, achieved) in enumerate(marks):
                spacer = "" if index == len(marks) - 1 else " "
                add(label + spacer, bold=achieved, dim=not achieved)
        if message:
            available = self.term.width - x - 1
            if available > 0:
                add(self.term.truncate(message, available), bold=True)
        return "".join(output)

    def draw_stage(
        self,
        *,
        hours,
        player,
        entities,
        field,
        cur_torched,
        torched,
        known_types,
        show_entities,
        stage_num=0,
        message=None,
        extra_keys=False,
        checkpoint=None,
        unlocked_treasures: Optional[Set[str]] = None,
        dim_types: Optional[Set[str]] = None,
        stage_roster: Optional[List[d.MonsterTribe]] = None,
        floor_view: bool = False,
        floor_label: Optional[str] = None,
        arrow_marks=(),
        mimic_marks=(),
    ):
        self._wait_for_terminal_size()
        show_entities = show_entities or self.map_mode
        stage_args = (
            entities, field, cur_torched, torched, known_types, show_entities,
            checkpoint, self.map_mode, unlocked_treasures, dim_types, stage_num, stage_roster, floor_view, floor_label,
            arrow_marks,
            mimic_marks,
        )
        status_args = (player, hours, stage_num, message, extra_keys)
        self._last_stage = (stage_args, status_args)
        self._render_last_stage()

    def input_direction(self) -> Optional[d.Point]:
        self.shift_direction = False
        while True:
            key = self._read_key()
            if key.code == self.term.KEY_ESCAPE or str(key).lower() == "q":
                return None
            if str(key).lower() == "m":
                self.map_mode = True
                return (0, 0)
            key_name = key.name or str(key)
            shift_names = {
                "KEY_SLEFT": (-1, 0), "KEY_SRIGHT": (1, 0),
            }
            direction = shift_names.get(key_name)
            if direction is not None:
                self.shift_direction = True
                return direction
            direction = key_to_dir(key_name)
            if direction is not None:
                self.shift_direction = len(key_name) == 1 and key_name in "WASD"
                return direction

    def input_alphabet(self) -> Optional[str]:
        key = self._read_key()
        if key.code == self.term.KEY_ESCAPE or str(key).lower() == "q":
            return None
        return str(key).lower()

    def select_stage(self) -> int:
        stage_numbers = d.PUBLIC_STAGE_NUMBERS
        options = [tr("[q]uit")] + [tr("stage [{n}]").format(n=n) for n in stage_numbers]
        current_index = 1
        while True:
            self._wait_for_terminal_size()
            output = [self.term.home + self.term.clear]
            output.append(self.term.move_xy(4, 2) + self.term.bold(self.term.yellow(tr("Stage Selection"))))
            for i, option in enumerate(options):
                prefix = ">" if i == current_index else " "
                text = f"{prefix} {option}"
                output.append(self.term.move_xy(4, 4 + i) + (self.term.bold(text) if i == current_index else text))
            print("".join(output) + self.term.normal, end="", flush=True)

            key = self._read_key()
            if key.name == "KEY_UP":
                current_index = (current_index - 1) % len(options)
            elif key.name == "KEY_DOWN":
                current_index = (current_index + 1) % len(options)
            elif str(key) in ("\n", "\r"):
                return current_index
            elif str(key).lower() == "q" or key.code == self.term.KEY_ESCAPE:
                return 0
            elif str(key).isdigit() and int(str(key)) in stage_numbers:
                return int(str(key))
