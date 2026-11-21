import random

import pytest

from arlq import defs as d
from arlq import display, i18n, iris_dialogue
from arlq import game_engine as engine
from arlq.game_events import Rewound
from arlq.game_session import GameSession
from arlq.stage_types import Floor


@pytest.fixture(autouse=True)
def english():
    previous = i18n.get_language()
    i18n.set_language("en")
    yield
    i18n.set_language(previous)


def floor_and_player(roles=(d.MEMBER_IRIS,), lp=90):
    player = d.Player(2, 2, 100, lp)
    player.rescue_stage = True
    player.members = [d.PartyMember(1, 2, role) for role in roles]
    field = [[d.CHAR_FLOOR] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    current = Floor(field, [], [[0] * d.FIELD_WIDTH for _ in field], (1, 1), (40, 16), None)
    return current, player


def session_with(monkeypatch, current, player, rng_seed=0):
    monkeypatch.setattr(engine, "build_single_floor", lambda *_: ([current], player))
    session = GameSession(1, seed_str="iris-chatter")
    session.iris_chatter = iris_dialogue.IrisChatter(random.Random(rng_seed))
    session.message = (-1, "")
    return session


def english_lines(category):
    return [iris_dialogue.format_line(line, "en")
            for line in iris_dialogue.lines_for("en")[category]]


def test_dialogue_files_pair_up_and_cover_every_category():
    en = iris_dialogue.lines_for("en")
    ja = iris_dialogue.lines_for("ja")
    assert list(en) == list(ja)
    assert all(en[key] and len(en[key]) == len(ja[key]) for key in en)
    assert set(en) == set(iris_dialogue.CATEGORIES) | {iris_dialogue.RATION_CATEGORY}
    for lines in (*en.values(), *ja.values()):
        assert all(line and not line.startswith(("I: ", "I「")) for line in lines)


def test_speaker_marks_follow_the_language():
    assert iris_dialogue.format_line("Hello.", "en") == "I: Hello."
    assert iris_dialogue.format_line("こんにちは", "ja") == "I「こんにちは」"


def test_lines_use_python_random_not_the_game_rng(monkeypatch):
    current, player = floor_and_player(lp=41)
    session = session_with(monkeypatch, current, player)
    state = engine.rand.getstate()
    session.iris_chatter.line("idle")
    session.iris_chatter.ration_line()
    assert engine.rand.getstate() == state


def test_low_lp_warning_when_lp_crosses_a_threshold(monkeypatch):
    current, player = floor_and_player(lp=d.LP_WARNING_THRESHOLD + 1)
    session = session_with(monkeypatch, current, player)
    for category in ("low_lp", "low_lp_after_emergency_food"):
        monkeypatch.setitem(iris_dialogue.CATEGORIES, category, (55, 0, 1.0))
    session.iris_chatter.turns_since_line = iris_dialogue.CHATTY_GAP
    session.step((1, 0))
    assert session.message[1] in english_lines("low_lp")
    session.player.members[0].has_ration = False
    session.player.lp = d.LP_LOW_THRESHOLD + 1
    session.iris_chatter.turns_since_line = iris_dialogue.CHATTY_GAP
    session.step((1, 0))
    assert session.message[1] in english_lines("low_lp_after_emergency_food")


def test_join_line_waits_for_the_game_message(monkeypatch):
    current, player = floor_and_player(roles=())
    iris = d.PartyMember(3, 2, d.MEMBER_IRIS)
    current.entities.append(iris)
    session = session_with(monkeypatch, current, player)
    session.step((1, 0))
    joined = session.message[1]
    assert iris in session.player.members and joined not in english_lines("join")
    session.step((1, 0))
    assert session.message[1] == joined
    session.step((1, 0))
    assert session.message[1] in english_lines("join")


def test_rejoin_lines_depend_on_the_ration(monkeypatch):
    current, player = floor_and_player(roles=())
    player.joined_members.add(d.MEMBER_IRIS)
    iris = d.PartyMember(3, 2, d.MEMBER_IRIS)
    iris.has_ration = False
    current.entities.append(iris)
    session = session_with(monkeypatch, current, player)
    for _ in range(3):
        session.step((1, 0))
    assert session.message[1] in english_lines("rejoin_after_emergency_food")


def test_silent_without_iris(monkeypatch):
    current, player = floor_and_player(roles=(d.MEMBER_KNIGHT,), lp=d.LP_WARNING_THRESHOLD + 1)
    session = session_with(monkeypatch, current, player)
    session.step((1, 0))
    assert session.message == (-1, "")


def test_newly_seen_monster_is_announced_by_its_look(monkeypatch):
    current, player = floor_and_player()
    session = session_with(monkeypatch, current, player)
    session.iris_chatter.turns_since_line = iris_dialogue.CHATTY_GAP
    session.step((1, 0))
    goblin = d.Monster(player.x + 2, player.y, d.CHAR_TO_MONSTER_TRIBE["g"], 1)
    player.known_monsters.discard(d.monster_type_key(goblin))
    current.entities.append(goblin)
    monkeypatch.setitem(
        iris_dialogue.CATEGORIES, "unidentified_monster_spotted", (30, 0, 1.0)
    )
    session.iris_chatter.turns_since_line = iris_dialogue.CHATTY_GAP
    session.step((0, 1))
    assert session.message[1] in english_lines("unidentified_monster_spotted")


def test_disguised_mimic_counts_as_a_treasure_chest():
    mimic = d.Monster(5, 5, d.CHAR_TO_MONSTER_TRIBE["M"], 1)
    glyphs = display.revealed_entity_glyphs(mimic, set(), False, 100, None)
    assert iris_dialogue._sighting(mimic, glyphs) == "treasure_spotted"


def test_rewind_turn_stays_quiet():
    chatter = iris_dialogue.IrisChatter(random.Random(0))
    current, player = floor_and_player(lp=d.LP_WARNING_THRESHOLD + 1)
    start = chatter.start_turn(player, 0)
    player.lp = d.LP_WARNING_THRESHOLD

    class Session:
        turn = 10
        stage_num = 6
        floors = [current]
        floor = [0]
        message = (-1, "")
        iris_rescue_pending = False

        class config:
            torch_radius = d.TORCH_RADIUS

    Session.player = player
    events = [Rewound(0, "", {})]
    assert chatter.end_turn(Session, start, events,
                            bridgehead_entered=False, game_spoke=False) is None


def test_restocked_ration_is_announced_at_the_bridgehead(monkeypatch):
    current, player = floor_and_player()
    current.bridgehead = (3, 2)
    player.members[0].has_ration = False
    session = session_with(monkeypatch, current, player)
    session.step((1, 0))
    assert session.player.members[0].has_ration
    assert session.message[1] in english_lines("ration_refilled")


def test_bridgehead_with_a_full_ration_is_only_optional_chatter(monkeypatch):
    current, player = floor_and_player()
    current.bridgehead = (3, 2)
    session = session_with(monkeypatch, current, player)
    session.step((1, 0))
    assert session.message == (-1, "")
