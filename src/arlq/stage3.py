"""Stage 3 rules, kept separate from the compact legacy stage loop."""

from collections import Counter, deque
from copy import deepcopy
from typing import Any, Container, Deque, Dict, List, Optional, Tuple

from . import defs as d
from .arlq import (
    MESSAGE_TICKS,
    create_field,
    find_random_place,
    get_torched,
    reveal_entities_in_fov,
    spawn_at,
    spread_caltrops,
    tick_message,
    unlock_treasure_for_defeat,
)
from .i18n import t as tr
from .trace import DIR_TO_KEY, TraceRecorder
from .utils import rand

FLOORS = 3
LOOP_TURNS = 80
STAGE3_C = d.STAGE3_C_FLAG
STAGE3_I = d.STAGE3_I_FLAG
STAGE3_K = d.STAGE3_K_FLAG
STAGE3_H = d.STAGE3_H_FLAG
STAGE3_W = d.STAGE3_W_FLAG
STAGE3_J = d.STAGE3_J_FLAG

ELF_REPEAT_MESSAGES = {
    "K": "-- The Collector Elf (K) looks satisfied.",
    "H": "-- Keep the talisman close to your skin.",
}

# Each entry is [(tribe_char, population, empowered), ...] for one floor.
ROSTER: List[List[Tuple[str, int, int]]] = [
    [("a", 20, 1), ("A", 2, 1), ("b", 6, 1), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("I", 1, 1), ("J", 1, 1), ("n", 1, 1), ("o", 1, 1), ("p", 1, 1)],
    [("a", 20, 1), ("A", 2, 1), ("b", 3, 1), ("b", 3, 2), ("c", 1, 1), ("c", 1, 2), ("C", 1, 1), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("K", 1, 1), ("n", 1, 1), ("o", 1, 1), ("p", 1, 1)],
    [("A", 2, 1), ("b", 3, 1), ("b", 3, 2), ("d", 3, 1), ("d", 3, 2), ("l", 1, 1), ("w", 1, 1), ("W", 1, 1), ("H", 1, 1), ("n", 1, 1), ("o", 1, 1), ("p", 1, 1)],
]

# Distinct, non-elf monster tribes across all floors, strongest first: feeds
# the right-edge strength column (see d.build_strength_column), which shows
# the whole stage's roster regardless of which floor the player is on.
_ROSTER_CHARS = dict.fromkeys(char for floor in ROSTER for char, _, _ in floor)
ROSTER_TRIBES: List[d.MonsterTribe] = sorted(
    (
        d.CHAR_TO_MONSTER_TRIBE[c]
        for c in _ROSTER_CHARS
        if c in d.CHAR_TO_MONSTER_TRIBE and not d.CHAR_TO_MONSTER_TRIBE[c].is_elf
    ),
    key=lambda t: t.level,
    reverse=True,
)

# A per-floor game state. Keeping this as a plain dict (rather than a new
# class) matches how legacy stages pass field/entities/torched around.
Floor = Dict[str, Any]

# History entries snapshot everything the Loop Companion can rewind.
HistoryEntry = Tuple[List[Floor], d.Player, int, d.Point, "Counter[Tuple[int, str]]"]


class _StepDone(Exception):
    """Internal signal: skip the rest of `_step` and return `result` now."""

    def __init__(self, result: Optional[Tuple[int, str]]) -> None:
        self.result = result


def _place_barrier(field: List[List[str]], center: d.Point) -> None:
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not (dx or dy):
                continue
            x, y = center[0] + dx, center[1] + dy
            if not (0 <= y < len(field) and 0 <= x < len(field[0])):
                continue
            # Never punch through the sealed Isolated Elf room's
            # perimeter when another Stage 3 feature is nearby.
            if field[y][x] == " ":
                field[y][x] = d.CHAR_BARRIER


def _inside_island(point: Optional[d.Point], island_tile: Optional[d.Point]) -> bool:
    if point is None or island_tile is None:
        return False
    left = island_tile[0] * (d.TILE_WIDTH + 1)
    top = island_tile[1] * (d.TILE_HEIGHT + 1)
    return left < point[0] < left + d.TILE_WIDTH + 1 and top < point[1] < top + d.TILE_HEIGHT + 1


def _spawn(
    entities: List[d.Entity],
    field: List[List[str]],
    ch: str,
    avoid: Container[d.Point] = (),
    island_tile: Optional[d.Point] = None,
    floor_index: Optional[int] = None,
    empowered: int = 1,
) -> d.Point:
    while True:
        x, y = find_random_place(entities, field, distance=2)
        if (x, y) not in avoid and not _inside_island((x, y), island_tile):
            break
    spawn_at(entities, x, y, d.CHAR_TO_TRIBE[ch], empowered=empowered, origin_floor=floor_index)
    return x, y


def _find_escape_place(current: Floor) -> d.Point:
    """A random open cell for the player to be sent to, never inside a
    sealed island (e.g. the Isolated Elf's room)."""
    island_tile = current.get("island")
    while True:
        x, y = find_random_place(current["entities"], current["field"], distance=2)
        if not _inside_island((x, y), island_tile):
            return x, y


def _main_connected(field: List[List[str]], start: d.Point, island_tile: Optional[d.Point]) -> bool:
    reached = {start}
    pending: Deque[d.Point] = deque([start])
    while pending:
        x, y = pending.popleft()
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            nx, ny = x + dx, y + dy
            point = (nx, ny)
            if (
                0 <= ny < len(field)
                and 0 <= nx < len(field[0])
                and field[ny][nx] in (" ", "^", "v", d.CHAR_BARRIER)
                and point not in reached
            ):
                reached.add(point)
                pending.append(point)
    return all(
        field[y][x] not in (" ", "^", "v", d.CHAR_BARRIER)
        or _inside_island((x, y), island_tile)
        or (x, y) in reached
        for y in range(len(field))
        for x in range(len(field[0]))
    )


def _build_floor(
    index: int,
    special_floors: Dict[str, int],
    elf_floors: Dict[str, int],
    entry_point: Optional[d.Point] = None,
) -> Floor:
    island_tile = None
    if index == elf_floors["I"]:
        while island_tile is None or _inside_island(entry_point, island_tile):
            island_tile = (rand.randrange(d.TILE_NUM_X), rand.randrange(d.TILE_NUM_Y))
    for _ in range(1000):
        field, up, down = create_field(d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH, d.WALL_CHAR, island_tile)
        if entry_point is not None:
            entry_x, entry_y = entry_point
            if not (0 <= entry_y < len(field) and 0 <= entry_x < len(field[0])):
                continue
            if _inside_island(entry_point, island_tile):
                continue
            generated_up = up
            if not _main_connected(field, generated_up, island_tile):
                continue
            # Preserve the exit coordinates from the previous floor. If the
            # corresponding cell is a wall on this floor, carve a short
            # connection to the generated main corridor.
            x, y = entry_point
            target_x, target_y = generated_up
            while x != target_x:
                field[y][x] = " "
                x += 1 if target_x > x else -1
            while y != target_y:
                field[y][x] = " "
                y += 1 if target_y > y else -1
            field[y][x] = " "
            up = entry_point
        if _main_connected(field, up, island_tile):
            break
    else:
        raise RuntimeError("could not generate a connected Stage 3 floor")

    if index < FLOORS - 1:
        field[down[1]][down[0]] = "v"
    if index:
        field[up[1]][up[0]] = "^"

    entities: List[d.Entity] = []
    reserved = {up, down}
    for ch, count, empowered in ROSTER[index]:
        if ch in {"W", "w", "I", "J", "K", "H"}:
            continue
        for _ in range(count):
            _spawn(entities, field, ch, reserved, island_tile, index, empowered)

    if island_tile is not None:
        left = island_tile[0] * (d.TILE_WIDTH + 1) + 1
        top = island_tile[1] * (d.TILE_HEIGHT + 1) + 1
        spots = [
            (x, y)
            for y in range(top, top + d.TILE_HEIGHT)
            for x in range(left, left + d.TILE_WIDTH)
            if field[y][x] == " "
        ]
        x, y = rand.choice(spots)
        entities.append(d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE["I"]))

    for ch in ("J", "K", "H"):
        if index == elf_floors[ch]:
            _spawn(entities, field, ch, reserved, island_tile, index)

    if index == 2:
        _spawn(entities, field, "w", reserved, floor_index=index)
        weak = next(e for e in entities if isinstance(e, d.Monster) and e.tribe.char == "w")
        _place_barrier(field, (weak.x, weak.y))
        entities.append(d.Monster(down[0], down[1], d.CHAR_TO_MONSTER_TRIBE["W"]))
        _place_barrier(field, down)
        entities.append(d.Treasure(*_treasure_spot(entities, field, reserved), d.CHAR_TREASURE + "W"))

    for ch, assigned_floor in special_floors.items():
        if index == assigned_floor:
            for _ in range(2 if ch == "m" else 1):
                _spawn(entities, field, ch, reserved, island_tile, index)

    return {
        "field": field,
        "entities": entities,
        "seen": [[0] * len(field[0]) for _ in field],
        "known_companions": set(),
        "up": up,
        "down": down,
        "island": island_tile,
    }


def _treasure_spot(entities: List[d.Entity], field: List[List[str]], reserved: Container[d.Point]) -> d.Point:
    while True:
        p = find_random_place(entities, field, distance=2)
        if p not in reserved:
            return p


def build() -> Tuple[List[Floor], d.Player]:
    elf_floors = {
        "I": rand.randrange(FLOORS),
        "J": rand.randrange(FLOORS),
        "K": rand.randrange(FLOORS - 1),
        "H": rand.randrange(FLOORS),
    }
    special_floors = {ch: rand.randrange(FLOORS) for ch in ("m", "X", "e", "g")}
    floors: List[Floor] = []
    entry_point = None
    for index in range(FLOORS):
        floor = _build_floor(index, special_floors, elf_floors, entry_point)
        floors.append(floor)
        entry_point = floor["down"]
    player = d.Player(floors[0]["up"][0], floors[0]["up"][1], 1, d.LP_INIT)
    player.stage3_elf_floors = {char: floor + 1 for char, floor in elf_floors.items()}
    return floors, player


def _move_player(
    direction: d.Point, current: Floor, player: d.Player, trace: Optional[TraceRecorder] = None
) -> None:
    """Apply one step of player movement, including sword-breaking and Pegasus jumps."""
    dx, dy = direction
    nx, ny = player.x + dx, player.y + dy
    field = current["field"]
    if not (0 <= ny < len(field) and 0 <= nx < len(field[0])):
        if trace is not None:
            trace.record_wall({"result": "blocked"})
        return

    cell = field[ny][nx]
    if cell in (" ", d.CHAR_CALTROP, "^", "v", d.CHAR_BARRIER):
        player.x, player.y = nx, ny
        return

    if player.companion and player.companion.tribe.char == "p":
        jx, jy = player.x + dx * d.PEGASUS_STEP_X, player.y + dy * d.PEGASUS_STEP_Y
        if 0 <= jy < len(field) and 0 <= jx < len(field[0]) and field[jy][jx] in (" ", d.CHAR_CALTROP):
            player.x, player.y = jx, jy
            player.karma += 1
            if trace is not None:
                trace.record_wall({"result": "pegasus_phase"})
        elif trace is not None:
            trace.record_wall({"result": "blocked"})
        return

    if player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) and player.item_uses:
        player.x, player.y = nx, ny
        field[ny][nx] = " "
        player.item_uses -= 1
        if not player.item_uses:
            player.item = None
        if trace is not None:
            trace.record_wall({"result": "sword_break", "item_uses_left": player.item_uses})
        return

    if trace is not None:
        trace.record_wall({"result": "blocked"})


def _apply_terrain_hazards(current: Floor, player: d.Player, previous: d.Point) -> Optional[str]:
    """Apply barrier/caltrop damage for the player's current cell.

    Returns an event message for the barrier case, or None otherwise (caltrop
    damage never produces a message, matching the legacy stages).
    """
    field = current["field"]
    event_message = None
    if field[player.y][player.x] == d.CHAR_BARRIER and not (player.stage3_flags & STAGE3_H) and (player.x, player.y) != previous:
        player.lp -= d.BARRIER_LP_DAMAGE
        event_message = tr("-- The barrier burns you.")
    if field[player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= d.CALTROP_LP_DAMAGE
        field[player.y][player.x] = " "
    return event_message


def _rewind_to_history(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: "Counter[Tuple[int, str]]",
    history: Deque[HistoryEntry],
) -> Tuple[int, str]:
    """Handle contact with the Loop Companion ('l'): rewind to the oldest recorded state."""
    known = player.known_monsters
    unlocked = player.unlocked_treasures
    elf_floors = player.stage3_elf_floors
    seen = [floor_data["seen"] for floor_data in floors]
    known_companions = [floor_data["known_companions"] for floor_data in floors]

    old_floors, old_player, old_floor, old_checkpoint, old_queue = history[0]
    floors[:] = old_floors
    queue.clear()
    queue.update(old_queue)
    for floor_data, preserved_seen in zip(floors, seen, strict=True):
        floor_data["seen"] = preserved_seen
    for floor_data, preserved_known in zip(floors, known_companions, strict=True):
        floor_data["known_companions"] = preserved_known

    player.__dict__.update(old_player.__dict__)
    # Monster/treasure knowledge and elf floor locations survive the rewind;
    # everything else (position, level, LP, floor, stage3_flags, ...)
    # reverts to the recorded past. stage3_met_elves must revert together
    # with stage3_flags: it gates re-processing of an elf encounter
    # (_resolve_monster_contact), so keeping it "met" while stage3_flags
    # reverts to not-yet-met would permanently block earning that elf's
    # flag again, and would render it on the field as already resolved
    # while the status bar (driven by stage3_flags) still shows it unmet.
    player.known_monsters = known
    player.unlocked_treasures = unlocked
    player.stage3_elf_floors = elf_floors

    floor[0], checkpoint[0] = old_floor, old_checkpoint
    history.clear()

    restored_entities = floors[floor[0]]["entities"]
    for index, restored in enumerate(restored_entities):
        if isinstance(restored, d.Companion) and restored.tribe.char == "l":
            del restored_entities[index]
            break
    _spawn(restored_entities, floors[floor[0]]["field"], "l", {(player.x, player.y)}, floors[floor[0]]["island"], floor[0])

    return (5, tr("-- Time folds back to the beginning of the recorded past."))


def _defeat_monster(
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: "Counter[Tuple[int, str]]",
    trace: Optional[TraceRecorder] = None,
) -> None:
    """Apply the effects of successfully defeating `entity` in combat."""
    ch = entity.tribe.char

    # A successful monster defeat establishes the next respawn point,
    # matching the legacy stages and the Rust port.
    if not entity.tribe.is_elf:
        checkpoint[0] = (player.x, player.y)

    # Every ordinary monster replaces the current item. This is important
    # for d (Poisoned): defeating another monster with no item must clear
    # the poison and identify the new source.
    if ch != "H":
        old_item, old_source = player.item, player.item_taken_from
        d.take_monster_item(player, entity.tribe.item, ch)
        if trace is not None and old_item:
            trace.add_expired({"type": "item_expired", "item": old_source, "reason": "overwritten"})

    if ch == "W":
        player.stage3_flags |= STAGE3_W
        unlock_treasure_for_defeat(entity, player.unlocked_treasures)
        player.known_monsters.add(d.monster_type_key(entity))
        if player.stage3_treasure_collected:
            player.stage3_won = True
    if ch == "K":
        player.stage3_flags |= STAGE3_K
        player.item = None
    if ch == "H":
        player.stage3_flags |= STAGE3_H
    if ch == "m":
        player.stage3_spores = True
    if ch == "C":
        player.stage3_flags |= STAGE3_C

    d.grant_defeat_level(player, entity.tribe.effect)
    d.apply_feed(player, entity.tribe.feed)
    player.karma += 1

    if entity.tribe.effect == d.EFFECT_CALTROP_SPREAD:
        spread_caltrops(current["field"], (player.x, player.y), current["entities"])

    if d.monster_level(entity) > 0 and ch not in d.STAGE3_NO_RESPAWN_MONSTERS:
        spawn_key = (floor[0], d.monster_type_key(entity))
        queue[spawn_key] = queue.get(spawn_key, 0) + 1


def _resolve_monster_contact(
    hit: int,
    entity: d.Monster,
    current: Floor,
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: "Counter[Tuple[int, str]]",
    event_message: Optional[str],
    trace: Optional[TraceRecorder] = None,
) -> Optional[str]:
    """Resolve contact with a monster (including elves). May raise `_StepDone`
    for a repeated encounter with an already-met elf, which ends the turn
    immediately without the usual end-of-turn processing."""
    ch = entity.tribe.char
    contact_key = (floor[0], entity.x, entity.y)

    if entity.tribe.is_elf:
        player.stage3_elf_floors.setdefault(ch, floor[0] + 1)

    if ch in player.stage3_met_elves:
        current["entities"].pop(hit)
        if trace is not None:
            trace.record_contact({"type": "monster", "id": ch, "outcome": "refused"})
        if ch == "I":
            # The sealed Isolated Elf island has no other way out (see
            # _inside_island): once the player has met "I", every further
            # visit sends them back out instead of trapping them inside.
            current["entities"].append(entity)
            player.x, player.y = _find_escape_place(current)
            raise _StepDone(
                (MESSAGE_TICKS, tr("-- The Isolated Elf wants to be left alone, and sends you elsewhere."))
            )
        if ch in ELF_REPEAT_MESSAGES:
            current["entities"].append(entity)
            raise _StepDone((MESSAGE_TICKS, tr(ELF_REPEAT_MESSAGES[ch])))
        raise _StepDone(None)

    # The W treasure must remain hidden until W is actually defeated. Other
    # monsters are revealed on contact, but revealing W here would also make
    # the renderer show its locked treasure.
    if ch != "W":
        player.known_monsters.add(d.monster_type_key(entity))
    current["entities"].pop(hit)

    # Contact with any monster clears the spores. The Rust version resets
    # this before resolving the encounter, so defeating a different monster
    # restores the normal FOV immediately.
    player.stage3_spores = False

    if ch == "I":
        player.stage3_flags |= STAGE3_I
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "I", "outcome": "granted"})
    elif ch == "J":
        player.stage3_flags |= STAGE3_J
        player.persistent_followers.append((player.x, player.y, floor[0], "J"))
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "J", "outcome": "granted"})
    elif ch == "K" and not (player.stage3_flags & STAGE3_C):
        current["entities"].append(entity)
        # The first refusal only shows a message; any later refusal sends the
        # player elsewhere, like repeat contact with the Isolated Elf.
        if player.k_elf_refused:
            player.x, player.y = _find_escape_place(current)
            event_message = tr("-- Respawned to a random location.")
        else:
            event_message = tr("-- Please bring the cursed sword (C).")
            player.k_elf_refused = True
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "K", "outcome": "refused"})
    elif ch == "H" and (player.stage3_flags & (STAGE3_I | STAGE3_J | STAGE3_K)).bit_count() < 2:
        current["entities"].append(entity)
        # The first refusal only shows a message; any later refusal sends the
        # player elsewhere, like repeat contact with the Isolated Elf.
        if player.high_elf_refused:
            player.x, player.y = _find_escape_place(current)
            event_message = tr("-- Respawned to a random location.")
        else:
            event_message = tr("-- The High Elf does not recognize you yet.")
            player.high_elf_refused = True
        if trace is not None:
            trace.record_contact({"type": "monster", "id": "H", "outcome": "refused"})
    elif d.current_player_attack(player, 3) < d.monster_level(entity):
        # The encounter remains on the map when the player loses. Rust
        # resolves combat before removing the monster; keeping the entity
        # here prevents a failed attack from deleting it.
        current["entities"].append(entity)
        # Losing twice in a row to the very same monster (no other monster
        # contact in between) means it is blocking the only way through:
        # send the player somewhere random instead of back to the
        # checkpoint, so a too-strong monster on a bridge corridor cannot
        # soft-lock the floor.
        if player.last_contact_monster == contact_key:
            player.x, player.y = _find_escape_place(current)
            event_message = tr("-- Respawned to a random location.")
        else:
            player.x, player.y = checkpoint[0]
            event_message = tr("-- Respawned!")
        if trace is not None:
            trace.record_contact(
                {
                    "type": "monster",
                    "id": d.monster_type_key(entity),
                    "outcome": "lose",
                    "respawn_to": [player.x, player.y],
                }
            )
        d.apply_respawn_penalty(player)
        old_item, old_source = player.item, player.item_taken_from
        player.item = None
        player.item_uses = 0
        player.item_taken_from = None
        if trace is not None and old_item:
            trace.add_expired({"type": "item_expired", "item": old_source, "reason": "lost_on_defeat"})
    else:
        if trace is not None:
            trace.record_contact({"type": "monster", "id": d.monster_type_key(entity), "outcome": "win"})
        _defeat_monster(entity, current, player, floor, checkpoint, queue, trace=trace)

    if entity.tribe.is_elf and ch != "J" and entity not in current["entities"]:
        player.stage3_met_elves.add(ch)
        current["entities"].append(entity)
    elif entity.tribe.is_elf and entity not in current["entities"]:
        player.stage3_met_elves.add(ch)

    player.last_contact_monster = contact_key

    if event_message is None:
        tribe_message = entity.tribe.event_message
        if tribe_message:
            event_message = tr(tribe_message)

    return event_message


def _resolve_contact(
    hit: int,
    current: Floor,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: "Counter[Tuple[int, str]]",
    history: Deque[HistoryEntry],
    event_message: Optional[str],
    trace: Optional[TraceRecorder] = None,
) -> Optional[str]:
    """Resolve contact with the entity at `hit` in current["entities"].

    Returns the event message to report for this turn (which may be
    `event_message` unchanged). May raise `_StepDone` for encounters that end
    the turn immediately, bypassing the usual end-of-turn processing (Loop
    Companion rewind, repeated elf contact).
    """
    entity = current["entities"][hit]

    if isinstance(entity, d.Treasure):
        collected = entity.unlock_key in player.unlocked_treasures
        if trace is not None:
            trace.record_contact({"type": "treasure", "id": entity.unlock_key, "collected": collected})
        if collected:
            current["entities"].pop(hit)
            player.stage3_treasure_collected = True
            if player.stage3_flags & STAGE3_W:
                player.stage3_won = True
            else:
                event_message = tr("-- You took the treasure chest, but the King's request remains.")
        return event_message

    if isinstance(entity, d.Companion):
        ch = entity.tribe.char
        current["known_companions"].add(ch)
        current["entities"].pop(hit)
        if trace is not None:
            trace.record_contact({"type": "companion", "id": ch})
        # l is a companion whose contact rewinds the recorded past.
        if ch == "l" and history:
            raise _StepDone(_rewind_to_history(floors, player, floor, checkpoint, queue, history))
        player.companion = entity
        player.karma = 0
        tribe_message = entity.tribe.event_message
        return tr(tribe_message) if tribe_message else None

    return _resolve_monster_contact(hit, entity, current, player, floor, checkpoint, queue, event_message, trace=trace)


def _advance_persistent_followers(player: d.Player, floor_index: int, moved: bool, previous: d.Point) -> None:
    """The Javelin Elf follows one step behind; keep its recorded position in sync."""
    for i, follower in enumerate(player.persistent_followers):
        if follower[2] == floor_index and moved:
            player.persistent_followers[i] = (previous[0], previous[1], follower[2], follower[3])


def _handle_floor_transition(
    current: Floor,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
) -> Optional[str]:
    if floor[0] < FLOORS - 1 and (player.x, player.y) == current["down"]:
        floor[0] += 1
        player.x, player.y = floors[floor[0]]["up"]
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [(player.x, player.y, floor[0], ch) for _, _, _, ch in player.persistent_followers]
        return tr("-- Descended to floor {n}/3.").format(n=floor[0] + 1)
    if floor[0] > 0 and (player.x, player.y) == current["up"]:
        floor[0] -= 1
        player.x, player.y = floors[floor[0]]["down"]
        checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [(player.x, player.y, floor[0], ch) for _, _, _, ch in player.persistent_followers]
        return tr("-- Ascended to floor {n}/3.").format(n=floor[0] + 1)
    return None


def _process_respawn_queue(
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    queue: "Counter[Tuple[int, str]]",
    hours: int,
    trace: Optional[TraceRecorder] = None,
) -> None:
    if hours % d.MONSTER_RESPAWN_INTERVAL != 0:
        return
    for (spawn_floor, type_key), count in list(queue.items()):
        if not count:
            continue
        avoid = {(player.x, player.y)} if spawn_floor == floor[0] else set()
        if type_key[-1].isdigit():
            ch = type_key[:-1]
            empowered = int(type_key[-1])
        else:
            ch = type_key
            empowered = 1
        args = (floors[spawn_floor]["entities"], floors[spawn_floor]["field"], ch, avoid, floors[spawn_floor]["island"], spawn_floor)
        if empowered == 1:
            x, y = _spawn(*args)
        else:
            x, y = _spawn(*args, empowered)
        queue[(spawn_floor, type_key)] -= 1
        if trace is not None:
            kind = "monster" if isinstance(d.CHAR_TO_TRIBE[ch], d.MonsterTribe) else "companion"
            trace.add_world_event(
                {"type": "respawn", "kind": kind, "id": type_key, "at": [x, y], "floor": spawn_floor}
            )


def _step(
    direction: d.Point,
    floors: List[Floor],
    player: d.Player,
    floor: List[int],
    checkpoint: List[d.Point],
    queue: "Counter[Tuple[int, str]]",
    history: Deque[HistoryEntry],
    hours: int,
    trace: Optional[TraceRecorder] = None,
) -> Optional[Tuple[int, str]]:
    current = floors[floor[0]]
    history.append((deepcopy(floors), deepcopy(player), floor[0], checkpoint[0], deepcopy(queue)))
    if len(history) > LOOP_TURNS:
        history.popleft()

    previous = (player.x, player.y)
    _move_player(direction, current, player, trace=trace)
    event_message = _apply_terrain_hazards(current, player, previous)

    hit = next((i for i, e in enumerate(current["entities"]) if (e.x, e.y) == (player.x, player.y)), None)
    if hit is not None:
        try:
            event_message = _resolve_contact(
                hit, current, floors, player, floor, checkpoint, queue, history, event_message, trace=trace
            )
        except _StepDone as done:
            return done.result

    if player.companion is not None and player.karma >= player.companion.tribe.durability:
        ch = player.companion.tribe.char
        # Respawn on the floor the companion came from, not wherever it was
        # carried to and expired: otherwise a floor that never lost its own
        # copy can end up with two once the queued respawn fires.
        origin_floor = player.companion.origin_floor
        if origin_floor is None:
            origin_floor = floor[0]
        spawn_key = (origin_floor, ch)
        queue[spawn_key] = queue.get(spawn_key, 0) + 1
        player.companion = None
        event_message = tr("-- The companion vanishes.")
        if trace is not None:
            trace.add_expired({"type": "companion_departed", "id": ch})

    reveal_entities_in_fov(player, current["entities"])
    _advance_persistent_followers(player, floor[0], (player.x, player.y) != previous, previous)

    floor_before = floor[0]
    transition_message = _handle_floor_transition(current, floors, player, floor, checkpoint)
    if transition_message is not None:
        event_message = transition_message
        if trace is not None:
            trace.record_contact({"type": "stairs", "from_floor": floor_before, "to_floor": floor[0]})

    _process_respawn_queue(floors, player, floor, queue, hours, trace=trace)

    return (MESSAGE_TICKS, event_message) if event_message else None


def run_game(ui: Any, seed_str: str, debug: bool = False, trace: Optional[TraceRecorder] = None) -> None:
    floors, player = build()
    player.known_monsters = set()
    player.unlocked_treasures = set()
    player.stage3_won = False
    player.stage3_treasure_collected = False
    player.stage3_met_elves = set()
    floor = [0]
    checkpoint = [floors[0]["up"]]
    player.stage3_floor = 0
    queue: "Counter[Tuple[int, str]]" = Counter()
    history: Deque[HistoryEntry] = deque()
    hours = 0
    message: Tuple[int, str] = (5, tr("-- The King has ordered the Dread Wyrm (W) slain."))

    while player.lp > 0 and not player.stage3_won:
        current = floors[floor[0]]
        cur = get_torched(player, d.TORCH_RADIUS)
        for y in range(len(cur)):
            for x in range(len(cur[0])):
                current["seen"][y][x] |= cur[y][x]

        message = tick_message(message)

        show_entities = debug or getattr(ui, "map_mode", False)
        # The terminal renderer discovers the player from the entity list, while
        # the pygame renderer receives it separately. Keep the Stage 3 state
        # model separate and provide a render-only combined list.
        render_entities = [player, *current["entities"]]
        known_types = player.known_monsters | current["known_companions"]
        ui.draw_stage(
            hours,
            player,
            render_entities,
            current["field"],
            cur,
            current["seen"],
            known_types,
            show_entities,
            3,
            message[1],
            checkpoint=checkpoint[0],
            unlocked_treasures=player.unlocked_treasures,
            dim_types=player.stage3_met_elves,
            stage_roster=ROSTER_TRIBES,
        )

        move = ui.input_direction()
        if move is None:
            if trace is not None:
                trace.record_quit()
                trace.set_outcome("unfinished" if getattr(ui, "ran_dry", False) else "quit")
            return
        if move == (0, 0):
            continue

        if trace is not None:
            key = DIR_TO_KEY.get(move)
            if key is None:
                raise RuntimeError("--trace-record does not support non-cardinal (e.g. diagonal joystick) movement")
            trace.begin_turn(key)

        event_message = _step(move, floors, player, floor, checkpoint, queue, history, hours, trace=trace)
        player.stage3_floor = floor[0]
        if event_message is not None:
            message = event_message

        if trace is not None:
            trace.set_player(player, 3)
            trace.commit_turn()

        hours += 1
        player.lp -= 1

    if trace is not None:
        trace.set_outcome("win" if player.stage3_won else "lose")

    message = (-1, tr(">> Treasure chest obtained! <<") if player.stage3_won else tr(">> Collapsed from hunger! <<"))
    while True:
        current = floors[floor[0]]
        cur = get_torched(player, d.TORCH_RADIUS)
        render_entities = [player, *current["entities"]]
        known_types = player.known_monsters | current["known_companions"]
        ui.draw_stage(
            hours,
            player,
            render_entities,
            current["field"],
            cur,
            current["seen"],
            known_types,
            debug,
            3,
            message[1],
            True,
            checkpoint[0],
            player.unlocked_treasures,
            player.stage3_met_elves,
            stage_roster=ROSTER_TRIBES,
        )
        key = ui.input_alphabet()
        if key is None:
            return
        if key == "m":
            debug = not debug
        elif key == "s":
            message = (-1, tr("SEED: {seed_str}").format(seed_str=seed_str))
