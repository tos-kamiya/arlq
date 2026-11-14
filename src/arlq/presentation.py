"""Replay turn events with the existing text frontend effects."""

from typing import TYPE_CHECKING

from . import defs as d
from .game_events import BarrierHit, Combat, FloorChanged, Rewound

if TYPE_CHECKING:
    from .game_session import TurnResult


def play_turn_events(
    ui, result: "TurnResult", player: d.Player, stage_num: int
) -> None:
    """Overlay effects on the previous frame before drawing the next turn."""
    floor = result.floor_before
    for event in result.events:
        if event.floor != floor:
            continue
        if isinstance(event, Combat):
            effect = getattr(ui, "draw_combat_effect", None)
            if effect is not None:
                positions = (
                    [point for _, point in event.targets]
                    if event.won
                    else event.party_positions or [event.attacker]
                )
                effect(positions if stage_num in (5, 6) else positions[0], event.won)
        elif isinstance(event, BarrierHit):
            effect = getattr(ui, "draw_combat_effect", None)
            if effect is not None:
                effect(event.at, False)
        elif isinstance(event, Rewound):
            effect = getattr(ui, "draw_rewind_transition", None)
            if effect is not None:
                effect(event.message)
            floor = result.floor_after
        elif isinstance(event, FloorChanged):
            effect = getattr(ui, "draw_floor_transition", None)
            if effect is not None:
                effect(event.kind, player, event.exit_point)
            floor = event.to_floor
