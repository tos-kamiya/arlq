"""Rules and generation checks for the five-floor Stage 5 dungeon."""

from collections import Counter, deque

import pytest

from arlq import defs as d
from arlq import display, stage5
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
        floors, _ = stage5.build()
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

    monkeypatch.setattr(stage5, '_neighbor_pairs', exhaustive_pairs)
    assert snapshot() == indexed


@pytest.mark.parametrize('known', [set(), {'a'}, {'a', 'D'}, {'a', 'D', 'M'}])
@pytest.mark.parametrize('attack', [1, 100])
def test_shared_party_tones_match_individual_glyphs(known, attack):
    entities = [monster(3, 3, 'a'), monster(3, 4, 'D'), monster(8, 8, 'M')]
    tones = display.monster_party_tones(entities, known, attack)
    for entity in entities:
        kwargs = {'stage_num': 5, 'party_entities': entities}
        expected = display.revealed_entity_glyphs(entity, known, False, attack, None, **kwargs)
        assert display.revealed_entity_glyphs(
            entity, known, False, attack, None, party_tones=tones, **kwargs
        ) == expected


def step(current, player, direction=(1, 0), checkpoint=(2, 2)):
    return engine._step(
        direction,
        [current],
        player,
        [0],
        [checkpoint],
        Counter(),
        deque(),
        1,
        stage_num=5,
    )


def test_playground_has_four_random_recruits_and_a_random_rank2_boss_party():
    floors, player = stage5.build()
    assert len(floors) == 5 and player.rescue_stage and player.treasure_stage
    for floor in floors:
        assert len(floor.room_components) == 2
        detached = next(component for component in floor.room_components if len(component) == 1)
        assert stage5.tile_at(floor.up) not in detached
        assert stage5.tile_at(floor.down) not in detached
        assert all(
            stage5.tile_at(point) not in detached
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
            and stage5.tile_at((entity.x, entity.y)) in detached
            for entity in floor.entities
        )
    assert stage5.tile_at((player.x, player.y)) not in next(
        component for component in floors[0].room_components if len(component) == 1
    )
    current = floors[-1]
    assert not any(
        isinstance(entity, d.Monster) and entity.tribe.char == "w"
        for entity in floors[1].entities
    )
    assert sum(
        isinstance(entity, d.Monster) and entity.tribe.char == "k"
        for entity in floors[1].entities
    ) == 2
    members = {
        e.role for f in floors for e in f.entities if isinstance(e, d.PartyMember)
    }
    assert len(members) == 4
    assert members <= {
        "Bard",
        "Healer",
        "Rogue",
        "Knight",
        "Dangeon Scholar",
        "Guardian",
    }
    assert not any(
        isinstance(e, d.PartyMember)
        for floor in floors[2:]
        for e in floor.entities
    )
    assert {
        e.origin_floor
        for floor in floors[:2]
        for e in floor.entities
        if isinstance(e, d.PartyMember)
    } <= {0, 1}
    assert sum(
        isinstance(e, d.PartyMember)
        for floor in floors[:2]
        for e in floor.entities
    ) == 4
    assert not any(
        isinstance(e, d.Monster) and e.tribe.is_elf for f in floors for e in f.entities
    )
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "W"
    )
    party = stage5.monster_party(current, boss)
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
    escorts = [e for e in party if e is not boss]
    assert len(escorts) <= 2
    assert all(
        e.empowered == 2 and e.tribe.char not in {"V", "W", "g"} for e in escorts
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
    ] == [1, 3, 3, 3, 3]
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
    player.known_member_floors = {"Bard": 1, "Rogue": 2}
    assert [
        label for label, _ in display.stage5_member_progress_marks(player)
    ] == ["B", "H", "R", "K", "D", "G"]


def test_departed_member_respawns_near_departure_after_long_delay():
    current, player = state(("Bard", "Healer"))
    lower, _ = state()
    player.joined_members.update(("Bard", "Healer"))
    departed = player.members[0]
    recruit = d.PartyMember(3, 2, "Rogue", origin_floor=1)
    current.entities.append(recruit)

    stage5.recruit(
        current,
        player,
        recruit,
        recycle_departed=True,
        floors=[lower, current],
        floor_index=1,
        turn=40,
        respawn_delay=d.STAGE5_MEMBER_RESPAWN_TURNS,
    )

    assert not any(
        isinstance(entity, d.PartyMember) and entity.role == "Bard"
        for entity in current.entities
    )
    assert player.member_respawns["Bard"] == (
        1,
        departed.x,
        departed.y,
        40 + d.STAGE5_MEMBER_RESPAWN_TURNS,
    )
    assert display.stage5_member_progress_marks(player)[0] == ("B2", True)

    stage5.process_member_respawns(
        [lower, current], player, 39 + d.STAGE5_MEMBER_RESPAWN_TURNS
    )
    assert "Bard" in player.member_respawns
    stage5.process_member_respawns(
        [lower, current], player, 40 + d.STAGE5_MEMBER_RESPAWN_TURNS
    )
    respawned = next(
        entity
        for entity in current.entities
        if isinstance(entity, d.PartyMember) and entity.role == "Bard"
    )
    assert abs(respawned.x - departed.x) + abs(respawned.y - departed.y) <= 1
    assert "Bard" not in player.member_respawns


def test_fifo_noble_lock_and_companion_slot_are_independent():
    current, player = state()
    companion = d.Companion(2, 2, d.CHAR_TO_TRIBE["n"])
    player.companion = companion
    for role in ("Bard", "Healer", "Noble", "Knight", "Rogue"):
        recruit = d.PartyMember(3, 2, role)
        current.entities.append(recruit)
        step(current, player)
        player.x, player.y = 2, 2
    assert [e.role for e in player.members] == ["Noble", "Knight"]
    assert sorted(
        e.role for e in current.entities if isinstance(e, d.PartyMember)
    ) == ["Rogue"]
    assert set(player.member_respawns) == {"Bard", "Healer"}
    assert player.companion is companion


@pytest.mark.parametrize(
    "roles, gain",
    [
        ((), 2),
        (("Bard",), 3),
        (("Knight",), 0.5),
        (("Bard", "Knight"), 1),
        (("Healer", "Rogue"), 2 / 3),
        (("Guardian",), 1),
    ],
)
def test_group_rewards_are_shared_then_adjusted_by_members(roles, gain):
    current, player = state(roles, lp=10)
    current.entities = [monster(3, 2, "b"), monster(3, 3, "a")]
    feed = max(e.tribe.feed for e in current.entities)
    step(current, player)
    assert current.entities == []
    assert player.level == 100 + gain
    assert player.lp == min(d.LP_MAX, 10 + feed)


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
    current, player = state(("Knight", "Dangeon Scholar"), level=100.5)
    assert d.current_player_attack(player) == pytest.approx(201)
    assert d.current_player_attack(player, 5) == pytest.approx(301.5)
    player.item = d.ITEM_SWORD_X1_5
    assert d.current_player_attack(player) == pytest.approx(301.5)
    assert d.current_player_attack(player, 5) == pytest.approx(452.25)
    assert barrier_lp_damage(player) == 30
    assert d.caltrop_lp_damage(player) == 3
    current.field[2][3] = d.CHAR_CALTROP
    step(current, player)
    assert player.lp == 87
    assert "LVL: 100" in display.status_prefix(player, 5, 0)
    assert "ATK: 452" in display.status_prefix(player, 5, 0)


def test_guardian_reduces_hazard_damage_independently_of_movement_cost():
    _, player = state(("Guardian",))
    assert barrier_lp_damage(player) == 15
    assert d.caltrop_lp_damage(player) == 1
    assert d.movement_lp_cost(player) == 1

    player.members.append(d.PartyMember(player.x, player.y, "Healer"))
    assert barrier_lp_damage(player) == 15
    assert d.caltrop_lp_damage(player) == 1
    assert d.movement_lp_cost(player) == pytest.approx(1 / 3)


def test_rogue_detects_shooting_lane_and_respects_blockers():
    current, player = state(("Rogue",))
    marksman = monster(7, 3, "k")
    current.entities.append(marksman)
    assert stage5.rogue_danger(current, player, (3, 3)) == "-"
    assert ((3, 3), "-") in marksman.warning_arrow_marks
    current.field[3][5] = d.CHAR_WALL
    assert stage5.rogue_danger(current, player, (3, 3)) is None
    current.field[3][5] = d.CHAR_FLOOR
    current.entities.append(d.Companion(5, 3, d.CHAR_TO_TRIBE["n"]))
    assert stage5.rogue_danger(current, player, (3, 3)) is None


def test_rogue_mimic_identification_requires_adjacency_and_activation():
    current, player = state(("Rogue",))
    mimic = monster(4, 2, "M")
    current.entities.append(mimic)
    stage5.reveal_mimics(current, player)
    assert "M" not in player.known_monsters
    mimic.x = 3
    mimic.active = False
    stage5.reveal_mimics(current, player)
    assert "M" not in player.known_monsters
    mimic.active = True
    stage5.reveal_mimics(current, player)
    assert "M" in player.known_monsters


def test_qualified_boss_win_rearranges_final_floor_and_unlocks_separate_treasure():
    floors, player = stage5.build()
    current = floors[-1]
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "W"
    )
    origin = (boss.x, boss.y)
    boss_zone = stage5.tile_at(origin)
    player.members.append(d.PartyMember(player.x, player.y, "Knight"))
    player.level = 10000
    player.x, player.y = boss.x, boss.y
    for floor_data in floors:
        floor_data.seen = [[1] * d.FIELD_WIDTH for _ in floor_data.field]
    floor_index = [len(floors) - 1]
    engine._step(
        (0, 0),
        floors,
        player,
        floor_index,
        [current.up],
        Counter(),
        deque(),
        1,
        stage_num=5,
    )
    assert player.boss_defeated and not player.stage_won
    assert current.seen[0][0] == 1  # Wall locations remain explored.
    assert current.seen[current.up[1]][current.up[0]] == 1
    assert any(
        current.seen[y][x] == 0
        for y, row in enumerate(current.field)
        for x, cell in enumerate(row)
        if cell == d.CHAR_FLOOR
    )
    assert floors[0].seen[1][1] == 1
    assert any(isinstance(e, d.Treasure) and e.unlocked for e in current.entities)
    chest = next(e for e in current.entities if isinstance(e, d.Treasure))
    assert stage5.tile_at((chest.x, chest.y)) != boss_zone
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


def test_stage5_boss_requires_knight_or_sword_from_chimera():
    current, player = state(level=10000)
    boss = monster(3, 2, "W")
    current.entities = [boss]
    step(current, player)
    assert not player.boss_defeated
    assert boss in current.entities

    player.x, player.y = 2, 2
    player.item = d.ITEM_SWORD_X1_5
    player.item_taken_from = "a"
    step(current, player)
    assert not player.boss_defeated

    player.x, player.y = 2, 2
    player.item = d.ITEM_SWORD_X1_5
    player.item_taken_from = "c"
    step(current, player)
    assert player.boss_defeated


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
    stage5.normalize_parties(current)
    assert boss in current.entities and vortex in current.entities
    for entity in current.entities:
        party = stage5.monster_party(current, entity)
        assert len(party) <= 5
        assert sum(stage5.special_monster(e) for e in party) <= 1


def test_followers_use_join_order_relative_to_direction():
    _, player = state(("Bard", "Knight"))
    player.facing = (0, -1)
    assert [(g.x, g.y, g.char) for g in display.member_glyphs(player)] == [
        (1, 3, "B"),
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
        deque(),
        1,
        stage_num=5,
    )
    assert floor_index[0] == 1
    assert (player.x, player.y) == (3, 2)
    assert [(e.x, e.y) for e in player.members] == [(3, 2), (3, 2)]


def test_rogue_warning_stops_repeat_and_requires_fresh_press_without_lp_cost(
    monkeypatch,
):
    current, player = state(("Rogue", "Healer"))
    current.field[2][3] = d.CHAR_COLLAPSE
    lower, _ = state()
    monkeypatch.setattr(stage5, "build", lambda *_: ([current, lower], player))

    class UI:
        shift_direction = False
        farthest_preview = False
        input_was_repeat = False

        def __init__(self):
            self.frames = []
            self.inputs = iter([False, True, False])
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
    engine.run_game(ui, "test", stage_num=5)
    assert ui.frames[:3] == [(0, 90, (2, 2))] * 3
    assert player.lp == pytest.approx(89 + 2 / 3)
    assert (player.x, player.y) == (3, 2)
    assert ui.stops >= 2


@pytest.mark.parametrize("roles", [(), ("Healer",)])
def test_loop_replay_preserves_lp_including_earlier_rewinds(monkeypatch, roles):
    from arlq.arlq import GameConfig
    from arlq.stage_replay import replay_to_operation
    from arlq.stage_types import ReplayContext

    def build(*_):
        current, player = state(roles)
        current.entities = [d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"])]
        return [current], player

    monkeypatch.setattr(stage5, "build", build)
    replay = ReplayContext(5, 123, GameConfig(), operations=[(1, 0), (1, 0)])
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

    monkeypatch.setattr(stage5, "build", build)
    moves = iter([(1, 0), (1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: frames.append(kwargs["player"].lp),
        input_direction=moves.__next__,
        map_mode=False,
    )
    engine.run_game(ui, "test", stage_num=5)
    assert frames[:3] == pytest.approx([90, 90 - (1 / 3 if roles else 1), 90])


def test_candidate_glyph_is_known_on_first_sighting():
    _, player = state()
    candidate = d.PartyMember(3, 2, "Bard")
    assert get_torched(player, d.TORCH_RADIUS)[candidate.y][candidate.x]
    assert (
        display.revealed_entity_glyphs(candidate, set(), False, 100, None)[0].char
        == "B"
    )


def test_floor_connections_are_reachable_and_keep_members_on_transitions():
    floors, player = stage5.build()
    for upper, lower in zip(floors, floors[1:]):
        assert len(upper.down_stairs) == 2
        assert len(lower.up_stairs) == 2
        assert len(upper.scholar_down_stairs) == 1
        assert len(lower.scholar_up_stairs) == 1
        sections = {
            stage5.tile_at(point)
            for point in upper.down_stairs + upper.scholar_down_stairs
        }
        assert len(sections) == 3
    player.members = [
        d.PartyMember(player.x, player.y, "Dangeon Scholar"),
        d.PartyMember(player.x, player.y, "Noble"),
    ]
    stage5.set_scholar_stairs(floors, True)
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
            engine._stage_draw_options(5, floors, index, False, True)["floor_label"]
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
        stage5.sync_members(player, exit_point, (1, 0))
        assert floor_index[0] == index + 1
        assert [member.role for member in player.members] == [
            "Dangeon Scholar",
            "Noble",
        ]
        assert all((e.x, e.y) == exit_point for e in player.members)


def test_parties_extend_vertically_and_accept_rank_two_and_three():
    current, _ = state()
    current.field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in current.field]
    for y in range(3, 8):
        current.field[y][7] = d.CHAR_FLOOR
    roster = [("a", 1), ("b", 2), ("c", 3), ("d", 1), ("e", 1)]
    stage5._place_party(current, roster)
    assert {(e.x, e.y) for e in current.entities} == {(7, y) for y in range(3, 8)}
    assert len(stage5.monster_party(current, current.entities[0])) == 5
    assert {e.empowered for e in current.entities} == {1, 2, 3}
    removed = current.entities.pop()
    assert stage5.respawn(current, "b", 1, 0, set()) == (removed.x, removed.y)


def test_horizontal_adjacency_does_not_join_monster_parties():
    current, _ = state()
    vertical = [monster(5, y, "a") for y in (3, 4, 5)]
    horizontal = monster(6, 4, "b")
    current.entities = [*vertical, horizontal]
    assert set(stage5.monster_party(current, vertical[1])) == set(vertical)
    assert stage5.monster_party(current, horizontal) == [horizontal]


def test_detached_terminal_room_receives_one_random_monster():
    current, _ = state()
    monster = stage5._place_detached_room_monster(
        current, ({(0, 0), (1, 0)}, {(2, 0)})
    )
    assert monster.tribe.char in {"b", "c", "A"}
    assert stage5.tile_at((monster.x, monster.y)) == (2, 0)
    assert current.entities == [monster]


def test_seed_reproduces_layout_and_groups():
    def signature():
        floors, _ = stage5.build()
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


def test_deep_roster_preserves_population_and_scales_party_sizes_by_floor():
    deep_rosters = d.STAGE5_ROSTER[1:]
    actual_counts = Counter(
        (char, rank)
        for roster in deep_rosters
        for char, count, rank in roster
        for _ in range(count)
    )
    expected_counts = Counter(
        {
            (char, rank): count * 3
            for char, count, rank in d.STAGE5_DEEP_ROSTER
        }
    )
    expected_counts[("w", 1)] -= 1
    expected_counts[("w", 2)] += 2
    expected_counts[("A", 1)] += 4
    assert actual_counts == expected_counts
    current_fixed_total = sum(
        count for roster in d.STAGE5_ROSTER for _, count, _ in roster
    ) + d.STAGE5_FLOORS
    previous_fixed_total = (
        sum(count for _, count, _ in d.STAGE5_ROSTER[0])
        - 1
        + 3 * sum(count for _, count, _ in d.STAGE5_DEEP_ROSTER)
        + 2
        + 4
    )
    assert current_fixed_total == previous_fixed_total + 5
    assert [
        sum(count for char, count, _ in roster if char == "A")
        for roster in d.STAGE5_ROSTER
    ] == [3, 2, 3, 2, 3]
    assert [sum(count for _, count, _ in roster) for roster in deep_rosters] == [
        34, 34, 34, 35
    ]
    assert [
        sum(count for char, count, rank in roster if char == "w" and rank == 2)
        for roster in deep_rosters
    ] == [0, 0, 0, 2]
    assert "w" not in {char for char, _ in d.STAGE5_SUPPORT_POOLS[1]}
    assert "k" not in {char for char, _ in d.STAGE5_SUPPORT_POOLS[1]}
    assert d.STAGE5_SUPPORT_POOLS[2:] == (d.STAGE5_SUPPORT_POOLS[2],) * 3
    floor2_support_weights = Counter(char for char, _ in d.STAGE5_SUPPORT_POOLS[1])
    assert floor2_support_weights == Counter(
        {"a": 3, "f": 2, "b": 3, "e": 2}
    )
    support_weights = Counter(char for char, _ in d.STAGE5_SUPPORT_POOLS[2])
    assert support_weights == Counter({"a": 2, "f": 2, "b": 2, "e": 2, "w": 1, "k": 1})
    assert d.STAGE5_PARTY_SIZE_WEIGHTS[1:] == (
        (50, 30, 15, 4, 1),
        (40, 30, 20, 8, 2),
        (34, 30, 24, 10, 2),
        (33, 30, 22, 12, 3),
    )
    assert all(sum(weights) == 100 for weights in d.STAGE5_PARTY_SIZE_WEIGHTS)
    assert next(entry[1] for entry in d.STAGE5_ROSTER[0] if entry[0] == "c") == 5
    assert sum(
        count for roster in deep_rosters for char, count, _ in roster if char == "c"
    ) == 18
    assert sum(
        count for roster in deep_rosters for char, count, _ in roster if char == "C"
    ) == 6
