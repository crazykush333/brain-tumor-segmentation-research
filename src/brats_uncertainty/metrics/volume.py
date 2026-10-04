"""ET volume error and the RANO 2.0-motivated binary volume failure (§4 S5).

Relative ET volume error >= 0.40 (sensitivity 0.65) counts as failure, only for
cases with GT ET >= 1 mL (a study-defined choice). The RANO thresholds concern
longitudinal change and are used only as clinically motivated proxies.

Threshold comparisons are exact: volumes are converted to rationals via their
shortest decimal representation (``Fraction(repr(x))``), so a relative error of
exactly 40% (e.g. 1.4 mL vs 1.0 mL) is a failure despite binary floating point.
``volume_failure_from_counts`` compares integer voxel counts directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

import numpy as np
from numpy.typing import NDArray

PRIMARY_REL_THRESHOLD = 0.40
SENSITIVITY_REL_THRESHOLD = 0.65
MIN_GT_ET_ML = 1.0
_THRESHOLDS = {PRIMARY_REL_THRESHOLD: Fraction(2, 5), SENSITIVITY_REL_THRESHOLD: Fraction(13, 20)}


def volume_ml(mask: NDArray[np.bool_], spacing_mm: Sequence[float] = (1.0, 1.0, 1.0)) -> float:
    voxel_mm3 = float(np.prod(np.asarray(spacing_mm, dtype=np.float64)))
    return float(np.asarray(mask, dtype=bool).sum()) * voxel_mm3 / 1000.0


def absolute_volume_error_ml(pred_ml: float, gt_ml: float) -> float:
    return abs(pred_ml - gt_ml)


def relative_volume_error(pred_ml: float, gt_ml: float) -> float:
    if gt_ml <= 0:
        raise ValueError("relative error undefined for empty ground truth")
    return abs(pred_ml - gt_ml) / gt_ml


def _threshold(threshold: float) -> Fraction:
    if threshold not in _THRESHOLDS:
        raise ValueError("threshold must be the protocol value 0.40 or 0.65")
    return _THRESHOLDS[threshold]


def _exact(x: float) -> Fraction:
    return Fraction(repr(float(x)))


def volume_failure(
    pred_ml: float, gt_ml: float, threshold: float = PRIMARY_REL_THRESHOLD
) -> bool | None:
    """Binary failure; ``None`` if the case is ineligible (GT ET < 1 mL)."""
    t = _threshold(threshold)
    gt, pred = _exact(gt_ml), _exact(pred_ml)
    if gt < _exact(MIN_GT_ET_ML):
        return None
    return abs(pred - gt) / gt >= t


def volume_failure_from_counts(
    pred_voxels: int,
    gt_voxels: int,
    voxel_volume_ml: float = 0.001,
    threshold: float = PRIMARY_REL_THRESHOLD,
) -> bool | None:
    """Exact integer version for voxel counts (1 mm isotropic -> 0.001 mL per voxel)."""
    t = _threshold(threshold)
    if min(pred_voxels, gt_voxels) < 0:
        raise ValueError("voxel counts must be non-negative")
    if gt_voxels * _exact(voxel_volume_ml) < _exact(MIN_GT_ET_ML):
        return None
    return Fraction(abs(pred_voxels - gt_voxels), gt_voxels) >= t
