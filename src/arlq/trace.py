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
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from . import defs as d
from .__about__ import __version__
from .game_events import TurnEvents, WallEvent

SCHEMA_VERSION = 3

DIR_TO_KEY: Dict[Tuple[int, int], str] = {
    (0, -1): "U",
    (0, 1): "D",
    (-1, 0): "L",
    (1, 0): "R",
}
KEY_TO_DIR: Dict[str, Tuple[int, int]] = {key: direction for direction, key in DIR_TO_KEY.items()}


class TraceRecorder:
    """Accumulates one play session's turns for --trace/--output
    output. ``game_engine.run_game()`` calls ``begin_turn()`` /
    ``set_player()`` / ``commit_turn()`` / ``record_quit()`` /
    ``set_outcome()`` directly, while the current turn handler records events
    as they happen. ``record_events()`` remains available for callers of the
    legacy ``arlq.arlq.update_entities()`` helper.
    """

    def __init__(self, params: Dict[str, Any]) -> None:
        self.params = params
        self.turns: List[Dict[str, Any]] = []
        self.start: Optional[Dict[str, Any]] = None
        self.outcome: Optional[str] = None
        self._current: Optional[Dict[str, Any]] = None
        self._turn_no = 0

    def begin_turn(self, input_key: str) -> None:
        self._turn_no += 1
        self._current = {"turn": self._turn_no, "input": input_key}

    def set_start_state(self, player: d.Player, floor_index: int) -> None:
        self.start = {
            "floor": floor_index,
            "position": [player.x, player.y],
            "lp": player.lp,
        }

    def set_player(
        self, player: d.Player, stage_num: int, floor_index: int = 0
    ) -> None:
        if self._current is None:
            return
        self._current["player"] = {
            "lp": player.lp,
            "level": player.level,
            "attack": d.current_player_attack(player, stage_num),
            "floor": floor_index,
            "position": [player.x, player.y],
        }

    def set_turn_end_lp(self, lp: int) -> None:
        if self._current is not None and "player" in self._current:
            self._current["player"]["lp_after_turn"] = lp

    def record_damage(self, source: str) -> None:
        if self._current is not None:
            self._current.setdefault("damage", []).append({"source": source})

    def record_state_changes(
        self,
        seen_added_count: int,
        known_monsters_added: List[str],
    ) -> None:
        if self._current is None:
            return
        self._current["seen_added_count"] = seen_added_count
        self._current["known_monsters_added"] = sorted(known_monsters_added)

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

    def record_checkpoint(
        self,
        reason: str,
        at: Tuple[int, int],
        floor: int,
        entities: Optional[List[str]] = None,
    ) -> None:
        if self._current is not None:
            event: Dict[str, Any] = {
                "reason": reason,
                "at": list(at),
                "floor": floor,
            }
            if entities:
                event["entities"] = list(entities)
            self._current.setdefault("checkpoint", []).append(event)

    def commit_turn(self) -> None:
        if self._current is None:
            return
        turn = self._current
        turn.setdefault("wall", None)
        turn.setdefault("contact", None)
        turn.setdefault("expired", [])
        turn.setdefault("world", [])
        turn.setdefault("damage", [])
        turn.setdefault("seen_added_count", 0)
        turn.setdefault("known_monsters_added", [])
        self.turns.append(turn)
        self._current = None

    def truncate_after_turn(self, retained_turns: int) -> None:
        """Drop turns after a rewind target and reset the turn counter."""
        if self._current is not None:
            raise RuntimeError("cannot truncate while a turn is in progress")
        if not 0 <= retained_turns <= len(self.turns):
            raise ValueError("retained_turns is outside the recorded trace")
        del self.turns[retained_turns:]
        self._turn_no = retained_turns

    def find_overshoot_rewind_target(
        self, max_turns: int = d.OVERSHOOT_REWIND_TURNS
    ) -> Optional[Tuple[int, int, d.Point, int]]:
        """Return a safe prior state if the player left and returned to it.

        The tuple contains retained trace turns, floor index, position, and LP
        after the target turn. Locked treasure contacts are harmless and are
        the only contact events allowed in the candidate window.
        """
        if self._current is not None or self.start is None or not self.turns:
            return None

        current_player = self.turns[-1].get("player")
        if not current_player:
            return None
        current_floor = current_player.get("floor")
        current_position = current_player.get("position")
        if current_floor is None or current_position is None:
            return None

        turn_count = len(self.turns)
        first_target = max(0, turn_count - max_turns)
        for retained_turns in range(turn_count - 1, first_target - 1, -1):
            if retained_turns == 0:
                target_floor = self.start.get("floor")
                target_position = self.start.get("position")
                target_lp = self.start.get("lp")
            else:
                target_player = self.turns[retained_turns - 1].get("player") or {}
                target_floor = target_player.get("floor")
                target_position = target_player.get("position")
                target_lp = target_player.get("lp_after_turn")

            if (
                target_floor != current_floor
                or target_position != current_position
                or target_lp is None
            ):
                continue

            # Require a genuine departure between the target and the return;
            # repeated blocked inputs at one location do not count.
            left_target = any(
                (row.get("player") or {}).get("floor") != target_floor
                or (row.get("player") or {}).get("position") != target_position
                for row in self.turns[retained_turns:-1]
            )
            if not left_target:
                continue

            if any(
                not self._turn_allows_overshoot_rewind(row, target_floor)
                for row in self.turns[retained_turns:]
            ):
                continue

            x, y = target_position
            return retained_turns, target_floor, (x, y), target_lp
        return None

    def overshoot_rewind_markers(
        self, floor: int, max_turns: int = d.OVERSHOOT_REWIND_TURNS
    ) -> Set[d.Point]:
        """Return recent cells that could currently serve as rewind targets.

        A marker is shown only when returning on the next turn would still be
        within the turn limit and the trace since leaving that cell is safe.
        """
        if self._current is not None or self.start is None or not self.turns:
            return set()

        current_player = self.turns[-1].get("player") or {}
        current_position = current_player.get("position")
        if current_player.get("floor") != floor or current_position is None:
            return set()

        turn_count = len(self.turns)
        first_target = max(0, turn_count + 1 - max_turns)
        markers: Set[d.Point] = set()
        for retained_turns in range(turn_count - 1, first_target - 1, -1):
            if retained_turns == 0:
                target_floor = self.start.get("floor")
                target_position = self.start.get("position")
            else:
                target_player = self.turns[retained_turns - 1].get("player") or {}
                target_floor = target_player.get("floor")
                target_position = target_player.get("position")

            if target_floor != floor or target_position == current_position:
                continue
            if not any(
                (row.get("player") or {}).get("position") != target_position
                for row in self.turns[retained_turns:]
            ):
                continue
            if any(
                not self._turn_allows_overshoot_rewind(row, floor)
                for row in self.turns[retained_turns:]
            ):
                continue
            x, y = target_position
            markers.add((x, y))
        return markers

    @staticmethod
    def _turn_allows_overshoot_rewind(turn: Dict[str, Any], floor: int) -> bool:
        player = turn.get("player") or {}
        if player.get("floor") != floor:
            return False
        contact = turn.get("contact")
        if contact is not None and not (
            contact.get("type") == "treasure" and contact.get("collected") is False
        ):
            return False
        return not (
            turn.get("damage")
            or turn.get("seen_added_count", 0)
            or turn.get("known_monsters_added")
            or turn.get("expired")
            or turn.get("world")
            or turn.get("checkpoint")
            or (turn.get("wall") or {}).get("result") == "sword_break"
        )

    def record_quit(self) -> None:
        self._turn_no += 1
        self.turns.append({"turn": self._turn_no, "input": "Q"})

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "schema_version": SCHEMA_VERSION,
            "arlq_version": __version__,
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "params": self.params,
        }
        if self.start is not None:
            data["start"] = self.start
        data["turns"] = self.turns
        data["final"] = {
            "outcome": self.outcome or "unfinished",
            "turns": self._turn_no,
        }
        return data

    def write(self, path: Path) -> None:
        data = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def write_outputs(self, paths: List[Path]) -> None:
        """Write identical trace data to each requested destination."""
        contents = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")


def timestamped_trace_path(cache_dir: Path) -> Path:
    """Return a collision-resistant timestamped trace path in the cache."""
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    return cache_dir / f"trace-{stamp}.json"


def load_trace(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") not in (2, SCHEMA_VERSION):
        raise ValueError(
            f"unsupported trace schema_version {data.get('schema_version')!r} "
            f"(expected 2 or {SCHEMA_VERSION})"
        )
    if "params" not in data or "turns" not in data:
        raise ValueError("trace file is missing required 'params' or 'turns' fields")
    return data


def checkpoint_turn_index(turns: List[Dict[str, Any]], index: int) -> int:
    """Return the input-turn index containing the requested checkpoint event.

    Positive indexes are one-based; negative indexes count from the end.
    """
    if index == 0:
        raise ValueError("--to-checkpoint index cannot be 0")
    event_turns = [
        turn_index
        for turn_index, turn in enumerate(turns)
        for _ in (turn.get("checkpoint") or [])
    ]
    event_index = index - 1 if index > 0 else len(event_turns) + index
    if event_index < 0 or event_index >= len(event_turns):
        raise ValueError(
            f"checkpoint event index {index} is out of range "
            f"(trace contains {len(event_turns)} checkpoint events)"
        )
    return event_turns[event_index]


class ReplayUI:
    """A UI stand-in that feeds recorded inputs to run_game()/game_engine.run_game()
    in place of a human player, in place of any UI object.

    Draws are forwarded to `draw_ui` when provided; otherwise drawing is a
    no-op. `select_stage()`
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
        continue_play: bool = False,
        final_state_only: bool = False,
    ) -> None:
        self._inputs: Deque[str] = deque(turn["input"] for turn in turns)
        self._stage = stage
        self._draw_ui = draw_ui
        self._draw_interval = draw_interval
        self._continue_play = continue_play
        self._final_state_only = final_state_only
        self._last_draw: Optional[Dict[str, Any]] = None
        self._last_state_drawn = False
        self._using_live_input = False
        self.ran_dry = False

    @property
    def input_was_repeat(self) -> bool:
        if not self._using_live_input or self._draw_ui is None:
            return False
        return bool(getattr(self._draw_ui, "input_was_repeat", False))

    def stop_movement_repeat(self) -> None:
        if not self._using_live_input or self._draw_ui is None:
            return
        stop_repeat = getattr(self._draw_ui, "stop_movement_repeat", None)
        if stop_repeat is not None:
            stop_repeat()

    def __getattr__(self, name: str) -> Any:
        draw_ui = self.__dict__.get("_draw_ui")
        if draw_ui is not None and hasattr(draw_ui, name):
            return getattr(draw_ui, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name == "ran_dry":
            object.__setattr__(self, name, value)
            return
        draw_ui = self.__dict__.get("_draw_ui")
        if draw_ui is not None and hasattr(draw_ui, name):
            setattr(draw_ui, name, value)
        else:
            object.__setattr__(self, name, value)

    def draw_stage(self, **kwargs: Any) -> None:
        if self._final_state_only:
            self._last_draw = kwargs
            # The loop draws once more after its last recorded move. At that
            # point the input queue is empty and the game state is complete.
            if self._inputs:
                self._last_state_drawn = False
                return
        if self._draw_ui is not None:
            self._draw_ui.draw_stage(**kwargs)
            if self._final_state_only:
                self._last_state_drawn = True
            if self._draw_interval > 0:
                time.sleep(self._draw_interval)

    def _draw_last_state(self) -> None:
        if (
            self._draw_ui is not None
            and self._last_draw is not None
            and not self._last_state_drawn
        ):
            self._draw_ui.draw_stage(**self._last_draw)
            self._last_state_drawn = True

    def select_stage(self, stage_numbers: Tuple[int, ...] = d.PUBLIC_STAGE_NUMBERS) -> int:
        return self._stage

    def input_direction(self) -> Optional[Tuple[int, int]]:
        self._using_live_input = False
        # Replays consume recorded input without entering the normal UI input
        # loop, so give event-driven UIs a chance to process window-close
        # events between turns.
        poll_events = (
            None
            if self._final_state_only
            else getattr(self._draw_ui, "poll_events", None)
        )
        if poll_events is not None and poll_events():
            return None
        while self._inputs:
            key = self._inputs.popleft()
            if key == "Q" and self._continue_play:
                continue
            if key == "Q":
                if self._final_state_only:
                    self._draw_last_state()
                return None
            return KEY_TO_DIR[key]
        if self._continue_play and self._draw_ui is not None:
            if self._final_state_only:
                self._draw_last_state()
            self._using_live_input = True
            return self._draw_ui.input_direction()
        self.ran_dry = True
        return None

    def input_alphabet(self) -> Optional[str]:
        # The game-over screen (map/seed keys) is out of scope for
        # replay: run_game() exits as soon as this returns None.
        if self._final_state_only:
            self._draw_last_state()
        return None

    def input_game_over(self) -> Optional[str]:
        # The game-over loop may be reached before all trace inputs are
        # consumed (for example, if a trace contains turns after a win).
        if self._final_state_only:
            self._draw_last_state()
            return None
        input_game_over = getattr(self._draw_ui, "input_game_over", None)
        return input_game_over() if input_game_over is not None else self.input_alphabet()
