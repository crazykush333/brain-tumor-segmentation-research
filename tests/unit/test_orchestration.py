"""Master orchestration: state journal, runner, gate pattern, budget rules, B2/B8 blockers,
review package, pilot selection, git safety, CLI. No data, no GPU, no network: every side
effect goes through a fake Ops (SYNTHETIC inputs only)."""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from brats_uncertainty.cli import main
from brats_uncertainty.data.crosswalk import CrosswalkRow
from brats_uncertainty.errors import ConfigError, ProtocolDeviationError, ProvenanceError
from brats_uncertainty.grouping.review import CSV_FIELDS
from brats_uncertainty.orchestration import gitops
from brats_uncertainty.orchestration.budget import (
    CAP_GPU_H,
    PilotMeasurements,
    Plan,
    decide,
    project,
)
from brats_uncertainty.orchestration.pilot import select_pilot_cases, verify_pilot_pool
from brats_uncertainty.orchestration.review_package import (
    build_review_package,
    protocol_section,
    review_slice,
)
from brats_uncertainty.orchestration.runner import plan, run, validate_order
from brats_uncertainty.orchestration.state import (
    BLOCKED,
    FAILED,
    LOCKED,
    PASSED,
    READY,
    REVIEW_REQUIRED,
    RUNNING,
    MasterState,
    Outcome,
    load_state,
    save_state,
)
from brats_uncertainty.orchestration.steps import (
    Context,
    Step,
    StepBlocked,
    build_steps,
    execute_d1,
    gate_step_executor,
    load_master_config,
    produce_b2,
    produce_b8,
)
from brats_uncertainty.orchestration.study_steps import execute_d6
from tests.conftest import REPO_ROOT

PROTOCOL_TEXT = (REPO_ROOT / "docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md").read_text("utf-8")


# ============================================================ fakes
@dataclass
class FakeReport:
    status: str = "READY"
    blockers: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(
        default_factory=lambda: {
            "environment": "vm",
            "gpu": {"name": "SYNTHETIC"},
            "protocol": {"verified": True},
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "blockers": self.blockers, "facts": self.facts}


@dataclass
class FakeOps:
    gates: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[Any, ...]] = field(default_factory=list)
    not_ready: dict[str, list[str]] = field(default_factory=dict)

    def gate_status(self, gid: str) -> str:
        return self.gates.get(gid, "NOT_STARTED")

    def transition(
        self, gid: str, new: str, *, evidence: str | None = None, on: str | None = None
    ) -> list[str]:
        self.calls.append(("transition", gid, new, evidence, on))
        self.gates[gid] = new
        return [f"{gid}.status -> {new}"]

    def milestone(self, message: str) -> str | None:
        self.calls.append(("milestone", message))
        return None

    def run(self, cmd: Any, *, cwd: Any = None, env: Any = None) -> int:
        self.calls.append(("run", list(cmd)))
        return 0

    def preflight(self, job: str | None) -> FakeReport:
        if job in self.not_ready:
            return FakeReport(status="NOT_READY", blockers=self.not_ready[job])
        return FakeReport()

    def fetch(self, url: str, dest: Path) -> None:
        self.calls.append(("fetch", url))
        dest.write_bytes(b"SYNTHETIC")


def make_ctx(tmp_path: Path, ops: FakeOps | None = None, **kw: Any) -> Context:
    repo = kw.pop("repo_root", tmp_path / "repo")
    repo.mkdir(parents=True, exist_ok=True)
    return Context(
        repo_root=repo,
        work_dir=tmp_path / "work",
        state_dir=tmp_path / "state",
        cfg=load_master_config(REPO_ROOT),
        environ=kw.pop("environ", {}),
        ops=ops or FakeOps(),
        today="2000-01-01",
        **kw,
    )


def ok(sid: str) -> Any:
    return lambda ctx: Outcome(PASSED, f"{sid} ok")


# ============================================================ state journal
def test_state_roundtrip_and_outcome_contract(tmp_path: Path) -> None:
    st = MasterState.new()
    st.start_session({"host": "SYNTHETIC"})
    st.step("B2").status = BLOCKED
    save_state(tmp_path, st)
    back = load_state(tmp_path)
    assert back.steps["B2"].status == BLOCKED and len(back.sessions) == 1
    assert not (tmp_path / "master_state.json.part").exists()
    with pytest.raises(ValueError, match="exact action"):
        Outcome(BLOCKED, "no action given")
    with pytest.raises(ValueError, match="invalid step status"):
        Outcome("DONE", "x")


# ============================================================ runner
def test_runner_locks_dependants_and_continues_independent_steps(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    blocked = lambda c: Outcome(BLOCKED, "no delivery", "deliver it")  # noqa: E731
    steps = [
        Step("A", "a", "x", (), ok("A")),
        Step("B", "b", "x", ("A",), blocked),
        Step("C", "c", "x", ("B",), ok("C")),
        Step("D", "d", "x", ("A",), ok("D")),
    ]
    rep = run(ctx, steps)
    assert rep.statuses == {"A": PASSED, "B": BLOCKED, "C": LOCKED, "D": PASSED}
    assert [s["step"] for s in rep.stops] == ["B"]
    assert rep.stops[0]["action"] == "deliver it"
    assert "STOP BLOCKED at B" in rep.describe()


def test_failed_steps_never_rerun_without_owner_retry(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    count = {"n": 0}

    def flaky(c: Context) -> Outcome:
        count["n"] += 1
        raise ProtocolDeviationError("SYNTHETIC assertion")

    steps = [Step("X", "x", "x", (), flaky)]
    assert run(ctx, steps).statuses["X"] == FAILED
    assert run(ctx, steps).statuses["X"] == FAILED
    assert count["n"] == 1  # not re-run silently
    run(ctx, steps, retry=["X"])
    assert count["n"] == 2


def test_crash_leaves_running_and_resumes(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)

    def crash(c: Context) -> Outcome:
        raise KeyboardInterrupt  # session killed mid-step

    with pytest.raises(KeyboardInterrupt):
        run(ctx, [Step("T", "t", "x", (), crash)])
    assert load_state(ctx.state_dir).steps["T"].status == RUNNING
    rep = run(ctx, [Step("T", "t", "x", (), ok("T"))])
    assert rep.statuses["T"] == PASSED
    st = load_state(ctx.state_dir)
    assert st.steps["T"].attempts == 2 and st.sessions[-1]["resumed"] is True


def test_closed_gate_is_passed_without_execution_and_compute_blocks(tmp_path: Path) -> None:
    ops = FakeOps(gates={"G": "CLOSED"}, not_ready={"JOB-X": ["no CUDA GPU available"]})
    ctx = make_ctx(tmp_path, ops)

    def never(c: Context) -> Outcome:
        raise AssertionError("must not run")

    rep = run(
        ctx,
        [Step("G", "g", "x", (), never, gate="G"), Step("H", "h", "x", ("G",), never, job="JOB-X")],
    )
    assert rep.statuses == {"G": PASSED, "H": BLOCKED}
    assert "no CUDA GPU" in rep.stops[0]["blocker"]


def test_unexpected_exception_is_reported_as_possible_bug(tmp_path: Path) -> None:
    def bug(c: Context) -> Outcome:
        return {}["missing"]  # type: ignore[no-any-return]

    rep = run(make_ctx(tmp_path), [Step("Z", "z", "x", (), bug)])
    assert rep.statuses["Z"] == FAILED and "possible bug" in rep.stops[0]["blocker"]


def test_registry_order_and_plan_on_real_status(tmp_path: Path) -> None:
    steps = build_steps()
    validate_order(steps)
    ids = [s.id for s in steps]
    for need in ("B2", "B8", "B12", "D6", "TRAIN-A0", "TRAIN-B2", "C5", "C6", "FINAL_AUDIT"):
        assert need in ids
    assert ids.index("B12") < ids.index("TRAIN-A0") and ids.index("D6") < ids.index("TRAIN-A0")
    with pytest.raises(ValueError, match="must precede"):
        validate_order([Step("B", "b", "x", ("A",), ok("B")), Step("A", "a", "x", (), ok("A"))])
    from brats_uncertainty.orchestration.steps import RealOps

    cfg = load_master_config(REPO_ROOT)
    real = RealOps(
        REPO_ROOT, cfg, commit=False, push=False, environ={}, work_dir=tmp_path, offline=True
    )
    ctx = make_ctx(tmp_path, repo_root=REPO_ROOT)
    ctx.ops = real
    statuses = plan(ctx, steps, MasterState.new())
    assert statuses["B2"] == LOCKED  # ENV has not run in an empty journal
    assert statuses["B3"] == LOCKED and statuses["TRAIN-A0"] == LOCKED
    assert statuses["ENV"] == READY and statuses["D1"] in (READY, PASSED)


# ============================================================ gate pattern
def test_gate_step_runs_records_and_passes_in_order(tmp_path: Path) -> None:
    ops = FakeOps(gates={"B9": "AUTHORIZED"})
    ctx = make_ctx(tmp_path, ops)
    rec = ctx.repo_root / "rec.json"

    def produce(c: Context) -> list[Path]:
        rec.write_text("{}", encoding="utf-8")
        return [rec]

    out = gate_step_executor("B9", produce, describe="groups")(ctx)
    assert out.status == PASSED and out.evidence == ["rec.json"]
    kinds = [(c[0], c[2] if c[0] == "transition" else None) for c in ops.calls]
    assert kinds == [
        ("transition", "RUNNING"),
        ("milestone", None),
        ("milestone", None),
        ("transition", "PASSED"),
        ("milestone", None),
    ]
    assert ops.calls[3][3:] == ("rec.json", "2000-01-01")


def test_gate_step_resume_blocked_and_failed_gate(tmp_path: Path) -> None:
    ops = FakeOps(gates={"B5": "RUNNING", "B6": "FAILED"})
    ctx = make_ctx(tmp_path, ops)

    def stuck(c: Context) -> list[Path]:
        raise StepBlocked("SYNTHETIC input missing", "provide it")

    step = Step("B5", "m", "B", (), gate_step_executor("B5", stuck, describe="m"), gate="B5")
    rep = run(ctx, [step])
    assert rep.statuses["B5"] == BLOCKED and ops.gates["B5"] == "RUNNING"  # never auto-failed
    assert not [c for c in ops.calls if c[0] == "transition"]
    out = gate_step_executor("B6", stuck, describe="c")
    from brats_uncertainty.orchestration.steps import run_guarded

    res = run_guarded(ctx, Step("B6", "c", "B", (), out, gate="B6"))
    assert res.status == REVIEW_REQUIRED and "gate-transition" in str(res.action_needed)


# ============================================================ B2: never guessed
def test_b2_blocks_without_delivery_or_verified_command(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    ctx.cfg["acquisition"]["receive_command"] = None  # route A not configured
    with pytest.raises(StepBlocked) as e:
        produce_b2(ctx)
    assert "ascli faspex5 -h" in e.value.action and "BRATS_OFFICIAL_DELIVERY" in e.value.action
    ctx.cfg["acquisition"]["receive_command"] = "SYNTHETIC receive"
    ctx.cfg["acquisition"]["receive_command_evidence"] = "docs/missing_help.txt"
    with pytest.raises(StepBlocked, match="evidence"):
        produce_b2(ctx)
    delivery = tmp_path / "delivery"
    delivery.mkdir()
    ctx2 = make_ctx(tmp_path, environ={"BRATS_OFFICIAL_DELIVERY": str(delivery)})
    with pytest.raises(StepBlocked, match="lacks"):
        produce_b2(ctx2)
    assert not FakeOps().calls  # nothing was run or fetched


def test_recorded_receive_command_is_evidenced_and_keeps_secrets_out(repo_root: Path) -> None:
    """The committed route-A command is backed by committed client evidence, receives
    exactly the training set and the .sums file, and embeds no package link/passcode."""
    import shlex

    acq = load_master_config(repo_root)["acquisition"]
    cmd = str(acq["receive_command"])
    assert (repo_root / acq["receive_command_evidence"]).is_file()
    assert float(acq["selected_gib"]) > 0
    parts = shlex.split(cmd)
    assert parts[:2] == ["sh", "-c"] and len(parts) == 3
    assert "faspex.cancerimagingarchive.net" not in cmd and "context=" not in cmd
    assert '"$BRATS_TCIA_PACKAGE_URL"' in parts[2]
    assert '/RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet"' in parts[2]
    assert '/RSNA-ASNR-MICCAI-BraTS-2021.sums"' in parts[2]
    assert "_dcm" not in parts[2] and "ValidationSet" not in parts[2]


# ============================================================ B8: human review only
def test_b8_requires_human_decisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_ctx(tmp_path)
    b7 = ctx.records / "B7"
    b7.mkdir(parents=True)
    (b7 / "flagged_pairs.csv").write_text(
        "case_a,case_b\nBraTS2021_00001,BraTS2021_00002\n", encoding="utf-8"
    )
    import brats_uncertainty.protocol as protocol_mod
    from brats_uncertainty.orchestration import steps as steps_mod

    real_load = protocol_mod.load_protocol
    monkeypatch.setattr(steps_mod, "_write_b8_package", lambda c, f, p: {"n_pairs": len(f)})
    monkeypatch.setattr(protocol_mod, "load_protocol", lambda root: real_load(REPO_ROOT))
    from brats_uncertainty.orchestration.steps import StepReview

    with pytest.raises(StepReview) as e:
        produce_b8(ctx)
    assert "Ayush Kushwaha" in e.value.action and "SAME_PATIENT" in e.value.action
    assert not (ctx.records / "B8_review_record.json").exists()
    # decisions by the protocol reviewer -> record written (IDs only)
    reviews = ctx.repo_root / ctx.cfg["review"]["decisions_file"]
    reviews.parent.mkdir(parents=True, exist_ok=True)
    with reviews.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CSV_FIELDS)
        w.writerow(
            [
                "BraTS2021_00001",
                "BraTS2021_00002",
                "DIFFERENT_PATIENT",
                "Ayush Kushwaha",
                "primary",
                "2000-01-01T00:00:00Z",
                "SYNTHETIC reason",
            ]
        )
    out = produce_b8(ctx)
    body = json.loads(out[0].read_text(encoding="utf-8"))
    assert body["decisions"] == {"BraTS2021_00001|BraTS2021_00002": "DIFFERENT_PATIENT"}


# ============================================================ D gates
def test_d1_closes_only_with_owner_record(tmp_path: Path) -> None:
    ops = FakeOps(gates={"D1": "NOT_STARTED"})
    ctx = make_ctx(tmp_path, ops)
    from brats_uncertainty.orchestration.steps import D1_EVIDENCE, StepReview

    with pytest.raises(StepReview):
        execute_d1(ctx)
    ev = ctx.repo_root / D1_EVIDENCE
    ev.parent.mkdir(parents=True)
    ev.write_text("SYNTHETIC owner record\n", encoding="utf-8")
    out = execute_d1(ctx)
    assert out.status == PASSED and ops.gates["D1"] == "CLOSED"
    assert ("transition", "D1", "CLOSED", D1_EVIDENCE, "2000-01-01") in ops.calls


def _measurements(**over: Any) -> dict[str, Any]:
    base = dict(
        median_epoch_s=180.0,
        overhead_frac=0.1,
        infer_s_per_case_condition=20.0,
        resume_pass=True,
        peak_mem_fits_default_plan=True,
    )
    base.update(over)
    return base


def test_d6_applies_budget_and_requires_owner_when_infeasible(tmp_path: Path) -> None:
    ops = FakeOps(gates={"D6": "NOT_STARTED"})
    ctx = make_ctx(tmp_path, ops)
    exp = ctx.repo_root / ctx.cfg["paths"]["exp001_dir"]
    exp.mkdir(parents=True)
    (exp / "measurements.json").write_text(
        json.dumps({"projection_inputs": _measurements()}), encoding="utf-8"
    )
    assert execute_d6(ctx).status == PASSED and ops.gates["D6"] == "CLOSED"
    ctx2 = make_ctx(tmp_path / "b", FakeOps(gates={"D6": "NOT_STARTED"}))
    exp2 = ctx2.repo_root / ctx2.cfg["paths"]["exp001_dir"]
    exp2.mkdir(parents=True)
    (exp2 / "measurements.json").write_text(
        json.dumps({"projection_inputs": _measurements(median_epoch_s=2000.0)}), encoding="utf-8"
    )
    from brats_uncertainty.orchestration.steps import StepReview

    with pytest.raises(StepReview):
        execute_d6(ctx2)


# ============================================================ budget (SR1/SR6/SR8)
def test_budget_baseline_formula() -> None:
    m = PilotMeasurements(**_measurements())
    p = project(m, Plan())
    assert p.t_train_run == pytest.approx(180 * 250 / 3600 * 1.1)
    assert p.t_train_total == pytest.approx(6 * p.t_train_run)
    assert p.t_infer_prim == pytest.approx(20 * 828 * 5 * 6 / 3 / 3600)
    assert p.t_infer_c15 == pytest.approx(20 * 148 * 10 * 3 / 3 / 3600)
    d = decide(m)
    assert d.status == "FEASIBLE" and not d.sr1_applied and not d.sr6_steps_applied


def test_sr1_switches_to_150_epochs_then_owner() -> None:
    d = decide(PilotMeasurements(**_measurements(median_epoch_s=400.0)))  # 30.6 h/run
    assert d.sr1_applied and d.final.plan.epochs == 150
    d2 = decide(PilotMeasurements(**_measurements(median_epoch_s=700.0)))  # > 25 h at 150
    assert d2.status == "OWNER_CONSULTATION"


def test_sr6_reductions_apply_in_order_with_reprojection() -> None:
    # training 6 x 24.75 h = 148.5 h (SR1 not triggered); inference pushes total over 220
    m = PilotMeasurements(**_measurements(median_epoch_s=324.0, infer_s_per_case_condition=60.0))
    d = decide(m)
    assert not d.sr1_applied
    assert d.sr6_steps_applied[0].startswith("arm A external inference")
    assert [s["step"].split(":")[0] for s in d.steps][: len(d.sr6_steps_applied) + 1][
        0
    ] == "baseline"
    for i, label in enumerate(d.sr6_steps_applied):
        assert (
            label
            == [
                "arm A external inference on Full, -T1c and -FLAIR only",
                "drop C15",
                "switch all six runs to 150 epochs",
                "consult the owner",
            ][i]
        )
    if d.status == "FEASIBLE":
        assert d.final.t_total <= CAP_GPU_H
    huge = decide(
        PilotMeasurements(**_measurements(median_epoch_s=360.0, infer_s_per_case_condition=400.0))
    )
    assert huge.status == "OWNER_CONSULTATION" and huge.sr6_steps_applied[-1] == "consult the owner"


def test_budget_acceptance_sr8_and_concurrency() -> None:
    d = decide(PilotMeasurements(**_measurements(resume_pass=False)))
    assert d.status == "OWNER_CONSULTATION" and d.acceptance_failures
    d2 = decide(PilotMeasurements(**_measurements(quota_h_week=20.0, session_limit_h=9.0)))
    assert len(d2.sr8_events) == 2 and d2.calendar_weeks == pytest.approx(d2.final.t_total / 20)
    fast = project(PilotMeasurements(**_measurements(concurrency_gain=1.8)), Plan())
    bound = project(
        PilotMeasurements(**_measurements(concurrency_gain=1.8, cpu_bound=True)), Plan()
    )
    assert fast.concurrency_applied and not bound.concurrency_applied
    with pytest.raises(ValueError):
        PilotMeasurements(**_measurements(median_epoch_s=0.0))


# ============================================================ pilot selection (D3/D5)
def _rows(n_dev: int = 60, n_hoi: int = 20) -> list[CrosswalkRow]:
    rows = [CrosswalkRow(f"BraTS2021_{i:05d}", "18", "SYNTH", None) for i in range(n_dev)]
    rows += [
        CrosswalkRow(f"BraTS2021_{i:05d}", "1", "SYNTH", None) for i in range(n_dev, n_dev + n_hoi)
    ]
    return rows


def test_pilot_selection_deterministic_and_development_only() -> None:
    rows = _rows()
    a = select_pilot_cases(rows, n=40, seed=101)
    assert a == select_pilot_cases(rows, n=40, seed=101) and a == sorted(a) and len(a) == 40
    assert all(int(c.split("_")[1]) < 60 for c in a)
    assert verify_pilot_pool(a, rows) == {"D3": True, "D5": True}
    with pytest.raises(ProtocolDeviationError):
        verify_pilot_pool([*a[:-1], "BraTS2021_00070"], rows)  # a site-1 case
    with pytest.raises(ProtocolDeviationError):
        select_pilot_cases(_rows(n_dev=10), n=40, seed=101)


# ============================================================ review package
def test_review_package_contents(tmp_path: Path) -> None:
    sec = protocol_section(PROTOCOL_TEXT)
    assert sec.startswith("### 6.2") and "UNRESOLVED" in sec and "### 6.3" not in sec
    lab = np.zeros((8, 8, 6), dtype=np.int16)
    lab[2:5, 2:5, 4] = 2
    assert review_slice(lab, np.zeros_like(lab)) == 4

    def load_case(cid: str) -> tuple[dict[str, Any], Any]:  # SYNTHETIC volumes
        rng = np.random.default_rng(0)
        return {m: rng.random((8, 8, 6)) for m in ("T1", "T1c", "T2", "FLAIR")}, lab

    info = build_review_package(
        tmp_path / "pkg",
        [("BraTS2021_00001", "BraTS2021_00002")],
        {"BraTS2021_00001": {"collection": "SYNTH", "site": "18"}},
        PROTOCOL_TEXT,
        ("Ayush Kushwaha", "Dr. Sreenivasa Chakravarthi"),
        load_case=load_case,
    )
    assert info["figures"] == ["pairs/BraTS2021_00001__BraTS2021_00002.png"]
    with (tmp_path / "pkg/reviews_TEMPLATE.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert tuple(rows[0]) == CSV_FIELDS and rows[1][2] == ""  # decision never pre-filled
    readme = (tmp_path / "pkg/README.md").read_text(encoding="utf-8")
    assert "never commit" in readme and "Decision rule" in readme


# ============================================================ git safety
def _git(root: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "g"
    root.mkdir()
    _git(root, "init", "-q")
    monkeypatch.setattr(gitops, "check_repository", lambda r: [])
    return root


GCFG = {
    "identity": {"name": "Ayush Kushwaha", "email": "ayushkushwaha21029@gmail.com"},
    "commit_paths": ["results/", "docs/project_status.yaml"],
    "remote": "origin",
    "branch": "x",
}


def test_commit_milestone_allowlist_identity_and_message(git_repo: Path) -> None:
    (git_repo / "results").mkdir()
    (git_repo / "results/a.json").write_text("{}", encoding="utf-8")
    (git_repo / "secret.txt").write_text("not allowed", encoding="utf-8")
    sha = gitops.commit_milestone(git_repo, "chore: SYNTHETIC milestone", GCFG)
    assert sha
    files = _git(git_repo, "show", "--name-only", "--format=", "HEAD").split()
    assert files == ["results/a.json"]  # secret.txt never staged
    body = _git(git_repo, "log", "-1", "--format=%an <%ae>%n%B")
    assert body.startswith("Ayush Kushwaha <ayushkushwaha21029@gmail.com>")
    assert "co-authored" not in body.lower()
    assert gitops.commit_milestone(git_repo, "chore: nothing new", GCFG) is None
    with pytest.raises(ProvenanceError, match="attribution"):
        gitops.commit_milestone(git_repo, "x\n\nCo-Authored-By: someone", GCFG)
    _git(git_repo, "add", "secret.txt")
    with pytest.raises(ProvenanceError, match="allow-list"):
        gitops.commit_milestone(git_repo, "chore: stray", GCFG)


def test_identity_mismatch_refused(git_repo: Path) -> None:
    _git(git_repo, "config", "--local", "user.name", "someone else")
    with pytest.raises(ProvenanceError, match="expected"):
        gitops.ensure_identity(git_repo, GCFG["identity"])
    assert gitops.is_allowed("results/x/y.json", ["results/"])
    assert not gitops.is_allowed("resultsX.json", ["results/"])


# ============================================================ CLI
def test_cli_master_run_plan_and_safety(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    work = tmp_path / "work"
    assert (
        main(["--repo-root", str(REPO_ROOT), "master-run", "--plan", "--work-dir", str(work)]) == 0
    )
    out = capsys.readouterr().out
    assert "B2" in out and "TRAIN-B2" in out and "nothing executed" in out
    assert "every reachable step" not in out
    assert not work.exists()  # --plan creates nothing
    assert (
        main(
            [
                "--repo-root",
                str(REPO_ROOT),
                "master-run",
                "--plan",
                "--work-dir",
                str(REPO_ROOT / "x"),
            ]
        )
        == 3
    )
    assert "outside the repository" in capsys.readouterr().err
    assert main(["--repo-root", str(REPO_ROOT), "master-run", "--plan"]) in (0, 3)
    from brats_uncertainty.orchestration.entry import master_run

    with pytest.raises(ConfigError):
        master_run(REPO_ROOT, work_dir=str(work), push=True, environ={})


# ============================================================ official metadata download
def test_fetch_official_file_is_restricted_and_byte_exact(tmp_path: Path) -> None:
    import io

    from brats_uncertainty.data.acquisition import fetch_official_file

    prefixes = ("https://www.cancerimagingarchive.net/",)
    payload = b"SYNTHETIC\x00bytes\r\n"
    url = "https://www.cancerimagingarchive.net/wp-content/uploads/x.csv"
    out = fetch_official_file(
        url, tmp_path / "x.csv", official_prefixes=prefixes, opener=lambda u: io.BytesIO(payload)
    )
    assert out.read_bytes() == payload and not (tmp_path / "x.csv.part").exists()
    for bad in (
        "http://www.cancerimagingarchive.net/x.csv",
        "https://mirror.example.org/x.csv",
        "https://user:pw@www.cancerimagingarchive.net/x.csv",
    ):
        with pytest.raises(ProvenanceError):
            fetch_official_file(bad, tmp_path / "y.csv", official_prefixes=prefixes)
    with pytest.raises(FileExistsError):
        fetch_official_file(url, out, official_prefixes=prefixes)
