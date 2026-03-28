from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass

from . import defs as d
from .branch_analyzer import (
    BeamState,
    SearchBudget,
    advance_until_contact,
    beam_state_key,
    ensure_branch_metadata,
    load_seed_file,
    rank_nearest_targets,
    select_top_beam,
)
from .solver import apply_runtime_flags, build_simulation


@dataclass
class ProbeSummary:
    seed: int
    states_checked: int = 0
    focus_available_states: int = 0
    required_cases: int = 0
    neglected_cases: int = 0
    first_required_depth: int | None = None
    first_neglected_depth: int | None = None


def candidate_monster_char(state, candidate) -> str | None:
    entity = state.entities[candidate.entity_index]
    if isinstance(entity, d.Monster):
        return entity.tribe.char
    return None


def has_winning_path_from_beam(
    beam: list[BeamState],
    *,
    top_k: int,
    max_depth: int,
    beam_width: int,
    node_budget: int,
    max_travel_steps: int,
    lp_weight: float,
    level_weight: float,
) -> bool:
    budget = SearchBudget(nodes_left=node_budget)
    path_cache = {}

    for _depth in range(max_depth):
        if not beam or budget.nodes_left <= 0:
            return False
        next_beam: list[BeamState] = []
        for beam_state in beam:
            if budget.nodes_left <= 0:
                break
            state = beam_state.state
            if state.won:
                return True
            if state.ended:
                continue

            candidates = rank_nearest_targets(state, top_k, path_cache)
            if not candidates:
                continue

            for candidate in candidates:
                if budget.nodes_left <= 0:
                    break
                budget.nodes_left -= 1
                child_state = deepcopy(state)
                ensure_branch_metadata(child_state)
                contacted = advance_until_contact(child_state, candidate.entity_index, max_travel_steps, path_cache)
                if not contacted:
                    continue
                if child_state.won:
                    return True
                if child_state.ended:
                    continue
                next_beam.append(BeamState(state=child_state, depth=beam_state.depth + 1))

        beam = select_top_beam(next_beam, beam_width, lp_weight, level_weight)

    return any(beam_state.state.won for beam_state in beam)


def has_winning_path_after_initial_choice(
    state,
    candidates,
    *,
    top_k: int,
    max_depth: int,
    beam_width: int,
    node_budget: int,
    max_travel_steps: int,
    lp_weight: float,
    level_weight: float,
) -> bool:
    if max_depth <= 0 or not candidates:
        return False

    initial_beam: list[BeamState] = []
    initial_budget = SearchBudget(nodes_left=node_budget)
    path_cache = {}

    for candidate in candidates:
        if initial_budget.nodes_left <= 0:
            break
        initial_budget.nodes_left -= 1
        child_state = deepcopy(state)
        ensure_branch_metadata(child_state)
        contacted = advance_until_contact(child_state, candidate.entity_index, max_travel_steps, path_cache)
        if not contacted:
            continue
        if child_state.won:
            return True
        if child_state.ended:
            continue
        initial_beam.append(BeamState(state=child_state, depth=1))

    if not initial_beam:
        return False

    return has_winning_path_from_beam(
        initial_beam,
        top_k=top_k,
        max_depth=max_depth - 1,
        beam_width=beam_width,
        node_budget=max(1, initial_budget.nodes_left),
        max_travel_steps=max_travel_steps,
        lp_weight=lp_weight,
        level_weight=level_weight,
    )


def probe_seed(
    *,
    stage_num: int,
    seed: int,
    focus_char: str,
    top_k: int,
    max_depth: int,
    beam_width: int,
    node_budget: int,
    max_travel_steps: int,
    lp_weight: float,
    level_weight: float,
    probe_beam_width: int,
    probe_node_budget: int,
    probe_max_depth: int,
) -> ProbeSummary:
    initial_state = build_simulation(stage_num, seed)
    ensure_branch_metadata(initial_state)
    beam: list[BeamState] = [BeamState(state=initial_state)]
    budget = SearchBudget(nodes_left=node_budget)
    path_cache = {}
    summary = ProbeSummary(seed=seed)
    probed_keys: set[tuple] = set()

    for depth in range(max_depth):
        if not beam or budget.nodes_left <= 0:
            break
        next_beam: list[BeamState] = []
        for beam_state in beam:
            if budget.nodes_left <= 0:
                break
            state = beam_state.state
            if state.won or state.ended:
                continue

            candidates = rank_nearest_targets(state, top_k, path_cache)
            if not candidates:
                continue

            focus_candidates = [candidate for candidate in candidates if candidate_monster_char(state, candidate) == focus_char]
            other_candidates = [candidate for candidate in candidates if candidate_monster_char(state, candidate) != focus_char]
            if focus_candidates and other_candidates:
                summary.focus_available_states += 1
                probe_key = (depth, beam_state_key(beam_state))
                if probe_key not in probed_keys:
                    probed_keys.add(probe_key)
                    summary.states_checked += 1
                    remaining_depth = min(probe_max_depth, max_depth - depth)
                    has_win_without_focus = has_winning_path_after_initial_choice(
                        state,
                        other_candidates,
                        top_k=top_k,
                        max_depth=remaining_depth,
                        beam_width=probe_beam_width,
                        node_budget=probe_node_budget,
                        max_travel_steps=max_travel_steps,
                        lp_weight=lp_weight,
                        level_weight=level_weight,
                    )
                    if has_win_without_focus:
                        summary.neglected_cases += 1
                        if summary.first_neglected_depth is None:
                            summary.first_neglected_depth = depth
                    else:
                        has_win_with_focus = has_winning_path_after_initial_choice(
                            state,
                            focus_candidates,
                            top_k=top_k,
                            max_depth=remaining_depth,
                            beam_width=probe_beam_width,
                            node_budget=probe_node_budget,
                            max_travel_steps=max_travel_steps,
                            lp_weight=lp_weight,
                            level_weight=level_weight,
                        )
                        if has_win_with_focus:
                            summary.required_cases += 1
                            if summary.first_required_depth is None:
                                summary.first_required_depth = depth

            for candidate in candidates:
                if budget.nodes_left <= 0:
                    break
                budget.nodes_left -= 1
                child_state = deepcopy(state)
                ensure_branch_metadata(child_state)
                contacted = advance_until_contact(child_state, candidate.entity_index, max_travel_steps, path_cache)
                if not contacted or child_state.ended or child_state.won:
                    continue
                next_beam.append(
                    BeamState(
                        state=child_state,
                        first_choice=beam_state.first_choice or candidate.entity_id,
                        depth=depth + 1,
                    )
                )

        beam = select_top_beam(next_beam, beam_width, lp_weight, level_weight)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe whether a focus monster choice is required for wins.")
    parser.add_argument("--stage", type=int, default=2, help="Stage number to probe.")
    parser.add_argument("--focus-char", type=str, default="C", help="Monster char to test for required choice points.")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds to analyze.")
    parser.add_argument("--seed-start", type=int, default=1, help="First seed value to use.")
    parser.add_argument("--seed-file", type=str, help="Path to a file containing explicit seed values.")
    parser.add_argument("--top-k", type=int, default=5, help="Nearest targets expanded by the main analyzer.")
    parser.add_argument("--max-depth", type=int, default=60, help="Maximum depth for the main traversal.")
    parser.add_argument("--beam-width", type=int, default=110, help="Maximum number of states kept per depth.")
    parser.add_argument("--node-budget", type=int, default=20000, help="Expanded child states per seed for the main traversal.")
    parser.add_argument("--max-travel-steps", type=int, default=500, help="Movement cap while advancing to a target.")
    parser.add_argument("--lp-weight", type=float, default=1.0, help="Weight for LP in the beam evaluation score.")
    parser.add_argument("--level-weight", type=float, default=10.0, help="Weight for level in the beam evaluation score.")
    parser.add_argument("--probe-beam-width", type=int, default=48, help="Beam width for local required-choice probes.")
    parser.add_argument("--probe-node-budget", type=int, default=4000, help="Node budget for local required-choice probes.")
    parser.add_argument("--probe-max-depth", type=int, default=24, help="Max depth for local required-choice probes.")
    parser.add_argument("-F", "--large-field", action="store_true", help="Large field.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-T", "--large-torch", action="store_true", help="Large torch.")
    group.add_argument("-t", "--small-torch", action="store_true", help="Small torch.")
    parser.add_argument("-n", "--narrower-corridors", action="store_true", help="Narrower corridors.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    apply_runtime_flags(args)
    seed_values = load_seed_file(args.seed_file) if args.seed_file else list(
        range(args.seed_start, args.seed_start + args.seeds)
    )

    summaries: list[ProbeSummary] = []
    total_focus_states = 0
    total_checked_states = 0
    total_required_cases = 0
    total_neglected_cases = 0
    seeds_with_required_cases = 0
    seeds_with_neglected_cases = 0

    for index, seed in enumerate(seed_values, start=1):
        summary = probe_seed(
            stage_num=args.stage,
            seed=seed,
            focus_char=args.focus_char,
            top_k=args.top_k,
            max_depth=args.max_depth,
            beam_width=args.beam_width,
            node_budget=args.node_budget,
            max_travel_steps=args.max_travel_steps,
            lp_weight=args.lp_weight,
            level_weight=args.level_weight,
            probe_beam_width=args.probe_beam_width,
            probe_node_budget=args.probe_node_budget,
            probe_max_depth=args.probe_max_depth,
        )
        summaries.append(summary)
        total_focus_states += summary.focus_available_states
        total_checked_states += summary.states_checked
        total_required_cases += summary.required_cases
        total_neglected_cases += summary.neglected_cases
        if summary.required_cases > 0:
            seeds_with_required_cases += 1
        if summary.neglected_cases > 0:
            seeds_with_neglected_cases += 1
        print(
            f"[progress] seeds={index}/{len(seed_values)} current_seed={seed} "
            f"focus_states={total_focus_states} required_cases={total_required_cases} "
            f"neglected_cases={total_neglected_cases}"
        )

    total_decisions = total_required_cases + total_neglected_cases
    decision_score = (
        (total_required_cases - total_neglected_cases) / total_decisions
        if total_decisions
        else 0.0
    )

    print(
        f"stage={args.stage} seeds={len(seed_values)} focus_char={args.focus_char} "
        f"top_k={args.top_k} max_depth={args.max_depth} beam_width={args.beam_width} "
        f"node_budget={args.node_budget}"
    )
    print(
        f"aggregate focus_available_states={total_focus_states} checked_states={total_checked_states} "
        f"required_cases={total_required_cases} neglected_cases={total_neglected_cases} "
        f"decision_score={decision_score:.3f} seeds_with_required_cases={seeds_with_required_cases} "
        f"seeds_with_neglected_cases={seeds_with_neglected_cases}"
    )
    print("")
    print("[seed summaries]")
    for summary in summaries:
        required_depth_text = str(summary.first_required_depth) if summary.first_required_depth is not None else "-"
        neglected_depth_text = str(summary.first_neglected_depth) if summary.first_neglected_depth is not None else "-"
        print(
            f"seed={summary.seed} focus_available_states={summary.focus_available_states} "
            f"checked_states={summary.states_checked} required_cases={summary.required_cases} "
            f"neglected_cases={summary.neglected_cases} first_required_depth={required_depth_text} "
            f"first_neglected_depth={neglected_depth_text}"
        )


if __name__ == "__main__":
    main()
