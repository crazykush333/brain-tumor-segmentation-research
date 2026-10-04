"""Deterministic U1 operating threshold tau_q and threshold transfer (§4 S7, §19).

tau_q = the largest observed U1 value such that coverage(validation C4 units,
U1 >= tau_q) >= q, with equal condition weighting over C4. Full is never used.
No interpolation, no random tie-breaking; all units with U1 >= tau are accepted.

Equal condition weighting is implemented by weighting every unit of condition c
by 1 / (|C4| * n_c), so coverage = mean over C4 of the per-condition coverage
and selective risk = weighted mean risk of accepted units. [Implementation of
"equal condition weighting"; with balanced conditions it equals the pooled
unweighted value.]

Transfer: Delta-risk = target selective risk - validation selective risk;
Delta-coverage = target coverage - validation coverage, with **independent**
patient-group bootstraps of the validation and target sets; tau is not
re-estimated within the bootstrap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.preprocessing.modalities import C4_NAMES
from brats_uncertainty.statistics.bootstrap import (
    PROTOCOL_REPLICATES,
    PROTOCOL_SEED,
    BootstrapResult,
    GroupIndex,
    percentile_ci,
    two_sided_p,
)
from brats_uncertainty.statistics.units import UnitTable

PROTOCOL_Q = (0.80, 0.70, 0.90)
FAILURE_ANALYSIS_Q = 0.20


def _c4_weights(condition: NDArray[np.str_], conditions: Sequence[str]) -> NDArray[np.float64]:
    if "Full" in conditions:
        raise ProtocolDeviationError("Full must not be used for tau estimation or transfer (§4 S7)")
    w = np.zeros(condition.size, dtype=np.float64)
    present = [c for c in conditions if np.any(condition == c)]
    if len(present) != len(conditions):
        missing = sorted(set(conditions) - set(present))
        raise ValueError(f"conditions without units: {missing}")
    for c in conditions:
        sel = condition == c
        w[sel] = 1.0 / (len(conditions) * sel.sum())
    return w


def weighted_coverage_risk(
    u1: NDArray[np.float64],
    risk: NDArray[np.float64],
    condition: NDArray[np.str_],
    tau: float,
    conditions: Sequence[str] = C4_NAMES,
) -> tuple[float, float]:
    """(coverage, selective risk) of the rule U1 >= tau with equal condition weighting."""
    keep = np.isin(condition, list(conditions))
    u, r, c = u1[keep], risk[keep], condition[keep]
    w = _c4_weights(c, conditions)
    acc = u >= tau
    cov = float(w[acc].sum() / w.sum())
    sel_risk = float((w[acc] * r[acc]).sum() / w[acc].sum()) if acc.any() else float("nan")
    return cov, sel_risk


@dataclass(frozen=True)
class TauResult:
    q: float
    tau: float
    realized_coverage: float


def select_tau(
    u1: NDArray[np.float64],
    condition: NDArray[np.str_],
    q: float,
    conditions: Sequence[str] = C4_NAMES,
) -> TauResult:
    """Deterministic >= rule on validation C4 units."""
    if q not in (*PROTOCOL_Q, FAILURE_ANALYSIS_Q):
        raise ProtocolDeviationError(
            f"q={q} is not a protocol value {(*PROTOCOL_Q, FAILURE_ANALYSIS_Q)}"
        )
    keep = np.isin(condition, list(conditions))
    u, c = u1[keep], condition[keep]
    _c4_weights(c, conditions)  # validates the population (no Full, all conditions present)
    per_cond = [u[c == name] for name in conditions]
    q_exact = Fraction(repr(float(q)))
    candidates = np.unique(u)[::-1]  # descending observed values
    for tau in candidates:
        # exact equal-condition-weighted coverage: mean over conditions of k_c / n_c
        cov = sum((Fraction(int(np.sum(v >= tau)), v.size) for v in per_cond), Fraction(0)) / len(
            per_cond
        )
        if cov >= q_exact:
            return TauResult(q=q, tau=float(tau), realized_coverage=float(cov))
    raise AssertionError("unreachable: the minimum observed U1 gives coverage 1")


@dataclass(frozen=True)
class TransferResult:
    tau: TauResult
    validation_coverage: float
    validation_risk: float
    target_coverage: float
    target_risk: float
    delta_risk: BootstrapResult
    delta_coverage: BootstrapResult


def threshold_transfer(
    validation: UnitTable,
    target: UnitTable,
    tau: TauResult,
    *,
    n_replicates: int = PROTOCOL_REPLICATES,
    seed: int = PROTOCOL_SEED,
    conditions: Sequence[str] = C4_NAMES,
) -> TransferResult:
    """Delta-risk and Delta-coverage with independent group bootstraps (tau fixed)."""

    def stats(t: UnitTable, idx: NDArray[np.intp]) -> tuple[float, float]:
        return weighted_coverage_risk(
            t.score("U1")[idx], t.risk[idx], t.condition[idx], tau.tau, conditions
        )

    v_all = np.arange(len(validation))
    t_all = np.arange(len(target))
    v_cov, v_risk = stats(validation, v_all)
    t_cov, t_risk = stats(target, t_all)
    gv = GroupIndex(validation.group_id)
    gt = GroupIndex(target.group_id)
    rng = np.random.default_rng(seed)
    d_risk = np.empty(n_replicates)
    d_cov = np.empty(n_replicates)
    for b in range(n_replicates):
        vc, vr = stats(validation, gv.resample(rng))
        tc, tr = stats(target, gt.resample(rng))
        d_risk[b] = tr - vr
        d_cov[b] = tc - vc

    def result(est: float, reps: NDArray[np.float64]) -> BootstrapResult:
        lo, hi = percentile_ci(reps)
        return BootstrapResult(
            estimate=est,
            replicates=reps,
            ci_low=lo,
            ci_high=hi,
            p_value=two_sided_p(reps),
            n_replicates=n_replicates,
            n_undefined=int(np.sum(~np.isfinite(reps))),
            seed=seed,
        )

    return TransferResult(
        tau=tau,
        validation_coverage=v_cov,
        validation_risk=v_risk,
        target_coverage=t_cov,
        target_risk=t_risk,
        delta_risk=result(t_risk - v_risk, d_risk),
        delta_coverage=result(t_cov - v_cov, d_cov),
    )


def transfer_labels(
    delta_risk: float, p_risk_holm: float, delta_cov: float, p_cov_holm: float
) -> dict[str, bool]:
    """F3/F3b claim rules. A non-significant result never establishes safety or equivalence."""
    return {
        "unsafe_transfer": bool(p_risk_holm < 0.05 and delta_risk > 0),
        "inefficient_transfer": bool(p_cov_holm < 0.05 and delta_cov < 0),
    }
