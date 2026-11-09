import pytest

from arlq.utils import MyRandom


def test_mt19937_reference_sequence():
    rng = MyRandom(5489)
    assert [rng._next_uint32() for _ in range(10)] == [
        3499211612, 581869302, 3890346734, 3586334585, 545404204,
        4161255391, 3922919429, 949333985, 2715962298, 1323567403,
    ]


def test_state_restores_sequence_across_twist():
    rng = MyRandom(42)
    for _ in range(620):
        rng._next_uint32()
    state = rng.getstate()
    expected = [rng.randrange(100) for _ in range(20)]
    rng.setstate(state)
    assert [rng.randrange(100) for _ in range(20)] == expected


def test_randrange_rejects_out_of_range_values(monkeypatch):
    rng = MyRandom(1)
    values = iter([0xffffffff, 0x80000000])
    monkeypatch.setattr(rng, "_next_uint32", lambda: next(values))
    assert rng.randrange(10, 13) == 12


def test_randrange_supports_large_ranges_and_empty_ranges():
    rng = MyRandom(7)
    assert 0 <= rng.randrange(1 << 100) < 1 << 100
    assert rng.randrange(-5, -4) == -5
    with pytest.raises(ValueError):
        rng.randrange(2, 2)


def test_seed_repeats_choices():
    rng = MyRandom(-23)
    first = [rng.choice("abcde") for _ in range(100)]
    rng.set_seed(-23)
    assert [rng.choice("abcde") for _ in range(100)] == first
