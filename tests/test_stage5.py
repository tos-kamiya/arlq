"""Behavior and generation checks for Stages 5 and 6."""

from collections import Counter

import pytest

from arlq import defs as d
from arlq import display, stage5, stage56, stage6
from arlq import game_engine as engine
from arlq.arlq import barrier_lp_damage, get_torched
from arlq.stage_types import Floor


@pytest.fixture(autouse=True)
def fixed_rearrangement_seed(monkeypatch):
    monkeypatch.setattr(engine.rand, "_value", 123)
    monkeypatch.setattr(engine.rand, "seed", 123)


def state(roles=(), level=100, lp=90):
    player = d.Player(2, 2, level, lp)
    player.rescue_stage = True
    player.members = [d.PartyMember(2, 2, role) for role in roles]
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    current = Floor(
        field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (40, 16), None
    )
    return current, player


def monster(x, y, char, rank=1):
    return d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[char], rank)


@pytest.mark.parametrize('seed', [123, 456, 789])
def test_indexed_neighbors_preserve_generation_and_random_state(monkeypatch, seed):
    def snapshot():
        engine.rand.set_seed(seed)
        floors, _ = stage6.build()
        return (
            [(floor.field, [
                (type(e).__name__, e.x, e.y,
                 getattr(getattr(e, 'tribe', None), 'char', None),
                 getattr(e, 'empowered', None))
                for e in floor.entities
            ]) for floor in floors],
            engine.rand._value,
        )

    indexed = snapshot()

    def exhaustive_pairs(monsters, offsets):
        for index, first in enumerate(monsters):
            for second in monsters[index + 1:]:
                if (second.x - first.x, second.y - first.y) in offsets:
                    yield first, second

    monkeypatch.setattr(stage56, '_neighbor_pairs', exhaustive_pairs)
    assert snapshot() == indexed


@pytest.mark.parametrize('known', [set(), {'a'}, {'a', 'D'}, {'a', 'D', 'M'}])
@pytest.mark.parametrize('attack', [1, 100])
def test_shared_party_tones_match_individual_glyphs(known, attack):
    entities = [monster(3, 3, 'a'), monster(3, 4, 'D'), monster(8, 8, 'M')]
    tones = display.monster_party_tones(entities, known, attack)
    for entity in entities:
        kwargs = {'stage_num': 6, 'party_entities': entities}
        expected = display.revealed_entity_glyphs(entity, known, False, attack, None, **kwargs)
        assert display.revealed_entity_glyphs(
            entity, known, False, attack, None, party_tones=tones, **kwargs
        ) == expected


def step(current, player, direction=(1, 0), checkpoint=(2, 2), stage_num=6):
    return engine._step(
        direction,
        [current],
        player,
        [0],
        [checkpoint],
        Counter(),
        1,
        stage_num=stage_num,
    )


def test_playground_has_four_random_recruits_and_a_random_rank2_boss_party():
    floors, player = stage6.build()
    assert len(floors) == 4 and player.rescue_stage and player.treasure_stage
    for floor in floors:
        assert len(floor.room_components) == 2
        detached = next(component for component in floor.room_components if len(component) == 1)
        assert stage6.tile_at(floor.up) not in detached
        assert stage6.tile_at(floor.down) not in detached
        assert all(
            stage6.tile_at(point) not in detached
            for point in (
                floor.up_stairs
                + floor.down_stairs
                + floor.scholar_up_stairs
                + floor.scholar_down_stairs
            )
        )
        assert any(
            isinstance(entity, d.Monster)
            and entity.tribe.char in {"b", "c", "A"}
            and stage6.tile_at((entity.x, entity.y)) in detached
            for entity in floor.entities
        )
    assert stage6.tile_at((player.x, player.y)) not in next(
        component for component in floors[0].room_components if len(component) == 1
    )
    current = floors[-1]
    assert sum(
        isinstance(entity, d.Monster) and entity.tribe.char == "k"
        for entity in floors[1].entities
    ) == 2
    members = {
        e.role for f in floors for e in f.entities if isinstance(e, d.PartyMember)
    }
    assert len(members) == 4
    assert members <= {
        "Jester",
        "Healer",
        "Rogue",
        "Knight",
        "Dungeon Explorer",
        "Guardian",
    }
    assert not any(
        isinstance(e, d.PartyMember)
        for floor in floors[3:]
        for e in floor.entities
    )
    assert {
        e.origin_floor
        for floor in floors[:3]
        for e in floor.entities
        if isinstance(e, d.PartyMember)
    } <= {0, 1, 2}
    assert sum(
        isinstance(e, d.PartyMember)
        for floor in floors[:3]
        for e in floor.entities
    ) == 4
    assert not any(
        isinstance(e, d.Monster) and e.tribe.is_elf for f in floors for e in f.entities
    )
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "W"
    )
    party = stage56.monster_party(current, boss)
    assert (boss.tribe.char, boss.empowered) == ("W", 1)
    assert sum(
        isinstance(e, d.Monster) and e.tribe.char == "W"
        for floor in floors
        for e in floor.entities
    ) == 1
    assert not any(
        isinstance(e, d.Monster) and e.tribe.char == "W" and e.empowered > 1
        for floor in floors
        for e in floor.entities
    )
    vortex = next(e for e in party if e.tribe.char == "V")
    assert vortex.empowered == 1
    escorts = [e for e in party if e not in (boss, vortex)]
    assert len(escorts) == 1
    assert all(
        (e.tribe.char, e.empowered) in d.STAGE5_BOSS_ESCORTS for e in escorts
    )
    mimics = [
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "M"
    ]
    assert len(mimics) == 1
    assert not mimics[0].active and mimics[0].mimic_boss_char == "W"
    assert [
        sum(
            isinstance(entity, d.Monster)
            and entity.tribe.char == "g"
            and entity.empowered == 1
            for entity in floor.entities
        )
        for floor in floors
    ] == [1, 3, 3, 3]
    assert not any(
        isinstance(entity, d.Monster)
        and entity.tribe.char == "g"
        and entity.empowered > 1
        for floor in floors
        for entity in floor.entities
    )
    assert len([e for e in current.entities if isinstance(e, d.Treasure)]) == 1


def test_stage5_member_progress_shows_candidates_before_they_depart():
    _, player = state()
    player.known_member_floors = {"Jester": 1, "Rogue": 2}
    assert [
        label for label, _ in display.stage5_member_progress_marks(player)
    ] == ["J1", "H", "R2", "K", "D", "G"]


def test_stage6_departed_member_does_not_reappear():
    current, player = state(("Jester", "Healer"))
    recruit = d.PartyMember(3, 2, "Rogue")
    current.entities.append(recruit)

    step(current, player, stage_num=5)

    assert [member.role for member in player.members] == ["Healer", "Rogue"]
    assert not any(
        isinstance(entity, d.PartyMember) and entity.role == "Jester"
        for entity in current.entities
    )


def test_stage5_replaces_oldest_member_without_respawning_them():
    current, player = state(("Jester", "Healer"))
    companion = d.Companion(2, 2, d.CHAR_TO_TRIBE["n"])
    player.companion = companion
    recruit = d.PartyMember(3, 2, "Rogue")
    current.entities.append(recruit)
    player.joined_members.update(("Jester", "Healer"))

    step(current, player)

    assert [member.role for member in player.members] == ["Healer", "Rogue"]
    assert recruit not in current.entities
    assert player.joined_members == {"Jester", "Healer", "Rogue"}
    assert not any(
        isinstance(entity, d.PartyMember) and entity.role == "Jester"
        for entity in current.entities
    )
    assert display.stage5_member_progress_marks(player)[0] == ("J-", False)
    assert player.companion is companion


@pytest.mark.parametrize(
    "roles, gain",
    [
        ((), 2),
        (("Jester",), 2.4),
        (("Knight",), 1),
        (("Jester", "Knight"), 4 / 3),
        (("Healer", "Rogue"), 4 / 3),
        (("Guardian",), 4 / 3),
    ],
)
@pytest.mark.parametrize("stage_num", [5, 6])
def test_group_rewards_are_shared_then_adjusted_by_members(roles, gain, stage_num):
    current, player = state(roles, lp=10)
    current.entities = [monster(3, 2, "b"), monster(3, 3, "a")]
    feed = max(e.tribe.feed for e in current.entities)
    step(current, player, stage_num=stage_num)
    assert current.entities == []
    assert player.level == 100 + gain
    assert player.lp == min(d.LP_MAX, 10 + feed)



def test_knight_growth_uses_shared_experience_before_jester_bonus():
    current, player = state(("Jester", "Knight"), lp=10)
    knight = player.members[1]
    assert knight.level == 50
    current.entities = [monster(3, 2, "b"), monster(3, 3, "a")]
    step(current, player)
    assert player.level == pytest.approx(100 + 2 / 2.25 * 1.5)
    assert knight.level == pytest.approx(50 + 2 / 2.25 * 0.5)
    assert d.current_player_attack(player, 5) == pytest.approx(player.level + knight.level)


def test_group_strength_defeat_preserves_party_and_healer_penalty():
    current, player = state(("Healer", "Rogue"), level=10)
    enemies = [monster(3, 2, "b", 2), monster(3, 3, "w")]
    current.entities = enemies.copy()
    before = player.members.copy()
    step(current, player, checkpoint=(1, 1))
    assert current.entities == enemies
    assert player.level == 10 and player.lp == 88
    assert player.members == before
    assert all((member.x, member.y) == (1, 1) for member in player.members)


def test_group_keeps_unique_item_even_when_contacting_ordinary_member():
    current, player = state()
    current.entities = [monster(3, 2, "a"), monster(3, 3, "c")]
    step(current, player)
    assert player.item == d.ITEM_SWORD_X1_5


def test_fractional_attack_hazards_and_status():
    current, player = state(("Knight", "Dungeon Explorer"), level=100.5)
    assert d.current_player_attack(player) == pytest.approx(100.5)
    assert d.current_player_attack(player, 5) == pytest.approx(150.5)
    player.item = d.ITEM_SWORD_X1_5
    assert d.current_player_attack(player) == pytest.approx(150.75)
    assert d.current_player_attack(player, 5) == pytest.approx(200.75)
    assert barrier_lp_damage(player) == 30
    assert d.caltrop_lp_damage(player) == 3
    current.field[2][3] = d.CHAR_CALTROP
    step(current, player)
    assert player.lp == 87
    assert "LVL: 100" in display.status_prefix(player, 5, 0)
    assert "ATK: 200" in display.status_prefix(player, 5, 0)


def test_guardian_reduces_hazard_damage_independently_of_movement_cost():
    _, player = state(("Guardian",))
    assert barrier_lp_damage(player) == 10
    assert d.caltrop_lp_damage(player) == 1
    assert d.movement_lp_cost(player) == 1

    player.members.append(d.PartyMember(player.x, player.y, "Healer"))
    assert barrier_lp_damage(player) == 10
    assert d.caltrop_lp_damage(player) == 1
    assert d.movement_lp_cost(player) == pytest.approx(1 / 2)


def test_rogue_does_not_preannounce_marksman_shooting_lane():
    current, player = state(("Rogue",))
    marksman = monster(7, 3, "k")
    current.entities.append(marksman)
    assert stage56.rogue_danger(current, player, (3, 3)) is None
    current.field[3][5] = d.CHAR_WALL
    assert stage56.rogue_danger(current, player, (3, 3)) is None


def test_rogue_avoids_odd_marksman_shot_damage_but_shows_arrows():
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    marksman = monster(1, 2, "k")
    current = Floor(
        field, [marksman], [[0] * d.FIELD_WIDTH for _ in field],
        (1, 1), (d.FIELD_WIDTH - 2, d.FIELD_HEIGHT - 2), None,
    )
    player = d.Player(5, 2, 1, 90)
    player.members.append(d.PartyMember(player.x, player.y, "Rogue"))

    for player_x, expected_lp in ((5, 90), (6, 86), (7, 86)):
        player.x = player_x
        marksman.marksman_cooldown = 0
        assert engine._marksman_shoot(current, player)
        assert player.lp == expected_lp

    assert marksman.marksman_shots_fired == 3
    assert marksman.arrow_marks == [((4, 2), "-"), ((5, 2), "-"), ((6, 2), "-")]


def test_waiting_member_blocks_marksman_shot():
    current, player = state()
    player.x, player.y = 5, 2
    marksman = monster(1, 2, "k")
    waiting = d.PartyMember(3, 2, "Healer")
    current.entities.extend([marksman, waiting])
    assert not engine._marksman_shoot(current, player)
    assert player.lp == 90
    current.entities.remove(waiting)
    assert engine._marksman_shoot(current, player)
    assert player.lp == 86


def test_rogue_identifies_active_mimics_and_traps_when_they_enter_fov():
    current, player = state(("Rogue",))
    targets = [monster(x, 2, char) for x, char in zip((4, 5, 6, 7), "EMgX")]
    current.entities.extend(targets)
    visible = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    visible[2][4] = 1

    stage56.reveal_rogue_monsters(current, player, visible)

    assert player.known_monsters == {d.monster_type_key(targets[0])}
    for target in targets[1:]:
        visible[target.y][target.x] = 1
    stage56.reveal_rogue_monsters(current, player, visible)
    assert player.known_monsters == {
        d.monster_type_key(target) for target in targets
    }


def test_boss_party_vortex_is_local_and_boss_unlocks_separate_treasure():
    floors, player = stage6.build()
    current = floors[-1]
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "W"
    )
    party = stage56.monster_party(current, boss)
    vortex = next(e for e in party if e.tribe.char == "V")
    origin = (boss.x, boss.y)
    boss_zone = stage6.tile_at(origin)
    player.members.append(d.PartyMember(player.x, player.y, "Knight"))
    player.level = 10000
    player.x, player.y = boss.x, boss.y
    for floor_data in floors:
        floor_data.seen = [[1] * d.FIELD_WIDTH for _ in floor_data.field]
    far_floor_cell = max(
        (
            (x, y)
            for y, row in enumerate(current.field)
            for x, cell in enumerate(row)
            if cell == d.CHAR_FLOOR
        ),
        key=lambda point: abs(point[0] - vortex.x) + abs(point[1] - vortex.y),
    )
    floor_index = [len(floors) - 1]
    engine._step(
        (0, 0),
        floors,
        player,
        floor_index,
        [current.up],
        Counter(),
        1,
        stage_num=6,
    )
    assert player.boss_defeated and not player.stage_won
    assert current.seen[far_floor_cell[1]][far_floor_cell[0]] == 1
    assert any(
        current.seen[y][x] == 0
        for y, row in enumerate(current.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_FLOOR
    )
    assert floors[0].seen[1][1] == 1
    assert any(isinstance(e, d.Treasure) and e.unlocked for e in current.entities)
    chest = next(e for e in current.entities if isinstance(e, d.Treasure))
    assert stage6.tile_at((chest.x, chest.y)) != boss_zone
    assert all(
        e.active
        for e in current.entities
        if isinstance(e, d.Monster) and e.tribe.char == "M"
    )
    assert all(
        e.role != "Noble"
        for e in current.entities
        if isinstance(e, d.PartyMember)
    )
    player.treasure_collected = True
    assert player.stage_won


@pytest.mark.parametrize("attack_offset, won", [(-1, False), (0, True), (1, True)])
def test_stage5_boss_uses_combined_party_strength_without_required_members_or_items(
    attack_offset, won
):
    current, player = state()
    party = [monster(3, 2, "W"), monster(3, 3, "V"), monster(3, 4, "a", 2)]
    current.entities = party.copy()
    player.level = sum(d.monster_level(entity) for entity in party) + attack_offset
    step(current, player)
    assert player.boss_defeated == won
    assert all((entity not in current.entities) == won for entity in party)


@pytest.mark.parametrize("escort", d.STAGE5_BOSS_ESCORTS)
def test_generated_boss_retains_each_escort(monkeypatch, escort):
    engine.rand.set_seed(123)
    original_choice = stage6.rand.choice

    def choose(values):
        if values is d.STAGE5_BOSS_ESCORTS:
            return escort
        return original_choice(values)

    monkeypatch.setattr(stage6.rand, "choice", choose)
    floors, _ = stage6.build()
    current = floors[-1]
    boss = next(e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "W")
    party = stage56.monster_party(current, boss)
    assert len(party) == 3
    assert sum(e.tribe.char == "V" and e.empowered == 1 for e in party) == 1
    actual = next(e for e in party if e.tribe.char not in ("W", "V"))
    assert (actual.tribe.char, actual.empowered) == escort
    assert not stage56.special_monster(actual)


def test_treasure_is_optional_and_does_not_finish_stage():
    current, player = state()
    chest = d.Treasure(3, 2, "TF")
    chest.unlocked = True
    current.entities.append(chest)
    player.boss_defeated = True
    step(current, player)
    assert player.treasure_collected and not player.stage_won


def test_normalize_limits_and_protects_boss_pair():
    current, _ = state()
    current.entities = [monster(2, y, "a") for y in range(2, 9)]
    boss, vortex = monster(10, 2, "W"), monster(10, 3, "V", 2)
    current.entities += [boss, vortex, monster(10, 4, "c")]
    stage56.normalize_parties(current)
    assert boss in current.entities and vortex in current.entities
    for entity in current.entities:
        party = stage56.monster_party(current, entity)
        assert len(party) <= 5
        assert sum(stage56.special_monster(e) for e in party) <= 1


def test_followers_use_join_order_relative_to_direction():
    _, player = state(("Jester", "Knight"))
    player.facing = (0, -1)
    assert [(g.x, g.y, g.char) for g in display.member_glyphs(player)] == [
        (1, 3, "J"),
        (3, 3, "K"),
    ]
    player.facing = (1, 0)
    assert [(g.x, g.y) for g in display.member_glyphs(player)] == [(1, 1), (1, 3)]


def test_pit_falls_to_next_floor_with_members():
    current, player = state(("Healer", "Rogue"))
    lower, _ = state()
    current.field[2][3] = d.CHAR_COLLAPSE
    floor_index = [0]
    engine._step(
        (1, 0),
        [current, lower],
        player,
        floor_index,
        [(2, 2)],
        Counter(),
        1,
        stage_num=6,
    )
    assert floor_index[0] == 1
    assert (player.x, player.y) == (3, 2)
    assert [(e.x, e.y) for e in player.members] == [(3, 2), (3, 2)]


def test_climbing_pit_moves_checkpoint_after_leaving_pit():
    upper, player = state(("Dungeon Explorer",))
    lower, _ = state()
    upper.field[2][3] = d.CHAR_COLLAPSE
    lower.field[2][3] = d.CHAR_SCHOLAR_STAIRS_UP
    player.x, player.y = 3, 2
    floor_index = [1]
    checkpoint = [(3, 2)]

    engine._handle_floor_transition(lower, [upper, lower], player, floor_index, checkpoint)

    assert floor_index == [0]
    assert checkpoint == [(3, 2)]
    assert player.just_climbed_pit
    engine._step((1, 0), [upper, lower], player, floor_index, checkpoint,
                 Counter(), 1, stage_num=6)
    assert (player.x, player.y) == (4, 2)
    assert checkpoint == [(4, 2)]


def test_pit_requires_scholar_but_discovered_passage_remains_usable():
    upper, player = state(("Dungeon Explorer",))
    lower, _ = state()
    upper.field[2][3] = d.CHAR_COLLAPSE
    lower.field[2][3] = d.CHAR_SCHOLAR_STAIRS_UP
    lower.field[2][4] = d.CHAR_D_GATE
    player.x, player.y = 3, 2
    player.members.clear()
    floor_index = [1]
    checkpoint = [(2, 2)]

    assert engine._handle_floor_transition(
        lower, [upper, lower], player, floor_index, checkpoint
    ) is None
    assert floor_index == [1]
    engine._step((1, 0), [upper, lower], player, floor_index, checkpoint,
                 Counter(), 1, stage_num=6)
    assert (player.x, player.y) == (4, 2)


def test_explorer_climbs_pit_by_stepping_onto_marker():
    upper, player = state(("Dungeon Explorer",))
    lower, _ = state()
    upper.field[2][3] = d.CHAR_COLLAPSE
    lower.field[2][3] = d.CHAR_SCHOLAR_STAIRS_UP
    floor_index = [1]
    engine._step((1, 0), [upper, lower], player, floor_index, [(2, 2)],
                 Counter(), 1, stage_num=6)
    assert floor_index == [0]
    assert (player.x, player.y) == (3, 2)


def test_rogue_warning_stops_repeat_without_holding_movement(monkeypatch):
    current, player = state(("Rogue", "Healer"))
    current.field[2][3] = d.CHAR_COLLAPSE
    lower, _ = state()
    monkeypatch.setattr(stage6, "build", lambda *_: ([current, lower], player))

    class UI:
        shift_direction = False
        farthest_preview = False
        input_was_repeat = False

        def __init__(self):
            self.frames = []
            self.inputs = iter([False, None])
            self.stops = 0

        def draw_stage(self, **kwargs):
            self.frames.append((kwargs["turn"], player.lp, (player.x, player.y)))

        def input_direction(self):
            repeat = next(self.inputs, None)
            if repeat is None:
                return None
            self.input_was_repeat = repeat
            return (1, 0)

        def stop_movement_repeat(self):
            self.stops += 1

    ui = UI()
    engine.run_game(ui, "test", stage_num=6)
    assert ui.frames[:2] == [(0, 90, (2, 2)), (1, 89.5, (3, 2))]
    assert player.lp == pytest.approx(89.5)
    assert (player.x, player.y) == (3, 2)
    assert player.current_floor == 1
    assert ui.stops == 2


@pytest.mark.parametrize("roles", [(), ("Healer",)])
def test_loop_replay_preserves_lp_including_earlier_rewinds(monkeypatch, roles):
    from arlq.arlq import GameConfig
    from arlq.stage_replay import replay_to_operation
    from arlq.stage_types import ReplayContext

    def build(*_):
        current, player = state(roles)
        current.entities = [d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"])]
        return [current], player

    monkeypatch.setattr(stage6, "build", build)
    replay = ReplayContext(6, 123, GameConfig(), operations=[(1, 0), (1, 0)])
    replay.rewind_targets[2] = 1
    _, first, *_ = replay_to_operation(replay, 1)
    _, restored, *_ = replay_to_operation(replay, 2)
    assert first.lp == pytest.approx(90 - d.movement_lp_cost(first))
    assert restored.lp == pytest.approx(first.lp)
    assert (restored.x, restored.y) == (first.x, first.y)


@pytest.mark.parametrize("roles", [(), ("Healer",)])
def test_live_loop_rewind_preserves_target_lp(monkeypatch, roles):
    from types import SimpleNamespace

    frames = []

    def build(*_):
        current, player = state(roles)
        current.entities = [d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"])]
        return [current], player

    monkeypatch.setattr(stage6, "build", build)
    moves = iter([(1, 0), (1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: frames.append(kwargs["player"].lp),
        input_direction=moves.__next__,
        map_mode=False,
    )
    engine.run_game(ui, "test", stage_num=6)
    assert frames[:3] == pytest.approx([90, 90 - (1 / 2 if roles else 1), 90])


def test_candidate_glyph_is_known_on_first_sighting():
    _, player = state()
    candidate = d.PartyMember(3, 2, "Jester")
    assert get_torched(player, d.TORCH_RADIUS)[candidate.y][candidate.x]
    assert (
        display.revealed_entity_glyphs(candidate, set(), False, 100, None)[0].char
        == "J"
    )


def test_floor_connections_are_reachable_and_keep_members_on_transitions():
    floors, player = stage6.build()
    for upper, lower in zip(floors, floors[1:]):
        assert len(upper.down_stairs) == 2
        assert len(lower.up_stairs) == 2
        assert not upper.scholar_down_stairs
        assert not lower.scholar_up_stairs
        sections = {
            stage6.tile_at(point)
            for point in upper.down_stairs + upper.scholar_down_stairs
        }
        assert len(sections) == 2
    player.members = [
        d.PartyMember(player.x, player.y, "Dungeon Explorer"),
        d.PartyMember(player.x, player.y, "Noble"),
    ]
    stage56.set_scholar_stairs(floors, True)
    floor_index, checkpoint = [0], [floors[0].up]
    for index, current in enumerate(floors):
        entry = (player.x, player.y)
        pending, visited = [entry], {entry}
        while pending:
            x, y = pending.pop()
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in visited or not (
                    0 <= ny < len(current.field) and 0 <= nx < len(current.field[ny])
                ):
                    continue
                if current.field[ny][nx] == d.CHAR_WALL:
                    continue
                visited.add((nx, ny))
                pending.append((nx, ny))
        assert (
            engine._stage_draw_options(6, floors, index, False, True)["floor_label"]
            == f"{index + 1}/{len(floors)}"
        )
        if index == len(floors) - 1:
            break
        exits = (
            current.down_stairs[1:]
            + current.scholar_down_stairs
            + current.down_stairs[:1]
        )
        exit_point = next((point for point in exits if point in visited), None)
        assert exit_point is not None
        assert current.down == floors[index + 1].up
        assert current.field[current.down[1]][current.down[0]] == d.CHAR_STAIRS_DOWN
        assert current.field[exit_point[1]][exit_point[0]] == (
            d.CHAR_SCHOLAR_STAIRS_DOWN
            if exit_point in current.scholar_down_stairs
            else d.CHAR_STAIRS_DOWN
        )
        player.x, player.y = exit_point
        engine._handle_floor_transition(
            current, floors, player, floor_index, checkpoint
        )
        stage56.sync_members(player, exit_point, (1, 0))
        assert floor_index[0] == index + 1
        assert [member.role for member in player.members] == [
            "Dungeon Explorer",
            "Noble",
        ]
        assert all((e.x, e.y) == exit_point for e in player.members)


def test_parties_extend_vertically_and_accept_rank_two_and_three():
    current, _ = state()
    current.field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in current.field]
    for y in range(3, 8):
        current.field[y][7] = d.CHAR_FLOOR
    roster = [("a", 1), ("b", 2), ("c", 3), ("d", 1), ("e", 1)]
    stage6._place_party(current, roster)
    assert {(e.x, e.y) for e in current.entities} == {(7, y) for y in range(3, 8)}
    assert len(stage56.monster_party(current, current.entities[0])) == 5
    assert {e.empowered for e in current.entities} == {1, 2, 3}
    removed = current.entities.pop()
    assert stage56.respawn(current, "b", 1, 0, set()) == (removed.x, removed.y)


def test_horizontal_adjacency_does_not_join_monster_parties():
    current, _ = state()
    vertical = [monster(5, y, "a") for y in (3, 4, 5)]
    horizontal = monster(6, 4, "b")
    current.entities = [*vertical, horizontal]
    assert set(stage56.monster_party(current, vertical[1])) == set(vertical)
    assert stage56.monster_party(current, horizontal) == [horizontal]


def test_monster_placement_and_respawn_avoid_horizontal_neighbors():
    current, _ = state()
    current.field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in current.field]
    for x, y in ((5, 5), (6, 5), (8, 5)):
        current.field[y][x] = d.CHAR_FLOOR
    current.entities = [monster(5, 5, "a")]

    stage6._place_party(current, [("b", 1)])
    assert (current.entities[-1].x, current.entities[-1].y) == (8, 5)
    current.entities.pop()
    assert stage56.respawn(current, "b", 1, 0, set()) == (8, 5)


def test_open_points_exclude_unopened_collapse_footprint():
    current, _ = state()
    collapse = d.Collapse(5, 5)
    current.entities = [collapse]
    footprint = d.collapse_footprint((5, 5))

    assert not footprint.intersection(stage56._open_points(current))
    stage6._place_party(current, [("a", 1)])
    assert (current.entities[-1].x, current.entities[-1].y) not in footprint
    assert stage56.respawn(current, "b", 1, 0, set()) not in footprint


def test_normalize_separates_horizontal_neighbors():
    current, _ = state()
    current.entities = [monster(5, 5, "a"), monster(6, 5, "b")]

    stage56.normalize_parties(current)

    first, second = current.entities
    assert not (first.y == second.y and abs(first.x - second.x) == 1)


def test_detached_terminal_room_receives_two_distinct_random_monsters():
    current, _ = state()
    monsters = stage6._place_detached_room_monsters(
        current, ({(0, 0), (1, 0)}, {(2, 0)})
    )
    assert len(monsters) == 2
    assert {(monster.tribe.char, monster.empowered) for monster in monsters} <= {
        ("b", 1), ("b", 2), ("c", 1), ("A", 1)
    }
    assert len({(monster.x, monster.y) for monster in monsters}) == 2
    assert all(stage6.tile_at((monster.x, monster.y)) == (2, 0) for monster in monsters)
    assert current.entities == monsters


def test_seed_reproduces_layout_and_groups():
    def signature():
        floors, _ = stage6.build()
        return [
            (
                floor.field,
                [
                    (type(e).__name__, e.x, e.y, getattr(e, "empowered", None))
                    for e in floor.entities
                ],
            )
            for floor in floors
        ]

    engine.rand.set_seed(321)
    first = signature()
    engine.rand.set_seed(321)
    assert signature() == first
    engine.rand.set_seed(322)
    assert signature() != first


def test_deep_roster_counts_and_party_sizes_by_floor():
    def counts(char, rank):
        return [sum(count for ch, count, r in floor if ch == char and r == rank)
                for floor in d.STAGE5_ROSTER]

    assert counts("b", 1) == [3, 0, 0, 0]
    assert counts("b", 2) == [0, 2, 2, 2]
    assert counts("d", 1) == [3, 0, 0, 0]
    assert counts("d", 2) == [0, 3, 3, 2]
    assert counts("B", 1) == [2, 2, 2, 2]
    assert counts("f", 2) == [0, 1, 1, 1]
    assert counts("w", 2) == [0, 1, 1, 3]
    assert Counter(d.STAGE5_SUPPORT_POOLS[1]) == Counter({
        ("a", 1): 3, ("f", 1): 2, ("b", 1): 2,
        ("B", 1): 1, ("e", 1): 2,
    })
    assert all(Counter(pool) == Counter({
        ("a", 1): 2, ("e", 1): 2, ("b", 1): 1,
        ("B", 1): 1, ("w", 2): 1, ("k", 1): 1,
    }) for pool in d.STAGE5_SUPPORT_POOLS[2:])
    assert d.STAGE5_PARTY_SIZE_WEIGHTS == (
        (78, 21, 1, 0, 0), (60, 30, 10, 0, 0),
        (46, 30, 24, 0, 0), (45, 30, 25, 0, 0),
    )
    assert d.STAGE5_BOSS_ESCORTS == (("f", 2), ("k", 1), ("w", 1), ("w", 2))


def test_member_trial_has_fixed_ordered_layout():
    floors, player = stage5.build_member_trial()
    again, _ = stage5.build_member_trial()
    assert len(floors) == 2
    assert all(len(f.field) == d.FIELD_HEIGHT and all(
        len(row) == d.FIELD_WIDTH for row in f.field
    ) for f in floors)
    assert [f.field for f in floors] == [f.field for f in again]
    members = [e for e in floors[0].entities if isinstance(e, d.PartyMember)]
    assert [m.role for m in members] == [
        d.MEMBER_KNIGHT, d.MEMBER_ROGUE, d.MEMBER_GUARDIAN,
        d.MEMBER_HEALER, d.MEMBER_DUNGEON_EXPLORER, d.MEMBER_JESTER,
    ]
    assert (player.x, player.y) == floors[0].up
    for member in members:
        stage56.recruit(floors[0], player, member)
    assert [m.role for m in player.members] == [
        d.MEMBER_DUNGEON_EXPLORER, d.MEMBER_JESTER,
    ]


def test_member_trial_pit_lands_on_floor_without_return_stairs():
    floors, player = stage5.build_member_trial()
    upper, lower = floors
    collapse = next(e for e in upper.entities if isinstance(e, d.Collapse))
    pit = (collapse.x, collapse.y)
    fall_point = (collapse.x, collapse.y - 1)
    assert pit == (23, 3)
    assert not upper.scholar_down_stairs
    assert not lower.scholar_up_stairs
    assert fall_point in lower.collapse_landings
    assert lower.field[fall_point[1]][fall_point[0]] == d.CHAR_FLOOR
    player.x, player.y = pit
    floor, checkpoint = [0], [pit]
    engine._reveal_collapse_pits(floors, 0, collapse)
    engine._step((0, -1), floors, player, floor, checkpoint, Counter(), 1, stage_num=5)
    assert floor == [1]
    assert (player.x, player.y) == fall_point
    assert lower.field[fall_point[1]][fall_point[0]] == d.CHAR_FLOOR
    assert engine._handle_floor_transition(lower, floors, player, floor, checkpoint) is None
    assert floor == [1]

def test_member_trial_corridor_and_initial_combat():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    first = next(e for e in upper.entities if isinstance(e, d.Monster) and (e.x, e.y) == (5, 3))
    pair = next(e for e in upper.entities if isinstance(e, d.Monster) and (e.x, e.y) == (8, 3))
    knight_pair = next(e for e in upper.entities if isinstance(e, d.Monster) and (e.x, e.y) == (14, 3))
    assert d.current_player_attack(player, 5) >= d.monster_level(first)
    engine._resolve_party_contact(first, upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert d.current_player_attack(player, 5) < sum(
        d.monster_level(e) for e in stage56.monster_party(upper, pair)
    )
    knight = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_KNIGHT)
    stage56.recruit(upper, player, knight)
    assert d.current_player_attack(player, 5) >= sum(
        d.monster_level(e) for e in stage56.monster_party(upper, knight_pair)
    )

def test_member_trial_rooms_are_connected_by_short_doorways():
    floors, _ = stage5.build_member_trial()
    field = floors[0].field
    rows = stage5.STAGE5_MEMBER_TRIAL_MAP.splitlines()
    assert len(rows) == d.FIELD_HEIGHT
    for y, row in enumerate(rows):
        for x, glyph in enumerate(row):
            if glyph == "#":
                assert field[y][x] == d.CHAR_WALL
            elif glyph == "=":
                assert field[y][x] == d.CHAR_BARRIER
            elif glyph == ".":
                assert field[y][x] == d.CHAR_HIDDEN_D_GATE
            elif glyph == "?":
                assert field[y][x] == d.CHAR_FLOOR
                assert any(isinstance(e, d.Collapse) and (e.x, e.y) == (x, y)
                           for e in floors[0].entities)
            elif glyph == "v":
                assert field[y][x] == d.CHAR_STAIRS_DOWN
            else:
                assert field[y][x] != d.CHAR_WALL

def test_member_trial_can_bypass_first_pair_and_recruit_knight():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    player.x, player.y = 11, 3
    floor, checkpoint, queue = [0], [upper.up], Counter()
    engine._step((1, 0), floors, player, floor, checkpoint, queue, 1, stage_num=5)
    assert (player.x, player.y) == (12, 3)
    assert [member.role for member in player.members] == [d.MEMBER_KNIGHT]
    assert sum(isinstance(e, d.Monster) and e.tribe.char == "f" for e in upper.entities) == 5

def test_member_trial_rogue_targets_before_and_after_recruit():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    rogue = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_ROGUE)
    targets = [e for e in upper.entities if isinstance(e, d.Monster) and e.tribe.char in ("g", "X", "E")]
    assert {e.tribe.char for e in targets} == {"g", "X", "E"}
    assert any(e.tribe.char == "X" and e.x > rogue.x for e in targets)
    assert any(isinstance(e, d.Collapse) and (e.x, e.y) == (23, 3) for e in upper.entities)
    visible = [[1] * d.FIELD_WIDTH for _ in upper.field]
    stage56.reveal_rogue_monsters(upper, player, visible)
    assert not player.known_monsters.intersection({"g", "X"})
    stage56.recruit(upper, player, rogue)
    stage56.reveal_rogue_monsters(upper, player, visible)
    assert {"g", "X", "E"} <= player.known_monsters

def test_member_trial_practice_pit_has_ordinary_return_stairs():
    floors, player = stage5.build_member_trial()
    upper, lower = floors
    collapse = next(e for e in upper.entities if isinstance(e, d.Collapse))
    engine._reveal_collapse_pits(floors, 0, collapse)
    player.x, player.y = collapse.x - 1, collapse.y
    floor, checkpoint = [0], [upper.up]
    engine._step((1, 0), floors, player, floor, checkpoint, Counter(), 1, stage_num=5)
    assert floor == [1]
    for _ in range(6):
        engine._step((1, 0), floors, player, floor, checkpoint, Counter(), 2, stage_num=5)
    assert floor == [0] and (player.x, player.y) == (28, 3)
    assert lower.up_stairs == [(28, 3)] and upper.down_stairs == [(28, 3)]

def test_member_trial_healer_is_in_middle_row_on_right():
    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    healer = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_HEALER)
    guardian = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_GUARDIAN)
    assert (guardian.x, guardian.y) == (31, 3)
    assert (healer.x, healer.y) == (46, 10)
    assert all(upper.field[3][x] != d.CHAR_WALL for x in range(42, 46))
    assert sorted(e.x for e in upper.entities if isinstance(e, d.Monster)
                  and e.tribe.char == "b" and e.y == 10) == [40, 43]

def test_member_trial_rogue_pit_blocks_the_route_to_guardian():
    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    collapse = next(e for e in upper.entities if isinstance(e, d.Collapse))
    assert (collapse.x, collapse.y) == (23, 3)
    engine._reveal_collapse_pits(floors, 0, collapse)
    assert upper.field[3][23] == d.CHAR_FLOOR
    assert all(upper.field[y][23] == d.CHAR_COLLAPSE for y in (2, 4))

def test_member_trial_healer_corridor_is_long_and_empty():
    from collections import deque

    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    start, end = (45, 10), (8, 17)
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        (x, y), distance = queue.popleft()
        if (x, y) == end:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = (x + dx, y + dy)
            if (point not in seen and 0 <= point[0] < d.FIELD_WIDTH
                    and 0 <= point[1] < d.FIELD_HEIGHT
                    and upper.field[point[1]][point[0]] not in d.WALL_CHARS):
                seen.add(point)
                queue.append((point, distance + 1))
    else:
        pytest.fail("Healer area has no route to the Dungeon Explorer")
    assert distance >= 100

def test_member_trial_members_can_be_walked_around():
    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    occupied = {(e.x, e.y) for e in upper.entities}
    for member in (e for e in upper.entities if isinstance(e, d.PartyMember)):
        # The row below each member permits passing without contact.
        assert all(
            upper.field[member.y + 1][x] == d.CHAR_FLOOR
            and (x, member.y + 1) not in occupied
            for x in range(member.x - 1, member.x + 2)
        )


def test_member_trial_healer_exit_faces_explorer_before_jester():
    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    explorer = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_DUNGEON_EXPLORER)
    jester = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_JESTER)
    assert (explorer.x, explorer.y) == (8, 17)
    assert (jester.x, jester.y) == (26, 17)
    assert upper.field[14][1] == d.CHAR_FLOOR
    assert all(upper.field[15][x] == d.CHAR_FLOOR for x in range(1, 11))
    assert explorer.x < jester.x

def test_member_trial_jester_experience_comparison():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    jester = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_JESTER)
    apples = [e for e in upper.entities if isinstance(e, d.Monster) and e.tribe.char == "A"]
    before = [e for e in apples if e.x < jester.x]
    after = [e for e in apples if e.x > jester.x]
    assert len(before) == len(after) == 8
    assert {e.y for e in before} == {15, 17, 19}
    assert {e.y for e in after} == {15, 17, 19}
    player.members = [d.PartyMember(0, 0, d.MEMBER_HEALER), d.PartyMember(0, 0, d.MEMBER_DUNGEON_EXPLORER)]
    level = player.level
    engine._resolve_party_contact(before[0], upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert player.level - level == pytest.approx(10 / 1.5)
    assert sum(isinstance(e, d.Monster) and e.tribe.char == "A" and e.x > jester.x for e in upper.entities) == 8
    stage56.recruit(upper, player, jester)
    level = player.level
    engine._resolve_party_contact(after[0], upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert player.level - level == pytest.approx(12)


def test_member_trial_dragon_unlocks_final_chest_and_completes_stage():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    dragon = next(e for e in upper.entities if isinstance(e, d.Monster) and e.tribe.char == d.CHAR_FIRE_DRAKE)
    chest = next(e for e in upper.entities if isinstance(e, d.Treasure))
    assert dragon.x < chest.x and dragon.y == chest.y == 17
    assert chest.unlock_key == "TF" and not chest.unlocked
    player.level = 100
    engine._resolve_party_contact(dragon, upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert chest.unlocked and player.boss_defeated
    engine._resolve_contact(upper.entities.index(chest), upper, floors, player, [0], [upper.up], Counter(), stage_num=5)
    assert player.stage_won


def test_trial_dialogue_repeats_on_adjacent_moves_and_recruitment_is_separate():
    current, player = state()
    member = d.PartyMember(4, 2, d.MEMBER_KNIGHT)
    current.entities.append(member)
    floors, floor, checkpoint, queue = [current], [0], [(1, 1)], Counter()
    reasons = set()
    result = engine._step((1, 0), floors, player, floor, checkpoint, queue, 1,
                          stage_num=5, repeat_stop_reasons=reasons)
    assert result == (-2, stage5.TRIAL_MEMBER_LINES[d.MEMBER_KNIGHT])
    assert "member_dialogue" in reasons
    assert not player.members
    engine._step((-1, 0), floors, player, floor, checkpoint, queue, 2,
                 stage_num=5)
    result = engine._step((1, 0), floors, player, floor, checkpoint, queue, 3,
                          stage_num=5)
    assert result and result[0] == -2
    result = engine._step((1, 0), floors, player, floor, checkpoint, queue, 4,
                          stage_num=5)
    assert result and result[0] != -2
    assert member in player.members


def test_trial_dialogue_only_on_successful_stage_five_movement():
    current, player = state()
    current.entities.append(d.PartyMember(4, 2, d.MEMBER_ROGUE))
    floors, floor, checkpoint, queue = [current], [0], [(1, 1)], Counter()
    result = engine._step((1, 0), floors, player, floor, checkpoint, queue, 1,
                          stage_num=6)
    assert result is None or result[0] != -2
    current.field[2][2] = d.CHAR_WALL
    result = engine._step((-1, 0), floors, player, floor, checkpoint, queue, 2,
                          stage_num=5)
    assert result is None or result[0] != -2


def test_member_trial_right_margin_provides_respawn_floor():
    floors, _ = stage5.build_member_trial()
    for current, layout in zip(floors, (
        stage5.STAGE5_MEMBER_TRIAL_MAP, stage5.STAGE5_MEMBER_TRIAL_LOWER_MAP,
    )):
        width = max(map(len, layout.splitlines()))
        for row in current.field:
            assert row[width:width + 2] == [d.CHAR_WALL] * 2
            assert row[width + 2:] == [d.CHAR_FLOOR] * (d.FIELD_WIDTH - width - 2)
        assert any(x >= width + 2 for x, y in stage56._open_points(current))
