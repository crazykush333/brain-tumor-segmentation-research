"""Per-case integrity checks on loaded arrays (shape, finiteness, labels, modalities)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.modalities import MODALITIES


def validate_case_arrays(
    case_id: str,
    image: NDArray[np.floating],
    label: NDArray[np.integer] | None,
    allowed_labels: Sequence[int],
    expected_shape: Sequence[int] | None = None,
) -> dict[str, object]:
    """Validate a (4, X, Y, Z) image and optional label; return summary facts.

    Raises DataValidationError on: wrong channel count, non-finite values, an
    all-zero modality (sequence absent in the source file), label/image shape
    mismatch or unexpected label values.
    """
    if image.ndim != 4 or image.shape[0] != len(MODALITIES):
        raise DataValidationError(f"{case_id}: image must be (4, X, Y, Z), got {image.shape}")
    if expected_shape is not None and tuple(image.shape[1:]) != tuple(expected_shape):
        raise DataValidationError(
            f"{case_id}: spatial shape {image.shape[1:]} != {tuple(expected_shape)}"
        )
    if not np.all(np.isfinite(image)):
        raise DataValidationError(f"{case_id}: non-finite intensities")
    empty = [m for i, m in enumerate(MODALITIES) if not np.any(image[i])]
    if empty:
        raise DataValidationError(f"{case_id}: modalities with no signal: {empty}")
    facts: dict[str, object] = {"case_id": case_id, "shape": list(image.shape[1:])}
    if label is not None:
        if label.shape != image.shape[1:]:
            raise DataValidationError(f"{case_id}: label shape {label.shape} != {image.shape[1:]}")
        values = sorted(int(v) for v in np.unique(label))
        unexpected = sorted(set(values) - set(allowed_labels))
        if unexpected:
            raise DataValidationError(f"{case_id}: unexpected label values {unexpected}")
        facts["label_values"] = values
    return facts
