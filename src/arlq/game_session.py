"""UI-independent world, turn processing, and display state for one game."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import defs as d
from . import game_engine as engine
from .arlq import GameConfig
from .utils import rand


@dataclass
class TurnResult:
    consumed: bool
    message: tuple[int, str] | None
    stop_repeat: bool
    floor_before: int
    floor_after: int


@dataclass
class LegacyHooks:
    combat_effect: Callable[..., None] | None = None
    barrier_effect: Callable[..., None] | None = None
    rewind_transition: Callable[..., None] | None = None
    floor_transition: Callable[..., None] | None = None
    stop_movement_repeat: Callable[..., None] | None = None

    @classmethod
    def from_ui(cls, ui):
        def barrier(session):
            view = session.view(map_mode=getattr(ui, "map_mode", False))
            view["message"] = None
            ui.draw_stage(**view)
            effect = getattr(ui, "draw_combat_effect", None)
            if effect is not None:
                effect((session.player.x, session.player.y), False)

        return cls(
            getattr(ui, "draw_combat_effect", None),
            barrier,
            getattr(ui, "draw_rewind_transition", None),
            getattr(ui, "draw_floor_transition", None),
            getattr(ui, "stop_movement_repeat", None),
        )


class GameSession:
    """Own a game without polling input or running a display loop."""

    def __init__(
        self,
        stage_num: int = 3,
        config: GameConfig | None = None,
        *,
        seed_str="",
        trace=None,
        debug_show_entities=False,
        hooks=None,
    ):
        # Keep the existing builders in game_engine so their callers and test
        # substitutions keep using the same implementations.
        self.config = config if config is not None else GameConfig()
        self.stage_num = stage_num
        self.initial_seed = rand.get_seed()
        self.single_floor_stage = stage_num in (1, 2)
        if self.single_floor_stage:
            self.floors, self.player = engine.build_single_floor(self.config, stage_num)
        elif stage_num == 6:
            self.floors, self.player = engine.stage6.build(self.config)
        elif stage_num == 5:
            self.floors, self.player = engine.stage5.build_member_trial(self.config)
        else:
            self.floors, self.player = engine.build(
                self.config.corridor_h_width,
                self.config.corridor_v_width,
                stage_num,
            )
        for floor_data in self.floors:
            floor_data.update_outer_wall_decor()
        self.player.known_monsters = set(d.INITIALLY_KNOWN_MONSTERS)
        self.player.boss_defeated = False
        self.player.dungeon_core_destroyed = False
        self.player.treasure_collected = False

        self.seed_str = seed_str
        self.trace = trace
        self.debug_show_entities = debug_show_entities
        self.hooks = hooks or LegacyHooks()
        self.phase = "playing"
        self.outcome = None
        self.replay_context = (
            engine.ReplayContext(self.stage_num, self.initial_seed, self.config)
            if not self.single_floor_stage
            else None
        )
        self.game_start_turn = 0
        self.loop_anchor_turn = 0
        self.has_rewound = False
        self.floor = [0]
        self.checkpoint = [self.floors[0].up]
        self.player.current_floor = 0
        self.operation_path: list[tuple[int, d.Point]] = [
            (self.floor[0], (self.player.x, self.player.y))
        ]
        self.loop_trail_by_floor: dict[int, set[d.Point]] = {}
        self.loop_trail_expires_at = 0
        if self.trace is not None:
            self.trace.set_start_state(self.player, self.floor[0])
        self.trace_seen_recorded = (
            [engine.deepcopy(floor_data.seen) for floor_data in self.floors]
            if self.trace is not None
            else []
        )
        self.trace_known_monsters_recorded = set(self.player.known_monsters)
        self.queue: engine.Counter[tuple[int, str]] = engine.Counter()
        self.turn = 0
        (message_ticks, start_text) = d.STAGE_START_MESSAGES[self.stage_num]
        self.message: tuple[int, str] = (
            message_ticks,
            engine.trp(start_text, 1) if start_text else "",
        )

    @property
    def floor_index(self):
        return self.floor[0]

    @property
    def floor_count(self):
        return len(self.floors)

    def view(self, view_floor=None, *, map_mode=False, farthest_preview=False):
        """Build draw_stage arguments, updating discoveries during play."""
        if view_floor is None:
            view_floor = self.floor[0]
        current = self.floors[self.floor[0]]
        display_floor = self.floors[view_floor]
        cur = (
            engine.observe_world(
                self.floors, self.player, self.floor[0], self.config.torch_radius
            )
            if self.phase == "playing"
            else engine.get_torched(self.player, self.config.torch_radius)
        )
        floor_view = view_floor != self.floor[0]
        show_entities = self.debug_show_entities or map_mode
        reachable_cells: set[d.Point] = set()
        if farthest_preview and (not floor_view):
            reachable_cells = engine.reachable_known_cells(
                current.field,
                current.seen,
                cur,
                current.entities,
                self.player,
                {
                    (x, y)
                    for (y, row) in enumerate(current.field)
                    for (x, cell) in enumerate(row)
                    if cell == d.CHAR_D_GATE
                },
            )
        render_entities = [self.player, *display_floor.entities]
        known_types = self.player.known_monsters
        no_current_visibility = [
            [0] * len(display_floor.field[0]) for _ in display_floor.field
        ]
        stage_draw_options = engine._stage_draw_options(
            self.stage_num,
            self.floors,
            view_floor,
            self.single_floor_stage,
            show_floor_label=self.phase == "playing",
        )
        if stage_draw_options:
            stage_draw_options["floor_view"] = floor_view
        if self.player.lp <= 0 and self.phase == "playing":
            self.message = (-1, engine.trp(">> Collapsed from hunger! <<", 9))
        options = dict(
            turn=self.turn,
            game_start_turn=self.game_start_turn if self.has_rewound else None,
            player=self.player,
            entities=render_entities,
            field=engine._field_for_display(self.floors, view_floor, self.player),
            cur_torched=no_current_visibility if floor_view else cur,
            torched=display_floor.seen,
            known_types=known_types,
            show_entities=show_entities,
            debug_show_entities=self.debug_show_entities,
            stage_num=self.stage_num,
            message=self.message[1],
            checkpoint=self.checkpoint[0],
            decor=display_floor.decor,
            respawn_glows=engine.respawn_glow_cells(display_floor),
            d_gates=display_floor.d_gates,
            reachable_cells=reachable_cells,
            loop_trail_markers=self.loop_trail_by_floor.get(self.floor[0], set())
            if not floor_view and self.turn < self.loop_trail_expires_at
            else set(),
            **stage_draw_options,
        )
        if self.phase == "game_over":
            options["extra_keys"] = True
            options["floor_view"] = floor_view
            options.pop("d_gates")
            options.pop("reachable_cells")
            options.pop("loop_trail_markers")
        return options

    def step(self, move, *, repeat=False, auto_repeat_stop=True, map_mode=False):
        """Resolve one movement and its turn end without polling input."""
        floor_before = self.floor[0]
        if self.phase == "playing" and self.player.lp <= 0:
            self._finish()
        if self.phase != "playing" or move == (0, 0):
            return TurnResult(False, self.message, False, floor_before, floor_before)
        stop_repeat = False
        # Discovery must also advance when no renderer calls view().
        engine.observe_world(
            self.floors, self.player, self.floor[0], self.config.torch_radius
        )
        current = self.floors[self.floor[0]]
        show_entities = self.debug_show_entities or map_mode
        known_types = self.player.known_monsters
        if self.message[0] == -2:
            self.message = (-1, "")
        rogue_spotted_danger = False
        if d.has_member(self.player, d.MEMBER_ROGUE):
            destination = (self.player.x + move[0], self.player.y + move[1])
            if engine.stage56.rogue_danger(current, destination):
                rogue_spotted_danger = True
                if self.replay_context is not None:
                    self.replay_context.rogue_checks.setdefault(
                        len(self.replay_context.operations), []
                    ).append(destination)
                stop_repeat = True
                if self.hooks.stop_movement_repeat is not None:
                    self.hooks.stop_movement_repeat()
                self.message = (
                    5,
                    engine.trp("-- Rogue spotted danger. Movement repeat stopped.", 5),
                )
        repeat_stop_enabled = auto_repeat_stop
        if (
            repeat_stop_enabled
            and (not rogue_spotted_danger)
            and repeat
            and engine._should_stop_movement_repeat(
                move,
                current,
                self.player,
                show_all_entities=show_entities,
                known_types=known_types,
            )
        ):
            stop_repeat = True
            if self.hooks.stop_movement_repeat is not None:
                self.hooks.stop_movement_repeat()
            return TurnResult(False, self.message, True, floor_before, floor_before)
        if self.trace is not None:
            key = engine.DIR_TO_KEY.get(move)
            if key is None:
                raise RuntimeError(
                    "--trace does not support non-cardinal (e.g. diagonal joystick) movement"
                )
            self.trace.begin_turn(key)
        if self.replay_context is not None:
            self.replay_context.save_snapshot(
                len(self.replay_context.operations),
                self.floors,
                self.player,
                self.floor,
                self.checkpoint,
                self.queue,
            )
            self.replay_context.prune_snapshots(self.game_start_turn)
            self.replay_context.operations.append(move)
            self.game_start_turn += 1
            self.replay_context.turn_to_operation[self.game_start_turn] = len(
                self.replay_context.operations
            )
        repeat_stop_reasons: set[str] | None = (
            set() if repeat_stop_enabled or self.stage_num == 5 else None
        )
        floor_before_step = self.floor[0]
        point_before_step = (self.player.x, self.player.y)
        step_result = engine._process_multi_floor_turn(
            move,
            self.floors,
            self.player,
            self.floor,
            self.checkpoint,
            self.queue,
            self.turn,
            stage_num=self.stage_num,
            trace=self.trace,
            repeat_stop_reasons=repeat_stop_reasons,
            combat_effect=self.hooks.combat_effect,
            barrier_effect=(lambda: self.hooks.barrier_effect(self))
            if self.hooks.barrier_effect
            else None,
        )
        if self.replay_context is not None:
            self.operation_path.append((self.floor[0], (self.player.x, self.player.y)))
        if repeat_stop_reasons and (
            repeat_stop_enabled or "member_dialogue" in repeat_stop_reasons
        ):
            stop_repeat = True
            if self.hooks.stop_movement_repeat is not None:
                self.hooks.stop_movement_repeat()
        if isinstance(step_result, engine._RewindRequest):
            assert self.replay_context is not None, (
                "Loop contact requires recorded inputs"
            )
            operation_count = len(self.replay_context.operations)
            (rewind_turn, rewind_operation) = self.replay_context.prepare_loop_rewind(
                self.game_start_turn, self.loop_anchor_turn
            )
            self.loop_trail_by_floor.clear()
            self.loop_trail_expires_at = self.turn + d.LOOP_TRAIL_TURNS + 1
            for trail_floor, position in self.operation_path[
                rewind_operation + 1 : operation_count + 1
            ]:
                self.loop_trail_by_floor.setdefault(trail_floor, set()).add(position)
            transition_message = engine.trp(
                "-- Time folds back to the beginning of the recorded past.", 9
            )
            show_transition = self.hooks.rewind_transition
            if show_transition is not None:
                show_transition(transition_message)
            rewind_message = engine._rewind(
                self.floors,
                self.player,
                self.floor,
                self.checkpoint,
                self.queue,
                self.replay_context,
                operation_count=operation_count,
                loop_floor_index=step_result.floor_index,
            )
            self.operation_path[operation_count] = (
                self.floor[0],
                (self.player.x, self.player.y),
            )
            self.player.lp += d.movement_lp_cost(self.player)
            self.replay_context.anchor_loop_rewind(rewind_turn)
            self.game_start_turn = rewind_turn
            self.loop_anchor_turn = rewind_turn
            self.has_rewound = True
            event_message: tuple[int, str] | None = (5, rewind_message)
        else:
            event_message = step_result
            transition = engine.floor_transition_kind(
                self.floors,
                floor_before_step,
                self.floor[0],
                (self.player.x, self.player.y),
            )
            show_floor_transition = self.hooks.floor_transition
            if transition is not None and show_floor_transition is not None:
                show_floor_transition(transition, self.player, self.player.floor_exit)
        self.player.current_floor = self.floor[0]
        if event_message is not None and (
            event_message[0] == -2
            or engine.prefer_event_message(self.message[1], event_message[1])
            == event_message[1]
        ):
            self.message = event_message
        if self.trace is not None:
            self.trace.set_player(self.player, floor_index=self.floor[0])
            seen_added_count = sum(
                1
                for (floor_data, previous_seen) in zip(
                    self.floors, self.trace_seen_recorded, strict=True
                )
                for (y, row) in enumerate(floor_data.seen)
                for (x, is_seen) in enumerate(row)
                if is_seen and (not previous_seen[y][x])
            )
            self.trace.record_state_changes(
                seen_added_count,
                list(self.player.known_monsters - self.trace_known_monsters_recorded),
            )
            self.trace_seen_recorded = [
                engine.deepcopy(floor_data.seen) for floor_data in self.floors
            ]
            self.trace_known_monsters_recorded = set(self.player.known_monsters)
        self.turn += 1
        self.player.lp -= d.movement_lp_cost(self.player)
        if not isinstance(step_result, engine._RewindRequest):
            engine.bridgehead.recover_at_bridgehead(
                self.floors,
                self.player,
                self.floor[0],
                floor_before_step,
                point_before_step,
            )
        if self.trace is not None:
            self.trace.set_turn_end_lp(self.player.lp)
            self.trace.commit_turn()
        if self.player.stage_won:
            self._finish()
            return TurnResult(
                True, self.message, stop_repeat, floor_before, self.floor[0]
            )
        if (
            self.stage_num == 6
            and (not self.player.dungeon_core_destroyed)
            and (self.turn >= d.STAGE6_TURN_LIMIT)
        ):
            stop_repeat = True
            if self.hooks.stop_movement_repeat is not None:
                self.hooks.stop_movement_repeat()
            self._finish()
            return TurnResult(
                True, self.message, stop_repeat, floor_before, self.floor[0]
            )
        if (
            self.stage_num == 6
            and (not self.player.dungeon_core_destroyed)
            and (d.STAGE6_TURN_LIMIT - self.turn == 500)
        ):
            self.message = (
                engine.MESSAGE_TICKS,
                engine.trp(
                    "-- The Dungeon Core is swelling; its rampage draws near!", 7
                ),
            )
        if self.player.lp <= 0:
            stop_repeat = True
            if self.hooks.stop_movement_repeat is not None:
                self.hooks.stop_movement_repeat()
            self._finish()
        return TurnResult(True, self.message, stop_repeat, floor_before, self.floor[0])

    def _finish(self):
        self.phase = "game_over"
        self.outcome = (
            "win"
            if self.player.stage_won
            else "time_up"
            if self.stage_num == 6
            and (not self.player.dungeon_core_destroyed)
            and (self.turn >= d.STAGE6_TURN_LIMIT)
            else "lose"
        )
        won = self.player.stage_won
        if self.trace is not None:
            self.trace.set_outcome("win" if won else "lose")
        if (
            not won
            and self.stage_num == 6
            and (not self.player.dungeon_core_destroyed)
            and (self.turn >= d.STAGE6_TURN_LIMIT)
        ):
            self.message = (
                -1,
                engine.trp(">> The Dungeon Core ran wild and the capital fell! <<", 9),
            )
        elif not won:
            self.message = (-1, engine.trp(">> Collapsed from hunger! <<", 9))
        else:
            self.message = (-1, engine.trp(">> Treasure chest obtained! <<", 9))

    def quit_check(self):
        cur = engine.observe_world(
            self.floors, self.player, self.floor[0], self.config.torch_radius
        )
        return engine._quit_check(self.floors, self.player, self.floor[0], cur)

    def quit(self, *, unfinished=False):
        if self.trace is not None:
            self.trace.record_quit()
            self.trace.set_outcome("unfinished" if unfinished else "quit")
        self.phase = "game_over"

    def game_over_message(self):
        return self.message[1]

    def seed_message(self):
        return engine.tr("SEED: {seed_str}").format(seed_str=self.seed_str)
