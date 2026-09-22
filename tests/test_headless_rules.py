from collections import Counter, deque
from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq import stage3 as stage3_module
from arlq.arlq import GameConfig, game_config_from_args, respawn_entity, run_game, update_entities
from arlq.stage3 import STAGE3_C, STAGE3_H, STAGE3_I, STAGE3_J, STAGE3_K, STAGE3_W, _step

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
    return [{
        "field": field,
        "entities": entities,
        "seen": [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
        "known_companions": set(),
        "up": (1, 1),
        "down": (d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2),
        "island": None,
    }], field


def run_stage3_keys(keys, floors, player, floor, checkpoint, queue, history):
    messages = []
    for key in keys:
        result = _step(KEYS[key], floors, player, floor, checkpoint, queue, history, 1)
        messages.append(result[1] if result is not None else None)
    return messages


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

    def fake_run_game(ui, seed_str, debug, trace=None, config=None):
        received.append((ui, seed_str, debug, trace, config))

    monkeypatch.setattr(stage3_module, "run_game", fake_run_game)

    run_game("ui", "seed", 3, debug_show_entities=True, config=config)

    assert received == [("ui", "seed", True, None, config)]


@pytest.mark.parametrize(
    ("level", "expected_message", "expected_position"),
    [
        (1, "-- Respawned!", (2, 2)),
        (200, ">> Dread Wyrm (W) defeated! <<", (3, 2)),
    ],
)
def test_stage3_wyrm_combat_updates_message_position_and_state(level, expected_message, expected_position):
    player = d.Player(2, 2, level, 90)
    wyrm = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    floors, _ = stage3_state(player, [wyrm])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)

    assert messages == [expected_message]
    assert (player.x, player.y) == expected_position
    if level == 1:
        assert floors[0]["entities"] == [wyrm]
        assert player.item is None
        assert player.lp == 84
        assert not player.unlocked_treasures
        assert not queue
    else:
        assert floors[0]["entities"] == []
        assert player.level == 201
        assert player.karma == 1
        assert player.unlocked_treasures == {"TW"}
        assert not queue
        assert floors[0]["entities"] == []


def test_stage3_excludes_fire_lizard():
    assert d.CHAR_TO_MONSTER_TRIBE["f"].level < d.CHAR_TO_MONSTER_TRIBE[d.CHAR_FIRE_DRAKE].level
    assert all(ch != "f" for floor in stage3_module.ROSTER for ch, _, _ in floor)


def test_empowered_monsters_triple_level_and_have_separate_identity():
    normal = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["d"])
    empowered = d.Monster(2, 2, d.CHAR_TO_MONSTER_TRIBE["d"], empowered=2)

    assert d.monster_level(normal) == 20
    assert d.monster_level(empowered) == 60
    assert d.monster_type_key(normal) == "d"
    assert d.monster_type_key(empowered) == "d2"
    assert d.CHAR_TO_MONSTER_TRIBE["d"].feed == 60


def test_stage2_rebalances_bison_and_comodo_dragon_counts():
    b_configs = [config for config in d.SPAWN_CONFIGS_ST2 if config.tribe.char == "b"]
    populations = {config.tribe.char: config.population for config in d.SPAWN_CONFIGS_ST2 if config.tribe.char != "b"}

    assert [(config.population, config.empowered) for config in b_configs] == [(3, 1), (3, 2)]
    assert populations["d"] == 6


def test_stage3_empowered_roster_counts_are_rounded_down():
    assert [(ch, count, power) for ch, count, power in stage3_module.ROSTER[0] if power == 2] == [
        ("c", 1, 2),
        ("d", 3, 2),
    ]
    assert [(ch, count, power) for ch, count, power in stage3_module.ROSTER[1] if power == 2] == [
        ("b", 3, 2),
        ("c", 1, 2),
        ("d", 3, 2),
    ]
    assert [(ch, count, power) for ch, count, power in stage3_module.ROSTER[2] if power == 2] == [
        ("b", 3, 2),
        ("d", 3, 2),
    ]


def test_stage3_treasure_requires_current_timeline_w_defeat():
    player = d.Player(2, 2, 200, 90)
    player.unlocked_treasures.add("TW")
    treasure = d.Treasure(3, 2, "TW")
    wyrm = d.Monster(4, 2, d.CHAR_TO_MONSTER_TRIBE["W"])
    floors, _ = stage3_state(player, [treasure, wyrm])
    floor = [0]
    checkpoint = [(2, 2)]
    queue = Counter()
    history = deque()

    messages = run_stage3_keys("RR", floors, player, floor, checkpoint, queue, history)

    assert messages[0] == "-- You took the treasure chest, but the King's request remains."
    assert messages[1] == ">> Dread Wyrm (W) defeated! <<"
    assert player.stage3_treasure_collected
    assert player.stage3_won
    assert floors[0]["entities"] == []


def test_legacy_defeat_applies_item_and_caltrop_field_effect():
    player = d.Player(2, 2, 100, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 3
    plant = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["X"])
    field = blank_field()
    entities = [player, plant]

    effect, respawns, message, contact = update_entities(
        KEYS["R"], field, player, entities, set(), respawn_point=(2, 2)
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


def test_legacy_respawn_queue_controls_actual_respawn(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    plant = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["X"])
    field = blank_field()
    entities = [player, plant]

    _, respawns, _, _ = update_entities(
        KEYS["R"], field, player, entities, set(), respawn_point=(2, 2)
    )

    assert respawns == ["X"]
    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_args, **_kwargs: (5, 2))
    respawn_entity(d.CHAR_TO_MONSTER_TRIBE["X"], entities, field)

    assert [(e.x, e.y, e.tribe.char) for e in entities if isinstance(e, d.Monster)] == [(5, 2, "X")]


def test_legacy_non_respawning_monster_does_not_enter_respawn_queue():
    player = d.Player(2, 2, 100, 90)
    amoeba = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    field = blank_field()
    entities = [player, amoeba]

    _, respawns, _, _ = update_entities(
        KEYS["R"], field, player, entities, set(), respawn_point=(2, 2)
    )

    respawn_queue = Counter(t for t in respawns if t not in d.NO_RESPAWN_MONSTERS)
    assert respawn_queue == Counter()
    assert entities == [player]


def test_legacy_losing_twice_in_a_row_to_same_monster_escapes_to_random_place(monkeypatch):
    """A monster too strong to beat, sitting in the only corridor into an
    area, must not soft-lock the game: losing to it once still sends the
    player back to the checkpoint, but losing to the very same monster again
    right after (with no other monster contact in between) sends the player
    somewhere random instead."""
    player = d.Player(2, 2, 1, 90)
    dragon = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON])
    field = blank_field()
    entities = [player, dragon]

    _, _, message, _ = update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))
    assert message == (8, "-- Respawned!")
    assert (player.x, player.y) == (2, 2)
    assert player.last_contact_monster == (0, 3, 2)

    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_a, **_k: (10, 10))
    _, _, message, _ = update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))

    assert message == (8, "-- Respawned to a random location.")
    assert (player.x, player.y) == (10, 10)


def test_legacy_stage2_high_elf_refuses_once_then_sends_player_elsewhere(monkeypatch):
    """Stage 2's High Elf never actually fights (no checkpoint repel, no LP
    cost). The first refusal only shows a message and leaves the player in
    place; any later contact (even after an unrelated monster in between)
    sends the player elsewhere, like repeat contact with the Isolated Elf."""
    player = d.Player(2, 2, 1, 90)
    high_elf = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["H"])
    weak = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    field = blank_field()
    entities = [player, high_elf, weak]

    _, _, message, _ = update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))
    assert message == (8, "-- The High Elf does not recognize you yet.")
    assert (player.x, player.y) == (3, 2)
    assert player.lp == 90
    assert player.high_elf_refused is True

    # Move back and defeat an unrelated monster; unlike the ordinary
    # too-strong-monster streak, this must NOT clear the High Elf refusal.
    update_entities(KEYS["L"], field, player, entities, set(), respawn_point=(2, 2))
    _, _, message, _ = update_entities(KEYS["L"], field, player, entities, set(), respawn_point=(2, 2))
    assert message is None
    assert (player.x, player.y) == (1, 2)
    assert weak not in entities
    assert player.high_elf_refused is True

    update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))
    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_a, **_k: (10, 10))
    _, _, message, _ = update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))

    assert message == (8, "-- Respawned to a random location.")
    assert (player.x, player.y) == (10, 10)
    assert player.lp == 100  # unchanged by the High Elf; raised earlier by defeating the amoeba


def test_legacy_defeating_a_different_monster_resets_the_escape_streak(monkeypatch):
    """Beating an unrelated monster in between two losses to the same strong
    monster must NOT count as "two losses in a row": the escape branch is
    only for genuinely consecutive contact with the same individual."""
    player = d.Player(2, 2, 1, 90)
    dragon = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE[d.CHAR_DRAGON])
    weak = d.Monster(1, 2, d.CHAR_TO_MONSTER_TRIBE["a"])
    field = blank_field()
    entities = [player, dragon, weak]

    update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))
    assert player.last_contact_monster == (0, 3, 2)
    assert (player.x, player.y) == (2, 2)

    update_entities(KEYS["L"], field, player, entities, set(), respawn_point=(2, 2))
    assert player.last_contact_monster == (0, 1, 2)
    assert (player.x, player.y) == (1, 2)

    update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))
    assert (player.x, player.y) == (2, 2)

    monkeypatch.setattr("arlq.arlq.find_random_place", lambda *_a, **_k: (99, 99))
    _, _, message, _ = update_entities(KEYS["R"], field, player, entities, set(), respawn_point=(2, 2))

    assert message == (8, "-- Respawned!")
    assert (player.x, player.y) == (2, 2)
    assert player.last_contact_monster == (0, 3, 2)


def test_loop_companion_rewinds_world_but_preserves_knowledge(monkeypatch):
    player = d.Player(2, 2, 100, 90)
    player.known_monsters = {"a", "W"}
    player.unlocked_treasures = {"TW"}
    player.stage3_treasure_collected = True
    player.stage3_met_elves = {"I"}
    player.stage3_elf_floors = {"I": 1, "J": 3, "K": 2, "H": 1}
    loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    current_floors, current_field = stage3_state(player, [loop])
    current_floors[0]["known_companions"] = {"n"}
    current_floors[0]["seen"][1][1] = 9
    current_field[10][10] = d.WALL_CHAR

    old_player = d.Player(5, 5, 7, 60)
    old_player.stage3_won = False
    old_loop = d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"])
    old_treasure = d.Treasure(7, 5, "TW")
    old_floors, old_field = stage3_state(old_player, [old_loop, old_treasure])
    old_field[10][10] = " "
    old_queue = Counter({(0, "a"): 2})
    current_queue = Counter({(0, "X"): 3})
    history = deque([(old_floors, old_player, 0, (4, 5), old_queue)])
    floor = [0]
    checkpoint = [(2, 2)]

    def spawn_loop(entities, _field, _char, _avoid, _island, _floor_index=None):
        entities.append(d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"]))

    monkeypatch.setattr(stage3_module, "_spawn", spawn_loop)
    messages = run_stage3_keys(
        "R", current_floors, player, floor, checkpoint, current_queue, history
    )

    assert messages == ["-- Time folds back to the beginning of the recorded past."]
    assert (player.x, player.y) == (5, 5)
    assert player.level == 7
    assert player.lp == 60
    assert checkpoint == [(4, 5)]
    assert current_queue == Counter({(0, "a"): 2})
    assert current_floors[0]["field"][10][10] == " "
    assert current_floors[0]["seen"][1][1] == 9
    assert current_floors[0]["known_companions"] == {"l", "n"}
    assert player.known_monsters == {"a", "W"}
    assert player.unlocked_treasures == {"TW"}
    assert not player.stage3_treasure_collected
    # stage3_met_elves must revert with stage3_flags (it gates re-processing
    # of elf encounters), unlike the elf floor locations, which are pure map
    # knowledge and survive the rewind.
    assert player.stage3_met_elves == set()
    assert player.stage3_elf_floors == {"I": 1, "J": 3, "K": 2, "H": 1}
    assert not player.stage3_won
    assert len(current_floors[0]["entities"]) == 2
    assert any(
        isinstance(entity, d.Companion) and entity.tribe.char == "l"
        for entity in current_floors[0]["entities"]
    )
    assert any(isinstance(entity, d.Treasure) for entity in current_floors[0]["entities"])
    assert not history


def test_rewind_reverts_met_elves_together_with_stage3_flags(monkeypatch):
    """Rewinding to a point before an elf flag (e.g. STAGE3_H) was earned
    must also drop that elf from stage3_met_elves. Otherwise the field
    renders the elf as already resolved (dimmed, via stage3_met_elves)
    while the status bar shows the flag as not yet earned (via
    stage3_flags), and the player can never legitimately earn it again
    since met_elves short-circuits future contact."""
    player = d.Player(2, 2, 100, 90)
    player.stage3_flags = STAGE3_H
    player.stage3_met_elves = {"H"}
    loop = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["l"])
    current_floors, _ = stage3_state(player, [loop])

    old_player = d.Player(5, 5, 7, 60)
    old_player.stage3_flags = 0
    old_player.stage3_met_elves = set()
    old_loop = d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"])
    old_floors, _ = stage3_state(old_player, [old_loop])
    history = deque([(old_floors, old_player, 0, (4, 5), Counter())])
    floor = [0]
    checkpoint = [(2, 2)]
    queue: "Counter" = Counter()

    def spawn_loop(entities, _field, _char, _avoid, _island, _floor_index=None):
        entities.append(d.Companion(6, 5, d.CHAR_TO_COMPANION_TRIBE["l"]))

    monkeypatch.setattr(stage3_module, "_spawn", spawn_loop)
    run_stage3_keys("R", current_floors, player, floor, checkpoint, queue, history)

    assert not (player.stage3_flags & STAGE3_H)
    assert player.stage3_met_elves == set()


def test_carried_companion_respawns_on_its_origin_floor_not_current_floor():
    """A companion carried to another floor before it expires must respawn
    where it came from. Otherwise the floor it expired on can end up with
    two of the same kind once the queued respawn fires (e.g. two Pegasus
    companions on one floor)."""
    player = d.Player(2, 2, 100, 90)
    origin_pegasus = d.Companion(3, 2, d.CHAR_TO_COMPANION_TRIBE["p"], origin_floor=0)
    other_pegasus = d.Companion(7, 7, d.CHAR_TO_COMPANION_TRIBE["p"], origin_floor=1)
    floors = [
        {
            "field": blank_field(),
            "entities": [origin_pegasus],
            "seen": [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            "known_companions": set(),
            "up": (1, 1),
            "down": (4, 2),
            "island": None,
        },
        {
            "field": blank_field(),
            "entities": [other_pegasus],
            "seen": [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)],
            "known_companions": set(),
            "up": (5, 5),
            "down": (50, 50),
            "island": None,
        },
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
        return sum(1 for e in entities if isinstance(e, d.Companion) and e.tribe.char == char)

    assert companion_count(floors[0]["entities"], "p") == 1
    assert companion_count(floors[1]["entities"], "p") == 1


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

    monkeypatch.setattr(stage3_module, "_spawn", record_spawn)
    _step(KEYS["U"], floors, player, floor, checkpoint, queue, history, 0)

    assert [(entities is floors[0]["entities"], char, floor_index) for entities, char, floor_index in spawned] == [
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
    field[2][3] = d.WALL_CHAR

    effect, respawns, message, contact = update_entities(
        KEYS["R"], field, player, [player], set(), respawn_point=(2, 2)
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
    field[2][3] = d.WALL_CHAR

    update_entities(KEYS["R"], field, player, [player], set(), respawn_point=(2, 2))

    assert player.item is None
    assert player.item_uses == 0
    assert player.item_taken_from is None


def test_stage3_sword_breaking_its_last_wall_clears_all_equipment_state():
    player = d.Player(2, 2, 10, 90)
    player.item = d.ITEM_SWORD_CURSED
    player.item_uses = 1
    player.item_taken_from = "C"
    floors, field = stage3_state(player, [])
    field[2][3] = d.WALL_CHAR

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
        ("I", 0, STAGE3_I, "-- The Isolated Elf told you about the history of the elves."),
        ("J", 0, STAGE3_J, "-- The Javelin Elf joined your hunt for the Dread Wyrm!"),
        ("K", STAGE3_C, STAGE3_C | STAGE3_K, "-- The Collector Elf (K) gave you a rustless blade for your Cursed Sword!"),
        ("H", STAGE3_I | STAGE3_J, STAGE3_I | STAGE3_J | STAGE3_H, "-- The High Elf bestowed the talisman upon you!"),
    ],
)
def test_elf_encounters_apply_their_conditions(elf, initial_flags, expected_flags, expected_message):
    player = d.Player(2, 2, 100, 90)
    player.stage3_flags = initial_flags
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
    assert player.stage3_flags == expected_flags
    if elf == "J":
        assert player.persistent_followers == [(2, 2, 0, "J")]
        assert floors[0]["entities"] == []
    elif elf == "H":
        assert player.stage3_flags & STAGE3_H
        assert floors[0]["entities"] == [entity]
    else:
        assert floors[0]["entities"] == [entity]
        if elf == "K":
            assert player.item is None
            assert player.item_uses == 0
            assert player.item_taken_from is None


def test_collector_and_javelin_elves_increase_stage3_attack():
    player = d.Player(2, 2, 100, 90)
    player.stage3_flags = STAGE3_K
    player.persistent_followers = [(2, 2, 0, "J")]

    assert d.current_player_attack(player, 3) == 150


@pytest.mark.parametrize("stage_num", [0, 1, 2])
def test_stage3_bonuses_do_not_apply_outside_stage3(stage_num):
    # Regression test: the on-screen red/blue color coding and the strength
    # ranking column must use the same boosted attack value that Stage 3
    # combat resolution uses, and only when actually in Stage 3 - otherwise a
    # monster can be shown as unbeatable (red) while dying on contact, or
    # vice versa.
    player = d.Player(2, 2, 100, 90)
    player.stage3_flags = STAGE3_K
    player.persistent_followers = [(2, 2, 0, "J")]

    assert d.current_player_attack(player, stage_num) == 100
    assert d.current_player_attack(player, 3) == 150


@pytest.mark.parametrize(
    ("elf", "initial_flags"),
    [("I", 0), ("K", STAGE3_C), ("H", STAGE3_I | STAGE3_J)],
)
def test_elf_repeat_contact_shows_follow_up_message(elf, initial_flags):
    player = d.Player(2, 2, 100, 90)
    player.stage3_flags = initial_flags
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
    assert len(floors[0]["entities"]) == 1


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
    assert player.stage3_flags == 0

    messages = run_stage3_keys("LL", floors, player, floor, checkpoint, queue, history)
    assert messages == [None, None]
    assert (player.x, player.y) == (1, 2)
    assert player.high_elf_refused is True

    monkeypatch.setattr(stage3_module, "find_random_place", lambda *_a, **_k: (10, 10))
    messages = run_stage3_keys("RR", floors, player, floor, checkpoint, queue, history)

    assert messages[-1] == "-- Respawned to a random location."
    assert (player.x, player.y) == (10, 10)


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
    assert player.stage3_flags == 0

    messages = run_stage3_keys("LL", floors, player, floor, checkpoint, queue, history)
    assert messages == [None, None]
    assert (player.x, player.y) == (1, 2)
    assert player.k_elf_refused is True

    monkeypatch.setattr(stage3_module, "find_random_place", lambda *_a, **_k: (10, 10))
    messages = run_stage3_keys("RR", floors, player, floor, checkpoint, queue, history)

    assert messages[-1] == "-- Respawned to a random location."
    assert (player.x, player.y) == (10, 10)


def test_stage3_losing_twice_in_a_row_to_same_monster_escapes_to_random_place(monkeypatch):
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

    monkeypatch.setattr(stage3_module, "find_random_place", lambda *_a, **_k: (10, 10))
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

    monkeypatch.setattr(stage3_module, "find_random_place", lambda *_a, **_k: (99, 99))
    messages = run_stage3_keys("R", floors, player, floor, checkpoint, queue, history)

    assert messages == ["-- Respawned!"]
    assert (player.x, player.y) == (1, 2)
    assert player.last_contact_monster == (0, 3, 2)


def test_isolated_elf_sends_player_away_on_repeat_contact(monkeypatch):
    """The Isolated Elf's room has no door (see _inside_island in stage3.py);
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
    assert floors[0]["entities"] == [entity]

    monkeypatch.setattr(stage3_module, "find_random_place", lambda *_a, **_k: (20, 15))
    messages = run_stage3_keys("LR", floors, player, floor, checkpoint, queue, history)

    assert messages[-1] == "-- The Isolated Elf wants to be left alone, and sends you elsewhere."
    assert (player.x, player.y) == (20, 15)
    assert floors[0]["entities"] == [entity]


def test_non_isolated_elf_repeat_contact_does_not_relocate_player():
    """Regression guard: only the Isolated Elf's repeat contact should
    relocate the player. Other elves keep their existing in-place message."""
    player = d.Player(2, 2, 100, 90)
    player.stage3_flags = STAGE3_C
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


def test_stage3_flags_keep_their_bit_values():
    assert (STAGE3_C, STAGE3_I, STAGE3_K, STAGE3_H, STAGE3_W, STAGE3_J) == (1, 2, 4, 8, 16, 64)
    assert d.STAGE3_NO_RESPAWN_MONSTERS == {"a", "A", "b", "c", "C", "W", "w"}


def test_stage3_rare_amoeba_grants_the_special_exp_bonus():
    player = d.Player(2, 2, 2, 90)
    amoeba = d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["A"])
    floors, _ = stage3_state(player, [amoeba])

    run_stage3_keys("R", floors, player, [0], [(2, 2)], Counter(), deque())

    assert player.level == 12


def test_level_item_labels_follow_the_stage3_attack_bonuses():
    player = d.Player(1, 1, 100, 90)
    player.item = d.ITEM_POISONED
    player.item_taken_from = "d"
    assert d.level_item_labels(player, 1) == ("LVL: 100 /2", "+Poisoned(d)")

    player.stage3_flags = STAGE3_K
    player.persistent_followers.append((1, 1, 0, "J"))
    assert d.level_item_labels(player, 3) == ("LVL: 100 /2 x1.2 +25%", "+Poisoned(d)")
    assert d.level_item_labels(player, 2) == ("LVL: 100 /2", "+Poisoned(d)")

    player.item = d.ITEM_SWORD_X1_5
    assert d.level_item_labels(player, 3)[0] == "LVL: 100 x1.5 +25%"
    assert d.status_prefix(player, 3, 4).endswith("LVL: 100 x1.5 +25%  +Sword(d)  ")


def test_stage3_progress_marks_add_elf_floors_after_the_isolated_elf():
    player = d.Player(1, 1, 1, 90)
    player.stage3_flags = STAGE3_I | STAGE3_K
    player.stage3_elf_floors = {"K": 2, "H": 3}
    player.stage3_won = True

    assert d.stage3_progress_marks(player) == [
        ("C", False),
        ("I", True),
        ("J", False),
        ("K2", True),
        ("H3", False),
        ("W", False),
        ("T", True),
    ]


def test_revealed_entity_glyphs_distinguish_unknown_known_and_empowered():
    monster = d.Monster(4, 4, d.CHAR_TO_MONSTER_TRIBE["b"], empowered=2)
    hidden = d.revealed_entity_glyphs(monster, set(), False, 100, None, None)
    assert [(glyph.char, glyph.tone, glyph.bold) for glyph in hidden] == [("?", "yellow", True)]

    shown = d.revealed_entity_glyphs(monster, {d.monster_type_key(monster)}, False, 1, None, {"b"})
    assert [(glyph.char, glyph.tone, glyph.dim) for glyph in shown] == [
        ("b", "red", True),
        ("'", "red", True),
    ]

    companion = d.Companion(2, 2, d.CHAR_TO_COMPANION_TRIBE["n"])
    unknown = d.revealed_entity_glyphs(companion, set(), False, 1, None, None)
    assert [(glyph.char, glyph.tone) for glyph in unknown] == [("!", "companion")]
    preview = d.preview_entity_glyphs(monster)
    assert [(glyph.char, glyph.dim, glyph.bold) for glyph in preview] == [
        ("b", True, False),
        ("'", True, False),
    ]
