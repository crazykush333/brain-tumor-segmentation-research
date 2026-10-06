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

Where the previous state comes from (``find_restore_source``, first match): an explicit
directory; a previous output attached to the notebook as an input (``/kaggle/input``); a
private Kaggle dataset holding the run state (``state_dataset``, written at every pause with
the owner's Kaggle API credentials, read from Kaggle Secrets at run time and never logged);
the notebook's own output (kagglehub; refused by Kaggle in non-interactive sessions).

Nothing here changes what is trained: the run identity (protocol, configs, training code,
data, split) is checked by ``compute.jobs`` exactly as before, and a resumed run continues
from its own verified checkpoint only.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
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
    state_dataset: str | None = None  # private dataset holding the run state (owner/slug)
    input_root: Path | None = None  # where attached inputs are mounted (/kaggle/input)


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
        state_dataset=sess.get("state_dataset"),
        input_root=Path(sess["input_root"]) if sess.get("input_root") else None,
    )


_CREDENTIAL_NAMES = ("KAGGLE_USERNAME", "KAGGLE_KEY")


def kaggle_credentials(environ: Mapping[str, str]) -> dict[str, str] | None:
    """The owner's Kaggle API credentials: environment, else Kaggle Secrets (never logged)."""
    found = {k: environ[k] for k in _CREDENTIAL_NAMES if environ.get(k)}
    if len(found) < 2:
        try:  # pragma: no cover - only inside a Kaggle session with the secrets attached
            from kaggle_secrets import UserSecretsClient

            client = UserSecretsClient()
            for k in _CREDENTIAL_NAMES:
                found.setdefault(k, client.get_secret(k))
        except Exception:
            return None
    return found if all(found.get(k) for k in _CREDENTIAL_NAMES) else None


def _kaggle_cli(args: Sequence[str], creds: Mapping[str, str], **kw: Any) -> tuple[int, str]:
    """Run the kaggle CLI with credentials in its environment only; output is scrubbed."""
    env = {**os.environ, **creds}
    res = subprocess.run(["kaggle", *args], env=env, capture_output=True, text=True, **kw)
    out = (res.stdout + res.stderr).replace(creds.get("KAGGLE_KEY", "\0"), "<redacted>")
    return res.returncode, out[-1500:]


def _find_persist(root: Path) -> Path | None:
    hits = sorted(p.parent for p in root.rglob(PERSIST_SUBDIR) if p.is_dir())
    return hits[0] if hits else None


def dataset_restore(handle: str, dest: Path, creds: Mapping[str, str]) -> Path | None:
    """Download the latest version of the private run-state dataset into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    code, out = _kaggle_cli(
        ["datasets", "download", "-d", handle, "-p", str(dest), "--unzip"], creds
    )
    LAST_RESTORE_NOTE["dataset_download"] = {"exit_code": code, "output_tail": out[-400:]}
    return _find_persist(dest) if code == 0 else None


def notebook_output_restore(handle: str, dest: Path, creds: Mapping[str, str]) -> Path | None:
    """Download the latest completed version's output of the notebook (Kaggle API)."""
    dest.mkdir(parents=True, exist_ok=True)
    code, out = _kaggle_cli(["kernels", "output", handle, "-p", str(dest)], creds)
    LAST_RESTORE_NOTE["notebook_output_download"] = {"exit_code": code, "output_tail": out[-400:]}
    return _find_persist(dest) if code == 0 else None


def dataset_persist(
    handle: str, persist_dir: Path, creds: Mapping[str, str], message: str
) -> dict[str, Any]:
    """Upload ``persist_dir`` as a new version of the private run-state dataset (created,
    private, on first use). Holds run directories only: manifests, checkpoints, logs."""
    import json

    meta = persist_dir / "dataset-metadata.json"
    meta.write_text(
        json.dumps(
            {
                "title": "brats-unc run state (private)",
                "id": handle,
                "licenses": [{"name": "other"}],
                "isPrivate": True,
            }
        ),
        encoding="utf-8",
    )
    code, out = _kaggle_cli(
        ["datasets", "version", "-p", str(persist_dir), "-m", message, "--dir-mode", "zip"], creds
    )
    action = "version"
    if code != 0:
        code, out = _kaggle_cli(
            ["datasets", "create", "-p", str(persist_dir), "--dir-mode", "zip"], creds
        )
        action = "create"
    return {"dataset": handle, "action": action, "exit_code": code, "output_tail": out[-400:]}


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


LAST_RESTORE_NOTE: dict[str, Any] = {}  # what the last find_restore_source call found


def find_restore_source(settings: SessionSettings) -> Path | None:
    """The previous session's persist directory: an explicit path, or the latest output of
    the configured hosted notebook (downloaded with kagglehub inside a Kaggle session)."""
    LAST_RESTORE_NOTE.clear()
    if settings.restore_dir is not None:
        LAST_RESTORE_NOTE["mode"] = "directory"
        return settings.restore_dir if settings.restore_dir.is_dir() else None
    if settings.input_root is not None and settings.input_root.is_dir():
        attached = _find_persist(settings.input_root)
        if attached is not None:
            LAST_RESTORE_NOTE["mode"] = "attached input"
            return attached
    if settings.state_dataset:
        creds = kaggle_credentials(os.environ)
        if creds is None:
            LAST_RESTORE_NOTE["dataset"] = "no Kaggle API credentials (Kaggle Secrets)"
        else:
            LAST_RESTORE_NOTE["mode"] = "private run-state dataset"
            dest = Path(os.environ.get("BRATS_WORK", "/tmp/brats")) / "restore_dataset"
            found = dataset_restore(settings.state_dataset, dest, creds)
            if found is not None:
                return found
            if settings.restore_notebook:  # the latest completed version's output, via the API
                found = notebook_output_restore(
                    settings.restore_notebook, dest.parent / "restore_notebook_output", creds
                )
                if found is not None:
                    LAST_RESTORE_NOTE["mode"] = "notebook output (Kaggle API)"
                    return found
    if not settings.restore_notebook:
        LAST_RESTORE_NOTE["mode"] = "none configured"
        return None
    LAST_RESTORE_NOTE["mode"] = "kagglehub notebook output"
    try:  # pragma: no cover - requires a Kaggle session
        import kagglehub

        out = Path(kagglehub.notebook_output_download(settings.restore_notebook))
    except Exception as exc:  # pragma: no cover - reported, never silent
        LAST_RESTORE_NOTE["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        print(f"session restore: notebook output unavailable ({LAST_RESTORE_NOTE['error']})")
        return None
    entries = sorted(p.name for p in out.iterdir())[:20] if out.is_dir() else []  # pragma: no cover
    LAST_RESTORE_NOTE.update(downloaded=True, top_level_entries=entries)  # pragma: no cover
    hits = [p for p in (out / "persist", out) if (p / PERSIST_SUBDIR).is_dir()]  # pragma: no cover
    LAST_RESTORE_NOTE["persist_dir_found"] = bool(hits)  # pragma: no cover
    return hits[0] if hits else None  # pragma: no cover


def popen_tee(cmd: Sequence[str], env: Mapping[str, str], log_path: Path) -> Any:
    """Start a process whose output goes both to this console and to ``log_path``."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = log_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        list(cmd),
        env={**env, "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            fh.write(line)
            fh.flush()
        fh.close()

    threading.Thread(target=pump, daemon=True).start()
    return proc


_UNSAFE_LINE = re.compile(r"https?://|token|passcode|secret|password|api[_-]?key|dice|aurc", re.I)


def log_tail(log_path: Path, n: int = 80) -> list[str]:
    """Last lines of a process log, without URL/credential-like or metric lines."""
    if not log_path.is_file():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [ln[:400] for ln in lines if not _UNSAFE_LINE.search(ln)][-n:]


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
        popen: Callable[..., Any] | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.deadline, self.checkpoint_dir = deadline, checkpoint_dir
        self.stop_margin_s, self.settle_s, self.poll_s = stop_margin_s, settle_s, poll_s
        self.clock, self.popen, self.log_path = clock, popen, log_path
        self.stopped_at_deadline = False
        # set by compute.jobs for a resumed run: returns False once the log shows the run
        # did not continue at the checkpoint epoch / learning rate (then it is stopped)
        self.resume_watch: Callable[[], bool] | None = None
        self.stopped_by_resume_check = False

    def _latest_mtime(self) -> float:
        times = [p.stat().st_mtime for p in self.checkpoint_dir.rglob("checkpoint_latest.pth")]
        return max(times, default=0.0)

    @staticmethod
    def _stop(proc: Any) -> int:
        proc.terminate()
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return int(proc.returncode if proc.returncode is not None else -15)

    def __call__(self, cmd: Sequence[str], env: Mapping[str, str]) -> int:
        full_env = {**os.environ, **env}
        if self.popen is not None:
            proc = self.popen(list(cmd), env=full_env)
        elif self.log_path is not None:
            proc = popen_tee(cmd, full_env, self.log_path)
        else:
            proc = subprocess.Popen(list(cmd), env=full_env)
        soft = self.deadline - self.stop_margin_s
        seen_at_soft: float | None = None
        while True:
            code = proc.poll()
            if code is not None:
                return int(code)
            if self.resume_watch is not None and not self.resume_watch():
                self.stopped_by_resume_check = True
                return self._stop(proc)
            now = self.clock()
            if now >= soft:
                mtime = self._latest_mtime()
                if seen_at_soft is None:
                    seen_at_soft = mtime
                fresh = mtime > seen_at_soft and now - mtime >= self.settle_s
                if fresh or now >= self.deadline:
                    self.stopped_at_deadline = True
                    return self._stop(proc)
            if self.poll_s:
                time.sleep(self.poll_s)
