from collections import Counter, deque
from copy import deepcopy
from types import SimpleNamespace

import pytest

from arlq import arlq as arlq_module
from arlq import defs as d
from arlq import game_engine as game_engine_module
from arlq import i18n
from arlq import stage_replay as stage_replay_module
from arlq import stage_world as stage_world_module
from arlq.arlq import (
    GameConfig,
    activate_mimic_for_defeat,
    game_config_from_args,
    get_torched,
    respawn_entity,
    reveal_entities_in_fov,
    run_game,
    unlock_treasure_for_defeat,
    update_entities,
)
from arlq.game_engine import Floor, _step
from arlq.game_events import ContactEvent


@pytest.fixture(autouse=True)
def english_messages():
    previous_language = i18n.get_language()
    i18n.set_language("en")
    yield
    i18n.set_language(previous_language)


KEYS = {
    "U": (0, -1),
    "D": (0, 1),
    "L": (-1, 0),
    "R": (1, 0),
}


def blank_field():
    return [[" " for _ in range(d.FIELD_WIDTH)] for _ in range(d.FIELD_HEIGHT)]


def stage3_state(player, entities):
    field = blank_field()
    return [
        Floor(
            field=field,
            entities=entities,
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(1, 1),
            down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
            island=None,
        )
    ], field


def test_stage3_floor_declares_its_complete_state_shape():
    assert set(Floor.__dataclass_fields__) == {
        "field",
        "entities",
        "seen",
        "up",
        "down",
        "island",
        "up_stairs",
        "down_stairs",
        "contact_reveal",
        "collapse_landings",
        "persistent_barriers",
        "room_components",
    }


def test_stage3_builder_supports_floors_without_island_or_filled_rooms():
    layout = [(0, 0)] * d.STAGE3_FLOORS

    floors, player = game_engine_module.build(floor_layout=layout)

    assert len(floors) == d.STAGE3_FLOORS
    assert all(floor.island is None for floor in floors)
    assert "I" not in player.elf_stage_floors
    assert not any(
        isinstance(entity, d.Monster) and entity.tribe.char == "I"
        for floor in floors
        for entity in floor.entities
    )


def test_stage3_adds_one_random_extra_stair_pair():
    extra_transition_indices = set()
    for seed in range(8):
        game_engine_module.rand.set_seed(seed)
        floors, _ = game_engine_module.build(stage_num=3)
        pair_counts = [len(floor.down_stairs) for floor in floors[:-1]]

        assert sorted(pair_counts) == [1, 2]
        assert all(
            set(upper.down_stairs) == set(lower.up_stairs)
            for upper, lower in zip(floors, floors[1:])
        )
        extra_transition_indices.add(pair_counts.index(2))

    assert extra_transition_indices == {0, 1}


def run_stage3_keys(
    keys, floors, player, floor, checkpoint, queue, history, stage_num=3
):
    messages = []
    for key in keys:
        result = _step(
            KEYS[key], floors, player, floor, checkpoint, queue, history, 1, stage_num
        )
        if isinstance(result, game_engine_module._RewindRequest):
            result = game_engine_module._rewind_to_history(
                floors, player, floor, checkpoint, queue, history
            )
            messages.append(result)
        else:
            messages.append(result[1] if result is not None else None)
    return messages


def test_stage3_respawn_on_up_stairs_does_not_ascend_automatically():
    upper = Floor(
        field=blank_field(),
        entities=[],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
        down_stairs=[(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2)],
    )
    lower = Floor(
        field=blank_field(),
        entities=[d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 2),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
        up_stairs=[(1, 2)],
    )
    floors = [upper, lower]
    player = d.Player(2, 2, 1, 90)
    floor = [1]
    checkpoint = [(1, 2)]

    _step(KEYS["R"], floors, player, floor, checkpoint, Counter(), deque(), 1)

    assert (player.x, player.y) == (1, 2)
    assert floor[0] == 1

    # A turn that leaves the player on the stair must not trigger it either.
    _step((0, 0), floors, player, floor, checkpoint, Counter(), deque(), 2)

    assert floor[0] == 1


def test_stage4_final_floor_barriers_cover_ten_percent_of_open_cells():
    field = blank_field()
    field[1][1] = d.CHAR_STAIRS_UP
    entity = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floor = Floor(
        field=field,
        entities=[entity],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1),
        down=(3, 3),
        island=None,
        up_stairs=[(1, 1)],
    )
    protected = {(1, 1), (2, 2), (3, 3)}
    eligible_count = d.FIELD_WIDTH * d.FIELD_HEIGHT - len(protected)
    expected_barriers = (
        eligible_count * d.STAGE4_FINAL_FLOOR_BARRIER_PERCENT // 100
    )

    stage_world_module._place_stage4_final_floor_barriers(floor)

    barrier_points = {
        (x, y)
        for y, row in enumerate(floor.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_BARRIER
    }
    assert len(barrier_points) == expected_barriers
    assert not barrier_points & protected
    assert floor.field[entity.y][entity.x] == d.CHAR_FLOOR


def test_game_config_from_args_does_not_mutate_gameplay_constants():
    original = (d.TORCH_RADIUS, d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH)

    large_narrow = game_config_from_args(
        SimpleNamespace(large_torch=True, small_torch=False, narrower_corridors=True)
    )
    small_normal = game_config_from_args(
        SimpleNamespace(large_torch=False, small_torch=True, narrower_corridors=False)
    )

    assert large_narrow == GameConfig(
        torch_radius=original[0] + 1,
        corridor_h_width=original[1] - 1,
        corridor_v_width=original[2] - 1,
    )
    assert small_normal == GameConfig(
        torch_radius=original[0] - 1,
        corridor_h_width=original[1],
        corridor_v_width=original[2],
    )
    assert (d.TORCH_RADIUS, d.CORRIDOR_H_WIDTH, d.CORRIDOR_V_WIDTH) == original


def test_stage3_receives_the_per_run_game_config(monkeypatch):
    config = GameConfig(torch_radius=5, corridor_h_width=1, corridor_v_width=2)
    received = []

    def fake_run_game(ui, seed_str, debug_show_entities, trace=None, config=None):
        received.append((ui, seed_str, debug_show_entities, trace, config))

    monkeypatch.setattr(game_engine_module, "run_game", fake_run_game)

    run_game("ui", "seed", 3, debug_show_entities=True, config=config)

    assert received == [("ui", "seed", True, None, config)]


def test_game_loop_draws_with_keyword_arguments_only():
    draws = []

    class KeywordOnlyUI:
        def draw_stage(self, **kwargs):
            draws.append(kwargs)

        def input_direction(self):
            return None

    run_game(KeywordOnlyUI(), "seed", 1)

    assert len(draws) == 1
    assert set(draws[0]) == {
        "turn",
        "game_start_turn",
        "player",
        "entities",
        "field",
        "cur_torched",
        "torched",
        "known_types",
        "show_entities",
        "debug_show_entities",
        "stage_num",
        "message",
        "checkpoint",
        "reachable_cells",
    }
    assert draws[0]["game_start_turn"] is None
    assert draws[0]["stage_num"] == 1
    assert draws[0]["reachable_cells"] == set()


@pytest.mark.parametrize(
    ("level", "expected_message", "expected_position"),
    [
        (1, "-- Respawned!", (2, 2)),
        (200, ">> Dread Wyrm (W) defeated! <<", (3, 2)),
    ],
)
def test_stage3_wyrm_combat_updates_message_position_and_state(
    level, expected_message, expected_position
):
    player = d.Player(2, 2, level, 90)
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    treasure = d.Treasure(4, 2, "TW")
    floors, _ = stage3_state(player, [wyrm, treasure])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)

    assert messages == [expected_message]
    assert (player.x, player.y) == expected_position
    if level == 1:
        assert floors[0].entities == [treasure, wyrm]
        assert player.item is None
        assert player.lp == 84
        assert not treasure.unlocked
        assert not queue
    else:
        assert floors[0].entities == [treasure]
        assert player.level == 201
        assert player.karma == 1
        assert treasure.unlocked
        assert not queue


def test_stage3_excludes_fire_lizard():
    assert (
        d.CHAR_TO_MONSTER_TRIBE["f"].level
        < d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE].level
    )
    assert all(ch != "f" for floor in d.STAGE3_ROSTER for ch, _, _ in floor)


def test_stage4_has_independent_per_floor_roster():
    assert len(d.STAGE4_ROSTER) == d.STAGE4_FLOORS == 5
    assert [filled_rooms for _, filled_rooms in d.STAGE4_FLOOR_LAYOUT] == [1] * 5
    assert sum(island_rooms for island_rooms, _ in d.STAGE4_FLOOR_LAYOUT) == 1
    assert all(
        filled_rooms == 1
        for island_rooms, filled_rooms in d.STAGE4_FLOOR_LAYOUT
        if island_rooms
    )
    assert all(
        stage4_floor is not stage3_floor
        for stage4_floor, stage3_floor in zip(d.STAGE4_ROSTER, d.STAGE3_ROSTER)
    )
    assert all(
        ch not in {"I", "J", "K", "H", "S"}
        for floor in d.STAGE4_ROSTER
        for ch, _, _ in floor
    )
    for floor in d.STAGE4_ROSTER:
        for char in {entry[0] for entry in floor}:
            ranks = {rank for ch, _, rank in floor if ch == char}
            assert any(ranks <= allowed for allowed in ({1}, {1, 2}, {2, 3}))
    assert [
        sum(count for ch, count, _ in floor if ch == "a")
        for floor in d.STAGE4_ROSTER
    ] == [20, 16, 12, 8, 4]
    assert [
        sum(count for ch, count, _ in floor if ch == "c")
        for floor in d.STAGE4_ROSTER
    ] == [1, 1, 1, 1, 1]
    assert [
        sum(count for ch, count, _ in floor if ch == "A")
        for floor in d.STAGE4_ROSTER
    ] == [1, 1, 1, 1, 1]
    assert [
        sum(count for ch, count, _ in floor if ch == "k") for floor in d.STAGE4_ROSTER
    ] == [0, 2, 3, 3, 0]
    assert [
        sum(count for ch, count, _ in floor if ch == "X")
        for floor in d.STAGE4_ROSTER
    ] == [0, 1, 1, 1, 0]
    assert [
        sum(count for ch, count, _ in floor if ch == "g")
        for floor in d.STAGE4_ROSTER
    ] == [0, 2, 2, 2, 2]
    assert [
        sum(count for _, count, rank in floor if rank == 2 or rank == 3)
        for floor in d.STAGE4_ROSTER
    ] == [2, 10, 14, 14, 15]
    assert [
        sum(count for _, count, rank in floor if rank == 3)
        for floor in d.STAGE4_ROSTER
    ] == [0, 0, 0, 6, 12]
    assert [
        sum(count for ch, count, _ in floor if ch == "d")
        for floor in d.STAGE4_ROSTER
    ] == [6, 6, 6, 6, 6]
    assert all(
        rank == 1
        for floor in d.STAGE4_ROSTER
        for ch, _, rank in floor
        if ch in {"a", "A", "c"}
    )
    assert d.MARKSMAN_LP_DAMAGE == 4
    assert not any(ch == "G" for floor in d.STAGE4_ROSTER for ch, _, _ in floor)
    assert sum(count for ch, count, _ in d.STAGE4_ROSTER[3] if ch == "w") == 2
    assert sum(
        count
        for ch, count, rank in d.STAGE4_ROSTER[4]
        if ch == d.CHAR_FIRE_DRAKE and rank == 2
    ) == 1
    assert sum(count for ch, count, _ in d.STAGE4_ROSTER[4] if ch == "MF'") == 1
    assert not any(ch == "W" for floor in d.STAGE4_ROSTER for ch, _, _ in floor)
    assert (
        sum(count for floor in d.STAGE4_ROSTER for ch, count, _ in floor if ch == "V")
        == 1
    )
    assert (
        sum(count for floor in d.STAGE4_ROSTER for ch, count, _ in floor if ch == "E")
        == 1
    )
    assert sum(count for ch, count, _ in d.STAGE4_ROSTER[0] if ch == "e") == 1
    assert all(
        sum(count for ch, count, _ in d.STAGE4_ROSTER[index] if ch == "e") == 0
        for index in (1, 2, 3, 4)
    )
    assert (
        d.CHAR_TO_MONSTER_TRIBE["V"].level == d.CHAR_TO_MONSTER_TRIBE["E"].level == 30
    )
    assert all(
        sum(count for ch, count, _ in floor if ch == special) == 0
        for floor in d.STAGE4_ROSTER
        for special in ("F", "M")
        if floor is not d.STAGE4_ROSTER[4]
    )
    assert all(
        sum(count for ch, count, _ in floor if ch == "w") == 0
        for index, floor in enumerate(d.STAGE4_ROSTER)
        if index != 3
    )


def test_stage4_builds_elves_fire_drake_boss_and_barrier_wyrms(monkeypatch):
    monkeypatch.setattr(
        stage_world_module, "_place_stage4_final_floor_barriers", lambda _floor: None
    )
    floors, _ = game_engine_module.build(stage_num=4)

    elves = {
        entity.tribe.char
        for floor in floors
        for entity in floor.entities
        if isinstance(entity, d.Monster) and entity.tribe.is_elf
    }
    bosses = [
        entity
        for floor in floors
        for entity in floor.entities
        if isinstance(entity, d.Monster)
        and entity.tribe.char == d.CHAR_FIRE_DRAKE
        and entity.empowered == 2
    ]
    wyrms = [
        entity
        for entity in floors[3].entities
        if isinstance(entity, d.Monster) and entity.tribe.char == "w"
    ]
    golems = [
        (floor_index, entity)
        for floor_index, floor in enumerate(floors)
        for entity in floor.entities
        if isinstance(entity, d.Monster) and entity.tribe.char == "g"
    ]
    treasures = [
        entity for entity in floors[4].entities if isinstance(entity, d.Treasure)
    ]
    mimics = [
        entity
        for entity in floors[4].entities
        if isinstance(entity, d.Monster) and entity.tribe.char == "M"
    ]

    assert elves == {"I", "J", "K", "H", "L", "S"}
    assert len(bosses) == 1
    assert len(floors) == 5
    assert not any(
        isinstance(entity, d.Monster) and entity.tribe.char == "W"
        for floor in floors
        for entity in floor.entities
    )
    assert bosses[0] in floors[4].entities
    assert bosses[0].empowered == 2
    assert len(wyrms) == 2
    assert all(
        any(
            floors[3].field[y][x] == d.CHAR_BARRIER
            for x, y in (
                (wyrm.x - 1, wyrm.y),
                (wyrm.x + 1, wyrm.y),
                (wyrm.x, wyrm.y - 1),
                (wyrm.x, wyrm.y + 1),
            )
        )
        for wyrm in wyrms
    )
    assert all(
        floors[4].field[bosses[0].y + dy][bosses[0].x + dx] != d.CHAR_BARRIER
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if dx or dy
    )
    special_floor = {
        char: next(
            index
            for index, floor in enumerate(floors)
            if any(
                isinstance(entity, d.Monster) and entity.tribe.char == char
                for entity in floor.entities
            )
        )
        for char in ("V", "E")
    }
    assert special_floor["V"] in (1, 2, 3)
    assert special_floor["E"] in (1, 2, 3)
    assert special_floor["V"] != special_floor["E"]
    collapse_floors = [
        floor_index
        for floor_index, floor in enumerate(floors)
        for entity in floor.entities
        if isinstance(entity, d.Collapse)
    ]
    assert 1 <= len(collapse_floors) <= 2
    assert all(1 <= floor_index <= 3 for floor_index in collapse_floors)
    assert [
        sum(
            isinstance(entity, d.Monster) and entity.tribe.char == "X"
            for entity in floor.entities
        )
        for floor in floors
    ] == [0, 1, 1, 1, 0]
    assert bosses[0] in floors[4].entities
    assert bosses[0].empowered == 2
    assert len(treasures) == len(mimics) == 1
    assert treasures[0].encounter_type == "TF"
    assert d.monster_type_key(mimics[0]) == "MF'"
    assert not treasures[0].unlocked
    assert not mimics[0].active
    assert len(golems) == 9
    assert sorted(
        sum(floor_index == index for floor_index, _ in golems)
        for index in range(len(floors))
    ) == [0, 2, 2, 2, 3]


def test_trap_test_places_requested_entities_and_collapse_landing():
    floors, _ = stage_world_module.build_trap_test()

    assert len(floors) == 2
    assert all(cell == d.CHAR_WALL for row in floors[0].field for cell in row[:13])
    assert all(cell == d.CHAR_WALL for row in floors[0].field for cell in row[52:])
    assert sum(isinstance(entity, d.Collapse) for entity in floors[0].entities) == 1
    assert [
        sum(
            isinstance(entity, d.Monster) and entity.tribe.char == char
            for entity in floors[0].entities
        )
        for char in ("k", "X", "g")
    ] == [1, 1, 1]
    collapse = next(
        entity for entity in floors[0].entities if isinstance(entity, d.Collapse)
    )
    assert d.collapse_footprint((collapse.x, collapse.y)) <= floors[1].collapse_landings


def test_marksman_spawn_chooses_best_of_three_candidates(monkeypatch):
    scores = {(1, 1): 0, (2, 1): 4, (3, 1): 2}
    monkeypatch.setattr(arlq_module.rand, "randrange", lambda _length: 0)
    monkeypatch.setattr(
        arlq_module,
        "_marksman_sight_score",
        lambda _entities, _field, point: scores[point],
    )

    assert arlq_module.find_marksman_place([], blank_field()) == (2, 1)


def test_stage3_build_places_assigned_elves_and_wyrm_treasure():
    random_state = game_engine_module.rand._value
    random_seed = game_engine_module.rand.seed
    try:
        game_engine_module.rand.set_seed(12345)
        floors, player = game_engine_module.build(stage_num=3)
    finally:
        game_engine_module.rand._value = random_state
        game_engine_module.rand.seed = random_seed

    boss_floor = next(
        floor
        for floor in floors
        if any(
            isinstance(entity, d.Monster) and entity.tribe.char == "W"
            for entity in floor.entities
        )
    )

    treasures = [
        entity for entity in boss_floor.entities if isinstance(entity, d.Treasure)
    ]
    mimics = [
        entity
        for entity in boss_floor.entities
        if isinstance(entity, d.Monster) and entity.tribe.char == "M"
    ]
    assert len(treasures) == 1
    assert treasures[0].encounter_type == "TW"
    assert mimics == []
    for char in ("J", "K", "H"):
        assigned_floor = player.elf_stage_floors[char] - 1
        elves = [
            entity
            for floor in floors
            for entity in floor.entities
            if isinstance(entity, d.Monster) and entity.tribe.char == char
        ]
        assert len(elves) == 1
        assert elves[0] in floors[assigned_floor].entities
    assert "S" not in player.elf_stage_floors
    assert not any(
        isinstance(entity, d.Monster) and entity.tribe.char == "S"
        for floor in floors
        for entity in floor.entities
    )


@pytest.mark.parametrize(
    ("terrain", "blocked"),
    [
        (d.CHAR_CALTROP, False),
        (d.CHAR_BARRIER, False),
        (d.CHAR_COLLAPSE, False),
        (d.CHAR_WALL, True),
        *((stair, True) for stair in d.STAIR_CHARS),
    ],
)
def test_marksman_shots_are_blocked_only_by_opaque_terrain(terrain, blocked):
    field = blank_field()
    field[2][3] = terrain
    marksman = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["k"])
    current = Floor(
        field=field,
        entities=[marksman],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )
    player = d.Player(5, 2, 1, 90)

    game_engine_module._marksman_shoot(current, player)

    expected_lp = 90 if blocked else 90 - d.MARKSMAN_LP_DAMAGE
    assert player.lp == expected_lp
    assert marksman.arrow_marks == ([] if blocked else [((4, 2), "-")])


@pytest.mark.parametrize("old_arrow_mark", [False, True])
@pytest.mark.parametrize(
    "marksman_x, player_x, companion_x, mark_x",
    [
        (1, 5, 3, 4),
        (8, 4, 6, 5),
    ],
)
def test_floor_loop_companion_blocks_marksman_shots_after_player_moves(
    old_arrow_mark, marksman_x, player_x, companion_x, mark_x
):
    field = blank_field()
    marksman = d.Monster(marksman_x, 2, d.CHAR_TO_MONSTER_TRIBE["k"])
    player = d.Player(player_x, 3, 1, 90)
    entities = [marksman, d.Companion(companion_x, 2, d.CHAR_TO_COMPANION_TRIBE["l"])]
    current = Floor(
        field=field,
        entities=entities,
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )
    if old_arrow_mark:
        marksman.arrow_marks = [((mark_x, 2), "-")]

    _step(
        (0, -1),
        [current],
        player,
        [0],
        [(player_x, 3)],
        Counter(),
        deque(),
        1,
        stage_num=4,
    )

    assert (player.x, player.y) == (player_x, 2)
    assert player.lp == 90
    assert marksman.arrow_marks == ([((mark_x, 2), "-")] if old_arrow_mark else [])


def test_vortex_moves_wyrms_and_treasure_with_barriers_hidden(monkeypatch):
    field = blank_field()
    dread_wyrm = d.Monster(10, 8, d.CHAR_TO_MONSTER_TRIBE["W"])
    wyrm = d.Monster(20, 8, d.CHAR_TO_MONSTER_TRIBE["w"])
    marksman = d.Monster(20, 12, d.CHAR_TO_MONSTER_TRIBE["k"])
    marksman.arrow_marks = [((19, 12), "-")]
    treasure = d.Treasure(10, 15, "TW")
    for center in ((dread_wyrm.x, dread_wyrm.y), (wyrm.x, wyrm.y)):
        stage_world_module._place_barrier(field, center)
    seen = [[1] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    field[4][4] = d.CHAR_WALL
    field[4][5] = d.CHAR_STAIRS_UP
    current = Floor(
        field=field,
        entities=[dread_wyrm, wyrm, marksman, treasure],
        seen=seen,
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )

    positions = iter([(30, 16), (30, 8), (30, 12), (40, 16)])
    monkeypatch.setattr(
        game_engine_module,
        "find_random_place",
        lambda *_args, **_kwargs: next(positions),
    )
    player = d.Player(1, 1, 1, 90)

    game_engine_module._vortex_rearrange(current, player, 2, (20, 12))

    relocated_wyrm = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "w"
    )
    relocated_boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "W"
    )
    assert relocated_wyrm is not wyrm
    assert (relocated_wyrm.x, relocated_wyrm.y) == (30, 8)
    assert relocated_boss is not dread_wyrm
    assert (relocated_boss.x, relocated_boss.y) == (30, 16)
    assert treasure in current.entities
    assert (treasure.x, treasure.y) == (40, 16)
    assert field[8][19] == d.CHAR_FLOOR
    assert field[8][9] == field[8][11] == d.CHAR_FLOOR
    assert field[8][29] == field[8][31] == d.CHAR_BARRIER
    assert field[16][29] == field[16][31] == d.CHAR_BARRIER
    assert field[16][9] == field[16][11] == d.CHAR_FLOOR
    assert seen[8][9] == seen[8][11] == seen[8][29] == seen[8][31] == 0
    assert seen[16][29] == seen[16][31] == 0
    assert seen[16][9] == seen[16][11] == 0
    assert seen[4][4] == seen[4][5] == 1
    assert marksman.arrow_marks == []
    relocated_marksman = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "k"
    )
    assert relocated_marksman.arrow_marks == []


@pytest.mark.parametrize(
    ("initial_level", "expected_level"), [(1, 1), (2, 1), (21, 14), (22, 14)]
)
def test_erebus_rare_reduces_level_to_two_thirds_instead_of_granting_level(
    initial_level, expected_level
):
    player = d.Player(1, 1, initial_level, 90)

    d.grant_defeat_level(player, d.EFFECT_LEVEL_REDUCE)

    assert player.level == expected_level


def test_empowered_monsters_scale_level_and_have_separate_identity():
    normal = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["d"])
    empowered = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["d"], empowered=2)
    rank_three = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["b"], empowered=3)

    assert d.monster_level(normal) == 20
    assert d.monster_level(empowered) == 70
    assert d.monster_level(rank_three) == 75
    assert d.monster_type_key(normal) == "d"
    assert d.monster_type_key(empowered) == "d2"
    assert d.monster_type_key(rank_three) == "b3"
    assert d.CHAR_TO_MONSTER_TRIBE["d"].feed == 60


def test_stage2_rebalances_bison_and_comodo_dragon_counts():
    b_configs = [config for config in d.SPAWN_CONFIGS_ST2 if config.tribe.char == "b"]
    populations = {
        config.tribe.char: config.population
        for config in d.SPAWN_CONFIGS_ST2
        if config.tribe.char != "b"
    }

    assert [(config.population, config.empowered) for config in b_configs] == [
        (5, 1),
        (2, 2),
    ]
    assert populations["A"] == 3
    assert populations["d"] == 4


@pytest.mark.parametrize("stage_num", [3, 4])
def test_treasure_requires_current_timeline_w_defeat(stage_num):
    player = d.Player(2, 2, 200, 90)
    treasure = d.Treasure(3, 2, "TW")
    treasure.unlocked = True
    wyrm = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    floors, _ = stage3_state(player, [treasure, wyrm])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys(
        "RR", floors, player, floor, checkpoint, queue, history, stage_num=stage_num
    )

    assert (
        messages[0] == "-- You took the treasure chest, but the King's request remains."
    )
    assert messages[1] == ">> The King's request is complete! <<"
    assert player.treasure_collected
    assert player.stage_won
    assert floors[0].entities == []


def test_stage4_treasure_uses_the_win_screen_message():
    player = d.Player(2, 2, 200, 90)
    player.elf_stage_flags |= d.STAGE3_W_FLAG
    player.boss_defeated = True
    treasure = d.Treasure(3, 2, "TW")
    treasure.unlocked = True
    floors, _ = stage3_state(player, [treasure])

    messages = run_stage3_keys(
        "R", floors, player, [0], [(2, 2)], Counter(), deque(), stage_num=4
    )

    assert messages == [None]
    assert player.treasure_collected
    assert player.stage_won


def test_stage4_empowered_fire_drake_unlocks_treasure_and_completes_stage():
    player = d.Player(2, 2, 200, 90)
    boss = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE], empowered=2)
    treasure = d.Treasure(4, 2, "TF")
    floors, _ = stage3_state(player, [boss, treasure])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys(
        "RR", floors, player, floor, checkpoint, queue, history, stage_num=4
    )

    assert messages[0] == ">> Strong Fire Drake (F') defeated! <<"
    assert messages[1] is None
    assert player.boss_defeated
    assert not (player.elf_stage_flags & d.STAGE3_W_FLAG)
    assert player.treasure_collected
    assert player.stage_won
    assert treasure not in floors[0].entities
    assert not queue


def test_trap_test_shows_treasure_message_after_main_loop(monkeypatch):
    player = d.Player(2, 2, 200, d.LP_INIT)
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    treasure = d.Treasure(4, 2, "TW")
    floor = Floor(
        field=blank_field(),
        entities=[wyrm, treasure],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(2, 2),
        down=(4, 2),
        island=None,
    )
    monkeypatch.setattr(
        game_engine_module,
        "build_trap_test",
        lambda *_args, **_kwargs: ([floor], player),
    )
    draws = []
    moves = iter([(1, 0), (1, 0)])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: draws.append(kwargs),
        input_direction=moves.__next__,
        input_alphabet=lambda: None,
        map_mode=False,
    )

    game_engine_module.run_game(ui, "seed", stage_num=6)

    assert player.boss_defeated
    assert player.treasure_collected
    assert player.stage_won
    assert draws[-1]["message"] == ">> Treasure chest obtained! <<"


@pytest.mark.parametrize("stage_num", [3, 4])
def test_multifloor_win_screen_shows_treasure_and_floor(monkeypatch, stage_num):
    player = d.Player(2, 2, 200, d.LP_INIT)
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    treasure = d.Treasure(4, 2, "TW")
    floor = Floor(
        field=blank_field(),
        entities=[wyrm, treasure],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(2, 2),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )
    empty_floors = [
        Floor(
            field=blank_field(),
            entities=[],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(2, 2),
            down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
            island=None,
        )
        for _ in range((3 if stage_num == 3 else 4) - 1)
    ]
    monkeypatch.setattr(
        game_engine_module,
        "build",
        lambda *_args, **_kwargs: ([floor, *empty_floors], player),
    )
    draws = []
    moves = iter([(1, 0), (1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: draws.append(kwargs),
        input_direction=moves.__next__,
        input_alphabet=lambda: None,
        map_mode=False,
    )

    game_engine_module.run_game(ui, "seed", stage_num=stage_num)

    assert draws[-1]["message"] == ">> Treasure chest obtained! <<"
    assert draws[-1]["floor_label"] == f"1/{3 if stage_num == 3 else 4}"


def test_stage4_chests_wait_for_fire_drake_defeat():
    player = d.Player(2, 2, 200, 90)
    treasure = d.Treasure(3, 2, "TF")
    fire_drake = d.Monster(
        4, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE], empowered=2
    )
    mimic = d.Monster(
        5,
        2,
        d.CHAR_TO_MONSTER_TRIBE["M"],
        mimic_boss_char=d.CHAR_FIRE_DRAKE,
    )
    mimic.active = False
    floors, _ = stage3_state(player, [treasure, fire_drake, mimic])
    assert not treasure.unlocked
    assert d.revealed_entity_glyphs(treasure, set(), False, 200, None) == []
    assert d.revealed_entity_glyphs(mimic, set(), False, 200, None) == []
    assert d.preview_entity_glyphs(treasure)[0].char == "T"
    assert d.preview_entity_glyphs(mimic) == []
    assert d.preview_entity_glyphs(mimic, reveal_disguises=True)[0].char == "M"

    floor, checkpoint, queue, history = [0], [(2, 2)], Counter(), deque()
    messages = run_stage3_keys(
        "RR", floors, player, floor, checkpoint, queue, history, stage_num=4
    )
    assert d.revealed_entity_glyphs(treasure, set(), False, 200, None)[0].char == "T"
    assert d.revealed_entity_glyphs(mimic, set(), False, 200, None)[0].char == "T"
    assert (
        d.preview_entity_glyphs(treasure)[0].char
        == d.preview_entity_glyphs(mimic)[0].char
        == "T"
    )
    messages += run_stage3_keys(
        "RLL", floors, player, floor, checkpoint, queue, history, stage_num=4
    )

    assert messages == [
        None,
        ">> Strong Fire Drake (F') defeated! <<",
        "-- You defeated the Mimic, but were sent somewhere else.",
        None,
        None,
    ]
    assert treasure.unlocked
    assert player.boss_defeated
    assert mimic not in floors[0].entities
    assert not mimic.active
    assert not mimic.revealed and mimic.met
    assert checkpoint[0] == (mimic.x, mimic.y)
    assert "MF" in player.known_monsters
    assert d.revealed_entity_glyphs(mimic, set(), False, 200, None) == []
    assert d.preview_entity_glyphs(mimic) == []


def test_spores_are_a_temporary_item_replaced_by_the_next_monster():
    player = d.Player(2, 2, 100, 90)
    spores_monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["m"])
    next_monster = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floors, _ = stage3_state(player, [spores_monster, next_monster])
    floor, checkpoint, queue, history = [0], [(2, 2)], Counter(), deque()

    run_stage3_keys(
        "R", floors, player, floor, checkpoint, queue, history, stage_num=3
    )
    assert player.item == d.ITEM_SPORES
    assert player.item_taken_from == "m"

    run_stage3_keys(
        "R", floors, player, floor, checkpoint, queue, history, stage_num=3
    )
    assert player.item is None


def test_spores_reduce_torch_radius_and_are_shown_as_an_item():
    player = d.Player(2, 2, 100, 90)
    normal_torch = get_torched(player, d.TORCH_RADIUS)
    player.item = d.ITEM_SPORES
    player.item_taken_from = "m"

    spore_torch = get_torched(player, d.TORCH_RADIUS)

    assert sum(map(sum, spore_torch)) < sum(map(sum, normal_torch))
    assert d.level_item_labels(player, 3) == ("LVL: 100", "+Spores(m)")


def test_level_one_mimic_cannot_defeat_player_on_first_contact():
    player = d.Player(2, 2, 1, 90)
    mimic = d.Monster(
        3,
        2,
        d.CHAR_TO_MONSTER_TRIBE["M"],
        mimic_boss_char=d.CHAR_FIRE_DRAKE,
    )
    floors, _ = stage3_state(player, [mimic])
    floor, checkpoint, queue, history = [0], [(2, 2)], Counter(), deque()

    assert d.monster_level(mimic) == 1
    assert run_stage3_keys(
        "R", floors, player, floor, checkpoint, queue, history, stage_num=4
    ) == ["-- You defeated the Mimic, but were sent somewhere else."]
    assert "MF" in player.known_monsters
    assert "MW" not in player.known_monsters
    assert not mimic.active
    assert not mimic.revealed


def test_mimic_identification_is_scoped_to_its_boss():
    wyrm_mimic = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W")
    dragon_mimic = d.Monster(
        4, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char=d.CHAR_DRAGON
    )

    assert d.monster_type_key(wyrm_mimic) == "MW"
    assert d.monster_type_key(dragon_mimic) == "MD"
    assert d.preview_entity_glyphs(wyrm_mimic, known_types={"MW"})[0].char == "M"
    assert d.preview_entity_glyphs(dragon_mimic, known_types={"MW"})[0].char == "T"


def test_nomicon_identifies_active_mimic_in_fov():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    mimic = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W")
    mimic.active = False

    reveal_entities_in_fov(player, [mimic], torch_radius=3)
    assert "MW" not in player.known_monsters

    mimic.active = True
    reveal_entities_in_fov(player, [mimic], torch_radius=3)
    assert "MW" in player.known_monsters
    assert not mimic.revealed


def test_nomicon_records_cursed_chimera_floor_in_fov():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    chimera = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])

    reveal_entities_in_fov(player, [chimera], torch_radius=3, floor_index=1)

    assert player.known_c_floors == {2}


def test_non_nomicon_fov_does_not_record_cursed_chimera_floor():
    player = d.Player(2, 2, 1, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["p"])
    chimera = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])

    reveal_entities_in_fov(player, [chimera], torch_radius=3, floor_index=2)

    assert player.known_c_floors == set()


def test_debug_entity_display_reveals_mimic_identity():
    monster = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W")

    assert d.preview_entity_glyphs(monster)[0].char == "T"
    assert d.preview_entity_glyphs(monster, known_types={"MW"})[0].char == "M"
    assert d.preview_entity_glyphs(monster, reveal_disguises=True)[0].char == "M"
    assert d.revealed_entity_glyphs(monster, set(), True, 1, None)[0].char == "T"
    assert d.revealed_entity_glyphs(monster, {"MW"}, False, 1, None)[0].char == "M"
    assert (
        d.revealed_entity_glyphs(monster, set(), True, 1, None, reveal_disguises=True)[
            0
        ].char
        == "M"
    )


def test_vortex_uses_ordinary_monster_identification():
    vortex = d.Monster(4, 5, d.CHAR_TO_MONSTER_TRIBE["V"])

    assert d.preview_entity_glyphs(vortex)[0].char == "V"
    assert d.revealed_entity_glyphs(vortex, set(), False, 1, None)[0].char == "?"
    assert d.revealed_entity_glyphs(vortex, set(), True, 1, None) == []
    assert d.revealed_entity_glyphs(vortex, {"V"}, False, 1, None)[0].char == "V"


def test_stage4_debug_floor_views_show_v_as_v():
    draws = []
    moves = iter([(0, 1), (0, 1), (0, 1), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: draws.append(kwargs),
        input_direction=moves.__next__,
        input_alphabet=lambda: None,
        map_mode=False,
        shift_direction=True,
    )
    game_engine_module.rand.set_seed(1)

    run_game(ui, "debug", 4, debug_show_entities=True)

    by_floor = {draw["floor_label"]: draw for draw in draws}
    assert set(by_floor) == {"1/5", "2/5", "3/5", "4/5"}
    assert all(draw["debug_show_entities"] for draw in draws)
    assert not any(
        isinstance(entity, d.Monster) and entity.tribe.char == "V"
        for entity in by_floor["1/5"]["entities"]
    )
    vortex_draws = [
        (label, entity)
        for label in ("2/5", "3/5", "4/5")
        for entity in by_floor[label]["entities"]
        if isinstance(entity, d.Monster) and entity.tribe.char == "V"
    ]
    assert len(vortex_draws) == 1
    label, vortex = vortex_draws[0]
    assert (
        d.preview_entity_glyphs(
            vortex, reveal_disguises=by_floor[label]["debug_show_entities"]
        )[0].char
        == "V"
    )


def test_legacy_defeat_applies_item_and_caltrop_field_effect():
    player = d.Player(2, 2, 100, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 3
    plant = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["X"])
    field = blank_field()
    entities = [player, plant]

    effect, respawns, message, contact = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2)
    )

    assert effect == d.EFFECT_CALTROP_SPREAD
    assert respawns == ["X"]
    assert message == (8, "-- Caltrops were scattered!")
    assert contact
    assert player.item is None
    assert player.item_taken_from == "X"
    assert player.level == 101
    assert player.karma == 1
    assert any(d.CHAR_CALTROP in row for row in field)


def test_legacy_companion_identity_is_tracked_on_the_instance():
    player = d.Player(2, 2, 100, 90)
    companion = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["n"])

    update_entities(KEYS["R"], blank_field(), player, [companion])

    assert player.companion is companion
    assert companion.revealed


def test_legacy_boss_unlocks_its_treasure_object():
    player = d.Player(2, 2, 200, 90)
    dragon = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON])
    treasure = d.Treasure(4, 2, d.CHAR_TREASURE + d.CHAR_DRAGON)
    entities = [player, dragon, treasure]

    update_entities(KEYS["R"], blank_field(), player, entities)

    assert treasure.unlocked


@pytest.mark.parametrize("char", [d.CHAR_DRAGON, d.CHAR_FIRE_DRAKE, "W"])
def test_defeated_monster_char_identifies_its_treasure_key(char):
    monster = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[char])
    treasure = d.Treasure(4, 2, d.CHAR_TREASURE + char)

    unlock_treasure_for_defeat(monster, [treasure])

    assert treasure.unlocked


def test_defeated_boss_activates_only_its_mimics():
    wyrm = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    wyrm_mimic = d.Monster(
        3, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W"
    )
    dragon_mimic = d.Monster(
        4, 2, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char=d.CHAR_DRAGON
    )
    wyrm_mimic.active = False
    dragon_mimic.active = False

    activate_mimic_for_defeat(wyrm, [wyrm_mimic, dragon_mimic])

    assert wyrm_mimic.active
    assert not dragon_mimic.active


def test_defeated_empowered_boss_activates_only_matching_mimic():
    empowered_fire_drake = d.Monster(
        2, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE], empowered=2
    )
    mimic = d.Monster(
        3,
        2,
        d.CHAR_TO_MONSTER_TRIBE["M"],
        mimic_boss_char=d.CHAR_FIRE_DRAKE,
        mimic_boss_empowered=2,
    )
    ordinary_fire_drake_mimic = d.Monster(
        4,
        2,
        d.CHAR_TO_MONSTER_TRIBE["M"],
        mimic_boss_char=d.CHAR_FIRE_DRAKE,
        mimic_boss_empowered=1,
    )
    mimic.active = ordinary_fire_drake_mimic.active = False

    activate_mimic_for_defeat(
        empowered_fire_drake, [mimic, ordinary_fire_drake_mimic]
    )

    assert mimic.active
    assert not ordinary_fire_drake_mimic.active


def test_legacy_respawn_queue_controls_actual_respawn(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    plant = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["X"])
    field = blank_field()
    entities = [player, plant]

    _, respawns, _, _ = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2)
    )

    assert respawns == ["X"]
    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_args, **_kwargs: (5, 2))
    respawn_entity(d.CHAR_TO_MONSTER_TRIBE["X"], entities, field)

    assert [(e.x, e.y, e.tribe.char) for e in entities if isinstance(e, d.Monster)] == [
        (5, 2, "X")
    ]


def test_legacy_respawned_companion_is_already_revealed(monkeypatch):
    entities = []
    field = blank_field()
    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_args, **_kwargs: (5, 2))

    companion = respawn_entity(d.CHAR_TO_TRIBE["n"], entities, field)

    assert isinstance(companion, d.Companion)
    assert companion.revealed


def test_stage3_respawned_companion_is_already_revealed(monkeypatch):
    floor = Floor(
        field=blank_field(),
        entities=[],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(2, 2),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )
    monkeypatch.setattr(
        game_engine_module, "find_random_place", lambda *_args, **_kwargs: (5, 2)
    )

    game_engine_module._process_respawn_queue(
        [floor], d.Player(2, 2, 100, 90), [0], Counter({(0, "n"): 1}), 0
    )

    companion = next(
        entity for entity in floor.entities if isinstance(entity, d.Companion)
    )
    assert companion.tribe.char == "n"
    assert companion.revealed


def test_legacy_non_respawning_monster_does_not_enter_respawn_queue():
    player = d.Player(2, 2, 100, 90)
    amoeba = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    field = blank_field()
    entities = [player, amoeba]

    _, respawns, _, _ = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2)
    )

    respawn_queue = Counter(t for t in respawns if t not in d.NO_RESPAWN_MONSTERS)
    assert respawn_queue == Counter()
    assert entities == [player]


def test_legacy_losing_twice_in_a_row_to_same_monster_escapes_to_random_place(
    monkeypatch,
):
    """A monster too strong to beat, sitting in the only corridor into an
    area, must not soft-lock the game: losing to it once still sends the
    player back to the checkpoint, but losing to the very same monster again
    right after (with no other monster contact in between) sends the player
    somewhere random instead."""
    player = d.Player(2, 2, 1, 90)
    dragon = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON])
    field = blank_field()
    entities = [player, dragon]

    _, _, message, _ = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2)
    )
    assert message == (8, "-- Respawned!")
    assert (player.x, player.y) == (2, 2)
    assert player.last_contact_monster == (0, 3, 2)

    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_a, **_k: (10, 10))
    _, _, message, _ = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2)
    )

    assert message == (8, "-- Respawned to a random location.")
    assert (player.x, player.y) == (10, 10)


def test_stage2_high_elf_is_passive_red_monster_decoy(monkeypatch):
    """Stage 2's High Elf is identified on contact and never fights or respawns."""
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    field = blank_field()
    entities = [player, high_elf]
    hidden_glyph = d.revealed_entity_glyphs(
        high_elf, set(), False, 1, None, stage_num=2
    )
    assert hidden_glyph[0].char == "?"
    monkeypatch.setattr(
        "arlq.arlq.find_random_place",
        lambda *_a, **_k: pytest.fail("passive H must not respawn the player"),
    )

    result = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2), stage_num=2
    )
    assert result.message == (
        8,
        "-- It looks powerful, but doesn't seem to intend to attack you.",
    )
    assert high_elf.revealed
    revealed_glyph = d.revealed_entity_glyphs(
        high_elf, set(), False, 1, None, stage_num=2
    )
    assert (revealed_glyph[0].char, revealed_glyph[0].tone) == ("H", "red")
    assert (player.x, player.y) == (3, 2)
    assert player.lp == 90
    assert high_elf in entities
    assert "H" in player.known_monsters
    assert result.events.contact == ContactEvent("monster", "H", outcome="passive")

    update_entities(KEYS["L"], field, player, entities, stage_num=2)
    result = update_entities(KEYS["R"], field, player, entities, stage_num=2)
    assert result.events.contact == ContactEvent("monster", "H", outcome="passive")
    assert (player.x, player.y) == (3, 2)
    assert high_elf in entities


def test_legacy_defeating_a_different_monster_resets_the_escape_streak(monkeypatch):
    """Beating an unrelated monster in between two losses to the same strong
    monster must NOT count as "two losses in a row": the escape branch is
    only for genuinely consecutive contact with the same individual."""
    player = d.Player(2, 2, 1, 90)
    dragon = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON])
    weak = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    field = blank_field()
    entities = [player, dragon, weak]

    update_entities(KEYS["R"], field, player, entities, respawn_point=(2, 2))
    assert player.last_contact_monster == (0, 3, 2)
    assert (player.x, player.y) == (2, 2)

    update_entities(KEYS["L"], field, player, entities, respawn_point=(2, 2))
    assert player.last_contact_monster == (0, 1, 2)
    assert (player.x, player.y) == (1, 2)

    update_entities(KEYS["R"], field, player, entities, respawn_point=(2, 2))
    assert (player.x, player.y) == (2, 2)

    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_a, **_k: (99, 99))
    _, _, message, _ = update_entities(
        KEYS["R"], field, player, entities, respawn_point=(2, 2)
    )

    assert message == (8, "-- Respawned!")
    assert (player.x, player.y) == (2, 2)
    assert player.last_contact_monster == (0, 3, 2)


def test_loop_companion_rewinds_world_and_per_instance_companion_knowledge(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    player.known_monsters = {"a", "W"}
    player.known_c_floors = {2}
    player.elf_stage_flags |= d.STAGE3_W_FLAG
    player.boss_defeated = True
    player.treasure_collected = True
    player.elf_stage_floors = {"I": 1, "J": 3, "K": 2, "H": 1}
    loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    known_companion = d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    known_companion.revealed = True
    current_treasure = d.Treasure(5, 2, "TW")
    current_treasure.unlocked = True
    current_floors, current_field = stage3_state(
        player, [loop, known_companion, current_treasure]
    )
    current_floors[0].seen[1][1] = 9
    current_field[10][10] = d.CHAR_WALL

    old_player = d.Player(5, 5, 7, 60)
    old_loop = d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"])
    old_companion = d.Companion(8, 5, d.CHAR_TO_COMPANION_TRIBE["n"])
    old_treasure = d.Treasure(7, 5, "TW")
    old_floors, old_field = stage3_state(
        old_player, [old_loop, old_companion, old_treasure]
    )
    old_field[10][10] = " "
    old_queue = Counter({(0, "a"): 2})
    current_queue = Counter({(0, "X"): 3})
    history = deque([(old_floors, old_player, 0, (4, 5), old_queue)])
    floor = [0]
    checkpoint = [(2, 2)]

    def spawn_loop(entities, _field, _char, _avoid, _island, _floor_index=None):
        entities.append(d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"]))

    monkeypatch.setattr(game_engine_module, "_spawn", spawn_loop)
    messages = run_stage3_keys(
        "R", current_floors, player, floor, checkpoint, current_queue, history
    )

    assert messages == ["-- Time folds back to the beginning of the recorded past."]
    assert (player.x, player.y) == (5, 5)
    assert player.level == 7
    assert player.lp == 60
    assert checkpoint == [(4, 5)]
    assert current_queue == Counter({(0, "a"): 2})
    assert current_floors[0].field[10][10] == " "
    assert current_floors[0].seen[1][1] == 9
    assert player.known_monsters == {"a", "W"}
    assert player.known_c_floors == {2}
    assert not next(
        entity
        for entity in current_floors[0].entities
        if isinstance(entity, d.Treasure)
    ).unlocked
    assert not player.boss_defeated
    assert not player.treasure_collected
    restored_companion = next(
        entity
        for entity in current_floors[0].entities
        if isinstance(entity, d.Companion) and entity.tribe.char == "n"
    )
    assert not restored_companion.revealed
    assert player.elf_stage_floors == {"I": 1, "J": 3, "K": 2, "H": 1}
    assert not player.stage_won
    assert len(current_floors[0].entities) == 3
    assert any(
        isinstance(entity, d.Companion) and entity.tribe.char == "l"
        for entity in current_floors[0].entities
    )
    assert any(isinstance(entity, d.Treasure) for entity in current_floors[0].entities)
    assert not history


def test_rewind_reverts_per_instance_elf_encounter_state(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags = d.ELF_STAGE_H_FLAG | d.ELF_STAGE_S_FLAG
    current_high_elf = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    current_high_elf.revealed = True
    current_high_elf.met = True
    current_sylvan_elf = d.Monster(5, 2, d.CHAR_TO_MONSTER_TRIBE["S"])
    current_sylvan_elf.revealed = True
    current_sylvan_elf.met = True
    loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    current_floors, _ = stage3_state(
        player, [loop, current_high_elf, current_sylvan_elf]
    )

    old_player = d.Player(5, 5, 7, 60)
    old_player.elf_stage_flags = 0
    old_loop = d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"])
    old_high_elf = d.Monster(7, 5, d.CHAR_TO_MONSTER_TRIBE["H"])
    old_sylvan_elf = d.Monster(8, 5, d.CHAR_TO_MONSTER_TRIBE["S"])
    old_floors, _ = stage3_state(old_player, [old_loop, old_high_elf, old_sylvan_elf])
    history = deque([(old_floors, old_player, 0, (4, 5), Counter())])
    floor = [0]
    checkpoint = [(2, 2)]
    queue: "Counter" = Counter()

    def spawn_loop(entities, _field, _char, _avoid, _island, _floor_index=None):
        entities.append(d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"]))

    monkeypatch.setattr(game_engine_module, "_spawn", spawn_loop)
    run_stage3_keys("R", current_floors, player, floor, checkpoint, queue, history)

    assert not (player.elf_stage_flags & d.ELF_STAGE_H_FLAG)
    assert not (player.elf_stage_flags & d.ELF_STAGE_S_FLAG)
    restored_high_elf = next(
        entity
        for entity in current_floors[0].entities
        if isinstance(entity, d.Monster) and entity.tribe.char == "H"
    )
    assert not restored_high_elf.revealed
    assert not restored_high_elf.met
    restored_sylvan_elf = next(
        entity
        for entity in current_floors[0].entities
        if isinstance(entity, d.Monster) and entity.tribe.char == "S"
    )
    assert not restored_sylvan_elf.revealed
    assert not restored_sylvan_elf.met


def test_loop_contact_returns_rewind_request_before_normal_turn_processing(monkeypatch):
    player = d.Player(2, 2, 1, d.LP_INIT)
    loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    floors, _ = stage3_state(player, [loop])
    history = deque()

    def unexpected_hazard(*_args):
        raise AssertionError("normal turn processing ran after Loop contact")

    monkeypatch.setattr(game_engine_module, "_apply_terrain_hazards", unexpected_hazard)

    result = _step(KEYS["R"], floors, player, [0], [(2, 2)], Counter(), history, 0)

    assert isinstance(result, game_engine_module._RewindRequest)
    assert (player.x, player.y) == (3, 2)
    assert loop in floors[0].entities
    assert loop.revealed
    assert len(history) == 1


def test_cross_floor_loop_rewind_respawns_loop_on_contact_floor(monkeypatch):
    player = d.Player(2, 2, 20, d.LP_INIT)
    first_floor_loop = d.Companion(8, 8, d.CHAR_TO_COMPANION_TRIBE["l"])
    second_floor_loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    floors = [
        Floor(
            field=blank_field(),
            entities=[first_floor_loop],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(2, 2),
            down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
            island=None,
        ),
        Floor(
            field=blank_field(),
            entities=[second_floor_loop],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(2, 2),
            down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
            island=None,
        ),
    ]
    saved_floors = deepcopy(floors)
    saved_player = deepcopy(player)
    floor = [1]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque([(saved_floors, saved_player, 0, (2, 2), Counter())])
    respawn_position = (6, 6)

    def spawn_loop(entities, _field, char, _avoid, _island, floor_index=None):
        assert char == "l"
        assert floor_index == 1
        entities.append(
            d.Companion(*respawn_position, d.CHAR_TO_COMPANION_TRIBE["l"])
        )
        return respawn_position

    monkeypatch.setattr(stage_replay_module, "_spawn", spawn_loop)

    result = _step(
        KEYS["R"], floors, player, floor, checkpoint, queue, history, turn=1
    )

    assert isinstance(result, game_engine_module._RewindRequest)
    assert result.floor_index == 1
    game_engine_module._rewind_to_history(
        floors,
        player,
        floor,
        checkpoint,
        queue,
        history,
        loop_floor_index=result.floor_index,
    )

    assert floor == [0]
    assert (player.x, player.y) == (2, 2)
    restored_first_floor_loop = next(
        entity
        for entity in floors[0].entities
        if isinstance(entity, d.Companion) and entity.tribe.char == "l"
    )
    respawned_loop = next(
        entity
        for entity in floors[1].entities
        if isinstance(entity, d.Companion) and entity.tribe.char == "l"
    )
    assert (restored_first_floor_loop.x, restored_first_floor_loop.y) == (8, 8)
    assert (respawned_loop.x, respawned_loop.y) == respawn_position
    assert respawned_loop.revealed
    assert (
        d.revealed_entity_glyphs(respawned_loop, set(), False, 200, None)[0].char
        == "l"
    )


@pytest.mark.parametrize("has_vortex_map", [False, True])
def test_replay_rewind_restores_world_state_and_preserves_selected_map(
    monkeypatch, has_vortex_map
):
    def initial_state(*_args, **_kwargs):
        player = d.Player(5, 5, 1, d.LP_INIT)
        mimic = d.Monster(8, 8, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W")
        companion = d.Companion(7, 8, d.CHAR_TO_COMPANION_TRIBE["n"])
        chest = d.Treasure(9, 8, "TW")
        floor = Floor(
            field=blank_field(),
            entities=[mimic, companion, chest],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(5, 5),
            down=(9, 8),
            island=None,
        )
        return [floor], player

    monkeypatch.setattr(game_engine_module, "build", initial_state)
    monkeypatch.setattr(stage_replay_module, "build", initial_state)

    def spawn_loop(entities, _field, char, _avoid, _island, _floor_index=None):
        assert char == "l"
        entities.append(d.Companion(12, 12, d.CHAR_TO_COMPANION_TRIBE["l"]))
        return 12, 12

    monkeypatch.setattr(stage_replay_module, "_spawn", spawn_loop)
    player = d.Player(2, 2, 9, 30)
    player.known_monsters = {"MW"}
    player.elf_stage_floors = {"I": 2}
    loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    floors, _ = stage3_state(player, [loop])
    floors[0].seen[1][1] = 7
    changed_mimic = d.Monster(4, 4, d.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="W")
    changed_mimic.met = True
    changed_mimic.active = False
    changed_chest = d.Treasure(5, 4, "TW")
    changed_chest.unlocked = True
    floors[0].entities.extend([changed_mimic, changed_chest])

    vortex_seen = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    vortex_seen[2][2] = 3
    context = game_engine_module.ReplayContext(
        stage_num=4,
        seed=2468,
        config=GameConfig(),
        operations=[(1, 0), (0, 1)],
        vortex_maps=[(1, [vortex_seen])] if has_vortex_map else [],
    )
    history = deque([None])
    floor_index = [0]
    checkpoint = [(2, 2)]
    queue = Counter()

    game_engine_module._rewind_to_history(
        floors,
        player,
        floor_index,
        checkpoint,
        queue,
        history,
        context,
        operation_count=2,
    )

    restored_mimic = next(
        entity for entity in floors[0].entities if isinstance(entity, d.Monster)
    )
    restored_companion = next(
        entity for entity in floors[0].entities if isinstance(entity, d.Companion)
    )
    restored_loop = next(
        entity
        for entity in floors[0].entities
        if isinstance(entity, d.Companion) and entity.tribe.char == "l"
    )
    restored_chest = next(
        entity for entity in floors[0].entities if isinstance(entity, d.Treasure)
    )
    assert not restored_mimic.revealed
    assert not restored_mimic.met
    assert restored_mimic.active
    assert not restored_companion.revealed
    assert (restored_loop.x, restored_loop.y) == (12, 12)
    assert restored_loop.revealed
    assert (
        d.revealed_entity_glyphs(restored_loop, set(), False, 200, None)[0].char
        == "l"
    )
    assert not restored_chest.unlocked
    assert player.known_monsters == {"MW"}
    assert player.elf_stage_floors == {"I": 2}
    assert floors[0].seen[2][2] == (3 if has_vortex_map else 0)
    assert floors[0].seen[1][1] == (0 if has_vortex_map else 7)


def test_repeated_loop_rewind_uses_global_operation_window_and_keeps_vortex_history(
    monkeypatch,
):
    player = d.Player(2, 2, 9, 30)
    floors, _ = stage3_state(player, [])
    history = deque(
        [None] * 11
    )  # Only ten turns have passed since the previous rewind.
    early_vortex_map = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    later_vortex_map = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    early_vortex_map[3][4] = 5
    later_vortex_map[3][4] = 9
    replay = game_engine_module.ReplayContext(
        stage_num=4,
        seed=123,
        config=GameConfig(),
        operations=[(1, 0)] * 111,
        vortex_maps=[(35, [early_vortex_map]), (80, [later_vortex_map])],
    )
    restored_player = d.Player(5, 5, 3, 20)
    restored_floors, _ = stage3_state(restored_player, [])
    replay_targets = []

    def replay_prefix(context, target_count):
        replay_targets.append(target_count)
        return restored_floors, restored_player, 0, (1, 1), Counter()

    def spawn_loop(entities, _field, _char, _avoid, _island, _floor_index=None):
        entities.append(d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"]))

    monkeypatch.setattr(stage_replay_module, "replay_to_operation", replay_prefix)
    monkeypatch.setattr(stage_replay_module, "_spawn", spawn_loop)

    game_engine_module._rewind_to_history(
        floors,
        player,
        [0],
        [(2, 2)],
        Counter(),
        history,
        replay,
        operation_count=111,
    )

    # Rewinding 80 operations from operation 111 crosses the first l at 100;
    # it must reach the original timeline at 31, despite history holding 11.
    assert replay_targets == [111 - d.LOOP_TURNS]
    assert floors[0].seen[3][4] == 5
    assert replay.vortex_maps == [(35, [early_vortex_map]), (80, [later_vortex_map])]


def test_live_loop_rewind_replays_from_seed_for_repeatable_random_results(monkeypatch):
    def initial_state(*_args, **_kwargs):
        # Stage construction also consumes randomness in a real run.
        game_engine_module.rand.randrange(1000)
        player = d.Player(2, 2, 1, d.LP_INIT)
        floor = Floor(
            field=blank_field(),
            entities=[d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(2, 2),
            down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
            island=None,
        )
        return [floor], player

    monkeypatch.setattr(game_engine_module, "build", initial_state)
    monkeypatch.setattr(stage_replay_module, "build", initial_state)

    def play_once():
        game_engine_module.rand.set_seed(97531)
        loop_positions = []

        def draw_stage(**kwargs):
            loop_positions.append(
                next(
                    (entity.x, entity.y)
                    for entity in kwargs["entities"]
                    if isinstance(entity, d.Companion) and entity.tribe.char == "l"
                )
            )

        moves = iter([(1, 0), (0, 1), None])
        ui = SimpleNamespace(
            draw_stage=draw_stage,
            input_direction=moves.__next__,
            input_alphabet=lambda: None,
            map_mode=False,
        )
        run_game(ui, "seed", 3)
        return loop_positions, game_engine_module.rand.randrange(1000)

    assert play_once() == play_once()


def test_vortex_records_map_knowledge_before_disturbing_it(monkeypatch):
    player = d.Player(2, 2, 1, d.LP_INIT)
    vortex = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["V"])
    floor = Floor(
        field=blank_field(),
        entities=[],
        seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        up=(1, 1),
        down=(d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        island=None,
    )
    floor.seen[4][5] = 8
    replay = game_engine_module.ReplayContext(4, 55, GameConfig())

    def disturb_map(current, *_args, **_kwargs):
        current.seen[4][5] = 0

    monkeypatch.setattr(game_engine_module, "_vortex_rearrange", disturb_map)
    game_engine_module._defeat_monster(
        vortex,
        floor,
        player,
        [0],
        [(2, 2)],
        Counter(),
        floors=[floor],
        replay_context=replay,
        operation_index=2,
    )

    assert len(replay.vortex_maps) == 1
    assert replay.vortex_maps[0][0] == 2
    assert replay.vortex_maps[0][1][0][4][5] == 8
    assert floor.seen[4][5] == 0


def test_carried_companion_respawns_on_its_origin_floor_not_current_floor():
    """A companion carried to another floor before it expires must respawn
    where it came from. Otherwise the floor it expired on can end up with
    two of the same kind once the queued respawn fires (e.g. two Pegasus
    companions on one floor)."""
    player = d.Player(2, 2, 100, 90)
    origin_pegasus = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["p"], origin_floor=0)
    other_pegasus = d.Companion(7, 7, d.CHAR_TO_COMPANION_TRIBE["p"], origin_floor=1)
    floors = [
        Floor(
            field=blank_field(),
            entities=[origin_pegasus],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(1, 1),
            down=(4, 2),
            island=None,
        ),
        Floor(
            field=blank_field(),
            entities=[other_pegasus],
            seen=[[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            up=(5, 5),
            down=(50, 50),
            island=None,
        ),
    ]
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    # Pick up floor 0's own Pegasus, then descend to floor 1 while carrying it.
    _step(KEYS["R"], floors, player, floor, checkpoint, queue, history, 1)
    _step(KEYS["R"], floors, player, floor, checkpoint, queue, history, 2)
    assert floor[0] == 1
    assert player.companion is origin_pegasus

    # Force the carried companion to expire while it is on floor 1.
    player.karma = origin_pegasus.tribe.durability
    _step((0, 0), floors, player, floor, checkpoint, queue, history, 3)
    assert player.companion is None
    assert queue[(0, "p")] == 1  # queued for its origin floor, not floor 1

    # Advance to the next respawn tick: the respawn must land on floor 0,
    # leaving floor 1's own untouched Pegasus alone.
    interval = d.MONSTER_RESPAWN_INTERVAL
    next_boundary = ((3 // interval) + 1) * interval
    _step((0, 0), floors, player, floor, checkpoint, queue, history, next_boundary)

    def companion_count(entities, char):
        return sum(
            1 for e in entities if isinstance(e, d.Companion) and e.tribe.char == char
        )

    assert companion_count(floors[0].entities, "p") == 1
    assert companion_count(floors[1].entities, "p") == 1


def test_stage3_respawns_only_on_the_entity_original_floor(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    first_floors, _ = stage3_state(player, [])
    second_player = d.Player(2, 2, 100, 90)
    second_floors, _ = stage3_state(second_player, [])
    floors = first_floors + second_floors
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter({(0, "p"): 1, (0, "X"): 1, (1, "p"): 1})
    history = deque()
    spawned = []

    def record_spawn(entities, _field, char, _avoid, _island, floor_index=None):
        spawned.append((entities, char, floor_index))
        return (0, 0)

    monkeypatch.setattr(game_engine_module, "_spawn", record_spawn)
    _step(KEYS["U"], floors, player, floor, checkpoint, queue, history, 0)

    assert [
        (entities is floors[0].entities, char, floor_index)
        for entities, char, floor_index in spawned
    ] == [
        (True, "p", 0),
        (True, "X", 0),
        (False, "p", 1),
    ]
    assert queue[(0, "p")] == 0
    assert queue[(0, "X")] == 0
    assert queue[(1, "p")] == 0


@pytest.mark.parametrize(
    ("item", "expected_attack"),
    [
        (None, 10),
        (d.ITEM_SWORD_X1_5, 15),
        (d.ITEM_SWORD_CURSED, 30),
        (d.ITEM_POISONED, 5),
    ],
)
def test_sword_and_poison_attack_modifiers(item, expected_attack):
    player = d.Player(2, 2, 10, 90)
    player.item = item

    assert d.current_player_attack(player) == expected_attack


def test_clear_player_item_removes_all_equipment_state():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 3
    player.item_taken_from = "C"

    d.clear_player_item(player)

    assert player.item is None
    assert player.item_uses == 0
    assert player.item_taken_from is None


def test_sword_breaks_wall_and_consumes_one_use():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 2
    field = blank_field()
    field[2][3] = d.CHAR_WALL

    effect, respawns, message, contact = update_entities(
        KEYS["R"], field, player, [player], respawn_point=(2, 2)
    )

    assert effect is None
    assert respawns == []
    assert message is None
    assert not contact
    assert (player.x, player.y) == (3, 2)
    assert field[2][3] == " "
    assert player.item == d.ITEM_SWORD_CURSED
    assert player.item_uses == 1


def test_sword_breaking_its_last_wall_clears_all_equipment_state():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 1
    player.item_taken_from = "C"
    field = blank_field()
    field[2][3] = d.CHAR_WALL

    update_entities(KEYS["R"], field, player, [player], respawn_point=(2, 2))

    assert player.item is None
    assert player.item_uses == 0
    assert player.item_taken_from is None


def test_stage3_sword_breaking_its_last_wall_clears_all_equipment_state():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 1
    player.item_taken_from = "C"
    floors, field = stage3_state(player, [])
    field[2][3] = d.CHAR_WALL

    run_stage3_keys("R", floors, player, [0], [(2, 2)], Counter(), deque())

    assert player.item is None
    assert player.item_uses == 0
    assert player.item_taken_from is None


@pytest.mark.parametrize("cell", ["^", "v", d.CHAR_BARRIER])
def test_stage3_special_floor_cells_are_passable_without_using_sword(cell):
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 2
    player.item_taken_from = "C"
    floors, field = stage3_state(player, [])
    field[2][3] = cell

    run_stage3_keys("R", floors, player, [0], [(2, 2)], Counter(), deque())

    assert (player.x, player.y) == (3, 2)
    assert field[2][3] == cell
    assert player.item == d.ITEM_SWORD_CURSED
    assert player.item_uses == 2


@pytest.mark.parametrize(
    ("elf", "initial_flags", "expected_flags", "expected_message"),
    [
        (
            "I",
            0,
            d.ELF_STAGE_I_FLAG,
            "-- The Isolated Elf told you about the history of the elves.",
        ),
        (
            "J",
            0,
            d.ELF_STAGE_J_FLAG,
            "-- The Javelin Elf joined your hunt!",
        ),
        (
            "K",
            d.ELF_STAGE_C_FLAG,
            d.ELF_STAGE_C_FLAG | d.ELF_STAGE_K_FLAG,
            "-- The Collector Elf (K) gave you a rustless blade for your Cursed Sword!",
        ),
        (
            "H",
            d.ELF_STAGE_I_FLAG | d.ELF_STAGE_J_FLAG,
            d.ELF_STAGE_I_FLAG | d.ELF_STAGE_J_FLAG | d.ELF_STAGE_H_FLAG,
            "-- The High Elf bestowed the protective amulet upon you!",
        ),
    ],
)
def test_elf_encounters_apply_their_conditions(
    elf, initial_flags, expected_flags, expected_message
):
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags = initial_flags
    if elf == "K":
        player.item = d.ITEM_SWORD_CURSED
        player.item_uses = 2
        player.item_taken_from = "C"
    entity = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[elf])
    floors, _ = stage3_state(player, [entity])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)

    assert messages == [expected_message]
    assert player.elf_stage_flags == expected_flags
    if elf == "J":
        assert player.persistent_followers == [(2, 2, 0, "J")]
        assert floors[0].entities == []
    elif elf == "H":
        assert player.elf_stage_flags & d.ELF_STAGE_H_FLAG
        assert floors[0].entities == [entity]
    else:
        assert floors[0].entities == [entity]
        if elf == "K":
            assert player.item is None
            assert player.item_uses == 0
            assert player.item_taken_from is None


def test_collector_and_javelin_elves_increase_elf_stage_attack():
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags = d.ELF_STAGE_K_FLAG
    player.persistent_followers = [(2, 2, 0, "J")]

    assert d.current_player_attack(player, 3) == 150


@pytest.mark.parametrize("stage_num", [0, 1, 2, 3, 4])
def test_collector_and_javelin_bonuses_apply_in_every_stage(stage_num):
    # Field colors and combat must agree on permanent elf attack bonuses.
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags = d.ELF_STAGE_K_FLAG
    player.persistent_followers = [(2, 2, 0, "J")]

    assert d.current_player_attack(player, stage_num) == 150
    assert d.current_player_attack(player, 3) == 150


@pytest.mark.parametrize(
    ("elf", "initial_flags"),
    [("I", 0), ("K", d.ELF_STAGE_C_FLAG), ("H", d.ELF_STAGE_I_FLAG | d.ELF_STAGE_J_FLAG)],
)
def test_elf_repeat_contact_shows_follow_up_message(elf, initial_flags):
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags = initial_flags
    entity = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[elf])
    floors, _ = stage3_state(player, [entity])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("RLR", floors, player, floor, checkpoint, queue, history)

    assert messages[0] is not None
    assert messages[1] is None
    assert messages[2] is not None
    assert messages[2] != messages[0]
    assert len(floors[0].entities) == 1


def test_stage3_high_elf_refuses_once_then_sends_player_elsewhere(monkeypatch):
    """Before the player has met two of I/J/K, Stage 3's High Elf behaves
    like Stage 2's: the first refusal only shows a message and leaves the
    player in place, but any later contact sends the player elsewhere, even
    after an unrelated monster contact in between."""
    player = d.Player(2, 2, 100, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    weak = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floors, _ = stage3_state(player, [high_elf, weak])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    assert messages == ["-- The High Elf does not recognize you yet."]
    assert (player.x, player.y) == (3, 2)
    assert player.high_elf_refused is True
    assert player.elf_stage_flags == 0

    messages = run_stage3_keys("LL", floors, player, floor, checkpoint, queue, history)
    assert messages == [None, None]
    assert (player.x, player.y) == (1, 2)
    assert player.high_elf_refused is True

    monkeypatch.setattr(
        game_engine_module, "find_random_place", lambda *_a, **_k: (10, 10)
    )
    messages = run_stage3_keys("RR", floors, player, floor, checkpoint, queue, history)

    assert messages[-1] == "-- You were sent somewhere else."
    assert (player.x, player.y) == (10, 10)


def test_stage4_high_elf_accepts_l_and_s_after_initial_refusal():
    player = d.Player(2, 2, 100, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    floors, _ = stage3_state(player, [high_elf])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys(
        "R", floors, player, floor, checkpoint, queue, history, stage_num=4
    )
    assert messages == ["-- The High Elf does not recognize you yet."]

    player.elf_stage_flags |= d.ELF_STAGE_L_FLAG | d.ELF_STAGE_S_FLAG
    messages = run_stage3_keys(
        "LR", floors, player, floor, checkpoint, queue, history, stage_num=4
    )

    assert messages == [
        None,
        "-- The High Elf bestowed the protective amulet upon you!",
    ]
    assert player.elf_stage_flags & d.ELF_STAGE_H_FLAG


def test_stage3_collector_elf_refuses_once_then_sends_player_elsewhere(monkeypatch):
    """Before the player has the cursed sword, Stage 3's Collector Elf (K)
    behaves like the High Elf: the first refusal only shows a message and
    leaves the player in place, but any later contact sends the player
    elsewhere, even after an unrelated monster contact in between."""
    player = d.Player(2, 2, 100, 90)
    k_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["K"])
    weak = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floors, _ = stage3_state(player, [k_elf, weak])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    assert messages == ["-- Please bring the cursed sword (C)."]
    assert (player.x, player.y) == (3, 2)
    assert player.k_elf_refused is True
    assert player.elf_stage_flags == 0

    messages = run_stage3_keys("LL", floors, player, floor, checkpoint, queue, history)
    assert messages == [None, None]
    assert (player.x, player.y) == (1, 2)
    assert player.k_elf_refused is True

    monkeypatch.setattr(
        game_engine_module, "find_random_place", lambda *_a, **_k: (10, 10)
    )
    messages = run_stage3_keys("RR", floors, player, floor, checkpoint, queue, history)

    assert messages[-1] == "-- Respawned to a random location."
    assert (player.x, player.y) == (10, 10)


@pytest.mark.parametrize(("level", "expected_floors"), [(1, {1}), (100, set())])
def test_cursed_chimera_floor_is_recorded_on_loss_but_not_on_victory(
    level, expected_floors
):
    player = d.Player(2, 2, level, 90)
    chimera = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["C"])
    floors, _ = stage3_state(player, [chimera])

    run_stage3_keys("R", floors, player, [0], [(2, 2)], Counter(), deque())

    assert player.known_c_floors == expected_floors


def test_stage3_losing_twice_in_a_row_to_same_monster_escapes_to_random_place(
    monkeypatch,
):
    player = d.Player(2, 2, 1, 90)
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    floors, _ = stage3_state(player, [wyrm])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    assert messages == ["-- Respawned!"]
    assert (player.x, player.y) == (2, 2)
    assert player.last_contact_monster == (0, 3, 2)

    monkeypatch.setattr(
        game_engine_module, "find_random_place", lambda *_a, **_k: (10, 10)
    )
    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)

    assert messages == ["-- Respawned to a random location."]
    assert (player.x, player.y) == (10, 10)


def test_stage3_defeating_a_different_monster_resets_the_escape_streak(monkeypatch):
    player = d.Player(2, 2, 1, 90)
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    weak = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    floors, _ = stage3_state(player, [wyrm, weak])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    assert player.last_contact_monster == (0, 3, 2)

    run_stage3_keys("L", floors, player, floor, checkpoint, queue, history)
    assert player.last_contact_monster == (0, 1, 2)
    # Defeating a non-elf monster establishes a new checkpoint at the
    # player's current position (existing behavior), which matters for the
    # position asserted after the next loss below.
    assert checkpoint == [(1, 2)]

    run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    assert (player.x, player.y) == (2, 2)

    monkeypatch.setattr(
        game_engine_module, "find_random_place", lambda *_a, **_k: (99, 99)
    )
    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)

    assert messages == ["-- Respawned!"]
    assert (player.x, player.y) == (1, 2)
    assert player.last_contact_monster == (0, 3, 2)


def test_isolated_elf_sends_player_away_on_repeat_contact(monkeypatch):
    """The Isolated Elf's room has no door (see _inside_island in game_engine.py);
    a player who reaches it (e.g. via a Pegasus jump) must not be able to get
    trapped there, so any contact after the first sends them elsewhere."""
    player = d.Player(2, 2, 100, 90)
    entity = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["I"])
    floors, _ = stage3_state(player, [entity])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    assert messages == ["-- The Isolated Elf told you about the history of the elves."]
    assert (player.x, player.y) == (3, 2)
    assert floors[0].entities == [entity]

    monkeypatch.setattr(
        game_engine_module, "find_random_place", lambda *_a, **_k: (20, 15)
    )
    messages = run_stage3_keys("LR", floors, player, floor, checkpoint, queue, history)

    assert (
        messages[-1]
        == "-- The Isolated Elf wants to be left alone, and sends you elsewhere."
    )
    assert (player.x, player.y) == (20, 15)
    assert floors[0].entities == [entity]


def test_non_isolated_elf_repeat_contact_does_not_relocate_player():
    """Regression guard: only the Isolated Elf's repeat contact should
    relocate the player. Other elves keep their existing in-place message."""
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags = d.ELF_STAGE_C_FLAG
    entity = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["K"])
    floors, _ = stage3_state(player, [entity])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)
    messages = run_stage3_keys("LR", floors, player, floor, checkpoint, queue, history)

    assert messages[-1] == "-- The Collector Elf (K) looks satisfied."
    assert (player.x, player.y) == (3, 2)


def test_repeated_elf_contact_ends_turn_before_companion_expiration():
    player = d.Player(2, 2, 100, 90)
    player.companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["n"], origin_floor=0)
    player.karma = player.companion.tribe.durability
    entity = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["K"])
    entity.met = True
    floors, _ = stage3_state(player, [entity])
    queue = Counter()

    messages = run_stage3_keys("R", floors, player, [0], [(2, 2)], queue, deque())

    assert messages == ["-- The Collector Elf (K) looks satisfied."]
    assert player.companion is not None
    assert queue == Counter()


def test_sylvan_elf_grants_nectar_once_and_stays_in_place():
    player = d.Player(2, 2, 100, 90)
    companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    player.companion = companion
    elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["S"])
    floors, _ = stage3_state(player, [elf])

    messages = run_stage3_keys(
        "RLR", floors, player, [0], [(2, 2)], Counter(), deque()
    )

    assert player.elf_stage_flags & d.ELF_STAGE_S_FLAG
    assert companion.durability == 10
    assert elf.met and elf in floors[0].entities
    assert (player.x, player.y) == (3, 2)
    assert messages[-1] == "-- The Sylvan Elf replenished your fairy nectar."


@pytest.mark.parametrize(
    ("char", "expected_durability"),
    [("n", 13), ("o", 25), ("p", 7), ("l", 1)],
)
def test_fairy_nectar_extends_future_companions_except_loop_companion(
    char, expected_durability
):
    player = d.Player(2, 2, 100, 90)
    player.elf_stage_flags |= d.ELF_STAGE_S_FLAG
    companion = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE[char])
    floors, _ = stage3_state(player, [companion])

    game_engine_module._resolve_contact(
        0, floors[0], floors, player, [0], [(2, 2)], Counter(), deque(), None
    )

    assert player.companion is companion
    assert companion.durability == expected_durability


def test_elf_stage_flags_keep_their_bit_values():
    assert (
        d.ELF_STAGE_C_FLAG,
        d.ELF_STAGE_I_FLAG,
        d.ELF_STAGE_K_FLAG,
        d.ELF_STAGE_H_FLAG,
        d.ELF_STAGE_S_FLAG,
        d.STAGE3_W_FLAG,
        d.ELF_STAGE_J_FLAG,
    ) == (1, 2, 4, 8, 32, 16, 64)
    assert d.MONSTERS_EXCLUDED_FROM_RESPAWN == {
        "a", "A", "b", "c", "C", "F", "M", "O", "W", "w"
    }


def test_stage3_rare_amoeba_grants_the_special_exp_bonus():
    player = d.Player(2, 2, 2, 90)
    amoeba = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["A"])
    floors, _ = stage3_state(player, [amoeba])

    run_stage3_keys("R", floors, player, [0], [(2, 2)], Counter(), deque())

    assert player.level == 12


def test_level_item_labels_follow_permanent_elf_attack_bonuses():
    player = d.Player(1, 1, 100, 90)
    player.item = d.ITEM_POISONED
    player.item_taken_from = "d"
    assert d.level_item_labels(player, 1) == ("LVL: 100 /2", "+Poisoned(d)")

    player.elf_stage_flags = d.ELF_STAGE_K_FLAG
    player.persistent_followers.append((1, 1, 0, "J"))
    assert d.level_item_labels(player, 3) == ("LVL: 100 /2 x1.2 x1.25", "+Poisoned(d)")
    assert d.level_item_labels(player, 2) == ("LVL: 100 /2 x1.2 x1.25", "+Poisoned(d)")

    player.item = d.ITEM_SWORD_X1_5
    assert d.level_item_labels(player, 3)[0] == "LVL: 100 x1.5 x1.2 x1.25"
    assert d.status_prefix(player, 3, 4).endswith(
        "LVL: 100 x1.5 x1.2 x1.25  +Sword(d)  "
    )


def test_elf_stage_progress_marks_add_elf_floors_after_the_isolated_elf():
    player = d.Player(1, 1, 1, 90)
    player.elf_stage_flags = d.ELF_STAGE_I_FLAG | d.ELF_STAGE_K_FLAG
    player.elf_stage_floors = {"K": 2, "H": 3}
    player.known_c_floors = {3, 2}
    player.treasure_collected = True

    assert d.elf_stage_progress_marks(player, 3) == [
        ("C23", False),
        ("I", True),
        ("J", False),
        ("K2", True),
        ("H3", False),
        ("W", False),
        ("T", True),
    ]


def test_elf_stage_progress_marks_use_stage_specific_boss_labels():
    player = d.Player(1, 1, 1, 90)
    player.elf_stage_flags = d.STAGE3_W_FLAG

    assert d.stage_boss_label(3) == "W"
    assert d.stage_boss_label(4) == "F'"
    assert ("W", False) in d.elf_stage_progress_marks(player, 3)
    assert ("F'", False) in d.elf_stage_progress_marks(player, 4)

    player.boss_defeated = True

    assert ("W", True) in d.elf_stage_progress_marks(player, 3)
    assert ("F'", True) in d.elf_stage_progress_marks(player, 4)
    assert ("F'", True) not in d.elf_stage_progress_marks(player, 3)
    assert ("W", True) not in d.elf_stage_progress_marks(player, 4)

    assert d.STAGE_BOSSES[3] in {
        (char, rank) for floor in d.STAGE3_ROSTER for char, _, rank in floor
    }
    assert d.STAGE_BOSSES[4] in {
        (char, rank) for floor in d.STAGE4_ROSTER for char, _, rank in floor
    }


def test_revealed_entity_glyphs_distinguish_unknown_known_and_empowered():
    monster = d.Monster(4, 4, d.CHAR_TO_MONSTER_TRIBE["b"], empowered=2)
    hidden = d.revealed_entity_glyphs(monster, set(), False, 100, None)
    assert [(glyph.char, glyph.tone, glyph.bold) for glyph in hidden] == [
        ("?", "yellow", True)
    ]

    shown = d.revealed_entity_glyphs(
        monster, {d.monster_type_key(monster)}, False, 1, {"b"}
    )
    assert [(glyph.char, glyph.tone, glyph.dim) for glyph in shown] == [
        ("b", "red", True),
        ("'", "red", True),
    ]

    companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    unknown = d.revealed_entity_glyphs(companion, set(), False, 1, None)
    assert [(glyph.char, glyph.tone) for glyph in unknown] == [("!", "companion")]
    unknown_debug = d.revealed_entity_glyphs(
        companion, set(), True, 1, None, debug_show_entities=True
    )
    assert [(glyph.char, glyph.tone) for glyph in unknown_debug] == [("n", "default")]
    known_by_tribe = d.revealed_entity_glyphs(
        companion, {"n"}, True, 1, None, debug_show_entities=True
    )
    assert [(glyph.char, glyph.tone) for glyph in known_by_tribe] == [("n", "default")]
    companion.revealed = True
    known_debug = d.revealed_entity_glyphs(
        companion, set(), True, 1, None, debug_show_entities=True
    )
    assert [(glyph.char, glyph.tone) for glyph in known_debug] == [("n", "companion")]
    preview = d.preview_entity_glyphs(monster)
    assert [(glyph.char, glyph.dim, glyph.bold) for glyph in preview] == [
        ("b", True, False),
        ("'", True, False),
    ]

    rank_three = d.Monster(4, 4, d.CHAR_TO_MONSTER_TRIBE["b"], empowered=3)
    shown_rank_three = d.revealed_entity_glyphs(
        rank_three, {d.monster_type_key(rank_three)}, False, 1, {"b"}
    )
    assert [(glyph.char, glyph.tone) for glyph in shown_rank_three] == [
        ("b", "red"),
        ('"', "red"),
    ]
    assert [glyph.char for glyph in d.preview_entity_glyphs(rank_three)] == [
        "b",
        '"',
    ]
