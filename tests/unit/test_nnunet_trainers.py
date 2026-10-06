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


_FAKE_NNUNET = '''
import inspect


class nnUNetTrainer:
    """Mimics nnU-Net v2: constructor arguments are recorded from the subclass signature."""

    def __init__(self, plans, configuration, fold, dataset_json, device="cuda"):
        self.my_init_kwargs = {}
        for k in inspect.signature(self.__init__).parameters.keys():
            self.my_init_kwargs[k] = locals()[k]
        self.device = device
        self.num_epochs = 1000
        self.save_every = 50

    def get_dataloaders(self):
        return iter([{"data": None}]), None
'''


def test_trainers_construct_under_nnunet_signature_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Regression (EXP-001, 2026-10-06): ``*args, **kwargs`` crashed nnU-Net with KeyError."""
    import importlib
    import sys
    import types

    fake_torch = types.ModuleType("torch")
    fake_torch.device = lambda name: f"device:{name}"  # type: ignore[attr-defined]
    fake_torch.manual_seed = lambda s: None  # type: ignore[attr-defined]
    fake_torch.cuda = types.SimpleNamespace(manual_seed_all=lambda s: None)  # type: ignore[attr-defined]
    fake_torch.Tensor = type("Tensor", (), {})  # type: ignore[attr-defined]
    mod = types.ModuleType("nnunetv2.training.nnUNetTrainer.nnUNetTrainer")
    exec(_FAKE_NNUNET, mod.__dict__)
    for name in ("nnunetv2", "nnunetv2.training", "nnunetv2.training.nnUNetTrainer"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "nnunetv2.training.nnUNetTrainer.nnUNetTrainer", mod)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setenv("BRATS_UNC_SEED", "1")
    try:
        fresh = importlib.reload(tr)
        monkeypatch.setattr(fresh, "require_action", lambda action: None)
        for name in fresh.__all__:
            cls = getattr(fresh, name)
            if not name.startswith("nnUNetTrainer_"):
                continue
            t = cls({"p": 1}, "3d_fullres", 0, {"d": 1})
            assert set(t.my_init_kwargs) == {
                "plans",
                "configuration",
                "fold",
                "dataset_json",
                "device",
            }
            assert t.my_init_kwargs["fold"] == 0 and t.protocol_seed == 1
            assert t.num_epochs == cls.EPOCHS and t.save_every == cls.SAVE_EVERY
    finally:
        monkeypatch.undo()
        importlib.reload(tr)
