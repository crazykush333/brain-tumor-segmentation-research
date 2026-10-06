"""Hosted-session time budget and checkpoint carry-over (SYNTHETIC files only)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from brats_uncertainty.compute import session as sess
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.utils.hashing import sha256_file


def _run(results: Path, name: str = "arm_a_seed_0", status: str = "FAILED") -> Path:
    run_dir = results / "MAIN" / name
    fold = run_dir / "Dataset501_X" / "Trainer__plans__3d_fullres" / "fold_0"
    fold.mkdir(parents=True)
    ckpt = fold / "checkpoint_latest.pth"
    ckpt.write_bytes(b"SYNTHETIC checkpoint " + name.encode())
    (fold / "validation").mkdir()
    (fold / "validation" / "pred.nii.gz").write_bytes(b"x")
    rel = ckpt.relative_to(run_dir).as_posix()
    manifest = {"status": status, "checkpoint": {"path": rel, "sha256": sha256_file(ckpt)}}
    (run_dir / sess.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def test_settings_from_config_and_environment() -> None:
    cfg = {"session": {"kaggle": {"budget_h": 11.0, "persist_dir": "/out/persist"}}}
    s = sess.session_settings(cfg, "kaggle", {})
    assert s.budget_s == 11.0 * 3600 and s.persist_dir == Path("/out/persist")
    assert s.min_start_s == 3600 and s.stop_margin_s == 1800
    s = sess.session_settings(cfg, "kaggle", {"BRATS_SESSION_BUDGET_H": "2"})
    assert s.budget_s == 7200
    assert sess.session_settings(cfg, "vm", {}).budget_s is None  # no limit elsewhere


def test_persist_and_restore_round_trip(tmp_path: Path) -> None:
    results_1 = tmp_path / "session1" / "nnunet_results"
    out_1 = tmp_path / "session1" / "persist"
    a0, b0 = _run(results_1), _run(results_1, "arm_b_seed_0", "COMPLETED")
    sess.persist_run(a0, results_1, out_1)
    sess.persist_run(b0, results_1, out_1)
    assert not list(out_1.rglob("validation"))  # predictions are not carried

    results_2, out_2 = tmp_path / "session2" / "nnunet_results", tmp_path / "session2" / "persist"
    restored = sess.restore_runs(out_1, results_2, out_2)
    assert restored == ["MAIN/arm_a_seed_0", "MAIN/arm_b_seed_0"]
    assert (results_2 / "MAIN/arm_a_seed_0" / sess.MANIFEST_NAME).is_file()
    # carried forward, so a third session still sees both runs
    assert sess.restore_runs(out_2, tmp_path / "s3", None) == restored
    assert sess.restore_runs(out_1, results_2, out_2) == []  # local runs are left alone


def test_restore_fails_closed_on_a_changed_checkpoint(tmp_path: Path) -> None:
    results_1, out_1 = tmp_path / "r1", tmp_path / "o1"
    sess.persist_run(_run(results_1), results_1, out_1)
    ckpt = next(out_1.rglob("checkpoint_latest.pth"))
    ckpt.write_bytes(b"tampered")
    with pytest.raises(ProvenanceError, match="SHA-256"):
        sess.restore_runs(out_1, tmp_path / "r2", None)


class _FakeProc:
    def __init__(self, ends_at: float | None, clock: list[float]) -> None:
        self.ends_at, self.clock, self.returncode = ends_at, clock, None
        self.terminated = False

    def poll(self) -> int | None:
        if self.ends_at is not None and self.clock[0] >= self.ends_at:
            self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self.terminated, self.returncode = True, -15

    def wait(self, timeout: float | None = None) -> int:
        return int(self.returncode or 0)


def _deadline_runner(
    tmp_path: Path, proc: _FakeProc, clock: list[float], on_tick: Any = None
) -> sess.DeadlineRunner:
    def tick() -> float:
        clock[0] += 60
        if on_tick:
            on_tick(clock[0])
        return clock[0]

    return sess.DeadlineRunner(
        deadline=10_000,
        checkpoint_dir=tmp_path,
        stop_margin_s=1800,
        settle_s=60,
        poll_s=0,
        clock=tick,
        popen=lambda cmd, env: proc,
    )


def test_deadline_runner_stops_after_a_fresh_checkpoint(tmp_path: Path) -> None:
    ckpt = tmp_path / "checkpoint_latest.pth"
    ckpt.write_bytes(b"epoch 5")
    os.utime(ckpt, (1000, 1000))
    clock = [0.0]

    def rewrite(now: float) -> None:  # nnU-Net saves again at t = 8,500 s (after soft)
        if now == 8_520:
            os.utime(ckpt, (8_500, 8_500))

    proc = _FakeProc(None, clock)
    runner = _deadline_runner(tmp_path, proc, clock, rewrite)
    assert runner(["nnUNetv2_train"], {}) == -15
    assert proc.terminated and runner.stopped_at_deadline
    assert 8_560 <= clock[0] < 10_000  # stopped once the new checkpoint settled


def test_deadline_runner_lets_a_finishing_process_finish(tmp_path: Path) -> None:
    clock = [0.0]
    proc = _FakeProc(3_000, clock)
    runner = _deadline_runner(tmp_path, proc, clock)
    assert runner(["nnUNetv2_train"], {}) == 0
    assert not proc.terminated and not runner.stopped_at_deadline


def test_deadline_runner_hard_stop_without_a_new_checkpoint(tmp_path: Path) -> None:
    clock = [0.0]
    proc = _FakeProc(None, clock)
    runner = _deadline_runner(tmp_path, proc, clock)
    runner(["nnUNetv2_train"], {})
    assert proc.terminated and runner.stopped_at_deadline and clock[0] >= 10_000


# ------------------------------------------------------------ training step integration
def _training_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **environ: str) -> Any:
    from brats_uncertainty.orchestration import steps as st
    from brats_uncertainty.orchestration import study_steps as ss
    from tests.unit.test_orchestration import make_ctx

    env = {"KAGGLE_KERNEL_RUN_TYPE": "Batch", "BRATS_PERSIST_DIR": str(tmp_path / "out"), **environ}
    ctx = make_ctx(tmp_path, environ=env)
    import shutil

    from tests.conftest import REPO_ROOT

    for rel in ("configs/compute/remote_compute.yaml", "configs/experiments/main_training.yaml"):
        (ctx.repo_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, ctx.repo_root / rel)
    for rel, body in (
        ("docs/data/records/B5_manifest.json", {"manifest_sha256": "a" * 64}),
        ("splits/split_hashes.json", {"split_all_csv_sha256": "b" * 64}),
    ):
        (ctx.repo_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (ctx.repo_root / rel).write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setattr(ss, "planned_epochs", lambda c: 250)
    monkeypatch.setattr(ss, "require_confirmations", lambda c, s: None)
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: None)
    monkeypatch.setattr(st, "_ensure_nnunet_dataset", lambda c: (501, tmp_path / "prov.json"))
    monkeypatch.setattr(
        "brats_uncertainty.models.trainer_registration.register_trainers", lambda *a: None
    )
    monkeypatch.setattr(sess, "find_restore_source", lambda settings: None)
    return ctx


def test_training_step_pauses_at_the_session_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brats_uncertainty.compute import jobs
    from brats_uncertainty.orchestration import steps as st

    ctx = _training_ctx(tmp_path, monkeypatch)

    class PausingRunner:
        def __init__(self, deadline: float, run_dir: Path, **kw: Any) -> None:
            self.stopped_at_deadline = True

    def fake_job(repo: Path, job: Any, *, results_root: Path, runner: Any, **kw: Any) -> dict:
        assert isinstance(runner, PausingRunner)  # a session budget applies on Kaggle
        run_dir = _run(results_root, "arm_a_seed_0")
        return json.loads((run_dir / sess.MANIFEST_NAME).read_text(encoding="utf-8"))

    monkeypatch.setattr(sess, "DeadlineRunner", PausingRunner)
    monkeypatch.setattr(jobs, "run_training_job", fake_job)
    with pytest.raises(st.StepBlocked, match="paused at this session's time budget"):
        st.training_executor("JOB-02")(ctx)
    assert list((tmp_path / "out").rglob(sess.MANIFEST_NAME))  # persisted to session output
    published = ctx.repo_root / "results/MAIN/runs/arm_a_seed_0/run_manifest.json"
    assert json.loads(published.read_text(encoding="utf-8"))["status"] == "FAILED"


def test_training_step_never_starts_late_or_restarts_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brats_uncertainty.compute import jobs
    from brats_uncertainty.orchestration import steps as st

    monkeypatch.setattr(jobs, "run_training_job", lambda *a, **k: pytest.fail("must not run"))
    late = _training_ctx(tmp_path / "late", monkeypatch, BRATS_SESSION_BUDGET_H="0.5")
    with pytest.raises(st.StepBlocked, match="too little of this session's time budget"):
        st.training_executor("JOB-02")(late)
    assert not (late.work_dir / "nnunet_results" / "MAIN").exists()  # no run was created

    lost = _training_ctx(tmp_path / "lost", monkeypatch)
    published = lost.repo_root / "results/MAIN/runs/arm_a_seed_0/run_manifest.json"
    published.parent.mkdir(parents=True)
    published.write_text(json.dumps({"status": "FAILED"}), encoding="utf-8")
    with pytest.raises(st.StepBlocked, match="was not restored in this session"):
        st.training_executor("JOB-02")(lost)


def test_training_step_refuses_a_stale_restored_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from brats_uncertainty.compute import jobs
    from brats_uncertainty.orchestration import steps as st

    monkeypatch.setattr(jobs, "run_training_job", lambda *a, **k: pytest.fail("must not run"))
    ctx = _training_ctx(tmp_path, monkeypatch)
    _run(ctx.work_dir / "nnunet_results")  # restored, but from an older session
    published = ctx.repo_root / "results/MAIN/runs/arm_a_seed_0/run_manifest.json"
    published.parent.mkdir(parents=True)
    newer = {"status": "FAILED", "checkpoint": {"path": "x", "sha256": "f" * 64}}
    published.write_text(json.dumps(newer), encoding="utf-8")
    with pytest.raises(st.StepBlocked, match="not the latest committed one"):
        st.training_executor("JOB-02")(ctx)
