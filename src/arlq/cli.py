"""Command-line argument handling and application startup."""

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

from appdirs import user_cache_dir

from . import arlq as game
from . import defs as d
from . import settings
from .__about__ import __version__
from .i18n import get_language, set_language
from .trace import (
    ReplayUI,
    TraceRecorder,
    checkpoint_turn_index,
    load_trace,
    timestamped_trace_path,
    trace_includes_iris,
)


def _choice_seconds(choices):
    def parse(value):
        try:
            seconds = float(value)
            tenths = round(seconds * 10)
            seconds = tenths / 10 if abs(seconds * 10 - tenths) < 1e-9 else None
        except ValueError:
            seconds = None
        if seconds not in choices:
            raise argparse.ArgumentTypeError(
                "choose from " + ", ".join(f"{choice:.1f}" for choice in choices)
            )
        return seconds
    return parse


def _on_off(value):
    if value.lower() == "on":
        return True
    if value.lower() == "off":
        return False
    raise argparse.ArgumentTypeError("choose on or off")


# Option dest -> setting name, in Settings screen order.
SETTINGS_OPTIONS = {
    "scale": "scale",
    "key_repeat_interval": "key_repeat_interval",
    "auto_repeat_stop": "auto_repeat_stop_enabled",
    "combat_effect_duration": "combat_effect_seconds",
    "floor_transition_duration": "floor_transition_seconds",
    "character_bobbing": "idle_bob_enabled",
    "smooth_movement": "move_glide_enabled",
}


def _add_settings_arguments(group) -> None:
    """Options for the Settings screen items, available in all frontends."""
    suppress = argparse.SUPPRESS
    group.add_argument(
        "--scale", type=float, metavar="FACTOR", default=suppress,
        help="GUI display scale (0.5 to 4.0).",
    )
    group.add_argument(
        "--key-repeat-interval",
        type=lambda value: None if value.lower() == "none" else float(value),
        metavar="SECONDS|none", default=suppress,
        help="GUI movement repeat delay and interval (0.1 to 1.0 seconds, or none).",
    )
    group.add_argument(
        "--auto-repeat-stop", type=_on_off, metavar="on|off", default=suppress,
        help="Stop held movement near known hazards and entities.",
    )
    group.add_argument(
        "--combat-effect-duration",
        type=_choice_seconds(d.COMBAT_EFFECT_SECONDS_CHOICES),
        metavar="SECONDS", default=suppress,
        help="Combat and barrier damage effect duration (0 to 0.5 seconds in 0.1 steps).",
    )
    group.add_argument(
        "--floor-transition-duration",
        type=_choice_seconds(d.FLOOR_TRANSITION_SECONDS_CHOICES),
        metavar="SECONDS", default=suppress,
        help="Sprite GUI floor transition duration (0 to 1 second in 0.1 steps).",
    )
    group.add_argument(
        "--character-bobbing", type=_on_off, metavar="on|off", default=suppress,
        help="Sprite GUI idle character bobbing.",
    )
    group.add_argument(
        "--smooth-movement", type=_on_off, metavar="on|off", default=suppress,
        help=suppress,
    )


def cli_setting_overrides(args) -> dict:
    """Settings given on the command line, used for this run only."""
    overrides = {
        name: getattr(args, dest)
        for dest, name in SETTINGS_OPTIONS.items()
        if hasattr(args, dest)
    }
    if "scale" in overrides:
        overrides["scale"] = settings.valid_ui_scale(overrides["scale"])
    if "key_repeat_interval" in overrides:
        overrides["key_repeat_interval"] = settings.valid_key_repeat_interval(
            overrides["key_repeat_interval"]
        )
    return overrides


def _prepare_cli_session(terminal_only=False, sprites_only=False):
    parser = argparse.ArgumentParser(
        description="A Rogue-Like game.",
    )
    parser.set_defaults(sprites=False)
    general = parser.add_argument_group("General options")
    gui = None if terminal_only else parser.add_argument_group("GUI options")
    settings_group = parser.add_argument_group(
        "Settings options (this run only; the Settings screen saves settings)"
    )
    terminal = parser.add_argument_group("Terminal options")
    dev = parser.add_argument_group("Development options")
    if terminal_only:
        parser.set_defaults(terminal=True)
    if sprites_only:
        parser.set_defaults(sprites=True, terminal=False)

    general.add_argument(
        "--rematch",
        action="store_true",
        help="Replay the last stage with the same seed.",
    )
    general.add_argument(
        "--stage", action="store", type=int, default=0, help="Stage (1 through 6)."
    )
    general.add_argument("--seed", action="store", help="Seed value or seed string")
    g = general.add_mutually_exclusive_group()
    g.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    g.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    parser.set_defaults(narrower_corridors=False)
    if not terminal_only and not sprites_only:
        terminal.add_argument(
            "--terminal",
            "--curses",
            dest="terminal",
            action="store_true",
            help="Use the Blessed terminal UI (--curses is a deprecated alias).",
        )
    if not sprites_only:
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
        if not sprites_only:
            gui.add_argument(
                '--sprites', action='store_true',
                help='Use the Pyglet sprite UI: 3D-rendered characters and marble column walls '
                     '(characters without a sprite stay text).',
            )
        gui.add_argument(
            "--allow-screensaver", action="store_true",
            help="Do not keep the screensaver and display sleep off while the GUI runs.",
        )
    if sprites_only:
        gui.add_argument("--samurai", action="store_true",
                         help="Use the samurai player sprites.")
    _add_settings_arguments(settings_group)
    dev.add_argument("--debug-show-entities", action="store_true", help="Debug option.")
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
    if args.sprites and args.terminal:
        parser.error('--sprites cannot be combined with --terminal')

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

    if args.stage != 0 and args.stage not in d.PUBLIC_STAGE_NUMBERS:
        parser.error("--stage must be 1, 2, 3, 4, 5, or 6")

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
        ):
            parser.error(
                "--trace cannot be combined with --seed, --stage, --rematch, -T, or -t"
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
                ]
            ):
                exit(
                    "Error: option --seed is mutually exclusive to options --stage, -T, -t"
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

    if trace_data is not None:
        args.include_iris = trace_includes_iris(trace_data)
    game.rand.set_seed(args.seed)
    seed_str = game.generate_seed_string(args)
    game_config = game.game_config_from_args(args)
    if not getattr(args, "include_iris", True):
        game_config = replace(game_config, include_iris=False)

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


def main(terminal_only=False, sprites_only=False):
    args, trace_data, seed_str, game_config, trace_recorder = _prepare_cli_session(
        terminal_only=terminal_only, sprites_only=sprites_only
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
            try:
                game.run_game(
                    replay_ui,
                    seed_str,
                    args.stage,
                    args.debug_show_entities,
                    None,
                    trace=trace_recorder,
                    config=game_config,
                )
            finally:
                replay_ui.finish_replay()
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

    overrides = cli_setting_overrides(args)

    if args.terminal:
        from .blessed_funcs import BlessedUI
        from .blessed_map import Terminal

        term = Terminal()
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            ui = BlessedUI(term, dots=args.dots)
            ui.setting_overrides = overrides
            if "combat_effect_seconds" in overrides:
                ui.combat_effect_seconds = overrides["combat_effect_seconds"]
            play(ui)
    else:
        from .pyglet_funcs import PygletUI

        if args.sprites:
            from .sprites.sprite_funcs import SpriteUI

            ui = SpriteUI(overrides.get("scale"), samurai=getattr(args, "samurai", False))
        else:
            ui = PygletUI(overrides.get("scale"))
        # The Pyglet frontends keep each setting in an attribute of the same name.
        for name, value in overrides.items():
            setattr(ui, name, value)
        if args.allow_screensaver:
            play(ui)
        else:
            from wakepy import keep

            with keep.presenting(on_fail="pass"):
                play(ui)

    if trace_recorder is not None:
        cache_dir = Path(user_cache_dir("arlq"))
        archive_path = timestamped_trace_path(cache_dir)
        output_paths = [archive_path, game.last_trace_path()]
        if args.trace_output:
            output_paths.append(Path(args.trace_output))
        trace_recorder.write_outputs(output_paths)
