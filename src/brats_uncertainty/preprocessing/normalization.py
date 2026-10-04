"""Reference z-score normalization within the non-zero mask (§8).

Training and inference use nnU-Net v2's own ``ZScoreNormalization`` (protocol §8).
This reference implementation exists so that the missingness operation
(set the *normalized* channel to 0) can be tested and quality-checked outside
nnU-Net. It is not a new preprocessing method.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError


def nonzero_mask(image: NDArray[np.floating], channel_axis: int = 0) -> NDArray[np.bool_]:
    """Union over channels of voxels that are non-zero (the brain mask)."""
    return np.any(np.moveaxis(image, channel_axis, 0) != 0, axis=0)


def zscore_within_mask(
    image: NDArray[np.floating], channel_axis: int = 0, eps: float = 1e-8
) -> NDArray[np.float32]:
    """Per-channel z-score over the non-zero mask; voxels outside the mask set to 0."""
    if image.ndim < 2:
        raise DataValidationError("image must have a channel axis plus spatial axes")
    img = np.moveaxis(np.asarray(image, dtype=np.float64), channel_axis, 0)
    mask = np.any(img != 0, axis=0)
    out = np.zeros_like(img)
    if not mask.any():
        raise DataValidationError("empty non-zero mask: image contains no foreground voxels")
    for c in range(img.shape[0]):
        vals = img[c][mask]
        mean = float(vals.mean())
        std = float(vals.std())
        out[c][mask] = (img[c][mask] - mean) / max(std, eps)
    return np.moveaxis(out, 0, channel_axis).astype(np.float32)
