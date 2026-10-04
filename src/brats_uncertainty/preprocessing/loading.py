"""Loading of preprocessed multi-sequence cases (requires the optional ``io`` extra).

BraTS-provided images are already SRI24-registered, 1 mm isotropic and
skull-stripped (§8); no re-registration is performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.modalities import MODALITIES


@dataclass(frozen=True)
class CaseFiles:
    """Paths of one case's four sequences (in channel order) and optional label."""

    case_id: str
    images: tuple[Path, ...]
    label: Path | None

    def __post_init__(self) -> None:
        if len(self.images) != len(MODALITIES):
            raise DataValidationError(
                f"{self.case_id}: expected {len(MODALITIES)} image paths, got {len(self.images)}"
            )


def _require_nibabel() -> Any:
    try:
        import nibabel as nib
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "install the optional extra: pip install 'brats-uncertainty[io]'"
        ) from exc
    return nib


def load_case(case: CaseFiles) -> tuple[NDArray[np.float32], NDArray[np.int16] | None]:
    """Load a case as a (4, X, Y, Z) float32 array plus an optional int16 label.

    Validates that all volumes are 3-D and share shape and affine.
    """
    nib = _require_nibabel()
    arrays: list[NDArray[np.float32]] = []
    affine: Any = None
    shape: tuple[int, ...] | None = None
    for path in case.images:
        img = nib.load(str(path))
        data = np.asarray(img.get_fdata(dtype=np.float32))
        if data.ndim != 3:
            raise DataValidationError(f"{case.case_id}: {path.name} is not 3-D ({data.shape})")
        if shape is None:
            shape, affine = data.shape, img.affine
        elif data.shape != shape or not np.allclose(img.affine, affine, atol=1e-4):
            raise DataValidationError(f"{case.case_id}: {path.name} shape/affine mismatch")
        arrays.append(data)
    label = None
    if case.label is not None:
        lab_img = nib.load(str(case.label))
        label = np.asarray(lab_img.dataobj).astype(np.int16)
        if label.shape != shape:
            raise DataValidationError(f"{case.case_id}: label shape {label.shape} != {shape}")
    return np.stack(arrays, axis=0), label
