"""Confidence scores (protocol §11). Higher value = more confident.

- **U1 (primary):** mean pairwise Dice between the three members' binary masks
  (each thresholded at 0.5). Both empty -> 1 (per pair).
- **U2 (secondary, descriptive):** negative mean binary entropy of the
  ensemble-mean probability within the ROI (union of member masks dilated by 3
  voxels). Empty ROI -> entropy 0 (U2 = 0).
  [Implementation choice: entropy in bits (log base 2). Rank-invariant, so it
  does not affect AURC.]
- **U3 (exploratory):** seed-0 model's mean max-probability, max(p, 1-p), within
  the ROI. [Implementation choice: same ROI as U2; empty ROI -> 1.0.]
- **I (baseline):** -(validation mean risk of the condition) for the same arm's
  ensemble. Validation-only; never estimated from test or external data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.inference.ensemble import PROTOCOL_N_MEMBERS, binarize, ensemble_mean
from brats_uncertainty.metrics.morphology import dilate

ROI_DILATION = 3
_EPS = 1e-12


def u1_pairwise_dice(member_masks: Sequence[NDArray[np.bool_]]) -> float:
    """Mean pairwise Dice between the 3 member masks (empty-pair convention -> 1)."""
    if len(member_masks) != PROTOCOL_N_MEMBERS:
        raise ProtocolDeviationError(f"U1 requires exactly {PROTOCOL_N_MEMBERS} members")
    # Exact rational mean so that mathematically tied U1 values are bitwise tied
    # (ties matter for the expected-tie AURC and for the tau_q >= rule).
    if len({np.shape(m) for m in member_masks}) != 1:
        raise ValueError("member masks must share one shape")
    total = Fraction(0)
    for a, b in combinations(member_masks, 2):
        sa, sb = int(np.count_nonzero(a)), int(np.count_nonzero(b))
        if sa == 0 and sb == 0:
            total += 1
        elif sa and sb:
            total += Fraction(2 * int(np.count_nonzero(np.logical_and(a, b))), sa + sb)
    return float(total / 3)


def uncertainty_roi(
    member_masks: Sequence[NDArray[np.bool_]], dilation: int = ROI_DILATION
) -> NDArray[np.bool_]:
    union = np.logical_or.reduce([np.asarray(m, dtype=bool) for m in member_masks])
    return dilate(union, dilation)


def binary_entropy_bits(p: NDArray[np.floating]) -> NDArray[np.float64]:
    q = np.clip(np.asarray(p, dtype=np.float64), _EPS, 1.0 - _EPS)
    return -(q * np.log2(q) + (1.0 - q) * np.log2(1.0 - q))


def u2_negative_entropy(mean_prob: NDArray[np.floating], roi: NDArray[np.bool_]) -> float:
    if not roi.any():
        return 0.0  # empty ROI -> entropy 0
    return -float(binary_entropy_bits(np.asarray(mean_prob)[roi]).mean())


def u3_max_probability(seed0_prob: NDArray[np.floating], roi: NDArray[np.bool_]) -> float:
    if not roi.any():
        return 1.0
    p = np.asarray(seed0_prob, dtype=np.float64)[roi]
    return float(np.maximum(p, 1.0 - p).mean())


def case_scores(
    member_probs: Sequence[NDArray[np.floating]], *, seed0_index: int = 0
) -> dict[str, float]:
    """U1, U2 and U3 for one case and one region from the members' probabilities.

    ``member_probs`` must be ordered by seed (0, 1, 2).
    """
    mean_prob = ensemble_mean(member_probs)
    masks = [binarize(p) for p in member_probs]
    roi = uncertainty_roi(masks)
    return {
        "U1": u1_pairwise_dice(masks),
        "U2": u2_negative_entropy(mean_prob, roi),
        "U3": u3_max_probability(member_probs[seed0_index], roi),
    }


def indicator_scores(validation_mean_risk: Mapping[str, float]) -> dict[str, float]:
    """I per condition = -(validation mean risk). Input must come from validation."""
    out: dict[str, float] = {}
    for cond, r in validation_mean_risk.items():
        if not 0.0 <= r <= 1.0 or not np.isfinite(r):
            raise ValueError(f"validation mean risk for {cond} must be in [0, 1], got {r}")
        out[cond] = -float(r)
    return out
