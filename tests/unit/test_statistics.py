from __future__ import annotations

import numpy as np
import pytest

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.statistics.bootstrap import (
    GroupIndex,
    bca_from_result,
    group_bootstrap,
    percentile_ci,
    two_sided_p,
)
from brats_uncertainty.statistics.multiplicity import holm_adjust, holm_family
from brats_uncertainty.statistics.primary import (
    delta_aurc_condition,
    mean_delta_aurc,
    run_primary,
)
from brats_uncertainty.statistics.thresholds import (
    select_tau,
    threshold_transfer,
    transfer_labels,
    weighted_coverage_risk,
)
from brats_uncertainty.statistics.units import UnitTable
from tests.fixtures.synthetic import synthetic_units


# ---------------- units ----------------
def test_unit_table_rejects_inconsistent_groups_and_duplicates() -> None:
    with pytest.raises(DataValidationError, match="more than one patient group"):
        UnitTable.from_columns(
            ["a", "a"], ["g1", "g2"], ["Full", "-T1"], [0.1, 0.2], {"U1": [1, 1]}
        )
    with pytest.raises(DataValidationError, match="duplicate"):
        UnitTable.from_columns(
            ["a", "a"], ["g1", "g1"], ["Full", "Full"], [0.1, 0.2], {"U1": [1, 1]}
        )
    with pytest.raises(DataValidationError):
        UnitTable.from_columns(["a"], ["g1"], ["Full"], [1.2], {"U1": [1]})


# ---------------- bootstrap ----------------
def test_group_index_keeps_groups_together() -> None:
    gi = GroupIndex(["g2", "g1", "g2", "g3", "g1"])
    assert list(gi.groups) == ["g1", "g2", "g3"]
    idx = gi.resample(np.random.default_rng(0))
    assert len(idx) >= 3
    gids = np.array(["g2", "g1", "g2", "g3", "g1"])
    for g in set(gids[idx]):
        # each drawn group contributes all of its members (possibly several times)
        members = set(np.flatnonzero(gids == g))
        assert members <= set(idx.tolist())


def test_bootstrap_deterministic_and_seeded() -> None:
    x = np.random.default_rng(0).normal(size=40)
    gi = GroupIndex([f"g{i}" for i in range(40)])
    a = group_bootstrap(lambda i: float(x[i].mean()), gi, n_replicates=500, seed=12345)
    b = group_bootstrap(lambda i: float(x[i].mean()), gi, n_replicates=500, seed=12345)
    np.testing.assert_array_equal(a.replicates, b.replicates)
    assert a.ci_low < a.estimate < a.ci_high
    lo, hi = bca_from_result(a, lambda i: float(x[i].mean()), gi)
    assert lo < hi


def test_two_sided_p_construction() -> None:
    assert two_sided_p(np.array([1.0, 2.0, 3.0, -1.0])) == pytest.approx(0.5)
    assert two_sided_p(np.array([1.0, 2.0])) == 0.0
    assert two_sided_p(np.array([0.0, 0.0])) == 1.0  # capped
    assert percentile_ci(np.arange(101.0)) == pytest.approx((2.5, 97.5))


# ---------------- Holm ----------------
def test_holm_known_values() -> None:
    adj = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.005})
    assert adj == pytest.approx({"d": 0.02, "a": 0.03, "c": 0.06, "b": 0.06})


def test_holm_family_rules() -> None:
    with pytest.raises(ValueError, match="descriptive"):
        holm_family("F5", {"x": 0.1})
    with pytest.raises(ValueError, match="must contain 4"):
        holm_family("F1", {"x": 0.1})
    assert len(holm_family("F3b", {"i": 0.01, "u": 0.2, "a": 0.03})) == 3


# ---------------- primary statistic ----------------
def test_delta_aurc_zero_for_constant_u1() -> None:
    u = synthetic_units(n_groups=12)
    const = UnitTable(u.case_id, u.group_id, u.condition, u.risk, {"U1": np.full(len(u), 0.5)})
    idx = np.arange(len(u))
    for c in ("-T1", "-T1c", "-T2", "-FLAIR", "Full"):
        assert delta_aurc_condition(const, idx, c) == pytest.approx(0.0, abs=1e-12)


def test_primary_excludes_full_from_estimand() -> None:
    u = synthetic_units(n_groups=15)
    idx = np.arange(len(u))
    manual = np.mean([delta_aurc_condition(u, idx, c) for c in ("-T1", "-T1c", "-T2", "-FLAIR")])
    assert mean_delta_aurc(u, idx) == pytest.approx(manual)


def test_run_primary_synthetic_small() -> None:
    u = synthetic_units(n_groups=20, signal=0.9)
    res = run_primary(u, n_replicates=200)
    assert set(res.per_condition) == {"-T1", "-T1c", "-T2", "-FLAIR", "Full"}
    assert res.mean_c4.n_replicates == 200
    assert res.mean_c4.estimate < 0  # synthetic signal couples U1 to low risk


# ---------------- thresholds ----------------
def _val_units() -> UnitTable:
    cond = ["-T1"] * 4 + ["-T1c"] * 4 + ["-T2"] * 4 + ["-FLAIR"] * 4 + ["Full"] * 4
    u1 = [1.0, 0.9, 0.9, 0.1] * 5
    risk = [0.0, 0.2, 0.4, 0.8] * 5
    cases = [f"SYN-{i}" for i in range(4)] * 5
    return UnitTable.from_columns(cases, [f"G{c[-1]}" for c in cases], cond, risk, {"U1": u1})


def test_select_tau_ge_rule_with_ties() -> None:
    v = _val_units()
    # coverage(U1>=1.0)=0.25, (>=0.9)=0.75, (>=0.1)=1.0
    t80 = select_tau(v.score("U1"), v.condition, 0.80)
    assert t80.tau == pytest.approx(0.1) and t80.realized_coverage == pytest.approx(1.0)
    t70 = select_tau(v.score("U1"), v.condition, 0.70)
    assert t70.tau == pytest.approx(0.9) and t70.realized_coverage == pytest.approx(0.75)
    t20 = select_tau(v.score("U1"), v.condition, 0.20)
    assert t20.tau == pytest.approx(1.0)


def test_select_tau_rejects_non_protocol_q_and_full() -> None:
    v = _val_units()
    with pytest.raises(ProtocolDeviationError):
        select_tau(v.score("U1"), v.condition, 0.5)
    with pytest.raises(ProtocolDeviationError):
        select_tau(v.score("U1"), v.condition, 0.8, conditions=("Full", "-T1"))


def test_full_units_do_not_affect_tau() -> None:
    v = _val_units()
    u1 = v.score("U1").copy()
    u1[v.condition == "Full"] = 0.0
    assert select_tau(u1, v.condition, 0.7).tau == select_tau(v.score("U1"), v.condition, 0.7).tau


def test_equal_condition_weighting() -> None:
    cond = np.array(["-T1"] * 2 + ["-T1c"] * 4 + ["-T2"] + ["-FLAIR"])
    u1 = np.array([1, 0, 1, 1, 1, 1, 0, 1], float)
    risk = np.zeros(8)
    cov, _ = weighted_coverage_risk(u1, risk, cond, 1.0)
    assert cov == pytest.approx((0.5 + 1.0 + 0.0 + 1.0) / 4)


def test_transfer_identical_sets_gives_zero_deltas() -> None:
    v = _val_units()
    tau = select_tau(v.score("U1"), v.condition, 0.70)
    res = threshold_transfer(v, v, tau, n_replicates=200)
    assert res.delta_risk.estimate == pytest.approx(0.0)
    assert res.delta_coverage.estimate == pytest.approx(0.0)
    assert res.delta_risk.n_replicates == 200


def test_transfer_labels() -> None:
    assert transfer_labels(0.1, 0.01, -0.1, 0.01) == {
        "unsafe_transfer": True,
        "inefficient_transfer": True,
    }
    assert transfer_labels(0.1, 0.2, -0.1, 0.2) == {
        "unsafe_transfer": False,
        "inefficient_transfer": False,
    }
    assert transfer_labels(-0.1, 0.001, 0.1, 0.001) == {
        "unsafe_transfer": False,
        "inefficient_transfer": False,
    }


def test_read_units_csv(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from brats_uncertainty.statistics.units import read_units_csv

    p = tmp_path / "units.csv"
    p.write_text(
        "case_id,group_id,condition,region,risk,U1,U2,U3,I\n"
        "SYN-1,G1,-T1,ET,0.2,0.9,-0.1,0.95,-0.3\n"
        "SYN-1,G1,-T1,WT,0.1,0.95,-0.1,0.95,-0.2\n"
        "SYN-2,G2,-T1,ET,0.6,0.4,-0.5,0.7,-0.3\n",
        encoding="utf-8",
    )
    u = read_units_csv(p, "ET")
    assert len(u) == 2
    assert u.score("U1").tolist() == [0.9, 0.4]
    with pytest.raises(DataValidationError):
        read_units_csv(p, "TC")
