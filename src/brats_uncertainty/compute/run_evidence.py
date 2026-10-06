"""Evidence that a protocol training run really trained, and where each session left it.

Collected from nnU-Net's own artefacts (training logs, checkpoint content) and the GPU,
committed with the run manifest (no metric values; only losses, learning rates, epochs,
hashes and utilisation). Used at the end of every attempt (pause, failure, completion) and
when a run is restored in a new session (the transfer record).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from brats_uncertainty.utils.hashing import sha256_file

_EPOCH = re.compile(r"^\S+ \S+: Epoch (\d+)\s*$", re.M)
_LR = re.compile(r"Current learning rate:\s*([0-9.eE+-]+)")
_TRAIN_LOSS = re.compile(r"train_loss\s+(-?[0-9.eE+-]+)")
_EPOCH_TIME = re.compile(r"Epoch time:\s*([0-9.]+)\s*s")
_DEVICE = re.compile(r"Using device:\s*(\S+)")


def training_logs(fold_dir: Path, since: float | None = None) -> list[Path]:
    logs = sorted(fold_dir.rglob("training_log_*.txt"), key=lambda p: p.stat().st_mtime)
    return [p for p in logs if since is None or p.stat().st_mtime >= since]


def training_log_summary(fold_dir: Path, since: float | None = None) -> dict[str, Any]:
    """What nnU-Net's logs show: epochs started and finished, losses, lr, device."""
    logs = training_logs(fold_dir, since)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in logs)
    epochs = [int(m) for m in _EPOCH.findall(text)]
    losses = [float(m) for m in _TRAIN_LOSS.findall(text)]
    lrs = [float(m) for m in _LR.findall(text)]
    times = [float(m) for m in _EPOCH_TIME.findall(text)]
    return {
        "logs": [{"file": p.name, "sha256": sha256_file(p)} for p in logs],
        "first_epoch_started": epochs[0] if epochs else None,
        "last_epoch_started": epochs[-1] if epochs else None,
        "epochs_started": len(epochs),
        "epochs_finished": len(times),
        "train_loss_lines": len(losses),
        "first_train_loss": losses[0] if losses else None,
        "last_train_loss": losses[-1] if losses else None,
        "last_logged_lr": lrs[-1] if lrs else None,
        "median_epoch_s": sorted(times)[len(times) // 2] if times else None,
        "devices": sorted(set(_DEVICE.findall(text))),
        "trained": bool(times),  # at least one epoch finished
    }


def lineage(
    run: str, session: int, started_at: str, checkpoint: dict[str, Any] | None, epoch: int | None
) -> str:
    """RUN -> SESSION -> CHECKPOINT -> SHA256 -> EPOCH -> NEXT EXPECTED EPOCH."""
    if not checkpoint:
        return f"{run} -> session {session} ({started_at}) -> no checkpoint"
    return (
        f"{run} -> session {session} ({started_at}) -> {checkpoint['path']} -> "
        f"sha256 {checkpoint['sha256']} -> epoch {epoch} -> next expected epoch {epoch}"
    )


class GpuSampler:  # pragma: no cover - requires nvidia-smi
    """nvidia-smi samples of one GPU (the one the run uses) every ``period_s`` seconds."""

    def __init__(self, out: Path, gpu_index: int = 0, period_s: int = 30) -> None:
        self.out, self.gpu_index, self.period_s = out, gpu_index, period_s
        self.proc: subprocess.Popen[bytes] | None = None
        self.fh: Any = None

    def __enter__(self) -> GpuSampler:
        smi = shutil.which("nvidia-smi")
        if smi:
            self.out.parent.mkdir(parents=True, exist_ok=True)
            self.fh = self.out.open("a", encoding="utf-8")
            self.proc = subprocess.Popen(
                [
                    smi,
                    "-i",
                    str(self.gpu_index),
                    "--query-gpu=name,utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits",
                    "-l",
                    str(self.period_s),
                ],
                stdout=self.fh,
                stderr=subprocess.DEVNULL,
            )
        return self

    def __exit__(self, *exc: Any) -> None:
        if self.proc is not None:
            self.proc.terminate()
            self.proc.wait()
        if self.fh is not None:
            self.fh.close()


def gpu_summary(csv_path: Path) -> dict[str, Any] | None:
    """Mean/peak utilisation and peak memory of the sampled GPU (None if not sampled)."""
    if not csv_path.is_file():
        return None
    names, util, mem = set(), [], []
    for line in csv_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) >= 3 and parts[1].replace(".", "", 1).isdigit():
            names.add(parts[0])
            util.append(float(parts[1]))
            mem.append(float(parts[2]))
    if not util:
        return None
    return {
        "gpu": sorted(names),
        "samples": len(util),
        "util_mean_pct": round(sum(util) / len(util), 1),
        "util_busy_fraction": round(sum(u > 0 for u in util) / len(util), 3),
        "mem_peak_gb": round(max(mem) / 1024.0, 2),
    }
