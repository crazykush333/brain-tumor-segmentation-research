"""Gated execution stages for the data gates B3-B6 (B2 lives in ``data.acquisition``).

Every stage runs in exactly one explicit mode:

- **real** (default): calls ``require_action`` for its gate, which needs the
  prerequisite gates PASSED and the stage's own gate AUTHORIZED/RUNNING in
  docs/project_status.yaml. It refuses inputs from a SYNTHETIC_TEST_DATA tree.
- **synthetic** (``synthetic=True``): no gate check, but every input must be a
  generator-listed, unmodified file of a SYNTHETIC_TEST_DATA tree outside the
  repository. Outputs must be written outside the repository, and records
  carry ``synthetic: true``, so they can never close a gate.

Stages write one provenance-stamped record and never overwrite an existing
one. Software never advances a gate: after reviewing a record, the owner moves
the gate with ``brats-uncertainty gate-transition`` and commits the
(non-synthetic) record as evidence.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from brats_uncertainty.data.checksums import (
    ChecksumReport,
    parse_checksum_file,
    verify_checksums,
)
from brats_uncertainty.data.crosswalk import (
    crosswalk_config_files,
    load_crosswalk_config,
    parse_rows,
    read_table_records,
    select_cohort,
)
from brats_uncertainty.data.integrity import IntegrityReport, validate_dataset_tree
from brats_uncertainty.data.manifest_doc import build_raw_manifest, manifest_to_csv
from brats_uncertainty.data.records import (
    B6_TARGETS,
    CROSSWALK_FILENAME,
    UCSF_METADATA_FILENAME,
    Clock,
    CountsRecord,
    HashedFile,
    InventoryEntry,
    MetadataFileRecord,
    make_stamp,
    read_acquisition_record,
    read_metadata_record,
    record_body,
    utc_now,
    write_record,
)
from brats_uncertainty.data.schema import load_schema
from brats_uncertainty.data.synthetic import find_marker_root, require_synthetic
from brats_uncertainty.errors import DataValidationError, ProvenanceError
from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.utils.hashing import sha256_bytes, sha256_file
from brats_uncertainty.utils.io import read_yaml, write_json
from brats_uncertainty.utils.paths import is_link, is_within

METADATA_GATES = {
    "B3": ("record_crosswalk_hash", "crosswalk", CROSSWALK_FILENAME),
    "B4": ("record_ucsf_metadata_hash", "ucsf_pdgm_metadata", UCSF_METADATA_FILENAME),
}


def _enter(
    repo_root: Path,
    action: str,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    synthetic: bool,
    clock: Clock = utc_now,
) -> None:
    """Mode check shared by all stages (see module docstring).

    Fails closed. Real mode checks the research gate FIRST (an unauthorized
    call always ends in ResearchGateError, whatever its inputs). Then:
    missing inputs, symbolic links, a non-default clock in real mode (no
    fabricated execution timestamps), synthetic inputs in real mode and
    unlisted inputs in synthetic mode are all rejected.
    """
    if not synthetic:
        if clock is not utc_now:
            raise ProvenanceError("a custom clock is only allowed for SYNTHETIC_TEST_DATA runs")
        require_action(action, repo_root)
    for p in inputs:
        if is_link(Path(p)):
            raise ProvenanceError(f"{Path(p).name}: symbolic links are not accepted as inputs")
        if not Path(p).exists():
            raise DataValidationError(f"input not found: {Path(p).name} (no source, no record)")
    if synthetic:
        require_synthetic([Path(p) for p in inputs], repo_root)
        for o in outputs:
            if is_within(o, repo_root):
                raise ProvenanceError(
                    "synthetic-mode outputs must be written outside the repository"
                )
        return
    for p in inputs:
        if find_marker_root(p) is not None:
            raise ProvenanceError(f"{Path(p).name}: SYNTHETIC_TEST_DATA input in real mode")


def _reference(path: Path, repo_root: Path, label: str | None, synthetic: bool) -> str:
    if label:
        return label
    if synthetic:
        return f"SYNTHETIC_TEST_DATA/{path.name}"
    if is_within(path, repo_root):
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    raise ProvenanceError(
        "inputs outside the repository need a logical path reference (never absolute)"
    )


def stage_hash_metadata(
    repo_root: Path,
    gate: str,
    path: Path,
    *,
    source_url: str,
    doi: str,
    out: Path,
    path_reference: str | None = None,
    synthetic: bool = False,
    require_clean_commit: bool = True,
    clock: Clock = utc_now,
) -> MetadataFileRecord:
    """Gates B3/B4: exact SHA-256 (and size) of the crosswalk or the UCSF-PDGM metadata file."""
    if gate not in METADATA_GATES:
        raise ValueError("gate must be B3 or B4")
    action, kind, filename = METADATA_GATES[gate]
    _enter(repo_root, action, [path], [out], synthetic, clock)
    if path.name != filename:
        raise DataValidationError(f"gate {gate} requires the file {filename!r}, got {path.name!r}")
    record = MetadataFileRecord(
        gate=gate,
        synthetic=synthetic,
        kind=kind,
        file=HashedFile.from_path(path),
        path_reference=_reference(path, repo_root, path_reference, synthetic),
        source_url=source_url,
        doi=doi,
        stamp=make_stamp(
            repo_root, require_clean_commit=require_clean_commit and not synthetic, clock=clock
        ),
    )
    write_record(out, record)
    return record


def stage_validate_data(
    repo_root: Path,
    dataset_config: Path,
    data_root: Path,
    *,
    deep: bool = True,
    synthetic: bool = False,
) -> IntegrityReport:
    """Integrity audit of acquired files (real mode requires B1 PASSED and B2 runnable/passed)."""
    _enter(repo_root, "validate_data", [data_root], [], synthetic)
    if any(is_link(p) for p in data_root.rglob("*")):
        raise ProvenanceError("symbolic links are not allowed in the data tree")
    cfg = read_yaml(dataset_config)
    return validate_dataset_tree(
        data_root,
        load_schema(dataset_config),
        require_labels=True,
        deep=deep,
        expected_shape=cfg.get("layout", {}).get("expected_shape"),
        expected_layout=cfg.get("layout", {}).get("tree"),
    )


def stage_verify_checksums(
    repo_root: Path,
    sums_file: Path,
    delivery_root: Path,
    *,
    prefix: str,
    out: Path,
    require_clean_commit: bool = True,
) -> ChecksumReport:
    """B2 support: verify the delivered files against the provider checksum file (real mode only).

    The checksum file is used exactly as delivered (see ``data.checksums``). The
    report is written once (never overwritten) and fails closed on any problem.
    """
    # part of B2 (before B2 can pass): allowed while B1 PASSED and B2 AUTHORIZED/RUNNING
    _enter(repo_root, "acquire_data", [sums_file, delivery_root], [out], False)
    report = verify_checksums(parse_checksum_file(sums_file), delivery_root, prefix=prefix)
    stamp = make_stamp(repo_root, require_clean_commit=require_clean_commit)
    write_json(
        out, {"kind": "provider_checksum_verification", **report.to_dict(), "stamp": asdict(stamp)}
    )
    if not report.ok:
        raise DataValidationError(
            f"provider checksum verification failed: {len(report.missing)} missing, "
            f"{len(report.mismatched)} mismatched, {len(report.unlisted)} unlisted, "
            f"{len(report.links)} links (report: {out.name})"
        )
    return report


def stage_build_manifest(
    repo_root: Path,
    dataset_config: Path,
    data_root: Path,
    acquisition_record: Path,
    out_json: Path,
    *,
    out_csv: Path | None = None,
    metadata_files: Sequence[Path] = (),
    metadata_records: Sequence[Path] = (),
    data_root_reference: str | None = None,
    synthetic: bool = False,
    require_clean_commit: bool = True,
    clock: Clock = utc_now,
) -> dict[str, Any]:
    """Gate B5: integrity audit, then the RAW DATA MANIFEST (JSON + optional CSV).

    Real mode requires the crosswalk and UCSF-PDGM files together with their
    B3 and B4 records; each file must still match its recorded SHA-256.

    ``data_root_reference`` is the data root's path inside the B2 storage (e.g.
    ``RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet``). Real mode requires it,
    and every manifested data file must then appear in the B2 inventory at
    ``<data_root_reference>/<relpath>`` with the same SHA-256 and size, so the
    manifest provably describes the acquired files.
    """
    outputs = [out_json, *([out_csv] if out_csv else [])]
    _enter(
        repo_root,
        "build_manifest",
        [data_root, *metadata_files],
        outputs,
        synthetic,
        clock,
    )
    acquisition = read_acquisition_record(acquisition_record)
    if acquisition.synthetic != synthetic:
        raise ProvenanceError("acquisition record synthetic flag does not match the stage mode")
    records = [read_metadata_record(r) for r in metadata_records]
    by_name = {r.file.file_name: r for r in records}
    if len(by_name) != len(records):
        raise DataValidationError("duplicate metadata records")
    pairs = []
    for m in metadata_files:
        if m.name not in by_name:
            raise DataValidationError(f"no B3/B4 record supplied for metadata file {m.name}")
        pairs.append((m, by_name.pop(m.name)))
    if by_name:
        raise DataValidationError(f"metadata records without files: {sorted(by_name)}")
    if not synthetic and sorted(r.gate for _, r in pairs) != ["B3", "B4"]:
        raise ProvenanceError(
            "real B5 requires the crosswalk and UCSF-PDGM files with B3 and B4 records"
        )
    if not synthetic and not data_root_reference:
        raise ProvenanceError(
            "real B5 requires --data-root-reference (the data root's path in the B2 storage)"
        )
    cfg = read_yaml(dataset_config)
    report = validate_dataset_tree(
        data_root,
        load_schema(dataset_config),
        deep=True,
        expected_layout=cfg.get("layout", {}).get("tree"),
    )
    if report.n_case_dirs == 0:
        raise DataValidationError("empty data tree: no case directories to manifest")
    if not report.ok:
        raise DataValidationError(
            f"integrity audit failed with {len(report.errors)} error(s); first: {report.errors[0]}"
        )
    stamp = make_stamp(
        repo_root,
        require_clean_commit=require_clean_commit and not synthetic,
        config_files=[dataset_config],
        clock=clock,
    )
    doc = build_raw_manifest(
        data_root,
        load_schema(dataset_config),
        acquisition,
        stamp,
        metadata=pairs,
        extra={
            "gate": "B5",
            "integrity": {
                "n_errors": 0,
                "n_warnings": len(report.issues),
                "n_cases": report.n_case_dirs,
            },
        },
        data_root_reference=data_root_reference,
    )
    if data_root_reference:
        _check_against_inventory(doc, acquisition.inventory, data_root_reference)
    if out_csv and out_csv.exists():
        raise FileExistsError(f"refusing to overwrite {out_csv.name}")
    write_json(out_json, doc)
    if out_csv:
        tmp = out_csv.with_suffix(out_csv.suffix + ".part")
        try:
            tmp.write_text(manifest_to_csv(doc), encoding="utf-8", newline="\n")
            tmp.replace(out_csv)  # atomic: no partial CSV on interruption
        finally:
            if tmp.exists():
                tmp.unlink()
    return doc


def _check_against_inventory(
    doc: dict[str, Any], inventory: Sequence[InventoryEntry], reference: str
) -> None:
    """Every manifested data file must be a B2-acquired file (same path below the reference)."""
    by_path = {e.relpath: e for e in inventory}
    for f in doc["files"]:
        if f["file_type"] == "metadata":
            continue  # bound to B3/B4 records instead
        key = f"{reference.strip('/')}/{f['relpath']}"
        e = by_path.get(key)
        if e is None or e.sha256 != f["sha256"] or e.size_bytes != f["size_bytes"]:
            raise ProvenanceError(
                f"{f['relpath']}: not in the B2 inventory at {key} (or hash/size differ); "
                "the manifest must describe the acquired files"
            )


def _ids_sha256(ids: Sequence[str]) -> str:
    return sha256_bytes(("\n".join(sorted(ids)) + "\n").encode("utf-8"))


def stage_derive_counts(
    repo_root: Path,
    crosswalk: Path,
    b3_record: Path,
    dataset_config: Path,
    out: Path,
    *,
    synthetic: bool = False,
    require_clean_commit: bool = True,
    clock: Clock = utc_now,
) -> CountsRecord:
    """Gate B6: derive 1,251 / 511 / 740 from the hashed crosswalk (fail closed).

    Counts are always computed from the file. The protocol targets are only
    compared against, never substituted. The crosswalk is re-hashed and must
    equal the B3 record. The record is written in both outcomes: on any
    mismatch it is FAILED_VERIFICATION with diagnostics, and the stage then
    raises (SR3: stop, do not modify the protocol).
    """
    _enter(repo_root, "derive_counts", [crosswalk], [out], synthetic, clock)
    b3 = read_metadata_record(b3_record)
    if b3.gate != "B3":
        raise ProvenanceError("b3_record is not a gate-B3 crosswalk record")
    if b3.synthetic != synthetic:
        raise ProvenanceError("B3 record synthetic flag does not match the stage mode")
    if crosswalk.name != CROSSWALK_FILENAME:
        raise DataValidationError(f"expected {CROSSWALK_FILENAME!r}, got {crosswalk.name!r}")
    b3_fp = str(record_body(b3)["record_fingerprint"])
    actual = sha256_file(crosswalk)
    hash_ok = actual == b3.file.sha256
    cfg: dict[str, Any] = read_yaml(dataset_config)
    cohorts_cfg = load_protocol(repo_root).raw["cohorts"]
    hoi_site = str(cohorts_cfg["hoi_site_id"])
    targets = {
        "total": int(cohorts_cfg["brats2021_training_total"]),
        "held_out_institution": int(cohorts_cfg["hoi_count"]),
        "development": int(cohorts_cfg["development_count_before_grouping"]),
    }
    if targets != B6_TARGETS:
        raise ProvenanceError("protocol mirror counts differ from the B6 targets")
    cw = load_crosswalk_config(dataset_config)
    rows = parse_rows(
        select_cohort(read_table_records(crosswalk, cw.get("sheet")), cw),
        cw["columns"],
        case_id_pattern=cfg["layout"]["case_id_pattern"],
    )
    hoi = [r.case_id for r in rows if r.site_id == hoi_site]
    dev = [r.case_id for r in rows if r.site_id != hoi_site]
    counts = {"total": len(rows), "held_out_institution": len(hoi), "development": len(dev)}
    checks = {k: counts[k] == v for k, v in targets.items()}
    diagnostics = [
        f"{k}: derived {counts[k]}, protocol target {v} (difference {counts[k] - v:+d})"
        for k, v in targets.items()
        if counts[k] != v
    ]
    if not hash_ok:
        diagnostics.insert(
            0, "crosswalk SHA-256 differs from the B3 record (file changed after B3)"
        )
    ok = hash_ok and all(checks.values())
    success = "SYNTHETIC_TEST_ONLY" if synthetic else "VERIFIED_FROM_SOURCE"
    record = CountsRecord(
        gate="B6",
        synthetic=synthetic,
        status=success if ok else "FAILED_VERIFICATION",
        crosswalk_sha256=actual,
        crosswalk_matches_b3=hash_ok,
        b3_record_fingerprint=b3_fp,
        counts=counts,
        targets=targets,
        checks=checks,
        diagnostics=diagnostics,
        site_counts=dict(sorted(Counter(r.site_id for r in rows).items())),
        hoi_site_id=hoi_site,
        development_ids_sha256=_ids_sha256(dev),
        hoi_ids_sha256=_ids_sha256(hoi),
        stamp=make_stamp(
            repo_root,
            require_clean_commit=require_clean_commit and not synthetic,
            config_files=crosswalk_config_files(dataset_config),
            clock=clock,
        ),
    )
    write_record(out, record)
    if not hash_ok:
        raise ProvenanceError(
            "B6 FAILED_VERIFICATION: crosswalk SHA-256 differs from the B3 record"
        )
    if not ok:
        raise DataValidationError(
            "B6 FAILED_VERIFICATION (SR3: stop; the protocol is not modified): "
            + "; ".join(diagnostics)
        )
    return record
