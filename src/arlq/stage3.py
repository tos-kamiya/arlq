"""Stage 3 rules, kept separate from the compact legacy stage loop."""

from collections import Counter, deque
from copy import deepcopy
from typing import List, Set, Tuple

from . import defs as d
from .arlq import MESSAGE_TICKS, create_field, find_random_place, get_torched, iterate_ellipse_points, iterate_offsets
from .utils import rand

FLOORS = 3
LOOP_TURNS = 80
STAGE3_C, STAGE3_I, STAGE3_K, STAGE3_H, STAGE3_W, STAGE3_J = 1, 2, 4, 8, 16, 64

ROSTER = [
    [("a", 20), ("A", 2), ("b", 12), ("c", 2), ("C", 1), ("d", 3), ("l", 1), ("I", 1), ("J", 1), ("o", 1), ("p", 1)],
    [("a", 20), ("A", 2), ("b", 12), ("c", 2), ("C", 1), ("d", 3), ("l", 1), ("K", 1), ("o", 1), ("p", 1)],
    [("A", 2), ("b", 12), ("d", 3), ("l", 1), ("w", 1), ("W", 1), ("H", 1), ("n", 1), ("o", 1), ("p", 1)],
]


def _place_barrier(field, center):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                x, y = center[0] + dx, center[1] + dy
                if 0 <= y < len(field) and 0 <= x < len(field[0]):
                    # Never punch through the sealed Isolated Elf room's
                    # perimeter when another Stage 3 feature is nearby.
                    if field[y][x] == " ":
                        field[y][x] = d.CHAR_BARRIER


def _inside_island(point, island_tile):
    if island_tile is None:
        return False
    left = island_tile[0] * (d.TILE_WIDTH + 1)
    top = island_tile[1] * (d.TILE_HEIGHT + 1)
    return left < point[0] < left + d.TILE_WIDTH + 1 and top < point[1] < top + d.TILE_HEIGHT + 1


def _spawn(entities, field, ch, avoid=(), island_tile=None):
    while True:
        x, y = find_random_place(entities, field, distance=2)
        if (x, y) not in avoid and not _inside_island((x, y), island_tile):
            break
    tribe = d.CHAR_TO_TRIBE[ch]
    if isinstance(tribe, d.CompanionTribe):
        entities.append(d.Companion(x, y, tribe))
    else:
        entities.append(d.Monster(x, y, tribe))
    return x, y


def _main_connected(field, start, island_tile):
    reached = {start}
    pending = deque([start])
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


def _build_floor(index, special_floors, elf_floors):
    island_tile = (
        (rand.randrange(d.TILE_NUM_X), rand.randrange(d.TILE_NUM_Y))
        if index == elf_floors["I"]
        else None
    )
    for _ in range(1000):
        field, up, down = create_field(d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH, d.WALL_CHAR, island_tile)
        if _main_connected(field, up, island_tile):
            break
    else:
        raise RuntimeError("could not generate a connected Stage 3 floor")
    if index < FLOORS - 1:
        field[down[1]][down[0]] = "v"
    if index:
        field[up[1]][up[0]] = "^"
    entities = []
    reserved = {up, down}
    for ch, count in ROSTER[index]:
        if ch in {"W", "w", "I", "J", "K", "H"}:
            continue
        for _ in range(count):
            _spawn(entities, field, ch, reserved, island_tile)
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
            _spawn(entities, field, ch, reserved, island_tile)
    if index == 2:
        _spawn(entities, field, "w", reserved)
        weak = next(e for e in entities if isinstance(e, d.Monster) and e.tribe.char == "w")
        _place_barrier(field, (weak.x, weak.y))
        entities.append(d.Monster(down[0], down[1], d.CHAR_TO_MONSTER_TRIBE["W"]))
        _place_barrier(field, down)
        entities.append(d.Treasure(*_treasure_spot(entities, field, reserved), "W"))
    for ch, assigned_floor in special_floors.items():
        if index == assigned_floor:
            for _ in range(2 if ch == "m" else 1):
                _spawn(entities, field, ch, reserved, island_tile)
    return {"field": field, "entities": entities, "seen": [[0] * len(field[0]) for _ in field], "up": up, "down": down, "island": island_tile}


def _treasure_spot(entities, field, reserved):
    while True:
        p = find_random_place(entities, field, distance=2)
        if p not in reserved:
            return p


def build():
    elf_floors = {
        "I": rand.randrange(FLOORS),
        "J": rand.randrange(FLOORS),
        "K": rand.randrange(FLOORS - 1),
        "H": rand.randrange(FLOORS),
    }
    special_floors = {ch: rand.randrange(FLOORS) for ch in ("m", "X", "e", "g")}
    floors = [_build_floor(i, special_floors, elf_floors) for i in range(FLOORS)]
    player = d.Player(floors[0]["up"][0], floors[0]["up"][1], 1, d.LP_INIT)
    return floors, player


def _attack(player):
    value = d.player_attack_by_level(player)
    if player.stage3_flags & STAGE3_K:
        value = (value * 6 + 1) // 5
    if any(f[3] == "J" for f in player.persistent_followers):
        value = (value * 5 + 2) // 4
    return value


def _known_monster(player, ch):
    return ch in getattr(player, "stage3_known", set())


def _step(direction, floors, player, floor, checkpoint, queue, history, hours):
    current = floors[floor[0]]
    event_message = None
    history.append((deepcopy(floors), deepcopy(player), floor[0], checkpoint[0]))
    if len(history) > LOOP_TURNS:
        history.popleft()
    previous = (player.x, player.y)
    dx, dy = direction
    nx, ny = player.x + dx, player.y + dy
    if 0 <= ny < len(current["field"]) and 0 <= nx < len(current["field"][0]):
        cell = current["field"][ny][nx]
        if cell in (" ", d.CHAR_CALTROP, "^", "v", d.CHAR_BARRIER):
            player.x, player.y = nx, ny
        elif player.companion and player.companion.tribe.char == "p":
            jx, jy = player.x + dx * d.PEGASUS_STEP_X, player.y + dy * d.PEGASUS_STEP_Y
            if 0 <= jy < len(current["field"]) and 0 <= jx < len(current["field"][0]) and current["field"][jy][jx] in (" ", d.CHAR_CALTROP):
                player.x, player.y = jx, jy; player.karma += 1
        elif player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) and player.item_uses:
            player.x, player.y = nx, ny; current["field"][ny][nx] = " "; player.item_uses -= 1
            if not player.item_uses: player.item = None
    if current["field"][player.y][player.x] == d.CHAR_BARRIER and not (player.stage3_flags & STAGE3_H) and (player.x, player.y) != previous:
        player.lp -= 30
        event_message = "-- The barrier burns you."
    if current["field"][player.y][player.x] == d.CHAR_CALTROP:
        player.lp -= 3; current["field"][player.y][player.x] = " "
    hit = next((i for i, e in enumerate(current["entities"]) if (e.x, e.y) == (player.x, player.y)), None)
    if hit is not None:
        entity = current["entities"][hit]
        if isinstance(entity, d.Treasure):
            if entity.encounter_type in getattr(player, "stage3_unlocked", set()): current["entities"].pop(hit); player.stage3_won = True
        elif isinstance(entity, d.Companion):
            player.companion = entity; player.karma = 0; current["entities"].pop(hit)
            event_message = entity.tribe.event_message
        else:
            ch = entity.tribe.char; player.stage3_known.add(ch); current["entities"].pop(hit)
            # Contact with any monster clears the spores. The Rust version
            # resets this before resolving the encounter, so defeating a
            # different monster restores the normal FOV immediately.
            player.stage3_spores = False
            if ch == "l" and history:
                known = player.stage3_known
                unlocked = player.stage3_unlocked
                seen = [floor_data["seen"] for floor_data in floors]
                old_floors, old_player, old_floor, old_checkpoint = history[0]
                floors[:] = old_floors
                # Mapping is persistent knowledge, not part of the rewindable
                # world state. Restore the rewound fields while retaining the
                # current seen map for every floor.
                for floor_data, preserved_seen in zip(floors, seen):
                    floor_data["seen"] = preserved_seen
                player.__dict__.update(old_player.__dict__)
                player.stage3_known = known
                player.stage3_unlocked = unlocked
                floor[0], checkpoint[0] = old_floor, old_checkpoint
                history.clear()
                restored_entities = floors[floor[0]]["entities"]
                for index, restored in enumerate(restored_entities):
                    if isinstance(restored, d.Monster) and restored.tribe.char == "l":
                        del restored_entities[index]
                        break
                _spawn(restored_entities, floors[floor[0]]["field"], "l", {(player.x, player.y)}, floors[floor[0]]["island"])
                return (5, "-- Time folds back to the beginning of the recorded past.")
            if ch == "I": player.stage3_flags |= STAGE3_I
            elif ch == "J": player.stage3_flags |= STAGE3_J; player.persistent_followers.append((player.x, player.y, floor[0], "J"))
            elif ch == "K" and not (player.stage3_flags & STAGE3_C): current["entities"].append(entity); event_message = "-- Bring the cursed sword."
            elif ch == "H" and (player.stage3_flags & (STAGE3_I | STAGE3_J | STAGE3_K)).bit_count() < 2: current["entities"].append(entity); event_message = "-- The High Elf does not recognize you."
            elif ch == "l": current["entities"].append(entity)
            elif _attack(player) < entity.tribe.level:
                # The encounter remains on the map when the player loses.
                # Rust resolves combat before removing the monster; keeping
                # the entity here prevents a failed attack from deleting it.
                current["entities"].append(entity)
                player.x, player.y = checkpoint[0]; player.lp = max(20, min(90, player.lp - 6)); player.item = None; player.item_uses = 0; player.item_taken_from = None
                event_message = "-- Respawned!"
            else:
                # A successful monster defeat establishes the next respawn
                # point, matching the legacy stages and the Rust port.
                if ch not in {"I", "J", "K", "H"}:
                    checkpoint[0] = (player.x, player.y)
                # Every ordinary monster replaces the current item. This is
                # important for d (Poisoned): defeating another monster with
                # no item must clear the poison and identify the new source.
                if ch != "H":
                    player.item = entity.tribe.item
                    player.item_taken_from = ch
                    player.item_uses = d.SWORD_USES if player.item in (d.ITEM_SWORD_X1_5, d.ITEM_SWORD_CURSED) else 0
                    if player.item == d.ITEM_SWORD_CURSED:
                        player.lp = (player.lp * 3 + 3) // 4
                if ch == "W": player.stage3_flags |= STAGE3_W; player.stage3_unlocked.add("W")
                if ch == "K": player.stage3_flags |= STAGE3_K; player.item = None
                if ch == "H": player.stage3_flags |= STAGE3_H
                if ch == "m": player.stage3_spores = True
                if ch == "C": player.stage3_flags |= STAGE3_C
                player.level += 10 if ch == "A" else 1; player.lp = max(1, min(100, player.lp + entity.tribe.feed)); player.karma += 1
                if ch == "D" or ch == "F": player.stage3_unlocked.add(ch)
                if entity.tribe.effect == d.EFFECT_CALTROP_SPREAD:
                    for x, y in iterate_ellipse_points(player.x, player.y, 3, 1.7, True, current["entities"]):
                        if (x + y) % 2 == 0 and current["field"][y][x] in (" ", d.WALL_CHAR): current["field"][y][x] = d.CHAR_CALTROP
                if entity.tribe.level > 0 and ch not in {"a", "A", "b", "c", "C", "W", "w"}:
                    queue[ch] = queue.get(ch, 0) + 1
            if event_message is None and ch not in ("K", "H", "l"):
                event_message = entity.tribe.event_message
            elif event_message is None and ch in ("K", "H") and entity not in current["entities"]:
                event_message = entity.tribe.event_message
    if player.companion is not None and player.karma >= player.companion.tribe.durability:
        ch = player.companion.tribe.char
        queue[ch] = queue.get(ch, 0) + 1
        player.companion = None
        event_message = "-- The companion vanishes."
    for f in player.persistent_followers:
        if f[2] == floor[0] and (player.x, player.y) != previous: player.persistent_followers[player.persistent_followers.index(f)] = (previous[0], previous[1], f[2], f[3])
    if floor[0] < 2 and (player.x, player.y) == current["down"]:
        floor[0] += 1; player.x, player.y = floors[floor[0]]["up"]; checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [(player.x, player.y, floor[0], ch) for _, _, _, ch in player.persistent_followers]
        event_message = f"-- Descended to floor {floor[0] + 1}/3."
    elif floor[0] > 0 and (player.x, player.y) == current["up"]:
        floor[0] -= 1; player.x, player.y = floors[floor[0]]["down"]; checkpoint[0] = (player.x, player.y)
        player.persistent_followers = [(player.x, player.y, floor[0], ch) for _, _, _, ch in player.persistent_followers]
        event_message = f"-- Ascended to floor {floor[0] + 1}/3."
    if hours % d.MONSTER_RESPAWN_INTERVAL == 0:
        for ch, count in list(queue.items()):
            if count:
                _spawn(floors[floor[0]]["entities"], floors[floor[0]]["field"], ch, {(player.x, player.y)}, floors[floor[0]]["island"])
                queue[ch] -= 1
    return (MESSAGE_TICKS, event_message) if event_message else None


def run_game(ui, seed_str, debug=False):
    floors, player = build()
    player.stage3_known, player.stage3_unlocked, player.stage3_won = set(), set(), False
    floor, checkpoint = [0], [floors[0]["up"]]
    player.stage3_floor = 0
    queue, history, hours = Counter(), deque(), 0
    message = (5, "-- The King has ordered the Dread Wyrm slain.")
    while player.lp > 0 and not player.stage3_won:
        current = floors[floor[0]]; cur = get_torched(player, d.TORCH_RADIUS)
        for y in range(len(cur)):
            for x in range(len(cur[0])): current["seen"][y][x] |= cur[y][x]
        if message[0] >= 0:
            remaining_tick = message[0] - 1
            message = (-1, "") if remaining_tick < 0 else (remaining_tick, message[1])
        show_entities = debug or getattr(ui, "map_mode", False)
        # The curses renderer discovers the player from the entity list, while
        # the pygame renderer receives it separately. Keep the Stage 3 state
        # model separate and provide a render-only combined list.
        render_entities = [player, *current["entities"]]
        ui.draw_stage(hours, player, render_entities, current["field"], cur, current["seen"], player.stage3_known, show_entities, 3, message[1], checkpoint=checkpoint[0])
        move = ui.input_direction()
        if move is None: return
        if move == (0, 0):
            continue
        event_message = _step(move, floors, player, floor, checkpoint, queue, history, hours)
        player.stage3_floor = floor[0]
        if event_message is not None:
            message = event_message
        hours += 1; player.lp -= 1
    message = (-1, ">> Treasures collected! <<" if player.stage3_won else ">> Starved to Death. <<")
    while True:
        current = floors[floor[0]]; cur = get_torched(player, d.TORCH_RADIUS)
        render_entities = [player, *current["entities"]]
        ui.draw_stage(hours, player, render_entities, current["field"], cur, current["seen"], player.stage3_known, debug, 3, message[1], True, checkpoint[0])
        key = ui.input_alphabet()
        if key is None:
            return
        if key == "m":
            debug = not debug
        elif key == "s":
            message = (-1, f"SEED: {seed_str}")
