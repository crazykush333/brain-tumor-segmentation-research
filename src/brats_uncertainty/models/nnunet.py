"""nnU-Net v2 adapter: dataset.json, fixed split file and command construction.

This module builds files and command lines; it never launches training itself.
Launching training is guarded by research gates (see
``brats_uncertainty.evaluation.guards``) and is performed by scripts only after
the protocol gates B1-B12 and D1-D6 have been closed.

Design (protocol §8-§9):
- 3d_fullres, region-based (sigmoid WT/TC/ET); labels remapped per
  ``preprocessing.labels.BRATS2021_TO_NNUNET``.
- The raw dataset folder contains **train + validation only** so the dataset
  fingerprint and plans never see test data.
- A fixed ``splits_final.json`` with one fold (train split / validation split)
  replaces nnU-Net's random 5-fold CV. [Implementation choice; documented in
  docs/reproducibility/REPRODUCIBILITY.md.]
- 250 epochs, ``checkpoint_final``, seeds 0/1/2, arms A and B.
- Inference: sliding window step 0.5, mirroring OFF, threshold 0.5.

The exact nnU-Net version is pinned at M1/EXP-001; the trainer glue in
``nnunet_trainers.py`` must be verified against that pinned version.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.preprocessing.modalities import MODALITIES

PROTOCOL_EPOCHS = 250
PROTOCOL_SEEDS: tuple[int, ...] = (0, 1, 2)
PROTOCOL_CONFIGURATION = "3d_fullres"
PROTOCOL_CHECKPOINT = "checkpoint_final.pth"
ARMS: dict[str, str] = {
    "A": "nnUNetTrainer_BratsUnc_250ep",
    "B": "nnUNetTrainer_BratsUnc_250ep_ModalityDropout",
}
FIXED_FOLD = 0
# SR1 / SR6 step 3: "switch all six runs to 150 epochs" (protocol §20); never another value
REDUCED_EPOCHS = 150
ALLOWED_EPOCHS = (PROTOCOL_EPOCHS, REDUCED_EPOCHS)
ARMS_REDUCED: dict[str, str] = {
    "A": "nnUNetTrainer_BratsUnc_150ep",
    "B": "nnUNetTrainer_BratsUnc_150ep_ModalityDropout",
}
# EXP-001 timing runs (spec §1: 5 epochs; save_every 1 so the R1 resume test has a checkpoint)
PILOT_EPOCHS = 5
PILOT_TRAINERS: dict[str, str] = {
    "A": "nnUNetTrainer_BratsUnc_Pilot5ep",
    "B": "nnUNetTrainer_BratsUnc_Pilot5ep_ModalityDropout",
}


def trainer_for(arm: str, epochs: int = PROTOCOL_EPOCHS) -> str:
    """Trainer class for a protocol arm and an allowed epoch count (250, or 150 via SR1/SR6)."""
    if arm not in ARMS:
        raise ProtocolDeviationError(f"unknown arm {arm!r}; protocol arms are A and B")
    if epochs == PROTOCOL_EPOCHS:
        return ARMS[arm]
    if epochs == REDUCED_EPOCHS:
        return ARMS_REDUCED[arm]
    raise ProtocolDeviationError(f"{epochs} epochs: the protocol allows {ALLOWED_EPOCHS} only")


@dataclass(frozen=True)
class RunSpec:
    """One training run: an arm and a seed."""

    arm: str
    seed: int

    def __post_init__(self) -> None:
        if self.arm not in ARMS:
            raise ProtocolDeviationError(f"unknown arm {self.arm!r}; protocol arms are A and B")
        if self.seed not in PROTOCOL_SEEDS:
            raise ProtocolDeviationError(f"seed {self.seed} not in protocol seeds {PROTOCOL_SEEDS}")

    @property
    def trainer(self) -> str:
        return ARMS[self.arm]

    @property
    def run_id(self) -> str:
        return f"arm{self.arm}_seed{self.seed}"


def all_run_specs() -> tuple[RunSpec, ...]:
    """The six protocol runs: arms A/B x seeds 0/1/2."""
    return tuple(RunSpec(arm, seed) for arm in ARMS for seed in PROTOCOL_SEEDS)


def build_dataset_json(num_training: int, *, dataset_name: str = "BraTS2021Dev") -> dict[str, Any]:
    """nnU-Net v2 dataset.json for region-based training on remapped BraTS 2021 labels."""
    if num_training <= 0:
        raise ValueError("num_training must be positive")
    return {
        "name": dataset_name,
        "channel_names": {str(i): m for i, m in enumerate(MODALITIES)},
        "labels": {
            "background": 0,
            "whole_tumor": [1, 2, 3],
            "tumor_core": [2, 3],
            "enhancing_tumor": [3],
        },
        "regions_class_order": [1, 2, 3],
        "numTraining": num_training,
        "file_ending": ".nii.gz",
    }


def build_splits_final(
    train_ids: Sequence[str], val_ids: Sequence[str]
) -> list[dict[str, list[str]]]:
    """Single-fold splits_final.json reproducing the frozen train/validation split."""
    overlap = set(train_ids) & set(val_ids)
    if overlap:
        raise ProtocolDeviationError(f"train/validation overlap: {sorted(overlap)[:5]}")
    if not train_ids or not val_ids:
        raise ValueError("train and validation id lists must be non-empty")
    return [{"train": sorted(train_ids), "val": sorted(val_ids)}]


def plan_and_preprocess_command(dataset_id: int) -> list[str]:
    return [
        "nnUNetv2_plan_and_preprocess",
        "-d",
        str(dataset_id),
        "-c",
        PROTOCOL_CONFIGURATION,
        "--verify_dataset_integrity",
    ]


def train_command(
    dataset_id: int, run: RunSpec, *, resume: bool = False, trainer: str | None = None
) -> list[str]:
    """Training command. The seed is passed through the environment (see trainers).

    ``resume`` appends nnU-Net's ``--c`` (continue from the run's latest checkpoint);
    it is set only by the job runner after it has found that checkpoint.
    """
    cmd = [
        "nnUNetv2_train",
        str(dataset_id),
        PROTOCOL_CONFIGURATION,
        str(FIXED_FOLD),
        "-tr",
        trainer or run.trainer,
    ]
    return [*cmd, "--c"] if resume else cmd


MAIN_EXPERIMENT_ID = "MAIN"  # the six protocol training runs (§9-§10); the pilot is EXP-001
_EXPERIMENT_ID = re.compile(r"^[A-Z][A-Z0-9-]{1,31}$")
_RUN_LABEL = re.compile(r"^[A-Za-z0-9]{1,16}$")


def run_namespace(
    results_root: str | Path, experiment_id: str, run: RunSpec, label: str | None = None
) -> Path:
    """Collision-free per-run ``nnUNet_results`` root.

    Layout: ``<root>/<experiment>/[<label>_]arm_<a>_seed_<s>``.

    nnU-Net derives its output folder from dataset/trainer/plans/configuration/fold
    only, so the three seeds of one arm would overwrite each other in a shared
    ``nnUNet_results``; different experiments (EXP-001 pilot vs MAIN) likewise.
    Each run therefore gets its own root.
    """
    if not _EXPERIMENT_ID.match(experiment_id):
        raise ValueError(f"invalid experiment_id {experiment_id!r}")
    if label is not None and not _RUN_LABEL.match(label):
        raise ValueError(f"invalid run label {label!r}")
    leaf = f"arm_{run.arm.lower()}_seed_{run.seed}"
    return Path(results_root) / experiment_id / (f"{label}_{leaf}" if label else leaf)


def train_environment(run: RunSpec, run_dir: str | Path | None = None) -> dict[str, str]:
    """Environment variables consumed by the guarded trainers (and nnU-Net's results root)."""
    env = {"BRATS_UNC_SEED": str(run.seed), "BRATS_UNC_ARM": run.arm}
    if run_dir is not None:
        env["nnUNet_results"] = str(run_dir)
    return env


@dataclass(frozen=True)
class InferenceSettings:
    """Frozen inference settings (§9). Construction fails on any deviation."""

    tile_step_size: float = 0.5
    use_mirroring: bool = False
    threshold: float = 0.5
    checkpoint: str = PROTOCOL_CHECKPOINT
    n_members: int = 3

    def __post_init__(self) -> None:
        expected = {
            "tile_step_size": 0.5,
            "use_mirroring": False,
            "threshold": 0.5,
            "checkpoint": PROTOCOL_CHECKPOINT,
            "n_members": 3,
        }
        for key, value in expected.items():
            if getattr(self, key) != value:
                raise ProtocolDeviationError(
                    f"inference setting {key}={getattr(self, key)!r} "
                    f"deviates from protocol {value!r}"
                )
