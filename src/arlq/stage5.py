"""Stage 5 member trial and tutorial behavior."""

from . import defs as d
from .arlq import GameConfig
from .i18n import t
from .stage_types import Floor


STAGE5_MEMBER_TRIAL_MAP = """##################################################
#         #     #g    E #            ===   X     #
#       f #   f #       #            ===    X    #
# @  f  f   K f      R ?    v  G b b ===   X     #
#         #     #       #            ===    X    #
#         #     # X     #            ===   X     #
################################################ #
################################################ #
#                                                #
# ####################################           #
#                                    #  b  b  H  #
#################################### #           #
#                                    #           #
# ################################################
# ################################################
#          #####  A A A #     A A A #            #
#          #####        #           #            #
#   b   D  .  ?   A A A   J   A A A       F  T   #
#          #####        #           #            #
#          #####    A A #       A A #            #
##################################################
##################################################"""

STAGE5_MEMBER_TRIAL_LOWER_MAP = """##################################################
####################            ##################
####################            ##################
####################        ^   ##################
####################            ##################
####################            ##################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
##################################################
###########       ################################
###########       ################################
###########       ################################
###########       ################################
###########       ################################
##################################################
##################################################"""


class TrialDialogue(str):
    """A tutorial line drawn in a small speech bubble."""


def trial_dialogue_lines(text: str, width: int, *, on_left: bool = False) -> list[str]:
    """Wrap dialogue into a one-line bubble or a two-line speech balloon."""
    width = max(8, width)
    words = text.split()
    lines = [""]
    for word in words:
        candidate = f"{lines[-1]} {word}".strip()
        if len(candidate) <= width or not lines[-1]:
            lines[-1] = candidate
        elif len(lines) == 1:
            lines.append(word)
        else:
            lines[-1] += f" {word}"
    if on_left:
        if len(lines) == 1:
            return [f"{lines[0]} >"]
        return [lines[0] + " " + chr(92), lines[1] + " /"]
    if len(lines) == 1:
        return [f"< {lines[0]}"]
    return [f"/ {lines[0]}", f"\\ {lines[1]}"]


TRIAL_MEMBER_LINES = {
    d.MEMBER_KNIGHT: "K: Two at once can be a lot. I can lend a hand.",
    d.MEMBER_ROGUE: "R: I can see through most traps.",
    d.MEMBER_GUARDIAN: "G: My enchanted shield can protect against barriers and spikes.",
    d.MEMBER_HEALER: "H: Take a healer on a long journey.",
    d.MEMBER_DUNGEON_EXPLORER: "D: I know caves. I can climb out of pits.",
    d.MEMBER_JESTER: "J: Here's a curious dance to help you gain experience.",
}


def trial_member_line(current: Floor, player: d.Player) -> str | None:
    for entity in current.entities:
        if (
            isinstance(entity, d.PartyMember)
            and entity.role not in player.joined_members
            and abs(entity.x - player.x) + abs(entity.y - player.y) == 1
            and entity.role in TRIAL_MEMBER_LINES
        ):
            return TrialDialogue(t(TRIAL_MEMBER_LINES[entity.role]))
    return None


def build_member_trial(
    config: GameConfig | None = None,
) -> tuple[list[Floor], d.Player]:
    """Build both Stage 5 tutorial floors from their in-code ASCII maps."""
    member_roles = {glyph: role for role, glyph in d.MEMBER_GLYPHS.items()}

    def check_map(rows: list[str], label: str) -> None:
        if len(rows) != d.FIELD_HEIGHT or any(len(row) > d.FIELD_WIDTH for row in rows):
            raise ValueError(f"{label} ASCII map dimensions do not match the field")

    upper_rows = STAGE5_MEMBER_TRIAL_MAP.splitlines()
    lower_rows = STAGE5_MEMBER_TRIAL_LOWER_MAP.splitlines()
    check_map(upper_rows, "Stage 5 floor 1")
    check_map(lower_rows, "Stage 5 floor 2")

    def blank_field(rows: list[str]) -> list[list[str]]:
        wall_end = min(d.FIELD_WIDTH, max(map(len, rows)) + 2)
        return [
            [d.CHAR_WALL] * wall_end
            + [d.CHAR_FLOOR] * (d.FIELD_WIDTH - wall_end)
            for _ in range(d.FIELD_HEIGHT)
        ]

    upper_field = blank_field(upper_rows)
    upper_seen = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    upper_entities: list[d.Entity] = []
    upper_barriers: set[d.Point] = set()
    upper_gates: dict[d.Point, str] = {}
    start = upper_stair = None
    upper_pits: list[d.Point] = []

    for y, row in enumerate(upper_rows):
        for x, glyph in enumerate(row):
            point = (x, y)
            if glyph == d.CHAR_WALL:
                continue
            if glyph == "=":
                upper_field[y][x] = d.CHAR_BARRIER
                upper_barriers.add(point)
                continue
            if glyph == d.CHAR_CALTROP:
                upper_field[y][x] = d.CHAR_CALTROP
                continue
            upper_field[y][x] = d.CHAR_FLOOR
            if glyph == "@":
                start = point
            elif glyph == d.CHAR_STAIRS_DOWN:
                upper_stair = point
                upper_field[y][x] = d.CHAR_STAIRS_DOWN
            elif glyph == ".":
                upper_field[y][x] = d.CHAR_HIDDEN_D_GATE
                upper_gates[point] = d.CHAR_D_GATE
            elif glyph == "?":
                upper_pits.append(point)
                upper_entities.append(d.Collapse(x, y))
            elif glyph in member_roles:
                upper_entities.append(
                    d.PartyMember(x, y, member_roles[glyph], origin_floor=0)
                )
            elif glyph == "T":
                upper_entities.append(d.Treasure(x, y, "TF"))
            elif glyph in d.CHAR_TO_MONSTER_TRIBE:
                upper_entities.append(d.Monster(x, y, d.CHAR_TO_MONSTER_TRIBE[glyph]))
            elif glyph != d.CHAR_FLOOR:
                raise ValueError(f"Unsupported Stage 5 floor 1 glyph: {glyph!r}")

    if start is None or upper_stair is None or not upper_pits or not upper_gates:
        raise ValueError("Stage 5 floor 1 needs @, v, ?, and . markers")

    lower_field = blank_field(lower_rows)
    lower_seen = [[0] * d.FIELD_WIDTH for _ in range(d.FIELD_HEIGHT)]
    lower_barriers: set[d.Point] = set()
    lower_gates: dict[d.Point, str] = {}
    lower_stair = None
    for y, row in enumerate(lower_rows):
        for x, glyph in enumerate(row):
            point = (x, y)
            if glyph == d.CHAR_WALL:
                continue
            if glyph == "=":
                lower_field[y][x] = d.CHAR_BARRIER
                lower_barriers.add(point)
            elif glyph == d.CHAR_CALTROP:
                lower_field[y][x] = d.CHAR_CALTROP
            elif glyph == "^":
                lower_stair = point
                lower_field[y][x] = d.CHAR_STAIRS_UP
            elif glyph == ".":
                lower_field[y][x] = d.CHAR_HIDDEN_D_GATE
                lower_gates[point] = d.CHAR_D_GATE
            elif glyph == d.CHAR_FLOOR:
                lower_field[y][x] = d.CHAR_FLOOR
            else:
                raise ValueError(f"Unsupported Stage 5 floor 2 glyph: {glyph!r}")

    if lower_stair is None or any(
        lower_field[y][x] != d.CHAR_FLOOR for x, y in upper_pits
    ):
        raise ValueError("Stage 5 floor 2 needs ^ and open floor below every pit")

    upper = Floor(
        upper_field,
        upper_entities,
        upper_seen,
        start,
        upper_stair,
        None,
        up_stairs=[start],
        down_stairs=[upper_stair],
        d_gates=upper_gates,
        persistent_barriers=upper_barriers,
        adjacent_monster_exemptions={
            (x, y)
            for y, row in enumerate(upper_rows)
            for x, glyph in enumerate(row)
            if glyph == "X"
        },
    )
    lower = Floor(
        lower_field,
        [],
        lower_seen,
        upper_pits[0],
        lower_stair,
        None,
        up_stairs=[lower_stair],
        collapse_landings=set().union(
            *(d.collapse_footprint(point) for point in upper_pits)
        ),
        d_gates=lower_gates,
        persistent_barriers=lower_barriers,
    )
    player = d.Player(*start, 25, d.LP_INIT)
    player.rescue_stage = True
    player.treasure_stage = True
    return [upper, lower], player
