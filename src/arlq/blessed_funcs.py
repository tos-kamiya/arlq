from typing import List, Optional, Set

from blessed import Terminal

from . import defs as d
from .utils import block_progress_cells


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
    def __init__(self, term: Terminal):
        self.term = term
        self.map_mode = False
        self._last_stage = None

    def _terminal_is_large_enough(self) -> bool:
        return self.term.width >= MIN_TERMINAL_WIDTH and self.term.height >= MIN_TERMINAL_HEIGHT

    def _wait_for_terminal_size(self) -> None:
        was_too_small = False
        while not self._terminal_is_large_enough():
            was_too_small = True
            print(
                self.term.clear
                + self.term.home
                + self.term.bold(TERMINAL_SIZE_MESSAGE),
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
        if dim:
            return self.term.dim(text)
        attr_name = f"{color}_on_{bg}" if color and bg else (f"on_{bg}" if bg else color)
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

        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                if cur_torched[y][x]:
                    put(x, y, cell, "green" if cell == d.WALL_CHAR else "magenta" if cell == d.CHAR_CALTROP else None)
                elif torched[y][x] or show_entities:
                    if cell == d.WALL_CHAR:
                        put(x, y, cell, "green")
                    elif cell == " " and (x + y) % 2 == 1:
                        put(x, y, ".", dim=True)
                    else:
                        put(x, y, cell)
                elif (x + y) % 2 == 1:
                    put(x, y, ".", dim=True)

        if checkpoint is not None and checkpoint != (px, py):
            put(checkpoint[0], checkpoint[1], "+", "yellow", bold=True)

        player_attack = d.player_attack_by_level(player)
        if show_entities:
            for entity in entities:
                char = None
                if isinstance(entity, (d.Companion, d.Monster)):
                    char = entity.tribe.char
                elif isinstance(entity, d.Treasure):
                    char = d.CHAR_TREASURE
                if char is not None:
                    put(entity.x, entity.y, char, dim=True)
                    if isinstance(entity, d.Monster) and entity.empowered > 1:
                        put(entity.x + 1, entity.y, "'", dim=True)

        for entity in entities:
            if torched[entity.y][entity.x] == 0 or (entity.x, entity.y) == (px, py):
                continue
            if isinstance(entity, d.Companion):
                char = entity.tribe.char if entity.tribe.char in known_types or show_entities else "!"
                put(entity.x, entity.y, char, bold=True)
            elif isinstance(entity, d.Monster):
                monster = entity
                char = monster.tribe.char
                type_key = d.monster_type_key(monster)
                if type_key not in known_types:
                    if not show_entities:
                        put(entity.x, entity.y, "?", "yellow", bold=True)
                else:
                    color = "yellow" if monster.tribe.effect == d.EFFECT_UNLOCK_TREASURE else (
                        "blue" if d.monster_level(monster) <= player_attack else "red"
                    )
                    put(entity.x, entity.y, char, color, bold=True, dim=bool(dim_types and char in dim_types))
                    if monster.empowered > 1:
                        put(entity.x + 1, entity.y, "'", color, bold=True, dim=bool(dim_types and char in dim_types))
            elif isinstance(entity, d.Treasure):
                if unlocked_treasures is not None and entity.unlock_key in unlocked_treasures:
                    put(entity.x, entity.y, d.CHAR_TREASURE, "yellow", bold=True)

        # "@" is white by default, matching the GUI. Poisoned tints the text
        # magenta; low LP takes over the text as red instead (it's the more
        # urgent state), pushing poisoned down to a background highlight so
        # both remain visible at once.
        is_poisoned = player.item == d.ITEM_POISONED
        if player.lp <= d.LP_LOW_THRESHOLD:
            player_fg, player_bg = "red", ("magenta" if is_poisoned else None)
        elif is_poisoned:
            player_fg, player_bg = "magenta", None
        else:
            player_fg, player_bg = "white", None
        put(px, py, "@", player_fg, bold=True, bg=player_bg)
        if player.companion and px + 1 < d.FIELD_WIDTH:
            put(px + 1, py, player.companion.tribe.char, dim=True)

        tribes = stage_roster if stage_roster is not None else (
            d.get_stage_roster_tribes(stage_num) if stage_num in (1, 2) else []
        )
        ranking_attack = d.player_attack_by_level(player, include_stage3_bonuses=stage_num == 3)
        for y, (char, is_player) in enumerate(d.build_strength_column(tribes, ranking_attack, d.FIELD_HEIGHT)):
            if char is None:
                continue
            put(d.FIELD_WIDTH, y, char, "white", bold=is_player)

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
            x += len(text)

        has_stage3_k = stage_num == 3 and getattr(player, "stage3_flags", 0) & d.STAGE3_K_FLAG
        has_stage3_j = stage_num == 3 and any(
            follower[3] == "J" for follower in getattr(player, "persistent_followers", [])
        )
        if player.item == d.ITEM_SWORD_X1_5:
            level_str, item_str = f"LVL: {player.level} x1.5", f"+{player.item}({player.item_taken_from})"
        elif player.item == d.ITEM_SWORD_CURSED:
            level_str, item_str = f"LVL: {player.level} x3", f"+{player.item}({player.item_taken_from})"
        elif player.item == d.ITEM_POISONED:
            level_str, item_str = f"LVL: {player.level} /2", f"+{player.item}({player.item_taken_from})"
            if has_stage3_k:
                level_str += " x1.2"
        else:
            level_str, item_str = f"LVL: {player.level}", ""
            if has_stage3_k:
                level_str += " x1.2"
        if has_stage3_j:
            level_str += " +25%"

        if stage_num == 3:
            add(f"ST: 3 F: {player.stage3_floor + 1}  ")
        elif stage_num != 0:
            add(f"ST: {stage_num}  ")
        add(f"HRS: {hours}  ")
        add(level_str + "  ")
        add(item_str + "  ")
        add(f"LP: {player.lp} [")
        bar_len = 8
        bar_color = "red" if player.lp <= d.LP_LOW_THRESHOLD else "white"
        for char, _ in block_progress_cells(player.lp, d.LP_MAX, bar_len, 0):
            add(char, bar_color)
        add("]  ")
        add("/ [q]uit/[m]ap/[s]eed" if extra_keys else "/ [q]uit")

        y += 1
        x = 0
        if stage_num == 3:
            elf_floors = getattr(player, "stage3_elf_floors", {})
            show_elf_floors = getattr(player, "stage3_flags", 0) & d.STAGE3_I_FLAG
            for label, bit in (("C", 1), ("I", 2), ("J", 64), ("K", 4), ("H", 8), ("W", 16)):
                progress_label = label + (str(elf_floors[label]) if show_elf_floors and label in elf_floors else "")
                add(progress_label + " ", bold=bool(player.stage3_flags & bit), dim=not bool(player.stage3_flags & bit))
            add("T", bold=player.stage3_won, dim=not player.stage3_won)
        if message:
            available = self.term.width - x - 1
            if available > 0:
                add(message[:available], bold=True)
        return "".join(output)

    def draw_stage(
        self,
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
    ):
        self._wait_for_terminal_size()
        show_entities = show_entities or self.map_mode
        stage_args = (
            entities, field, cur_torched, torched, known_types, show_entities,
            checkpoint, self.map_mode, unlocked_treasures, dim_types, stage_num, stage_roster,
        )
        status_args = (player, hours, stage_num, message, extra_keys)
        self._last_stage = (stage_args, status_args)
        self._render_last_stage()

    def input_direction(self) -> Optional[d.Point]:
        while True:
            key = self._read_key()
            if key.code == self.term.KEY_ESCAPE or str(key).lower() == "q":
                return None
            if str(key).lower() == "m":
                self.map_mode = True
                return (0, 0)
            direction = key_to_dir(key.name or str(key))
            if direction is not None:
                return direction

    def input_alphabet(self) -> Optional[str]:
        key = self._read_key()
        if key.code == self.term.KEY_ESCAPE or str(key).lower() == "q":
            return None
        return str(key).lower()

    def select_stage(self) -> int:
        num_stages = len(d.STAGE_TO_SPAWN_CONFIGS)
        options = ["[q]uit"] + [f"stage [{n}]" for n in range(1, num_stages + 1)]
        current_index = 1
        while True:
            self._wait_for_terminal_size()
            output = [self.term.home + self.term.clear]
            output.append(self.term.move_xy(2, 2) + self.term.bold(self.term.yellow("Stage Selection")))
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
            elif str(key).isdigit() and 1 <= int(str(key)) <= num_stages:
                return int(str(key))
