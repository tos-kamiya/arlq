"""Gameplay trace record/replay support.

See docs/gameplay-trace-spec.md for the full specification. This module is
internal developer/testing tooling (system-test golden masters), not a
player-facing feature, so it is deliberately kept separate from arlq.py and
game_engine.py: those files call into `TraceRecorder` at a handful of points, and
this module owns the trace file's schema plus the replay-side input source.
"""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from . import defs as d
from .__about__ import __version__
from .game_events import TurnEvents, WallEvent

SCHEMA_VERSION = 2

DIR_TO_KEY: Dict[Tuple[int, int], str] = {
    (0, -1): "U",
    (0, 1): "D",
    (-1, 0): "L",
    (1, 0): "R",
}
KEY_TO_DIR: Dict[str, Tuple[int, int]] = {key: direction for direction, key in DIR_TO_KEY.items()}


class TraceRecorder:
    """Accumulates one play session's turns for --trace-record/--trace-replay
    output. `run_game()` (arlq.py and game_engine.py) calls `begin_turn()` /
    `set_player()` / `commit_turn()` / `record_quit()` / `set_outcome()`
    directly; `update_entities()` / `_step()` and their helpers call
    `record_wall()` / `record_contact()` / `add_expired()` /
    `add_world_event()` for the turn currently being built.
    """

    def __init__(self, params: Dict[str, Any]) -> None:
        self.params = params
        self.turns: List[Dict[str, Any]] = []
        self.outcome: Optional[str] = None
        self._current: Optional[Dict[str, Any]] = None
        self._turn_no = 0

    def begin_turn(self, input_key: str) -> None:
        self._turn_no += 1
        self._current = {"turn": self._turn_no, "input": input_key}

    def set_player(self, player: d.Player, stage_num: int) -> None:
        if self._current is None:
            return
        self._current["player"] = {
            "lp": player.lp,
            "level": player.level,
            "attack": d.current_player_attack(player, stage_num),
        }

    def record_wall(self, wall: WallEvent) -> None:
        if self._current is not None:
            wall_record: Dict[str, Any] = {"result": wall.result}
            if wall.item_uses_left is not None:
                wall_record["item_uses_left"] = wall.item_uses_left
            self._current["wall"] = wall_record

    def record_events(self, events: TurnEvents) -> None:
        """Serialize gameplay events into the trace schema for this turn."""
        if self._current is None:
            return
        if events.wall is not None:
            wall: Dict[str, Any] = {"result": events.wall.result}
            if events.wall.item_uses_left is not None:
                wall["item_uses_left"] = events.wall.item_uses_left
            self._current["wall"] = wall
        if events.contact is not None:
            contact: Dict[str, Any] = {"type": events.contact.kind, "id": events.contact.event_id}
            if events.contact.outcome is not None:
                contact["outcome"] = events.contact.outcome
            if events.contact.respawn_to is not None:
                contact["respawn_to"] = list(events.contact.respawn_to)
            if events.contact.collected is not None:
                contact["collected"] = events.contact.collected
            if events.contact.from_floor is not None:
                contact["from_floor"] = events.contact.from_floor
            if events.contact.to_floor is not None:
                contact["to_floor"] = events.contact.to_floor
            self._current["contact"] = contact
        for expired_event in events.expired:
            expired: Dict[str, Any] = {"type": expired_event.kind}
            if expired_event.event_id is not None:
                expired["id"] = expired_event.event_id
            if expired_event.item is not None:
                expired["item"] = expired_event.item
            if expired_event.reason is not None:
                expired["reason"] = expired_event.reason
            self._current.setdefault("expired", []).append(expired)
        for world_event in events.world:
            world: Dict[str, Any] = {
                "type": "respawn",
                "kind": world_event.kind,
                "id": world_event.event_id,
                "at": list(world_event.at),
            }
            if world_event.floor is not None:
                world["floor"] = world_event.floor
            self._current.setdefault("world", []).append(world)

    def record_contact(self, contact: Dict[str, Any]) -> None:
        if self._current is not None:
            self._current["contact"] = contact

    def add_expired(self, expired: Dict[str, Any]) -> None:
        if self._current is not None:
            self._current.setdefault("expired", []).append(expired)

    def add_world_event(self, event: Dict[str, Any]) -> None:
        if self._current is not None:
            self._current.setdefault("world", []).append(event)

    def commit_turn(self) -> None:
        if self._current is None:
            return
        turn = self._current
        turn.setdefault("wall", None)
        turn.setdefault("contact", None)
        turn.setdefault("expired", [])
        turn.setdefault("world", [])
        self.turns.append(turn)
        self._current = None

    def record_quit(self) -> None:
        self._turn_no += 1
        self.turns.append({"turn": self._turn_no, "input": "Q"})

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "arlq_version": __version__,
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "params": self.params,
            "turns": self.turns,
            "final": {"outcome": self.outcome or "unfinished", "turns": self._turn_no},
        }

    def write(self, path: Path) -> None:
        data = self.to_dict()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def default_replay_output_path(path: Path) -> Path:
    """The default --trace-replay-output path: `path` with '.replay' inserted
    before its extension (e.g. "foo.json" -> "foo.replay.json")."""
    return path.with_name(f"{path.stem}.replay{path.suffix}")


def load_trace(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported trace schema_version {data.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION})"
        )
    if "params" not in data or "turns" not in data:
        raise ValueError("trace file is missing required 'params' or 'turns' fields")
    return data


class ReplayUI:
    """A UI stand-in that feeds recorded inputs to run_game()/game_engine.run_game()
    in place of a human player, in place of any UI object.

    Draws are forwarded to `draw_ui` when given (--trace-replay-watch);
    otherwise drawing is a no-op, for a fast headless replay. `select_stage()`
    returns `stage` directly rather than replaying the selection screen's key
    presses: both frontends' selection screens support direct numeric-key
    selection, so this is behaviorally equivalent and avoids depending on
    frontend-specific key codes here.
    """

    def __init__(
        self,
        turns: List[Dict[str, Any]],
        stage: int,
        draw_ui: Optional[Any] = None,
        draw_interval: float = 0.0,
    ) -> None:
        self._inputs: Deque[str] = deque(turn["input"] for turn in turns)
        self._stage = stage
        self._draw_ui = draw_ui
        self._draw_interval = draw_interval
        self.map_mode = False
        self.ran_dry = False

    def draw_stage(self, **kwargs: Any) -> None:
        if self._draw_ui is not None:
            self._draw_ui.draw_stage(**kwargs)
            if self._draw_interval > 0:
                time.sleep(self._draw_interval)

    def select_stage(self, stage_numbers: Tuple[int, ...] = d.PUBLIC_STAGE_NUMBERS) -> int:
        return self._stage

    def input_direction(self) -> Optional[Tuple[int, int]]:
        if not self._inputs:
            self.ran_dry = True
            return None
        key = self._inputs.popleft()
        if key == "Q":
            return None
        return KEY_TO_DIR[key]

    def input_alphabet(self) -> Optional[str]:
        # The game-over screen (map/seed keys) is out of scope for
        # replay: run_game() exits as soon as this returns None.
        return None
