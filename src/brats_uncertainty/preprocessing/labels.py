"""Label-to-region mapping (§8) and nnU-Net label conversion.

BraTS 2021:   ET = {4}, TC = {1, 4}, WT = {1, 2, 4}.
BraTS-Africa (expected; to be verified on files at gate C1):
              ET = {3}, TC = {1, 3}, WT = {1, 2, 3}.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError

REGIONS: tuple[str, ...] = ("WT", "TC", "ET")

BRATS2021_REGIONS: dict[str, tuple[int, ...]] = {"ET": (4,), "TC": (1, 4), "WT": (1, 2, 4)}
BRATS_AFRICA_EXPECTED_REGIONS: dict[str, tuple[int, ...]] = {
    "ET": (3,),
    "TC": (1, 3),
    "WT": (1, 2, 3),
}

# nnU-Net requires consecutive integer labels. BraTS 2021 {0,1,2,4} is remapped
# to {0: bg, 1: edema(2), 2: necrosis/NCR(1), 3: ET(4)} so that the region-based
# definitions WT=(1,2,3), TC=(2,3), ET=(3,) are equivalent to §8.
BRATS2021_TO_NNUNET: dict[int, int] = {0: 0, 2: 1, 1: 2, 4: 3}
NNUNET_REGIONS: dict[str, tuple[int, ...]] = {"WT": (1, 2, 3), "TC": (2, 3), "ET": (3,)}


def region_masks(
    label: NDArray[np.integer],
    mapping: Mapping[str, Sequence[int]],
    *,
    allowed_values: Sequence[int] | None = None,
) -> dict[str, NDArray[np.bool_]]:
    """Boolean region masks from an integer label volume.

    Unexpected label values raise instead of being silently ignored.
    """
    values = set(np.unique(label).tolist())
    allowed = (
        set(allowed_values)
        if allowed_values is not None
        else ({0} | {v for vs in mapping.values() for v in vs})
    )
    unexpected = values - allowed
    if unexpected:
        raise DataValidationError(f"unexpected label values {sorted(unexpected)}")
    return {region: np.isin(label, list(vals)) for region, vals in mapping.items()}


def convert_brats2021_to_nnunet(label: NDArray[np.integer]) -> NDArray[np.uint8]:
    """Remap BraTS 2021 labels {0,1,2,4} to consecutive nnU-Net labels {0,1,2,3}."""
    values = set(np.unique(label).tolist())
    unexpected = values - set(BRATS2021_TO_NNUNET)
    if unexpected:
        raise DataValidationError(f"unexpected BraTS 2021 label values {sorted(unexpected)}")
    out = np.zeros(label.shape, dtype=np.uint8)
    for src, dst in BRATS2021_TO_NNUNET.items():
        out[label == src] = dst
    return out
