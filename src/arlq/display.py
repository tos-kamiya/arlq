"""Shared text and glyph calculations used by both frontends."""

from typing import List, NamedTuple, Optional, Set, Tuple

from . import defs as d


def build_strength_column(
    tribes: List[d.MonsterTribe],
    player_attack: int,
    max_rows: int,
) -> List[Tuple[Optional[str], bool]]:
    """
    Lay out a stage's monster tribes and the player for the right-edge
    strength column, replacing the old ">X" beatable-monster indicator.

    The player is fixed near the vertical center with a blank row on each
    side. Tribes stronger than the player stack above it (strongest at the
    top, closest to the player at the bottom, right above the gap); tribes
    the player can beat (including a tie) stack below it (closest to the
    player at the top, right below the gap, weakest at the bottom). If a
    side has more tribes than fit, the ones closest to the player's
    strength are kept and the rest are dropped, leaving blank rows at that
    side's far end.

    Returns exactly `max_rows` (char, is_player) pairs, char is None for a
    blank row.
    """
    stronger = sorted(
        (t for t in tribes if t.level > player_attack),
        key=lambda t: t.level,
        reverse=True,
    )
    weaker = sorted(
        (t for t in tribes if t.level <= player_attack),
        key=lambda t: t.level,
        reverse=True,
    )

    center = max_rows // 2
    above_cap = max(center - 1, 0)
    below_cap = max(max_rows - center - 2, 0)

    kept_above = stronger[-above_cap:] if above_cap else []
    kept_below = weaker[:below_cap]

    above_column: List[Tuple[Optional[str], bool]] = [(None, False)] * (
        above_cap - len(kept_above)
    )
    above_column += [(t.char, False) for t in kept_above]
    below_column: List[Tuple[Optional[str], bool]] = [
        (t.char, False) for t in kept_below
    ]
    below_column += [(None, False)] * (below_cap - len(kept_below))

    return above_column + [(None, False), ("@", True), (None, False)] + below_column


def level_item_labels(player: d.Player, stage_num: int) -> Tuple[str, str]:
    """Level and item fragments shared by both status bars.

    The Collector's x1.2 and Javelin Elf's x1.25 bonuses apply in every stage.
    x1.2 is omitted while a sword already replaces the base multiplier.
    `stage_num` is retained for existing callers.
    """
    has_k = bool(player.elf_stage_flags & d.ELF_STAGE_K_FLAG)
    has_j = d._javelin_follower_active(player)
    item = player.item
    if item == d.ITEM_SWORD_X1_5:
        level = f"LVL: {player.level} x1.5"
        item_str = f"+{item}({player.item_taken_from})"
    elif item == d.ITEM_SWORD_CURSED:
        level = f"LVL: {player.level} x3"
        item_str = f"+{item}({player.item_taken_from})"
    elif item == d.ITEM_POISONED:
        level = f"LVL: {player.level} /2"
        item_str = f"+{item}({player.item_taken_from})"
    elif item == d.ITEM_SPORES:
        level = f"LVL: {player.level}"
        item_str = f"+{item}({player.item_taken_from})"
    else:
        level = f"LVL: {player.level}"
        item_str = ""
    if has_k:
        level += " x1.2"
    if has_j:
        level += " x1.25"
    return level, item_str


def status_prefix(
    player: d.Player,
    stage_num: int,
    turn: int,
    game_start_turn: Optional[int] = None,
) -> str:
    """Text to the left of the LP readout, including the trailing spaces."""
    level_str, item_str = level_item_labels(player, stage_num)
    text = ""
    if stage_num != 0:
        text += f"ST: {stage_num}  "
    if game_start_turn is None:
        text += f"TURN: {turn}  "
    else:
        text += f"TURN: {game_start_turn} (OP: {turn})  "
    text += level_str + "  "
    text += item_str + "  "
    return text


def elf_stage_progress_marks(
    player: d.Player, stage_num: int
) -> List[Tuple[str, bool]]:
    """Elf and treasure marks for the multi-floor stage status line.

    Each entry is (label, achieved). The Isolated Elf flag reveals all elf
    floors; otherwise, identifying an elf reveals that elf's floor. If L is
    present, its floor is shown as ``?`` after the player has met L.
    """
    show_floors = bool(player.elf_stage_flags & d.ELF_STAGE_I_FLAG)
    marks: List[Tuple[str, bool]] = []
    progress = list(d.ELF_STAGE_PROGRESS)
    if "L" in player.elf_stage_floors or player.elf_stage_flags & d.ELF_STAGE_L_FLAG:
        progress = [
            *d.ELF_STAGE_PROGRESS[:4],
            ("L", d.ELF_STAGE_L_FLAG),
            *d.ELF_STAGE_PROGRESS[4:],
        ]
    for label, bit in progress:
        text = label
        if label == "C" and player.known_c_floors:
            text += "".join(str(floor) for floor in sorted(player.known_c_floors))
        elif label == "L" and player.elf_stage_flags & d.ELF_STAGE_L_FLAG:
            text += "?"
        elif (
            show_floors or label in player.known_elf_floors
        ) and label in player.elf_stage_floors:
            text += str(player.elf_stage_floors[label])
        marks.append((text, bool(player.elf_stage_flags & bit)))
    marks.append((d.stage_boss_label(stage_num), player.boss_defeated))
    marks.append(("T", player.treasure_collected))
    return marks


class FieldGlyph(NamedTuple):
    """One character to draw on the field.

    ``tone`` is a semantic name (``yellow``, ``blue``, ``red``, ``companion``,
    ``default``, ``black``, ``magenta``, ``stair``). Each frontend maps it.
    ``companion`` is green in the GUI and the terminal's default color;
    ``stair`` follows the stair glyph style in each frontend.
    """

    x: int
    y: int
    char: str
    tone: str
    bold: bool = False
    dim: bool = False


def player_appearance(player: d.Player) -> Tuple[str, Optional[str]]:
    """Foreground and background tones for '@'.

    Low LP is a red background and warning-level LP is yellow. Poison is
    magenta text unless the background calls for black text for contrast.
    """
    low = player.lp <= d.LP_LOW_THRESHOLD
    warning = player.lp <= d.LP_WARNING_THRESHOLD
    poisoned = player.item == d.ITEM_POISONED
    background = "red" if low else "yellow" if warning else None
    if background == "yellow" or (background == "red" and poisoned):
        foreground = "black"
    elif poisoned:
        foreground = "magenta"
    else:
        foreground = "default"
    return foreground, background


def preview_entity_glyphs(
    entity: d.Entity,
    reveal_disguises: bool = False,
    known_types: Optional[Set[str]] = None,
    stage_num: int = 0,
) -> List[FieldGlyph]:
    """Dim glyphs for an entity when the whole map is revealed."""
    known_types = known_types or set()
    if (
        isinstance(entity, d.Monster)
        and not entity.active
        and not (entity.tribe.char == "M" and not entity.met and reveal_disguises)
    ):
        return []
    char = None
    if isinstance(entity, d.Monster):
        char = entity.tribe.char
        if (
            char == "M"
            and d.monster_type_key(entity) not in known_types
            and not reveal_disguises
        ):
            char = d.CHAR_TREASURE
    elif isinstance(entity, d.Companion):
        char = entity.tribe.char
    elif isinstance(entity, d.Treasure):
        char = d.CHAR_TREASURE
    elif isinstance(entity, d.Collapse):
        return [FieldGlyph(entity.x, entity.y, "?", "yellow", bold=True)]
    if char is None:
        return []
    stage2_high_elf = (
        isinstance(entity, d.Monster) and entity.tribe.char == "H" and stage_num == 2
    )
    known = False
    if isinstance(entity, d.Monster) and stage2_high_elf:
        known = entity.revealed or d.monster_type_key(entity) in known_types
    tone = "red" if known else "default"
    glyphs = [
        FieldGlyph(
            entity.x,
            entity.y,
            char,
            tone,
            bold=tone == "stair",
            dim=tone == "default",
        )
    ]
    if isinstance(entity, d.Monster) and entity.empowered > 1:
        marker = "'" if entity.empowered == 2 else '"'
        glyphs.append(FieldGlyph(entity.x + 1, entity.y, marker, "default", dim=True))
    return glyphs


def revealed_entity_glyphs(
    entity: d.Entity,
    known_types: Set[str],
    show_entities: bool,
    player_attack: int,
    dim_types: Optional[Set[str]],
    reveal_disguises: bool = False,
    debug_show_entities: bool = False,
    stage_num: int = 0,
) -> List[FieldGlyph]:
    """Glyphs for an entity inside the explored map.

    Empty when the entity stays hidden (an unknown monster while the whole
    map is already shown, or a treasure that is still locked).
    """
    if isinstance(entity, d.Companion):
        char = entity.tribe.char
        known = entity.revealed
        if not known and not show_entities:
            char = "!"
        tone = "default" if debug_show_entities and not known else "companion"
        return [FieldGlyph(entity.x, entity.y, char, tone, bold=True)]
    if isinstance(entity, d.Monster):
        char = entity.tribe.char
        if not entity.active:
            return []
        stage2_high_elf = char == "H" and stage_num == 2
        if stage2_high_elf:
            known = entity.revealed or d.monster_type_key(entity) in known_types
        elif entity.tribe.is_elf:
            known = entity.revealed
        else:
            known = d.monster_type_key(entity) in known_types
        if char == "M" and not known and not reveal_disguises:
            return [
                FieldGlyph(entity.x, entity.y, d.CHAR_TREASURE, "yellow", bold=True)
            ]
        if char != "M" and not known:
            if show_entities:
                return []
            if entity.tribe.is_elf and not stage2_high_elf:
                return [
                    FieldGlyph(
                        entity.x,
                        entity.y,
                        "&",
                        "default",
                        bold=not entity.met,
                    )
                ]
            return [FieldGlyph(entity.x, entity.y, "?", "yellow", bold=True)]
        if entity.tribe.is_elf and not stage2_high_elf:
            tone = "default"
        elif stage2_high_elf:
            tone = "red"
        elif d.monster_level(entity) <= player_attack:
            tone = (
                "yellow" if entity.tribe.effect == d.EFFECT_UNLOCK_TREASURE else "blue"
            )
        else:
            tone = "red"
        dim = (
            False
            if entity.tribe.is_elf
            else (entity.met if char == "M" else bool(dim_types and char in dim_types))
        )
        glyphs = [
            FieldGlyph(
                entity.x,
                entity.y,
                char,
                tone,
                bold=not (entity.tribe.is_elf and entity.met),
                dim=dim,
            )
        ]
        if entity.empowered > 1:
            marker = "'" if entity.empowered == 2 else '"'
            glyphs.append(
                FieldGlyph(entity.x + 1, entity.y, marker, tone, bold=True, dim=dim)
            )
        return glyphs
    if isinstance(entity, d.Collapse):
        return [FieldGlyph(entity.x, entity.y, "?", "yellow", bold=True)]
    if isinstance(entity, d.Treasure):
        if entity.unlocked:
            return [
                FieldGlyph(entity.x, entity.y, d.CHAR_TREASURE, "yellow", bold=True)
            ]
    return []
