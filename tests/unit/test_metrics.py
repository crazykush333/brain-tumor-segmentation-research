from __future__ import annotations

from itertools import permutations

import numpy as np
import pytest

from brats_uncertainty.metrics.calibration import brier, case_calibration, ece
from brats_uncertainty.metrics.dice import dice, dice_from_counts, risk_from_dice
from brats_uncertainty.metrics.hd95 import hd95
from brats_uncertainty.metrics.morphology import ball, dilate
from brats_uncertainty.metrics.selective import (
    aurc,
    auroc_failure,
    excess_aurc,
    oracle_aurc,
    risk_coverage_curve,
)
from brats_uncertainty.metrics.volume import (
    relative_volume_error,
    volume_failure,
    volume_failure_from_counts,
    volume_ml,
)


# ---------------- Dice ----------------
def test_dice_empty_conventions() -> None:
    z = np.zeros((4, 4), dtype=bool)
    o = z.copy()
    o[0, 0] = True
    assert dice(z, z) == 1.0
    assert dice(z, o) == 0.0
    assert dice(o, z) == 0.0
    assert dice(o, o) == 1.0


def test_dice_value() -> None:
    a = np.array([1, 1, 0, 0], dtype=bool)
    b = np.array([1, 0, 1, 0], dtype=bool)
    assert dice(a, b) == pytest.approx(0.5)
    assert dice_from_counts(2, 2, 1) == pytest.approx(0.5)
    assert risk_from_dice(0.75) == pytest.approx(0.25)


def test_dice_shape_mismatch() -> None:
    with pytest.raises(Exception, match="shape"):
        dice(np.zeros(3, bool), np.zeros(4, bool))


# ---------------- AURC ----------------
def brute_force_expected_aurc(conf: list[float], risk: list[float]) -> float:
    """Average AURC over all orderings consistent with descending confidence."""
    n = len(conf)
    vals = []
    for perm in permutations(range(n)):
        c = [conf[i] for i in perm]
        if all(c[k] >= c[k + 1] for k in range(n - 1)):
            r = np.array([risk[i] for i in perm])
            vals.append(np.mean(np.cumsum(r) / np.arange(1, n + 1)))
    return float(np.mean(vals))


@pytest.mark.parametrize(
    ("conf", "risk"),
    [
        ([0.9, 0.8, 0.7, 0.6, 0.5], [0.1, 0.2, 0.3, 0.4, 0.5]),
        ([0.9, 0.9, 0.7, 0.7, 0.7], [0.0, 1.0, 0.2, 0.5, 0.9]),
        ([1.0, 1.0, 1.0, 1.0, 0.0], [0.3, 0.1, 0.8, 0.0, 1.0]),
        ([0.5, 0.2, 0.5, 0.2, 0.9, 0.2], [0.4, 0.6, 0.0, 1.0, 0.3, 0.2]),
    ],
)
def test_aurc_matches_brute_force_expected_tie_breaking(
    conf: list[float], risk: list[float]
) -> None:
    assert aurc(conf, risk) == pytest.approx(brute_force_expected_aurc(conf, risk))


def test_constant_score_aurc_equals_mean_risk() -> None:
    rng = np.random.default_rng(0)
    r = rng.uniform(size=37)
    assert aurc(np.full(37, -0.3), r) == pytest.approx(r.mean())


def test_oracle_and_excess() -> None:
    r = np.array([0.5, 0.1, 0.9, 0.3])
    assert oracle_aurc(r) <= aurc(np.zeros(4), r)
    assert excess_aurc(-r, r) == pytest.approx(0.0)
    # Delta-AURC equals Delta-e-AURC for two scores on the same predictions (§3)
    s1, s2 = np.array([0.2, 0.9, 0.1, 0.4]), np.array([0.3, 0.3, 0.3, 0.3])
    assert aurc(s1, r) - aurc(s2, r) == pytest.approx(excess_aurc(s1, r) - excess_aurc(s2, r))


def test_risk_coverage_curve_shape() -> None:
    c = risk_coverage_curve([0.9, 0.1, 0.5], [0.0, 1.0, 0.5])
    np.testing.assert_allclose(c.coverage, [1 / 3, 2 / 3, 1.0])
    np.testing.assert_allclose(c.selective_risk, [0.0, 0.25, 0.5])


def test_aurc_validation() -> None:
    with pytest.raises(ValueError):
        aurc([], [])
    with pytest.raises(ValueError):
        aurc([1.0], [np.nan])
    with pytest.raises(ValueError):
        aurc([1.0, 2.0], [0.1])


def test_auroc_failure() -> None:
    assert auroc_failure([0.9, 0.8, 0.2, 0.1], [False, False, True, True]) == 1.0
    assert auroc_failure([0.5, 0.5], [False, True]) == 0.5
    assert np.isnan(auroc_failure([0.5, 0.4], [False, False]))


# ---------------- morphology / calibration ----------------
def test_ball_radius_3() -> None:
    b = ball(3)
    assert b.shape == (7, 7, 7)
    assert b[3, 3, 0] and not b[0, 0, 0]
    assert int(b.sum()) == 123  # lattice points with x^2+y^2+z^2 <= 9


def test_dilate_single_voxel() -> None:
    m = np.zeros((11, 11, 11), bool)
    m[5, 5, 5] = True
    assert int(dilate(m, 3).sum()) == 123
    assert int(dilate(np.zeros_like(m), 3).sum()) == 0


def test_ece_perfect_and_bad() -> None:
    y = np.array([0, 0, 1, 1], bool)
    assert ece(np.array([0.0, 0.0, 1.0, 1.0]), y) == pytest.approx(0.0)
    assert ece(np.array([1.0, 1.0, 0.0, 0.0]), y) == pytest.approx(1.0)
    assert brier(np.array([1.0, 1.0, 0.0, 0.0]), y) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        ece(np.array([1.5]), np.array([True]))


def test_case_calibration_empty_roi_is_nan() -> None:
    out = case_calibration(np.zeros((5, 5, 5)), np.zeros((5, 5, 5), bool))
    assert np.isnan(out["ece"]) and np.isnan(out["brier"])


# ---------------- volume / hd95 ----------------
def test_volume_failure_rules() -> None:
    m = np.ones((10, 10, 10), bool)
    assert volume_ml(m) == pytest.approx(1.0)
    assert relative_volume_error(1.4, 1.0) == pytest.approx(0.4)
    assert volume_failure(1.4, 1.0) is True
    assert volume_failure(1.3, 1.0) is False
    assert volume_failure(1.3, 1.0, threshold=0.65) is False
    assert volume_failure(5.0, 0.99) is None  # GT ET < 1 mL is ineligible
    with pytest.raises(ValueError):
        volume_failure(1.0, 1.0, threshold=0.5)
    # exact boundaries on voxel counts (1 mm isotropic)
    assert volume_failure_from_counts(1400, 1000) is True
    assert volume_failure_from_counts(600, 1000) is True
    assert volume_failure_from_counts(1399, 1000) is False
    assert volume_failure_from_counts(1650, 1000, threshold=0.65) is True
    assert volume_failure_from_counts(5000, 999) is None
    assert volume_failure_from_counts(0, 1000) is True


def test_hd95_is_deferred_to_gate_c6() -> None:
    with pytest.raises(NotImplementedError, match="C6"):
        hd95(np.zeros(3), np.zeros(3))
