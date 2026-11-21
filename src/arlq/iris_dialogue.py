"""Iris's chatter, picked from changes between the start and end of a turn.

The lines are presentation only: they are drawn with Python's own `random`,
never the game's `utils.rand`, so seeds and replays are unaffected (a
rewind may show a different line). Gameplay rules are not changed; the
game state and map are read after each turn instead.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from importlib import resources
from typing import Optional

from . import defs as d
from . import display
from .arlq import get_torched
from .game_events import BarrierHit, Combat, FloorChanged, GameEvent, Rewound
from .i18n import PrioritizedMessage, get_language

LINE_TICKS = 8
# A deferred line is dropped if the message line stays busy this long.
PENDING_TURNS = 4
# Lines at or above this priority are story beats: always spoken (they
# wait while a game message is showing). Lower ones are optional chatter,
# spoken by chance and only after a quiet spell.
MUST_SAY_PRIORITY = 70
CHATTY_GAP = 30
IDLE_SILENCE = 100
IDLE_CHANCE = 0.03
LP_THRESHOLDS = (d.LP_WARNING_THRESHOLD, d.LP_LOW_THRESHOLD)

# category: (priority, cooldown in turns, chance)
CATEGORIES: dict[str, tuple[int, int, float]] = {
    "core_destroyed": (100, 0, 1.0),
    "core_revealed": (95, 0, 1.0),
    "leave": (90, 0, 1.0),
    "join": (85, 0, 1.0),
    "rejoin": (85, 0, 1.0),
    "rejoin_after_emergency_food": (85, 0, 1.0),
    "fell_into_pit": (75, 0, 1.0),
    "ration_refilled": (72, 0, 1.0),
    "turns_below_500": (70, 0, 1.0),
    "boss_spotted": (60, 300, 1.0),
    "low_lp": (55, 80, 0.8),
    "low_lp_after_emergency_food": (55, 80, 0.8),
    "battle_lost": (50, 60, 0.5),
    "member_joined": (45, 60, 0.5),
    "treasure_spotted": (40, 100, 0.5),
    "bridgehead": (35, 150, 0.4),
    "barrier": (35, 100, 0.4),
    "unidentified_monster_spotted": (30, 60, 0.2),
    "battle_won": (25, 60, 0.15),
    "floor_change": (25, 0, 0.3),
    "identified_monster_spotted": (20, 80, 0.08),
    "idle": (10, 0, 1.0),
}
# Spoken through ration_line() when Iris catches the starving player.
RATION_CATEGORY = "emergency_food"

_lines_cache: dict[str, Optional[dict[str, list[str]]]] = {}


def _load_lines(tag: str) -> Optional[dict[str, list[str]]]:
    if tag not in _lines_cache:
        try:
            path = (resources.files(__package__).joinpath("locales")
                    .joinpath("iris-dialogue").joinpath(f"{tag}.json"))
            _lines_cache[tag] = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            _lines_cache[tag] = None
    return _lines_cache[tag]


def lines_for(language: str) -> dict[str, list[str]]:
    for tag in (language, language.split("-")[0], "en"):
        lines = _load_lines(tag)
        if lines is not None:
            return lines
    return {}


def format_line(text: str, language: str) -> str:
    if language.split("-")[0] == "ja":
        return f"I「{text}」"
    return f"I: {text}"


@dataclass
class TurnStart:
    roles: tuple[str, ...]
    joined_before: bool
    lp: float
    boss_defeated: bool
    core_destroyed: bool
    floor: int
    point: d.Point
    # None while Iris is not in the party.
    iris_had_ration: Optional[bool] = None


def _iris(player: d.Player) -> Optional[d.PartyMember]:
    return next((m for m in player.members if m.role == d.MEMBER_IRIS), None)


def _sighting(entity: d.Entity, glyphs: list[display.FieldGlyph]) -> Optional[str]:
    """Classify an entity by how it looks on screen, so lines never reveal
    what the player cannot see (a disguised Mimic is a treasure chest)."""
    own = [g.char for g in glyphs if (g.x, g.y) == (entity.x, entity.y)]
    if not own:
        return None
    char = own[0]
    if char == d.CHAR_TREASURE:
        return "treasure_spotted"
    if not isinstance(entity, d.Monster) or entity.tribe.is_elf or entity.tribe.passive:
        return None
    if char == d.CHAR_DUNGEON_CORE:
        return None
    if char == "?":
        return "unidentified_monster_spotted"
    if (char == d.STAGE6_BOSS_PARTY[0][0] and entity.empowered > 1
            and any(g.char in ("'", '"') for g in glyphs)):
        return "boss_spotted"
    return "identified_monster_spotted"


def visible_sightings(player: d.Player, current, torch_radius: int) -> dict[int, str]:
    """Entity uid -> sighting category for what the torch shows right now."""
    torched = get_torched(player, torch_radius)
    attack = d.current_player_attack(player)
    result: dict[int, str] = {}
    for entity in current.entities:
        x, y = entity.x, entity.y
        if not (0 <= y < len(torched) and 0 <= x < len(torched[y])) or not torched[y][x]:
            continue
        glyphs = display.revealed_entity_glyphs(
            entity, player.known_monsters, False, attack, None,
            party_entities=current.entities,
        )
        category = _sighting(entity, glyphs)
        if category is not None:
            result[entity.uid] = category
    return result


class IrisChatter:
    """Choose when Iris speaks and which line she says."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng if rng is not None else random.Random()
        self.turns_since_line = 0
        self.last_said: dict[str, int] = {}
        self.last_index: dict[str, int] = {}
        self.pending: Optional[tuple[str, int]] = None
        self.visible: Optional[dict[int, str]] = None
        self.game_spoke_turn: Optional[int] = None
        self.last_category: Optional[str] = None

    def start_turn(self, player: d.Player, floor_index: int) -> TurnStart:
        iris = _iris(player)
        return TurnStart(
            roles=tuple(m.role for m in player.members),
            joined_before=d.MEMBER_IRIS in player.joined_members,
            lp=player.lp,
            boss_defeated=bool(player.boss_defeated),
            core_destroyed=bool(player.dungeon_core_destroyed),
            floor=floor_index,
            point=(player.x, player.y),
            iris_had_ration=None if iris is None else iris.has_ration,
        )

    def line(self, category: str, importance: int = 1) -> PrioritizedMessage:
        language = get_language()
        lines = lines_for(language).get(category) or lines_for("en").get(category, [""])
        choices = list(range(len(lines)))
        if len(choices) > 1 and category in self.last_index:
            choices.remove(self.last_index[category])
        index = self.rng.choice(choices)
        self.last_index[category] = index
        self.last_category = category
        self.turns_since_line = 0
        return PrioritizedMessage(format_line(lines[index], language), importance)

    def ration_line(self) -> str:
        """The line shown over the collapsed player when Iris gives her ration."""
        return self.line(RATION_CATEGORY, 9)

    def end_turn(
        self,
        session,
        start: TurnStart,
        events: list[GameEvent],
        *,
        bridgehead_entered: bool,
        game_spoke: bool,
    ) -> Optional[tuple[int, str]]:
        """Return Iris's message for this turn, or None to leave the
        message line alone."""
        turn = session.turn
        player = session.player
        if game_spoke:
            self.game_spoke_turn = turn
        current = session.floors[session.floor[0]]
        if any(isinstance(event, Rewound) for event in events):
            # The world was replaced; compare from the restored state.
            self.pending = None
            self.visible = None
            if _iris(player) is not None:
                self.visible = visible_sightings(
                    player, current, session.config.torch_radius
                )
            return None

        iris = _iris(player)
        was_member = d.MEMBER_IRIS in start.roles
        candidates: list[str] = []
        if iris is not None and not was_member:
            if not start.joined_before:
                candidates.append("join")
            elif iris.has_ration:
                candidates.append("rejoin")
            else:
                candidates.append("rejoin_after_emergency_food")
        elif iris is None and was_member:
            candidates.append("leave")

        lost = any(isinstance(e, Combat) and not e.won for e in events)
        moved_far = (session.floor[0] != start.floor
                     or abs(player.x - start.point[0]) + abs(player.y - start.point[1]) > 1)
        if iris is None:
            # Sightings are only compared while she is along; start afresh
            # when she joins so she does not announce everything in view.
            self.visible = None
            sightings = []
        else:
            sightings = self._update_sightings(session, current, quiet=moved_far or lost)

        if iris is not None and was_member:
            self.turns_since_line += 1
            if set(m.role for m in player.members) - set(start.roles):
                candidates.append("member_joined")
            for threshold in LP_THRESHOLDS:
                if start.lp > threshold >= player.lp:
                    candidates.append(
                        "low_lp" if iris.has_ration else "low_lp_after_emergency_food"
                    )
            for event in events:
                if isinstance(event, Combat):
                    candidates.append("battle_won" if event.won else "battle_lost")
                elif isinstance(event, FloorChanged):
                    candidates.append(
                        "fell_into_pit" if event.kind == "fall" else "floor_change"
                    )
                elif isinstance(event, BarrierHit):
                    candidates.append("barrier")
            if bridgehead_entered:
                # Tell the player her used ration was restocked; otherwise
                # it is just a homecoming.
                candidates.append(
                    "ration_refilled"
                    if start.iris_had_ration is False and iris.has_ration
                    else "bridgehead"
                )
            if player.boss_defeated and not start.boss_defeated:
                candidates.append("core_revealed")
            if player.dungeon_core_destroyed and not start.core_destroyed:
                candidates.append("core_destroyed")
            if (session.stage_num == 6 and not player.dungeon_core_destroyed
                    and d.STAGE6_TURN_LIMIT - turn == 500):
                candidates.append("turns_below_500")
            candidates.extend(sightings)
            if self.turns_since_line >= IDLE_SILENCE and self.rng.random() < IDLE_CHANCE:
                candidates.append("idle")

        chosen = self._choose(candidates, turn)
        if self.pending is not None:
            category, expires = self.pending
            if turn > expires or iris is None and category != "leave":
                self.pending = None
            elif chosen is None or CATEGORIES[category][0] >= CATEGORIES[chosen][0]:
                chosen = category
        if chosen is None:
            return None
        if not self._can_speak(session, turn):
            if CATEGORIES[chosen][0] >= MUST_SAY_PRIORITY:
                if self.pending is None or self.pending[0] != chosen:
                    self.pending = (chosen, turn + PENDING_TURNS)
            return None
        self.pending = None
        self.last_said[chosen] = turn
        return (LINE_TICKS, self.line(chosen))

    def _update_sightings(self, session, current, *, quiet: bool) -> list[str]:
        now = visible_sightings(session.player, current, session.config.torch_radius)
        previous, self.visible = self.visible, now
        if previous is None or quiet:
            return []
        new = {now[uid] for uid in now.keys() - previous.keys()}
        return sorted(new, key=lambda c: CATEGORIES[c][0], reverse=True)[:1]

    def _choose(self, candidates: list[str], turn: int) -> Optional[str]:
        best = None
        for category in dict.fromkeys(candidates):
            priority, cooldown, chance = CATEGORIES[category]
            last = self.last_said.get(category)
            if last is not None and turn - last < cooldown:
                continue
            if priority < MUST_SAY_PRIORITY and (
                self.turns_since_line < CHATTY_GAP or self.rng.random() >= chance
            ):
                continue
            if best is None or priority > CATEGORIES[best][0]:
                best = category
        return best

    def _can_speak(self, session, turn: int) -> bool:
        """Leave the message line to the game for the turn it spoke and the
        next, and never cover persistent or dialogue messages."""
        if session.iris_rescue_pending or session.player.lp <= 0:
            return False
        if self.game_spoke_turn is not None and turn - self.game_spoke_turn < 2:
            return False
        ticks, text = session.message
        return not (ticks == -2 or (ticks == -1 and text))
