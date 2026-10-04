"""Risk-coverage curve and AURC with expected tie handling (protocol §3, §12).

For n units ranked by descending confidence, AURC is the mean selective risk over
coverages k/n, k = 1..n:

    AURC = (1/n) * sum_k (1/k) * sum_{i<=k} r_(i)

Ties are handled by the **expected value under random tie-breaking**. Because
AURC is linear in the cumulative risk sums, and the expected sum of any j units
drawn from a tie block equals j times the block's mean risk, the expectation is
obtained exactly by replacing each unit's risk with the mean risk of its tie
block. For a constant score (the indicator I within a condition), every unit is
in one block, so AURC equals the mean risk exactly.

``weights`` support equal-condition weighting where needed (S7/S13); the
unweighted definition above is the default.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _validate(
    confidence: ArrayLike, risk: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    c = np.asarray(confidence, dtype=np.float64).ravel()
    r = np.asarray(risk, dtype=np.float64).ravel()
    if c.shape != r.shape:
        raise ValueError(f"confidence/risk length mismatch {c.shape} vs {r.shape}")
    if c.size == 0:
        raise ValueError("AURC requires at least one unit")
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(r))):
        raise ValueError("confidence and risk must be finite")
    return c, r


def tie_expected_risks(
    confidence: ArrayLike, risk: ArrayLike
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Sort by descending confidence; replace risks by their tie-block means.

    Returns (sorted_confidence, expected_sorted_risk).
    """
    c, r = _validate(confidence, risk)
    order = np.argsort(-c, kind="stable")
    cs = c[order]
    rs = r[order]
    out = rs.copy()
    # boundaries of tie blocks in the sorted confidence
    change = np.flatnonzero(np.diff(cs) != 0) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [cs.size]))
    for s, e in zip(starts, ends, strict=True):
        if e - s > 1:
            out[s:e] = rs[s:e].mean()
    return cs, out


@dataclass(frozen=True)
class RiskCoverageCurve:
    coverage: NDArray[np.float64]
    selective_risk: NDArray[np.float64]
    confidence: NDArray[np.float64]


def risk_coverage_curve(confidence: ArrayLike, risk: ArrayLike) -> RiskCoverageCurve:
    """Expected (tie-averaged) selective risk at every coverage k/n."""
    cs, rs = tie_expected_risks(confidence, risk)
    n = rs.size
    k = np.arange(1, n + 1, dtype=np.float64)
    sel = np.cumsum(rs) / k
    return RiskCoverageCurve(coverage=k / n, selective_risk=sel, confidence=cs)


def aurc(confidence: ArrayLike, risk: ArrayLike) -> float:
    """Area under the risk-coverage curve (mean selective risk; expected ties)."""
    return float(risk_coverage_curve(confidence, risk).selective_risk.mean())


def oracle_aurc(risk: ArrayLike) -> float:
    """AURC of the optimal ranking (ascending risk)."""
    r = np.asarray(risk, dtype=np.float64).ravel()
    return aurc(-r, r)


def excess_aurc(confidence: ArrayLike, risk: ArrayLike) -> float:
    """e-AURC = AURC - oracle AURC. For two scores on the same predictions,
    their e-AURC difference equals their AURC difference (§3)."""
    return aurc(confidence, risk) - oracle_aurc(risk)


def auroc_failure(confidence: ArrayLike, failure: ArrayLike) -> float:
    """Exploratory AUROC for binary failure detection (§12); ties count 0.5.

    Higher confidence should indicate non-failure. Returns NaN if only one class.
    """
    c = np.asarray(confidence, dtype=np.float64).ravel()
    f = np.asarray(failure, dtype=bool).ravel()
    if c.shape != f.shape:
        raise ValueError("length mismatch")
    pos = c[~f]  # successes
    neg = c[f]  # failures
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    from scipy.stats import rankdata

    ranks = rankdata(np.concatenate([pos, neg]))
    u = ranks[: pos.size].sum() - pos.size * (pos.size + 1) / 2
    return float(u / (pos.size * neg.size))
