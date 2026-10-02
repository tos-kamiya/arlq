"""Command-line argument handling and application startup."""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from appdirs import user_cache_dir

from . import arlq as game
from . import defs as d
from .__about__ import __version__
from .i18n import get_language, set_language
from .trace import (
    ReplayUI,
    TraceRecorder,
    checkpoint_turn_index,
    load_trace,
    timestamped_trace_path,
)


def _prepare_cli_session(terminal_only=False):
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )
    general = parser.add_argument_group("General options")
    gui = None if terminal_only else parser.add_argument_group("GUI options")
    terminal = parser.add_argument_group("Terminal options")
    dev = parser.add_argument_group("Development options")
    if terminal_only:
        parser.set_defaults(terminal=True)

    general.add_argument(
        "--rematch",
        action="store_true",
        help="Replay the last stage with the same seed.",
    )
    general.add_argument(
        "--stage", action="store", type=int, default=0, help="Stage (1, 2, 3, or 4)."
    )
    general.add_argument("--seed", action="store", help="Seed value or seed string")
    g = general.add_mutually_exclusive_group()
    g.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    g.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    general.add_argument(
        "-n", "--narrower-corridors", action="store_true", help="Narrower corridors."
    )
    if not terminal_only:
        terminal.add_argument(
            "--terminal",
            "--curses",
            dest="terminal",
            action="store_true",
            help="Use the Blessed terminal UI (--curses is a deprecated alias).",
        )
    terminal.add_argument(
        "--dots",
        action="store_true",
        help="Use dots instead of background colors for unexplored areas in the terminal UI.",
    )
    general.add_argument(
        "--lang",
        choices=["auto", "en", "ja"],
        default="auto",
        help="UI message language ('auto' detects it from the locale; default: auto).",
    )
    general.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )
    if gui is not None:
        gui.add_argument(
            "--scale",
            type=float,
            metavar="FACTOR",
            help="GUI display scale (0.5 to 4.0); saves the value for future GUI starts.",
        )
        gui.add_argument(
            "--key-repeat-interval",
            type=lambda value: None if value.lower() == "none" else float(value),
            metavar="SECONDS|none",
            default=argparse.SUPPRESS,
            help="GUI movement repeat delay and interval (0.1 to 1.0 seconds, or none); saves for future GUI starts.",
        )
        gui.add_argument(
            "--auto-repeat-stop",
            action=argparse.BooleanOptionalAction,
            default=argparse.SUPPRESS,
            help="Stop held movement near hazards and after encounters (saves for future GUI starts).",
        )
    dev.add_argument("--debug-show-entities", action="store_true", help="Debug option.")
    dev.add_argument(
        "--trap-test", action="store_true", help="Start the trap test stage."
    )
    dev.add_argument(
        "--trace",
        dest="trace_path",
        metavar="PATH",
        help="Replay a trace in the UI without saving replay output. Use 'auto' for the cached last trace.",
    )
    dev.add_argument(
        "--continue",
        dest="continue_trace",
        action="store_true",
        help="With --trace, ignore recorded Q inputs and continue with live input when replay input ends.",
    )
    dev.add_argument(
        "--output",
        dest="trace_output",
        metavar="PATH",
        help="Also export a normal or continued session trace to PATH; cache copies are saved too.",
    )
    dev.add_argument(
        "--to-checkpoint",
        type=int,
        dest="checkpoint_index",
        metavar="INDEX",
        help="With --trace, replay through checkpoint event INDEX (positive from start, negative from end).",
    )
    dev.add_argument(
        "--rewind",
        type=int,
        dest="rewind_index",
        metavar="INDEX",
        help="Shortcut for --to-checkpoint INDEX --continue.",
    )
    replay_speed = dev.add_mutually_exclusive_group()
    replay_speed.add_argument(
        "--replay-interval",
        type=game.parse_replay_interval,
        metavar="SECONDS",
        default=0.0,
        help="Delay between turns during trace replay in either UI (default: 0, fastest).",
    )
    replay_speed.add_argument(
        "--replay-fast-forward",
        action="store_true",
        dest="replay_fast_forward",
        help="Replay a trace without intermediate screen updates, then show its final state.",
    )

    args = parser.parse_args()

    if args.rewind_index is not None:
        if args.checkpoint_index is not None:
            parser.error("--rewind cannot be combined with --to-checkpoint")
        if args.continue_trace:
            print(
                "Warning: --continue is implied by --rewind and has no additional effect.",
                file=sys.stderr,
            )
        args.checkpoint_index = args.rewind_index
        args.continue_trace = True

    set_language(args.lang)

    if args.trap_test:
        if args.stage or args.seed is not None or args.trace_path or args.trace_output:
            parser.error(
                "--trap-test cannot be combined with --stage, --seed, or trace options"
            )
        args.stage = 6
    elif args.stage != 0 and args.stage not in d.PUBLIC_STAGE_NUMBERS:
        parser.error("--stage must be 1, 2, 3, or 4")

    if args.continue_trace and not args.trace_path:
        parser.error("--continue requires --trace")
    if args.checkpoint_index is not None and not args.trace_path:
        option = "--rewind" if args.rewind_index is not None else "--to-checkpoint"
        parser.error(f"{option} requires --trace")
    if args.replay_fast_forward and not args.trace_path:
        parser.error("--replay-fast-forward requires --trace")
    if (
        args.trace_path
        and args.trace_output
        and not args.continue_trace
        and args.checkpoint_index is None
    ):
        parser.error("--output with --trace requires --continue")

    trace_data = None
    trace_input_path = None
    if args.trace_path:
        if (
            args.rematch
            or args.seed is not None
            or args.stage
            or args.large_torch
            or args.small_torch
            or args.narrower_corridors
        ):
            parser.error(
                "--trace cannot be combined with --seed, --stage, --rematch, -T, -t, or -n"
            )

        requested_trace_path = (
            Path(args.trace_path) if args.trace_path != "auto" else None
        )
        trace_input_path = (
            game.last_trace_path()
            if requested_trace_path is None
            or (
                requested_trace_path.name == "last-trace.json"
                and not requested_trace_path.exists()
            )
            else requested_trace_path
        )
        try:
            trace_data = load_trace(trace_input_path)
        except (OSError, ValueError) as error:
            sys.exit(f"Error: cannot load trace file {trace_input_path}: {error}")

        if args.checkpoint_index is not None:
            try:
                rewind_turn_index = checkpoint_turn_index(
                    trace_data["turns"], args.checkpoint_index
                )
            except ValueError as error:
                parser.error(str(error))
            trace_data = dict(trace_data)
            trace_data["turns"] = trace_data["turns"][: rewind_turn_index + 1]

        if trace_data.get("arlq_version") != __version__:
            print(
                f"Warning: trace was recorded with arlq {trace_data.get('arlq_version')}, "
                f"current version is {__version__}.",
                file=sys.stderr,
            )

        params = trace_data["params"]
        args.seed = params["seed"]
        game.parse_seed_string(args, args.seed, enforce_version=False)
        if args.lang == "auto":
            set_language(params.get("lang", "auto"))
    else:
        if args.rematch and args.seed is not None:
            parser.error("--rematch cannot be combined with --seed")

        if args.rematch:
            try:
                rematch_stage, args.seed = game.read_last_seed()
            except ValueError as error:
                parser.error(str(error))
            if args.stage:
                print(
                    f"Warning: --rematch uses saved stage {rematch_stage}; ignoring --stage {args.stage}.",
                    file=sys.stderr,
                )
            args.stage = rematch_stage
        elif args.seed is not None:
            # Check if any conflicting flags are provided
            if any(
                [
                    args.stage,
                    args.large_torch,
                    args.small_torch,
                    args.narrower_corridors,
                ]
            ):
                exit(
                    "Error: option --seed is mutually exclusive to options --stage, -T, -t, -n"
                )
            if isinstance(args.seed, str) and args.seed.startswith("v"):
                game.parse_seed_string(args, args.seed)
            else:
                try:
                    args.seed = int(args.seed)
                except (TypeError, ValueError):
                    parser.error("--seed must be an integer or a versioned seed string")
        else:
            args.seed = int(time.time()) % 100000

    game.rand.set_seed(args.seed)
    seed_str = game.generate_seed_string(args)
    game_config = game.game_config_from_args(args)

    trace_recorder: Optional[TraceRecorder] = None
    if trace_data is None or args.continue_trace or args.checkpoint_index is not None:
        trace_recorder = TraceRecorder(
            params={
                "stage": args.stage,
                "seed": seed_str,
                "large_torch": args.large_torch,
                "narrower_corridors": args.narrower_corridors,
                "lang": get_language(),
            }
        )

    return args, trace_data, seed_str, game_config, trace_recorder


def main(terminal_only=False):
    args, trace_data, seed_str, game_config, trace_recorder = _prepare_cli_session(
        terminal_only=terminal_only
    )

    def play(ui) -> None:
        if trace_data is not None:
            replay_ui = ReplayUI(
                trace_data["turns"],
                args.stage,
                ui,
                draw_interval=args.replay_interval,
                continue_play=args.continue_trace,
                final_state_only=args.replay_fast_forward,
            )
            game.run_game(
                replay_ui,
                seed_str,
                args.stage,
                args.debug_show_entities,
                None,
                trace=trace_recorder,
                config=game_config,
            )
        else:
            game.run_game(
                ui,
                seed_str,
                args.stage,
                args.debug_show_entities,
                args.seed,
                trace=trace_recorder,
                config=game_config,
            )

    if args.terminal:
        from blessed import Terminal

        from .blessed_funcs import BlessedUI

        term = Terminal()
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            play(BlessedUI(term, dots=args.dots))
    else:
        from .pyglet_funcs import PygletUI

        ui = PygletUI(args.scale)
        if args.scale is not None:
            from .pyglet_funcs import save_ui_scale

            save_ui_scale(ui.scale)
        if hasattr(args, "key_repeat_interval"):
            ui.set_key_repeat_interval(args.key_repeat_interval)
        if hasattr(args, "auto_repeat_stop"):
            ui.set_auto_repeat_stop_enabled(args.auto_repeat_stop)
        play(ui)

    if trace_recorder is not None:
        cache_dir = Path(user_cache_dir("arlq"))
        archive_path = timestamped_trace_path(cache_dir)
        output_paths = [archive_path, game.last_trace_path()]
        if args.trace_output:
            output_paths.append(Path(args.trace_output))
        trace_recorder.write_outputs(output_paths)
