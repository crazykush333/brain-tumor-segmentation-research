"""EXP-001 measurement harness (docs/experiments/EXP-001_COMPUTE_PILOT_SPEC.md §1-§4).

Runs on the current platform only what the platform can measure, and records every
spec quantity either as a measurement or as ``not measurable on this platform``
(never estimated):

- timing runs (5 epochs x 250 iterations, pilot trainers): arm B seed 0 (P2-type),
  arm A seed 0 (P4), arm B seeds 1, 2 (P5); P1 only on a P100, P3 only with >= 2 GPUs;
- epoch time = median (IQR) of epochs 2-5 parsed from the nnU-Net log (epoch 1 is
  warm-up); overhead_frac = (process wall time - sum of epoch times) / sum of epoch
  times [implementation of the spec's "validation/checkpoint time share"];
- GPU utilisation / memory from ``nvidia-smi -l 5`` during the runs (CPU-bound flag if
  mean utilisation < 70 %); peak memory = the monitor's peak;
- preprocessing wall time per case and on-disk sizes (raw, preprocessed, results);
- R1 resume check: kill after the epoch-3 checkpoint, resume with ``--c``; pass if
  training continues at epoch 3 and the logged learning rate equals the nnU-Net poly
  schedule value (1e-2 * (1 - e / 5) ** 0.9, rel. tol 1e-3) and the run completes;
- I1: per-case-condition 3-member ensemble inference time (no metric against labels:
  D4); metric time on synthetic volumes of identical shape.

No Dice, calibration, AURC or reliability metric is computed on pilot cases (D4), no
site-1 or BraTS-Africa case is touched (D3, D5), and pilot models are discarded.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

EPOCH_TIME = re.compile(r"Epoch time:\s*([0-9]+(?:\.[0-9]+)?)\s*s")
EPOCH_START = re.compile(r"\bEpoch\s+(\d+)\b(?!\s*time)")
LEARNING_RATE = re.compile(r"Current learning rate:\s*([0-9.eE+-]+)")
CPU_BOUND_UTIL = 70.0
PILOT_INITIAL_LR = 1e-2
PILOT_EPOCHS = 5
SPEC_QUANTITIES = (
    "p100_epoch_time_s",
    "single_gpu_epoch_time_s",
    "concurrent_2gpu_epoch_time_s",
    "gpu_util_mean",
    "peak_mem_gb",
    "preproc_s_per_case",
    "disk_gb",
    "resume_pass",
    "infer_s_per_case_condition",
    "quota_h_week",
    "session_limit_h",
    "disk_writable_gb",
    "seed_epoch_time_cv",
)
NOT_MEASURABLE = "not measurable on this platform"


def parse_epoch_times(log_text: str) -> list[float]:
    return [float(m.group(1)) for m in EPOCH_TIME.finditer(log_text)]


def parse_learning_rates(log_text: str) -> list[float]:
    return [float(m.group(1)) for m in LEARNING_RATE.finditer(log_text)]


def epoch_stats(times: Sequence[float]) -> dict[str, float]:
    """Median and IQR over epochs 2..5 (epoch 1 excluded as warm-up)."""
    t = list(times)[1:]
    if len(t) < 2:
        raise ValueError("need at least two post-warm-up epochs")
    q = np.quantile(t, [0.25, 0.75])
    return {
        "median_s": float(statistics.median(t)),
        "iqr_s": float(q[1] - q[0]),
        "n_epochs": len(t),
        "sum_s": float(sum(times)),  # all epochs, for the overhead share
    }


def poly_lr(epoch: int, num_epochs: int = PILOT_EPOCHS, initial: float = PILOT_INITIAL_LR) -> float:
    return initial * (1 - epoch / num_epochs) ** 0.9


def parse_gpu_monitor(text: str) -> dict[str, float]:
    """nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits."""
    util, mem = [], []
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 2 and row[0].strip().replace(".", "", 1).isdigit():
            util.append(float(row[0]))
            mem.append(float(row[1]))
    if not util:
        raise ValueError("no GPU monitor samples")
    return {
        "gpu_util_mean": float(np.mean(util)),
        "peak_mem_gb": max(mem) / 1024.0,
        "n_samples": len(util),
        "cpu_bound": float(np.mean(util)) < CPU_BOUND_UTIL,
    }


def resume_check(
    first_log: str, resumed_log: str, kill_epoch: int, completed: bool
) -> dict[str, Any]:
    """R1 pass criteria (spec §2.8)."""
    starts = [int(m.group(1)) for m in EPOCH_START.finditer(resumed_log)]
    lrs = parse_learning_rates(resumed_log)
    resumed_at = starts[0] if starts else None
    expected = poly_lr(kill_epoch)
    lr_ok = bool(lrs) and abs(lrs[0] - expected) <= 1e-3 * expected
    return {
        "killed_after_epoch": kill_epoch,
        "resumed_at_epoch": resumed_at,
        "logged_lr_at_resume": lrs[0] if lrs else None,
        "expected_lr_at_resume": expected,
        "completed": completed,
        "first_attempt_epochs_logged": len(parse_epoch_times(first_log)),
        "resume_pass": bool(resumed_at == kill_epoch and lr_ok and completed),
    }


@dataclass
class PilotRecord:
    platform: str
    gpu_names: list[str]
    timings: dict[str, dict[str, float]] = field(default_factory=dict)  # run id -> epoch stats
    wall_s: dict[str, float] = field(default_factory=dict)
    monitor: dict[str, float] | None = None
    preproc_s: float | None = None
    n_preproc_cases: int | None = None
    disk_bytes: dict[str, int] = field(default_factory=dict)
    resume: dict[str, Any] | None = None
    infer_s_per_case_condition: float | None = None
    metric_s_per_case_condition: float | None = None
    writable_bytes: int | None = None
    # float measured on a quota platform, or "not applicable: private VM ..." (no quota)
    quota_h_week: float | str | None = None
    session_limit_h: float | str | None = None
    peak_mem_fits_default_plan: bool | None = None


def assemble_measurements(rec: PilotRecord, planned_cases: int) -> dict[str, Any]:
    """The 13 spec quantities (measured or explicitly not measurable) + budget inputs."""
    single = rec.timings.get("P2")
    if single is None:
        raise ValueError("the single-GPU arm-B timing run (P2) is required")
    p5 = [rec.timings[k]["median_s"] for k in ("P2", "P5_seed1", "P5_seed2") if k in rec.timings]
    epochs_sum = rec.timings["P2"].get("sum_s")
    overhead = (
        (rec.wall_s["P2"] - epochs_sum) / epochs_sum if epochs_sum and "P2" in rec.wall_s else 0.0
    )
    gib = float(1 << 30)
    q: dict[str, Any] = {
        "p100_epoch_time_s": rec.timings["P1"]["median_s"]
        if "P1" in rec.timings
        else NOT_MEASURABLE,
        "single_gpu_epoch_time_s": single["median_s"],
        "concurrent_2gpu_epoch_time_s": rec.timings["P3"]["median_s"]
        if "P3" in rec.timings
        else NOT_MEASURABLE,
        "gpu_util_mean": rec.monitor["gpu_util_mean"] if rec.monitor else NOT_MEASURABLE,
        "peak_mem_gb": rec.monitor["peak_mem_gb"] if rec.monitor else NOT_MEASURABLE,
        "preproc_s_per_case": (rec.preproc_s / rec.n_preproc_cases)
        if rec.preproc_s and rec.n_preproc_cases
        else NOT_MEASURABLE,
        "disk_gb": {k: v / gib for k, v in rec.disk_bytes.items()} or NOT_MEASURABLE,
        "resume_pass": rec.resume["resume_pass"] if rec.resume else NOT_MEASURABLE,
        "infer_s_per_case_condition": rec.infer_s_per_case_condition
        if rec.infer_s_per_case_condition
        else NOT_MEASURABLE,
        "quota_h_week": rec.quota_h_week if rec.quota_h_week is not None else NOT_MEASURABLE,
        "session_limit_h": rec.session_limit_h
        if rec.session_limit_h is not None
        else NOT_MEASURABLE,
        "disk_writable_gb": rec.writable_bytes / gib
        if rec.writable_bytes is not None
        else NOT_MEASURABLE,
        "seed_epoch_time_cv": float(np.std(p5, ddof=1) / np.mean(p5))
        if len(p5) >= 2
        else NOT_MEASURABLE,
    }
    missing = [k for k in SPEC_QUANTITIES if q[k] == NOT_MEASURABLE]
    conc = None
    if "P3" in rec.timings:
        conc = 2 * single["median_s"] / rec.timings["P3"]["median_s"]
    inputs = {
        "median_epoch_s": single["median_s"],
        "overhead_frac": max(0.0, overhead),
        "infer_s_per_case_condition": rec.infer_s_per_case_condition or 0.0,
        "metric_s_per_case_condition_on_gpu": 0.0,  # metric code runs on the CPU (spec §3)
        "concurrency_gain": conc,
        "cpu_bound": bool(rec.monitor and rec.monitor.get("cpu_bound")),
        "quota_h_week": rec.quota_h_week if isinstance(rec.quota_h_week, (int, float)) else None,
        "session_limit_h": rec.session_limit_h
        if isinstance(rec.session_limit_h, (int, float))
        else None,
        "resume_pass": bool(rec.resume and rec.resume["resume_pass"]),
        "peak_mem_fits_default_plan": bool(rec.peak_mem_fits_default_plan),
        "platform": rec.platform,
    }
    return {
        "spec_quantities": q,
        "not_measurable_on_platform": missing,
        "metric_s_per_case_condition_cpu": rec.metric_s_per_case_condition,
        "planned_preprocessed_cases": planned_cases,
        "gpu_names": rec.gpu_names,
        "projection_inputs": inputs,
    }


def constraints_record(pilot_cases: Sequence[str], verified: Mapping[str, bool]) -> dict[str, Any]:
    """D3-D5 evidence: the selected pool (IDs) and what the harness guarantees."""
    return {
        "D3": bool(verified.get("D3")),
        "D4": True,  # the harness has no code path computing label-based metrics
        "D5": bool(verified.get("D5")),
        "pilot_cases": list(pilot_cases),
        "statement": "development cases (site != 1) only; no label-based metric; no site-1 or "
        "BraTS-Africa data; pilot models discarded",
    }
