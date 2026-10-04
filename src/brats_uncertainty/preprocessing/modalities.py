"""MRI modality subsets and the protocol's missingness simulation (§10).

Channel order is fixed as ``[T1, T1c, T2, FLAIR]`` (§8). A missing sequence is
represented by setting its **normalized** channel to 0 (§10). There are
2^4 - 1 = 15 non-empty subsets (C15). C5 = {Full, -T1, -T1c, -T2, -FLAIR}; C4 is
the four single-missing conditions (primary H-W estimand subset).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError

MODALITIES: tuple[str, ...] = ("T1", "T1c", "T2", "FLAIR")
MISSING_VALUE: float = 0.0


@dataclass(frozen=True, order=True)
class ModalitySubset:
    """A non-empty set of *available* modalities."""

    present: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.present:
            raise ValueError("a modality subset must contain at least one modality")
        unknown = set(self.present) - set(MODALITIES)
        if unknown:
            raise ValueError(f"unknown modalities: {sorted(unknown)}")
        if len(set(self.present)) != len(self.present):
            raise ValueError("duplicate modalities in subset")
        ordered = tuple(m for m in MODALITIES if m in self.present)
        object.__setattr__(self, "present", ordered)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(m for m in MODALITIES if m not in self.present)

    @property
    def is_full(self) -> bool:
        return len(self.present) == len(MODALITIES)

    @property
    def name(self) -> str:
        """Canonical condition name: 'Full', '-T1c' (single missing) or 'T1+T2'."""
        if self.is_full:
            return "Full"
        if len(self.missing) == 1:
            return f"-{self.missing[0]}"
        return "+".join(self.present)

    @property
    def channel_mask(self) -> NDArray[np.bool_]:
        """Boolean vector over MODALITIES; True = channel available."""
        return np.array([m in self.present for m in MODALITIES], dtype=bool)

    @classmethod
    def from_name(cls, name: str) -> ModalitySubset:
        if name == "Full":
            return cls(MODALITIES)
        if name.startswith("-") and name[1:] in MODALITIES:
            return cls(tuple(m for m in MODALITIES if m != name[1:]))
        parts = tuple(name.split("+"))
        return cls(parts)


FULL = ModalitySubset(MODALITIES)


def all_subsets() -> tuple[ModalitySubset, ...]:
    """All 15 non-empty subsets, ordered by size (descending) then channel order."""
    out: list[ModalitySubset] = []
    for k in range(len(MODALITIES), 0, -1):
        for combo in combinations(MODALITIES, k):
            out.append(ModalitySubset(combo))
    return tuple(out)


def non_full_subsets() -> tuple[ModalitySubset, ...]:
    """The 14 non-full, non-empty subsets used by the arm-B dropout policy."""
    return tuple(s for s in all_subsets() if not s.is_full)


C4: tuple[ModalitySubset, ...] = tuple(
    ModalitySubset(tuple(m for m in MODALITIES if m != missing)) for missing in MODALITIES
)
C5: tuple[ModalitySubset, ...] = (FULL, *C4)
C4_NAMES: tuple[str, ...] = tuple(s.name for s in C4)
C5_NAMES: tuple[str, ...] = tuple(s.name for s in C5)


def apply_missingness(
    image: NDArray[np.floating], subset: ModalitySubset, *, channel_axis: int = 0
) -> NDArray[np.floating]:
    """Return a copy of a normalized multi-channel image with absent channels set to 0.

    ``image`` must already be normalized (§10: the *normalized* channel is set to 0).
    """
    if image.ndim < 2:
        raise DataValidationError("image must have a channel axis plus spatial axes")
    if image.shape[channel_axis] != len(MODALITIES):
        raise DataValidationError(
            f"expected {len(MODALITIES)} channels {MODALITIES}, got {image.shape[channel_axis]}"
        )
    out = np.array(image, copy=True)
    moved = np.moveaxis(out, channel_axis, 0)
    for idx, m in enumerate(MODALITIES):
        if m not in subset.present:
            moved[idx] = MISSING_VALUE
    return out
