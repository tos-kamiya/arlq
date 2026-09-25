"""Experimental Stage 4 field: four floors with sealed rooms."""

from collections import Counter, deque
from copy import deepcopy
from typing import Deque, List, Optional, Set, Tuple

from . import defs as d
from .arlq import create_field, find_random_place, spawn_at
from .stage3 import Floor, ROSTER, ROSTER_TRIBES, _apply_terrain_hazards, _resolve_contact
from .utils import rand

FLOORS = 4
FILLED_ROOMS_PER_FLOOR = 2
_STAGE4_NO_RESPAWN = d.NO_RESPAWN_MONSTERS | {"W", "w"}


def _tile_at(point: d.Point) -> d.Point:
    return point[0] // (d.TILE_WIDTH + 1), point[1] // (d.TILE_HEIGHT + 1)


def _room_center(room: d.Point) -> d.Point:
    return room[0] * (d.TILE_WIDTH + 1) + d.TILE_WIDTH // 2 + 1, room[1] * (d.TILE_HEIGHT + 1) + d.TILE_HEIGHT // 2 + 1


def _field_connected(field: List[List[str]], start: d.Point, end: d.Point) -> bool:
    seen = {start}
    pending: Deque[d.Point] = deque([start])
    while pending:
        x, y = pending.popleft()
        if (x, y) == end:
            return True
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if (
                0 <= point[1] < len(field)
                and 0 <= point[0] < len(field[0])
                and point not in seen
                and field[point[1]][point[0]] in (d.CHAR_FLOOR, *d.STAIR_CHARS)
            ):
                seen.add(point)
                pending.append(point)
    return False


def _generate_floor(
    index: int,
    up_tile: Optional[d.Point],
    down_tile: Optional[d.Point],
    corridor_h_width: int,
    corridor_v_width: int,
) -> Tuple[Floor, Set[d.Point]]:
    all_rooms = {(x, y) for y in range(d.TILE_NUM_Y) for x in range(d.TILE_NUM_X)}
    for _ in range(1000):
        field, generated_up, generated_down = create_field(
            corridor_h_width, corridor_v_width, d.WALL_CHAR
        )
        up_tile_actual = _tile_at(generated_up) if up_tile is None else up_tile
        down_tile_actual = down_tile if down_tile is not None else _tile_at(generated_down)
        up = generated_up if up_tile is None else _room_center(up_tile)
        down = generated_down if down_tile is None else _room_center(down_tile)
        if up_tile_actual == down_tile_actual:
            continue

        # Stairs are fixed before choosing any rooms that will be filled.
        empty_candidates = all_rooms - {up_tile_actual, down_tile_actual}
        filled = set()
        available_columns = list(range(d.TILE_NUM_X))
        for _ in range(FILLED_ROOMS_PER_FLOOR):
            column = available_columns.pop(rand.randrange(len(available_columns)))
            row_candidates = [room for room in empty_candidates if room[0] == column]
            if not row_candidates:
                break
            filled.add(rand.choice(row_candidates))
        if len(filled) != FILLED_ROOMS_PER_FLOOR:
            continue

        # All filled rooms are excluded from the ordinary maze graph.
        for room in filled:
            left = room[0] * (d.TILE_WIDTH + 1) + 1
            top = room[1] * (d.TILE_HEIGHT + 1) + 1
            for y in range(top, top + d.TILE_HEIGHT):
                for x in range(left, left + d.TILE_WIDTH):
                    field[y][x] = d.WALL_CHAR

        rooms = all_rooms - filled
        connected = {up_tile_actual}
        edges: List[Tuple[d.Point, d.Point]] = []
        while connected != rooms:
            options = [
                (room, neighbor)
                for room in connected
                for neighbor in ((room[0] - 1, room[1]), (room[0] + 1, room[1]), (room[0], room[1] - 1), (room[0], room[1] + 1))
                if neighbor in rooms - connected
            ]
            if not options:
                break
            edge = rand.choice(options)
            edges.append(edge)
            connected.add(edge[1])
        if connected != rooms:
            continue

        # Rebuild all internal partitions as walls, then open only the
        # accepted tree. Filled ordinary rooms remain sealed.
        for ty in range(d.TILE_NUM_Y):
            for tx in range(d.TILE_NUM_X - 1):
                x = (tx + 1) * (d.TILE_WIDTH + 1)
                for y in range(ty * (d.TILE_HEIGHT + 1) + 1, (ty + 1) * (d.TILE_HEIGHT + 1)):
                    field[y][x] = d.WALL_CHAR
        for ty in range(d.TILE_NUM_Y - 1):
            y = (ty + 1) * (d.TILE_HEIGHT + 1)
            for tx in range(d.TILE_NUM_X):
                for x in range(tx * (d.TILE_WIDTH + 1) + 1, (tx + 1) * (d.TILE_WIDTH + 1)):
                    field[y][x] = d.WALL_CHAR
        for (x1, y1), (x2, y2) in edges:
            if y1 == y2:
                x = (max(x1, x2)) * (d.TILE_WIDTH + 1)
                offset = rand.randrange(d.TILE_HEIGHT + 1 - corridor_h_width) + 1
                for y in range(y1 * (d.TILE_HEIGHT + 1) + offset, y1 * (d.TILE_HEIGHT + 1) + offset + corridor_h_width):
                    field[y][x] = d.CHAR_FLOOR
            else:
                y = (max(y1, y2)) * (d.TILE_HEIGHT + 1)
                offset = rand.randrange(d.TILE_WIDTH + 1 - corridor_v_width) + 1
                for x in range(x1 * (d.TILE_WIDTH + 1) + offset, x1 * (d.TILE_WIDTH + 1) + offset + corridor_v_width):
                    field[y][x] = d.CHAR_FLOOR

        # create_field's generated start and end cells may sit away from
        # the room center; connect those reserved stair cells to this tree.
        for stair in (up, down):
            sx, sy = stair
            tx, ty = _tile_at(stair)
            cx, cy = _room_center((tx, ty))
            while sx != cx:
                field[sy][sx] = d.CHAR_FLOOR
                sx += 1 if cx > sx else -1
            while sy != cy:
                field[sy][sx] = d.CHAR_FLOOR
                sy += 1 if cy > sy else -1
            field[sy][sx] = d.CHAR_FLOOR

        # Carve stair rooms after the doors so the stair tiles always have
        # open floor around them. The connecting doorway remains the tree's.
        for stair in (up, down):
            left = _tile_at(stair)[0] * (d.TILE_WIDTH + 1) + 1
            top = _tile_at(stair)[1] * (d.TILE_HEIGHT + 1) + 1
            for y in range(top, top + d.TILE_HEIGHT):
                for x in range(left, left + d.TILE_WIDTH):
                    field[y][x] = d.CHAR_FLOOR
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
        if not _field_connected(field, up, down):
            continue
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
        ), filled
    raise RuntimeError("could not generate a connected Stage 4 floor")


def build(corridor_h_width: int = d.CORRIDOR_H_WIDTH, corridor_v_width: int = d.CORRIDOR_V_WIDTH):
    floors: List[Floor] = []
    filled_rooms_by_floor: List[Set[d.Point]] = []
    tiles = [(x, y) for y in range(d.TILE_NUM_Y) for x in range(d.TILE_NUM_X)]
    stair_tiles = [rand.choice(tiles)]
    for _ in range(FLOORS - 2):
        options = [tile for tile in tiles if tile != stair_tiles[-1]]
        stair_tiles.append(rand.choice(options))
    for _ in range(1000):
        floors = []
        filled_rooms_by_floor = []
        for index in range(FLOORS):
            up_tile = None if index == 0 else stair_tiles[index - 1]
            down_tile = None if index == FLOORS - 1 else stair_tiles[index]
            floor, filled_rooms = _generate_floor(index, up_tile, down_tile, corridor_h_width, corridor_v_width)
            floors.append(floor)
            filled_rooms_by_floor.append(filled_rooms)
        if len(floors) == FLOORS:
            break
    else:
        raise RuntimeError("could not generate Stage 4")
    # Only after every floor's ordinary maze is connected do we designate
    # one of the filled rooms across all floors as the isolated elf's room.
    elf_candidates = [
        (floor_index, room)
        for floor_index, filled_rooms in enumerate(filled_rooms_by_floor)
        for room in filled_rooms
    ]
    elf_floor, elf_room = rand.choice(elf_candidates)
    elf_data = floors[elf_floor]
    elf_data.island = _room_center(elf_room)
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
        first_stair_room = _tile_at(upper.down_stairs[0])
        candidates = [
            (x, y)
            for y in range(1, d.FIELD_HEIGHT - 1)
            for x in range(1, d.FIELD_WIDTH - 1)
            if upper.field[y][x] == d.CHAR_FLOOR and lower.field[y][x] == d.CHAR_FLOOR
            and _tile_at((x, y)) != first_stair_room
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
    message = (5, tr("-- Explore the sealed rooms across four floors."))
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
            show_entities=(debug or getattr(ui, "map_mode", False)) and not floor_view, stage_num=4,
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
        if result is not None:
            message = result
        if trace is not None:
            trace.set_player(player, 4)
            trace.commit_turn()
        hours += 1
        player.lp -= 1
    if trace is not None:
        trace.set_outcome("lose")


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
    tx, ty = _tile_at(room_center)
    left, top = tx * (d.TILE_WIDTH + 1), ty * (d.TILE_HEIGHT + 1)
    return left <= point[0] <= left + d.TILE_WIDTH + 1 and top <= point[1] <= top + d.TILE_HEIGHT + 1
