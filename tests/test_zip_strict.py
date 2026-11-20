import pytest

from arlq.utils import bit_count, zip_strict


def test_zip_strict_pairs_and_triples():
    assert list(zip_strict([1, 2], ["a", "b"])) == [(1, "a"), (2, "b")]
    assert list(zip_strict([1], [2], [3])) == [(1, 2, 3)]
    assert list(zip_strict([], [])) == []


@pytest.mark.parametrize("lengths", [(1, 2), (2, 1), (1, 1, 2), (1, 2, 1)])
def test_zip_strict_rejects_unequal_lengths(lengths):
    with pytest.raises(ValueError):
        list(zip_strict(*[list(range(length)) for length in lengths]))


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (13, 3), (-13, 3)])
def test_bit_count(value, expected):
    assert bit_count(value) == expected
