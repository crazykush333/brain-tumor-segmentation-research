"""EXP-001 execution on the current GPU platform (drives nnU-Net; see ``pilot_harness``).

The process runner is injectable (tests use a fake); the real one launches nnU-Net
commands, captures their output to log files and supports the R1 kill/resume.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from brats_uncertainty.compute.pilot_harness import (
    PilotRecord,
    epoch_stats,
    parse_epoch_times,
    parse_gpu_monitor,
    resume_check,
)
from brats_uncertainty.models.nnunet import (
    PILOT_TRAINERS,
    PROTOCOL_CONFIGURATION,
    RunSpec,
    plan_and_preprocess_command,
    run_namespace,
    train_command,
    train_environment,
)

PILOT_EXPERIMENT = "EXP-001"
RESUME_KILL_AFTER_EPOCHS = 3
# (run id, arm, seed) measured on any single GPU; P1 (P100) and P3 (2 GPUs) only on such hardware
TIMING_RUNS = (("P2", "B", 0), ("P4", "A", 0), ("P5_seed1", "B", 1), ("P5_seed2", "B", 2))


class ProcessRunner(Protocol):
    def run(self, cmd: Sequence[str], env: Mapping[str, str], log: Path) -> tuple[int, float]: ...

    def run_until(
        self, cmd: Sequence[str], env: Mapping[str, str], log: Path, n_epochs: int
    ) -> None: ...


class SubprocessRunner:  # pragma: no cover - launches real processes
    def run(self, cmd: Sequence[str], env: Mapping[str, str], log: Path) -> tuple[int, float]:
        log.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        with log.open("w", encoding="utf-8") as fh:
            code = subprocess.run(
                list(cmd),
                env={**os.environ, **env},
                stdout=fh,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
        return code, time.monotonic() - t0

    def run_until(
        self, cmd: Sequence[str], env: Mapping[str, str], log: Path, n_epochs: int
    ) -> None:
        """Start, wait until ``n_epochs`` epochs are logged (checkpoint written), then kill."""
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(
                list(cmd), env={**os.environ, **env}, stdout=fh, stderr=subprocess.STDOUT
            )
            try:
                while proc.poll() is None:
                    time.sleep(5)
                    if (
                        len(parse_epoch_times(log.read_text(encoding="utf-8", errors="ignore")))
                        >= n_epochs
                    ):
                        time.sleep(20)  # let the epoch checkpoint finish writing
                        proc.kill()
                        break
            finally:
                proc.wait()


class GpuMonitor:  # pragma: no cover - requires nvidia-smi
    def __init__(self, out: Path) -> None:
        self.out = out
        self.proc: subprocess.Popen[bytes] | None = None
        self.fh: Any = None

    def __enter__(self) -> GpuMonitor:
        smi = shutil.which("nvidia-smi")
        if smi:
            self.out.parent.mkdir(parents=True, exist_ok=True)
            self.fh = self.out.open("a", encoding="utf-8")
            self.proc = subprocess.Popen(
                [
                    smi,
                    "--query-gpu=utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits",
                    "-l",
                    "5",
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


def du_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0


def run_timing(
    runner: ProcessRunner,
    *,
    dataset_id: int,
    results_root: Path,
    logs: Path,
    base_env: Mapping[str, str],
    run_id: str,
    arm: str,
    seed: int,
    rec: PilotRecord,
) -> int:
    run = RunSpec(arm, seed)
    run_dir = run_namespace(results_root, PILOT_EXPERIMENT, run, label=run_id.replace("_", ""))
    env = {**base_env, **train_environment(run, run_dir)}
    log = logs / f"{run_id}.log"
    code, wall = runner.run(train_command(dataset_id, run, trainer=PILOT_TRAINERS[arm]), env, log)
    times = parse_epoch_times(log.read_text(encoding="utf-8", errors="ignore"))
    if code == 0 and len(times) >= 3:
        rec.timings[run_id] = epoch_stats(times)
        rec.wall_s[run_id] = wall
    return code


def run_resume_test(
    runner: ProcessRunner,
    *,
    dataset_id: int,
    results_root: Path,
    logs: Path,
    base_env: Mapping[str, str],
) -> dict[str, Any]:
    run = RunSpec("B", 0)
    run_dir = run_namespace(results_root, PILOT_EXPERIMENT, run, label="R1")
    env = {**base_env, **train_environment(run, run_dir)}
    first, second = logs / "R1_first.log", logs / "R1_resumed.log"
    runner.run_until(
        train_command(dataset_id, run, trainer=PILOT_TRAINERS["B"]),
        env,
        first,
        RESUME_KILL_AFTER_EPOCHS,
    )
    code, _ = runner.run(
        train_command(dataset_id, run, resume=True, trainer=PILOT_TRAINERS["B"]), env, second
    )
    final = list(run_dir.rglob("checkpoint_final.pth"))
    return resume_check(
        first.read_text(encoding="utf-8", errors="ignore"),
        second.read_text(encoding="utf-8", errors="ignore"),
        RESUME_KILL_AFTER_EPOCHS,
        completed=code == 0 and bool(final),
    )


def model_folder(run_dir: Path, dataset_dirname: str, trainer: str) -> Path:
    return run_dir / dataset_dirname / f"{trainer}__nnUNetPlans__{PROTOCOL_CONFIGURATION}"


def time_metric_code(shape: tuple[int, ...], repeats: int = 3) -> float:
    """Seconds per case-condition of the unit-metric code on SYNTHETIC volumes (spec §2.9)."""
    from brats_uncertainty.study.units import unit_rows

    rng = np.random.default_rng(0)
    probs = {r: [rng.random(shape, dtype=np.float32) for _ in range(3)] for r in ("WT", "TC", "ET")}
    gt = {r: rng.random(shape) > 0.97 for r in ("WT", "TC", "ET")}
    t0 = time.perf_counter()
    for _ in range(repeats):
        unit_rows(
            case_id="SYNTHETIC",
            group_id="SYNTHETIC",
            dataset="validation",
            arm="B",
            condition="Full",
            member_probs=probs,
            gt=gt,
        )
    return (time.perf_counter() - t0) / repeats


def gpu_monitor_summary(path: Path) -> dict[str, float] | None:
    if not path.is_file():
        return None
    try:
        return parse_gpu_monitor(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def plan_and_preprocess(
    runner: ProcessRunner, dataset_id: int, env: Mapping[str, str], log: Path
) -> tuple[int, float]:
    return runner.run(plan_and_preprocess_command(dataset_id), env, log)


__all__ = [
    "PILOT_EXPERIMENT",
    "TIMING_RUNS",
    "GpuMonitor",
    "SubprocessRunner",
    "du_bytes",
    "gpu_monitor_summary",
    "model_folder",
    "plan_and_preprocess",
    "run_resume_test",
    "run_timing",
    "time_metric_code",
]
