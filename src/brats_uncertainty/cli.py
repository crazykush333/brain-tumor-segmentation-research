"""Command-line interface: ``brats-uncertainty <command>``.

Safe commands (no data access): ``verify-protocol``, ``status``, ``check-repo``,
``check-action``, ``export-site-data``. Data-stage commands are gated and fail
with a ResearchGateError until their protocol gates are closed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from brats_uncertainty import PROTOCOL_VERSION, __version__
from brats_uncertainty.errors import BratsUncertaintyError, ConfigError
from brats_uncertainty.utils.paths import find_repo_root


def _cmd_verify_protocol(root: Path, _: argparse.Namespace) -> int:
    from brats_uncertainty.protocol import load_protocol

    spec = load_protocol(root)
    print(
        f"protocol {spec.version} OK: {spec.raw['protocol']['file']} "
        f"sha256={spec.raw['protocol']['sha256']}"
    )
    return 0


def _cmd_status(root: Path, _: argparse.Namespace) -> int:
    from brats_uncertainty.evaluation.status import load_status

    st = load_status(root)
    print(st.headline)
    for g in st.gates.values():
        print(f"  {g.id:<4} {g.status:<13} {g.title}")
    return 0


def _cmd_check_repo(root: Path, _: argparse.Namespace) -> int:
    from brats_uncertainty.repo_checks import check_repository

    findings = check_repository(root)
    for f in findings:
        print(f"PROHIBITED: {f.path}: {f.problem}", file=sys.stderr)
    if not findings:
        print(
            "repository check passed: no prohibited files, secrets or protocol integrity problems"
        )
    return 1 if findings else 0


def _cmd_check_action(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.evaluation.guards import check_action

    unmet = check_action(args.action, root)
    if unmet:
        print(f"NOT AUTHORIZED: {args.action}; unmet: {', '.join(unmet)}")
        return 2
    print(f"authorized: {args.action}")
    return 0


def _cmd_export_site(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.results.site_export import export_site_data

    changed = export_site_data(root, check=args.check)
    if args.check:
        if changed:
            print(
                f"website data out of sync: {changed}. Run `brats-uncertainty export-site-data`.",
                file=sys.stderr,
            )
            return 1
        print("website data in sync")
    else:
        print(f"wrote: {changed or 'nothing (already up to date)'}")
    return 0


DATA_SUBDIRS = ("raw", "manifests", "derived", "cache")


def _cmd_init_data_dirs(root: Path, _: argparse.Namespace) -> int:
    """Create the git-ignored local data layout (safe: creates empty folders only)."""
    for sub in DATA_SUBDIRS:
        (root / "data" / sub).mkdir(parents=True, exist_ok=True)
    print(f"created (git-ignored): {', '.join(f'data/{s}/' for s in DATA_SUBDIRS)}")
    return 0


def _source(args: argparse.Namespace) -> Any:
    from brats_uncertainty.data.records import SourceInfo

    return SourceInfo(
        dataset=args.dataset,
        dataset_version=args.dataset_version,
        doi=args.doi,
        source_url=args.source_url,
        route=args.route,
    )


def _cmd_acquire(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.acquisition import (
        AcquisitionPlan,
        HttpsFileAdapter,
        LocalImportAdapter,
        SyntheticFixtureAdapter,
        stage_acquire,
    )

    adapter: Any
    if args.adapter == "synthetic-fixture":
        adapter = SyntheticFixtureAdapter(root, n_cases=args.n_cases)
    elif args.adapter == "local-import":
        if not args.delivered:
            raise ConfigError("--delivered is required for the local-import adapter")
        adapter = LocalImportAdapter(_source(args), Path(args.delivered))
    else:
        urls = dict(item.split("=", 1) for item in (args.url or []))
        if not urls:
            raise ConfigError("--url REL=https://... is required for the https-file adapter")
        adapter = HttpsFileAdapter(_source(args), urls)
    result = stage_acquire(
        root,
        adapter,
        storage_root=Path(args.storage_root),
        out_record=Path(args.out),
        acquired_by=args.acquired_by,
        execute=args.execute,
        storage_label=args.storage_label,
    )
    if isinstance(result, AcquisitionPlan):
        print(result.describe())
        print(
            "No files were acquired (dry run). Real execution needs --execute AND B1 authorization."
        )
    else:
        print(
            f"B2 record: {args.out} ({len(result.inventory)} files, synthetic={result.synthetic})"
        )
    return 0


def _cmd_hash_metadata(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.stages import stage_hash_metadata

    rec = stage_hash_metadata(
        root,
        args.gate,
        Path(args.file),
        source_url=args.source_url,
        doi=args.doi,
        out=Path(args.out),
        path_reference=args.path_reference,
        synthetic=args.synthetic,
    )
    print(
        f"{args.gate} record written: {args.out} "
        f"({rec.file.file_name}, {rec.file.size_bytes} bytes, "
        f"sha256={rec.file.sha256}, synthetic={rec.synthetic})"
    )
    return 0


def _cmd_validate_data(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.stages import stage_validate_data
    from brats_uncertainty.utils.io import write_json

    report = stage_validate_data(
        root,
        Path(args.dataset_config),
        Path(args.data_root),
        deep=not args.quick,
        synthetic=args.synthetic,
    )
    if args.out:
        write_json(args.out, report.to_dict())
    print(
        f"integrity: {report.n_case_dirs} case dirs, {report.n_complete_cases} complete, "
        f"{len(report.errors)} error(s), {len(report.issues) - len(report.errors)} warning(s)"
    )
    return 0 if report.ok else 1


def _cmd_build_manifest(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.stages import stage_build_manifest

    doc = stage_build_manifest(
        root,
        Path(args.dataset_config),
        Path(args.data_root),
        Path(args.acquisition_record),
        Path(args.out),
        out_csv=Path(args.out_csv) if args.out_csv else None,
        metadata_files=[Path(m) for m in args.metadata_file or []],
        metadata_records=[Path(r) for r in args.metadata_record or []],
        data_root_reference=args.data_root_reference,
        synthetic=args.synthetic,
    )
    print(f"B5 raw manifest: {doc['summary']} manifest_sha256={doc['manifest_sha256']}")
    return 0


def _cmd_verify_checksums(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.stages import stage_verify_checksums

    report = stage_verify_checksums(
        root, Path(args.sums), Path(args.root), prefix=args.select, out=Path(args.out)
    )
    print(
        f"provider checksums OK: {report.n_verified}/{report.n_selected} selected files verified "
        f"({', '.join(report.algorithms)}); {report.n_not_selected} listed entries not selected"
    )
    return 0


def _cmd_compute_preflight(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.compute.probe import compute_preflight
    from brats_uncertainty.utils.io import write_json

    report = compute_preflight(
        root,
        work_dir=Path(args.work_dir) if args.work_dir else None,
        job=args.job,
        offline=args.offline,
    )
    print(report.describe())
    if args.json:
        write_json(args.json, report.to_dict(), overwrite=True)
    return 0 if report.status != "NOT_READY" else 1


def _cmd_job_run(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.compute.jobs import load_jobs, run_training_job

    job = load_jobs(root)[args.job]
    if job.kind != "training":
        raise ConfigError(
            f"{args.job} ({job.kind}) runs as notebook/CLI steps; see docs/reproducibility/"
            "REMOTE_COMPUTE.md"
        )
    record = run_training_job(
        root,
        job,
        dataset_id=args.dataset_id,
        results_root=Path(args.results_root),
        dataset_provenance=Path(args.dataset_provenance),
        manifest_sha256=args.manifest_sha256,
        split_sha256=args.split_sha256,
        resume=args.resume,
        restart_without_checkpoint=args.restart_without_checkpoint,
    )
    print(f"{args.job}: {record['status']} after {len(record['attempts'])} attempt(s)")
    return 0 if record["status"] == "COMPLETED" else 1


def _cmd_job_invalidate(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.compute.jobs import invalidate_run

    m = invalidate_run(Path(args.run_dir), args.reason)
    print(f"{Path(args.run_dir).name}: {m['status']} ({m['invalidation_reason']})")
    return 0


def _cmd_export_artifacts(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.results.export import export_public_artifacts

    rep = export_public_artifacts(Path(args.source), Path(args.dest))
    print(f"copied {len(rep.copied)} public-safe file(s); skipped {len(rep.skipped)}")
    for s in rep.skipped:
        print(f"  skipped (never copied): {s}")
    return 0


def _cmd_validate_metrics(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.results.metric_records import validate_metric_file

    for f in args.files:
        recs = validate_metric_file(Path(f))
        print(f"{f}: {len(recs)} valid metric record(s)")
    return 0


def _cmd_build_nnunet_dataset(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.nnunet_dataset import write_nnunet_dataset
    from brats_uncertainty.data.schema import load_schema

    case_ids = None
    if args.case_ids:
        case_ids = [
            ln.strip()
            for ln in Path(args.case_ids).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    res = write_nnunet_dataset(
        root,
        Path(args.training_root),
        load_schema(Path(args.dataset_config)),
        Path(args.out),
        dataset_id=args.dataset_id,
        dataset_name=args.dataset_name,
        case_ids=case_ids,
        gate_action=args.gate_action,
        training_root_reference=args.training_root_reference,
    )
    print(
        f"nnU-Net raw dataset: {res.n_cases} cases; provenance sha256={res.provenance_sha256}; "
        f"conversion config sha256={res.conversion_config_sha256}"
    )
    return 0


def _cmd_b8_a4_dryrun(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.grouping.a4_dryrun import run

    r = run(root, Path(args.crosswalk), Path(args.ucsf_metadata), root / args.out)
    print({k: r[k] for k in ("decisions", "rules", "n_groups", "largest_group", "accepted")})
    print("independent reconciliation:", r["independent_reconciliation"])
    return 0 if r["accepted"] else 1


def _cmd_a5_identity_sweep(root: Path, args: argparse.Namespace) -> int:
    import json as _json

    from brats_uncertainty.verification.identity_sweep import run

    r = run(
        root,
        Path(args.crosswalk),
        Path(args.ucsf_metadata),
        Path(args.not_previously_in_tcia),
        Path(args.gc_manifest),
    )
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"checked {r['n_checked_without_identity']}; newly resolved {r['n_newly_resolved']}; "
        f"remaining unresolved {r['n_remaining_unresolved']}"
    )
    return 0


def _cmd_audit_split(root: Path, args: argparse.Namespace) -> int:
    import json as _json

    from brats_uncertainty.verification.split_audit import audit, render_report

    result = audit(root)
    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.report:
        rep = root / args.report
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text(render_report(result), encoding="utf-8", newline="\n")
    for k, ok in result["checks"].items():
        print(f"{'PASS' if ok else 'FAIL'}  {k}")
    print("B8-B12 split audit:", "PASSED" if result["passed"] else "FAILED")
    return 0 if result["passed"] else 1


def _cmd_verify_inventory(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.records import read_acquisition_record, verify_inventory

    rec = read_acquisition_record(Path(args.record))
    diff = verify_inventory(rec.inventory, Path(args.root))
    bad = {k: v for k, v in diff.items() if v}
    if bad:
        print(f"MISMATCH against the B2 inventory: { {k: len(v) for k, v in bad.items()} }")
        for k, v in bad.items():
            print(f"  {k}: {v[:5]}")
        return 1
    print(f"tree identical to the B2 inventory ({len(rec.inventory)} files)")
    return 0


def _cmd_storage_preflight(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.preflight import GIB, storage_preflight

    result = storage_preflight(
        int(args.selected_gib * GIB),
        delivery_dir=Path(args.delivery_dir),
        storage_dir=Path(args.storage_dir) if args.storage_dir else None,
        margin=args.margin,
        reserve_bytes=int(args.reserve_gib * GIB),
        metadata_bytes=int(args.metadata_mib * (1 << 20)),
    )
    print(result.describe())
    return 0 if result.ok else 1


def _cmd_derive_counts(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.data.stages import stage_derive_counts

    rec = stage_derive_counts(
        root,
        Path(args.crosswalk),
        Path(args.b3_record),
        Path(args.dataset_config),
        Path(args.out),
        synthetic=args.synthetic,
    )
    print(f"B6 record written: {args.out} status={rec.status} counts={rec.counts}")
    return 0


def _cmd_count_targets(root: Path, __: argparse.Namespace) -> int:
    from brats_uncertainty.evaluation.status import load_status
    from brats_uncertainty.results.site_export import build_count_block

    t = build_count_block(root, load_status(root).raw)
    print(f"{t['status']}: {t['label']}")
    print(f"B6 verification state: {t['verification']}")
    for k, v in t["targets"].items():
        print(f"  target {k}: {v}")
    for k, v in (t.get("counts") or {}).items():
        print(f"  verified {k}: {v}")
    return 0


def _cmd_gate_transition(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.evaluation.transitions import write_transition

    changes = write_transition(
        root,
        args.gate,
        args.new_status,
        evidence=args.evidence,
        on=args.on,
        approved_route=args.approved_route,
        apply=args.apply,
    )
    print(("APPLIED" if args.apply else "DRY RUN (use --apply to write)") + ":")
    for c in changes:
        print(f"  {c}")
    return 0


def _cmd_master_run(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.orchestration.entry import master_run

    report, _ = master_run(
        root,
        work_dir=args.work_dir,
        state_dir=args.state_dir,
        resume=args.resume,
        commit=args.commit,
        push=args.push,
        offline=args.offline,
        retry=args.retry or [],
        approve_restart=args.approve_restart or [],
        until=args.until,
        plan_only=args.plan,
    )
    print(report.describe())
    if args.plan:
        return 0
    return 2 if report.stops else 0


def _cmd_verify_results(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.verification.run import save_result, verify_results_command

    res = verify_results_command(
        root, Path(args.main_repo), Path(args.work_dir), Path(args.analysis_out), Path(args.out)
    )
    save_result(res, Path(args.out) / "verification_result.json")
    print(f"scientific verification: {res.scientific_status}")
    for sid, st in res.stages.items():
        print(f"  {sid:<16} {st.status}")
    return 0 if res.scientific_status == "VERIFIED" else 1


def _cmd_demo(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.demo import generate_demo

    s = generate_demo(Path(args.out), repo_root=root, seed=args.seed)
    print(f"synthetic demonstration written to {args.out} ({len(s['files'])} files): {s['label']}")
    return 0


def _cmd_evaluate_set(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.study.commands import evaluate_set_command

    out = evaluate_set_command(
        root, args.dataset, Path(args.work_dir), Path(args.out_dir), Path(args.main_repo)
    )
    print(f"{args.dataset}: {', '.join(f'{k}={v.name}' for k, v in out.items())}")
    return 0


def _cmd_analyze_study(root: Path, args: argparse.Namespace) -> int:
    from brats_uncertainty.study.commands import analyze_study_command

    res = analyze_study_command(
        root,
        Path(args.units_dir),
        Path(args.frozen),
        Path(args.out_dir),
        Path(args.main_repo),
        Path(args.work_dir),
    )
    print(f"wrote {len(res['written'])} output(s); families complete: {res['families_complete']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brats-uncertainty", description=__doc__)
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__} (protocol {PROTOCOL_VERSION})",
    )
    p.add_argument("--repo-root", default=None, help="repository root (default: auto-detect)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("verify-protocol", help="verify the frozen protocol hash").set_defaults(
        func=_cmd_verify_protocol
    )
    sub.add_parser("status", help="print project status and gates").set_defaults(func=_cmd_status)
    sub.add_parser("check-repo", help="scan for prohibited files and secrets").set_defaults(
        func=_cmd_check_repo
    )
    ca = sub.add_parser("check-action", help="check whether a gated action is authorized")
    ca.add_argument("action")
    ca.set_defaults(func=_cmd_check_action)
    ex = sub.add_parser("export-site-data", help="export website/data JSON from sources of truth")
    ex.add_argument(
        "--check", action="store_true", help="only verify the committed files are in sync"
    )
    ex.set_defaults(func=_cmd_export_site)
    sub.add_parser(
        "init-data-dirs", help="create the git-ignored local data/ layout (no data)"
    ).set_defaults(func=_cmd_init_data_dirs)
    src_help = "as shown on the official source page"
    aq = sub.add_parser("acquire", help="B2 acquisition (dry run by default; real runs gated)")
    aq.add_argument(
        "--adapter", required=True, choices=["local-import", "https-file", "synthetic-fixture"]
    )
    aq.add_argument("--delivered", help="local-import: operator-delivered file or folder")
    aq.add_argument("--url", action="append", help="https-file: REL=https://... (repeatable)")
    aq.add_argument("--n-cases", type=int, default=3, help="synthetic-fixture: number of cases")
    aq.add_argument("--dataset", default="RSNA-ASNR-MICCAI-BraTS-2021")
    aq.add_argument("--dataset-version", default="unset", help=src_help)
    aq.add_argument("--doi", default="10.7937/jc8x-9874")
    aq.add_argument(
        "--source-url",
        default="https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/",
    )
    aq.add_argument("--route", default="unset", help="must equal the B1-approved route")
    aq.add_argument("--storage-root", required=True)
    aq.add_argument("--storage-label", default=None, help="logical label (no absolute paths)")
    aq.add_argument("--acquired-by", required=True)
    aq.add_argument("--out", required=True, help="B2 record path")
    aq.add_argument("--execute", action="store_true", help="actually acquire (default: dry run)")
    aq.set_defaults(func=_cmd_acquire)
    hm = sub.add_parser("hash-metadata", help="B3/B4: exact SHA-256 of a metadata file (gated)")
    hm.add_argument("--gate", required=True, choices=["B3", "B4"])
    hm.add_argument("--file", required=True)
    hm.add_argument("--source-url", required=True)
    hm.add_argument("--doi", required=True)
    hm.add_argument("--path-reference", default=None, help="logical/relative location label")
    hm.add_argument("--out", required=True)
    hm.add_argument("--synthetic", action="store_true", help="SYNTHETIC_TEST_DATA inputs only")
    hm.set_defaults(func=_cmd_hash_metadata)
    vd = sub.add_parser("validate-data", help="integrity audit of acquired data (gated)")
    vd.add_argument("--dataset-config", required=True)
    vd.add_argument("--data-root", required=True)
    vd.add_argument("--quick", action="store_true", help="headers only; skip full gzip CRC read")
    vd.add_argument("--out", default=None)
    vd.add_argument("--synthetic", action="store_true", help="SYNTHETIC_TEST_DATA inputs only")
    vd.set_defaults(func=_cmd_validate_data)
    bm = sub.add_parser("build-manifest", help="B5: integrity audit + raw data manifest (gated)")
    bm.add_argument("--dataset-config", required=True)
    bm.add_argument("--data-root", required=True)
    bm.add_argument("--acquisition-record", required=True, help="B2 record")
    bm.add_argument("--metadata-file", action="append", help="crosswalk / UCSF file (repeatable)")
    bm.add_argument("--metadata-record", action="append", help="B3/B4 record of each metadata file")
    bm.add_argument("--out", required=True, help="manifest JSON")
    bm.add_argument("--out-csv", default=None, help="manifest file table as CSV")
    bm.add_argument(
        "--data-root-reference",
        default=None,
        help="data root's path inside the B2 storage, e.g. "
        "RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet (required for real B5)",
    )
    bm.add_argument("--synthetic", action="store_true", help="SYNTHETIC_TEST_DATA inputs only")
    bm.set_defaults(func=_cmd_build_manifest)
    vc = sub.add_parser(
        "verify-checksums", help="B2: verify delivered files against the provider .sums (gated)"
    )
    vc.add_argument("--sums", required=True, help="provider checksum file, exactly as delivered")
    vc.add_argument("--root", required=True, help="directory the listed paths are relative to")
    vc.add_argument(
        "--select",
        required=True,
        help="listed prefix that was downloaded, e.g. "
        "RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet",
    )
    vc.add_argument("--out", required=True, help="verification report JSON (never overwritten)")
    vc.set_defaults(func=_cmd_verify_checksums)
    sp = sub.add_parser(
        "storage-preflight", help="B2: is there disk space for the download and import copy?"
    )
    sp.add_argument(
        "--selected-gib", type=float, required=True, help="selection size shown by the client"
    )
    sp.add_argument("--delivery-dir", required=True, help="where the official download goes")
    sp.add_argument("--storage-dir", default=None, help="local-import storage root")
    sp.add_argument("--margin", type=float, default=0.10, help="safety margin (fraction)")
    sp.add_argument("--reserve-gib", type=float, default=10.0, help="free space left per drive")
    sp.add_argument(
        "--metadata-mib", type=float, default=16.0, help="allowance for the B3/B4 metadata files"
    )
    sp.set_defaults(func=_cmd_storage_preflight)
    cp = sub.add_parser(
        "compute-preflight",
        help="probe this environment (GPU/CUDA/RAM/disk/packages/internet) and classify it",
    )
    cp.add_argument("--job", default=None, help="check against one job, e.g. JOB-01 or JOB-02")
    cp.add_argument("--work-dir", default=None, help="where data/checkpoints would be written")
    cp.add_argument("--offline", action="store_true", help="skip the HEAD-request internet check")
    cp.add_argument("--json", default=None, help="also write the report as JSON")
    cp.set_defaults(func=_cmd_compute_preflight)
    jr = sub.add_parser("job-run", help="run/resume one training job (gated: train_main)")
    jr.add_argument("job", help="JOB-02 ... JOB-07")
    jr.add_argument("--dataset-id", type=int, required=True, help="nnU-Net dataset id")
    jr.add_argument(
        "--results-root", required=True, help="parent of <experiment>/arm_<a>_seed_<s> run dirs"
    )
    jr.add_argument(
        "--dataset-provenance", required=True, help="conversion_provenance.json of the dataset"
    )
    jr.add_argument("--manifest-sha256", required=True, help="B5 manifest_sha256")
    jr.add_argument("--split-sha256", required=True, help="B12 split hash")
    jr.add_argument(
        "--resume",
        action="store_true",
        help="continue an earlier attempt from its own verified latest checkpoint",
    )
    jr.add_argument(
        "--restart-without-checkpoint",
        action="store_true",
        help="explicitly restart an earlier attempt that left no checkpoint (recorded)",
    )
    jr.set_defaults(func=_cmd_job_run)
    ji = sub.add_parser("job-invalidate", help="mark a run INVALIDATED (never resumed again)")
    ji.add_argument("run_dir")
    ji.add_argument("--reason", required=True)
    ji.set_defaults(func=_cmd_job_invalidate)
    nd = sub.add_parser(
        "build-nnunet-dataset",
        help="official nested BraTS tree -> nnU-Net raw dataset + provenance (gated)",
    )
    nd.add_argument("--training-root", required=True, help=".../BraTS2021_TrainingSet")
    nd.add_argument("--dataset-config", default="configs/dataset/brats2021.yaml")
    nd.add_argument("--out", required=True, help="nnUNet_raw/Dataset<ID>_<Name> (must not exist)")
    nd.add_argument("--dataset-id", type=int, required=True)
    nd.add_argument("--dataset-name", required=True)
    nd.add_argument("--case-ids", default=None, help="file with one case ID per line (split)")
    nd.add_argument("--gate-action", default="train_main", choices=["train_main", "run_exp001"])
    nd.add_argument("--training-root-reference", default=None, help="logical source reference")
    nd.set_defaults(func=_cmd_build_nnunet_dataset)
    ea = sub.add_parser(
        "export-artifacts", help="copy public-safe artifacts (never data/checkpoints) to a folder"
    )
    ea.add_argument("--source", required=True, help="remote export folder")
    ea.add_argument("--dest", required=True, help="destination, e.g. results/<EXPERIMENT>")
    ea.set_defaults(func=_cmd_export_artifacts)
    vm = sub.add_parser("validate-metrics", help="validate *.metrics.json result files")
    vm.add_argument("files", nargs="+")
    vm.set_defaults(func=_cmd_validate_metrics)
    a4 = sub.add_parser(
        "b8-a4-dryrun", help="pre-split dry run of the v1.0-A4 metadata linkage (no gate change)"
    )
    a4.add_argument("--crosswalk", required=True, help="BraTS2021_MappingToTCIA.xlsx (B3 hash)")
    a4.add_argument("--ucsf-metadata", required=True, help="UCSF-PDGM-metadata_v5.csv (B4 hash)")
    a4.add_argument("--out", default="docs/data/records/B8_A4_dryrun")
    a4.set_defaults(func=_cmd_b8_a4_dryrun)
    sw = sub.add_parser(
        "a5-identity-sweep", help="final A5 metadata identity-recovery sweep (no gate change)"
    )
    sw.add_argument("--crosswalk", required=True, help="BraTS2021_MappingToTCIA.xlsx (B3 hash)")
    sw.add_argument("--ucsf-metadata", required=True, help="UCSF-PDGM-metadata_v5.csv (B4 hash)")
    sw.add_argument("--not-previously-in-tcia", required=True, help="NotPreviouslyInTCIA.csv")
    sw.add_argument(
        "--gc-manifest", required=True, help="GC_manifest_RSNA-ASNR-MICCAI-BRATS-2021_sources.csv"
    )
    sw.add_argument("--out", default="docs/data/records/B8_A5_identity_sweep.json")
    sw.set_defaults(func=_cmd_a5_identity_sweep)
    au = sub.add_parser(
        "audit-split", help="independent B8-B12 leakage/provenance audit (committed IDs only)"
    )
    au.add_argument("--out", default="docs/research/execution/B8_B12_SUMMARY.json")
    au.add_argument("--report", default=None, help="also write the Markdown verdict here")
    au.set_defaults(func=_cmd_audit_split)
    vi = sub.add_parser(
        "verify-inventory", help="check a (re-)acquired tree against the committed B2 inventory"
    )
    vi.add_argument("--record", required=True, help="B2 acquisition record")
    vi.add_argument("--root", required=True, help="storage root of the re-acquired files")
    vi.set_defaults(func=_cmd_verify_inventory)
    dc = sub.add_parser("derive-counts", help="B6: counts from the hashed crosswalk (gated)")
    dc.add_argument("--crosswalk", required=True)
    dc.add_argument("--b3-record", required=True)
    dc.add_argument("--dataset-config", default="configs/dataset/brats2021.yaml")
    dc.add_argument("--out", required=True)
    dc.add_argument("--synthetic", action="store_true", help="SYNTHETIC_TEST_DATA inputs only")
    dc.set_defaults(func=_cmd_derive_counts)
    sub.add_parser(
        "count-targets", help="print the B6 protocol verification targets (EXPECTED_BY_PROTOCOL)"
    ).set_defaults(func=_cmd_count_targets)
    gt = sub.add_parser("gate-transition", help="owner: move a B gate (dry run unless --apply)")
    gt.add_argument("gate")
    gt.add_argument("new_status")
    gt.add_argument(
        "--evidence", default=None, help="committed evidence (PASSED/FAILED/BLOCKED, unblocking)"
    )
    gt.add_argument("--on", default=None, help="date YYYY-MM-DD (for PASSED)")
    gt.add_argument("--approved-route", default=None, help="B1 only: the approved data route")
    gt.add_argument("--apply", action="store_true")
    gt.set_defaults(func=_cmd_gate_transition)
    mr = sub.add_parser(
        "master-run",
        help="run the whole frozen protocol: every permitted gate/run, resumable; stops only "
        "at genuine blockers",
    )
    mr.add_argument("--work-dir", default=None, help="persistent private storage ($BRATS_WORK)")
    mr.add_argument("--state-dir", default=None, help="master state journal (default WORK/state)")
    mr.add_argument("--resume", action="store_true", help="continue from the existing state")
    mr.add_argument("--commit", action="store_true", help="commit milestones (allow-listed paths)")
    mr.add_argument("--push", action="store_true", help="push milestone commits (never forced)")
    mr.add_argument("--offline", action="store_true", help="no network access")
    mr.add_argument("--retry", action="append", help="owner: retry a FAILED step (repeatable)")
    mr.add_argument(
        "--approve-restart",
        action="append",
        help="owner: allow JOB-0x without a checkpoint to restart from scratch (recorded)",
    )
    mr.add_argument("--until", default=None, help="stop after this step id")
    mr.add_argument("--plan", action="store_true", help="show step statuses; execute nothing")
    mr.set_defaults(func=_cmd_master_run)
    vr = sub.add_parser(
        "verify-results", help="tagged: independent verification of the real analysis"
    )
    vr.add_argument("--main-repo", required=True)
    vr.add_argument("--work-dir", required=True)
    vr.add_argument("--analysis-out", required=True)
    vr.add_argument("--out", required=True)
    vr.set_defaults(func=_cmd_verify_results)
    dm = sub.add_parser(
        "demo", help="synthetic pipeline demonstration (NOT results); only results/demo/"
    )
    dm.add_argument("--out", default="results/demo")
    dm.add_argument("--seed", type=int, default=20261004)
    dm.set_defaults(func=_cmd_demo)
    es = sub.add_parser(
        "evaluate-set", help="tagged: evaluate one test/external set once (eval-v1 worktree)"
    )
    es.add_argument(
        "--dataset", required=True, choices=["internal_test", "upenn_hoi", "brats_africa"]
    )
    es.add_argument("--work-dir", required=True)
    es.add_argument("--out-dir", required=True)
    es.add_argument("--main-repo", required=True, help="live checkout (gate records, ledger)")
    es.set_defaults(func=_cmd_evaluate_set)
    an = sub.add_parser("analyze-study", help="tagged: all pre-registered analyses from unit files")
    an.add_argument("--units-dir", required=True)
    an.add_argument("--frozen", required=True, help="C5 frozen record")
    an.add_argument("--out-dir", required=True)
    an.add_argument("--main-repo", required=True)
    an.add_argument("--work-dir", required=True)
    an.set_defaults(func=_cmd_analyze_study)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.repo_root) if args.repo_root else find_repo_root()
        return int(args.func(root, args))
    except BratsUncertaintyError as exc:
        print(f"ERROR [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
