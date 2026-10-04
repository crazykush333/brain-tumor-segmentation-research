from __future__ import annotations

import numpy as np
import pytest

from brats_uncertainty.data.validation import validate_case_arrays
from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.labels import (
    BRATS2021_REGIONS,
    BRATS_AFRICA_EXPECTED_REGIONS,
    NNUNET_REGIONS,
    convert_brats2021_to_nnunet,
    region_masks,
)
from brats_uncertainty.preprocessing.normalization import zscore_within_mask
from tests.fixtures.synthetic import synthetic_image


def test_brats2021_region_mapping() -> None:
    label = np.array([0, 1, 2, 4])
    m = region_masks(label, BRATS2021_REGIONS)
    assert m["ET"].tolist() == [False, False, False, True]
    assert m["TC"].tolist() == [False, True, False, True]
    assert m["WT"].tolist() == [False, True, True, True]


def test_brats_africa_expected_mapping() -> None:
    label = np.array([0, 1, 2, 3])
    m = region_masks(label, BRATS_AFRICA_EXPECTED_REGIONS)
    assert m["ET"].tolist() == [False, False, False, True]
    assert m["TC"].tolist() == [False, True, False, True]
    assert m["WT"].tolist() == [False, True, True, True]


def test_unexpected_label_values_raise() -> None:
    with pytest.raises(DataValidationError):
        region_masks(np.array([0, 3]), BRATS2021_REGIONS)
    with pytest.raises(DataValidationError):
        convert_brats2021_to_nnunet(np.array([0, 3]))


def test_nnunet_conversion_preserves_regions() -> None:
    rng = np.random.default_rng(0)
    label = rng.choice([0, 1, 2, 4], size=(6, 6, 6))
    converted = convert_brats2021_to_nnunet(label)
    orig = region_masks(label, BRATS2021_REGIONS)
    new = region_masks(converted, NNUNET_REGIONS)
    for r in ("WT", "TC", "ET"):
        np.testing.assert_array_equal(orig[r], new[r])


def test_zscore_within_mask() -> None:
    img = synthetic_image(np.random.default_rng(3))
    out = zscore_within_mask(img)
    mask = np.any(img != 0, axis=0)
    for c in range(4):
        assert abs(out[c][mask].mean()) < 1e-5
        assert abs(out[c][mask].std() - 1) < 1e-4
        assert np.all(out[c][~mask] == 0)


def test_zscore_empty_raises() -> None:
    with pytest.raises(DataValidationError):
        zscore_within_mask(np.zeros((4, 3, 3, 3)))


def test_validate_case_arrays() -> None:
    img = synthetic_image(np.random.default_rng(4))
    label = np.zeros(img.shape[1:], dtype=np.int16)
    facts = validate_case_arrays("SYN-1", img, label, [0, 1, 2, 4])
    assert facts["label_values"] == [0]
    bad = img.copy()
    bad[2] = 0
    with pytest.raises(DataValidationError, match="no signal"):
        validate_case_arrays("SYN-1", bad, label, [0, 1, 2, 4])
    with pytest.raises(DataValidationError):
        validate_case_arrays("SYN-1", img, label + 3, [0, 1, 2, 4])
    with pytest.raises(DataValidationError):
        validate_case_arrays("SYN-1", img[:3], None, [0])
