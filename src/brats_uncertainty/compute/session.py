"""Hosted-session limits for long training runs: time budget, checkpoint carry-over.

A 250-epoch run needs about 19 GPU-hours on the measured platform (EXP-001), longer than
one hosted notebook session (12 h on Kaggle), and session storage is discarded when the
session ends. Therefore, in an environment with a session budget (``master_run.yaml``
``session``):

- a training process is stopped shortly after it writes a checkpoint, before the budget
  ends (``DeadlineRunner``); no new run starts when too little time is left;
- every run directory is mirrored into private session output (``persist_run``);
- the next session restores the run directories from the previous session's output,
  verifying each recorded checkpoint by SHA-256 (``restore_runs``), and resumes.

Nothing here changes what is trained: the run identity (protocol, configs, training code,
data, split) is checked by ``compute.jobs`` exactly as before, and a resumed run continues
from its own verified checkpoint only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.utils.hashing import sha256_file
from brats_uncertainty.utils.io import read_json

MANIFEST_NAME = "run_manifest.json"
PERSIST_SUBDIR = "nnunet_results"
_SKIP_DIRS = frozenset({"validation"})  # nnU-Net end-of-training predictions (not needed)


@dataclass(frozen=True)
class SessionSettings:
    budget_s: float | None  # seconds from runner start; None: no session limit
    persist_dir: Path | None
    restore_dir: Path | None
    restore_notebook: str | None  # hosted-notebook handle whose latest output is restored
    min_start_s: float
    stop_margin_s: float


def session_settings(
    cfg: Mapping[str, Any], environment: str, environ: Mapping[str, str]
) -> SessionSettings:
    """Settings for this environment; the BRATS_SESSION_* variables override the config."""
    sess = (cfg.get("session") or {}).get(environment) or {}
    budget_h = environ.get("BRATS_SESSION_BUDGET_H") or sess.get("budget_h")
    persist = environ.get("BRATS_PERSIST_DIR") or sess.get("persist_dir")
    restore = environ.get("BRATS_RESTORE_DIR") or sess.get("restore_dir")
    return SessionSettings(
        budget_s=float(budget_h) * 3600 if budget_h else None,
        persist_dir=Path(persist) if persist else None,
        restore_dir=Path(restore) if restore else None,
        restore_notebook=sess.get("restore_notebook"),
        min_start_s=float(sess.get("min_start_h", 1.0)) * 3600,
        stop_margin_s=float(sess.get("stop_margin_h", 0.5)) * 3600,
    )


def _copy_tree(src: Path, dest: Path) -> None:
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if _SKIP_DIRS & set(rel.parts):
            continue
        target = dest / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif p.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)


def persist_run(run_dir: Path, results_root: Path, persist_dir: Path) -> Path:
    """Mirror one run directory (manifest, checkpoints, logs) into session output."""
    dest = persist_dir / PERSIST_SUBDIR / run_dir.relative_to(results_root)
    if dest.exists():
        shutil.rmtree(dest)
    _copy_tree(run_dir, dest)
    return dest


def verify_run_dir(run_dir: Path) -> None:
    """The recorded checkpoint of a run must exist with its recorded SHA-256."""
    manifest = read_json(run_dir / MANIFEST_NAME)
    ckpt = manifest.get("checkpoint")
    if not ckpt:
        return
    path = run_dir / ckpt["path"]
    if not path.is_file() or sha256_file(path) != ckpt["sha256"]:
        raise ProvenanceError(
            f"{run_dir.name}: restored checkpoint {ckpt['path']} is missing or differs from "
            "its recorded SHA-256 (fail closed)"
        )


def restore_runs(source: Path, results_root: Path, persist_dir: Path | None) -> list[str]:
    """Restore every run directory found in ``source`` (a previous session's persist dir).

    Run directories already present locally are left alone. Each restored run is verified
    against its manifest's checkpoint hash, and the whole source is carried forward into
    this session's ``persist_dir`` so the next session sees every run.
    """
    base = source / PERSIST_SUBDIR
    restored: list[str] = []
    if not base.is_dir():
        return restored
    for manifest in sorted(base.rglob(MANIFEST_NAME)):
        run_src = manifest.parent
        rel = run_src.relative_to(base)
        run_dir = results_root / rel
        if not (run_dir / MANIFEST_NAME).is_file():
            _copy_tree(run_src, run_dir)
            verify_run_dir(run_dir)
            restored.append(rel.as_posix())
        if persist_dir is not None:
            carried = persist_dir / PERSIST_SUBDIR / rel
            if not (carried / MANIFEST_NAME).is_file():
                _copy_tree(run_src, carried)
    return restored


def find_restore_source(settings: SessionSettings) -> Path | None:
    """The previous session's persist directory: an explicit path, or the latest output of
    the configured hosted notebook (downloaded with kagglehub inside a Kaggle session)."""
    if settings.restore_dir is not None:
        return settings.restore_dir if settings.restore_dir.is_dir() else None
    if not settings.restore_notebook:
        return None
    try:  # pragma: no cover - requires a Kaggle session
        import kagglehub

        out = Path(kagglehub.notebook_output_download(settings.restore_notebook))
    except Exception as exc:  # pragma: no cover - reported, never silent
        print(f"session restore: notebook output unavailable ({type(exc).__name__}: {exc})")
        return None
    hits = [p for p in (out / "persist", out) if (p / PERSIST_SUBDIR).is_dir()]  # pragma: no cover
    return hits[0] if hits else None  # pragma: no cover


class DeadlineRunner:
    """Run a training command; stop it after a fresh checkpoint once the budget is near.

    From ``deadline - stop_margin_s`` on, the process is stopped as soon as a checkpoint
    file has been rewritten and left unchanged for ``settle_s`` (so the file is complete);
    at ``deadline`` it is stopped regardless. ``stopped_at_deadline`` records whether the
    stop came from here (a pause, resumed next session) rather than from the process.
    """

    def __init__(
        self,
        deadline: float,
        checkpoint_dir: Path,
        *,
        stop_margin_s: float,
        settle_s: float = 60.0,
        poll_s: float = 30.0,
        clock: Callable[[], float] = time.time,
        popen: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.deadline, self.checkpoint_dir = deadline, checkpoint_dir
        self.stop_margin_s, self.settle_s, self.poll_s = stop_margin_s, settle_s, poll_s
        self.clock, self.popen = clock, popen
        self.stopped_at_deadline = False

    def _latest_mtime(self) -> float:
        times = [p.stat().st_mtime for p in self.checkpoint_dir.rglob("checkpoint_latest.pth")]
        return max(times, default=0.0)

    def __call__(self, cmd: Sequence[str], env: Mapping[str, str]) -> int:
        proc = self.popen(list(cmd), env={**os.environ, **env})
        soft = self.deadline - self.stop_margin_s
        seen_at_soft: float | None = None
        while True:
            code = proc.poll()
            if code is not None:
                return int(code)
            now = self.clock()
            if now >= soft:
                mtime = self._latest_mtime()
                if seen_at_soft is None:
                    seen_at_soft = mtime
                fresh = mtime > seen_at_soft and now - mtime >= self.settle_s
                if fresh or now >= self.deadline:
                    self.stopped_at_deadline = True
                    proc.terminate()
                    try:
                        proc.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    return int(proc.returncode if proc.returncode is not None else -15)
            if self.poll_s:
                time.sleep(self.poll_s)
