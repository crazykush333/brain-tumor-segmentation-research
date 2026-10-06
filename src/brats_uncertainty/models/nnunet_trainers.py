"""Guarded nnU-Net v2 trainer classes for arms A and B (requires the ``nnunet`` extra).

STATUS: TEMPLATE, NOT YET VERIFIED against the nnU-Net version that will be
pinned at M1/EXP-001. nnU-Net's trainer and transform APIs change between
releases. Before any training, this module must be checked against the pinned
version (see docs/reproducibility/COMPUTE.md). Training is additionally blocked
by research gates until B12 and D6 are closed.

To be discovered by nnU-Net, these classes must be importable from
``nnunetv2.training.nnUNetTrainer`` (e.g. by copying/symlinking this file into
that package at environment-setup time). They are not a new architecture:
they only fix the epoch count, the seed and (arm B) append the §10 dropout
transform after nnU-Net's own augmentation pipeline.
"""

from __future__ import annotations

import os
import random
from typing import Any

import numpy as np

from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.models.dropout import ModalityDropoutPolicy
from brats_uncertainty.models.nnunet import PROTOCOL_EPOCHS, PROTOCOL_SEEDS

try:  # optional heavy dependency
    import torch
    from nnunetv2.training.nnUNetTrainer.nnUNetTrainer import nnUNetTrainer
except ImportError:  # pragma: no cover - exercised only with the nnunet extra
    nnUNetTrainer = None  # noqa: N816 - upstream class name
    torch = None


def _seed_from_env() -> int:
    raw = os.environ.get("BRATS_UNC_SEED")
    if raw is None:
        raise RuntimeError("BRATS_UNC_SEED must be set (protocol seeds 0, 1, 2)")
    seed = int(raw)
    if seed not in PROTOCOL_SEEDS:
        raise RuntimeError(f"seed {seed} not in protocol seeds {PROTOCOL_SEEDS}")
    return seed


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


class DropoutTransform:
    """Batch-level transform applying the §10 policy to the ``data`` entry.

    Applied after nnU-Net augmentation. Operates per sample on normalized data.
    """

    def __init__(self, seed: int) -> None:
        self.policy = ModalityDropoutPolicy()
        self.rng = np.random.default_rng(seed)

    def __call__(self, **data_dict: Any) -> dict[str, Any]:
        data = data_dict["data"]
        is_tensor = torch is not None and isinstance(data, torch.Tensor)
        arr = data.cpu().numpy() if is_tensor else np.asarray(data)
        if arr.ndim == 4:  # single sample (C, X, Y, Z)
            out, _ = self.policy.apply(arr, self.rng)
        else:
            out, _ = self.policy.apply_batch(arr, self.rng)
        data_dict["data"] = torch.from_numpy(out) if is_tensor else out
        return data_dict


_EXPORTS = (
    "DropoutTransform",
    "nnUNetTrainer_BratsUnc_150ep",
    "nnUNetTrainer_BratsUnc_150ep_ModalityDropout",
    "nnUNetTrainer_BratsUnc_250ep",
    "nnUNetTrainer_BratsUnc_250ep_ModalityDropout",
    "nnUNetTrainer_BratsUnc_Pilot5ep",
    "nnUNetTrainer_BratsUnc_Pilot5ep_ModalityDropout",
)


def _wrap_train_loader(train_loader: Any, transform: DropoutTransform) -> Any:
    class _Wrapped:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        def __iter__(self) -> Any:
            return self

        def __next__(self) -> Any:
            return transform(**next(self.inner))

        def __getattr__(self, name: str) -> Any:
            return getattr(self.inner, name)

    return _Wrapped(train_loader)


if nnUNetTrainer is not None:  # pragma: no cover - requires nnunetv2 + torch

    class _BratsUncBase(nnUNetTrainer):
        """Fixes the epoch count, checkpoint interval and protocol seed; gated."""

        ARM = "A"
        EPOCHS = PROTOCOL_EPOCHS
        SAVE_EVERY = 5
        GATE = "train_main"

        # nnU-Net records its constructor arguments by reading each parameter name of
        # ``self.__init__``'s signature from its own locals, so this signature must match
        # nnUNetTrainer.__init__ exactly (``*args, **kwargs`` raises KeyError: 'args').
        def __init__(
            self,
            plans: dict[str, Any],
            configuration: str,
            fold: int,
            dataset_json: dict[str, Any],
            device: Any = None,
        ) -> None:
            require_action(self.GATE)
            self.protocol_seed = _seed_from_env()
            _seed_everything(self.protocol_seed)
            super().__init__(
                plans,
                configuration,
                fold,
                dataset_json,
                torch.device("cuda") if device is None else device,
            )
            self.num_epochs = self.EPOCHS
            self.save_every = self.SAVE_EVERY

    class _ModalityDropoutMixin:
        """Arm B: the §10 modality-dropout policy after nnU-Net augmentation.

        VERIFY against the pinned nnU-Net version: the hook wraps the training
        dataloader output; the exact integration point differs across releases.
        """

        ARM = "B"
        protocol_seed: int

        def get_dataloaders(self) -> Any:
            train_loader, val_loader = super().get_dataloaders()  # type: ignore[misc]
            return _wrap_train_loader(
                train_loader, DropoutTransform(self.protocol_seed)
            ), val_loader

    class nnUNetTrainer_BratsUnc_250ep(_BratsUncBase):  # noqa: N801 - nnU-Net naming
        """Arm A: 250 epochs, protocol seed, no modality dropout."""

    class nnUNetTrainer_BratsUnc_250ep_ModalityDropout(  # noqa: N801
        _ModalityDropoutMixin, nnUNetTrainer_BratsUnc_250ep
    ):
        """Arm B: as arm A plus the §10 modality-dropout policy."""

    class nnUNetTrainer_BratsUnc_150ep(_BratsUncBase):  # noqa: N801
        """Arm A under SR1 / SR6 step 3: 150 epochs (all six runs switch together)."""

        EPOCHS = 150

    class nnUNetTrainer_BratsUnc_150ep_ModalityDropout(  # noqa: N801
        _ModalityDropoutMixin, nnUNetTrainer_BratsUnc_150ep
    ):
        """Arm B under SR1 / SR6 step 3: 150 epochs."""

    class nnUNetTrainer_BratsUnc_Pilot5ep(_BratsUncBase):  # noqa: N801
        """EXP-001 timing run (spec §1): 5 epochs, checkpoint every epoch (R1 resume test).

        Gated by ``run_exp001``; pilot models are discarded (D3-D5)."""

        EPOCHS = 5
        SAVE_EVERY = 1
        GATE = "run_exp001"

    class nnUNetTrainer_BratsUnc_Pilot5ep_ModalityDropout(  # noqa: N801
        _ModalityDropoutMixin, nnUNetTrainer_BratsUnc_Pilot5ep
    ):
        """EXP-001 arm-B timing run (the arm-B dropout policy, §10)."""


# star-import (the nnU-Net shim) exports only what exists in this environment
__all__ = [name for name in _EXPORTS if name in globals()]
