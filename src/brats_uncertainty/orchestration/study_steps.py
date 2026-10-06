"""Executors for EXP-001, D6, validation/SR2, C1-C6, evaluations, statistics, export, website.

Same contract as ``orchestration.steps``: complete the step or stop with the exact
blocker and action. GPU work goes through ``ctx.process_runner`` (EXP-001) and
``ctx.ensemble_factory`` (inference), both injectable for tests. Test and external
evaluations and the statistics run from a clean worktree of the ``eval-v1`` tag as a
subprocess (``brats-uncertainty evaluate-set`` / ``analyze-study``), so the tagged code
produces every result (SR4); the evaluation ledger lives in the main checkout.
"""

from __future__ import annotations

import csv
import re
import shutil
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from brats_uncertainty.evaluation.guards import EVAL_TAG
from brats_uncertainty.evaluation.lifecycle import CLOSED_STATUSES
from brats_uncertainty.orchestration.confirmations import (
    CONFIRMATIONS_RELPATH,
    missing_confirmations,
)
from brats_uncertainty.orchestration.state import PASSED, Outcome
from brats_uncertainty.orchestration.steps import (
    DATASET_CONFIG,
    Context,
    StepBlocked,
    StepFailed,
    StepReview,
    close_cd_gate,
    crosswalk_rows,
    split_partitions,
)
from brats_uncertainty.utils.io import read_json, read_yaml, write_json

MAIN_RESULTS = Path("results/MAIN")
UNITS_DIR = MAIN_RESULTS / "units"
FROZEN_C5 = MAIN_RESULTS / "c5_frozen.json"
D6_DECISION = Path("docs/research/execution/D6_OWNER_DECISION.yaml")
AFRICA_CONFIG = Path("configs/dataset/brats_africa.yaml")
EVAL_CONFIG = Path("configs/evaluation/evaluation.yaml")


# ------------------------------------------------------------------ shared helpers
def require_confirmations(ctx: Context, step_id: str) -> None:
    missing = missing_confirmations(ctx.repo_root, step_id)
    if missing:
        raise StepReview(
            f"{step_id}: owner confirmation of implementation choices {missing} is due "
            "(docs/reproducibility/REPRODUCIBILITY.md §4)",
            f"the owner records items {missing} as CONFIRMED (or requests a change, made in code "
            f"before this step) in {CONFIRMATIONS_RELPATH.as_posix()}; then re-run with --resume",
        )


def _set_status(
    ctx: Context,
    updates: Mapping[tuple[str, str], Any] | None = None,
    experiments: Mapping[str, str] | None = None,
    message: str = "",
) -> None:
    from brats_uncertainty.evaluation.stage_status import set_stage_fields

    if set_stage_fields(ctx.repo_root, updates or {}, experiments):
        ctx.ops.milestone(message or "chore(status): stage status")


def planned_epochs(ctx: Context) -> int:
    """Epochs after D6: the budget plan, or the owner's D6 decision (250 or 150 only)."""
    exp = ctx.repo_root / ctx.cfg["paths"]["exp001_dir"]
    epochs = int(read_json(exp / "budget_projection.json")["final"]["plan"]["epochs"])
    dec = ctx.repo_root / D6_DECISION
    if dec.is_file():
        epochs = int((read_yaml(dec) or {}).get("epochs", epochs))
    if epochs not in (250, 150):
        raise StepFailed(
            f"D6: {epochs} epochs is not a protocol value", "only 250 or 150 (SR1/SR6)"
        )
    return epochs


def _copy(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest


def _groups(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["case_id"]: r["group_id"] for r in csv.DictReader(fh)}


# ------------------------------------------------------------------ EXP-001
def execute_pilot(ctx: Context) -> Outcome:
    from brats_uncertainty.compute.pilot_harness import (
        PilotRecord,
        assemble_measurements,
        constraints_record,
    )
    from brats_uncertainty.compute.pilot_run import (
        PILOT_EXPERIMENT,
        TIMING_RUNS,
        GpuMonitor,
        SubprocessRunner,
        du_bytes,
        gpu_monitor_summary,
        plan_and_preprocess,
        run_resume_test,
        run_timing,
        time_metric_code,
    )
    from brats_uncertainty.orchestration.pilot import select_pilot_cases, verify_pilot_pool

    exp_dir = ctx.repo_root / ctx.cfg["paths"]["exp001_dir"]
    measurements = exp_dir / "measurements.json"
    if measurements.is_file():
        return Outcome(PASSED, "EXP-001 measurements recorded", evidence=[ctx.rel(measurements)])
    require_confirmations(ctx, "PILOT")
    rows = crosswalk_rows(ctx)
    pcfg = read_yaml(ctx.repo_root / "configs/experiments/EXP-001.yaml")["pilot"]
    cases = select_pilot_cases(rows, n=int(pcfg["n_cases"]), seed=int(pcfg["selection_seed"]))
    verified = verify_pilot_pool(cases, rows)  # D3/D5 before anything runs
    from brats_uncertainty.data.nnunet_dataset import write_nnunet_dataset
    from brats_uncertainty.data.schema import load_schema
    from brats_uncertainty.models.trainer_registration import register_trainers

    _set_status(ctx, experiments={"EXP-001": "RUNNING"}, message="chore(EXP-001): pilot RUNNING")
    register_trainers()
    tr = ctx.cfg["training"]
    did, name = int(tr["pilot_dataset_id"]), str(tr["pilot_dataset_name"])
    pilot_work = ctx.work_dir / "exp001"
    raw_base, pre_base = pilot_work / "nnUNet_raw", pilot_work / "nnUNet_preprocessed"
    results_root, logs = pilot_work / "nnunet_results", pilot_work / "logs"
    env = {"nnUNet_raw": str(raw_base), "nnUNet_preprocessed": str(pre_base)}
    raw = raw_base / f"Dataset{did:03d}_{name}"
    if not raw.is_dir():
        write_nnunet_dataset(
            ctx.repo_root,
            ctx.training_root(),
            load_schema(ctx.repo_root / DATASET_CONFIG),
            raw,
            dataset_id=did,
            dataset_name=name,
            case_ids=cases,
            gate_action="run_exp001",
            training_root_reference=ctx.cfg["acquisition"]["training_set"],
        )
    runner = ctx.process_runner or SubprocessRunner()
    facts = ctx.ops.preflight("JOB-PILOT").facts
    rec = PilotRecord(platform=str(facts["environment"]), gpu_names=[str(facts["gpu"].get("name"))])
    code, wall = plan_and_preprocess(runner, did, env, logs / "plan_and_preprocess.log")
    if code != 0:
        _record_pilot_failure(ctx, exp_dir, {"plan_and_preprocess": (code, logs)})
        raise StepBlocked(
            f"EXP-001: plan/preprocess exited {code}",
            f"see {ctx.rel(exp_dir / PILOT_FAILURE_LOG)}; fix; re-run --resume",
        )
    rec.preproc_s, rec.n_preproc_cases = wall, len(cases)
    codes = []
    monitor_csv = pilot_work / "gpu_monitor.csv"
    with GpuMonitor(monitor_csv):
        for run_id, arm, seed in TIMING_RUNS:
            codes.append(
                run_timing(
                    runner,
                    dataset_id=did,
                    results_root=results_root,
                    logs=logs,
                    base_env=env,
                    run_id=run_id,
                    arm=arm,
                    seed=seed,
                    rec=rec,
                )
            )
    rec.monitor = gpu_monitor_summary(monitor_csv)
    failed = {
        run_id: (c, logs)
        for (run_id, _arm, _seed), c in zip(TIMING_RUNS, codes, strict=True)
        if run_id not in rec.timings
    }
    if failed:
        _record_pilot_failure(ctx, exp_dir, failed)
    if "P2" not in rec.timings:
        raise StepBlocked(
            "EXP-001: the single-GPU timing run (P2) did not complete "
            f"(exit codes: { {k: v[0] for k, v in failed.items()} })",
            f"see {ctx.rel(exp_dir / PILOT_FAILURE_LOG)}; fix; re-run --resume",
        )
    rec.resume = run_resume_test(
        runner, dataset_id=did, results_root=results_root, logs=logs, base_env=env
    )
    rec.peak_mem_fits_default_plan = all(c == 0 for c in codes)
    rec.infer_s_per_case_condition = _pilot_inference_timing(ctx, cases, results_root, raw.name)
    rec.metric_s_per_case_condition = time_metric_code((240, 240, 155))
    rec.disk_bytes = {
        "raw": du_bytes(raw_base),
        "preprocessed": du_bytes(pre_base),
        "results": du_bytes(results_root),
    }
    rec.writable_bytes = shutil.disk_usage(ctx.work_dir).free
    if rec.platform == "vm":
        rec.quota_h_week = rec.session_limit_h = (
            "not applicable: private VM (no quota, no session limit)"
        )
    else:
        for attr, key in (
            ("quota_h_week", "BRATS_PLATFORM_QUOTA_H_WEEK"),
            ("session_limit_h", "BRATS_PLATFORM_SESSION_LIMIT_H"),
        ):
            if ctx.environ.get(key):
                setattr(rec, attr, float(ctx.environ[key]))  # read by the owner from the account UI
    planned = (
        sum(len(v) for k, v in split_partitions(ctx).items() if k != "internal_test")
        if (ctx.splits / "split_all.csv").is_file()
        else 592
    )
    body = assemble_measurements(rec, planned_cases=planned)
    exp_dir.mkdir(parents=True, exist_ok=True)
    write_json(exp_dir / "constraints.json", constraints_record(cases, verified), overwrite=True)
    from brats_uncertainty.compute.jobs import environment_facts

    write_json(exp_dir / "environment.json", environment_facts(), overwrite=True)
    write_json(exp_dir / "resume_check.json", rec.resume, overwrite=True)
    write_json(measurements, {"experiment": PILOT_EXPERIMENT, **body})
    _set_status(
        ctx, experiments={"EXP-001": "COMPLETED"}, message="data(EXP-001): pilot measurements"
    )
    return Outcome(PASSED, "EXP-001 measurements recorded", evidence=[ctx.rel(measurements)])


PILOT_FAILURE_LOG = "failure_logs.json"
_LOG_TAIL_LINES = 80
_UNSAFE_LOG_LINE = re.compile(
    r"https?://|token|passcode|secret|password|api[_-]?key|dice|aurc", re.I
)  # D4: no metric values


def _record_pilot_failure(
    ctx: Context, exp_dir: Path, failed: Mapping[str, tuple[int, Path]]
) -> None:
    """Commit-safe evidence of failed pilot processes: exit codes and log tails.

    The logs live in the session's temporary work directory, which a hosted notebook
    discards. Tails are printed and written next to the measurements; lines that look
    like URLs or credentials, and nnU-Net metric lines (D4), are dropped.
    """
    body: dict[str, Any] = {"experiment": "EXP-001", "failed_processes": {}}
    for run_id, (code, logs) in failed.items():
        log = logs / f"{run_id}.log"
        lines = (
            log.read_text(encoding="utf-8", errors="replace").splitlines() if log.is_file() else []
        )
        tail = [ln[:400] for ln in lines if not _UNSAFE_LOG_LINE.search(ln)][-_LOG_TAIL_LINES:]
        body["failed_processes"][run_id] = {
            "exit_code": code,
            "log_present": log.is_file(),
            "log_tail": tail,
        }
        print(f"---- EXP-001 {run_id}: exit {code}; last {len(tail)} log lines ----")
        print("\n".join(tail))
    exp_dir.mkdir(parents=True, exist_ok=True)
    write_json(exp_dir / PILOT_FAILURE_LOG, body, overwrite=True)


def _pilot_inference_timing(
    ctx: Context, cases: list[str], results_root: Path, dataset_dir: str
) -> float:
    """I1: 3-member ensemble inference time per case-condition; no label-based metric (D4)."""
    from brats_uncertainty.compute.pilot_run import PILOT_EXPERIMENT, model_folder
    from brats_uncertainty.models.nnunet import PILOT_TRAINERS, RunSpec, run_namespace
    from brats_uncertainty.preprocessing.modalities import C5

    members = [
        model_folder(
            run_namespace(results_root, PILOT_EXPERIMENT, RunSpec("B", s), label=lab),
            dataset_dir,
            PILOT_TRAINERS["B"],
        )
        for s, lab in ((0, "P2"), (1, "P5seed1"), (2, "P5seed2"))
    ]
    source = (
        ctx.ensemble_factory("pilot", "B", cases[:10])
        if ctx.ensemble_factory
        else _real_source(ctx, members, cases[:10], labels=False)
    )
    n, t0 = 0, time.perf_counter()
    for case in cases[:10]:
        for subset in C5:
            source.member_probabilities(case, subset)
            n += 1
    return (time.perf_counter() - t0) / n


def _real_source(
    ctx: Context,
    members: list[Path],
    cases: list[str],
    *,
    labels: bool,
    regions: Mapping[str, Any] | None = None,
) -> Any:  # pragma: no cover - GPU
    from brats_uncertainty.data.manifest_doc import load_case_manifest
    from brats_uncertainty.preprocessing.labels import BRATS2021_REGIONS
    from brats_uncertainty.preprocessing.modalities import MODALITIES
    from brats_uncertainty.study.nnunet_inference import NnUNetEnsembleSource

    manifest = {e.case_id: e for e in load_case_manifest(ctx.records / "B5_manifest.json").entries}
    root = ctx.training_root()
    images = {c: [root / manifest[c].images[m].relpath for m in MODALITIES] for c in cases}
    lab = {c: root / manifest[c].label.relpath for c in cases if labels and manifest[c].label}  # type: ignore[union-attr]
    return NnUNetEnsembleSource(members, images, lab, regions or BRATS2021_REGIONS)


def execute_d6(ctx: Context) -> Outcome:
    from brats_uncertainty.orchestration.budget import PilotMeasurements, decide

    exp = ctx.repo_root / ctx.cfg["paths"]["exp001_dir"]
    body = read_json(exp / "measurements.json")
    decision = decide(PilotMeasurements(**body["projection_inputs"]))
    unmeasurable = list(body.get("not_measurable_on_platform", []))
    path = exp / "budget_projection.json"
    if not path.is_file():
        write_json(path, {**decision.as_dict(), "not_measurable_on_platform": unmeasurable})
    if decision.status != "FEASIBLE" or unmeasurable:
        dec_path = ctx.repo_root / D6_DECISION
        dec = read_yaml(dec_path) if dec_path.is_file() else None
        if not dec or dec.get("decision") != "PROCEED":
            reasons = decision.acceptance_failures + [
                f"{q}: not measurable on this platform" for q in unmeasurable
            ]
            if decision.status != "FEASIBLE":
                reasons.append("SR1/SR6 reached 'consult the owner'")
            raise StepReview(
                f"D6: EXP-001 acceptance needs the owner: {reasons}",
                f"the owner reviews {ctx.rel(path)} and records the decision in "
                f"{D6_DECISION.as_posix()} "
                "(decision: PROCEED or STOP; epochs: 250 or 150; reason); then re-run --resume",
            )
        evidence = dec_path
    else:
        evidence = path
    return close_cd_gate(ctx, "D6", evidence, "SR1/SR6/SR8 applied before main training")


# ------------------------------------------------------------------ inference helpers
def _member_folders(ctx: Context, arm: str) -> list[Path]:
    from brats_uncertainty.models.nnunet import (
        MAIN_EXPERIMENT_ID,
        PROTOCOL_CONFIGURATION,
        RunSpec,
        run_namespace,
        trainer_for,
    )

    tr = ctx.cfg["training"]
    ds = f"Dataset{int(tr['dataset_id']):03d}_{tr['dataset_name']}"
    trainer = trainer_for(arm, planned_epochs(ctx))
    return [
        run_namespace(ctx.work_dir / "nnunet_results", MAIN_EXPERIMENT_ID, RunSpec(arm, s))
        / ds
        / f"{trainer}__nnUNetPlans__{PROTOCOL_CONFIGURATION}"
        for s in (0, 1, 2)
    ]


def _sources(ctx: Context, dataset: str, cases: list[str]) -> dict[str, Any]:
    if ctx.ensemble_factory is not None:
        return {arm: ctx.ensemble_factory(dataset, arm, cases) for arm in ("A", "B")}
    return {
        arm: _real_source(ctx, _member_folders(ctx, arm), cases, labels=True) for arm in ("A", "B")
    }


# ------------------------------------------------------------------ validation, SR2, C5
def execute_validation(ctx: Context) -> Outcome:
    from brats_uncertainty.preprocessing.modalities import C5_NAMES
    from brats_uncertainty.study.freeze import sr2_check
    from brats_uncertainty.study.run import evaluate_set
    from brats_uncertainty.study.units import read_unit_rows, units_filename

    require_confirmations(ctx, "VALIDATION")
    _set_status(
        ctx, {("training", "status"): "COMPLETED"}, message="chore(status): training COMPLETED"
    )
    sr2_path = ctx.repo_root / MAIN_RESULTS / "sr2.json"
    a_rel = UNITS_DIR / units_filename("validation", "A")
    if not (ctx.repo_root / a_rel).is_file():
        cases = split_partitions(ctx)["validation"]
        out = evaluate_set(
            dataset="validation",
            cases=cases,
            group_of=_groups(ctx.splits / "patient_groups_dev.csv"),
            sources=_sources(ctx, "validation", cases),
            out_dir=ctx.work_dir / "eval" / "units",
            arm_conditions={"A": C5_NAMES, "B": C5_NAMES},
        )
        for arm in ("A", "B"):
            _copy(out[arm], ctx.repo_root / UNITS_DIR / out[arm].name)
    sr2 = sr2_check(read_unit_rows(ctx.repo_root / a_rel))
    if not sr2_path.is_file():
        write_json(sr2_path, sr2)
    ctx.ops.milestone("data(validation): unit metrics and SR2 record")
    if not sr2["passed"]:
        raise StepFailed(
            f"SR2: arm A full-input mean ET Dice on validation {sr2['mean_et_dice']:.4f} < 0.75",
            "stop and debug before any test evaluation (protocol §20 SR2); "
            "the test set is untouched",
        )
    return Outcome(
        PASSED,
        f"validation evaluated; SR2 passed ({sr2['mean_et_dice']:.4f})",
        evidence=[ctx.rel(sr2_path)],
    )


def execute_c5(ctx: Context) -> Outcome:
    from brats_uncertainty.study.freeze import freeze_c5
    from brats_uncertainty.study.units import read_unit_rows, units_filename

    if ctx.ops.gate_status("C5") in CLOSED_STATUSES:
        return Outcome(PASSED, "C5 already closed")
    require_confirmations(ctx, "C5")
    path = ctx.repo_root / FROZEN_C5
    if not path.is_file():
        u = ctx.repo_root / UNITS_DIR
        write_json(
            path,
            freeze_c5(
                read_unit_rows(u / units_filename("validation", "A")),
                read_unit_rows(u / units_filename("validation", "B")),
            ),
        )
    return close_cd_gate(ctx, "C5", path, "validation-derived tau_q and I frozen")


# ------------------------------------------------------------------ C4 (HOI grouping)
def execute_c4(ctx: Context) -> Outcome:
    from brats_uncertainty.data.manifest_doc import load_case_manifest
    from brats_uncertainty.grouping.similarity import MaskIndex
    from brats_uncertainty.pipeline import load_label, wt_mask
    from brats_uncertainty.protocol import load_protocol
    from brats_uncertainty.study.hoi import freeze_hoi_groups, screen_hoi

    if ctx.ops.gate_status("C4") in CLOSED_STATUSES:
        return Outcome(PASSED, "C4 already closed")
    spec = load_protocol(ctx.repo_root)
    hoi_site = str(spec.raw["cohorts"]["hoi_site_id"])
    hoi_rows = [r for r in crosswalk_rows(ctx) if r.site_id == hoi_site]
    out_dir = ctx.records / "C4"
    flagged_csv = out_dir / "flagged_pairs_hoi.csv"
    if not flagged_csv.is_file():
        manifest = {
            e.case_id: e for e in load_case_manifest(ctx.records / "B5_manifest.json").entries
        }
        root = ctx.training_root()
        masks = {}
        for r in hoi_rows:
            label = manifest[r.case_id].label
            if label is None:
                raise StepFailed(f"C4: {r.case_id} has no label in the B5 manifest", "owner review")
            masks[r.case_id] = MaskIndex.from_mask(
                r.case_id, wt_mask(load_label(root / label.relpath))
            )
        screen_hoi(ctx.repo_root, masks, ctx.records / "B7" / "t_screen.json", out_dir)
    with flagged_csv.open(encoding="utf-8", newline="") as fh:
        flagged = [(r["case_a"], r["case_b"]) for r in csv.DictReader(fh)]
    reviews = ctx.records / "C4_reviews.csv"
    env_reviews = ctx.environ.get("BRATS_C4_REVIEWS", "").strip()
    if env_reviews and Path(env_reviews).is_file() and not reviews.is_file():
        _copy(Path(env_reviews), reviews)
    if flagged and not reviews.is_file():
        raise StepReview(
            f"C4: {len(flagged)} flagged HOI pair(s) need the frozen §6.2 manual review",
            f"reviewers {spec.reviewers[0]} and {spec.reviewers[1]} record SAME_PATIENT / "
            "DIFFERENT_PATIENT "
            f"/ UNRESOLVED per pair of {ctx.rel(flagged_csv)} in {ctx.rel(reviews)} "
            "(B8 review format); "
            "then re-run --resume",
        )
    groups = ctx.splits / "patient_groups_hoi.csv"
    if not groups.is_file():
        freeze_hoi_groups(
            ctx.repo_root, hoi_rows, flagged, reviews if flagged else None, spec.reviewers, groups
        )
    return close_cd_gate(ctx, "C4", groups, "HOI patient grouping frozen")


# ------------------------------------------------------------------ C1-C3 (BraTS-Africa)
AFRICA_RECORD = Path("docs/data/records/C1_C3_brats_africa.json")


def execute_c1(ctx: Context) -> Outcome:
    from brats_uncertainty.data.crosswalk import read_table_records
    from brats_uncertainty.errors import ConfigError
    from brats_uncertainty.study.africa import require_route, verify_africa

    if ctx.ops.gate_status("C1") in CLOSED_STATUSES:
        return Outcome(PASSED, "C1 already closed")
    cfg = read_yaml(ctx.repo_root / AFRICA_CONFIG)
    try:
        require_route(cfg)
    except ConfigError as exc:
        raise StepReview(
            f"C1: {exc}",
            "owner decision: approve an official BraTS-Africa route (TCIA, DOI 10.7937/v8h6-8x67, "
            "processed "
            "release CC BY 4.0) as a logged protocol amendment / route record, then set "
            "source.route in "
            f"{AFRICA_CONFIG.as_posix()}; SR7 halts this until then",
        ) from exc
    record = ctx.repo_root / AFRICA_RECORD
    if not record.is_file():
        id_col = cfg["inclusion"].get("id_column")
        root_env, meta_env = cfg["data_root_env"], "BRATS_AFRICA_METADATA"
        data_root, meta = ctx.environ.get(root_env, ""), ctx.environ.get(meta_env, "")
        if not id_col or not data_root or not meta:
            raise StepBlocked(
                "C1: BraTS-Africa inputs not available",
                f"deliver the official processed release to private storage and set "
                f"{root_env}; set "
                f"{meta_env} to BraTS-Africa_TCIA_datainfo_v2.xlsx; set inclusion.id_column in "
                f"{AFRICA_CONFIG.as_posix()} to the case-ID header of the '95 Glioma' sheet",
            )
        glioma = [
            str(r[id_col])
            for r in read_table_records(Path(meta), cfg["inclusion"]["sheet"])
            if r.get(id_col)
        ]
        brats_hashes = frozenset(
            f["sha256"]
            for f in read_json(ctx.records / "B5_manifest.json")["files"]
            if f.get("file_type") == "image"
        )
        import nibabel as nib
        import numpy as np

        res = verify_africa(
            Path(data_root),
            glioma,
            cfg,
            load_label=lambda p: np.asarray(nib.load(str(p)).dataobj),  # type: ignore[attr-defined]
            image_shape=lambda p: tuple(nib.load(str(p)).shape),  # type: ignore[attr-defined]
            brats2021_image_sha256=brats_hashes,
        )
        write_json(record, {"gates": ["C1", "C2", "C3"], **res})
    return close_cd_gate(ctx, "C1", record, "BraTS-Africa label verification")


def _close_from_africa(gid: str, text: str) -> Callable[[Context], Outcome]:
    def execute(ctx: Context) -> Outcome:
        record = ctx.repo_root / AFRICA_RECORD
        if not record.is_file():
            raise StepBlocked(f"{gid}: C1-C3 record missing", "C1 must run first")
        return close_cd_gate(ctx, gid, record, text)

    return execute


execute_c2 = _close_from_africa("C2", "BraTS-Africa four-sequence verification")
execute_c3 = _close_from_africa("C3", "BraTS-Africa eligible count frozen (<= 95)")


# ------------------------------------------------------------------ C6 (eval-v1)
def execute_c6(ctx: Context) -> Outcome:
    from brats_uncertainty.utils.git import git_is_dirty, git_tag_commit

    if ctx.ops.gate_status("C6") in CLOSED_STATUSES and git_tag_commit(ctx.repo_root, EVAL_TAG):
        return Outcome(PASSED, "C6 already closed and tagged")
    require_confirmations(ctx, "C6")
    hd = read_yaml(ctx.repo_root / EVAL_CONFIG).get("hd95", {})
    if not hd.get("evaluator"):
        raise StepReview(
            "C6: no HD95 evaluator is pinned (protocol §4 S3: the BraTS evaluation code "
            "pinned at C6)",
            f"the owner pins the BraTS HD95 evaluator (package + version + entry point) in "
            f"{EVAL_CONFIG.as_posix()} hd95.evaluator; its empty-mask behaviour is then verified "
            "by a "
            "test before the tag; re-run --resume",
        )
    doc = ctx.repo_root / "docs/research/execution/C6_EVAL_V1.md"
    if not doc.is_file():
        doc.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Gate C6: evaluation code tagged `{EVAL_TAG}`",
            "",
            f"The commit that carries this record (and closes C6) is tagged `{EVAL_TAG}`.",
            "",
            f"- HD95 evaluator: `{hd['evaluator']}`",
            f"- Implementation choices confirmed: `{CONFIRMATIONS_RELPATH.as_posix()}`",
            "",
            "Test and external evaluations run only from this tag (SR4); each set is evaluated "
            "once (experiments/evaluation_ledger.jsonl).",
        ]
        doc.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if ctx.ops.gate_status("C6") not in CLOSED_STATUSES:
        close_cd_gate(ctx, "C6", doc, "evaluation code tagged eval-v1")
    if git_tag_commit(ctx.repo_root, EVAL_TAG) is None:
        if git_is_dirty(ctx.repo_root) is not False:
            raise StepBlocked(
                "C6: working tree not clean", "commit or remove the changes, then --resume"
            )
        code = ctx.ops.run(
            ["git", "tag", "-a", EVAL_TAG, "-m", "Evaluation code frozen (gate C6)"],
            cwd=ctx.repo_root,
        )
        if code != 0:
            raise StepBlocked(
                "C6: creating the eval-v1 tag failed", "inspect git output; re-run --resume"
            )
        if getattr(ctx.ops, "push_enabled", False):
            ctx.ops.run(
                ["git", "push", ctx.cfg["git"]["remote"], f"refs/tags/{EVAL_TAG}"],
                cwd=ctx.repo_root,
            )
    return Outcome(
        PASSED,
        f"C6 closed; {EVAL_TAG} = {git_tag_commit(ctx.repo_root, EVAL_TAG)}",
        evidence=[ctx.rel(doc)],
    )


# ------------------------------------------------------------------ tagged evaluations
def eval_worktree(ctx: Context) -> Path:
    wt = ctx.work_dir / "eval-v1-worktree"
    if not (wt / ".git").exists():
        code = ctx.ops.run(
            ["git", "worktree", "add", "--detach", str(wt), EVAL_TAG], cwd=ctx.repo_root
        )
        if code != 0:
            raise StepBlocked(
                "could not create the eval-v1 worktree", "inspect git output; re-run --resume"
            )
    return wt


def _tagged_cli(ctx: Context, args: list[str], *, allow_fail: bool = False) -> None:
    import sys

    wt = eval_worktree(ctx)
    env = {"PYTHONPATH": str(wt / "src")}
    code = ctx.ops.run(
        [sys.executable, "-m", "brats_uncertainty.cli", "--repo-root", str(wt), *args],
        cwd=wt,
        env=env,
    )
    if code != 0 and not allow_fail:
        raise StepBlocked(
            f"tagged command failed ({code}): {' '.join(args[:2])}",
            "inspect its output (gates, ledger, inputs); re-run --resume",
        )


def evaluation_executor(dataset: str) -> Callable[[Context], Outcome]:
    def execute(ctx: Context) -> Outcome:
        from brats_uncertainty.study.units import units_filename

        dest = ctx.repo_root / UNITS_DIR / units_filename(dataset, "B")
        if dest.is_file():
            return Outcome(PASSED, f"{dataset} evaluated", evidence=[ctx.rel(dest)])
        section = "internal" if dataset == "internal_test" else "external"
        _set_status(
            ctx,
            {("evaluation", section): "IN_PROGRESS"},
            message=f"chore(status): {dataset} evaluation",
        )
        out = ctx.work_dir / "eval" / "units"
        _tagged_cli(
            ctx,
            [
                "evaluate-set",
                "--dataset",
                dataset,
                "--work-dir",
                str(ctx.work_dir),
                "--out-dir",
                str(out),
                "--main-repo",
                str(ctx.repo_root),
            ],
        )
        for f in sorted(out.glob(f"units_{dataset}_*.csv")):
            _copy(f, ctx.repo_root / UNITS_DIR / f.name)
        c15 = out / f"raw_{units_filename(dataset, 'B', 'C15')}"
        if c15.is_file():  # S10 (internal test, arm B only)
            _copy(c15, ctx.repo_root / UNITS_DIR / c15.name)
        ctx.ops.milestone(f"data(evaluation): {dataset} unit metrics (eval-v1)")
        return Outcome(PASSED, f"{dataset} evaluated with eval-v1", evidence=[ctx.rel(dest)])

    return execute


ANALYSIS_OUT = Path("eval") / "analysis"
VERIFICATION_DIR = Path("results/verification")
VERIFICATION_REPORT = Path("docs/research/execution/RESULT_VERIFICATION_REPORT.md")


def execute_statistics(ctx: Context) -> Outcome:
    """All pre-registered analyses, into private storage. Nothing is published here."""
    out = ctx.work_dir / ANALYSIS_OUT
    if (out / "analysis" / "internal_test_analysis.json").is_file():
        return Outcome(PASSED, "analyses computed (awaiting independent verification)")
    _tagged_cli(
        ctx,
        [
            "analyze-study",
            "--units-dir",
            str(ctx.repo_root / UNITS_DIR),
            "--frozen",
            str(ctx.repo_root / FROZEN_C5),
            "--out-dir",
            str(out),
            "--main-repo",
            str(ctx.repo_root),
            "--work-dir",
            str(ctx.work_dir),
        ],
    )
    return Outcome(PASSED, "analyses computed (awaiting independent verification)")


def blocked_report(result: Any) -> str:
    """BLOCKED RESULT / RESULT ID / EXACT DISCREPANCY / AFFECTED ARTIFACTS / REQUIRED RERUN."""
    from brats_uncertainty.verification.model import FAIL, NOT_PERFORMED

    lines = []
    for st in result.stages.values():
        for c in st.checks:
            if c.status in (FAIL, NOT_PERFORMED):
                ids = ", ".join(sorted(result.result_index)) or "all"
                lines.append(
                    f"BLOCKED RESULT: {st.id} | RESULT ID: {ids} | EXACT DISCREPANCY: {c.name}: "
                    f"production {c.production!r} vs recomputed {c.recomputed!r} "
                    f"({c.status}; {c.detail}) | AFFECTED ARTIFACTS: analysis outputs of stage "
                    f"{st.id} | REQUIRED RERUN: fix the cause, rerun the {st.id} producer, "
                    "re-verify"
                )
    return "\n".join(lines[:20])


def execute_verify(ctx: Context) -> Outcome:
    """Independent verification; publish to the working tree only if VERIFIED."""
    from brats_uncertainty.results.export import export_public_artifacts
    from brats_uncertainty.verification.run import load_result
    from brats_uncertainty.verification.verify import write_outputs

    work_ver = ctx.work_dir / "verification"
    result_path = work_ver / "verification_result.json"
    if not result_path.is_file():
        _tagged_cli(
            ctx,
            [
                "verify-results",
                "--main-repo",
                str(ctx.repo_root),
                "--work-dir",
                str(ctx.work_dir),
                "--analysis-out",
                str(ctx.work_dir / ANALYSIS_OUT),
                "--out",
                str(work_ver),
            ],
            allow_fail=True,
        )
    if not result_path.is_file():
        raise StepBlocked(
            "verification did not produce a result", "inspect the verify-results output"
        )
    result = load_result(result_path)
    if result.scientific_status != "VERIFIED":
        write_outputs(
            result, ctx.repo_root / VERIFICATION_DIR, ctx.repo_root / VERIFICATION_REPORT, {}
        )
        ctx.ops.milestone("docs(verification): verification BLOCKED - nothing published")
        raise StepFailed(
            "independent verification BLOCKED publication",
            blocked_report(result) or "see results/verification/RESULT_VERIFICATION_REPORT",
        )
    dest = ctx.repo_root / "results" / "public-safe"
    if not (dest / "analysis" / "internal_test_analysis.json").is_file():
        rep = export_public_artifacts(ctx.work_dir / ANALYSIS_OUT, dest)
        if rep.skipped:
            raise StepFailed(f"export refused files: {rep.skipped[:5]}", "nothing is published")
    write_outputs(result, ctx.repo_root / VERIFICATION_DIR, ctx.repo_root / VERIFICATION_REPORT, {})
    arts = sorted((dest / "analysis").glob("*.json"))
    write_json(
        ctx.repo_root / "results" / "index.json",
        {"artifacts": [ctx.rel(a) for a in arts]},
        overwrite=True,
    )
    for section in ("internal", "external"):
        _set_status(ctx, {("evaluation", section): "COMPLETED"})
    _set_status(
        ctx,
        {
            ("results", "status"): "AVAILABLE",
            ("results", "available"): True,
            ("results", "evidence"): "results/index.json",
            ("results", "statement"): "Independently verified results of the pre-registered "
            "analyses (results/verification/RESULT_VERIFICATION_CERTIFICATE.md).",
        },
    )
    return Outcome(PASSED, "scientific results independently VERIFIED (publication checks follow)")


def published_files(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / "results/public-safe",
        repo_root / "results/MAIN",
        repo_root / "results/EXP-001",
    ]
    files = [p for r in roots if r.is_dir() for p in r.rglob("*") if p.is_file()]
    return [*files, repo_root / "results/index.json"]


def retract(ctx: Context) -> None:
    """Undo an unverified publication in the working tree (nothing was committed)."""
    shutil.rmtree(ctx.repo_root / "results/public-safe", ignore_errors=True)
    (ctx.repo_root / "results/index.json").unlink(missing_ok=True)
    _set_status(
        ctx,
        {
            ("results", "status"): "UNAVAILABLE",
            ("results", "available"): False,
            ("results", "evidence"): None,
            ("results", "statement"): "Scientific results are being independently verified.",
        },
    )


def execute_website(ctx: Context) -> Outcome:
    """Build the site, reconcile the rendered Results page and the public files, certify."""
    from brats_uncertainty.results.site_export import export_site_data
    from brats_uncertainty.verification.run import load_result
    from brats_uncertainty.verification.verify import (
        check_public_export,
        check_website,
        write_outputs,
    )

    export_site_data(ctx.repo_root)
    site = ctx.repo_root / "website"
    npm = shutil.which("npm")
    if npm is None:
        raise StepBlocked(
            "website: npm not available in this environment",
            "install Node.js >= 20; re-run --resume",
        )
    if ctx.ops.run([npm, "run", "build"], cwd=site) != 0:
        raise StepBlocked("website production build failed", "fix the build error; re-run --resume")
    result_path = ctx.work_dir / "verification" / "verification_result.json"
    if result_path.is_file():
        result = load_result(result_path)
        page = (site / "out" / "results" / "index.html").read_text(encoding="utf-8")
        result.stages["WEBSITE"] = check_website(page, result)
        result.stages["PUBLIC_EXPORT"], hashes = check_public_export(
            published_files(ctx.repo_root), ctx.repo_root
        )
        write_outputs(
            result, ctx.repo_root / VERIFICATION_DIR, ctx.repo_root / VERIFICATION_REPORT, hashes
        )
        if result.overall != "VERIFIED":
            retract(ctx)
            write_outputs(
                result,
                ctx.repo_root / VERIFICATION_DIR,
                ctx.repo_root / VERIFICATION_REPORT,
                hashes,
            )
            export_site_data(ctx.repo_root)
            ctx.ops.milestone("docs(verification): publication checks BLOCKED - results retracted")
            raise StepFailed("publication checks failed; results retracted", blocked_report(result))
    export_site_data(ctx.repo_root)
    ctx.ops.milestone("data(results): independently verified results, website data and certificate")
    deployed = (
        "not deployed: no deployment credentials in this environment "
        "(NETLIFY_AUTH_TOKEN / VERCEL_TOKEN)"
    )
    if ctx.environ.get("NETLIFY_AUTH_TOKEN") and ctx.environ.get("NETLIFY_SITE_ID"):
        npx = shutil.which("npx") or "npx"
        if ctx.ops.run([npx, "netlify", "deploy", "--prod", "--dir", "out"], cwd=site) == 0:
            deployed = "deployed to Netlify (production)"
    return Outcome(
        PASSED, f"website built and reconciled; {deployed}", details={"deployment": deployed}
    )
