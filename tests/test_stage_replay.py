"""Live/replay parity for exploration, effects, and repeated Loop contacts."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from arlq import defs as d
from arlq import game_engine as engine
from arlq import stage5, stage_replay
from arlq.arlq import GameConfig
from arlq.stage_types import Floor, ReplayContext


def signature(player, entities, field, seen):
    entity_states = []
    for entity in entities:
        if isinstance(entity, d.Player):
            continue
        state = (type(entity).__name__, entity.x, entity.y)
        if isinstance(entity, d.Monster):
            state += (
                entity.tribe.char,
                entity.empowered,
                entity.active,
                entity.revealed,
                entity.met,
                entity.marksman_cooldown,
                entity.marksman_shots_fired,
                entity.arrow_marks,
            )
        elif isinstance(entity, d.Companion):
            state += (entity.tribe.char, entity.revealed, entity.durability)
        elif isinstance(entity, d.PartyMember):
            state += (entity.role, entity.origin_floor)
        elif isinstance(entity, d.Treasure):
            state += (entity.unlock_key, entity.unlocked)
        entity_states.append(deepcopy(state))
    return deepcopy(
        (
            (
                player.x,
                player.y,
                player.level,
                player.lp,
                player.item,
                player.item_uses,
                player.karma,
                player.current_floor,
                player.elf_stage_flags,
                player.last_contact_monster,
                player.boss_defeated,
                player.treasure_collected,
            ),
            player.known_monsters,
            player.seen_members,
            player.joined_members,
            player.known_member_floors,
            player.known_c_floors,
            [(m.role, m.x, m.y) for m in player.members],
            entity_states,
            field,
            seen,
            engine.rand._value,
        )
    )


def run_and_replay(monkeypatch, build, stage_num, moves, config):
    if stage_num == 5:
        monkeypatch.setattr(stage5, "build", build)
    elif stage_num == 6:
        monkeypatch.setattr(stage5, "build_member_trial", build)
    else:
        monkeypatch.setattr(engine, "build", build)
        monkeypatch.setattr(stage_replay, "build", build)
    contexts = []

    def make_context(*args):
        context = ReplayContext(*args)
        contexts.append(context)
        return context

    monkeypatch.setattr(engine, "ReplayContext", make_context)
    frames = []

    def draw_stage(**kwargs):
        frames.append(
            signature(
                kwargs["player"], kwargs["entities"], kwargs["field"], kwargs["torched"]
            )
        )

    inputs = iter([*moves, None])
    ui = SimpleNamespace(
        draw_stage=draw_stage, input_direction=inputs.__next__, map_mode=False
    )
    engine.rand.set_seed(2468)
    engine.run_game(ui, "test", stage_num=stage_num, config=config)
    context = contexts[0]
    floors, player, floor, *_ = stage_replay.replay_to_operation(
        context,
        len(context.operations),
    )
    assert (
        signature(
            player, floors[floor].entities, floors[floor].field, floors[floor].seen
        )
        == frames[-1]
    )
    return context


@pytest.mark.parametrize("stage_num", [4, 5])
@pytest.mark.parametrize("torch_radius", [1, 4])
def test_live_and_replay_match_after_vortex_rearrangement(
    monkeypatch, stage_num, torch_radius
):
    def build(*_):
        engine.rand.randrange(100)
        player = d.Player(2, 2, 10000, 120)
        player.rescue_stage = stage_num == 5
        field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
        entities = [
            d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["V"]),
            d.Monster(8, 6, d.CHAR_TO_MONSTER_TRIBE["k"]),
            d.Companion(10, 5, d.CHAR_TO_COMPANION_TRIBE["n"]),
        ]
        if stage_num == 5:
            entities.extend(
                [
                    d.Monster(3, 3, d.CHAR_TO_MONSTER_TRIBE["W"]),
                    d.Monster(3, 4, d.CHAR_TO_MONSTER_TRIBE["a"], 2),
                ]
            )
        return [
            Floor(
                field,
                entities,
                [[0] * len(row) for row in field],
                (2, 2),
                (70, 18),
                None,
            )
        ], player

    run_and_replay(
        monkeypatch,
        build,
        stage_num,
        [(1, 0), (0, 1), (1, 0)],
        GameConfig(torch_radius=torch_radius),
    )


@pytest.mark.parametrize("stage_num", [5, 6])
def test_repeated_rewinds_replay_rogue_checks_and_scholar_discoveries(
    monkeypatch, stage_num
):
    def build(*_):
        engine.rand.randrange(100)
        player = d.Player(2, 2, 10000, 120)
        player.rescue_stage = True
        player.members = [
            d.PartyMember(2, 2, role) for role in ("Rogue", "Dangeon Scholar")
        ]
        field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
        field[3][2] = d.CHAR_COLLAPSE
        field[3][3] = d.CHAR_HIDDEN_D_GATE
        current = Floor(
            field,
            [
                d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["V"]),
                d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"]),
            ],
            [[0] * len(row) for row in field],
            (2, 2),
            (70, 18),
            None,
        )
        current.d_gates[(3, 3)] = d.CHAR_D_GATE
        return [current], player

    def disturb_map(current, *_args, **_kwargs):
        engine.rand.randrange(100)
        current.seen = [[0] * len(row) for row in current.field]

    def respawn_loop(entities, *_args):
        engine.rand.randrange(100)
        entities.append(d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"]))
        return 4, 2

    monkeypatch.setattr(engine, "_vortex_rearrange", disturb_map)
    monkeypatch.setattr(stage_replay, "_spawn", respawn_loop)
    context = run_and_replay(
        monkeypatch,
        build,
        stage_num,
        [(0, 1), (1, 0), (1, 0), (1, 0), (1, 0), (1, 0), (1, 0)],
        GameConfig(),
    )
    assert len(context.rewind_targets) == 3
    assert context.rogue_checks == {0: [(2, 3)]}


def test_repeated_rewinds_without_vortex_preserve_exploration(monkeypatch):
    def build(*_):
        player = d.Player(2, 2, 10, 120)
        player.rescue_stage = True
        field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
        current = Floor(
            field,
            [d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"])],
            [[0] * len(row) for row in field],
            (2, 2),
            (70, 18),
            None,
        )
        return [current], player

    def respawn_loop(entities, *_args):
        entities.append(d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"]))
        return 4, 2

    monkeypatch.setattr(stage_replay, "_spawn", respawn_loop)
    context = run_and_replay(monkeypatch, build, 5, [(1, 0)] * 8, GameConfig())
    assert len(context.rewind_targets) == 4


def test_rewind_keeps_current_knowledge_after_vortex_erasure(monkeypatch):
    def build(*_):
        player = d.Player(2, 2, 10000, 120)
        player.rescue_stage = True
        player.members = [d.PartyMember(2, 2, "Dangeon Scholar")]
        field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
        field[3][12] = d.CHAR_HIDDEN_D_GATE
        entities = [
            d.Monster(15, 2, d.CHAR_TO_MONSTER_TRIBE["V"]),
            d.Companion(16, 2, d.CHAR_TO_COMPANION_TRIBE["l"]),
        ]
        current = Floor(
            field, entities, [[0] * len(row) for row in field], (2, 2), (70, 18), None
        )
        current.d_gates[(12, 3)] = d.CHAR_D_GATE
        return [current], player

    def disturb_map(current, *_args, **_kwargs):
        current.seen = [[0] * len(row) for row in current.field]

    def respawn_loop(entities, *_args):
        entities.append(d.Companion(16, 2, d.CHAR_TO_COMPANION_TRIBE["l"]))
        return 16, 2

    monkeypatch.setattr(engine, "_vortex_rearrange", disturb_map)
    monkeypatch.setattr(stage_replay, "_spawn", respawn_loop)
    context = run_and_replay(monkeypatch, build, 5, [(1, 0)] * 14, GameConfig())
    floors, player, *_ = stage_replay.replay_to_operation(context, 14)
    assert (player.x, player.y) == (2, 2)
    assert floors[0].seen[2][15]
    assert not floors[0].seen[2][8]
    assert floors[0].field[3][12] == d.CHAR_D_GATE
    assert "V" in player.known_monsters


def test_replay_executes_operations_discarded_by_loop_contacts(monkeypatch):
    def build(*_):
        player = d.Player(2, 2, 10000, 120)
        player.rescue_stage = True
        field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
        entities = [
            d.Monster(3, 2, d.CHAR_TO_MONSTER_TRIBE["V"]),
            d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"]),
        ]
        return [
            Floor(
                field,
                entities,
                [[0] * len(row) for row in field],
                (2, 2),
                (70, 18),
                None,
            )
        ], player

    effects = []

    def disturb_map(current, *_args, **_kwargs):
        effects.append("V")
        current.seen = [[0] * len(row) for row in current.field]

    def respawn_loop(entities, *_args):
        entities.append(d.Companion(4, 2, d.CHAR_TO_COMPANION_TRIBE["l"]))
        return 4, 2

    monkeypatch.setattr(stage5, "build", build)
    monkeypatch.setattr(engine, "_vortex_rearrange", disturb_map)
    monkeypatch.setattr(stage_replay, "_spawn", respawn_loop)
    context = ReplayContext(
        5, 123, GameConfig(), operations=[(1, 0)] * 3, rewind_targets={2: 0}
    )
    _, player, *_ = stage_replay.replay_to_operation(context, 3)
    assert effects == ["V", "V"]
    assert (player.x, player.y) == (3, 2)
    assert "V" in player.known_monsters
