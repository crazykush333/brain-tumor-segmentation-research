"""Resume verification: checkpoint content before, nnU-Net log while running (SYNTHETIC)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from brats_uncertainty.compute import resume_verification as rv
from brats_uncertainty.compute.jobs import load_jobs, run_training_job
from brats_uncertainty.errors import ProvenanceError
from tests.conftest import REPO_ROOT

TRAINER = "nnUNetTrainer_BratsUnc_250ep"


def _ckpt(epoch: int = 120, **over: Any) -> dict[str, Any]:
    lrs = [rv.poly_lr(e, 250) for e in range(epoch)]
    ck: dict[str, Any] = {
        "current_epoch": epoch,
        "trainer_name": TRAINER,
        "init_args": {"configuration": "3d_fullres", "fold": 0},
        "optimizer_state": {
            "state": {0: {"momentum_buffer": 1}},
            "param_groups": [{"lr": lrs[-1]}],
        },
        "grad_scaler_state": {"scale": 1024.0},
        "logging": {"lrs": lrs, "epoch_end_timestamps": list(range(epoch))},
    }
    ck.update(over)
    return ck


def test_checkpoint_inspection_accepts_a_consistent_checkpoint() -> None:
    s = rv.inspect_checkpoint(
        Path("c.pth"), trainer=TRAINER, num_epochs=250, load=lambda p: _ckpt()
    )
    assert s["passed"] and s["checkpoint_epoch"] == 120 and s["grad_scaler_state"]
    assert s["expected_resume_lr"] == pytest.approx(0.01 * (1 - 120 / 250) ** 0.9)


@pytest.mark.parametrize(
    ("over", "problem"),
    [
        ({"trainer_name": "nnUNetTrainer_BratsUnc_250ep_ModalityDropout"}, "trainer"),
        ({"current_epoch": 0}, "current_epoch"),
        ({"optimizer_state": {"state": {}, "param_groups": []}}, "optimizer state missing"),
        ({"optimizer_state": {"state": {0: 1}, "param_groups": [{"lr": 0.01}]}}, "optimizer lr"),
        ({"grad_scaler_state": None}, "grad scaler"),
        ({"init_args": {"configuration": "2d", "fold": 0}}, "init_args"),
    ],
)
def test_checkpoint_inspection_fails_closed(over: dict[str, Any], problem: str) -> None:
    with pytest.raises(ProvenanceError, match=problem):
        rv.inspect_checkpoint(
            Path("c.pth"), trainer=TRAINER, num_epochs=250, load=lambda p: _ckpt(**over)
        )


def _log(fold: Path, epoch: int, lr: float) -> None:
    fold.mkdir(parents=True, exist_ok=True)
    (fold / "training_log_2026_10_7_10_00_00.txt").write_text(
        "2026-10-07 10:00:01.000000: Using device: cuda\n"
        f"2026-10-07 10:00:02.000000: Epoch {epoch} \n"
        f"2026-10-07 10:00:02.100000: Current learning rate: {lr:.5f} \n",
        encoding="utf-8",
    )


def test_resume_watch_checks_epoch_and_learning_rate(tmp_path: Path) -> None:
    since = time.time() - 1
    good = rv.ResumeWatch(tmp_path / "a", epoch=120, num_epochs=250, since=since)
    assert good() is True and good.result is None  # nothing logged yet: keep waiting
    _log(tmp_path / "a", 120, rv.poly_lr(120, 250))
    assert good() is True and good.result and good.result["passed"]
    bad = rv.ResumeWatch(tmp_path / "b", epoch=120, num_epochs=250, since=since)
    _log(tmp_path / "b", 0, 0.01)  # restarted from scratch
    assert bad() is False and bad.result and not bad.result["passed"]


def _prov(tmp_path: Path) -> Path:
    p = tmp_path / "prov.json"
    p.write_text(
        json.dumps({"kind": "nnunet_raw_dataset_conversion", "data_class": "SYNTHETIC_TEST_DATA"}),
        encoding="utf-8",
    )
    return p


class WatchingRunner:
    """Fake training process: writes nnU-Net's log for the resumed attempt, then polls."""

    def __init__(self, logged_epoch: int, run_dir: Path) -> None:
        self.logged_epoch, self.run_dir = logged_epoch, run_dir
        self.resume_watch: Any = None
        self.calls = 0

    def __call__(self, cmd: list[str], env: dict[str, str]) -> int:
        self.calls += 1
        fold = next(self.run_dir.rglob("fold_0"))
        if "--c" not in cmd:  # first attempt: stops with a checkpoint at epoch 120
            (fold / "checkpoint_latest.pth").write_bytes(b"SYNTHETIC epoch 120")
            return 1
        _log(fold, self.logged_epoch, rv.poly_lr(self.logged_epoch, 250))
        if self.resume_watch is not None and not self.resume_watch():
            return -15
        (fold / "checkpoint_final.pth").write_bytes(b"SYNTHETIC final")
        return 0


@pytest.mark.parametrize("logged_epoch", [120, 0])
def test_resumed_run_is_verified_and_recorded(tmp_path: Path, logged_epoch: int) -> None:
    job = load_jobs(REPO_ROOT)["JOB-02"]
    results = tmp_path / "res"
    run_dir = results / "MAIN" / "arm_a_seed_0"
    (run_dir / "Dataset501_X" / "Trainer__plans__3d_fullres" / "fold_0").mkdir(parents=True)
    kw: dict[str, Any] = {
        "dataset_id": 501,
        "results_root": results,
        "dataset_provenance": _prov(tmp_path),
        "manifest_sha256": "a" * 64,
        "split_sha256": "b" * 64,
        "synthetic_test_mode": True,
        "checkpoint_inspector": lambda path, **k: rv.inspect_checkpoint(
            path, load=lambda p: _ckpt(), **k
        ),
    }
    runner = WatchingRunner(logged_epoch, run_dir)
    m = run_training_job(REPO_ROOT, job, runner=runner, **kw)  # type: ignore[arg-type]
    assert m["status"] == "FAILED" and m["attempts"][0]["gpu_hours"] >= 0
    assert m["epochs_planned"] == 250 and m["a5_amendment"]["sha256"]
    if logged_epoch == 120:
        m = run_training_job(REPO_ROOT, job, runner=runner, resume=True, **kw)  # type: ignore[arg-type]
        a = m["attempts"][1]
        assert m["status"] == "COMPLETED"
        assert a["resumed_from_checkpoint"]["epoch"] == 120
        assert a["resume_verification"]["checkpoint"]["passed"]
        assert a["resume_verification"]["log"]["passed"]
        assert a["checkpoint_out"]["path"].endswith("checkpoint_final.pth")
    else:
        with pytest.raises(ProvenanceError, match="did not continue at the checkpoint epoch"):
            run_training_job(REPO_ROOT, job, runner=runner, resume=True, **kw)  # type: ignore[arg-type]
        m = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert m["status"] == "FAILED" and m["attempts"][1]["resume_verification_failed"]
