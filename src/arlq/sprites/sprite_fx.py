"""Sprite presentation and frame pacing without blocking input dispatch."""

from dataclasses import replace
from time import monotonic

from ..game_events import BarrierHit, Combat, FloorChanged, Rewound
from ..presentation import play_turn_events


def attack_facing(event):
    """The screen direction of a fight, from the player's cell toward the
    monster it ran into (the first target), or None without one."""
    if not event.targets:
        return None
    (tx, ty), (ax, ay) = event.targets[0][1], event.attacker
    dx, dy = tx - ax, ty - ay
    if abs(dx) >= abs(dy):
        return 'right' if dx > 0 else 'left' if dx < 0 else None
    return 'down' if dy > 0 else 'up'


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
                if isinstance(event, Combat):
                    # The slash is cut the way the player attacked.
                    ui._attack_facing = attack_facing(event) or 'up'
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

    def hold(self, ui, seconds, create, update=None):
        """Keep an effect alive, pumping input and rebuilding it after resize.

        With `update`, it is called as update(progress) before each frame,
        progress running from 0 to 1 over the effect's time, to animate it.
        """
        if seconds <= 0 or ui._closed:
            return
        was_active = ui._stage_input_active
        ui._stage_input_active = True
        objects = []
        try:
            start = self.clock()
            deadline = start + seconds
            objects = create()
            layout = self._layout(ui)

            def show():
                if update is not None:
                    update(min(1.0, max(0.0, (self.clock() - start) / seconds)))
                ui._flip()

            show()
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
                show()
                remaining = deadline - self.clock()
                if remaining > 0:
                    self.wait(min(1 / 60, remaining))
            if update is not None and not ui._closed:
                # End an animation on its last frame.
                update(1.0)
                ui._flip()
        finally:
            for obj in objects:
                obj.delete()
            ui._stage_input_active = was_active
