from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.models.dropout import ModalityDropoutPolicy
from brats_uncertainty.preprocessing.modalities import (
    C4,
    C4_NAMES,
    C5_NAMES,
    FULL,
    MODALITIES,
    ModalitySubset,
    all_subsets,
    apply_missingness,
    non_full_subsets,
)
from tests.fixtures.synthetic import synthetic_image

ALL = all_subsets()


def test_channel_order_is_fixed_by_protocol() -> None:
    assert MODALITIES == ("T1", "T1c", "T2", "FLAIR")


def test_exactly_15_unique_non_empty_subsets() -> None:
    assert len(ALL) == 15
    assert len({s.present for s in ALL}) == 15
    assert all(len(s.present) >= 1 for s in ALL)
    assert len(non_full_subsets()) == 14


def test_c4_c5_names() -> None:
    assert C5_NAMES == ("Full", "-T1", "-T1c", "-T2", "-FLAIR")
    assert C4_NAMES == ("-T1", "-T1c", "-T2", "-FLAIR")
    assert "Full" not in C4_NAMES
    assert all(len(s.missing) == 1 for s in C4)


def test_empty_and_unknown_subsets_rejected() -> None:
    with pytest.raises(ValueError):
        ModalitySubset(())
    with pytest.raises(ValueError):
        ModalitySubset(("T1", "DWI"))
    with pytest.raises(ValueError):
        ModalitySubset(("T1", "T1"))


@pytest.mark.parametrize("subset", ALL, ids=[s.name for s in ALL])
def test_apply_missingness_all_15_subsets(subset: ModalitySubset) -> None:
    rng = np.random.default_rng(1)
    img = synthetic_image(rng)
    out = apply_missingness(img, subset)
    for i, m in enumerate(MODALITIES):
        if m in subset.present:
            np.testing.assert_array_equal(out[i], img[i])
        else:
            assert np.all(out[i] == 0.0)
    # input untouched
    assert np.any(img != 0)
    assert ModalitySubset.from_name(subset.name) == subset


def test_apply_missingness_channel_axis_last() -> None:
    img = np.ones((3, 3, 3, 4), dtype=np.float32)
    out = apply_missingness(img, ModalitySubset.from_name("-T1c"), channel_axis=-1)
    assert np.all(out[..., 1] == 0) and np.all(out[..., [0, 2, 3]] == 1)


def test_apply_missingness_rejects_wrong_channels() -> None:
    with pytest.raises(DataValidationError):
        apply_missingness(np.ones((3, 4, 4, 4)), FULL)


def test_dropout_policy_probabilities_sum_to_one() -> None:
    probs = ModalityDropoutPolicy().probabilities()
    assert len(probs) == 15
    assert probs["Full"] == 0.5
    assert pytest.approx(sum(probs.values())) == 1.0
    assert all(pytest.approx(v) == 0.5 / 14 for k, v in probs.items() if k != "Full")


def test_dropout_policy_rejects_non_protocol_p_full() -> None:
    with pytest.raises(ProtocolDeviationError):
        ModalityDropoutPolicy(p_full=0.3)


def test_dropout_policy_reaches_all_15_subsets_with_expected_frequencies() -> None:
    policy = ModalityDropoutPolicy()
    rng = np.random.default_rng(123)
    n = 56_000
    counts = Counter(policy.sample(rng).name for _ in range(n))
    assert set(counts) == {s.name for s in ALL}
    assert abs(counts["Full"] / n - 0.5) < 0.01
    for s in non_full_subsets():
        assert abs(counts[s.name] / n - 0.5 / 14) < 0.006


def test_dropout_apply_batch_zeroes_only_missing_channels() -> None:
    rng = np.random.default_rng(5)
    batch = np.stack([synthetic_image(rng) for _ in range(8)])
    out, chosen = ModalityDropoutPolicy().apply_batch(batch, np.random.default_rng(9))
    for b, s in enumerate(chosen):
        for i, m in enumerate(MODALITIES):
            if m in s.missing:
                assert np.all(out[b, i] == 0)
            else:
                np.testing.assert_array_equal(out[b, i], batch[b, i])


def test_dropout_is_deterministic_given_seed() -> None:
    p = ModalityDropoutPolicy()
    a = [p.sample(np.random.default_rng(7)).name for _ in range(3)]
    r1, r2 = np.random.default_rng(7), np.random.default_rng(7)
    assert [p.sample(r1).name for _ in range(50)] == [p.sample(r2).name for _ in range(50)]
    assert len(set(a)) == 1
