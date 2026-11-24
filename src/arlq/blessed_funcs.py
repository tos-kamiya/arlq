import time
from typing import Any, Optional

from . import defs as d
from . import display as ui_display
from .arlq import barrier_lp_damage
from .blessed_map import BlessedMap, EffectAnimation, EffectCell, Terminal
from .blessed_settings import BlessedSettingsMixin
from .braille_effects import effect_frames, wide_effect_frames
from .i18n import t as tr
from .settings import combat_effect_seconds, load_settings
from .treasure_particles import (
    IRIS_SPARKLE_FRAMES,
    IRIS_SPARKLE_SECONDS,
    SPARKLE_TICKS_PER_SECOND,
    iris_sparkle_cells,
    iris_sparkle_frame,
    sparkle_cells,
    sparkle_frame,
    wide_iris_sparkle_frame,
    wide_sparkle_frame,
)

MIN_TERMINAL_WIDTH = 80
MIN_TERMINAL_HEIGHT = 24
TERMINAL_SIZE_MESSAGE = "Please resize the terminal to at least 80x24."
WIDE_TERMINAL_SIZE_MESSAGE = "Please resize the terminal to at least 160x24."


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


class BlessedUI(BlessedSettingsMixin):
    def __init__(self, term: Terminal, dots: bool = False, wide: bool = False):
        self.combat_effect_seconds = combat_effect_seconds(load_settings())
        # Command-line settings for this run only; never saved by themselves.
        self.setting_overrides = {}
        self.term = term
        self.dots = dots
        self.wide = wide
        self.map_mode = False
        self.farthest_preview = False
        self.shift_direction = False
        self._last_stage: Optional[tuple[Any, Any]] = None
        self._treasure_sparkle_cells: list[tuple[int, int]] = []
        self._sparkle_context = None
        self._treasure_sparkle_started: Optional[float] = None
        self._stage_snapshot = ""
        self._effect_player_pos: Optional[tuple[int, int]] = None

    @property
    def _map(self) -> BlessedMap:
        return BlessedMap(self.term, cell_width=2 if getattr(self, "wide", False) else 1)

    def _terminal_is_large_enough(self) -> bool:
        width = MIN_TERMINAL_WIDTH * (2 if getattr(self, "wide", False) else 1)
        return self.term.width >= width and self.term.height >= MIN_TERMINAL_HEIGHT

    def _wait_for_terminal_size(self) -> None:
        was_too_small = False
        while not self._terminal_is_large_enough():
            was_too_small = True
            print(
                self.term.clear
                + self.term.home
                + self.term.bold(tr(WIDE_TERMINAL_SIZE_MESSAGE) if getattr(self, "wide", False)
                                 else tr(TERMINAL_SIZE_MESSAGE)),
                end="",
                flush=True,
            )
            self.term.inkey(timeout=0.5)
        if was_too_small and self._last_stage is not None:
            self._render_last_stage()

    def _render_last_stage(self) -> None:
        if self._last_stage is None:
            return
        self._stage_snapshot = (
            self._draw_stage(*self._last_stage[0]) + self._draw_status_bar(*self._last_stage[1])
        )
        print(self._stage_snapshot, end="", flush=True)

    def _discard_pending_keys(self) -> None:
        """Drop keys already waiting in the terminal, such as OS key
        repeats that arrived while an effect was playing."""
        while self.term.inkey(timeout=0):
            pass

    def stop_movement_repeat(self) -> None:
        # The terminal has no repeat of its own to stop; held-key repeats
        # queued so far are discarded instead.
        self._discard_pending_keys()

    def _read_key(self):
        while True:
            self._wait_for_terminal_size()
            key = self.term.inkey(timeout=0.5)
            if key:
                return key

    def begin_replay(self) -> None:
        self._discard_pending_keys()

    def end_replay(self) -> None:
        self._discard_pending_keys()

    def poll_events(self) -> bool:
        """Discard pending input, except the replay quit keys."""
        cancelled = False
        while key := self.term.inkey(timeout=0):
            if key.code == self.term.KEY_ESCAPE or str(key).lower() == "q":
                cancelled = True
        return cancelled

    def _style(
        self,
        text: str,
        color: Optional[str] = None,
        bold: bool = False,
        dim: bool = False,
        bg: Optional[str] = None,
    ) -> str:
        if color == "default":
            color = None
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
        entities: list[d.Entity],
        field: list[list[str]],
        cur_torched: list[list[int]],
        torched: list[list[int]],
        known_types: set[str],
        show_entities: bool = False,
        debug_show_entities: bool = False,
        checkpoint: Optional[d.Point] = None,
        monochrome: bool = False,
        dim_types: Optional[set[str]] = None,
        stage_num: int = 0,
        stage_roster: Optional[list[d.MonsterTribe]] = None,
        floor_view: bool = False,
        floor_label: Optional[str] = None,
        reachable_cells: Optional[set[d.Point]] = None,
        loop_trail_markers: Optional[set[d.Point]] = None,
        d_gates: Optional[dict[d.Point, str]] = None,
        message=None,
        decor: Optional[list[list[str]]] = None,
        target_floors: Optional[dict[str, int]] = None,
    ) -> str:
        output = [self.term.home + self.term.clear]
        reveal_disguises = debug_show_entities or monochrome
        highlighted_cells = reachable_cells or set()
        loop_markers = loop_trail_markers or set()
        render_monochrome = monochrome and not highlighted_cells

        def put(
            x: int,
            y: int,
            text: str,
            color: Optional[str] = None,
            bold: bool = False,
            dim: bool = False,
            bg: Optional[str] = None,
            rank: bool = False,
        ):
            if rank:
                text = self._map.rank_text(text)
            output.append(self._map.map_text(
                x, y, text, lambda value: self._style(
                    value, None if render_monochrome else color, bold, dim,
                    None if render_monochrome else bg,
                ),
            ))

        player, px, py = None, None, None
        for entity in entities:
            if isinstance(entity, d.Player):
                player = entity
                px, py = entity.x, entity.y
        assert player is not None and px is not None and py is not None
        self._effect_player_pos = None if floor_view else (px, py)
        barrier_damage = barrier_lp_damage(player)

        def cell_background(x: int, y: int) -> Optional[str]:
            if (x, y) in highlighted_cells:
                return "blue"
            if not (0 <= y < len(field) and 0 <= x < len(field[y])):
                return None
            discovered = torched[y][x] or show_entities
            if discovered and field[y][x] == d.CHAR_BARRIER:
                return "red" if barrier_damage == d.BARRIER_LP_DAMAGE else None
            if self.dots:
                return None
            return "black" if discovered else None

        def visible_default_foreground(
            color: Optional[str], background: Optional[str]
        ) -> Optional[str]:
            if color is None and background == "blue":
                return "white"
            if color is None and background == "black":
                return "white"
            if color is None and background == "red":
                return "black"
            return color

        self._combat_cell_backgrounds = {
            (x, y): None if render_monochrome else cell_background(x, y)
            for y, row in enumerate(field) for x in range(len(row))
        }

        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                display_cell = (
                    "+" if cell == d.CHAR_GOLEM_WALL
                    else ("▫" if decor and decor[y][x] in
                          (d.DECOR_OUTER_WALL, d.DECOR_BURIED_WALL) else "□")
                    if getattr(self, "wide", False) and cell in (d.CHAR_WALL, d.CHAR_HIDDEN_D_GATE)
                    else d.CHAR_WALL
                    if cell == d.CHAR_HIDDEN_D_GATE
                    else d.CHAR_FLOOR
                    if cell in d.HIDDEN_STAIRS_CHARS
                    else "∆"
                    if getattr(self, "wide", False) and cell == d.CHAR_STAIRS_UP
                    else "∇"
                    if getattr(self, "wide", False) and cell == d.CHAR_STAIRS_DOWN
                    else cell
                )
                discovered = bool(torched[y][x] or show_entities)
                visible = bool(cur_torched[y][x])
                if discovered and cell == d.CHAR_BARRIER:
                    background = cell_background(x, y)
                    color = "black" if background == "red" else "red"
                    put(x, y, display_cell, color, dim=barrier_damage == 0, bg=background)
                    continue
                if discovered and cell in (*d.SCHOLAR_STAIR_CHARS, d.CHAR_PIT_UP_MARKER):
                    stair_glyph = (
                        d.CHAR_STAIRS_UP
                        if cell in (d.CHAR_SCHOLAR_STAIRS_UP, d.CHAR_PIT_UP_MARKER)
                        else d.CHAR_STAIRS_DOWN
                    )
                    if getattr(self, "wide", False):
                        stair_glyph = ("▵" if cell == d.CHAR_PIT_UP_MARKER else
                                       "∆" if cell == d.CHAR_SCHOLAR_STAIRS_UP else "∇")
                    put(
                        x,
                        y,
                        stair_glyph,
                        "green",
                        bold=True,
                        bg=cell_background(x, y),
                    )
                    continue
                if self.dots:
                    if visible:
                        put(
                            x,
                            y,
                            display_cell,
                            "green"
                            if cell in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
                            else "magenta"
                            if cell == d.CHAR_CALTROP
                            else "yellow"
                            if cell in (
                                d.CHAR_COLLAPSE,
                                d.CHAR_STAIRS_UP,
                                d.CHAR_STAIRS_DOWN,
                            )
                            else None,
                            bg="blue" if (x, y) in highlighted_cells else None,
                        )
                    elif discovered:
                        if cell in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE):
                            put(x, y, display_cell, "green", bg="blue" if (x, y) in highlighted_cells else None)
                        elif cell in (d.CHAR_STAIRS_UP, d.CHAR_STAIRS_DOWN):
                            put(
                                x,
                                y,
                                display_cell,
                                "yellow",
                                bg="blue" if (x, y) in highlighted_cells else None,
                            )
                        else:
                            put(x, y, display_cell,
                                bg="blue" if (x, y) in highlighted_cells else None)
                    elif (x + y) % 2 == 1:
                        put(x, y, ".", dim=True)
                else:
                    color = (
                        "green"
                        if cell in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)
                        else "magenta"
                        if cell == d.CHAR_CALTROP
                        else "yellow"
                        if cell in (
                            d.CHAR_COLLAPSE,
                            d.CHAR_STAIRS_UP,
                            d.CHAR_STAIRS_DOWN,
                        )
                        else None
                    )
                    background = cell_background(x, y)
                    put(x, y, display_cell if discovered else " ", color,
                        bg=background)

        for (x, y), glyph in (d_gates or {}).items():
            if field[y][x] == d.CHAR_D_GATE:
                put(
                    x,
                    y,
                    glyph,
                    "green",
                    bold=True,
                    bg=cell_background(x, y),
                )

        for y, row in enumerate(decor or ()):
            for x, value in enumerate(row):
                if value.startswith(d.DECOR_BRIDGEHEAD_PREFIX) and torched[y][x]:
                    put(x, y, value[len(d.DECOR_BRIDGEHEAD_PREFIX):], "yellow",
                        bold=True, bg=cell_background(x, y))
                elif (value in (d.DECOR_BOSS_ROUTE, d.DECOR_BOSS_ROUTE_FALLEN_ROCKS)
                        and torched[y][x] and field[y][x] in (d.CHAR_FLOOR, d.CHAR_PIT_LANDING)
                        and (floor_view or (x, y) != (px, py))):
                    put(x, y, ".", "yellow", bg=cell_background(x, y))

        if not floor_view:
            for x, y in loop_markers:
                if (
                    0 <= y < len(field)
                    and 0 <= x < len(field[y])
                    and torched[y][x]
                    and field[y][x] in (d.CHAR_FLOOR, d.CHAR_PIT_LANDING)
                    and (x, y) != (px, py)
                ):
                    put(
                        x,
                        y,
                        "・" if getattr(self, "wide", False) else ".",
                        "cyan",
                        bg=cell_background(x, y),
                    )

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

        for entity in entities:
            if not isinstance(entity, d.Monster) or entity.tribe.char != "k":
                continue
            for (x, y), char in entity.arrow_marks:
                if (show_entities or torched[y][x]) and (x, y) != (px, py):
                    put(x, y, char, "red", bold=True, bg=cell_background(x, y))

        player_attack = d.current_player_attack(player)
        party_tones = (
            ui_display.monster_party_tones(entities, known_types, player_attack)
            if stage_num in (5, 6) else None
        )

        def paint(glyph: ui_display.FieldGlyph, rank: bool = False) -> None:
            color = (
                None
                if glyph.tone in (
                    "fairy", "member", "member_waiting", "default", "stair"
                )
                else glyph.tone
            )
            background = cell_background(glyph.x, glyph.y)
            put(
                glyph.x,
                glyph.y,
                glyph.char,
                visible_default_foreground(color, background),
                bold=False if glyph.tone in ("stair", "member") else glyph.bold,
                dim=glyph.dim,
                bg=background,
                rank=rank,
            )

        drawing_entities = ui_display.entities_for_drawing(entities)
        entity_glyphs = []
        if show_entities:
            for entity in drawing_entities:
                entity_glyphs.extend((entity, glyph) for glyph in ui_display.preview_entity_glyphs(
                    entity, reveal_disguises=reveal_disguises, known_types=known_types,
                ))

        for entity in drawing_entities:
            if torched[entity.y][entity.x] == 0 or (entity.x, entity.y) == (px, py):
                continue
            entity_glyphs.extend((entity, glyph) for glyph in ui_display.revealed_entity_glyphs(
                entity, known_types, show_entities, player_attack, dim_types,
                reveal_disguises=reveal_disguises,
                debug_show_entities=debug_show_entities,
                party_entities=entities if stage_num in (5, 6) else None,
                party_tones=party_tones,
            ))

        def is_bracket(entity, glyph):
            return glyph.char in ("[", "]") and glyph.x != entity.x

        occupied = {(glyph.x, glyph.y) for entity, glyph in entity_glyphs
                    if not is_bracket(entity, glyph)}
        bracket_owners = {}
        for entity, glyph in entity_glyphs:
            if is_bracket(entity, glyph):
                bracket_owners.setdefault((glyph.x, glyph.y), set()).add(id(entity))
        occupied.update(point for point, owners in bracket_owners.items() if len(owners) > 1)
        if not floor_view:
            occupied.add((px, py))
            occupied.update((glyph.x, glyph.y) for glyph in ui_display.member_glyphs(player))
            wall_break = ui_display.player_wall_break_glyph(player)
            if wall_break is not None:
                occupied.add((wall_break.x, wall_break.y))
            occupied.update(loop_trail_markers or set())
            if checkpoint is not None:
                occupied.add(checkpoint)
        occupied.update((x, y) for entity in entities
                        if isinstance(entity, d.Monster) and entity.tribe.char == "k"
                        for (x, y), _ in entity.arrow_marks
                        if show_entities or torched[y][x])
        for entity, glyph in entity_glyphs:
            if (is_bracket(entity, glyph)
                    and not ui_display.core_bracket_is_clear(glyph, field, occupied, decor)):
                continue
            paint(glyph, rank=(isinstance(entity, d.Monster)
                               and glyph.x == entity.x + 1
                               and glyph.char in ("'", '"')))

        if not floor_view:
            for glyph in ui_display.member_glyphs(player):
                paint(glyph)
            wall_break_glyph = ui_display.player_wall_break_glyph(player)
            if wall_break_glyph is not None:
                put(
                    wall_break_glyph.x,
                    wall_break_glyph.y,
                    "⍀" if getattr(self, "wide", False) else wall_break_glyph.char,
                    "white",
                    bold=True,
                    bg=cell_background(wall_break_glyph.x, wall_break_glyph.y),
                )

        foreground, background = ui_display.player_appearance(player)
        if not floor_view:
            player_background = background or cell_background(px, py)
            put(
                px,
                py,
                "@",
                visible_default_foreground(
                    None if foreground == "default" else foreground,
                    player_background,
                ),
                bold=True,
                bg=player_background,
            )
            if player.status_popup and player.status_popup_ticks > 0:
                output.append(self._map.status_popup(
                    px, py, player.status_popup, player.status_popup_tone,
                    d.FIELD_WIDTH, d.FIELD_HEIGHT, render_monochrome))
        if not floor_view and player.fairy and px + 1 < d.FIELD_WIDTH:
            put(
                px + 1,
                py,
                player.fairy.tribe.char,
                "green" if not self.dots else None,
                dim=self.dots,
                bg=cell_background(px + 1, py),
            )

        tribes = stage_roster if stage_roster is not None else (
            d.get_stage_roster_tribes(stage_num) if stage_num in (1, 2) else []
        )
        ranking_attack = d.current_player_attack(player)
        for y, (strength_char, is_player) in enumerate(ui_display.build_strength_column(tribes, ranking_attack, d.FIELD_HEIGHT)):
            if strength_char is None:
                continue
            gauge_x = d.FIELD_WIDTH + d.FIELD_SIDEBAR_GAP + 2 - len(strength_char)
            known = is_player or ui_display.strength_label_known(strength_char, known_types)
            put(gauge_x, y, strength_char, "white", bold=is_player, dim=not known, rank=True)

        if stage_num in d.ELF_STAGES:
            progress_x = 0
            for label, achieved in ui_display.elf_stage_progress_marks(
                    player, stage_num, target_floors):
                put(
                    progress_x,
                    d.FIELD_HEIGHT - 1,
                    label,
                    bold=achieved,
                    dim=not achieved,
                )
                progress_x += len(label) + 1
        elif stage_num == 6:
            progress_x = 0
            for label, achieved in ui_display.stage6_progress_marks(player, target_floors):
                put(
                    progress_x,
                    d.FIELD_HEIGHT - 1,
                    label,
                    bold=achieved,
                    dim=not achieved,
                )
                progress_x += len(label) + 1

        if floor_label:
            put(d.FIELD_WIDTH - len(floor_label) - 2, d.FIELD_HEIGHT - 1, floor_label)

        from .stage5 import TrialDialogue

        if isinstance(message, TrialDialogue) and not floor_view:
            output.append(self._map.dialogue(
                px, py, str(message), d.FIELD_WIDTH, d.FIELD_HEIGHT, render_monochrome))

        return "".join(output) + self.term.normal

    def _draw_status_bar(
        self,
        player: d.Player,
        turn: int,
        stage_num: int = 0,
        message: Optional[str] = None,
        extra_keys: bool = False,
        game_start_turn: Optional[int] = None,
    ) -> str:
        output = []
        x, y = 0, d.FIELD_HEIGHT

        def add(text: str, color: Optional[str] = None, bold: bool = False, dim: bool = False):
            nonlocal x
            output.append(self._map.screen_text(
                x, y, text, lambda value: self._style(value, color, bold, dim)))
            x += self.term.length(text)

        add(ui_display.status_prefix(player, stage_num, turn, game_start_turn))
        add(f"LP: {int(player.lp)} [")
        bar_len = 8
        lp_max = d.player_lp_max(player)
        filled = round(max(0, min(player.lp, lp_max)) / lp_max * bar_len)
        bar_color = (
            "magenta"
            if player.lp > lp_max
            else "red"
            if player.lp <= d.LP_LOW_THRESHOLD
            else None
        )
        add("#" * filled + "-" * (bar_len - filled), bar_color)
        add("]  ")
        add("/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit")

        y += 1
        x = 0
        from .stage5 import TrialDialogue

        dialogue = message if isinstance(message, TrialDialogue) else None
        party = "" if dialogue else player.last_encounter_party
        if party:
            party_panel = f"[{party}]  "
            available = max(0, self.term.width - x - 1)
            add(self.term.truncate(party_panel, available), color="cyan")
        if message and dialogue is None:
            available = self.term.width - x - 1
            if available > 0:
                add(self.term.truncate(message, available), color="yellow")
        return "".join(output)

    def draw_stage(
        self,
        *,
        turn,
        game_start_turn=None,
        player,
        entities,
        field,
        cur_torched,
        torched,
        known_types,
        show_entities,
        debug_show_entities=False,
        stage_num=0,
        message=None,
        extra_keys=False,
        checkpoint=None,
        dim_types: Optional[set[str]] = None,
        stage_roster: Optional[list[d.MonsterTribe]] = None,
        floor_view: bool = False,
        floor_label: Optional[str] = None,
        reachable_cells: Optional[set[d.Point]] = None,
        loop_trail_markers: Optional[set[d.Point]] = None,
        d_gates: Optional[dict[d.Point, str]] = None,
        decor: Optional[list[list[str]]] = None,
        respawn_glows: Optional[set[d.Point]] = None,
        target_floors: Optional[dict[str, int]] = None,
    ):
        # Respawn glows are not drawn in the terminal.
        self._wait_for_terminal_size()
        show_entities = show_entities or self.map_mode
        stage_args = (
            entities, field, cur_torched, torched, known_types, show_entities,
            debug_show_entities, checkpoint, self.map_mode, dim_types,
            stage_num, stage_roster, floor_view, floor_label, reachable_cells,
            loop_trail_markers,
            d_gates,
            message,
            decor,
            target_floors,
        )
        status_args = (
            player,
            turn,
            stage_num,
            message,
            extra_keys,
            game_start_turn,
        )
        blocked = set(loop_trail_markers or ())
        if checkpoint is not None:
            blocked.add(checkpoint)
        if not (player.treasure_collected and player.stage_won):
            self._treasure_sparkle_started = None
        elif self._treasure_sparkle_started is None:
            self._treasure_sparkle_started = time.monotonic()
        self._treasure_sparkle_center = (player.x, player.y)
        self._sparkle_context = (
            None if floor_view or self.map_mode
            else (player, entities, field, torched, decor, blocked)
        )
        self._treasure_sparkle_cells = (
            sparkle_cells(player, entities, field, torched, decor, blocked)
            if player.treasure_collected and player.stage_won and not floor_view
            and not self.map_mode and self.combat_effect_seconds > 0 else []
        )
        self._last_stage = (stage_args, status_args)
        self._render_last_stage()

    def draw_combat_effect(self, pos, won: bool) -> None:
        seconds = self.combat_effect_seconds
        if seconds == 0:
            return
        positions = [pos] if len(pos) == 2 and all(
            isinstance(value, (int, float)) for value in pos
        ) else pos
        cells = [EffectCell(*point, "*", "blue" if won else "red",
                            self._combat_cell_backgrounds.get(point), True)
                 for point in positions]
        print(self._map.effect_frame(cells), end="", flush=True)
        time.sleep(seconds)
        self._discard_pending_keys()

    def _draw_braille_effect(self, name, pos):
        wide = getattr(self, "wide", False)
        loader = wide_effect_frames if wide else effect_frames
        seconds, frames = loader(name, pos, self.combat_effect_seconds)
        if not frames:
            return
        effect_frames_data = []
        for cells in frames:
            frame = []
            for item in cells:
                if wide:
                    (x, y), subcell, char, color = item
                else:
                    (x, y), char, color = item
                    subcell = None
                if (x, y) == self._effect_player_pos:
                    continue
                bg = self._combat_cell_backgrounds.get((x, y))
                fallback = ("white" if name == "Vortex" and color == (170, 170, 170)
                            else {"Boss": "yellow", "Dungeon Core": "magenta", "Vortex": "cyan",
                                  "Core Calamity": "magenta"}[name])
                frame.append(EffectCell(x, y, char, None if self.map_mode else color,
                                        bg, fallback_color=fallback, subcell=subcell))
            effect_frames_data.append(frame)
        animation = EffectAnimation(effect_frames_data, seconds / len(frames))
        self._map.play_effect(animation, self._stage_snapshot, self._wait_for_terminal_size)
        self._discard_pending_keys()

    def draw_iris_ration(self, pos):
        """Twinkle a small treasure-like sparkle in the cells beside Iris as
        she hands over her ration."""
        if self.combat_effect_seconds == 0 or self._sparkle_context is None:
            return
        cells = iris_sparkle_cells(pos, *self._sparkle_context)
        if not cells:
            return
        frames = []
        for index in range(IRIS_SPARKLE_FRAMES):
            if getattr(self, "wide", False):
                frames.append([EffectCell(*point, char, "yellow",
                                          self._combat_cell_backgrounds.get(point), True,
                                          subcell=subcell)
                               for point, subcell, char in wide_iris_sparkle_frame(cells, index, pos)])
            else:
                frames.append([EffectCell(*point, char, "yellow",
                                          self._combat_cell_backgrounds.get(point), True)
                               for point, char in iris_sparkle_frame(cells, index, pos)])
        animation = EffectAnimation(frames, IRIS_SPARKLE_SECONDS / IRIS_SPARKLE_FRAMES)
        self._map.play_effect(animation, self._stage_snapshot, self._wait_for_terminal_size)
        self._discard_pending_keys()

    def draw_vortex_effect(self, pos):
        self._draw_braille_effect("Vortex", pos)

    def draw_boss_afterglow(self, pos):
        self._draw_braille_effect("Boss", pos)

    def draw_core_burst(self, pos):
        self._draw_braille_effect("Dungeon Core", pos)

    def present_core_calamity(self, at, view):
        """The core ran wild at the time limit: cut to its floor and let its
        smoke reach out and scatter."""
        if self.combat_effect_seconds == 0:
            return
        self.draw_stage(**view)
        self._draw_braille_effect("Core Calamity", at)

    def draw_rewind_transition(self, message: str) -> None:
        """Show the Loop Fairy transition before the next stage frame."""
        self._wait_for_terminal_size()
        print(self._map.rewind_transition(message, d.FIELD_WIDTH, d.FIELD_HEIGHT),
              end="", flush=True)

    def input_direction(self) -> Optional[d.Point]:
        self.shift_direction = False
        while True:
            key = self._read_key()
            if key.code == self.term.KEY_ESCAPE or str(key).lower() == "q":
                return None
            key_name = key.name or str(key)
            if key_name.lower() in ("f", "key_f") or str(key).lower() == "f":
                self.farthest_preview = not self.farthest_preview
                self.escape_check_requested = True
                return (0, 0)
            if str(key).lower() == "m":
                self.map_mode = True
                return (0, 0)
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

    def confirm_game_over(self):
        return self._confirm_choice(tr("No reachable encounters or exits. End the game?"))

    def _confirm_choice(self, prompt):
        yes = False
        while True:
            self._wait_for_terminal_size()
            width = min(d.FIELD_WIDTH - 3, self.term.width)
            middle = min(d.FIELD_HEIGHT, self.term.height) // 2
            output = [self.term.home + self.term.clear]
            lines = ui_display.wrap_prompt(prompt, self.term.length, width)
            lines += ["", ui_display.choice_labels(yes), "", tr("Esc / q: cancel")]
            for offset, text in enumerate(lines):
                x = max(0, (width - self.term.length(text)) // 2)
                output.append(self.term.move_xy(x, middle - len(lines) // 2 + offset))
                if offset == len(lines) - 3:
                    output.append(self._style("    ", bg="black").join(
                        self._style(label, color="white", bold=selected, bg="black")
                        for label, selected in ui_display.choice_options(yes)
                    ))
                else:
                    output.append(self._style(text, color="white", bold=True, bg="black"))
            print("".join(output) + self.term.normal, end="", flush=True)
            key = self._read_key()
            if str(key).lower() == "y":
                return True
            if str(key).lower() == "q" or key.code == self.term.KEY_ESCAPE:
                return None
            if str(key).lower() == "n":
                return False
            if str(key) in ("\n", "\r"):
                return yes
            if key.name in ("KEY_LEFT", "KEY_RIGHT"):
                yes = key.name == "KEY_LEFT"

    def input_game_over(self):
        """Wait for a game-over command or a shifted floor-view direction."""
        last_tick = None
        while True:
            self._wait_for_terminal_size()
            if self._treasure_sparkle_cells:
                tick = int((time.monotonic() - self._treasure_sparkle_started) * SPARKLE_TICKS_PER_SECOND)
                if tick != last_tick:
                    output = [self._stage_snapshot]
                    if getattr(self, "wide", False):
                        cells = [EffectCell(*point, char, "yellow",
                                            self._combat_cell_backgrounds.get(point), True,
                                            subcell=subcell)
                                 for point, subcell, char in wide_sparkle_frame(
                                     self._treasure_sparkle_cells, tick, self._treasure_sparkle_center)]
                    else:
                        cells = [EffectCell(x, y, char, "yellow",
                                            self._combat_cell_backgrounds.get((x, y)), True)
                                 for (x, y), char in sparkle_frame(
                                     self._treasure_sparkle_cells, tick, self._treasure_sparkle_center)]
                    output.append(self._map.effect_frame(cells))
                    print("".join(output) + self.term.normal, end="", flush=True)
                    last_tick = tick
            key = self.term.inkey(timeout=0.2 if self._treasure_sparkle_cells else 0.5)
            if not key:
                continue
            key_name = key.name or str(key)
            key_text = str(key).lower()
            if key.code == self.term.KEY_ESCAPE or key_text == "q":
                return None
            shifted_directions = {
                "W": (0, -1), "S": (0, 1),
                "KEY_SUP": (0, -1), "KEY_SDOWN": (0, 1),
                "KEY_SLEFT": (-1, 0), "KEY_SRIGHT": (1, 0),
                "KEY_SHIFT_UP": (0, -1), "KEY_SHIFT_DOWN": (0, 1),
                "KEY_SHIFT_LEFT": (-1, 0), "KEY_SHIFT_RIGHT": (1, 0),
                "KEY_SHIFT_W": (0, -1), "KEY_SHIFT_S": (0, 1),
            }
            if key_name in shifted_directions:
                return (*shifted_directions[key_name], True)
            if key_text == "m":
                return "m"
            if key_text == "s":
                return "s"
            if key_text == "h":
                self.controls_menu()
                return (0, 0, False)
            direction = key_to_dir(key_name)
            if direction is not None:
                return (*direction, False)

    def select_stage(self, stage_numbers: tuple[int, ...] = d.PUBLIC_STAGE_NUMBERS) -> int:
        options = [tr("[q]uit")] + [
            tr("Stage {number}").format(number=f"[{n}]") for n in stage_numbers
        ]
        options.append(tr("[s]ettings"))
        settings_index = len(options) - 1
        stage_rows = (len(stage_numbers) + 1) // 2
        positions = [(0, 0)] + [
            (i % 2, 1 + i // 2) for i in range(len(stage_numbers))
        ] + [(0, stage_rows + 1)]
        current_index = 1

        def move_selection(dx, dy):
            col, row = positions[current_index]
            if dy:
                target_row = (row + dy) % (stage_rows + 2)
                candidates = [i for i, (_, r) in enumerate(positions) if r == target_row]
                return min(candidates, key=lambda i: abs(positions[i][0] - col))
            target = (col + dx, row)
            return positions.index(target) if target in positions else current_index

        while True:
            self._wait_for_terminal_size()
            output = [self.term.home + self.term.clear]
            output.append(self.term.move_xy(4, 2) + self.term.bold(self.term.yellow(tr("Stage Selection"))))
            for i, option in enumerate(options):
                text = f"{'>' if i == current_index else ' '} {option}"
                col, row = positions[i]
                display_row = row + (2 if i == settings_index else 1 if i else 0)
                output.append(self.term.move_xy(4 + 22 * col, 4 + display_row)
                              + (self.term.bold(text) if i == current_index else text))
            print("".join(output) + self.term.normal, end="", flush=True)

            key = self._read_key()
            if key.name == "KEY_UP":
                current_index = move_selection(0, -1)
            elif key.name == "KEY_DOWN":
                current_index = move_selection(0, 1)
            elif key.name == "KEY_LEFT":
                current_index = move_selection(-1, 0)
            elif key.name == "KEY_RIGHT":
                current_index = move_selection(1, 0)
            elif str(key) in ("\n", "\r"):
                if current_index == settings_index:
                    self.settings_menu()
                    continue
                return stage_numbers[current_index - 1] if current_index else 0
            elif str(key).lower() == "s":
                self.settings_menu()
            elif str(key).lower() == "q" or key.code == self.term.KEY_ESCAPE:
                return 0
            elif str(key).isdigit() and int(str(key)) in stage_numbers:
                return int(str(key))
