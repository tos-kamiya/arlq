"""Sprite presentation and frame pacing without blocking input dispatch."""

from dataclasses import replace
from time import monotonic

from .game_events import BarrierHit, Combat, FloorChanged, Rewound
from .presentation import play_turn_events


class Presenter:
    def __init__(self, *, clock=monotonic, wait=None):
        self.clock = clock
        self.wait = wait or self._wait_for_events

    @staticmethod
    def _wait_for_events(seconds):
        import pyglet

        pyglet.app.platform_event_loop.step(seconds)

    @staticmethod
    def visible_events(ui, result, view):
        """Use the old floor's visibility until a transition reaches the new one."""
        visibility = {result.floor_after: view.get("cur_torched")}
        if result.floor_before != result.floor_after:
            previous = getattr(ui, "_last_stage_draw", None)
            previous_view = previous[1] if previous is not None else {}
            visibility[result.floor_before] = (
                previous_view.get("cur_torched")
                if not previous_view.get("floor_view")
                else None
            )
        floor = result.floor_before
        events = []

        def visible(point):
            grid = visibility.get(floor)
            x, y = point
            return (
                grid is not None
                and 0 <= y < len(grid)
                and 0 <= x < len(grid[y])
                and bool(grid[y][x])
            )

        for event in result.events:
            if event.floor != floor:
                continue
            if isinstance(event, FloorChanged):
                events.append(event)
                floor = event.to_floor
            elif isinstance(event, Rewound):
                events.append(event)
                floor = result.floor_after
            elif isinstance(event, BarrierHit):
                if visible(event.at):
                    events.append(event)
            elif isinstance(event, Combat):
                if event.won:
                    targets = [
                        (entity, point)
                        for entity, point in event.targets
                        if visible(point)
                    ]
                    if targets:
                        events.append(replace(event, targets=targets))
                else:
                    positions = [
                        point
                        for point in event.party_positions or [event.attacker]
                        if visible(point)
                    ]
                    if positions:
                        events.append(replace(event, party_positions=positions))
        return events

    def play(self, ui, result, view):
        events = self.visible_events(ui, result, view)
        was_active = ui._stage_input_active
        ui._stage_input_active = True
        try:
            for event in events:
                if ui._closed:
                    break
                ui._pump()
                if ui._closed:
                    break
                # Dispatch one event at a time so closing a window stops the
                # remaining effects, while queued keys stay for the next input.
                single = replace(result, events=[event], floor_before=event.floor)
                play_turn_events(ui, single, view["player"], view["stage_num"])
        finally:
            ui._stage_input_active = was_active
        return not ui._closed

    @staticmethod
    def _layout(ui):
        return tuple(
            getattr(ui, name, None)
            for name in (
                "scale",
                "window_width",
                "window_height",
                "_horizontal_scroll_px",
            )
        )

    def hold(self, ui, seconds, create):
        """Keep an effect alive, pumping input and rebuilding it after resize."""
        if seconds <= 0 or ui._closed:
            return
        was_active = ui._stage_input_active
        ui._stage_input_active = True
        objects = []
        try:
            deadline = self.clock() + seconds
            objects = create()
            layout = self._layout(ui)
            ui._flip()
            while not ui._closed and self.clock() < deadline:
                ui._pump()
                if ui._closed:
                    break
                if self._layout(ui) != layout:
                    for obj in objects:
                        obj.delete()
                    objects = []
                    objects = create()
                    layout = self._layout(ui)
                ui._flip()
                remaining = deadline - self.clock()
                if remaining > 0:
                    self.wait(min(1 / 60, remaining))
        finally:
            for obj in objects:
                obj.delete()
            ui._stage_input_active = was_active
