from arlq import defs, display


def test_core_brackets_yield_to_map_contents():
    glyph = display.FieldGlyph(1, 0, "[", "yellow")
    field = [[defs.CHAR_FLOOR] * 3]
    assert display.core_bracket_is_clear(glyph, field, set())
    assert not display.core_bracket_is_clear(glyph, field, {(1, 0)})
    assert not display.core_bracket_is_clear(glyph, field, set(), [["", "boss route", ""]])
    field[0][1] = defs.CHAR_BARRIER
    assert not display.core_bracket_is_clear(glyph, field, set())
    assert not display.core_bracket_is_clear(glyph._replace(x=-1), field, set())


def test_treasure_and_unknown_mimic_have_identical_bracketed_glyphs():
    treasure = defs.Treasure(4, 5, "TD")
    treasure.unlocked = True
    mimic = defs.Monster(4, 5, defs.CHAR_TO_MONSTER_TRIBE["M"], mimic_boss_char="D")
    mimic.active = True
    for glyphs in (display.preview_entity_glyphs,):
        assert glyphs(treasure) == glyphs(mimic)
        assert [g.char for g in glyphs(mimic, known_types={"MD"})] == ["M"]
    chest = display.revealed_entity_glyphs(treasure, set(), False, 8, None)
    disguised = display.revealed_entity_glyphs(mimic, set(), False, 8, None)
    assert chest == disguised
    assert [g.char for g in chest] == ["T", "[", "]"]
    assert [g.char for g in display.revealed_entity_glyphs(mimic, {"MD"}, False, 8, None)] == ["M"]
