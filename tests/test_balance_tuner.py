import copy
import random

import pytest

from arlq import defs as d
from arlq.balance_tuner import (
    DEFAULT_CONFIG,
    Tuning,
    current_tuning,
    generate_candidates,
    patched_tuning,
    validate_config,
)


def test_patched_tuning_restores_values_after_error():
    config = copy.deepcopy(DEFAULT_CONFIG)
    baseline = current_tuning(config)
    tuning = Tuning((("b", 31),), ((1, "a", 11), (2, "a", 12)))

    with pytest.raises(RuntimeError), patched_tuning(tuning):
        assert d.CHAR_TO_MONSTER_TRIBE["b"].feed == 31
        assert (
            next(sc.population for sc in d.SPAWN_CONFIGS_ST1 if sc.tribe.char == "a")
            == 11
        )
        raise RuntimeError("test")

    assert d.CHAR_TO_MONSTER_TRIBE["b"].feed == dict(baseline.feed)["b"]
    stage1 = {char: value for stage, char, value in baseline.spawn if stage == 1}
    assert (
        next(sc.population for sc in d.SPAWN_CONFIGS_ST1 if sc.tribe.char == "a")
        == stage1["a"]
    )


def test_candidate_generation_is_reproducible_and_includes_baseline():
    config = copy.deepcopy(DEFAULT_CONFIG)
    first = generate_candidates(config, random.Random(1234))
    second = generate_candidates(config, random.Random(1234))

    assert first == second
    assert first[0] == current_tuning(config)
    assert len({candidate.candidate_id for candidate in first}) == len(first)


def test_seed_phases_must_not_overlap():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["validation"]["seed_start"] = config["search"]["seed_start"]

    with pytest.raises(ValueError, match="must be disjoint"):
        validate_config(config)
