"""Framework-independent parts of the guarded trainer module (no nnU-Net needed)."""

from __future__ import annotations

import numpy as np
import pytest

from brats_uncertainty.models import nnunet_trainers as tr
from brats_uncertainty.preprocessing.modalities import MODALITIES


def test_seed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRATS_UNC_SEED", raising=False)
    with pytest.raises(RuntimeError, match="must be set"):
        tr._seed_from_env()
    monkeypatch.setenv("BRATS_UNC_SEED", "3")
    with pytest.raises(RuntimeError, match="not in protocol seeds"):
        tr._seed_from_env()
    monkeypatch.setenv("BRATS_UNC_SEED", "2")
    assert tr._seed_from_env() == 2


def test_dropout_transform_on_numpy_batch() -> None:
    batch = np.ones((16, len(MODALITIES), 4, 4, 4), dtype=np.float32)
    out = tr.DropoutTransform(seed=0)(data=batch, target=None)
    data = out["data"]
    assert data.shape == batch.shape
    for b in range(data.shape[0]):
        zeroed = [bool(np.all(data[b, c] == 0)) for c in range(len(MODALITIES))]
        assert not all(zeroed)  # never all four missing
        for c in range(len(MODALITIES)):
            assert zeroed[c] or np.all(data[b, c] == 1)
    assert out["target"] is None


def test_dropout_transform_is_seeded() -> None:
    batch = np.ones((32, 4, 2, 2, 2), dtype=np.float32)
    a = tr.DropoutTransform(seed=1)(data=batch)["data"]
    b = tr.DropoutTransform(seed=1)(data=batch)["data"]
    np.testing.assert_array_equal(a, b)
