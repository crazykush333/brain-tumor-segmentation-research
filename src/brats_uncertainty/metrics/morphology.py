"""Binary dilation used for ROIs (U2/U3 and ECE/Brier).

"Dilated by 3 voxels" (§4 S4, §11) is implemented as dilation by a Euclidean
ball of radius 3 voxels (all offsets with dx^2+dy^2+dz^2 <= 9). The protocol
does not name the structuring element; this is a documented implementation
choice to be confirmed by the owner before eval-v1 (gate C6).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage


@lru_cache(maxsize=8)
def ball(radius: int, ndim: int = 3) -> NDArray[np.bool_]:
    if radius < 0:
        raise ValueError("radius must be >= 0")
    grid = np.indices((2 * radius + 1,) * ndim) - radius
    return np.asarray((grid**2).sum(axis=0) <= radius**2)


def dilate(mask: NDArray[np.bool_], radius: int) -> NDArray[np.bool_]:
    """Binary dilation by a Euclidean ball of ``radius`` voxels."""
    m = np.asarray(mask, dtype=bool)
    if radius == 0 or not m.any():
        return m.copy()
    return np.asarray(ndimage.binary_dilation(m, structure=ball(radius, m.ndim)))
