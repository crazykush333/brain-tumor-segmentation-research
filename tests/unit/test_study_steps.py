"""Orchestrator executors for EXP-001, D6, validation/SR2, C5, C6, C1 and the tagged evaluations,
with fake Ops / process runner / ensemble sources (SYNTHETIC only; no GPU, no data)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from brats_uncertainty.compute import pilot_run
from brats_uncertainty.compute.pilot_harness import PilotRecord, poly_lr
from brats_uncertainty.data.crosswalk import CrosswalkRow
from brats_uncertainty.orchestration import study_steps as ss
from brats_uncertainty.orchestration.confirmations import CONFIRMATIONS_RELPATH, REQUIRED
from brats_uncertainty.orchestration.steps import StepBlocked, StepFailed, StepReview
from brats_uncertainty.preprocessing.modalities import C5_NAMES
from brats_uncertainty.study.units import read_unit_rows, units_filename, write_units
from tests.unit.test_orchestration import FakeOps, make_ctx
from tests.unit.test_study_pipeline import SyntheticSource, make_cases


def confirm_all(repo: Path) -> None:
    items = sorted({i for v in REQUIRED.values() for i in v})
    p = repo / CONFIRMATIONS_RELPATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "confirmed_by: SYNTHETIC\nitems:\n"
        + "".join(f"  {i}: {{confirmed_on: '2000-01-01', decision: CONFIRMED}}\n" for i in items),
        encoding="utf-8",
    )


def log_text(epochs: range, times: tuple[float, ...]) -> str:
    return "\n".join(
        f"Epoch {e}\nCurrent learning rate: {poly_lr(e):.5f}\nEpoch time: {t} s"
        for e, t in zip(epochs, times, strict=True)
    )


class FakeRunner:
    """Writes nnU-Net-like logs; records commands (no process is started)."""

    def __init__(self) -> None:
        self.cmds: list[list[str]] = []

    def run(self, cmd: Any, env: Any, log: Path) -> tuple[int, float]:
        self.cmds.append(list(cmd))
        log.parent.mkdir(parents=True, exist_ok=True)
        if "--c" in cmd:  # R1 resume: continues at epoch 3, then completes
            log.write_text(log_text(range(3, 5), (100.0, 101.0)), encoding="utf-8")
            Path(env["nnUNet_results"], "checkpoint_final.pth").parent.mkdir(
                parents=True, exist_ok=True
            )
            Path(env["nnUNet_results"], "checkpoint_final.pth").write_bytes(b"SYNTHETIC")
        elif cmd[0] == "nnUNetv2_plan_and_preprocess":
            log.write_text("SYNTHETIC preprocessing", encoding="utf-8")
            return 0, 80.0
        else:
            log.write_text(log_text(range(5), (130.0, 101.0, 99.0, 100.0, 102.0)), encoding="utf-8")
        return 0, 600.0

    def run_until(self, cmd: Any, env: Any, log: Path, n_epochs: int) -> None:
        self.cmds.append([*cmd, f"<killed after {n_epochs}>"])
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(log_text(range(n_epochs), (130.0, 101.0, 99.0)), encoding="utf-8")


# ============================================================ EXP-001
def test_pilot_timing_and_resume_with_fake_runner(tmp_path: Path) -> None:
    runner, rec = FakeRunner(), PilotRecord(platform="vm", gpu_names=["SYNTHETIC"])
    code = pilot_run.run_timing(
        runner,
        dataset_id=502,
        results_root=tmp_path / "r",
        logs=tmp_path / "l",
        base_env={},
        run_id="P2",
        arm="B",
        seed=0,
        rec=rec,
    )
    assert code == 0 and rec.timings["P2"]["median_s"] == 100.5 and rec.wall_s["P2"] == 600.0
    assert runner.cmds[0][-1] == "nnUNetTrainer_BratsUnc_Pilot5ep_ModalityDropout"
    res = pilot_run.run_resume_test(
        runner, dataset_id=502, results_root=tmp_path / "r", logs=tmp_path / "l", base_env={}
    )
    assert res["resume_pass"] and res["resumed_at_epoch"] == 3


def test_execute_pilot_end_to_end_with_fakes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops = FakeOps(gates={})
    ctx = make_ctx(
        tmp_path,
        ops,
        process_runner=FakeRunner(),
        ensemble_factory=lambda kind, arm, cases: SyntheticSource(2),
    )
    import shutil

    from tests.conftest import REPO_ROOT

    for rel in ("configs/experiments/EXP-001.yaml", "configs/dataset/brats2021.yaml"):
        (ctx.repo_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, ctx.repo_root / rel)
    rows = [CrosswalkRow(f"BraTS2021_{i:05d}", "18", "SYNTH", None) for i in range(60)]
    rows += [CrosswalkRow(f"BraTS2021_{i:05d}", "1", "SYNTH", None) for i in range(60, 80)]
    monkeypatch.setattr(ss, "crosswalk_rows", lambda c: rows)
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: None)
    monkeypatch.setattr(pilot_run, "GpuMonitor", lambda path: _NullCtx())
    monkeypatch.setattr(pilot_run, "time_metric_code", lambda shape: 0.5)
    monkeypatch.setattr(
        "brats_uncertainty.models.trainer_registration.register_trainers", lambda *a: None
    )
    monkeypatch.setattr(
        "brats_uncertainty.data.nnunet_dataset.write_nnunet_dataset",
        lambda *a, **k: Path(a[3]).mkdir(parents=True),
    )
    with pytest.raises(StepReview, match="22"):
        ss.execute_pilot(ctx)  # confirmations 22/23 are due first
    confirm_all(ctx.repo_root)
    out = ss.execute_pilot(ctx)
    exp = ctx.repo_root / "results/EXP-001"
    m = json.loads((exp / "measurements.json").read_text(encoding="utf-8"))
    assert out.status == "PASSED" and m["projection_inputs"]["median_epoch_s"] == 100.5
    assert "p100_epoch_time_s" in m["not_measurable_on_platform"]
    c = json.loads((exp / "constraints.json").read_text(encoding="utf-8"))
    assert c["D3"] and c["D4"] and c["D5"] and len(c["pilot_cases"]) == 40
    assert all(int(x.split("_")[1]) < 60 for x in c["pilot_cases"])  # no site-1 case (D3/D5)
    assert ss.execute_pilot(ctx).summary == "EXP-001 measurements recorded"  # never re-run


class CrashingRunner(FakeRunner):
    """Preprocessing succeeds; every training process crashes at start-up."""

    def run(self, cmd: Any, env: Any, log: Path) -> tuple[int, float]:
        if cmd[0] == "nnUNetv2_plan_and_preprocess":
            return super().run(cmd, env, log)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            "Traceback (most recent call last):\n"
            "  fetching https://example.invalid/x\n"
            "TypeError: SYNTHETIC trainer failure\n",
            encoding="utf-8",
        )
        return 1, 3.0


def test_execute_pilot_failure_commits_log_tails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import shutil

    from tests.conftest import REPO_ROOT

    ctx = make_ctx(tmp_path, FakeOps(gates={}), process_runner=CrashingRunner())
    for rel in ("configs/experiments/EXP-001.yaml", "configs/dataset/brats2021.yaml"):
        (ctx.repo_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / rel, ctx.repo_root / rel)
    rows = [CrosswalkRow(f"BraTS2021_{i:05d}", "18", "SYNTH", None) for i in range(60)]
    monkeypatch.setattr(ss, "crosswalk_rows", lambda c: rows)
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: None)
    monkeypatch.setattr(pilot_run, "GpuMonitor", lambda path: _NullCtx())
    monkeypatch.setattr(
        "brats_uncertainty.models.trainer_registration.register_trainers", lambda *a: None
    )
    monkeypatch.setattr(
        "brats_uncertainty.data.nnunet_dataset.write_nnunet_dataset",
        lambda *a, **k: Path(a[3]).mkdir(parents=True),
    )
    confirm_all(ctx.repo_root)
    with pytest.raises(StepBlocked, match=r"P2.*exit codes"):
        ss.execute_pilot(ctx)
    body = json.loads(
        (ctx.repo_root / "results/EXP-001" / ss.PILOT_FAILURE_LOG).read_text(encoding="utf-8")
    )
    p2 = body["failed_processes"]["P2"]
    assert p2["exit_code"] == 1 and p2["log_tail"][-1].startswith("TypeError")
    assert not any("https://" in ln for ln in p2["log_tail"])  # URL-like lines dropped
    assert set(body["failed_processes"]) == {"P2", "P4", "P5_seed1", "P5_seed2"}
    assert "SYNTHETIC trainer failure" in capsys.readouterr().out


class _NullCtx:
    def __enter__(self) -> _NullCtx:
        return self

    def __exit__(self, *a: Any) -> None:
        return None


# ============================================================ D6
def _measurements(ctx: Any, *, unmeasurable: list[str]) -> None:
    exp = ctx.repo_root / "results/EXP-001"
    exp.mkdir(parents=True, exist_ok=True)
    inputs = dict(
        median_epoch_s=180.0,
        overhead_frac=0.1,
        infer_s_per_case_condition=20.0,
        resume_pass=True,
        peak_mem_fits_default_plan=True,
    )
    (exp / "measurements.json").write_text(
        json.dumps({"projection_inputs": inputs, "not_measurable_on_platform": unmeasurable}),
        encoding="utf-8",
    )


def test_d6_owner_decision_for_unmeasurable_quantities(tmp_path: Path) -> None:
    ops = FakeOps(gates={"D6": "NOT_STARTED"})
    ctx = make_ctx(tmp_path, ops)
    _measurements(ctx, unmeasurable=["p100_epoch_time_s"])
    with pytest.raises(StepReview, match="not measurable"):
        ss.execute_d6(ctx)
    dec = ctx.repo_root / ss.D6_DECISION
    dec.parent.mkdir(parents=True, exist_ok=True)
    dec.write_text("decision: PROCEED\nepochs: 250\nreason: SYNTHETIC\n", encoding="utf-8")
    assert ss.execute_d6(ctx).status == "PASSED" and ops.gates["D6"] == "CLOSED"
    assert ss.planned_epochs(ctx) == 250
    dec.write_text("decision: PROCEED\nepochs: 200\n", encoding="utf-8")
    with pytest.raises(StepFailed):
        ss.planned_epochs(ctx)  # only 250 or 150


# ============================================================ validation / SR2 / C5
def _splits(ctx: Any, cases: list[str], groups: dict[str, str]) -> None:
    ctx.splits.mkdir(parents=True, exist_ok=True)
    with (ctx.splits / "split_all.csv").open("w", encoding="utf-8") as fh:
        fh.write("case_id,group_id,partition\n")
        fh.writelines(f"{c},{groups[c]},validation\n" for c in cases)
    with (ctx.splits / "patient_groups_dev.csv").open("w", encoding="utf-8") as fh:
        fh.write("case_id,group_id\n")
        fh.writelines(f"{c},{groups[c]}\n" for c in cases)


def test_validation_sr2_and_c5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ops = FakeOps(gates={"C5": "NOT_STARTED"})
    quality = {"A": 3.0, "B": 1.0}
    ctx = make_ctx(
        tmp_path,
        ops,
        ensemble_factory=lambda kind, arm, cases: SyntheticSource(
            1 if arm == "A" else 2, quality[arm]
        ),
    )
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: None)
    cases, groups = make_cases("SYNTH", 8)
    _splits(ctx, cases, groups)
    confirm_all(ctx.repo_root)
    out = ss.execute_validation(ctx)
    sr2 = json.loads((ctx.repo_root / "results/MAIN/sr2.json").read_text(encoding="utf-8"))
    assert out.status == "PASSED" and sr2["passed"]  # SR2 failure raises StepFailed instead
    units = ctx.repo_root / ss.UNITS_DIR
    assert (units / units_filename("validation", "B")).is_file()
    c5 = ss.execute_c5(ctx)
    frozen = json.loads((ctx.repo_root / ss.FROZEN_C5).read_text(encoding="utf-8"))
    assert c5.status == "PASSED" and ops.gates["C5"] == "CLOSED" and "0.80" in frozen["tau_q"]


def test_sr2_failure_stops_before_any_test_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_ctx(
        tmp_path, FakeOps(), ensemble_factory=lambda kind, arm, cases: SyntheticSource(1, 0.2)
    )
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: None)
    cases, groups = make_cases("SYNTH", 6)
    _splits(ctx, cases, groups)
    confirm_all(ctx.repo_root)
    with pytest.raises(StepFailed, match="SR2"):
        ss.execute_validation(ctx)


# ============================================================ C6 / C1
def test_c6_requires_pinned_hd95_evaluator(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path, FakeOps(gates={"C6": "NOT_STARTED"}))
    confirm_all(ctx.repo_root)
    cfg = ctx.repo_root / ss.EVAL_CONFIG
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("hd95: {evaluator: null}\n", encoding="utf-8")
    with pytest.raises(StepReview, match="HD95"):
        ss.execute_c6(ctx)


def test_c1_stops_without_an_approved_route(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path, FakeOps(gates={"C1": "NOT_STARTED"}))
    cfg = ctx.repo_root / ss.AFRICA_CONFIG
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("source: {route: null}\n", encoding="utf-8")
    with pytest.raises(StepReview, match="SR7"):
        ss.execute_c1(ctx)


# ============================================================ tagged evaluation / statistics
def test_evaluation_runs_tagged_cli_and_copies_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Ops(FakeOps):
        def run(self, cmd: Any, *, cwd: Any = None, env: Any = None) -> int:
            self.calls.append(("run", list(cmd)))
            if "evaluate-set" in cmd:
                out = Path(cmd[cmd.index("--out-dir") + 1])
                cases, groups = make_cases("SYNTH", 2)
                from brats_uncertainty.study.inference import evaluate_cases

                evaluate_cases(
                    cases=cases,
                    group_of=groups,
                    dataset="internal_test",
                    arm="B",
                    conditions=C5_NAMES,
                    source=SyntheticSource(2),
                    out=out / units_filename("internal_test", "B"),
                )
            return 0

    ops = Ops()
    ctx = make_ctx(tmp_path, ops)
    (ctx.work_dir / "eval-v1-worktree" / ".git").mkdir(parents=True)
    monkeypatch.setattr(ss, "_set_status", lambda *a, **k: None)
    res = ss.evaluation_executor("internal_test")(ctx)
    cmd = next(c[1] for c in ops.calls if c[0] == "run")
    assert "evaluate-set" in cmd and str(ctx.work_dir / "eval-v1-worktree") in cmd
    dest = ctx.repo_root / ss.UNITS_DIR / units_filename("internal_test", "B")
    assert res.status == "PASSED" and len(read_unit_rows(dest)) == 2 * 5 * 3
    assert ss.evaluation_executor("internal_test")(ctx).summary == "internal_test evaluated"


def test_tagged_command_failure_blocks(tmp_path: Path) -> None:
    class Ops(FakeOps):
        def run(self, cmd: Any, *, cwd: Any = None, env: Any = None) -> int:
            return 3

    ctx = make_ctx(tmp_path, Ops())
    (ctx.work_dir / "eval-v1-worktree" / ".git").mkdir(parents=True)
    with pytest.raises(StepBlocked, match="tagged command failed"):
        ss._tagged_cli(ctx, ["analyze-study"])


def test_write_units_refuses_mixed_sets(tmp_path: Path) -> None:
    from brats_uncertainty.errors import DataValidationError

    rows = [
        {"case_id": "a", "condition": "Full", "region": "ET", "dataset": "validation", "arm": "A"},
        {"case_id": "a", "condition": "Full", "region": "WT", "dataset": "validation", "arm": "B"},
    ]
    with pytest.raises(DataValidationError, match="one dataset and one arm"):
        write_units(tmp_path / "u.csv", rows)
