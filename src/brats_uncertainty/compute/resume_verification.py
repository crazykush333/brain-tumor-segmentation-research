"""Independent checks that a training run continues exactly where it stopped.

Used whenever a protocol run resumes, in particular across hosted sessions:

1. ``inspect_checkpoint`` - before the process starts: the checkpoint belongs to this
   run (trainer class, configuration, fold) and is internally consistent: epoch counter,
   optimizer state (SGD momentum buffers and the learning rate of the last trained
   epoch), mixed-precision scaler state and the logged per-epoch learning rates.
2. ``ResumeWatch`` - while the process runs: nnU-Net's own training log must show that
   the first epoch trained is the checkpoint's epoch, at the learning rate the frozen
   poly schedule gives for it (nnU-Net's scheduler is stateless: lr = f(epoch)).

A failed check stops the run (fail closed). Nothing here changes training.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ProvenanceError

INITIAL_LR = 1e-2  # nnU-Net v2 default (not overridden, protocol §9)
POLY_EXPONENT = 0.9
_EPOCH = re.compile(r"^\S+ \S+: Epoch (\d+)\s*$", re.M)
_LR = re.compile(r"Current learning rate:\s*([0-9.eE+-]+)")


def poly_lr(epoch: int, num_epochs: int) -> float:
    return INITIAL_LR * (1 - epoch / num_epochs) ** POLY_EXPONENT


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-4 * max(abs(b), 1e-12) + 6e-6  # nnU-Net logs 5 decimals


def _torch_load(path: Path) -> dict[str, Any]:  # pragma: no cover - requires torch
    import torch

    return dict(torch.load(path, map_location="cpu", weights_only=False))


def inspect_checkpoint(
    path: Path,
    *,
    trainer: str,
    num_epochs: int,
    configuration: str = "3d_fullres",
    fold: int = 0,
    load: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify a checkpoint before resuming from it; returns a weight-free summary."""
    ck = (load or _torch_load)(path)
    problems: list[str] = []
    epoch = ck.get("current_epoch")
    if not isinstance(epoch, int) or not 0 < epoch <= num_epochs:
        problems.append(f"current_epoch {epoch!r} outside 1..{num_epochs}")
        epoch = None
    if ck.get("trainer_name") != trainer:
        problems.append(f"trainer {ck.get('trainer_name')!r} != {trainer!r}")
    init = ck.get("init_args") or {}
    if init.get("configuration") != configuration or init.get("fold") != fold:
        problems.append(
            f"init_args configuration/fold {init.get('configuration')!r}/{init.get('fold')!r}"
        )
    opt = ck.get("optimizer_state") or {}
    groups = opt.get("param_groups") or []
    if not opt.get("state") or not groups:
        problems.append("optimizer state missing (no momentum buffers / param groups)")
    lrs = list((ck.get("logging") or {}).get("lrs") or [])
    ends = list((ck.get("logging") or {}).get("epoch_end_timestamps") or [])
    if epoch is not None:
        if len(lrs) != epoch or len(ends) != epoch:
            problems.append(f"logging has {len(lrs)} lrs / {len(ends)} epochs for epoch {epoch}")
        last = poly_lr(epoch - 1, num_epochs)
        if groups and not _close(float(groups[0].get("lr", -1)), last):
            problems.append(f"optimizer lr {groups[0].get('lr')} != schedule {last:.6g}")
        if lrs and not _close(float(lrs[-1]), last):
            problems.append(f"last logged lr {lrs[-1]} != schedule {last:.6g}")
    if ck.get("grad_scaler_state") is None:
        problems.append("mixed-precision grad scaler state missing")
    summary = {
        "checkpoint_epoch": epoch,
        "trainer": ck.get("trainer_name"),
        "optimizer_param_groups": len(groups),
        "optimizer_state_entries": len(opt.get("state") or {}),
        "grad_scaler_state": ck.get("grad_scaler_state") is not None,
        "logged_epochs": len(lrs),
        "expected_resume_lr": poly_lr(epoch, num_epochs) if epoch is not None else None,
        "problems": problems,
        "passed": not problems,
    }
    if problems:
        raise ProvenanceError(f"{path.name}: checkpoint fails resume verification: {problems}")
    return summary


class ResumeWatch:
    """Polls the run's nnU-Net training logs written after ``since`` until the first
    resumed epoch and its learning rate are logged; then fixes the verdict."""

    def __init__(self, fold_dir: Path, *, epoch: int, num_epochs: int, since: float) -> None:
        self.fold_dir, self.epoch, self.since = fold_dir, epoch, since
        self.expected_lr = poly_lr(epoch, num_epochs)
        self.result: dict[str, Any] | None = None

    def _new_logs(self) -> str:
        logs = sorted(
            (
                p
                for p in self.fold_dir.glob("training_log_*.txt")
                if p.stat().st_mtime >= self.since
            ),
            key=lambda p: p.stat().st_mtime,
        )
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in logs)

    def __call__(self) -> bool:
        """False once the resumed epoch is known to be wrong (the caller stops the run)."""
        if self.result is not None:
            return bool(self.result["passed"])
        text = self._new_logs()
        m = _EPOCH.search(text)
        if not m:
            return True
        lr = _LR.search(text, m.end())
        if not lr:
            return True
        first, logged = int(m.group(1)), float(lr.group(1))
        self.result = {
            "first_logged_epoch": first,
            "expected_epoch": self.epoch,
            "logged_lr": logged,
            "expected_lr": self.expected_lr,
            "passed": first == self.epoch and _close(logged, self.expected_lr),
        }
        return bool(self.result["passed"])
