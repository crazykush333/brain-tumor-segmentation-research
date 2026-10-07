"""Controlled-input checks of analysis pieces before eval-v1 (SYNTHETIC values only).

Each test states the protocol rule it checks and computes the expected value by hand.
"""

from __future__ import annotations

import numpy as np
import pytest

from brats_uncertainty.study.analysis import _rho_stat, indicator_transfer_error
from brats_uncertainty.study.failure import categorize


def _unit(case: str, cond: str, region: str, **kw: object) -> dict[str, str]:
    base = {"case_id": case, "condition": cond, "region": region, "U1": "1.0", "dice": "1.0"}
    base.update({k: str(v) for k, v in kw.items()})
    return base


def test_s14_indicator_transfer_error_is_validation_minus_target_risk() -> None:
    """§4 S14: per condition, validation-estimated ET risk minus the realised target risk."""
    frozen = {"indicator": {"B": {"ET": {"-T1c": {"mean_risk": 0.30}, "Full": {"mean_risk": 0.1}}}}}
    rows = [
        _unit("c1", "-T1c", "ET", risk=0.10),
        _unit("c2", "-T1c", "ET", risk=0.50),
        _unit("c1", "-T1c", "WT", risk=0.90),  # other regions are ignored
        _unit("c1", "Full", "ET", risk=0.20),
    ]
    out = indicator_transfer_error(rows, frozen)
    assert out == pytest.approx({"-T1c": 0.30 - 0.30, "Full": 0.1 - 0.2})


def test_s6_spearman_statistic_on_a_resample() -> None:
    """§4 S6: Spearman rho between U1 and ET Dice; undefined when either is constant."""
    u = np.array([0.1, 0.4, 0.2, 0.9])
    d = np.array([0.2, 0.5, 0.3, 0.8])  # same order as u -> rho = 1
    stat = _rho_stat(u, d)
    assert stat(np.arange(4)) == pytest.approx(1.0)
    assert stat(np.array([3, 2, 1, 0])) == pytest.approx(1.0)  # order of units irrelevant
    assert np.isnan(stat(np.array([0, 0, 0])))  # constant resample: undefined, not 0


def test_s19_failure_categories_follow_the_frozen_rules() -> None:
    """§19: confident failure = U1 >= tau_0.20 and ET Dice < 0.5; hallucinated ET = GT
    empty, prediction present; missed ET = the reverse; per condition."""
    tau = 0.8
    rows = [
        _unit(
            "a", "-T1c", "ET", U1=0.8, dice=0.49, gt_voxels=10, pred_voxels=5
        ),  # confident failure (U1 == tau)
        _unit(
            "b", "-T1c", "ET", U1=0.79, dice=0.1, gt_voxels=10, pred_voxels=5
        ),  # below tau: not confident
        _unit(
            "c", "-T1c", "ET", U1=0.95, dice=0.5, gt_voxels=10, pred_voxels=8
        ),  # Dice 0.5 is not < 0.5
        _unit("d", "-T1c", "ET", U1=0.2, dice=0.0, gt_voxels=0, pred_voxels=3),  # hallucinated ET
        _unit(
            "e", "-T1c", "ET", U1=0.9, dice=0.0, gt_voxels=7, pred_voxels=0
        ),  # missed ET (+ confident failure)
        _unit("a", "-T1c", "WT", gt_voxels=50, pred_voxels=0),  # WT false negative
        _unit("a", "Full", "ET", U1=0.99, dice=0.9, gt_voxels=10, pred_voxels=9),
    ]
    out = categorize(rows, tau)
    t1c = out["-T1c"]["cases"]
    assert t1c["confident_failure"] == ["a", "e"]
    assert t1c["hallucinated_ET"] == ["d"] and t1c["missed_ET"] == ["e"]
    assert t1c["false_negative_WT"] == ["a"]
    assert out["-T1c"]["n_cases"] == 5 and out["Full"]["counts"]["confident_failure"] == 0


def test_s10_c15_block_reports_descriptive_estimates_per_subset() -> None:
    """§4 S10 (arm B, internal test, all 15 subsets): ET Dice, within-condition ET
    Delta-AURC and ECE per subset, descriptive (no p-value)."""
    from brats_uncertainty.metrics.selective import aurc
    from brats_uncertainty.study.analysis import c15_block

    rows = []
    for cond, vals in {
        "T1c": [(0.9, 0.9, 0.02), (0.6, 0.4, 0.10), (0.8, 0.7, 0.05)],
        "T1+T2": [(0.5, 0.2, 0.20), (0.9, 0.95, 0.01)],
    }.items():
        for k, (u1, dice, ece) in enumerate(vals):
            rows.append(
                {
                    "case_id": f"c{k}",
                    "group_id": f"g{k}",
                    "condition": cond,
                    "region": "ET",
                    "U1": str(u1),
                    "dice": str(dice),
                    "risk": str(1 - dice),
                    "ece": str(ece),
                }
            )
    out = c15_block(rows, n=200, seed=12345)
    assert set(out) == {"T1c", "T1+T2"}
    t1c = out["T1c"]
    risk = [0.1, 0.6, 0.3]
    expected_delta = aurc([0.9, 0.6, 0.8], risk) - float(np.mean(risk))
    assert t1c["et_dice"]["estimate"] == pytest.approx(np.mean([0.9, 0.4, 0.7]))
    assert t1c["delta_aurc"]["estimate"] == pytest.approx(expected_delta)
    assert t1c["ece"]["estimate"] == pytest.approx(np.mean([0.02, 0.10, 0.05]))
    assert "p_value_two_sided_approx" not in t1c["delta_aurc"]  # descriptive only
    assert t1c["delta_aurc"]["n_replicates"] == 200 and t1c["delta_aurc"]["seed"] == 12345
