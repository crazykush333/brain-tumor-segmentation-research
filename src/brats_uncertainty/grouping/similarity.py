"""WT-label Dice between ground-truth masks and the exhaustive pairwise screen.

All BraTS cases share SRI24 space, so no registration is performed (§6.2).
The screen compares every unordered pair. Two **exact** prunings avoid needless
voxel intersections without changing any result:

1. Dice(A, B) <= 2 min(|A|, |B|) / (|A| + |B|); if this bound is below T_screen
   the pair cannot be flagged.
2. Disjoint bounding boxes imply Dice = 0.

Only flagged pairs are returned: the full development similarity distribution
is never materialized, consistent with the no-threshold-shopping rule.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.metrics.dice import dice_from_counts


@dataclass(frozen=True)
class MaskIndex:
    """Sparse representation of a binary mask: sorted flat voxel indices + bbox."""

    case_id: str
    shape: tuple[int, ...]
    flat: NDArray[np.int64]
    bbox_min: tuple[int, ...]
    bbox_max: tuple[int, ...]

    @property
    def size(self) -> int:
        return int(self.flat.size)

    @classmethod
    def from_mask(cls, case_id: str, mask: NDArray[np.bool_]) -> MaskIndex:
        m = np.asarray(mask, dtype=bool)
        flat = np.flatnonzero(m).astype(np.int64)
        if flat.size:
            coords = np.argwhere(m)
            lo = tuple(int(v) for v in coords.min(axis=0))
            hi = tuple(int(v) for v in coords.max(axis=0))
        else:
            lo = hi = tuple(-1 for _ in m.shape)
        return cls(case_id=case_id, shape=tuple(m.shape), flat=flat, bbox_min=lo, bbox_max=hi)


def _bbox_disjoint(a: MaskIndex, b: MaskIndex) -> bool:
    return any(
        amax < bmin or bmax < amin
        for amin, amax, bmin, bmax in zip(
            a.bbox_min, a.bbox_max, b.bbox_min, b.bbox_max, strict=True
        )
    )


def wt_dice(a: MaskIndex, b: MaskIndex) -> float:
    if a.shape != b.shape:
        raise DataValidationError(f"shape mismatch {a.case_id} {a.shape} vs {b.case_id} {b.shape}")
    if a.size == 0 or b.size == 0 or _bbox_disjoint(a, b):
        return dice_from_counts(a.size, b.size, 0)
    inter = int(np.intersect1d(a.flat, b.flat, assume_unique=True).size)
    return dice_from_counts(a.size, b.size, inter)


@dataclass(frozen=True)
class FlaggedPair:
    case_a: str
    case_b: str
    wt_dice: float

    @property
    def key(self) -> tuple[str, str]:
        return (self.case_a, self.case_b)


@dataclass(frozen=True)
class ScreenResult:
    t_screen: float
    n_cases: int
    n_pairs_compared: int
    flagged: tuple[FlaggedPair, ...]


def pair_key(a: str, b: str) -> tuple[str, str]:
    if a == b:
        raise ValueError("a pair needs two distinct cases")
    return (a, b) if a < b else (b, a)


def pairwise_screen(
    masks: Mapping[str, MaskIndex] | Iterable[MaskIndex], t_screen: float
) -> ScreenResult:
    """Flag every unordered pair with WT-label Dice >= t_screen."""
    items = sorted(masks.values() if isinstance(masks, Mapping) else masks, key=lambda m: m.case_id)
    ids = [m.case_id for m in items]
    if len(ids) != len(set(ids)):
        raise DataValidationError("duplicate case IDs in screen input")
    if not 0.0 < t_screen <= 1.0:
        raise ValueError("t_screen must be in (0, 1]")
    flagged: list[FlaggedPair] = []
    n_pairs = 0
    for a, b in combinations(items, 2):
        n_pairs += 1
        sa, sb = a.size, b.size
        if sa and sb and 2.0 * min(sa, sb) / (sa + sb) < t_screen:
            continue
        d = wt_dice(a, b)
        if d >= t_screen:
            ka, kb = pair_key(a.case_id, b.case_id)
            flagged.append(FlaggedPair(ka, kb, d))
    return ScreenResult(
        t_screen=t_screen, n_cases=len(items), n_pairs_compared=n_pairs, flagged=tuple(flagged)
    )
