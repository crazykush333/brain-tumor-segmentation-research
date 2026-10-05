"""Independent re-implementations (pure Python / exact arithmetic where practical).

Nothing here imports the production metric, score or statistics modules. Definitions
are taken from the frozen protocol and docs/reproducibility/REPRODUCIBILITY.md §4:

- Dice: |A∩B|·2 / (|A|+|B|); both empty -> 1; exactly one empty -> 0 (§3).
- U1: mean of the 3 pairwise member Dice values (same empty rule), exact rational (§11).
- AURC with expected tie handling (§3), via the rank-weight identity
      AURC = (1/n) Σ_i r_(i) · (H_n − H_(i−1)),   H_m = Σ_{k≤m} 1/k,
  where r_(i) is the risk at rank i after replacing each tie block by its mean risk.
  (Production integrates the cumulative selective risk instead.)
- percentile CI: linear interpolation between order statistics (quantile type 7);
  two-sided p = min(1, 2·min(P*(Δ≥0), P*(Δ≤0))) over finite replicates (§13).
- Holm step-down within a family (§14).
- τ_q: largest observed U1 with equal-condition-weighted coverage ≥ q (§4 S7), exact.
- ECE: Σ_b |Σp_b − Σy_b| / N over 15 equal-width bins; Brier: SSE / N (§4 S4).
- S5: relative ET volume error ≥ 40 % / 65 % for GT ET ≥ 1 mL, exact integers.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction


# ------------------------------------------------------------------ unit level
def dice_counts(size_a: int, size_b: int, inter: int) -> Fraction:
    if size_a == 0 and size_b == 0:
        return Fraction(1)
    if size_a == 0 or size_b == 0:
        return Fraction(0)
    return Fraction(2 * inter, size_a + size_b)


def u1_counts(voxels: Sequence[int], pair_inter: Sequence[int]) -> Fraction:
    """voxels = (|M0|, |M1|, |M2|); pair_inter = (|M0∩M1|, |M0∩M2|, |M1∩M2|)."""
    pairs = ((0, 1), (0, 2), (1, 2))
    total = sum(
        (dice_counts(voxels[a], voxels[b], pair_inter[k]) for k, (a, b) in enumerate(pairs)),
        Fraction(0),
    )
    return total / 3


def ece_brier_bins(bins: Sequence[tuple[int, float, int]], sse: float) -> tuple[float, float, int]:
    n = sum(c for c, _, _ in bins)
    if n == 0:
        return math.nan, math.nan, 0
    ece = math.fsum(abs(sp - sy) for _, sp, sy in bins) / n
    return ece, sse / n, n


def volume_failure(pred_vox: int, gt_vox: int, voxel_ml: Fraction, rel: Fraction) -> bool | None:
    if gt_vox * voxel_ml < 1:  # GT ET < 1 mL: ineligible (study-defined minimum)
        return None
    return Fraction(abs(pred_vox - gt_vox), gt_vox) >= rel


# ------------------------------------------------------------------ ranking metrics
def aurc(confidence: Sequence[float], risk: Sequence[float]) -> float:
    n = len(confidence)
    if n == 0 or n != len(risk):
        raise ValueError("AURC needs equally long, non-empty inputs")
    order = sorted(range(n), key=lambda i: -confidence[i])
    expected: list[float] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and confidence[order[j + 1]] == confidence[order[i]]:
            j += 1
        block = [risk[order[k]] for k in range(i, j + 1)]
        expected += [math.fsum(block) / len(block)] * len(block)
        i = j + 1
    harmonic = [0.0] * (n + 1)
    for m in range(1, n + 1):
        harmonic[m] = harmonic[m - 1] + 1.0 / m
    return math.fsum(expected[i] * (harmonic[n] - harmonic[i]) for i in range(n)) / n


def delta_aurc(confidence: Sequence[float], risk: Sequence[float]) -> float:
    """AURC(U1) − AURC(I); I is constant within a condition, so AURC(I) = mean risk."""
    return aurc(confidence, risk) - math.fsum(risk) / len(risk)


# ------------------------------------------------------------------ inference helpers
def percentile(values: Sequence[float], q: float) -> float:
    v = sorted(x for x in values if math.isfinite(x))
    if not v:
        return math.nan
    h = (len(v) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (h - lo) * (v[hi] - v[lo])


def p_two_sided(values: Sequence[float]) -> float:
    v = [x for x in values if math.isfinite(x)]
    if not v:
        return math.nan
    ge = sum(1 for x in v if x >= 0) / len(v)
    le = sum(1 for x in v if x <= 0) / len(v)
    return min(1.0, 2.0 * min(ge, le))


def holm(p: Mapping[str, float]) -> dict[str, float]:
    items = sorted(p.items(), key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, float] = {}
    running = 0.0
    for rank, (k, pv) in enumerate(items):
        running = max(running, min(1.0, (m - rank) * pv))
        out[k] = running
    return out


def coverage_risk(
    u1: Sequence[float],
    risk: Sequence[float],
    cond: Sequence[str],
    tau: float,
    conditions: Sequence[str],
) -> tuple[Fraction, float]:
    """Equal-condition-weighted coverage (exact) and selective risk of U1 >= tau."""
    cov = Fraction(0)
    num = 0.0
    den = 0.0
    for c in conditions:
        idx = [i for i in range(len(u1)) if cond[i] == c]
        acc = [i for i in idx if u1[i] >= tau]
        cov += Fraction(len(acc), len(idx))
        w = 1.0 / (len(conditions) * len(idx))
        num += math.fsum(w * risk[i] for i in acc)
        den += w * len(acc)
    return cov / len(conditions), (num / den if den > 0 else math.nan)


def tau_q(
    u1: Sequence[float], cond: Sequence[str], q: float, conditions: Sequence[str]
) -> tuple[float, Fraction]:
    target = Fraction(repr(float(q)))
    for t in sorted(set(u1), reverse=True):
        cov, _ = coverage_risk(u1, [0.0] * len(u1), cond, t, conditions)
        if cov >= target:
            return t, cov
    raise AssertionError("unreachable: the minimum U1 gives coverage 1")
