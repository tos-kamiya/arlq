"""Behavior and generation checks for Stages 5 and 6."""

from collections import Counter

import pytest

from arlq import defs as d
from arlq import display, i18n, stage5, stage56, stage6
from arlq import game_engine as engine
from arlq.arlq import barrier_lp_damage, get_torched, iterate_ellipse_points
from arlq.stage_types import Floor


@pytest.fixture(autouse=True)
def fixed_rearrangement_seed():
    state = engine.rand.getstate()
    engine.rand.set_seed(123)
    yield
    engine.rand.setstate(state)


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


def boss_route(floor):
    return {(x, y) for y, row in enumerate(floor.decor)
            for x, value in enumerate(row) if value == d.DECOR_BOSS_ROUTE}


def test_boss_route_avoids_pits_and_hidden_passages_and_uses_stairs(monkeypatch):
    def corridor():
        field = [list("#######"), list("#     #"), list("#     #"), list("#######")]
        return Floor(field, [], [[0] * 7 for _ in field], (1, 1), (5, 1), None)

    upper, lower = corridor(), corridor()
    upper.down_stairs = [(5, 1)]
    lower.up_stairs = [(5, 1)]
    upper.entities.append(d.Collapse(2, 1))
    upper.field[1][3] = d.CHAR_HIDDEN_D_GATE
    routes = []
    monkeypatch.setattr(stage6, "_balance_route_parties", lambda floors, route: routes.append(route))
    stage6._balance_boss_route([upper, lower], (1, 1), (4, 1))

    assert (0, (2, 1)) not in routes[0]
    assert (0, (3, 1)) not in routes[0]
    assert (0, (3, 2)) in routes[0]
    assert (1, (5, 1)) in routes[0]
    assert not boss_route(upper)
    assert not boss_route(lower)


def test_generated_stage6_has_no_boss_route_markers():
    floors, _ = stage6.build()
    assert all(not boss_route(floor) for floor in floors)


def test_stage6_retries_missing_boss_route_without_resetting_random_state(monkeypatch):
    original = stage6._balance_boss_route
    states = []

    def fail_once(floors, start, boss):
        states.append(engine.rand.getstate())
        if len(states) == 1:
            raise stage6._BossRouteNotFound()
        return original(floors, start, boss)

    monkeypatch.setattr(stage6, "_balance_boss_route", fail_once)
    floors, _ = stage6.build()
    assert len(floors) == d.STAGE6_FLOORS
    assert len(states) == 2
    assert states[0] != states[1]


def test_stage6_retry_limit_and_other_errors(monkeypatch):
    monkeypatch.setattr(stage6, "MAX_STAGE_GENERATION_RETRIES", 2)
    attempts = []

    def fail(config):
        attempts.append(config)
        raise stage6._BossRouteNotFound()

    monkeypatch.setattr(stage6, "_build_once", fail)
    with pytest.raises(RuntimeError, match="could not generate a Stage 6 route.*after 2 retries"):
        stage6.build()
    assert len(attempts) == 3

    def unexpected(config):
        raise RuntimeError("unrelated failure")

    monkeypatch.setattr(stage6, "_build_once", unexpected)
    with pytest.raises(RuntimeError, match="unrelated failure"):
        stage6.build()


def test_stage6_floors_have_no_loop_fairies():
    floors, _ = stage6.build()

    for floor in floors:
        fairies = [entity.tribe.char for entity in floor.entities
                      if isinstance(entity, d.Fairy)]
        assert len(fairies) == 3
        assert len(set(fairies)) == 3
        assert set(fairies) <= {"l", "n", "o", "p"}


@pytest.mark.parametrize('rogue', [False, True])
@pytest.mark.parametrize('explorer', [False, True])
def test_world_discoveries_depend_on_joined_members(rogue, explorer):
    roles = []
    if rogue:
        roles.append(d.MEMBER_ROGUE)
    if explorer:
        roles.append(d.MEMBER_DUNGEON_EXPLORER)
    current, player = state(roles)
    current.entities = [monster(3, 2, 'X')]
    current.field[3][2] = d.CHAR_HIDDEN_D_GATE

    engine.observe_world([current], player, 0, d.TORCH_RADIUS)

    assert ('X' in player.known_monsters) is rogue
    expected = d.CHAR_D_GATE if explorer else d.CHAR_HIDDEN_D_GATE
    assert current.field[3][2] == expected


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
            engine.rand.getstate(),
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
        kwargs = {'party_entities': entities}
        expected = display.revealed_entity_glyphs(entity, known, False, attack, None, **kwargs)
        assert display.revealed_entity_glyphs(
            entity, known, False, attack, None, party_tones=tones, **kwargs
        ) == expected


@pytest.mark.parametrize(
    ('mode', 'known', 'expected'),
    [
        ('individual', {'a', 'D'}, 'blue'),
        ('entities', {'a', 'D'}, 'red'),
        ('entities', {'a'}, 'yellow'),
        ('tones', {'a', 'D'}, 'red'),
        ('empty_tones', {'a', 'D'}, 'red'),
    ],
)
def test_glyph_party_inputs_control_strength_coloring(mode, known, expected):
    first = monster(3, 3, 'a')
    entities = [first, monster(3, 4, 'D')]
    attack = d.monster_level(first)
    kwargs = {}
    if mode in ('entities', 'empty_tones'):
        kwargs['party_entities'] = entities
    if mode == 'tones':
        kwargs['party_tones'] = display.monster_party_tones(entities, known, attack)
    elif mode == 'empty_tones':
        kwargs['party_tones'] = {}

    glyph = display.revealed_entity_glyphs(
        first, known, False, attack, None, **kwargs,
    )[0]
    assert glyph.tone == expected


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


def test_playground_has_four_random_recruits_and_a_boss_party():
    floors, player = stage6.build()
    assert len(floors) == 3 and player.rescue_stage and player.treasure_stage
    for floor_index, floor in enumerate(floors):
        if floor_index == len(floors) - 1:
            assert len(floor.room_components) == 1
            continue
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
    assert stage6.tile_at((player.x, player.y)) not in next(
        component for component in floors[0].room_components if len(component) == 1
    )
    current = floors[-1]
    members = {
        e.role for f in floors for e in f.entities if isinstance(e, d.PartyMember)
    }
    assert len(members) == 4
    assert members <= set(d.RECRUITABLE_MEMBER_ROLES)
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
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F"
    )
    party = stage56.monster_party(current, boss)
    assert (boss.tribe.char, boss.empowered) == ("F", 2)
    assert sum(
        isinstance(e, d.Monster) and e.tribe.char == "F"
        for floor in floors
        for e in floor.entities
    ) == 1
    assert not any(
        isinstance(e, d.Monster) and e.tribe.char == "F" and e.empowered != 2
        for floor in floors
        for e in floor.entities
    )
    vortex = next(e for e in party if e.tribe.char == "V")
    assert vortex.empowered == 2
    escorts = [e for e in party if e not in (boss, vortex)]
    assert ("k", 1) in [(e.tribe.char, e.empowered) for e in escorts]
    assert len(party) <= d.STAGE6_MONSTER_PARTY_LIMIT
    mimics = [
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "M"
    ]
    assert len(mimics) == 1
    assert not mimics[0].active and mimics[0].mimic_boss_char == d.CHAR_DUNGEON_CORE
    assert not any(
        isinstance(entity, d.Monster)
        and entity.tribe.char == "g"
        and entity.empowered > 1
        for floor in floors[:2]
        for entity in floor.entities
    )
    assert len([e for e in current.entities if isinstance(e, d.Treasure)]) == 1


def test_stage5_member_progress_shows_candidates_before_they_depart():
    _, player = state()
    player.known_member_floors = {"Jester": 1, "Rogue": 2}
    assert [
        label for label, _ in display.stage5_member_progress_marks(player)
    ] == ["J1", "H", "R2", "K", "D", "G"]
    player.stage6_candidates = True
    assert display.stage5_member_progress_marks(player)[-2:] == [("Y", False), ("S", False)]


def test_fairy_seer_identifies_fairies_in_explored_areas_on_every_floor():
    upper, player = state((d.MEMBER_FAIRY_SEER,))
    lower, _ = state()
    known = d.Fairy(20, 10, d.CHAR_TO_FAIRY_TRIBE["n"])
    later = d.Fairy(21, 10, d.CHAR_TO_FAIRY_TRIBE["o"])
    other_floor = d.Fairy(20, 10, d.CHAR_TO_FAIRY_TRIBE["n"])
    upper.entities.extend([known, later])
    lower.entities.append(other_floor)
    upper.seen[10][20] = lower.seen[10][20] = 1

    engine.observe_world([upper, lower], player, 0, d.TORCH_RADIUS)
    assert known.revealed and other_floor.revealed
    assert not later.revealed

    upper.seen[10][21] = 1
    engine.observe_world([upper, lower], player, 0, d.TORCH_RADIUS)
    assert later.revealed

    player.members.clear()
    newcomer = d.Fairy(21, 10, d.CHAR_TO_FAIRY_TRIBE["o"])
    lower.entities.append(newcomer)
    lower.seen[10][21] = 1
    engine.observe_world([upper, lower], player, 1, d.TORCH_RADIUS)
    assert known.revealed and later.revealed and other_floor.revealed
    assert not newcomer.revealed


def test_stage5_second_member_does_not_reappear():
    current, player = state(("Jester", "Healer"))
    recruit = d.PartyMember(3, 2, "Rogue")
    current.entities.append(recruit)

    step(current, player, stage_num=5)

    assert [member.role for member in player.members] == ["Jester", "Rogue"]
    assert not any(
        isinstance(entity, d.PartyMember) and entity.role == "Healer"
        for entity in current.entities
    )


def test_stage6_candidates_start_near_first_floor_bridgehead():
    for seed in range(5):
        engine.rand.set_seed(seed)
        floors, player = stage6.build()
        first = floors[0]
        x, y = first.bridgehead
        for dx, char in enumerate("/\\"):
            assert first.decor[y][x + dx] == d.DECOR_BRIDGEHEAD_PREFIX + char
        assert all(floor.bridgehead is None for floor in floors[1:])
        members = [(index, e) for index, floor in enumerate(floors)
                   for e in floor.entities if isinstance(e, d.PartyMember)]
        assert len(members) == 4
        assert len({member.role for _, member in members}) == 4
        for index, member in members:
            assert index == member.origin_floor == 0
            assert (member.x, member.y) in stage6._reachable_floor_points(first, first.up)
            assert (member.x, member.y) != (player.x, player.y)
            assert abs(member.x - x) + abs(member.y - y) <= 7


def test_stage6_leaving_first_floor_scatters_waiting_candidates(monkeypatch):
    upper, player = state()
    lower, _ = state()
    upper.down = lower.up = (3, 2)
    upper.field[2][3] = d.CHAR_STAIRS_DOWN
    lower.field[2][3] = d.CHAR_STAIRS_UP
    candidate = d.PartyMember(10, 10, d.MEMBER_FAIRY_SEER, origin_floor=0)
    upper.entities.append(candidate)
    player.known_member_floors[candidate.role] = 1
    floor = [0]
    monkeypatch.setattr(stage6.rand, "choice", lambda choices: choices[-1])

    engine._step((1, 0), [upper, lower], player, floor, [(2, 2)], Counter(), 1, stage_num=6)

    assert floor == [1]
    assert candidate in lower.entities and candidate not in upper.entities
    assert candidate.origin_floor == 1
    assert (candidate.x, candidate.y) != (player.x, player.y)
    assert candidate.role not in player.known_member_floors


def test_stage6_falling_from_first_floor_scatters_members_on_all_floors(monkeypatch):
    upper, player = state(roles=(d.MEMBER_KNIGHT,))
    lower, _ = state()
    upper.field[2][3] = d.CHAR_COLLAPSE
    lower.field[2][3] = d.CHAR_PIT_LANDING
    first = d.PartyMember(10, 10, d.MEMBER_HEALER, origin_floor=0)
    second = d.PartyMember(11, 10, d.MEMBER_ROGUE, origin_floor=1)
    upper.entities.append(first)
    lower.entities.append(second)
    player.known_member_floors.update({first.role: 1, second.role: 2})
    monkeypatch.setattr(stage6.rand, "choice", lambda choices: choices[0])
    floor_index = [0]

    engine._step((1, 0), [upper, lower], player, floor_index, [(2, 2)],
                 Counter(), 1, stage_num=6)

    assert floor_index == [1]
    assert first in upper.entities and second in upper.entities
    assert first.origin_floor == second.origin_floor == 0
    assert first.role not in player.known_member_floors
    assert second.role not in player.known_member_floors
    assert [member.role for member in player.members] == [d.MEMBER_KNIGHT]
    assert (first.x, first.y) != (second.x, second.y)


def test_stage6_scatter_when_route_differs_from_previous(monkeypatch):
    upper, player = state()
    lower, _ = state()
    upper.down = (3, 2)
    lower.up = (8, 8)
    upper.field[2][3] = d.CHAR_STAIRS_DOWN
    lower.field[8][8] = d.CHAR_STAIRS_UP
    floor_index = [0]
    calls = []
    monkeypatch.setattr(stage6, "scatter_waiting_members",
                        lambda floors, player, index: calls.append(index))

    engine._step((1, 0), [upper, lower], player, floor_index, [(2, 2)], Counter(), 1, stage_num=6)
    assert floor_index == [1] and calls == [1]
    player.x, player.y = 7, 8
    engine._step((1, 0), [upper, lower], player, floor_index, [(7, 8)], Counter(), 2, stage_num=6)
    assert floor_index == [0] and calls == [1]
    player.x, player.y = 2, 2
    engine._step((1, 0), [upper, lower], player, floor_index, [(2, 2)], Counter(), 3, stage_num=6)
    assert floor_index == [1] and calls == [1]
    player.x, player.y = 12, 12
    stage6.scatter_members_on_new_route([upper, lower], player, 0, (4, 2), 1)
    assert calls == [1, 1]
    player.x, player.y = 3, 2
    stage6.scatter_members_on_new_route([upper, lower], player, 1, (8, 8), 0)
    assert calls == [1, 1, 0]
    player.x, player.y = 8, 8
    stage6.scatter_members_on_new_route([upper, lower], player, 0, (3, 2), 1)
    assert calls == [1, 1, 0]


def test_stage6_new_route_scatter_including_pit_climb(monkeypatch):
    upper, player = state(roles=(d.MEMBER_DUNGEON_EXPLORER,))
    lower, _ = state()
    upper.field[5][5] = d.CHAR_COLLAPSE
    lower.field[5][5] = d.CHAR_PIT_LANDING
    player.x, player.y = 5, 6
    floor_index = [1]
    calls = []
    monkeypatch.setattr(stage6, "scatter_waiting_members",
                        lambda floors, player, index: calls.append(index))
    engine._step((0, -1), [upper, lower], player, floor_index, [(5, 6)], Counter(), 1, stage_num=6)
    assert floor_index == [0] and calls == [0]
    player.x, player.y = 5, 4
    engine._step((0, 1), [upper, lower], player, floor_index, [(5, 4)], Counter(), 2, stage_num=6)
    assert floor_index == [1] and calls == [0]


def test_stage6_departed_members_return_to_first_floor_bridgehead():
    floors, player = stage6.build()
    member = next(e for e in floors[0].entities if isinstance(e, d.PartyMember))
    stage56.recruit(floors[0], player, member)
    player.members.remove(member)
    stage6.relocate_candidates(floors, player, [member], player_floor=1)

    assert member in floors[0].entities and member.origin_floor == 0
    assert member.role not in player.known_member_floors
    x, y = floors[0].bridgehead
    assert abs(member.x - x) + abs(member.y - y) <= 7


def test_stage5_replaces_second_member_without_respawning_them():
    current, player = state(("Jester", "Healer"))
    fairy = d.Fairy(2, 2, d.CHAR_TO_TRIBE["n"])
    player.fairy = fairy
    recruit = d.PartyMember(3, 2, "Rogue")
    current.entities.append(recruit)
    player.joined_members.update(("Jester", "Healer"))

    step(current, player, stage_num=5)

    assert [member.role for member in player.members] == ["Jester", "Rogue"]
    assert recruit not in current.entities
    assert player.joined_members == {"Jester", "Healer", "Rogue"}
    assert not any(
        isinstance(entity, d.PartyMember) and entity.role == "Healer"
        for entity in current.entities
    )
    assert ("H-", False) in display.stage5_member_progress_marks(player)
    assert player.fairy is fairy


@pytest.mark.parametrize(
    "roles, gain",
    [
        ((), 2),
        (("Jester",), 3),
        (("Knight",), 2),
        (("Jester", "Knight"), 3),
        (("Healer", "Rogue"), 2),
        (("Guardian",), 2),
        ((d.MEMBER_YAWNING_CAT,), 2),
    ],
)
@pytest.mark.parametrize("stage_num", [5, 6])
def test_group_rewards_go_to_player_with_jester_multiplier(roles, gain, stage_num):
    current, player = state(roles, lp=10)
    current.entities = [monster(3, 2, "b"), monster(3, 3, "a")]
    feed = max(e.tribe.feed for e in current.entities)
    step(current, player, stage_num=stage_num)
    assert not any(isinstance(entity, d.Monster) for entity in current.entities)
    assert player.level == 100 + gain
    assert player.lp == min(d.LP_MAX, 10 + feed)



@pytest.mark.parametrize("stage_num", [3, 5, 6])
@pytest.mark.parametrize("rank", [1, 2])
def test_flame_cobra_grants_five_experience(stage_num, rank):
    current, player = state(level=100)
    current.entities = [monster(3, 2, "f", rank)]
    step(current, player, stage_num=stage_num)
    assert player.level == 105


@pytest.mark.parametrize("stage_num", [3, 5, 6])
@pytest.mark.parametrize("char", ["w", "W"])
@pytest.mark.parametrize("rank", [1, 2, 3])
def test_wyrms_grant_five_experience(stage_num, char, rank):
    current, player = state(level=2000)
    current.entities = [monster(3, 2, char, rank)]
    step(current, player, stage_num=stage_num)
    assert player.level == 2005


@pytest.mark.parametrize("stage_num", [3, 5, 6])
def test_marksman_grants_three_experience(stage_num):
    current, player = state(level=100)
    current.entities = [monster(3, 2, "k")]
    step(current, player, stage_num=stage_num)
    assert player.level == 103


def test_knight_level_is_fixed_and_jester_leaves_at_100():
    current, player = state(("Jester", "Knight"), lp=10)
    knight = player.members[1]
    assert knight.level == 40
    current.entities = [monster(3, 2, "b"), monster(3, 3, "a")]
    step(current, player)
    assert player.level == pytest.approx(103)
    assert knight.level == 40
    assert not d.has_member(player, d.MEMBER_JESTER)
    assert d.current_player_attack(player) == pytest.approx(player.level + knight.level)


@pytest.mark.parametrize("stage_num", [5, 6])
def test_jester_leaves_when_experience_crosses_level_100(stage_num):
    current, player = state(("Jester",), level=98)
    current.entities = [monster(3, 2, "a")]
    step(current, player, stage_num=stage_num)
    assert player.level == pytest.approx(99.5)
    assert d.has_member(player, d.MEMBER_JESTER)
    current.entities = [monster(4, 2, "a")]
    step(current, player, stage_num=stage_num)
    assert player.level == pytest.approx(101)
    assert not d.has_member(player, d.MEMBER_JESTER)
    assert any(isinstance(e, d.PartyMember) and e.role == d.MEMBER_JESTER for e in current.entities)
    assert player.jester_retired


@pytest.mark.parametrize("level, returns", [(99, True), (100, False), (101, False)])
def test_jester_reappears_only_below_departure_level(level, returns):
    floors, player = stage6.build()
    player.level = level
    jester = d.PartyMember(0, 0, d.MEMBER_JESTER, origin_floor=0)
    player.known_member_floors[d.MEMBER_JESTER] = 1
    stage6.relocate_candidates(floors, player, [jester], player_floor=1)
    assert (jester in floors[0].entities) is returns
    assert d.MEMBER_JESTER not in player.known_member_floors


def test_recruiting_jester_at_level_100_is_refused():
    current, player = state(level=100)
    jester = d.PartyMember(3, 2, d.MEMBER_JESTER, origin_floor=0)
    current.entities.append(jester)
    step(current, player)
    assert jester not in player.members and jester in current.entities


@pytest.mark.parametrize("stage_num", [5, 6])
def test_retired_jester_refuses_after_level_loss_without_displacing_members(stage_num):
    current, player = state(("Healer", "Rogue"), level=100)
    jester = d.PartyMember(3, 2, d.MEMBER_JESTER, origin_floor=0)
    current.entities.append(jester)
    step(current, player, stage_num=stage_num)
    assert player.jester_retired
    assert [m.role for m in player.members] == ["Healer", "Rogue"]
    assert jester in current.entities
    player.level = 50
    player.x, player.y = 2, 2
    step(current, player, stage_num=stage_num)
    assert [m.role for m in player.members] == ["Healer", "Rogue"]
    assert jester in current.entities


def test_stage6_new_member_replaces_second_and_relocates_them(monkeypatch):
    current, player = state(("Healer", "Rogue"), level=20)
    first, second = player.members
    recruit = d.PartyMember(3, 2, "Knight")
    current.entities.append(recruit)
    relocated = []
    monkeypatch.setattr(stage6, "relocate_candidates",
                        lambda floors, player, candidates, index: relocated.extend(candidates))
    step(current, player)
    assert player.members == [first, recruit]
    assert relocated == [second]


def test_group_strength_defeat_preserves_party_and_healer_penalty():
    current, player = state(("Healer", "Rogue"), level=10)
    enemies = [monster(3, 2, "b", 2), monster(3, 3, "w")]
    current.entities = enemies.copy()
    before = player.members.copy()
    step(current, player, checkpoint=(1, 1))
    assert current.entities == enemies
    assert player.level == 10 and player.lp == 87
    assert player.members == before
    assert all((member.x, member.y) == (1, 1) for member in player.members)


def test_group_keeps_unique_item_even_when_contacting_ordinary_member():
    current, player = state()
    current.entities = [monster(3, 2, "a"), monster(3, 3, "c")]
    step(current, player)
    assert player.item == d.ITEM_SWORD_X1_5


@pytest.mark.parametrize("stage_num", [5, 6])
@pytest.mark.parametrize("chars", [("c", "m"), ("m", "c")])
def test_group_sword_is_not_overwritten_by_spores(stage_num, chars):
    current, player = state()
    current.entities = [monster(3, 2, chars[0]), monster(3, 3, chars[1])]
    step(current, player, stage_num=stage_num)
    assert player.item == d.ITEM_SWORD_X1_5
    assert player.item_taken_from == "c"
    assert d.current_player_attack(player) == pytest.approx(player.level * 1.5)


def test_fractional_attack_hazards_and_status():
    current, player = state(("Knight", "Dungeon Explorer"), level=100.5)
    assert d.current_player_attack(player) == pytest.approx(140.5)
    player.item = d.ITEM_SWORD_X1_5
    assert d.current_player_attack(player) == pytest.approx(190.75)
    assert barrier_lp_damage(player) == 30
    current.field[2][3] = d.CHAR_CALTROP
    step(current, player)
    assert player.lp == 87
    assert "LVL: 100" in display.status_prefix(player, 5, 0)
    assert "ATK: 190" in display.status_prefix(player, 5, 0)


def test_guardian_reduces_hazard_damage_independently_of_movement_cost():
    _, player = state(("Guardian",))
    assert barrier_lp_damage(player) == 5
    assert d.movement_lp_cost(player) == 1

    player.members.append(d.PartyMember(player.x, player.y, "Healer"))
    assert barrier_lp_damage(player) == 5
    assert d.movement_lp_cost(player) == pytest.approx(3 / 4)

    player.elf_stage_flags |= d.ELF_STAGE_H_FLAG
    assert barrier_lp_damage(player) == 0
    player.item = d.ITEM_SWORD_CURSED
    assert barrier_lp_damage(player) == 5


@pytest.mark.parametrize("cell, hazard_cost", [(d.CHAR_CALTROP, 3), (d.CHAR_BARRIER, 5)])
def test_guardian_and_healer_terrain_costs(cell, hazard_cost):
    current, player = state(("Guardian", "Healer"))
    current.field[2][3] = cell
    step(current, player)
    assert player.lp == pytest.approx(90 - hazard_cost)


def test_guardian_pegasus_barrier_landing_costs_five_lp():
    current, player = state(("Guardian",))
    player.fairy = d.Fairy(2, 2, d.CHAR_TO_FAIRY_TRIBE["p"])
    current.field[2][3] = d.CHAR_WALL
    current.field[2][2 + d.PEGASUS_STEP_X] = d.CHAR_BARRIER
    step(current, player)
    assert player.x == 2 + d.PEGASUS_STEP_X
    assert player.lp == 85


def test_rogue_does_not_preannounce_marksman_shooting_lane():
    current, player = state(("Rogue",))
    marksman = monster(7, 3, "k")
    current.entities.append(marksman)
    assert stage56.rogue_danger(current, (3, 3)) is None
    current.field[3][5] = d.CHAR_WALL
    assert stage56.rogue_danger(current, (3, 3)) is None


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

    assert player.known_monsters == {"a", d.monster_type_key(targets[0])}
    for target in targets[1:]:
        visible[target.y][target.x] = 1
    stage56.reveal_rogue_monsters(current, player, visible)
    assert player.known_monsters == {"a"} | {
        d.monster_type_key(target) for target in targets
    }


def test_boss_party_vortex_is_local_and_boss_unlocks_separate_treasure():
    floors, player = stage6.build()
    current = floors[-1]
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F"
    )
    party = stage56.monster_party(current, boss)
    vortex = next(e for e in party if e.tribe.char == "V")
    origin = (boss.x, boss.y)
    boss_zone = stage6.tile_at(origin)
    chest = next(e for e in current.entities if isinstance(e, d.Treasure))
    assert stage6.tile_at((chest.x, chest.y)) != boss_zone
    core = next(e for e in current.entities if isinstance(e, d.Monster)
                and e.tribe.char == d.CHAR_DUNGEON_CORE)
    core_position = (core.x, core.y)
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
    assert core.active and (core.x, core.y) == core_position
    assert not any(isinstance(e, d.Treasure) and e.unlocked for e in current.entities)
    assert not any(
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








@pytest.mark.parametrize("escort", d.STAGE6_BOSS_ESCORTS)
@pytest.mark.parametrize("seed", [0, 2, 53, 123])
def test_initial_boss_party_remains_in_its_room(monkeypatch, seed, escort):
    engine.rand.set_seed(seed)
    original_choice = stage6.rand.choice
    monkeypatch.setattr(
        stage6.rand, "choice",
        lambda values: escort if values is d.STAGE6_BOSS_ESCORTS else original_choice(values),
    )
    original_boss = stage6._place_initial_boss_party
    boss_positions = []

    def place_boss(current):
        assert not current.entities
        party, entrance = original_boss(current)
        boss_positions.extend((entity, entity.x, entity.y) for entity in party)
        return party, entrance

    monkeypatch.setattr(stage6, "_place_initial_boss_party", place_boss)
    floors, _ = stage6.build()
    current = floors[-1]
    boss = next(e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F")
    party = stage56.monster_party(current, boss)
    assert {"F", "V"} <= {e.tribe.char for e in party}
    assert next(e for e in party if e.tribe.char == "F").rank == 2
    assert next(e for e in party if e.tribe.char == "V").rank == 1
    assert len(party) <= d.STAGE6_MONSTER_PARTY_LIMIT
    assert all((entity.x, entity.y) == (x, y) for entity, x, y in boss_positions)
    room = stage6.tile_at((boss.x, boss.y))
    assert all(stage6.tile_at((entity.x, entity.y)) == room for entity, _, _ in boss_positions)
    chest = next(e for e in current.entities if isinstance(e, d.Treasure))
    assert stage6.tile_at((chest.x, chest.y)) != room



@pytest.mark.parametrize("escort", d.STAGE6_BOSS_ESCORTS)
@pytest.mark.parametrize("seed", [0, 53, 123])
def test_final_floor_random_barriers_stay_near_boss(monkeypatch, seed, escort):
    engine.rand.set_seed(seed)
    original_choice = stage6.rand.choice
    monkeypatch.setattr(
        stage6.rand, "choice",
        lambda values: escort if values is d.STAGE6_BOSS_ESCORTS else original_choice(values),
    )
    floors, _ = stage6.build()
    current = floors[-1]
    boss = next(e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F")
    horizontal_radius = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
    vortex_radius = round(horizontal_radius / d.FOV_WIDTH_EXPANSION_RATIO)
    radius = round(vortex_radius * 1.5)
    allowed = set(iterate_ellipse_points(boss.x, boss.y, radius, d.FOV_WIDTH_EXPANSION_RATIO))
    assert current.persistent_barriers
    assert current.persistent_barriers <= allowed
    assert all(current.field[y][x] == d.CHAR_BARRIER for x, y in current.persistent_barriers)
    for index in (1,):
        assert len(floors[index].persistent_barriers) == d.STAGE6_HAZARD_COUNTS[index][1]


def test_treasure_is_optional_and_does_not_finish_stage():
    current, player = state()
    chest = d.Treasure(3, 2, "TF")
    chest.unlocked = True
    current.entities.append(chest)
    player.boss_defeated = True
    step(current, player)
    assert player.treasure_collected and not player.stage_won


def test_normalize_limits_and_protects_boss_pair():
    current, player = state()
    current.entities = [monster(2, y, "a") for y in range(2, 9)]
    boss, vortex = monster(10, 2, "W"), monster(10, 3, "V")
    current.entities += [boss, vortex, monster(10, 4, "c")]
    stage56.normalize_parties(current)
    assert boss in current.entities and vortex in current.entities
    for entity in current.entities:
        party = stage56.monster_party(current, entity)
        assert len(party) <= 5
        assert sum(stage56.special_monster(e) for e in party) <= 1


def test_followers_trace_player_path_in_join_order():
    _, player = state(("Jester", "Knight"))
    player.x, player.y = 3, 2
    stage56.sync_members(player, (2, 2), (1, 0))
    player.x, player.y = 3, 3
    stage56.sync_members(player, (3, 2), (0, 1))
    assert [(m.x, m.y) for m in player.members] == [(3, 2), (2, 2)]
    assert {(g.x, g.y, g.char) for g in display.member_glyphs(player)} == {
        (3, 2, "J"), (2, 2, "K"),
    }
    stage56.sync_members(player, (3, 3), (0, 0))
    assert [(m.x, m.y) for m in player.members] == [(3, 2), (2, 2)]
    player.x, player.y = 3, 2
    stage56.sync_members(player, (3, 3), (0, -1))
    assert [(m.x, m.y) for m in player.members] == [(3, 3), (3, 2)]
    assert [(g.x, g.y, g.char) for g in display.member_glyphs(player)] == [(3, 3, "J")]


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


def test_generated_pit_landings_are_floor_for_reported_seed():
    engine.rand.set_seed(49011)
    floors, _ = stage6.build()
    for upper, lower in zip(floors, floors[1:]):
        for collapse in (e for e in upper.entities if isinstance(e, d.Collapse)):
            for x, y in d.collapse_footprint((collapse.x, collapse.y)):
                if upper.field[y][x] == d.CHAR_FLOOR:
                    assert lower.field[y][x] == d.CHAR_PIT_LANDING


def test_collapse_placement_rejects_wall_below_reachable_pit():
    upper, _ = state()
    lower, _ = state()
    lower.field[4][5] = d.CHAR_WALL
    assert not d.collapse_placement_cells_valid((5, 5), upper.field, lower.field)
    upper.field[4][5] = d.CHAR_WALL
    assert d.collapse_placement_cells_valid((5, 5), upper.field, lower.field)


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


def test_pit_and_discovered_passage_require_explorer():
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
    assert (player.x, player.y) == (3, 2)
    player.members.append(d.PartyMember(3, 2, d.MEMBER_DUNGEON_EXPLORER))
    engine._step((1, 0), [upper, lower], player, floor_index, checkpoint,
                 Counter(), 1, stage_num=6)
    assert (player.x, player.y) == (4, 2)


@pytest.mark.parametrize('explorer', [False, True])
def test_discovered_passage_reachability_and_repeat_follow_explorer(explorer):
    current, player = state((d.MEMBER_DUNGEON_EXPLORER,) if explorer else ())
    current.field = [list('#####'), list('# . #'), list('#####')]
    current.seen = [[1] * 5 for _ in range(3)]
    player.x, player.y = 1, 1
    reachable = engine.reachable_known_cells(
        current.field, current.seen, current.seen, [], player,
        phase_walls={(2, 1)}, terminal_targets={(3, 1)},
    )
    assert ((3, 1) in reachable) is explorer
    assert engine._should_stop_movement_repeat((1, 0), current, player) is not explorer


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
    assert ui.frames[0] == (0, 90, (2, 2))
    assert ui.frames[1][0::2] == (1, (3, 2))
    assert ui.frames[1][1] == pytest.approx(90 - 3 / 4)
    assert player.lp == pytest.approx(90 - 3 / 4)
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
        current.entities = [d.Fairy(4, 2, d.CHAR_TO_FAIRY_TRIBE["l"])]
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
        current.entities = [d.Fairy(4, 2, d.CHAR_TO_FAIRY_TRIBE["l"])]
        return [current], player

    monkeypatch.setattr(stage6, "build", build)
    moves = iter([(1, 0), (1, 0), None])
    ui = SimpleNamespace(
        draw_stage=lambda **kwargs: frames.append(kwargs["player"].lp),
        input_direction=moves.__next__,
        map_mode=False,
    )
    engine.run_game(ui, "test", stage_num=6)
    assert frames[:3] == pytest.approx([90, 90 - (3 / 4 if roles else 1), 90])


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
        assert len(upper.down_stairs) in (1, 2)
        assert len(lower.up_stairs) == len(upper.down_stairs)
        assert not upper.scholar_down_stairs
        assert not lower.scholar_up_stairs
        sections = {
            stage6.tile_at(point)
            for point in upper.down_stairs + upper.scholar_down_stairs
        }
        assert len(sections) == len(upper.down_stairs)
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
        stage56.sync_members(player, exit_point, (1, 0), reset=True)
        assert floor_index[0] == index + 1
        assert [member.role for member in player.members] == [
            "Dungeon Explorer",
            "Noble",
        ]
        assert all((e.x, e.y) == (player.x, player.y) for e in player.members)


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


def test_respawn_glow_follows_monster_moved_by_party_normalization():
    current, _ = state()
    first, second = monster(5, 5, "a"), monster(6, 5, "b")
    current.entities = [first, second]
    current.respawn_glows = {(6, 5): d.RESPAWN_GLOW_TURNS}

    stage56.normalize_parties(current)

    assert (second.x, second.y) != (6, 5)
    assert current.respawn_glows == {(second.x, second.y): d.RESPAWN_GLOW_TURNS}


def test_respawn_glow_removed_when_party_normalization_removes_monster(monkeypatch):
    current, player = state()
    current.entities = [monster(5, 5, "a")]

    def spawn(current, char, rank, origin_floor, avoid, floor_index=0):
        current.entities.append(monster(5, 6, char, rank))
        return (5, 6)

    monkeypatch.setattr(stage56, "respawn", spawn)
    monkeypatch.setattr(d, "MEMBER_STAGE_MONSTER_PARTY_LIMIT", 1)
    engine._process_respawn_queue(
        [current], player, [0], Counter({(0, "b"): 1}), 0, stage_num=5
    )

    assert len(current.entities) == 1
    assert current.respawn_glows == {}
    assert engine.respawn_glow_cells(current) == set()


def test_detached_terminal_room_receives_two_distinct_random_monsters():
    current, _ = state()
    monsters = stage6._place_detached_room_monsters(
        current, ({(0, 0), (1, 0)}, {(2, 0)})
    )
    assert len(monsters) == 2
    assert {(monster.tribe.char, monster.empowered) for monster in monsters} <= {
        ("b", 1), ("b", 2), ("c", 1), ("f", 1), ("A", 1)
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




def test_stage6_spawn_roster_scales_by_floor():
    assert len(d.STAGE6_ROSTER) == d.STAGE6_FLOORS == 4
    assert [(count, rank) for char, count, rank, _ in d.STAGE6_ROSTER[1] if char == "B"] == [(1, 2)]
    for roster in d.STAGE6_ROSTER:
        assert sum(count for char, count, rank, _ in roster if char == "c" and rank == 1) == 1
        assert any(char == "a" and rank == 2 for char, _, rank, _ in roster)
    assert any(char == "b" and rank == 3 for char, _, rank, _ in d.STAGE6_ROSTER[-1])
    assert any(char == "a" and rank == 3 for char, _, rank, _ in d.STAGE6_ROSTER[-1])
    assert d.STAGE6_EXTRA_CORRIDORS == 0


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
        d.MEMBER_KNIGHT, d.MEMBER_JESTER,
    ]


def test_member_trial_pit_lands_on_floor_without_return_stairs():
    floors, player = stage5.build_member_trial()
    upper, lower = floors
    collapse = next(e for e in upper.entities if isinstance(e, d.Collapse))
    pit = (collapse.x, collapse.y)
    fall_point = (collapse.x, collapse.y - 1)
    assert pit == (27, 3)
    assert not upper.scholar_down_stairs
    assert not lower.scholar_up_stairs
    assert fall_point in lower.collapse_landings
    assert lower.field[fall_point[1]][fall_point[0]] == d.CHAR_PIT_LANDING
    player.x, player.y = pit
    floor, checkpoint = [0], [pit]
    engine._reveal_collapse_pits(floors, 0, collapse)
    engine._step((0, -1), floors, player, floor, checkpoint, Counter(), 1, stage_num=5)
    assert floor == [1]
    assert (player.x, player.y) == fall_point
    assert lower.field[fall_point[1]][fall_point[0]] == d.CHAR_PIT_LANDING
    assert engine._handle_floor_transition(lower, floors, player, floor, checkpoint) is None
    assert floor == [1]

def test_member_trial_corridor_and_initial_combat():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    first = next(e for e in upper.entities if isinstance(e, d.Monster) and (e.x, e.y) == (7, 3))
    pair = next(e for e in upper.entities if isinstance(e, d.Monster) and (e.x, e.y) == (10, 3))
    knight_pair = next(e for e in upper.entities if isinstance(e, d.Monster) and (e.x, e.y) == (16, 3))
    assert d.current_player_attack(player) >= d.monster_level(first)
    engine._resolve_party_contact(first, upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert d.current_player_attack(player) < sum(
        d.monster_level(e) for e in stage56.monster_party(upper, pair)
    )
    knight = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_KNIGHT)
    stage56.recruit(upper, player, knight)
    assert d.current_player_attack(player) >= sum(
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
    player.x, player.y = 13, 3
    floor, checkpoint, queue = [0], [upper.up], Counter()
    engine._step((1, 0), floors, player, floor, checkpoint, queue, 1, stage_num=5)
    assert (player.x, player.y) == (14, 3)
    assert [member.role for member in player.members] == [d.MEMBER_KNIGHT]
    assert sum(isinstance(e, d.Monster) and e.tribe.char == "f" for e in upper.entities) == 5

def test_member_trial_rogue_targets_before_and_after_recruit():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    rogue = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_ROGUE)
    targets = [e for e in upper.entities if isinstance(e, d.Monster) and e.tribe.char in ("g", "X", "E")]
    assert {e.tribe.char for e in targets} == {"g", "X", "E"}
    assert any(e.tribe.char == "X" and e.x < rogue.x for e in targets)
    assert any(isinstance(e, d.Collapse) and (e.x, e.y) == (27, 3) for e in upper.entities)
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
    assert floor == [0] and (player.x, player.y) == (33, 3)
    assert lower.up_stairs == [(32, 3)] and upper.down_stairs == [(33, 3)]

def test_member_trial_healer_is_in_middle_row_on_right():
    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    healer = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_HEALER)
    guardian = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_GUARDIAN)
    assert (guardian.x, guardian.y) == (36, 3)
    assert (healer.x, healer.y) == (47, 10)
    assert all(upper.field[3][x] != d.CHAR_WALL for x in range(44, 48))
    assert sorted(e.x for e in upper.entities if isinstance(e, d.Monster)
                  and e.tribe.char == "b" and e.y == 10) == [41, 44]

def test_member_trial_rogue_pit_blocks_the_route_to_guardian():
    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    collapse = next(e for e in upper.entities if isinstance(e, d.Collapse))
    assert (collapse.x, collapse.y) == (27, 3)
    engine._reveal_collapse_pits(floors, 0, collapse)
    assert upper.field[3][27] == d.CHAR_FLOOR
    assert all(upper.field[y][27] == d.CHAR_COLLAPSE for y in (2, 4))

def test_member_trial_healer_corridor_is_long_and_empty():
    from collections import deque

    floors, _ = stage5.build_member_trial()
    upper = floors[0]
    start, end = (47, 10), (10, 17)
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
    assert (explorer.x, explorer.y) == (10, 17)
    assert (jester.x, jester.y) == (30, 17)
    assert upper.field[14][3] == d.CHAR_FLOOR
    assert all(upper.field[15][x] == d.CHAR_FLOOR for x in range(3, 13))
    assert explorer.x < jester.x

def test_member_trial_jester_experience_comparison():
    floors, player = stage5.build_member_trial()
    upper = floors[0]
    jester = next(e for e in upper.entities if isinstance(e, d.PartyMember) and e.role == d.MEMBER_JESTER)
    apples = [e for e in upper.entities if isinstance(e, d.Monster) and e.tribe.char == "A"]
    before = [e for e in apples if e.x < jester.x]
    after = [e for e in apples if e.x > jester.x]
    assert len(before) == len(after) == 9
    assert {e.y for e in before} == {15, 17, 19}
    assert {e.y for e in after} == {15, 17, 19}
    player.members = [d.PartyMember(0, 0, d.MEMBER_HEALER), d.PartyMember(0, 0, d.MEMBER_DUNGEON_EXPLORER)]
    level = player.level
    engine._resolve_party_contact(before[0], upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert player.level - level == pytest.approx(10)
    assert sum(isinstance(e, d.Monster) and e.tribe.char == "A" and e.x > jester.x for e in upper.entities) == 9
    stage56.recruit(upper, player, jester)
    level = player.level
    engine._resolve_party_contact(after[0], upper, floors, player, [0], [upper.up], Counter(), None, 5)
    assert player.level - level == pytest.approx(15)


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


@pytest.mark.parametrize('language', ['en', 'ja'])
def test_trial_dialogue_repeats_on_adjacent_moves_and_recruitment_is_separate(monkeypatch, language):
    monkeypatch.setattr(i18n, '_lang', language)
    current, player = state()
    member = d.PartyMember(4, 2, d.MEMBER_KNIGHT)
    current.entities.append(member)
    floors, floor, checkpoint, queue = [current], [0], [(1, 1)], Counter()
    reasons = set()
    result = engine._step((1, 0), floors, player, floor, checkpoint, queue, 1,
                          stage_num=5, repeat_stop_reasons=reasons)
    assert result == (-2, i18n.t(stage5.TRIAL_MEMBER_LINES[d.MEMBER_KNIGHT]))
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


def test_wyrm_barrier_does_not_appear_under_player_after_wall_break():
    current, player = state()
    player.item = d.ITEM_SWORD_X1_5
    player.item_uses = 1
    current.field[2][3] = d.CHAR_WALL
    current.entities.append(monster(4, 2, "w"))

    step(current, player)

    assert (player.x, player.y) == (3, 2)
    assert current.field[2][3] == d.CHAR_FLOOR

    step(current, player, direction=(-1, 0))

    assert (player.x, player.y) == (2, 2)
    assert (3, 2) in current.broken_walls
    assert current.field[2][3] == d.CHAR_FLOOR


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


@pytest.mark.parametrize("exempt", [False, True])
def test_monster_adjacency_exceptions_are_explicit_floor_state(exempt):
    current, _ = state()
    current.entities = [monster(5, 5, "X"), monster(6, 5, "X")]
    original_positions = [(entity.x, entity.y) for entity in current.entities]
    if exempt:
        current.adjacent_monster_exemptions.update(original_positions)

    stage56.normalize_parties(current)

    positions = [(entity.x, entity.y) for entity in current.entities]
    assert (positions == original_positions) is exempt


def test_dread_wyrm_barriers_become_persistent_when_defeated():
    current, player = state()
    dread_wyrm = monster(6, 6, "W")
    wyrm = monster(12, 6, "w")
    current.entities = [dread_wyrm, wyrm]

    stage56.normalize_parties(current)
    stage56.initialize_monster_barriers(current)

    dread_cells = set(stage56.barrier_cells(current, dread_wyrm))
    wyrm_cells = set(stage56.barrier_cells(current, wyrm))
    assert dread_cells.isdisjoint(current.persistent_barriers)
    assert all(current.field[y][x] == d.CHAR_BARRIER for x, y in dread_cells)
    assert wyrm_cells.isdisjoint(current.persistent_barriers)
    assert all(current.field[y][x] == d.CHAR_BARRIER for x, y in wyrm_cells)
    current.entities.remove(dread_wyrm)

    engine._defeat_monster(
        dread_wyrm, current, player, [0], [(2, 2)], Counter(), stage_num=6
    )

    assert dread_cells <= current.persistent_barriers
    assert wyrm_cells.isdisjoint(current.persistent_barriers)


@pytest.mark.parametrize("floor_index", [0, 1])
def test_tutorial_maps_support_chimera_marker(monkeypatch, floor_index):
    map_name = (
        "STAGE5_MEMBER_TRIAL_MAP" if floor_index == 0
        else "STAGE5_MEMBER_TRIAL_LOWER_MAP"
    )
    rows = getattr(stage5, map_name).splitlines()
    row = list(rows[1])
    row[20] = "c"
    rows[1] = "".join(row)
    monkeypatch.setattr(stage5, map_name, "\n".join(rows))

    floors, _ = stage5.build_member_trial()

    current = floors[floor_index]
    assert current.field[1][20] == d.CHAR_FLOOR
    assert any(
        isinstance(entity, d.Monster)
        and (entity.x, entity.y) == (20, 1)
        and entity.tribe.char == "c"
        for entity in current.entities
    )


def test_tutorial_adjacency_exceptions_follow_monster_markers(monkeypatch):
    rows = stage5.STAGE5_MEMBER_TRIAL_MAP.splitlines()
    row = list(rows[1])
    row[43], row[42] = " ", "X"
    rows[1] = "".join(row)
    monkeypatch.setattr(stage5, "STAGE5_MEMBER_TRIAL_MAP", "\n".join(rows))

    floors, _ = stage5.build_member_trial()

    assert (42, 1) in floors[0].adjacent_monster_exemptions
    assert (43, 1) not in floors[0].adjacent_monster_exemptions


@pytest.mark.parametrize("stage_num", range(1, 7))
@pytest.mark.parametrize("rank, footprint", [
    (1, {(4, 3), (2, 3)}),
    (2, {(3, 2), (4, 3), (3, 4), (2, 3)}),
])
def test_f_barriers_depend_on_rank_and_clear_on_defeat(stage_num, rank, footprint):
    current, player = state()
    cobra = monster(3, 3, "f", rank)
    assert set(stage56.barrier_cells(current, cobra)) == footprint
    current.entities = [cobra]
    stage56.place_monster_barriers(current, cobra)
    assert all(current.field[y][x] == d.CHAR_BARRIER for x, y in footprint)
    current.entities.remove(cobra)

    engine._defeat_monster(
        cobra, current, player, [0], [(1, 1)], Counter(), stage_num=stage_num,
    )

    assert all(current.field[y][x] == d.CHAR_FLOOR for x, y in footprint)


def test_defeating_wyrm_preserves_overlapping_and_persistent_barriers():
    current, player = state()
    defeated = monster(3, 3, "w")
    survivor = monster(5, 3, "w")
    current.entities = [survivor]
    footprint = set(stage56.barrier_cells(current, defeated))
    for x, y in footprint:
        current.field[y][x] = d.CHAR_BARRIER
    current.persistent_barriers.add((2, 2))

    engine._defeat_monster(
        defeated, current, player, [0], [(1, 1)], Counter(), stage_num=6,
    )

    remaining = {(x, y) for x, y in footprint
                 if current.field[y][x] == d.CHAR_BARRIER}
    assert remaining == {(2, 2), (4, 2), (4, 3), (4, 4)}


def test_emergency_ration_requires_visible_reachable_winnable_monster():
    current, player = state(level=100, lp=0)
    visible = [[0] * d.FIELD_WIDTH for _ in current.field]
    current.seen = [[1] * d.FIELD_WIDTH for _ in current.field]
    enemy = monster(5, 2, 'a')
    current.entities = [enemy]
    assert engine._ration_available(current, player, visible)
    player.level = 0
    assert not engine._ration_available(current, player, visible)
    player.level = 100
    current.seen[2][5] = 0
    assert not engine._ration_available(current, player, visible)
    current.seen[2][5] = 1
    enemy.x = 35
    assert not engine._ration_available(current, player, visible)


def test_stage6_emergency_ration_used_once(monkeypatch):
    monkeypatch.setattr(d, 'RATIONS_ENABLED', True)
    current, player = state(level=100, lp=0)
    current.seen = [[1] * d.FIELD_WIDTH for _ in current.field]
    current.entities = [monster(3, 2, 'a')]
    monkeypatch.setattr(stage6, 'build', lambda *_: ([current], player))
    prompts, messages = [], []
    def collapse(*args, **kwargs):
        player.lp = 0
    monkeypatch.setattr(engine, '_step', collapse)
    from types import SimpleNamespace
    ui = SimpleNamespace(
        draw_stage=lambda **kw: messages.append(kw['message']),
        confirm_ration=lambda p: prompts.append(p.lp) or True,
        input_direction=lambda: (1, 0),
        input_game_over=lambda: None,
    )
    engine.run_game(ui, '123', stage_num=6)
    assert prompts == [0]
    assert player.rations == 0
    assert any('hunger' in message.lower() or '飢' in message for message in messages)


def test_stage6_disabled_ration_ends_game_without_prompt(monkeypatch):
    current, player = state(level=100, lp=0)
    current.seen = [[1] * d.FIELD_WIDTH for _ in current.field]
    current.entities = [monster(3, 2, 'a')]
    monkeypatch.setattr(d, 'RATIONS_ENABLED', False)
    monkeypatch.setattr(stage6, 'build', lambda *_: ([current], player))
    from types import SimpleNamespace
    ui = SimpleNamespace(
        draw_stage=lambda **kw: None,
        confirm_ration=lambda p: pytest.fail('Disabled ration must not be offered'),
        input_game_over=lambda: None,
    )
    engine.run_game(ui, '123', stage_num=6)
    assert player.rations == 1


@pytest.mark.parametrize("char", ["g", "e"])
def test_emergency_ration_excludes_monsters_without_food(char):
    current, player = state(level=100, lp=0)
    current.seen = [[1] * d.FIELD_WIDTH for _ in current.field]
    visible = [[0] * d.FIELD_WIDTH for _ in current.field]
    current.entities = [monster(3, 2, char)]
    assert not engine._ration_available(current, player, visible)
    current.entities.append(monster(3, 3, "a"))
    assert engine._ration_available(current, player, visible)


def test_stage6_uses_centered_narrow_sections_without_changing_field_size():
    floors, _ = stage6.build()
    right_edge = d.FIELD_X_MARGIN + (d.TILE_WIDTH + 1) * d.TILE_NUM_X
    assert d.FIELD_X_MARGIN == 1
    assert d.TILE_WIDTH == 11
    for current in floors:
        assert all(len(row) == d.FIELD_WIDTH for row in current.field)
        assert all(cell == d.CHAR_WALL for row in current.field for cell in row[:d.FIELD_X_MARGIN])
        assert all(cell == d.CHAR_WALL for row in current.field for cell in row[right_edge:])
        for x in range(1, d.TILE_NUM_X):
            point = (d.FIELD_X_MARGIN + x * (d.TILE_WIDTH + 1) + 1, 1)
            assert stage6.tile_at(point) == (x, 0)


@pytest.mark.parametrize("stage_num", [5, 6])
def test_cat_explores_after_twenty_turns_without_identifying_or_stopping(monkeypatch, stage_num):
    monkeypatch.setattr(stage6, "advance_spawns", lambda *_args: None)
    current, player = state((d.MEMBER_YAWNING_CAT,))
    enemy = monster(10, 6, "b")
    waiting = d.PartyMember(11, 6, d.MEMBER_HEALER)
    current.entities = [enemy, waiting]
    monkeypatch.setattr(stage56.rand, "choice", lambda cells: (10, 6))
    stops = set()
    for turn in range(20):
        engine._step(
            (1, 0) if turn % 2 == 0 else (-1, 0), [current], player,
            [0], [(2, 2)], Counter(), turn, stage_num=stage_num,
            repeat_stop_reasons=stops,
        )
        if turn < 19:
            assert not any(map(any, current.seen))
    assert {(x, y) for y, row in enumerate(current.seen)
            for x, value in enumerate(row) if value} == {
        (x, y) for y in range(6, 8) for x in range(10, 12)
    }
    assert player.known_monsters == {"a"}
    assert not player.known_member_floors
    assert not stops
    assert display.revealed_entity_glyphs(
        enemy, player.known_monsters, False, 100, None,
    )[0].char == "?"
    assert display.revealed_entity_glyphs(
        waiting, player.known_monsters, False, 100, None,
    )[0].char == "H"


@pytest.mark.parametrize("bottom_right", [False, True])
def test_cat_exploration_clips_at_map_edges_and_preserves_knowledge(monkeypatch, bottom_right):
    current, player = state((d.MEMBER_YAWNING_CAT,))
    if bottom_right:
        player.x, player.y = d.FIELD_WIDTH - 1, d.FIELD_HEIGHT - 1
    current.seen[10][10] = 1
    current.field[0][1] = "#"
    cat = player.members[0]
    cat.exploration_turns = 19
    def choose(cells):
        assert (10, 10) not in cells
        assert (1, 0) not in cells
        return (d.FIELD_WIDTH - 1, d.FIELD_HEIGHT - 1) if bottom_right else (0, 0)
    monkeypatch.setattr(stage56.rand, "choice", choose)
    stage56.explore_with_cat(current, player)
    left = d.FIELD_WIDTH - 2 if bottom_right else 0
    top = d.FIELD_HEIGHT - 2 if bottom_right else 0
    assert {(x, y) for y, row in enumerate(current.seen)
            for x, value in enumerate(row) if value} == {
        (10, 10), *((x, y) for y in range(top, top + 2)
                    for x in range(left, left + 2)),
    }
    assert current.seen[10][10] == 1
    assert cat.exploration_turns == 0


def test_cat_handles_fully_explored_floor_and_recruitment_resets_counter():
    current, player = state((d.MEMBER_YAWNING_CAT,))
    cat = player.members.pop()
    cat.exploration_turns = 19
    stage56.explore_with_cat(current, player)
    assert not any(map(any, current.seen))
    assert cat.exploration_turns == 19
    current.entities.append(cat)
    stage56.recruit(current, player, cat)
    assert cat.exploration_turns == 0
    current.seen = [[1] * len(row) for row in current.field]
    cat.exploration_turns = 19
    stage56.explore_with_cat(current, player)
    assert cat.exploration_turns == 0


def test_cat_selects_only_nearby_unexplored_floor_independently_of_vortex(monkeypatch):
    current, player = state((d.MEMBER_YAWNING_CAT,))
    player.x, player.y = 35, 11
    current.seen[11][35] = 1
    current.field[11][36] = "#"
    monkeypatch.setattr(d, "VORTEX_FLOOR_DIAMETER_RATIO", 0)
    def choose(cells):
        expected = set(iterate_ellipse_points(35, 11, 10, d.FOV_WIDTH_EXPANSION_RATIO))
        assert set(cells) == expected - {(35, 11), (36, 11)}
        assert (35, 1) in cells
        assert (35, 0) not in cells
        assert (35, 21) in cells
        assert (35, 22) not in cells
        assert (0, 11) not in cells
        return (35, 1)
    monkeypatch.setattr(stage56.rand, "choice", choose)
    player.members[0].exploration_turns = 19
    stage56.explore_with_cat(current, player)
    assert current.seen[1][35] == 1


def test_cat_does_nothing_when_only_distant_floor_is_unexplored(monkeypatch):
    current, player = state((d.MEMBER_YAWNING_CAT,))
    current.seen = [[1] * len(row) for row in current.field]
    current.seen[-1][-1] = 0
    monkeypatch.setattr(stage56.rand, "choice", lambda cells: pytest.fail("No local candidates"))
    player.members[0].exploration_turns = 19
    stage56.explore_with_cat(current, player)
    assert current.seen[-1][-1] == 0
    assert player.members[0].exploration_turns == 0
