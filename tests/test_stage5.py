"""Rules, generation, and rescue checks for the five-floor party stage."""

from collections import Counter, deque
from itertools import pairwise

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


def test_playground_has_all_recruits_and_connected_rank2_bosses():
    floors, player = stage5.build()
    assert len(floors) == 5 and player.rescue_stage
    current = floors[-1]
    assert {
        e.role for f in floors for e in f.entities if isinstance(e, d.PartyMember)
    } == {
        "Bard",
        "Healer",
        "Rogue",
        "Knight",
        "Dangeon Scholar",
    }
    assert {
        e.role for e in floors[0].entities if isinstance(e, d.PartyMember)
    } == {
        "Bard",
        "Healer",
        "Rogue",
        "Knight",
        "Dangeon Scholar",
    }
    assert not any(
        isinstance(e, d.PartyMember)
        for floor in floors[1:]
        for e in floor.entities
    )
    assert not any(
        isinstance(e, d.Monster) and e.tribe.is_elf for f in floors for e in f.entities
    )
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F"
    )
    party = stage5.monster_party(current, boss)
    assert {(e.tribe.char, e.empowered) for e in party} >= {("F", 2), ("V", 2)}
    assert 2 <= len(party) <= 5
    assert sum(d.monster_level(e) for e in party) >= 290


def test_stage5_member_progress_has_no_floor_numbers():
    _, player = state()
    player.known_member_floors = {"Bard": 1, "Rogue": 2}
    assert [
        label for label, _ in display.stage5_member_progress_marks(player)
    ] == ["B", "H", "R", "K", "D", "N"]


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
    ) == ["Bard", "Healer", "Rogue"]
    assert player.companion is companion


@pytest.mark.parametrize(
    "roles, gain",
    [
        ((), 2),
        (("Bard",), 3),
        (("Knight",), 0.5),
        (("Bard", "Knight"), 1),
        (("Healer", "Rogue"), 2 / 3),
    ],
)
def test_group_rewards_are_shared_then_adjusted_by_members(roles, gain):
    current, player = state(roles, lp=10)
    current.entities = [monster(3, 2, "b"), monster(4, 2, "a")]
    feed = max(e.tribe.feed for e in current.entities)
    step(current, player)
    assert current.entities == []
    assert player.level == 100 + gain
    assert player.lp == min(d.LP_MAX, 10 + feed)


def test_group_strength_defeat_preserves_party_and_healer_penalty():
    current, player = state(("Healer", "Rogue"), level=10)
    enemies = [monster(3, 2, "b", 2), monster(4, 2, "w")]
    current.entities = enemies.copy()
    before = player.members.copy()
    step(current, player, checkpoint=(1, 1))
    assert current.entities == enemies
    assert player.level == 10 and player.lp == 88
    assert player.members == before
    assert all((member.x, member.y) == (1, 1) for member in player.members)


def test_group_keeps_unique_item_even_when_contacting_ordinary_member():
    current, player = state()
    current.entities = [monster(3, 2, "a"), monster(4, 2, "c")]
    step(current, player)
    assert player.item == d.ITEM_SWORD_X1_5


def test_fractional_attack_hazards_and_status():
    current, player = state(("Knight", "Dangeon Scholar"), level=100.5)
    assert d.current_player_attack(player) == pytest.approx(201)
    player.item = d.ITEM_SWORD_X1_5
    assert d.current_player_attack(player) == pytest.approx(301.5)
    assert barrier_lp_damage(player) == 30
    assert d.caltrop_lp_damage(player) == 3
    current.field[2][3] = d.CHAR_CALTROP
    step(current, player)
    assert player.lp == 87
    assert "LVL: 100" in display.status_prefix(player, 5, 0)
    assert "ATK:" in display.status_prefix(player, 5, 0)


def test_rogue_detects_shooting_lane_and_respects_blockers():
    current, player = state(("Rogue",))
    marksman = monster(7, 3, "k")
    current.entities.append(marksman)
    assert stage5.rogue_danger(current, player, (3, 3)) == "-"
    assert ((3, 3), "-") in marksman.arrow_marks
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


def test_boss_win_rearranges_only_final_floor_and_spawns_noble_without_winning():
    floors, player = stage5.build()
    current = floors[-1]
    boss = next(
        e for e in current.entities if isinstance(e, d.Monster) and e.tribe.char == "F"
    )
    origin = (boss.x, boss.y)
    player.level = 10000
    player.x, player.y = boss.x, boss.y
    for floor_data in floors:
        floor_data.seen = [[1] * d.FIELD_WIDTH for _ in floor_data.field]
    floor_index = [3]
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
    noble = next(
        e
        for e in current.entities
        if isinstance(e, d.PartyMember) and e.role == "Noble"
    )
    assert abs(noble.x - origin[0]) + abs(noble.y - origin[1]) <= 2
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
    assert all(
        e.active
        for e in current.entities
        if isinstance(e, d.Monster) and e.tribe.char == "M"
    )
    stage5.recruit(current, player, noble)
    # A matching coordinate on another floor must not finish the rescue.
    player.x, player.y = floors[0].up
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
    assert not player.stage_won
    # Return through the actual stairs, preserving Noble and joining order.
    for index in (3, 2, 1):
        player.x, player.y = floors[index].up
        assert engine._handle_floor_transition(
            floors[index], floors, player, floor_index, [current.up]
        )
        assert floor_index[0] == index - 1
    engine._step(
        (0, 0),
        floors,
        player,
        floor_index,
        [floors[0].up],
        Counter(),
        deque(),
        1,
        stage_num=5,
    )
    assert player.stage_won and not player.treasure_collected


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
    current.entities = [monster(x, 2, "a") for x in range(2, 8)]
    boss, vortex = monster(8, 2, "F", 2), monster(9, 2, "V", 2)
    current.entities += [boss, vortex, monster(10, 2, "c")]
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
    assert player.lp == 89.25
    assert (player.x, player.y) == (3, 2)
    assert ui.stops >= 2


def test_candidate_glyph_is_known_on_first_sighting():
    _, player = state()
    candidate = d.PartyMember(3, 2, "Bard")
    assert get_torched(player, d.TORCH_RADIUS)[candidate.y][candidate.x]
    assert (
        display.revealed_entity_glyphs(candidate, set(), False, 100, None)[0].char
        == "B"
    )


def test_all_floors_have_connected_stairs_and_keep_members_on_transitions():
    floors, player = stage5.build()
    player.members = [
        d.PartyMember(player.x, player.y, "Knight"),
        d.PartyMember(player.x, player.y, "Noble"),
    ]
    floor_index, checkpoint = [0], [floors[0].up]
    for index, current in enumerate(floors):
        pending, visited = [current.up], {current.up}
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
        assert current.down in visited
        assert all((e.x, e.y) in visited for e in current.entities)
        assert (
            engine._stage_draw_options(5, floors, index, False, True)["floor_label"]
            == f"{index + 1}/4"
        )
        if index == 3:
            break
        assert current.down == floors[index + 1].up
        assert current.field[current.down[1]][current.down[0]] == d.CHAR_STAIRS_DOWN
        player.x, player.y = current.down
        engine._handle_floor_transition(
            current, floors, player, floor_index, checkpoint
        )
        stage5.sync_members(player, current.down, (1, 0))
        assert floor_index[0] == index + 1
        assert [member.role for member in player.members] == ["Knight", "Noble"]
        assert all((e.x, e.y) == floors[index + 1].up for e in player.members)


def test_party_can_fill_a_narrow_corridor_against_walls():
    current, _ = state()
    current.field = [[d.CHAR_WALL] * d.FIELD_WIDTH for _ in current.field]
    for x in range(5, 10):
        current.field[5][x] = d.CHAR_FLOOR
    stage5._place_party(current, [("a", 1)] * 5)
    assert {(e.x, e.y) for e in current.entities} == {(x, 5) for x in range(5, 10)}
    assert len(stage5.monster_party(current, current.entities[0])) == 5
    removed = current.entities.pop()
    assert stage5.respawn(current, "b", 1, 0, set()) == (removed.x, removed.y)


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


def test_deeper_floors_have_stronger_and_larger_parties_across_seeds():
    total_sizes, total_strengths, total_groups = [0] * 4, [0] * 4, [0] * 4
    seen_sizes = [set() for _ in range(4)]
    for seed in range(12):
        engine.rand.set_seed(seed)
        floors, _ = stage5.build()
        for index, current in enumerate(floors):
            checked = set()
            for entity in current.entities:
                if (
                    not isinstance(entity, d.Monster)
                    or not entity.active
                    or isinstance(entity, d.Collapse)
                    or entity in checked
                ):
                    continue
                party = stage5.monster_party(current, entity)
                checked.update(party)
                assert 1 <= len(party) <= 5
                assert sum(stage5.special_monster(e) for e in party) <= 1
                total_sizes[index] += len(party)
                total_strengths[index] += sum(d.monster_level(e) for e in party)
                total_groups[index] += 1
                seen_sizes[index].add(len(party))
    mean_sizes = [size / count for size, count in zip(total_sizes, total_groups)]
    mean_strengths = [
        power / count for power, count in zip(total_strengths, total_groups)
    ]
    mean_monster_strengths = [
        power / size for power, size in zip(total_strengths, total_sizes)
    ]
    assert all(a < b for a, b in pairwise(mean_sizes))
    assert all(a < b for a, b in pairwise(mean_strengths))
    assert all(a < b for a, b in pairwise(mean_monster_strengths))
    assert all(len(sizes) > 1 for sizes in seen_sizes)
    assert 5 in seen_sizes[-1]
