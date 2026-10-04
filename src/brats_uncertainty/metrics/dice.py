"""Dice coefficient with the protocol's empty-mask convention (§3).

Both masks empty -> 1.0; exactly one empty -> 0.0. Risk = 1 - Dice.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError


def dice(a: NDArray[np.bool_], b: NDArray[np.bool_]) -> float:
    """Dice between two binary masks of identical shape."""
    if a.shape != b.shape:
        raise DataValidationError(f"mask shape mismatch {a.shape} vs {b.shape}")
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    sa = int(a.sum())
    sb = int(b.sum())
    if sa == 0 and sb == 0:
        return 1.0
    if sa == 0 or sb == 0:
        return 0.0
    inter = int(np.logical_and(a, b).sum())
    return 2.0 * inter / (sa + sb)


def risk_from_dice(d: float) -> float:
    """Primary continuous risk = 1 - Dice."""
    if not 0.0 <= d <= 1.0:
        raise ValueError(f"Dice must be in [0, 1], got {d}")
    return 1.0 - d


def dice_from_counts(size_a: int, size_b: int, intersection: int) -> float:
    """Dice from voxel counts (same empty-mask convention)."""
    if min(size_a, size_b, intersection) < 0 or intersection > min(size_a, size_b):
        raise ValueError("invalid voxel counts")
    if size_a == 0 and size_b == 0:
        return 1.0
    if size_a == 0 or size_b == 0:
        return 0.0
    return 2.0 * intersection / (size_a + size_b)
