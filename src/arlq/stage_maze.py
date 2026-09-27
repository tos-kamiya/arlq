"""Shared room-graph maze generation for the multi-floor stages."""

from . import defs as d
from .arlq import create_field
from .utils import rand


def tile_at(point: d.Point) -> d.Point:
    return point[0] // (d.TILE_WIDTH + 1), point[1] // (d.TILE_HEIGHT + 1)


def room_center(room: d.Point) -> d.Point:
    return (
        room[0] * (d.TILE_WIDTH + 1) + d.TILE_WIDTH // 2 + 1,
        room[1] * (d.TILE_HEIGHT + 1) + d.TILE_HEIGHT // 2 + 1,
    )


def shuffle_floor_layout(layout: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Shuffle ``(isolated_rooms, filled_rooms)`` specifications with rand."""
    remaining = layout.copy()
    shuffled = []
    while remaining:
        shuffled.append(remaining.pop(rand.randrange(len(remaining))))
    return shuffled


def generate_floor_field(
    up_point: d.Point | None,
    down_point: d.Point | None,
    corridor_h_width: int,
    corridor_v_width: int,
    island_room_count: int,
    filled_room_count: int,
    split_room_graph: bool = False,
) -> tuple[
    list[list[str]],
    d.Point,
    d.Point,
    set[d.Point],
    set[d.Point],
    tuple[set[d.Point], ...],
]:
    """Build a floor and return its isolated, filled, and split graph rooms."""
    all_rooms = {(x, y) for y in range(d.TILE_NUM_Y) for x in range(d.TILE_NUM_X)}
    for _ in range(1000):
        field, generated_up, generated_down = create_field(
            corridor_h_width, corridor_v_width, d.WALL_CHAR
        )
        up = up_point if up_point is not None else generated_up
        down = down_point if down_point is not None else generated_down
        up_tile, down_tile = tile_at(up), tile_at(down)
        if up_tile == down_tile:
            continue

        empty_candidates = all_rooms - {up_tile, down_tile}
        island_rooms: set[d.Point] = set()
        filled_rooms: set[d.Point] = set()
        available_columns = list(range(d.TILE_NUM_X))
        for _ in range(island_room_count):
            if not available_columns:
                break
            column = available_columns.pop(rand.randrange(len(available_columns)))
            row_candidates = [room for room in empty_candidates if room[0] == column]
            if row_candidates:
                island_rooms.add(rand.choice(row_candidates))
        for _ in range(filled_room_count):
            if not available_columns:
                break
            column = available_columns.pop(rand.randrange(len(available_columns)))
            row_candidates = [room for room in empty_candidates if room[0] == column]
            if row_candidates:
                filled_rooms.add(rand.choice(row_candidates))
        if (
            len(island_rooms) != island_room_count
            or len(filled_rooms) != filled_room_count
        ):
            continue

        # Isolated and ordinary filled rooms stay outside the room graph.
        sealed_rooms = island_rooms | filled_rooms
        connected_rooms = all_rooms - sealed_rooms
        connected = {up_tile}
        edges: list[tuple[d.Point, d.Point]] = []
        while connected != connected_rooms:
            options = [
                (room, neighbor)
                for room in connected
                for neighbor in (
                    (room[0] - 1, room[1]),
                    (room[0] + 1, room[1]),
                    (room[0], room[1] - 1),
                    (room[0], room[1] + 1),
                )
                if neighbor in connected_rooms - connected
            ]
            if not options:
                break
            edge = rand.choice(options)
            edges.append(edge)
            connected.add(edge[1])
        if connected != connected_rooms:
            continue

        room_components: tuple[set[d.Point], ...] = ()
        if split_room_graph:
            split_options = []
            for edge in edges:
                remaining_edges = [candidate for candidate in edges if candidate != edge]
                adjacency: dict[d.Point, set[d.Point]] = {
                    room: set() for room in connected_rooms
                }
                for room_a, room_b in remaining_edges:
                    adjacency[room_a].add(room_b)
                    adjacency[room_b].add(room_a)
                first = {edge[0]}
                pending = [edge[0]]
                while pending:
                    room = pending.pop()
                    for neighbor in adjacency[room] - first:
                        first.add(neighbor)
                        pending.append(neighbor)
                second = connected_rooms - first
                if len(first) < 3 or len(second) < 3:
                    continue
                split_options.append((edge, first, second))
            if not split_options:
                continue
            split_edge, first_component, second_component = rand.choice(split_options)
            edges.remove(split_edge)
            room_components = (first_component, second_component)

        for room in sealed_rooms:
            left = room[0] * (d.TILE_WIDTH + 1) + 1
            top = room[1] * (d.TILE_HEIGHT + 1) + 1
            for y in range(top, top + d.TILE_HEIGHT):
                for x in range(left, left + d.TILE_WIDTH):
                    field[y][x] = d.WALL_CHAR

        # Rebuild internal partitions, opening only the accepted room tree.
        for ty in range(d.TILE_NUM_Y):
            for tx in range(d.TILE_NUM_X - 1):
                x = (tx + 1) * (d.TILE_WIDTH + 1)
                for y in range(
                    ty * (d.TILE_HEIGHT + 1) + 1, (ty + 1) * (d.TILE_HEIGHT + 1)
                ):
                    field[y][x] = d.WALL_CHAR
        for ty in range(d.TILE_NUM_Y - 1):
            y = (ty + 1) * (d.TILE_HEIGHT + 1)
            for tx in range(d.TILE_NUM_X):
                for x in range(
                    tx * (d.TILE_WIDTH + 1) + 1, (tx + 1) * (d.TILE_WIDTH + 1)
                ):
                    field[y][x] = d.WALL_CHAR

        for (x1, y1), (x2, y2) in edges:
            if y1 == y2:
                x = max(x1, x2) * (d.TILE_WIDTH + 1)
                offset = rand.randrange(d.TILE_HEIGHT + 1 - corridor_h_width) + 1
                for y in range(
                    y1 * (d.TILE_HEIGHT + 1) + offset,
                    y1 * (d.TILE_HEIGHT + 1) + offset + corridor_h_width,
                ):
                    field[y][x] = d.CHAR_FLOOR
            else:
                y = max(y1, y2) * (d.TILE_HEIGHT + 1)
                offset = rand.randrange(d.TILE_WIDTH + 1 - corridor_v_width) + 1
                for x in range(
                    x1 * (d.TILE_WIDTH + 1) + offset,
                    x1 * (d.TILE_WIDTH + 1) + offset + corridor_v_width,
                ):
                    field[y][x] = d.CHAR_FLOOR

        # Join stair cells to the center of their rooms and open those rooms.
        for stair in (up, down):
            sx, sy = stair
            tx, ty = tile_at(stair)
            cx, cy = room_center((tx, ty))
            while sx != cx:
                field[sy][sx] = d.CHAR_FLOOR
                sx += 1 if cx > sx else -1
            while sy != cy:
                field[sy][sx] = d.CHAR_FLOOR
                sy += 1 if cy > sy else -1
            field[sy][sx] = d.CHAR_FLOOR
            left = tx * (d.TILE_WIDTH + 1) + 1
            top = ty * (d.TILE_HEIGHT + 1) + 1
            for y in range(top, top + d.TILE_HEIGHT):
                for x in range(left, left + d.TILE_WIDTH):
                    field[y][x] = d.CHAR_FLOOR

        return field, up, down, island_rooms, filled_rooms, room_components

    raise RuntimeError("could not generate a connected room-graph floor")
