"""Replay turn events with the existing frontend effects."""

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
            vortex = getattr(ui, "draw_vortex_effect", None)
            if event.won and vortex is not None:
                for target, point in event.targets:
                    if target.glyph == "V":
                        vortex(point)
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


def play_defeat_effects(ui, result: "TurnResult") -> None:
    """Play post-move boss and core effects on the new floor."""
    for event in result.events:
        if not isinstance(event, Combat) or event.floor != result.floor_after or not event.won:
            continue
        for point, method in ((event.boss_at, "draw_boss_afterglow"),
                              (event.core_at, "draw_core_burst")):
            effect = getattr(ui, method, None)
            if point is not None and effect is not None:
                effect(point)
