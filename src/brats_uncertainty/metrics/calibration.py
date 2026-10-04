"""Voxel-level calibration: ECE and Brier score within an ROI (§4 S4, replication).

- Computed on the ensemble-mean probability of a region.
- ROI = union of GT and predicted region, dilated by 3 voxels.
- ECE: 15 equal-width bins on the predicted foreground probability; per-bin
  |mean predicted probability - observed foreground frequency| weighted by the
  bin's voxel fraction. [Implementation choice: binary foreground-probability
  reliability; to be confirmed before eval-v1.]
- Per-case values are averaged over cases by the caller.
- An empty ROI (GT and prediction both empty) is undefined and returns NaN;
  such cases are excluded from averages and counted.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.metrics.morphology import dilate

PROTOCOL_ECE_BINS = 15
PROTOCOL_ROI_DILATION = 3


def calibration_roi(
    gt: NDArray[np.bool_], pred: NDArray[np.bool_], dilation: int = PROTOCOL_ROI_DILATION
) -> NDArray[np.bool_]:
    return dilate(np.logical_or(gt, pred), dilation)


def ece(
    prob: NDArray[np.floating], gt: NDArray[np.bool_], n_bins: int = PROTOCOL_ECE_BINS
) -> float:
    """Expected calibration error of foreground probabilities (flattened voxels)."""
    p = np.asarray(prob, dtype=np.float64).ravel()
    y = np.asarray(gt, dtype=bool).ravel()
    if p.shape != y.shape:
        raise ValueError("shape mismatch")
    if p.size == 0:
        return float("nan")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must lie in [0, 1]")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        sel = idx == b
        cnt = int(sel.sum())
        if cnt == 0:
            continue
        total += cnt / p.size * abs(float(p[sel].mean()) - float(y[sel].mean()))
    return total


def brier(prob: NDArray[np.floating], gt: NDArray[np.bool_]) -> float:
    p = np.asarray(prob, dtype=np.float64).ravel()
    y = np.asarray(gt, dtype=np.float64).ravel()
    if p.shape != y.shape:
        raise ValueError("shape mismatch")
    if p.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def case_calibration(
    prob: NDArray[np.floating],
    gt: NDArray[np.bool_],
    threshold: float = 0.5,
    n_bins: int = PROTOCOL_ECE_BINS,
    dilation: int = PROTOCOL_ROI_DILATION,
) -> dict[str, float]:
    """Per-case ECE and Brier within the protocol ROI."""
    pred = np.asarray(prob) >= threshold
    roi = calibration_roi(np.asarray(gt, dtype=bool), pred, dilation)
    if not roi.any():
        return {"ece": float("nan"), "brier": float("nan"), "roi_voxels": 0.0}
    return {
        "ece": ece(np.asarray(prob)[roi], np.asarray(gt, dtype=bool)[roi], n_bins),
        "brier": brier(np.asarray(prob)[roi], np.asarray(gt, dtype=bool)[roi]),
        "roi_voxels": float(roi.sum()),
    }
