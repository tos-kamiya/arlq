"""Experimental Stage 4 field: three floors with sealed rooms."""

from collections import Counter, deque
from copy import deepcopy
from typing import List, Optional, Set, Tuple

from . import defs as d
from .arlq import find_random_place, spawn_at
from .stage3 import Floor, ROSTER, ROSTER_TRIBES, _apply_terrain_hazards, _resolve_contact
from .stage_maze import generate_floor_field, room_center, shuffle_floor_layout, tile_at
from .utils import rand

FLOORS = 3
FLOOR_LAYOUT = [(1, 1), (0, 2), (0, 2)]
_STAGE4_NO_RESPAWN = d.NO_RESPAWN_MONSTERS | {"W", "w"}


def _generate_floor(
    index: int,
    up_tile: Optional[d.Point],
    down_tile: Optional[d.Point],
    corridor_h_width: int,
    corridor_v_width: int,
    room_counts: Tuple[int, int],
) -> Tuple[Floor, Set[d.Point]]:
    up_point = None if up_tile is None else room_center(up_tile)
    down_point = None if down_tile is None else room_center(down_tile)
    field, up, down, island_rooms, _ = generate_floor_field(
        up_point,
        down_point,
        corridor_h_width,
        corridor_v_width,
        *room_counts,
    )
    if index:
        field[up[1]][up[0]] = d.CHAR_STAIRS_UP
    if index < FLOORS - 1:
        field[down[1]][down[0]] = d.CHAR_STAIRS_DOWN
    entities: List[d.Entity] = []
    roster_index = 0 if index < 2 else index - 1
    for ch, count, empowered in ROSTER[roster_index]:
        if ch in {"I", "J", "K", "H", "W", "w"}:
            continue
        for _ in range(count):
            x, y = find_random_place(entities, field, distance=2)
            spawn_at(entities, x, y, d.CHAR_TO_TRIBE[ch], empowered=empowered, origin_floor=index)
    if index == FLOORS - 1:
        down = up
    return Floor(
        field=field,
        entities=entities,
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        known_companions=set(),
        up=up,
        down=down,
        island=None,
        up_stairs=[up] if index else [],
        down_stairs=[down] if index < FLOORS - 1 else [],
    ), island_rooms


def build(corridor_h_width: int = d.CORRIDOR_H_WIDTH, corridor_v_width: int = d.CORRIDOR_V_WIDTH):
    floor_layout = shuffle_floor_layout(FLOOR_LAYOUT)
    floors: List[Floor] = []
    island_rooms_by_floor: List[Set[d.Point]] = []
    tiles = [(x, y) for y in range(d.TILE_NUM_Y) for x in range(d.TILE_NUM_X)]
    stair_tiles = [rand.choice(tiles)]
    for _ in range(FLOORS - 2):
        options = [tile for tile in tiles if tile != stair_tiles[-1]]
        stair_tiles.append(rand.choice(options))
    for _ in range(1000):
        floors = []
        island_rooms_by_floor = []
        for index in range(FLOORS):
            up_tile = None if index == 0 else stair_tiles[index - 1]
            down_tile = None if index == FLOORS - 1 else stair_tiles[index]
            floor, island_rooms = _generate_floor(
                index,
                up_tile,
                down_tile,
                corridor_h_width,
                corridor_v_width,
                floor_layout[index],
            )
            floors.append(floor)
            island_rooms_by_floor.append(island_rooms)
        if len(floors) == FLOORS:
            break
    else:
        raise RuntimeError("could not generate Stage 4")
    elf_candidates = [
        (floor_index, room)
        for floor_index, island_rooms in enumerate(island_rooms_by_floor)
        for room in island_rooms
    ]
    if len(elf_candidates) != 1:
        raise RuntimeError("Stage 4 floor layout must reserve one Isolated Elf room")
    elf_floor, elf_room = elf_candidates[0]
    elf_data = floors[elf_floor]
    elf_data.island = room_center(elf_room)
    left = elf_room[0] * (d.TILE_WIDTH + 1) + 1
    top = elf_room[1] * (d.TILE_HEIGHT + 1) + 1
    for y in range(top, top + d.TILE_HEIGHT):
        for x in range(left, left + d.TILE_WIDTH):
            elf_data.field[y][x] = d.CHAR_FLOOR
    for x in range(left, left + d.TILE_WIDTH):
        if elf_room[1] > 0:
            elf_data.field[top - 1][x] = d.WALL_CHAR
        if elf_room[1] < d.TILE_NUM_Y - 1:
            elf_data.field[top + d.TILE_HEIGHT][x] = d.WALL_CHAR
    for y in range(top, top + d.TILE_HEIGHT):
        if elf_room[0] > 0:
            elf_data.field[y][left - 1] = d.WALL_CHAR
        if elf_room[0] < d.TILE_NUM_X - 1:
            elf_data.field[y][left + d.TILE_WIDTH] = d.WALL_CHAR
    elf_data.entities.append(
        d.Monster(left + d.TILE_WIDTH // 2, top + d.TILE_HEIGHT // 2, d.CHAR_TO_MONSTER_TRIBE["I"])
    )
    # After the roster and isolated elf are placed, add one optional second
    # stair at an unused open doorway. Choose a matching room location on
    # both adjoining floors so the extra stair is traversable in either way.
    for index in range(FLOORS - 1):
        upper, lower = floors[index], floors[index + 1]
        first_stair_room = tile_at(upper.down_stairs[0])
        candidates = [
            (x, y)
            for y in range(1, d.FIELD_HEIGHT - 1)
            for x in range(1, d.FIELD_WIDTH - 1)
            if upper.field[y][x] == d.CHAR_FLOOR and lower.field[y][x] == d.CHAR_FLOOR
            and tile_at((x, y)) != first_stair_room
            and (x, y) != upper.down and (x, y) != lower.up
        ]
        while candidates:
            upper_point = candidates.pop(rand.randrange(len(candidates)))
            if any(abs(entity.x - upper_point[0]) <= 2 and abs(entity.y - upper_point[1]) <= 2 for entity in upper.entities):
                continue
            lower_point = upper_point
            if any(abs(entity.x - lower_point[0]) <= 2 and abs(entity.y - lower_point[1]) <= 2 for entity in lower.entities):
                continue
            upper.field[upper_point[1]][upper_point[0]] = d.CHAR_STAIRS_DOWN
            lower.field[lower_point[1]][lower_point[0]] = d.CHAR_STAIRS_UP
            upper.down_stairs.append(upper_point)
            lower.up_stairs.append(lower_point)
            break
    player = d.Player(*floors[0].up, 1, d.LP_INIT)
    return floors, player


def run_game(ui, seed_str, debug=False, trace=None, config=None):
    """Run the experimental field with the existing multi-floor controls."""
    from .arlq import GameConfig, get_torched, tick_message
    from .i18n import t as tr
    from .trace import DIR_TO_KEY

    if config is None:
        config = GameConfig()
    floors, player = build(config.corridor_h_width, config.corridor_v_width)
    player.known_monsters = set()
    floor = [0]
    view_floor = 0
    checkpoint = [floors[0].up]
    queue = Counter()
    history = deque()
    hours = 0
    message = (5, tr("-- Explore the sealed rooms across three floors."))
    while player.lp > 0:
        current = floors[floor[0]]
        display_floor = floors[view_floor]
        cur = get_torched(player, config.torch_radius)
        for y in range(d.FIELD_HEIGHT):
            for x in range(d.FIELD_WIDTH):
                current.seen[y][x] |= cur[y][x]
        message = tick_message(message)
        floor_view = view_floor != floor[0]
        render_player = deepcopy(player) if floor_view else player
        ui.draw_stage(
            hours=hours, player=render_player, entities=[render_player, *display_floor.entities],
            field=display_floor.field,
            cur_torched=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)] if floor_view else cur,
            torched=display_floor.seen,
            known_types=player.known_monsters | display_floor.known_companions,
            show_entities=debug or getattr(ui, "map_mode", False), stage_num=4,
            message=message[1], checkpoint=None if floor_view else checkpoint[0], stage_roster=ROSTER_TRIBES,
            floor_view=floor_view,
            floor_label=f"F: {view_floor + 1}",
        )
        move = ui.input_direction()
        if move is None:
            if trace is not None:
                trace.record_quit()
                trace.set_outcome("unfinished" if getattr(ui, "ran_dry", False) else "quit")
            return
        if move == (0, 0):
            continue
        if getattr(ui, "shift_direction", False):
            view_floor = max(0, min(FLOORS - 1, view_floor + move[1]))
            continue
        view_floor = floor[0]
        if trace is not None:
            key = DIR_TO_KEY.get(move)
            if key is None:
                raise RuntimeError("--trace-record does not support non-cardinal movement")
            trace.begin_turn(key)
        result = _step4(move, floors, player, floor, checkpoint, queue, history, hours, trace)
        # A stair transition can change the player's floor during _step4().
        # Keep the displayed floor in sync for the next frame.
        view_floor = floor[0]
        if result is not None:
            message = result
        if trace is not None:
            trace.set_player(player, 4)
            trace.commit_turn()
        hours += 1
        player.lp -= 1
    if trace is not None:
        trace.set_outcome("lose")

    message = (-1, tr(">> Collapsed from hunger! <<"))
    while True:
        current = floors[floor[0]]
        cur = get_torched(player, config.torch_radius)
        ui.draw_stage(
            hours=hours,
            player=player,
            entities=[player, *current.entities],
            field=current.field,
            cur_torched=cur,
            torched=current.seen,
            known_types=player.known_monsters | current.known_companions,
            show_entities=debug,
            stage_num=4,
            message=message[1],
            extra_keys=True,
            checkpoint=checkpoint[0],
            stage_roster=ROSTER_TRIBES,
            floor_label=f"F: {floor[0] + 1}",
        )
        key = ui.input_alphabet()
        if key is None:
            return
        if key == "m":
            debug = not debug
        elif key == "s":
            message = (-1, tr("SEED: {seed_str}").format(seed_str=seed_str))


def _step4(direction, floors, player, floor, checkpoint, queue, history, hours, trace=None):
    current = floors[floor[0]]
    history.append((deepcopy(floors), deepcopy(player), floor[0], checkpoint[0], deepcopy(queue)))
    if len(history) > 80:
        history.popleft()
    previous = (player.x, player.y)
    from .stage3 import _move_player
    _move_player(direction, current, player, trace=trace)
    event_message = _apply_terrain_hazards(current, player, previous)
    hit = next((i for i, entity in enumerate(current.entities) if (entity.x, entity.y) == (player.x, player.y)), None)
    if hit is not None:
        contact = _resolve_contact(hit, current, floors, player, floor, checkpoint, queue, history, event_message, trace=trace)
        if contact.end_turn:
            return (contact.message_ticks, contact.message) if contact.message else None
        event_message = contact.message
    down_index = next((i for i, point in enumerate(current.down_stairs) if (player.x, player.y) == point), None)
    up_index = next((i for i, point in enumerate(current.up_stairs) if (player.x, player.y) == point), None)
    if floor[0] < FLOORS - 1 and down_index is not None:
        floor[0] += 1
        player.x, player.y = floors[floor[0]].up_stairs[down_index]
        checkpoint[0] = (player.x, player.y)
        event_message = f"-- Descended to floor {floor[0] + 1}/{FLOORS}."
    elif floor[0] > 0 and up_index is not None:
        floor[0] -= 1
        player.x, player.y = floors[floor[0]].down_stairs[up_index]
        checkpoint[0] = (player.x, player.y)
        event_message = f"-- Ascended to floor {floor[0] + 1}/{FLOORS}."
    _process_respawn_queue4(floors, player, floor, queue, hours, trace=trace)
    return (8, event_message) if event_message else None


def _process_respawn_queue4(floors, player, floor, queue, hours, trace=None):
    if hours % d.MONSTER_RESPAWN_INTERVAL:
        return
    for (spawn_floor, type_key), count in list(queue.items()):
        if not count:
            continue
        if type_key[-1].isdigit():
            ch, empowered = type_key[:-1], int(type_key[-1])
        else:
            ch, empowered = type_key, 1
        if ch in _STAGE4_NO_RESPAWN:
            queue[(spawn_floor, type_key)] -= 1
            continue
        current = floors[spawn_floor]
        avoid = {(player.x, player.y)} if spawn_floor == floor[0] else set()
        while True:
            x, y = find_random_place(current.entities, current.field, distance=2)
            if (x, y) not in avoid and not _inside_room((x, y), current.island):
                break
        spawn_at(current.entities, x, y, d.CHAR_TO_TRIBE[ch], empowered=empowered, origin_floor=spawn_floor)
        queue[(spawn_floor, type_key)] -= 1
        if trace is not None:
            trace.add_world_event({"type": "respawn", "kind": "monster", "id": type_key, "at": [x, y], "floor": spawn_floor})


def _inside_room(point, room_center):
    if room_center is None:
        return False
    tx, ty = tile_at(room_center)
    left, top = tx * (d.TILE_WIDTH + 1), ty * (d.TILE_HEIGHT + 1)
    return left <= point[0] <= left + d.TILE_WIDTH + 1 and top <= point[1] <= top + d.TILE_HEIGHT + 1
