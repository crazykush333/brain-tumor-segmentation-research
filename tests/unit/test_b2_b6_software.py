"""B2-B6 software: acquisition gate, hashing, manifests, counts, provenance, state machine.

All data here are SYNTHETIC_TEST_DATA generated in pytest temporary directories
(outside the repository) or tiny fake inputs. Positive real-mode paths run only
in temporary FAKE repositories whose status file passes gates. The real
repository status is only ever read, never changed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.cli import build_parser, main
from brats_uncertainty.data import acquisition as acq
from brats_uncertainty.data import stages
from brats_uncertainty.data.acquisition import (
    AcquisitionPlan,
    HttpsFileAdapter,
    LocalImportAdapter,
    SyntheticFixtureAdapter,
    redact_url,
    stage_acquire,
)
from brats_uncertainty.data.manifest_doc import (
    CSV_COLUMNS,
    DERIVED_REQUIRED,
    FILE_REQUIRED,
    RAW_REQUIRED,
    build_derived_manifest,
    case_manifest_from_doc,
    content_sha256,
    manifest_to_csv,
    validate_manifest_doc,
)
from brats_uncertainty.data.records import (
    B6_TARGETS,
    AcquisitionRecord,
    CountsRecord,
    InventoryEntry,
    ProvenanceStamp,
    SourceInfo,
    fingerprint,
    make_stamp,
    protocol_count_targets,
    read_acquisition_record,
    read_record_body,
    record_body,
    write_record,
)
from brats_uncertainty.data.stages import (
    stage_build_manifest,
    stage_derive_counts,
    stage_hash_metadata,
    stage_validate_data,
)
from brats_uncertainty.data.synthetic import (
    MARKER_NAME,
    SYNTHETIC_LABEL,
    SyntheticDataset,
    generate_synthetic_dataset,
    require_synthetic,
)
from brats_uncertainty.errors import (
    ConfigError,
    DataValidationError,
    ProvenanceError,
    ResearchGateError,
)
from brats_uncertainty.evaluation.guards import ACQUISITION_LOCKED_MESSAGE, check_action
from brats_uncertainty.evaluation.lifecycle import apply_transition, check_invariants
from brats_uncertainty.evaluation.status import load_status, validate_status
from brats_uncertainty.evaluation.transitions import plan_transition, write_transition
from brats_uncertainty.results.site_export import build_overview
from brats_uncertainty.utils.hashing import sha256_file
from tests.conftest import (
    FAKE_ROUTE,
    OWNER_ROUTE,
    dataset_cfg,
    make_status_repo,
    make_verbatim_status_repo,
    pending_raw,
)
from tests.fixtures.fake_evidence import fake_stamp, write_b1_evidence, write_record_copy

FIXED = datetime(2000, 1, 1, tzinfo=UTC)
SYN_URL = "https://synthetic.invalid/source"


def _clock() -> datetime:
    return FIXED


def _src(route: str = FAKE_ROUTE) -> SourceInfo:
    return SourceInfo("SYNTHETIC_TEST_DATA", "v-test", "10.0000/synthetic", SYN_URL, route)


def _b(n: int) -> set[str]:
    return {f"B{i}" for i in range(1, n + 1)}


def _synthetic_config(tmp_path: Path, repo_root: Path) -> Path:
    cfg = dataset_cfg(repo_root)
    cfg["name"] = "synthetic"
    cfg["layout"]["case_id_pattern"] = r"SYN-\d{4}"
    cfg["layout"]["tree"] = "flat"  # flat synthetic fixture (nested: test_nested_layout.py)
    p = tmp_path / "synthetic_dataset.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


@pytest.fixture
def syn(tmp_path: Path, repo_root: Path) -> SyntheticDataset:
    return generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=3)


def _acquire_synthetic(repo_root: Path, tmp_path: Path, **kw: object) -> AcquisitionRecord:
    adapter = SyntheticFixtureAdapter(repo_root, **kw)  # type: ignore[arg-type]
    rec = stage_acquire(
        repo_root,
        adapter,
        storage_root=tmp_path / "acq",
        out_record=tmp_path / "B2.json",
        acquired_by="pytest",
        execute=True,
        clock=_clock,
    )
    assert isinstance(rec, AcquisitionRecord)
    return rec


# =========================================================== 1. acquisition denied without B1
def test_real_acquisition_denied_before_b1(tmp_path: Path) -> None:
    pending = make_verbatim_status_repo(tmp_path / "pending")  # pre-B1 baseline
    delivered = tmp_path / "delivered.bin"
    delivered.write_bytes(b"synthetic stand-in")
    adapter = LocalImportAdapter(_src("any route"), delivered)
    with pytest.raises(ResearchGateError, match="Real-data acquisition is locked"):
        stage_acquire(
            pending,
            adapter,
            storage_root=tmp_path / "store",
            out_record=tmp_path / "B2.json",
            acquired_by="t",
            execute=True,
        )
    assert not (tmp_path / "store").exists()
    assert not (tmp_path / "B2.json").exists()
    assert ACQUISITION_LOCKED_MESSAGE.startswith("Real-data acquisition is locked")


def test_real_repository_acquisition_requires_the_owner_approved_route(
    pre_execution_root: Path, tmp_path: Path
) -> None:
    """Real state (B1 owner-approved, B2 ready): any other route is refused; nothing written."""
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    delivered = tmp_path / "delivered.bin"
    delivered.write_bytes(b"synthetic stand-in")
    for route in ("any route", "Private Kaggle dataset mirror", FAKE_ROUTE):
        with pytest.raises(ResearchGateError, match="not the B1-approved route"):
            LocalImportAdapter(_src(route), delivered).execute(
                tmp_path / "store", repo_root=repo_root
            )
    assert not (tmp_path / "store").exists()
    assert load_status(repo_root).raw["data"]["approved_route"] == OWNER_ROUTE


def test_real_acquisition_requires_approved_route_and_b2_authorized(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=set())
    delivered = tmp_path / "delivered.bin"
    delivered.write_bytes(b"synthetic stand-in")
    kw = {
        "storage_root": tmp_path / "store",
        "out_record": tmp_path / "B2.json",
        "acquired_by": "t",
    }
    with pytest.raises(ResearchGateError, match="locked"):
        stage_acquire(root, LocalImportAdapter(_src(), delivered), execute=True, **kw)  # type: ignore[arg-type]
    root2 = make_status_repo(tmp_path / "repo2", closed=_b(1))  # B1 PASSED, B2 AUTHORIZED
    with pytest.raises(ResearchGateError, match="not the B1-approved route"):
        stage_acquire(root2, LocalImportAdapter(_src("OTHER"), delivered), execute=True, **kw)  # type: ignore[arg-type]
    rec = stage_acquire(
        root2,
        LocalImportAdapter(_src(), delivered),
        execute=True,
        storage_label="fake-store",
        require_clean_commit=False,
        **kw,  # type: ignore[arg-type]
    )
    assert isinstance(rec, AcquisitionRecord)
    assert rec.synthetic is False
    assert rec.inventory == (
        InventoryEntry("delivered.bin", sha256_file(delivered), delivered.stat().st_size),
    )


# =========================================================== 2. dry run
def test_dry_run_is_default_and_touches_nothing(repo_root: Path, tmp_path: Path) -> None:
    calls: list[str] = []

    def opener(url: str):  # type: ignore[no-untyped-def]
        calls.append(url)
        raise AssertionError("network must not be used in a dry run")

    adapter = HttpsFileAdapter(
        _src(), {"meta/file.csv": "https://example.org/f.csv?token=SECRET"}, opener=opener
    )
    plan = stage_acquire(
        repo_root,
        adapter,
        storage_root=tmp_path / "s",
        out_record=tmp_path / "r.json",
        acquired_by="t",
    )
    assert isinstance(plan, AcquisitionPlan)
    assert calls == []
    assert not (tmp_path / "s").exists()
    assert not (tmp_path / "r.json").exists()
    assert "SECRET" not in plan.describe()
    assert plan.items[0].origin == "https://example.org/f.csv"


def test_https_adapter_refuses_credentials_and_non_https() -> None:
    with pytest.raises(ProvenanceError, match="https"):
        HttpsFileAdapter(_src(), {"a": "http://example.org/a"})
    with pytest.raises(ProvenanceError, match="credentials"):
        HttpsFileAdapter(_src(), {"a": "https://user:pw@example.org/a"})
    assert redact_url("https://u:p@h.org:8443/x?sig=abc#f") == "https://h.org:8443/x"


def test_cli_acquire_dry_run(
    repo_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    delivered = tmp_path / "d.bin"
    delivered.write_bytes(b"x")
    rc = main(
        [
            "--repo-root",
            str(repo_root),
            "acquire",
            "--adapter",
            "local-import",
            "--delivered",
            str(delivered),
            "--storage-root",
            str(tmp_path / "s"),
            "--acquired-by",
            "t",
            "--out",
            str(tmp_path / "r.json"),
        ]
    )
    assert rc == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert not (tmp_path / "s").exists()


# =========================================================== 3. synthetic acquisition bookkeeping
def test_synthetic_acquisition_bookkeeping(repo_root: Path, tmp_path: Path) -> None:
    rec = _acquire_synthetic(repo_root, tmp_path)
    assert rec.synthetic is True
    assert rec.adapter == "synthetic-fixture"
    assert rec.acquired_at == FIXED.isoformat()
    paths = {e.relpath for e in rec.inventory}
    assert MARKER_NAME in paths
    assert "metadata/BraTS2021_MappingToTCIA.xlsx" in paths
    assert sum(p.startswith("images/SYN-") for p in paths) == 3 * 5
    reread = read_acquisition_record(tmp_path / "B2.json")
    assert reread.inventory == rec.inventory
    marker = json.loads((tmp_path / "acq" / MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["label"] == SYNTHETIC_LABEL


def test_synthetic_generation_refused_inside_repository(repo_root: Path) -> None:
    with pytest.raises(ProvenanceError, match="outside the repository"):
        generate_synthetic_dataset(repo_root / "data" / "raw" / "x", repo_root=repo_root)
    with pytest.raises(ProvenanceError, match="outside the repository"):
        stage_acquire(
            repo_root,
            SyntheticFixtureAdapter(repo_root),
            storage_root=repo_root / "data" / "raw" / "x",
            out_record=repo_root / "data" / "manifests" / "x.json",
            acquired_by="t",
            execute=True,
        )
    assert not (repo_root / "data" / "raw").exists()


# =========================================================== 4/5. exact SHA-256
def test_b3_b4_hash_exact_bytes(repo_root: Path, tmp_path: Path, syn: SyntheticDataset) -> None:
    b3 = stage_hash_metadata(
        repo_root,
        "B3",
        syn.crosswalk,
        source_url=SYN_URL,
        doi="10.0/x",
        out=tmp_path / "B3.json",
        synthetic=True,
        clock=_clock,
    )
    data = syn.crosswalk.read_bytes()
    assert b3.file.sha256 == hashlib.sha256(data).hexdigest()
    assert b3.file.size_bytes == len(data)
    assert b3.synthetic is True
    assert b3.stamp.protocol_version == "v1.0"
    assert b3.path_reference == "SYNTHETIC_TEST_DATA/BraTS2021_MappingToTCIA.xlsx"
    b4 = stage_hash_metadata(
        repo_root,
        "B4",
        syn.ucsf_metadata,
        source_url=SYN_URL,
        doi="10.0/x",
        out=tmp_path / "B4.json",
        synthetic=True,
    )
    assert b4.file.sha256 == hashlib.sha256(syn.ucsf_metadata.read_bytes()).hexdigest()


def test_changed_bytes_change_hash_and_break_synthetic_listing(
    repo_root: Path, tmp_path: Path, syn: SyntheticDataset
) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    h1 = sha256_file(p)
    p.write_bytes(b"abd")
    assert sha256_file(p) != h1
    assert h1 == hashlib.sha256(b"abc").hexdigest()
    syn.ucsf_metadata.write_text("modified\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="not a generator-listed"):
        stage_hash_metadata(
            repo_root,
            "B4",
            syn.ucsf_metadata,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "B4.json",
            synthetic=True,
        )


def test_metadata_filenames_are_exact(
    repo_root: Path, tmp_path: Path, syn: SyntheticDataset
) -> None:
    with pytest.raises(DataValidationError, match="requires the file"):
        stage_hash_metadata(
            repo_root,
            "B3",
            syn.ucsf_metadata,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "B3.json",
            synthetic=True,
        )


# =========================================================== 6/7. manifest schema and duplicates
def _manifest(repo_root: Path, tmp_path: Path) -> dict:  # type: ignore[type-arg]
    _acquire_synthetic(repo_root, tmp_path)
    root = tmp_path / "acq"
    xw = root / "metadata" / "BraTS2021_MappingToTCIA.xlsx"
    stage_hash_metadata(
        repo_root,
        "B3",
        xw,
        source_url=SYN_URL,
        doi="10.0/x",
        out=tmp_path / "B3.json",
        synthetic=True,
        clock=_clock,
    )
    return stage_build_manifest(
        repo_root,
        _synthetic_config(tmp_path, repo_root),
        root / "images",
        tmp_path / "B2.json",
        tmp_path / "B5.json",
        out_csv=tmp_path / "B5.csv",
        metadata_files=[xw],
        metadata_records=[tmp_path / "B3.json"],
        synthetic=True,
        clock=_clock,
    )


def test_raw_manifest_schema_and_csv(repo_root: Path, tmp_path: Path) -> None:
    doc = _manifest(repo_root, tmp_path)
    validate_manifest_doc(doc)
    assert doc["manifest_type"] == "raw"
    assert doc["synthetic"] is True
    assert doc["summary"]["n_cases"] == 3
    assert doc["summary"]["n_images"] == 12
    assert doc["summary"]["n_labels"] == 3
    assert {f["modality"] for f in doc["files"] if f["file_type"] == "image"} == {
        "T1",
        "T1c",
        "T2",
        "FLAIR",
    }
    assert (
        doc["acquisition"]["record_fingerprint"]
        == read_record_body(tmp_path / "B2.json")["record_fingerprint"]
    )
    csv_text = (tmp_path / "B5.csv").read_text(encoding="utf-8")
    assert csv_text.splitlines()[0] == ",".join(CSV_COLUMNS)
    assert len(csv_text.splitlines()) == len(doc["files"]) + 1
    assert manifest_to_csv(doc) == csv_text
    cm = case_manifest_from_doc(doc, "synthetic")
    assert len(cm.entries) == 3


@pytest.mark.parametrize(
    ("mutate", "msg"),
    [
        (lambda d: d.pop("doi"), "missing required"),
        (lambda d: d["files"][0].update(sha256="abc"), "malformed sha256"),
        (lambda d: d["files"][0].update(relpath="C:/x/y.nii.gz"), "non-relative"),
        (lambda d: d["files"][0].update(file_type="image-ish"), "file_type"),
        (lambda d: d["files"][0].update(size_bytes=d["files"][0]["size_bytes"] + 1), "summary"),
        (lambda d: d.update(dataset="changed"), "manifest_sha256"),
    ],
)
def test_manifest_validation_rejects_tampering(
    repo_root: Path, tmp_path: Path, mutate, msg
) -> None:  # type: ignore[no-untyped-def]
    doc = _manifest(repo_root, tmp_path)
    mutate(doc)
    with pytest.raises(DataValidationError, match=msg):
        validate_manifest_doc(doc)


def test_json_schemas_match_validator(repo_root: Path) -> None:
    raw = json.loads(
        (repo_root / "configs/schemas/raw_data_manifest.schema.json").read_text(encoding="utf-8")
    )
    der = json.loads(
        (repo_root / "configs/schemas/derived_data_manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(raw["required"]) == RAW_REQUIRED
    assert tuple(der["required"]) == DERIVED_REQUIRED
    assert tuple(raw["$defs"]["file"]["required"]) == FILE_REQUIRED


def test_duplicate_detection(repo_root: Path, tmp_path: Path) -> None:
    doc = _manifest(repo_root, tmp_path)
    # all-zero synthetic volumes of identical shape have identical bytes -> reported duplicates
    assert doc["duplicates"]
    assert all(len(g) > 1 for g in doc["duplicates"])
    dup = json.loads(json.dumps(doc))
    dup["files"].append(dict(dup["files"][0]))
    with pytest.raises(DataValidationError, match="duplicate relpath"):
        validate_manifest_doc(dup)
    dup2 = json.loads(json.dumps(doc))
    img = next(f for f in dup2["files"] if f["file_type"] == "image")
    dup2["files"].append({**img, "relpath": img["relpath"] + ".copy"})
    with pytest.raises(DataValidationError, match="duplicate"):
        validate_manifest_doc(dup2)


def test_derived_manifest_links_parent(repo_root: Path, tmp_path: Path) -> None:
    doc = _manifest(repo_root, tmp_path)
    derived_root = tmp_path / "derived"
    derived_root.mkdir()
    (derived_root / "summary.txt").write_text("synthetic derived output\n", encoding="utf-8")
    stamp = make_stamp(repo_root, require_clean_commit=False, clock=_clock, environment={})
    d = build_derived_manifest(
        derived_root, doc, tool="pytest", description="synthetic", config_sha256={}, stamp=stamp
    )
    assert d["manifest_type"] == "derived"
    assert d["parent_manifest_sha256"] == doc["manifest_sha256"]
    assert d["manifest_sha256"] == content_sha256(d)


def test_manifest_stage_refuses_integrity_errors(repo_root: Path, tmp_path: Path) -> None:
    _acquire_synthetic(repo_root, tmp_path)
    (tmp_path / "acq" / "images" / "SYN-0001" / "SYN-0001_t2.nii.gz").unlink()
    # file removal is allowed by the marker check (remaining files are listed), integrity fails
    with pytest.raises(DataValidationError, match="integrity audit failed"):
        stage_build_manifest(
            repo_root,
            _synthetic_config(tmp_path, repo_root),
            tmp_path / "acq" / "images",
            tmp_path / "B2.json",
            tmp_path / "B5.json",
            synthetic=True,
        )


def test_validate_data_synthetic(repo_root: Path, tmp_path: Path) -> None:
    _acquire_synthetic(repo_root, tmp_path)
    rep = stage_validate_data(
        repo_root,
        _synthetic_config(tmp_path, repo_root),
        tmp_path / "acq" / "images",
        synthetic=True,
    )
    assert rep.ok
    assert rep.n_complete_cases == 3


# =========================================================== 8. deterministic provenance
def test_provenance_records_are_deterministic(
    repo_root: Path, tmp_path: Path, syn: SyntheticDataset
) -> None:
    def run(out: str, clock) -> dict:  # type: ignore[no-untyped-def,type-arg]
        stage_hash_metadata(
            repo_root,
            "B4",
            syn.ucsf_metadata,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / out,
            synthetic=True,
            clock=clock,
        )
        return json.loads((tmp_path / out).read_text(encoding="utf-8"))

    a = run("a.json", _clock)
    b = run("b.json", _clock)
    c = run("c.json", lambda: datetime(2011, 1, 1, tzinfo=UTC))
    assert a["record_fingerprint"] == b["record_fingerprint"] == c["record_fingerprint"]
    assert a["stamp"]["created_at"] != c["stamp"]["created_at"]
    assert fingerprint(a) == a["record_fingerprint"]
    body = dict(a)
    body["file"] = {**body["file"], "sha256": "0" * 64}
    assert fingerprint(body) != a["record_fingerprint"]
    (tmp_path / "a.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="fingerprint mismatch"):
        read_record_body(tmp_path / "a.json")


def test_stamp_contents(repo_root: Path, tmp_path: Path) -> None:
    cfg = repo_root / "configs/dataset/brats2021.yaml"
    s = make_stamp(
        repo_root, require_clean_commit=False, config_files=[cfg], clock=_clock, environment={}
    )
    assert s.protocol_version == "v1.0"
    assert s.protocol_sha256 == "704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811"
    assert s.config_sha256 == {"configs/dataset/brats2021.yaml": sha256_file(cfg)}
    fake = make_status_repo(tmp_path / "repo", closed=set())
    with pytest.raises(ProvenanceError, match="clean, committed"):
        make_stamp(fake)


# =========================================================== 9/10/11. B6 expected vs verified
def test_b6_expected_by_protocol_before_any_source(
    pre_execution_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    t = protocol_count_targets()
    assert t["status"] == "EXPECTED_BY_PROTOCOL"
    assert t["targets"] == {"total": 1251, "held_out_institution": 511, "development": 740}
    assert "not yet verified" in t["label"]
    site = json.loads((repo_root / "website/data/status.json").read_text(encoding="utf-8"))
    assert site["count_verification"]["status"] == "EXPECTED_BY_PROTOCOL"
    assert "counts" not in site["count_verification"]
    assert main(["--repo-root", str(repo_root), "count-targets"]) == 0
    assert "EXPECTED_BY_PROTOCOL" in capsys.readouterr().out


def _b3(repo_root: Path, tmp_path: Path, ds: SyntheticDataset, name: str = "B3.json") -> Path:
    stage_hash_metadata(
        repo_root,
        "B3",
        ds.crosswalk,
        source_url=SYN_URL,
        doi="10.0/x",
        out=tmp_path / name,
        synthetic=True,
    )
    return tmp_path / name


def test_b6_passes_on_synthetic_expected_dataset(repo_root: Path, tmp_path: Path) -> None:
    ds = generate_synthetic_dataset(
        tmp_path / "syn", repo_root=repo_root, n_cases=1, crosswalk_counts=(511, 740)
    )
    rec = stage_derive_counts(
        repo_root,
        ds.crosswalk,
        _b3(repo_root, tmp_path, ds),
        _synthetic_config(tmp_path, repo_root),
        tmp_path / "B6.json",
        synthetic=True,
    )
    assert rec.status == "SYNTHETIC_TEST_ONLY"  # never VERIFIED_FROM_SOURCE for synthetic data
    assert rec.synthetic is True  # synthetic: can never close gate B6
    assert rec.counts == B6_TARGETS
    assert rec.checks == {"total": True, "held_out_institution": True, "development": True}
    assert rec.site_counts == {"1": 511, "18": 740}
    assert rec.diagnostics == []


def test_b6_fails_on_wrong_counts(repo_root: Path, tmp_path: Path) -> None:
    ds = generate_synthetic_dataset(
        tmp_path / "syn", repo_root=repo_root, n_cases=1, crosswalk_counts=(3, 5)
    )
    with pytest.raises(DataValidationError, match="FAILED_VERIFICATION"):
        stage_derive_counts(
            repo_root,
            ds.crosswalk,
            _b3(repo_root, tmp_path, ds),
            _synthetic_config(tmp_path, repo_root),
            tmp_path / "B6.json",
            synthetic=True,
        )
    body = read_record_body(tmp_path / "B6.json")
    assert body["status"] == "FAILED_VERIFICATION"
    assert body["targets"] == B6_TARGETS  # targets are never altered to fit the data
    assert any("total: derived 8, protocol target 1251" in d for d in body["diagnostics"])


def test_b6_fails_when_crosswalk_differs_from_b3(repo_root: Path, tmp_path: Path) -> None:
    a = generate_synthetic_dataset(
        tmp_path / "a", repo_root=repo_root, n_cases=1, crosswalk_counts=(511, 740)
    )
    b = generate_synthetic_dataset(
        tmp_path / "b", repo_root=repo_root, n_cases=1, crosswalk_counts=(511, 741)
    )
    with pytest.raises(ProvenanceError, match="differs from the B3 record"):
        stage_derive_counts(
            repo_root,
            b.crosswalk,
            _b3(repo_root, tmp_path, a),
            _synthetic_config(tmp_path, repo_root),
            tmp_path / "B6.json",
            synthetic=True,
        )
    body = read_record_body(tmp_path / "B6.json")
    assert body["status"] == "FAILED_VERIFICATION"
    assert body["crosswalk_matches_b3"] is False


def test_counts_record_cannot_claim_verified_with_failed_checks() -> None:
    stamp = ProvenanceStamp("t", None, None, "0", "v1.0", "0" * 64, {}, {})
    with pytest.raises(ProvenanceError):
        CountsRecord(
            "B6",
            False,
            "VERIFIED_FROM_SOURCE",
            "a" * 64,
            True,
            "b" * 64,
            {"total": 1, "held_out_institution": 511, "development": 740},
            dict(B6_TARGETS),
            {"total": False, "held_out_institution": True, "development": True},
            ["x"],
            {},
            "1",
            "c" * 64,
            "d" * 64,
            stamp,
        ).validate()
    with pytest.raises(ProvenanceError, match="targets differ"):
        CountsRecord(
            "B6",
            False,
            "VERIFIED_FROM_SOURCE",
            "a" * 64,
            True,
            "b" * 64,
            {"total": 8},
            {"total": 8},
            {"total": True},
            [],
            {},
            "1",
            "c" * 64,
            "d" * 64,
            stamp,
        ).validate()


# =========================================================== 12. B7 locked before B6
def test_b7_locked_before_b6(pre_execution_root: Path, tmp_path: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    st = load_status(repo_root)
    assert st.gate("B7").status == "LOCKED"
    assert check_action("compute_t_screen", repo_root)
    root = make_status_repo(tmp_path / "repo", closed=_b(5))
    st2 = load_status(root)
    assert st2.gate("B6").status == "AUTHORIZED"
    assert st2.gate("B7").status == "LOCKED"
    assert any("B6" in u for u in check_action("compute_t_screen", root))
    with pytest.raises(ConfigError, match="prerequisites"):
        apply_transition(st2.raw, "B7", "AUTHORIZED")
    raw = yaml.safe_load((root / "docs/project_status.yaml").read_text(encoding="utf-8"))
    next(g for g in raw["gates"] if g["id"] == "B7")["status"] = "AUTHORIZED"
    with pytest.raises(ConfigError, match="must be LOCKED"):
        validate_status(raw, root)


# =========================================================== 13. transitions
def test_invalid_transitions_rejected(repo_root: Path) -> None:
    raw = pending_raw()  # pre-B1 baseline
    for gid, new, kw, msg in [
        ("B2", "PASSED", {}, "illegal transition"),  # LOCKED -> PASSED
        ("B2", "AUTHORIZED", {}, "prerequisites"),  # B1 not passed
        ("B1", "AUTHORIZED", {}, "illegal transition"),
        ("B1", "PASSED", {"evidence": "x", "on": "2000-01-01"}, "approved data route"),
        ("B1", "PASSED", {"approved_route": "r"}, "evidence and a date"),
        ("A1", "PASSED", {}, "B1-B12, C1-C6 and D1-D6"),
        ("D1", "CLOSED", {"evidence": "x", "on": "2000-01-01"}, r"\['B1'\] not closed"),
        ("D3", "CLOSED", {"evidence": "x", "on": "2000-01-01"}, "not closed"),
        ("D1", "PASSED", {}, "illegal transition"),
        ("C1", "BLOCKED", {}, "evidence document"),
        ("D1", "IN_PROGRESS", {"approved_route": "r"}, "approved_route"),
    ]:
        with pytest.raises(ConfigError, match=msg):
            apply_transition(raw, gid, new, **kw)
    with pytest.raises(ConfigError):
        check_invariants({"B1": "PENDING", "B2": "AUTHORIZED"})
    with pytest.raises(ConfigError, match="LOCKED although"):
        check_invariants({"B1": "PASSED", "B2": "LOCKED"})
    real = copy.deepcopy(load_status(repo_root).raw)  # B1 PASSED is terminal; B2 may not
    for g in real["gates"]:  # skip RUNNING (snapshot independent of the live B2 state)
        if g["id"] == "B2":
            g.update(status="AUTHORIZED", evidence=None, closed_on=None)
    for gid, new in (("B1", "PENDING"), ("B1", "PASSED"), ("B2", "PASSED"), ("B3", "AUTHORIZED")):
        with pytest.raises(ConfigError):
            apply_transition(real, gid, new, evidence="x", on="2000-01-01")
    # a B1-passed baseline with the D gates not started (independent of the live D states)
    base = copy.deepcopy(real)
    for g in base["gates"]:
        if g["id"].startswith("D"):
            g.update(status="NOT_STARTED", evidence=None, closed_on=None)
    with pytest.raises(ConfigError, match="evidence and a date"):
        apply_transition(base, "D1", "CLOSED")
    # B1 has PASSED: D1 may close with evidence; D6 still needs D1-D5
    closed = apply_transition(base, "D1", "CLOSED", evidence="x", on="2000-01-01")
    d1 = next(g for g in closed["gates"] if g["id"] == "D1")
    assert (d1["status"], d1["evidence"], d1["closed_on"]) == ("CLOSED", "x", "2000-01-01")
    with pytest.raises(ConfigError, match="not closed"):
        apply_transition(closed, "D6", "CLOSED", evidence="x", on="2000-01-01")


def test_b1_pass_unlocks_only_b2_and_records_route(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    ev = write_b1_evidence(root)
    changes = write_transition(
        root,
        "B1",
        "PASSED",
        evidence=ev,
        on="2000-01-01",
        approved_route=FAKE_ROUTE,
    )
    assert "B1.status: PENDING -> PASSED" in changes
    assert "B2.status: LOCKED -> AUTHORIZED" in changes
    before = (root / "docs/project_status.yaml").read_text(encoding="utf-8")
    assert "status: PENDING" in before  # dry run wrote nothing
    write_transition(
        root,
        "B1",
        "PASSED",
        evidence=ev,
        on="2000-01-01",
        approved_route=FAKE_ROUTE,
        apply=True,
    )
    st = load_status(root)
    assert st.gate("B1").status == "PASSED"
    assert st.gate("B2").status == "AUTHORIZED"
    assert all(st.gate(f"B{i}").status == "LOCKED" for i in range(3, 13))
    assert st.raw["data"]["authorization"] == "APPROVED"
    assert st.raw["data"]["approved_route"] == FAKE_ROUTE
    text = (root / "docs/project_status.yaml").read_text(encoding="utf-8")
    assert "# Single source of truth for project state." in text  # comments preserved
    assert check_action("acquire_data", root) == []


def test_gates_cannot_pass_on_synthetic_or_failed_records(repo_root: Path, tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    # B2 is AUTHORIZED; move to RUNNING, then try to pass on a genuine SYNTHETIC record
    raw = apply_transition(load_status(root).raw, "B2", "RUNNING")
    _acquire_synthetic(repo_root, tmp_path)
    syn_body = read_record_body(tmp_path / "B2.json")
    syn_ev = write_record_copy(root, "evidence/B2_synthetic.json", syn_body)
    bad = apply_transition(raw, "B2", "PASSED", evidence=syn_ev, on="2000-01-01")
    with pytest.raises(ConfigError, match="synthetic"):
        validate_status(bad, root)
    md = apply_transition(raw, "B2", "PASSED", evidence="evidence/gate.md", on="2000-01-01")
    with pytest.raises(ConfigError, match="JSON execution record"):
        validate_status(md, root)
    forged = write_record_copy(root, "evidence/B2_forged.json", {"gate": "B2", "synthetic": False})
    bad_forged = apply_transition(raw, "B2", "PASSED", evidence=forged, on="2000-01-01")
    with pytest.raises(ConfigError, match="invalid"):
        validate_status(bad_forged, root)
    root6 = make_status_repo(tmp_path / "repo6", closed=_b(5))
    raw6 = apply_transition(load_status(root6).raw, "B6", "RUNNING")
    good = read_record_body(root6 / "evidence/B6_record.json")
    failed = CountsRecord(
        "B6",
        False,
        "FAILED_VERIFICATION",
        good["crosswalk_sha256"],
        True,
        good["b3_record_fingerprint"],
        {**B6_TARGETS, "total": 1250},
        dict(B6_TARGETS),
        {"total": False, "held_out_institution": True, "development": True},
        ["total: derived 1250, protocol target 1251 (difference -1)"],
        {"1": 511, "18": 739},
        "1",
        good["development_ids_sha256"],
        good["hoi_ids_sha256"],
        fake_stamp(),
    )
    write_record(root6 / "evidence/B6_failed.json", failed)
    bad6 = apply_transition(
        raw6, "B6", "PASSED", evidence="evidence/B6_failed.json", on="2000-01-01"
    )
    with pytest.raises(ConfigError, match="VERIFIED_FROM_SOURCE"):
        validate_status(bad6, root6)


def test_plan_transition_does_not_write(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    before = (root / "docs/project_status.yaml").read_bytes()
    with pytest.raises(ConfigError, match="requires an evidence document"):
        plan_transition(root, "B1", "BLOCKED")
    _, changes = plan_transition(root, "B1", "BLOCKED", evidence="evidence/gate.md")
    assert changes == ["B1.status: PENDING -> BLOCKED", "B1.evidence: None -> evidence/gate.md"]
    assert (root / "docs/project_status.yaml").read_bytes() == before


# =========================================================== 14. no real-data bypass
def _all_options(parser: argparse.ArgumentParser) -> list[str]:
    opts: list[str] = []
    for action in parser._actions:
        opts += action.option_strings
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                opts += _all_options(sub)
    return opts


def test_no_bypass_flags_or_parameters() -> None:
    forbidden = ("force", "skip", "bypass", "override", "unsafe", "no-gate", "ignore-gate")
    for opt in _all_options(build_parser()):
        assert not any(f in opt for f in forbidden), opt
    for fn in (
        stage_acquire,
        stage_hash_metadata,
        stage_validate_data,
        stage_build_manifest,
        stage_derive_counts,
    ):
        for name in inspect.signature(fn).parameters:
            assert not any(f.replace("-", "_") in name for f in forbidden), (fn.__name__, name)


def test_synthetic_mode_cannot_process_real_or_unlisted_files(
    repo_root: Path, tmp_path: Path
) -> None:
    other = tmp_path / "elsewhere" / "BraTS2021_MappingToTCIA.xlsx"
    other.parent.mkdir()
    other.write_bytes(b"not generated by the synthetic generator")
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_DATA tree"):
        stage_hash_metadata(
            repo_root,
            "B3",
            other,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "B3.json",
            synthetic=True,
        )
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root)
    intruder = ds.root / "metadata" / "extra.csv"
    intruder.write_text("a\n", encoding="utf-8")
    with pytest.raises(ProvenanceError, match="not a generator-listed"):
        require_synthetic([ds.root / "metadata"], repo_root)


def test_real_mode_refuses_synthetic_inputs(tmp_path: Path, repo_root: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(2))  # B3 AUTHORIZED in the fake repo
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root)
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_DATA input in real mode"):
        stage_hash_metadata(
            root,
            "B3",
            ds.crosswalk,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "B3.json",
            require_clean_commit=False,
        )


def test_real_mode_stages_blocked_in_current_repository(
    pre_execution_root: Path, tmp_path: Path
) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    f = tmp_path / "BraTS2021_MappingToTCIA.xlsx"
    f.write_bytes(b"placeholder")
    with pytest.raises(ResearchGateError):
        stage_hash_metadata(
            repo_root, "B3", f, source_url=SYN_URL, doi="10.0/x", out=tmp_path / "o.json"
        )
    with pytest.raises(ResearchGateError):
        stage_validate_data(repo_root, repo_root / "configs/dataset/brats2021.yaml", tmp_path)
    assert not (tmp_path / "o.json").exists()
    assert "stage_record_acquisition" not in dir(acq)
    assert "stage_record_acquisition" not in dir(stages)


# =========================================================== status and website consistency
def test_current_status_is_b1_owner_approved_b2_ready_b3_to_b12_locked(
    pre_execution_root: Path,
) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    st = load_status(repo_root)
    assert st.gate("B1").status == "PASSED"
    assert st.gate("B2").status in ("AUTHORIZED", "RUNNING")  # RUNNING once the runner started it
    for i in range(3, 13):
        assert st.gate(f"B{i}").status == "LOCKED", i
    assert st.raw["data"]["authorization"] == "APPROVED"
    assert st.raw["data"]["approved_route"] == OWNER_ROUTE
    assert st.raw["data"]["acquired"] is False
    raw = st.raw
    ov = {
        o["key"]: o["status"]
        for o in build_overview(raw, {g.id: g.status for g in st.gates.values()}, repo_root)
    }
    assert ov == {
        "protocol": "FROZEN",
        "route_docs": "PREPARED",
        "b1": "ROUTE_AUTHORIZED",
        "b2": st.gate("B2").status,  # AUTHORIZED or RUNNING (asserted above)
        "b3": "LOCKED",
        "b4": "LOCKED",
        "b5": "LOCKED",
        "b6": "LOCKED",
        "b7": "LOCKED",
        "b8": "LOCKED",
        "b9": "LOCKED",
        "b10": "LOCKED",
        "b11": "LOCKED",
        "b12": "LOCKED",
        "training": "NOT_STARTED",
        "evaluation": "NOT_STARTED",
        "results": "NOT_AVAILABLE",
    }


def test_status_section_consistency(pre_execution_root: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    real = load_status(repo_root).raw  # B1 PASSED: authorization and route must stay consistent
    for mutate, msg in [
        (lambda r: r["data"].update(authorization="PENDING"), "APPROVED exactly"),
        (lambda r: r["data"].update(approved_route=None), "must name the route"),
        (lambda r: r["data"].update(approved_route="Private Kaggle mirror"), "Approved route"),
        (lambda r: r["data"].update(acquired=True), "acquired"),
    ]:
        raw = json.loads(json.dumps(real))
        mutate(raw)
        with pytest.raises(ConfigError, match=msg):
            validate_status(raw, repo_root)
    base = pending_raw()
    for mutate, msg in [
        (
            lambda r: r["data"].update(authorization="APPROVED", approved_route="x"),
            "APPROVED exactly",
        ),
        (lambda r: r["data"].update(approved_route="x"), "approved_route is set"),
        (lambda r: r["data"].update(acquired=True), "acquired"),
        (lambda r: r["data"].update(authorization="REFUSED"), "REFUSED"),
        (lambda r: r["training"].update(status="IN_PROGRESS"), "B12"),
        (lambda r: r["evaluation"].update(internal="COMPLETED"), "C5 and C6"),
        (lambda r: r["results"].update(status="AVAILABLE"), "disagree"),
    ]:
        raw = json.loads(json.dumps(base))
        mutate(raw)
        with pytest.raises(ConfigError, match=msg):
            validate_status(raw, repo_root)


def test_record_write_refuses_overwrite(repo_root: Path, tmp_path: Path) -> None:
    rec = _acquire_synthetic(repo_root, tmp_path)
    with pytest.raises(FileExistsError):
        write_record(tmp_path / "B2.json", rec)
    assert (
        record_body(rec)["record_fingerprint"]
        == read_record_body(tmp_path / "B2.json")["record_fingerprint"]
    )


# =========================================================== security scan
def test_security_scan_flags_credentials_and_personal_paths(tmp_path: Path) -> None:
    from brats_uncertainty.repo_checks import check_paths

    sep = chr(92)  # backslash
    personal = "C:" + sep + "Users" + sep + "someone" + sep + "data"  # assembled at runtime
    (tmp_path / "a.yaml").write_text(f"data_root: {personal}\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("KAGGLE_KEY = '" + "a1b2c3d4e5f6a7b8" + "'\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("see /home/" + "someone/brats\n", encoding="utf-8")
    (tmp_path / "ok.md").write_text("ENV PATH=/home/researcher/.local/bin\n", encoding="utf-8")
    found = {
        (f.path, f.problem) for f in check_paths(["a.yaml", "b.py", "c.md", "ok.md"], tmp_path)
    }
    assert ("a.yaml", "possible secret: hard-coded personal path") in found
    assert ("b.py", "possible secret: Kaggle/TCIA credential assignment") in found
    assert ("c.md", "possible secret: hard-coded personal path") in found
    assert not any(p == "ok.md" for p, _ in found)


def test_logs_and_records_never_contain_url_secrets(repo_root: Path, tmp_path: Path) -> None:
    served: list[str] = []

    class _Resp:
        def __init__(self) -> None:
            self.done = False

        def read(self, n: int) -> bytes:
            if self.done:
                return b""
            self.done = True
            return b"synthetic payload"

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *a: object) -> None:
            return None

    def opener(url: str) -> _Resp:
        served.append(url)
        return _Resp()

    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    url = "https://example.org/m.csv?token=TOPSECRET"
    adapter = HttpsFileAdapter(_src(), {"meta.csv": url}, opener=opener)  # type: ignore[arg-type]
    rec = stage_acquire(
        root,
        adapter,
        storage_root=tmp_path / "store",
        out_record=tmp_path / "B2.json",
        acquired_by="t",
        execute=True,
        storage_label="fake-store",
        require_clean_commit=False,
    )
    assert isinstance(rec, AcquisitionRecord)
    assert served == [url]  # the full URL is used only for the request itself
    assert "TOPSECRET" not in (tmp_path / "B2.json").read_text(encoding="utf-8")
    assert (tmp_path / "store" / "meta.csv").read_bytes() == b"synthetic payload"
