"""``brats-uncertainty verify-results``: verify the real analysis (from the eval-v1 worktree).

Builds the provenance stages from the real records and data (B2-B6 records, the private
training tree, the split files, the six MAIN run manifests and checkpoints, the external
gates and the evaluation ledger), runs the scientific verification and a second complete
analysis, and writes the evidence. Exit status 0 only if the scientific stages VERIFIED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brats_uncertainty.verification import provenance_checks as pc
from brats_uncertainty.verification.model import FAIL, Check, Stage, expect
from brats_uncertainty.verification.verify import Lineage, VerificationResult, verify_scientific

JOBS = {
    "JOB-02": ("A", 0),
    "JOB-03": ("A", 1),
    "JOB-04": ("A", 2),
    "JOB-05": ("B", 0),
    "JOB-06": ("B", 1),
    "JOB-07": ("B", 2),
}


def _sha(path: Path) -> str | None:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def build_provenance(main_repo: Path, work_dir: Path) -> tuple[list[Stage], Lineage]:
    from brats_uncertainty.compute.jobs import read_manifest
    from brats_uncertainty.data.manifest_doc import load_case_manifest
    from brats_uncertainty.data.records import read_acquisition_record, read_metadata_record
    from brats_uncertainty.evaluation.ledger import LEDGER_RELPATH, read_ledger
    from brats_uncertainty.evaluation.status import load_status
    from brats_uncertainty.models.nnunet import (
        MAIN_EXPERIMENT_ID,
        RunSpec,
        run_namespace,
        trainer_for,
    )
    from brats_uncertainty.orchestration.steps import Context, crosswalk_rows, load_master_config
    from brats_uncertainty.orchestration.study_steps import AFRICA_RECORD, planned_epochs
    from brats_uncertainty.protocol import load_protocol
    from brats_uncertainty.splitting.split import PROTOCOL_SPLIT_SEED

    ctx = Context(
        repo_root=main_repo,
        work_dir=work_dir,
        state_dir=work_dir / "state",
        cfg=load_master_config(main_repo),
        environ={},
        ops=None,  # type: ignore[arg-type]
    )
    rec = ctx.records
    b5 = json.loads((rec / "B5_manifest.json").read_text(encoding="utf-8"))
    b3, b4 = read_metadata_record(rec / "B3.json"), read_metadata_record(rec / "B4.json")
    rows = crosswalk_rows(ctx)
    stages: list[Stage] = []
    stages.append(
        pc.check_data(
            training_root=ctx.training_root(),
            manifest=b5,
            inventory=read_acquisition_record(rec / "B2.json").inventory,
            data_root_reference=ctx.cfg["acquisition"]["training_set"],
            metadata_files={
                "B3": (ctx.metadata_path("B3"), b3.file.sha256),
                "B4": (ctx.metadata_path("B4"), b4.file.sha256),
            },
            crosswalk_case_ids=[r.case_id for r in rows],
        )
    )
    manifest = load_case_manifest(rec / "B5_manifest.json")
    labels = {e.case_id: ctx.training_root() / e.label.relpath for e in manifest.entries if e.label}
    spec = load_protocol(main_repo)
    stages.append(
        pc.check_split(
            site_of_case={r.case_id: r.site_id for r in rows},
            groups_csv=ctx.splits / "patient_groups_dev.csv",
            split_csv=ctx.splits / "split_all.csv",
            split_hashes=json.loads((ctx.splits / "split_hashes.json").read_text(encoding="utf-8")),
            verified_groups=spec.verified_groups,
            label_features=pc.label_features_nibabel(labels),
            split_seed=PROTOCOL_SPLIT_SEED,
        )
    )
    epochs = planned_epochs(ctx)
    results_root = work_dir / "nnunet_results"
    run_dirs = {
        j: run_namespace(results_root, MAIN_EXPERIMENT_ID, RunSpec(a, s))
        for j, (a, s) in JOBS.items()
    }
    manifests = {j: read_manifest(d) for j, d in run_dirs.items()}
    split_sha = str(
        json.loads((ctx.splits / "split_hashes.json").read_text(encoding="utf-8"))[
            "split_all_csv_sha256"
        ]
    )
    stages.append(
        pc.check_runs(
            run_manifests=manifests,
            run_dirs=run_dirs,
            expected={j: (a, s, trainer_for(a, epochs)) for j, (a, s) in JOBS.items()},
            manifest_sha256=str(b5["manifest_sha256"]),
            split_sha256=split_sha,
        )
    )
    stages.append(
        pc.check_checkpoints(
            {
                j: (
                    run_dirs[j] / str((m or {}).get("checkpoint", {}).get("path", "")),
                    trainer_for(JOBS[j][0], epochs),
                    epochs,
                )
                for j, m in manifests.items()
            }
        )
    )
    status = load_status(main_repo)
    ledger = read_ledger(main_repo / LEDGER_RELPATH)
    ext = Stage("EXTERNAL", "External sets: population, grouping, no contamination, evaluated once")
    units = main_repo / "results/MAIN/units"
    split_rows = pc._read_csv(ctx.splits / "split_all.csv")
    dev_eval = {r["case_id"] for r in split_rows if r["partition"] in ("train", "validation")}
    hoi_units = units / "units_upenn_hoi_armB_C5.csv"
    if hoi_units.is_file():
        hoi_cases = {r["case_id"] for r in pc._read_csv(hoi_units)}
        site1 = {r.case_id for r in rows if r.site_id == "1"}
        ext.add(
            expect(
                "UPenn HOI population = the 511 site-1 cases",
                hoi_cases == site1 and len(site1) == 511,
            )
        )
        hoi_groups = {r["case_id"] for r in pc._read_csv(ctx.splits / "patient_groups_hoi.csv")}
        ext.add(expect("HOI patient groups cover exactly the HOI cases", hoi_groups == hoi_cases))
        ext.add(expect("gate C4 closed", status.gate("C4").is_closed))
        ext.add(expect("no HOI case in training/validation", not (hoi_cases & dev_eval)))
        ext.add(
            expect(
                "HOI evaluated once per arm (ledger, SR4)",
                sorted(e.arm for e in ledger if e.dataset == "upenn_hoi") in (["A", "B"], ["B"]),
            )
        )
    afr_units = units / "units_brats_africa_armB_C5.csv"
    if afr_units.is_file():
        rec_c = json.loads((main_repo / AFRICA_RECORD).read_text(encoding="utf-8"))
        cases = {r["case_id"] for r in pc._read_csv(afr_units)}
        ext.add(
            expect(
                "BraTS-Africa gates C1-C3 closed",
                all(status.gate(g).is_closed for g in ("C1", "C2", "C3")),
            )
        )
        ext.add(
            expect(
                "BraTS-Africa cases = the frozen C3 eligible list",
                cases == set(rec_c["C3_eligible"]),
            )
        )
        ext.add(
            expect(
                "no BraTS-Africa image identical to a BraTS 2021 image",
                not rec_c.get("identical_image_hash_overlap_with_brats2021"),
            )
        )
        ext.add(
            expect(
                "BraTS-Africa evaluated once per arm (ledger, SR4)",
                sorted(e.arm for e in ledger if e.dataset == "brats_africa") in (["A", "B"], ["B"]),
            )
        )
    if not ext.checks:
        ext = pc.not_applicable(
            "EXTERNAL", ext.title, "no external set has been evaluated; none is published"
        )
    stages.append(ext.finish())
    lineage = Lineage(
        dataset_manifest_hash=str(b5["manifest_sha256"]),
        crosswalk_hash=b3.file.sha256,
        metadata_hash=b4.file.sha256,
        split_hash=split_sha,
        grouping_hash=_sha(ctx.splits / "patient_groups_dev.csv"),
        hoi_grouping_hash=_sha(ctx.splits / "patient_groups_hoi.csv"),
        run_ids={
            a: [run_dirs[j].name for j, (aa, _) in JOBS.items() if aa == a] for a in ("A", "B")
        },
        environment_hashes=[str(m.get("environment_hash")) for m in manifests.values() if m],
        protocol_sha256=str(spec.raw["protocol"]["sha256"]),
    )
    return stages, lineage


def verify_results_command(
    worktree: Path, main_repo: Path, work_dir: Path, analysis_out: Path, out_dir: Path
) -> VerificationResult:
    from brats_uncertainty.evaluation.guards import require_action
    from brats_uncertainty.study.commands import analyze_study_command

    require_action("evaluate_internal_test", worktree, status_root=main_repo)
    try:
        stages, lineage = build_provenance(main_repo, work_dir)
    except (OSError, KeyError, ValueError) as exc:  # a missing record is a failed verification
        stages = [
            Stage(
                "DATA",
                "Provenance inputs",
                [Check("provenance inputs readable", FAIL, detail=str(exc))],
            ).finish()
        ]
        lineage = Lineage()

    def rerun(out: Path) -> None:
        analyze_study_command(
            worktree,
            main_repo / "results/MAIN/units",
            main_repo / "results/MAIN/c5_frozen.json",
            out,
            main_repo,
            work_dir,
        )

    return verify_scientific(
        units_dir=main_repo / "results/MAIN/units",
        frozen_path=main_repo / "results/MAIN/c5_frozen.json",
        analysis_out=analysis_out,
        out_dir=out_dir,
        provenance_stages=stages,
        lineage=lineage,
        rerun=rerun,
        rerun_dir=out_dir / "rerun_analysis",
    )


def save_result(result: VerificationResult, path: Path) -> None:
    from dataclasses import asdict

    path.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {
        "scientific_status": result.scientific_status,
        "stages": {k: asdict(v) for k, v in result.stages.items()},
        "result_index": result.result_index,
        "records": result.records,
        "rerun": result.rerun,
        "analysis_commit": result.analysis_commit,
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_result(path: Path) -> VerificationResult:
    from brats_uncertainty.verification.model import Check

    body = json.loads(path.read_text(encoding="utf-8"))
    stages = {
        k: Stage(v["id"], v["title"], [Check(**c) for c in v["checks"]], v["status"], v["detail"])
        for k, v in body["stages"].items()
    }
    return VerificationResult(
        stages, body["result_index"], body["records"], body["rerun"], body["analysis_commit"]
    )
