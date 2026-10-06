"""Resumable, provenance-checked training runs (configs/compute/remote_compute.yaml ``jobs``).

Namespace: every run owns ``<results_root>/<experiment_id>/[<label>_]arm_<a>_seed_<s>/``
(its nnU-Net ``nnUNet_results`` root), so no seed, arm or experiment can overwrite
another. ``run_manifest.json`` lives in that folder next to the checkpoints and records
the run identity (experiment, arm, seed, trainer, protocol version/hash, config hashes,
dataset manifest hash, split hash, dataset-conversion hash, data class) and every
attempt (start/end time, git commit, environment hash, hardware, exit code).

Statuses: PLANNED -> RUNNING -> COMPLETED | FAILED; any -> INVALIDATED.

- COMPLETED requires exit code 0 and ``checkpoint_final.pth``; it is never re-run.
- INVALIDATED runs are never resumed.
- Continuing an earlier attempt needs an explicit ``resume=True``. The checkpoint must be
  inside the run's own namespace, the manifest identity must equal the current one
  (otherwise FAIL CLOSED: the checkpoint belongs to another configuration), and if a
  checkpoint hash was recorded it must still match.
- Without a checkpoint, an earlier attempt is never silently restarted from epoch 0:
  ``restart_without_checkpoint=True`` must be explicit and is recorded.
- Real mode is gated (``train_main``: B1-B12, D1-D6) and needs a clean commit and a
  REAL_RESEARCH_DATA conversion record. ``synthetic_test_mode`` (Python API only, for
  tests) skips the gate but accepts only a SYNTHETIC_TEST_DATA conversion record and
  writes outside the repository; it can never train on study data.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brats_uncertainty.compute.probe import COMPUTE_CONFIG
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.models.nnunet import (
    PROTOCOL_EPOCHS,
    RunSpec,
    run_namespace,
    train_command,
    train_environment,
    trainer_for,
)
from brats_uncertainty.utils.git import git_commit, git_is_dirty
from brats_uncertainty.utils.hashing import sha256_file, sha256_json
from brats_uncertainty.utils.io import read_json, read_yaml
from brats_uncertainty.utils.paths import is_within

TRAINING_CONFIG = Path("configs/experiments/main_training.yaml")
TRAINING_CODE = (
    Path("src/brats_uncertainty/models/nnunet_trainers.py"),
    Path("src/brats_uncertainty/models/dropout.py"),
    Path("src/brats_uncertainty/models/nnunet.py"),
)
MANIFEST_NAME = "run_manifest.json"
RUN_STATUSES = ("PLANNED", "RUNNING", "COMPLETED", "FAILED", "INVALIDATED")
IDENTITY_KEYS = (
    "experiment_id",
    "arm",
    "seed",
    "trainer",
    "protocol_version",
    "protocol_sha256",
    "config_sha256",
    "dataset_manifest_sha256",
    "split_sha256",
    "dataset_conversion_sha256",
    "data_class",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    kind: str
    gated_action: str
    needs_gpu: bool
    experiment_id: str
    arm: str | None = None
    seed: int | None = None

    @property
    def run(self) -> RunSpec:
        if self.kind != "training" or self.arm is None or self.seed is None:
            raise ValueError(f"{self.job_id} is not a training job")
        return RunSpec(self.arm, self.seed)


def load_jobs(repo_root: Path) -> dict[str, JobSpec]:
    cfg = read_yaml(repo_root / COMPUTE_CONFIG)
    jobs = {
        jid: JobSpec(
            jid,
            str(j["kind"]),
            str(j["gated_action"]),
            bool(j["needs_gpu"]),
            str(j["experiment_id"]),
            j.get("arm"),
            None if j.get("seed") is None else int(j["seed"]),
        )
        for jid, j in cfg["jobs"].items()
    }
    runs = sorted((s.arm, s.seed) for s in jobs.values() if s.kind == "training")
    if runs != sorted((a, sd) for a in ("A", "B") for sd in (0, 1, 2)):
        raise ProvenanceError(f"training jobs must be exactly arms A/B x seeds 0/1/2, got {runs}")
    return jobs


def _now() -> str:
    return datetime.now(UTC).isoformat()


def read_manifest(run_dir: Path) -> dict[str, Any] | None:
    p = run_dir / MANIFEST_NAME
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    if manifest["status"] not in RUN_STATUSES:
        raise ProvenanceError(f"invalid run status {manifest['status']!r}")
    run_dir.mkdir(parents=True, exist_ok=True)
    tmp = run_dir / (MANIFEST_NAME + ".part")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(run_dir / MANIFEST_NAME)


def find_checkpoint(run_dir: Path, name: str) -> Path | None:
    """nnU-Net writes <run_dir>/<Dataset>/<trainer>__<plans>__<config>/fold_0/<name>."""
    hits = sorted(run_dir.glob(f"*/*/fold_0/{name}")) if run_dir.is_dir() else []
    if len(hits) > 1:
        raise ProvenanceError(f"ambiguous checkpoints in {run_dir.name}: {len(hits)}")
    return hits[0] if hits else None


@dataclass(frozen=True)
class Decision:
    action: str  # "start" | "resume" | "restart" | "refuse"
    reason: str
    checkpoint: Path | None = None


def decide(
    manifest: dict[str, Any] | None,
    run_dir: Path,
    identity: dict[str, Any],
    *,
    resume: bool,
    restart_without_checkpoint: bool = False,
) -> Decision:
    """Pure decision: start, resume (explicit, verified), explicit restart, or refuse."""
    latest = find_checkpoint(run_dir, "checkpoint_latest.pth")
    final = find_checkpoint(run_dir, "checkpoint_final.pth")
    if manifest is None:
        if latest or final:
            return Decision("refuse", "checkpoints without a run manifest (unknown provenance)")
        if resume:
            return Decision("refuse", "--resume given but this run has no earlier attempt")
        return Decision("start", "new run")
    diff = [k for k in IDENTITY_KEYS if manifest.get(k) != identity.get(k)]
    if diff:
        return Decision(
            "refuse",
            f"run identity differs ({diff}): the existing run/checkpoint belongs to another "
            "configuration (fail closed)",
        )
    status = manifest["status"]
    if status == "COMPLETED":
        return Decision("refuse", "run already COMPLETED; never re-run")
    if status == "INVALIDATED":
        return Decision("refuse", "run is INVALIDATED; use a new namespace")
    if status == "PLANNED" and not manifest["attempts"] and latest is None:
        if resume:
            return Decision("refuse", "--resume given but the run never started")
        return Decision("start", "planned run starts")
    if latest is None:
        if restart_without_checkpoint:
            return Decision("restart", "earlier attempt left no checkpoint; explicit restart")
        return Decision(
            "refuse",
            "earlier attempt left no checkpoint; restarting from epoch 0 needs an explicit "
            "restart_without_checkpoint (recorded) - never silent",
        )
    if not resume:
        return Decision("refuse", "earlier attempt with a checkpoint: pass --resume to continue")
    recorded: dict[str, Any] = manifest.get("checkpoint") or {}
    same_file = recorded.get("path") == latest.relative_to(run_dir).as_posix()
    if same_file and sha256_file(latest) != recorded.get("sha256"):
        return Decision("refuse", "checkpoint changed since it was recorded (fail closed)")
    return Decision("resume", "explicit resume from the run's own latest checkpoint", latest)


def environment_facts() -> dict[str, Any]:
    from brats_uncertainty.compute.probe import _gpu_facts, _ram_bytes, _version, detect_environment

    gpu = _gpu_facts()
    return {
        "environment": detect_environment(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "torch": _version("torch"),
        "nnunetv2": _version("nnunetv2"),
        "numpy": _version("numpy"),
        "cuda": gpu.get("cuda_version"),
        "gpu": gpu.get("name"),
        "vram_bytes": gpu.get("vram_bytes"),
        "ram_total_bytes": _ram_bytes()[0],
        "cpu_count": os.cpu_count(),
    }


def environment_hash(facts: dict[str, Any]) -> str:
    keys = ("os", "python", "torch", "nnunetv2", "numpy", "cuda", "gpu")
    return sha256_json({k: facts.get(k) for k in keys})


def run_identity(
    repo_root: Path,
    job: JobSpec,
    *,
    manifest_sha256: str,
    split_sha256: str,
    dataset_provenance: Path,
    synthetic: bool,
    epochs: int = PROTOCOL_EPOCHS,
) -> dict[str, Any]:
    for name, h in (("manifest_sha256", manifest_sha256), ("split_sha256", split_sha256)):
        if not _HEX64.match(h):
            raise ProvenanceError(f"{name} must be a SHA-256 hex digest")
    prov = read_json(dataset_provenance)
    want = "SYNTHETIC_TEST_DATA" if synthetic else "REAL_RESEARCH_DATA"
    if prov.get("kind") != "nnunet_raw_dataset_conversion" or prov.get("data_class") != want:
        raise ProvenanceError(f"dataset conversion record must be {want} in this mode")
    from brats_uncertainty.protocol import load_protocol

    protocol = load_protocol(repo_root)
    run = job.run
    return {
        "experiment_id": job.experiment_id,
        "arm": run.arm,
        "seed": run.seed,
        "trainer": trainer_for(run.arm, epochs),
        "protocol_version": protocol.version,
        "protocol_sha256": str(protocol.raw["protocol"]["sha256"]),
        "config_sha256": {
            p.as_posix(): sha256_file(repo_root / p)
            for p in (COMPUTE_CONFIG, TRAINING_CONFIG, *TRAINING_CODE)
        },
        "dataset_manifest_sha256": manifest_sha256,
        "split_sha256": split_sha256,
        "dataset_conversion_sha256": conversion_content_sha256(prov),
        "data_class": want,
    }


# Session-specific fields of the conversion record. The same converted dataset is rebuilt
# in every hosted session (ephemeral storage) at whatever commit the runner is on, so these
# fields must not enter a run's identity or a run could never resume in a later session.
_SESSION_FIELDS = ("git_commit",)


def conversion_content_sha256(provenance: Mapping[str, Any]) -> str:
    """SHA-256 of the conversion record (cases, files, config) without session fields."""
    body = {k: v for k, v in provenance.items() if k not in _SESSION_FIELDS}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def plan_run(run_dir: Path, identity: dict[str, Any]) -> dict[str, Any]:
    """Create the PLANNED manifest (or return the existing one if the identity matches)."""
    existing = read_manifest(run_dir)
    if existing is not None:
        diff = [k for k in IDENTITY_KEYS if existing.get(k) != identity.get(k)]
        if diff:
            raise ProvenanceError(f"{run_dir.name}: run identity differs ({diff}); fail closed")
        return existing
    manifest = {**identity, "status": "PLANNED", "attempts": [], "planned_at": _now()}
    _write_manifest(run_dir, manifest)
    return manifest


def invalidate_run(run_dir: Path, reason: str) -> dict[str, Any]:
    manifest = read_manifest(run_dir)
    if manifest is None:
        raise ProvenanceError(f"no run manifest in {run_dir.name}")
    if not reason.strip():
        raise ValueError("a reason is required")
    manifest.update(status="INVALIDATED", invalidated_at=_now(), invalidation_reason=reason)
    _write_manifest(run_dir, manifest)
    return manifest


def _artifacts(run_dir: Path) -> list[str]:
    keep = ("checkpoint_final.pth", "checkpoint_latest.pth", "progress.png", "debug.json")
    return [
        p.relative_to(run_dir).as_posix()
        for p in sorted(run_dir.rglob("*"))
        if p.is_file() and (p.name in keep or p.name.startswith("training_log"))
    ]


def run_training_job(
    repo_root: Path,
    job: JobSpec,
    *,
    dataset_id: int,
    results_root: Path,
    dataset_provenance: Path,
    manifest_sha256: str,
    split_sha256: str,
    resume: bool = False,
    restart_without_checkpoint: bool = False,
    synthetic_test_mode: bool = False,
    epochs: int = PROTOCOL_EPOCHS,
    runner: Callable[[Sequence[str], dict[str, str]], int] | None = None,
) -> dict[str, Any]:
    """Plan, start or (explicitly) resume one protocol training run; fully recorded."""
    if synthetic_test_mode:
        if is_within(results_root, repo_root):
            raise ProvenanceError("synthetic test mode writes outside the repository")
        commit = git_commit(repo_root)
    else:
        require_action(job.gated_action, repo_root)  # B1-B12 and D1-D6 closed
        commit = git_commit(repo_root)
        if commit is None or git_is_dirty(repo_root) is not False:
            raise ProvenanceError("training runs require a clean, committed checkout")
    identity = run_identity(
        repo_root,
        job,
        manifest_sha256=manifest_sha256,
        split_sha256=split_sha256,
        dataset_provenance=dataset_provenance,
        synthetic=synthetic_test_mode,
        epochs=epochs,
    )
    run = job.run
    run_dir = run_namespace(results_root, job.experiment_id, run)
    decision = decide(
        read_manifest(run_dir),
        run_dir,
        identity,
        resume=resume,
        restart_without_checkpoint=restart_without_checkpoint,
    )
    if decision.action == "refuse":
        raise ProvenanceError(f"{job.job_id}: {decision.reason}")
    manifest = plan_run(run_dir, identity)
    facts = environment_facts()
    attempt: dict[str, Any] = {
        "started_at": _now(),
        "action": decision.action,
        "reason": decision.reason,
        "resumed_from": (
            decision.checkpoint.relative_to(run_dir).as_posix() if decision.checkpoint else None
        ),
        "git_commit": commit,
        "environment_hash": environment_hash(facts),
        "hardware": facts,
    }
    cmd = train_command(
        dataset_id, run, resume=decision.action == "resume", trainer=identity["trainer"]
    )
    env = train_environment(run, run_dir)
    attempt["command"] = cmd
    manifest["attempts"].append(attempt)
    manifest.update(
        status="RUNNING",
        start_time=manifest.get("start_time") or attempt["started_at"],
        git_commit=commit,
        environment_hash=attempt["environment_hash"],
        hardware=facts,
    )
    _write_manifest(run_dir, manifest)

    def _default(c: Sequence[str], e: dict[str, str]) -> int:
        return subprocess.run(list(c), env={**os.environ, **e}, check=False).returncode

    def _finish(code: int | None) -> None:
        final = find_checkpoint(run_dir, "checkpoint_final.pth")
        latest = find_checkpoint(run_dir, "checkpoint_latest.pth")
        attempt.update(ended_at=_now(), exit_code=code)
        manifest["end_time"] = attempt["ended_at"]
        manifest["status"] = "COMPLETED" if code == 0 and final else "FAILED"
        ckpt = final or latest
        manifest["checkpoint"] = (
            {"path": ckpt.relative_to(run_dir).as_posix(), "sha256": sha256_file(ckpt)}
            if ckpt
            else None
        )
        manifest["checkpoint_path"] = manifest["checkpoint"]["path"] if ckpt else None
        manifest["artifact_paths"] = _artifacts(run_dir)
        _write_manifest(run_dir, manifest)

    try:
        code = (runner or _default)(cmd, env)
    except BaseException:
        _finish(None)
        raise
    _finish(code)
    return manifest
