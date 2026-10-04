"""Arm-B modality-dropout policy (protocol §10), framework-independent.

Per training sample: with probability ``p_full`` = 0.5 the input is full;
otherwise one of the 14 non-full, non-empty subsets is chosen uniformly. The
policy is applied after augmentation and is fixed a priori (not tuned).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.preprocessing.modalities import (
    FULL,
    ModalitySubset,
    apply_missingness,
    non_full_subsets,
)

PROTOCOL_P_FULL = 0.5


@dataclass(frozen=True)
class ModalityDropoutPolicy:
    """Sampler for the arm-B policy. ``p_full`` is fixed by the protocol."""

    p_full: float = PROTOCOL_P_FULL
    subsets: tuple[ModalitySubset, ...] = field(default_factory=non_full_subsets)

    def __post_init__(self) -> None:
        if self.p_full != PROTOCOL_P_FULL:
            raise ProtocolDeviationError(
                f"p_full={self.p_full} deviates from the frozen protocol value {PROTOCOL_P_FULL}"
            )
        if len(self.subsets) != 14 or any(s.is_full for s in self.subsets):
            raise ProtocolDeviationError("policy must use exactly the 14 non-full subsets")

    def sample(self, rng: np.random.Generator) -> ModalitySubset:
        """Draw one subset for one training sample."""
        if rng.random() < self.p_full:
            return FULL
        return self.subsets[int(rng.integers(len(self.subsets)))]

    def probabilities(self) -> dict[str, float]:
        """Exact per-subset probabilities implied by the policy."""
        probs = {FULL.name: self.p_full}
        each = (1.0 - self.p_full) / len(self.subsets)
        probs.update({s.name: each for s in self.subsets})
        return probs

    def apply(
        self, image: NDArray[np.floating], rng: np.random.Generator, *, channel_axis: int = 0
    ) -> tuple[NDArray[np.floating], ModalitySubset]:
        """Sample a subset and zero the missing normalized channels of one sample."""
        subset = self.sample(rng)
        return apply_missingness(image, subset, channel_axis=channel_axis), subset

    def apply_batch(
        self, batch: NDArray[np.floating], rng: np.random.Generator
    ) -> tuple[NDArray[np.floating], list[ModalitySubset]]:
        """Apply independently per sample to a (B, C, ...) batch."""
        out = np.array(batch, copy=True)
        chosen: list[ModalitySubset] = []
        for b in range(out.shape[0]):
            out[b], subset = self.apply(out[b], rng, channel_axis=0)
            chosen.append(subset)
        return out, chosen
