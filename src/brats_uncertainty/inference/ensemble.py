"""Three-member ensemble combination and thresholding (§9).

Ensemble = mean of the 3 members' sigmoid probabilities; masks use threshold 0.5.
Missingness at inference must be applied to the **normalized** (preprocessed)
tensor, never to raw intensities: zeroing a raw channel would change nnU-Net's
non-zero-mask z-score normalization. See ``apply_missingness_preprocessed``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.preprocessing.modalities import ModalitySubset, apply_missingness

PROTOCOL_THRESHOLD = 0.5
PROTOCOL_N_MEMBERS = 3


def _check_members(member_probs: Sequence[NDArray[np.floating]]) -> None:
    if len(member_probs) != PROTOCOL_N_MEMBERS:
        raise ProtocolDeviationError(
            f"ensemble must have exactly {PROTOCOL_N_MEMBERS} members, got {len(member_probs)}"
        )
    shapes = {np.shape(p) for p in member_probs}
    if len(shapes) != 1:
        raise ValueError(f"member probability shapes differ: {shapes}")
    for p in member_probs:
        arr = np.asarray(p)
        if arr.size and (float(arr.min()) < 0.0 or float(arr.max()) > 1.0):
            raise ValueError("member probabilities must lie in [0, 1]")


def ensemble_mean(member_probs: Sequence[NDArray[np.floating]]) -> NDArray[np.float32]:
    _check_members(member_probs)
    return np.mean(np.stack([np.asarray(p, dtype=np.float32) for p in member_probs]), axis=0)


def binarize(
    prob: NDArray[np.floating], threshold: float = PROTOCOL_THRESHOLD
) -> NDArray[np.bool_]:
    if threshold != PROTOCOL_THRESHOLD:
        raise ProtocolDeviationError(f"threshold {threshold} deviates from protocol 0.5")
    return np.asarray(prob) >= threshold


def member_masks(member_probs: Sequence[NDArray[np.floating]]) -> list[NDArray[np.bool_]]:
    _check_members(member_probs)
    return [binarize(p) for p in member_probs]


def apply_missingness_preprocessed(
    preprocessed: NDArray[np.floating], subset: ModalitySubset
) -> NDArray[np.floating]:
    """Zero absent channels of an nnU-Net-preprocessed (normalized) (C, ...) array."""
    return apply_missingness(preprocessed, subset, channel_axis=0)
