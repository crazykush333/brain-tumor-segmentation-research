"""Adversarial audit tests for the integrated B2-B6 infrastructure.

Invariants A-N (see docs/data/B2_B6_SOFTWARE_READINESS.md) and edge
cases. Only SYNTHETIC_TEST_DATA and FAKE evidence in temporary directories are
used; the real repository status is read-only here.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.data import acquisition as acq_mod
from brats_uncertainty.data.acquisition import (
    HttpsFileAdapter,
    LocalImportAdapter,
    SyntheticFixtureAdapter,
    stage_acquire,
)
from brats_uncertainty.data.manifest_doc import (
    CSV_COLUMNS,
    build_raw_manifest,
    content_sha256,
    manifest_to_csv,
    validate_manifest_doc,
)
from brats_uncertainty.data.records import (
    B6_TARGETS,
    AcquisitionRecord,
    CountsRecord,
    HashedFile,
    MetadataFileRecord,
    SourceInfo,
    make_stamp,
    read_acquisition_record,
    read_counts_record,
    read_metadata_record,
    read_record_body,
    write_record,
)
from brats_uncertainty.data.stages import (
    stage_build_manifest,
    stage_derive_counts,
    stage_hash_metadata,
)
from brats_uncertainty.data.synthetic import generate_synthetic_dataset, require_synthetic
from brats_uncertainty.errors import (
    ConfigError,
    DataValidationError,
    ProvenanceError,
    ResearchGateError,
)
from brats_uncertainty.evaluation.guards import check_action
from brats_uncertainty.evaluation.lifecycle import apply_transition, check_invariants
from brats_uncertainty.evaluation.status import load_status, validate_status
from brats_uncertainty.evaluation.transitions import write_transition
from brats_uncertainty.repo_checks import check_paths, sniff_imaging
from brats_uncertainty.results.site_export import build_count_block
from brats_uncertainty.utils.hashing import sha256_bytes, sha256_file
from brats_uncertainty.utils.io import write_json
from tests.conftest import (
    FAKE_ROUTE,
    dataset_cfg,
    make_status_repo,
    make_verbatim_status_repo,
)
from tests.fixtures.fake_evidence import (
    FAKE_SCHEMA,
    build_fake_chain,
    fake_source,
    fake_stamp,
    write_b1_evidence,
    write_record_copy,
)

SYN_URL = "https://synthetic.invalid/source"
FIXED = datetime(2000, 1, 1, tzinfo=UTC)


def _b(n: int) -> set[str]:
    return {f"B{i}" for i in range(1, n + 1)}


def _raw(root: Path) -> dict:  # type: ignore[type-arg]
    return yaml.safe_load((root / "docs/project_status.yaml").read_text(encoding="utf-8"))


def _synthetic_config(tmp_path: Path, repo_root: Path) -> Path:
    cfg = dataset_cfg(repo_root)
    cfg["layout"]["case_id_pattern"] = r"SYN-\d{4}"
    cfg["layout"]["tree"] = "flat"  # flat synthetic fixture (nested: test_nested_layout.py)
    p = tmp_path / "syn_cfg.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


# ----- A. B1 before real B2
def test_A_real_acquisition_requires_b1(pre_execution_root: Path, tmp_path: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    d = tmp_path / "d.bin"
    d.write_bytes(b"x")
    pending = make_verbatim_status_repo(tmp_path / "pending")  # pre-B1 baseline
    for root in (pending, make_status_repo(tmp_path / "fake", closed=set())):
        with pytest.raises(ResearchGateError, match="Real-data acquisition is locked"):
            stage_acquire(
                root,
                LocalImportAdapter(fake_source(), d),
                storage_root=tmp_path / "s",
                out_record=tmp_path / "r.json",
                acquired_by="t",
                execute=True,
                storage_label="x",
            )
    assert not (tmp_path / "s").exists()
    # real state: B1 passed via the owner-approved alternative; a non-approved route is refused
    with pytest.raises(ResearchGateError, match="not the B1-approved route"):
        stage_acquire(
            repo_root,
            LocalImportAdapter(fake_source(), d),
            storage_root=tmp_path / "s",
            out_record=tmp_path / "r.json",
            acquired_by="t",
            execute=True,
            storage_label="x",
            require_clean_commit=False,
        )
    assert not (tmp_path / "s").exists() and not (tmp_path / "r.json").exists()


# ----- B. calling acquisition != B2 passed
def test_B_acquisition_call_does_not_advance_status(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    before = (root / "docs/project_status.yaml").read_bytes()
    d = tmp_path / "d.bin"
    d.write_bytes(b"x")
    stage_acquire(
        root,
        LocalImportAdapter(fake_source(), d),
        storage_root=tmp_path / "s",
        out_record=tmp_path / "r.json",
        acquired_by="t",
        execute=True,
        storage_label="x",
        require_clean_commit=False,
    )
    assert (root / "docs/project_status.yaml").read_bytes() == before
    st = load_status(root)
    assert st.gate("B2").status == "AUTHORIZED"
    assert st.raw["data"]["acquired"] is False


# ---------------------------------------------------------------- C/D. exact designated files
def test_C_D_evidence_must_be_the_designated_file_record(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(2))
    raw = apply_transition(load_status(root).raw, "B3", "RUNNING")
    wrong = apply_transition(
        raw, "B3", "PASSED", evidence="evidence/B4_record.json", on="2000-01-01"
    )
    with pytest.raises(ConfigError, match="belongs to gate"):
        validate_status(wrong, root)
    ok = apply_transition(raw, "B3", "PASSED", evidence="evidence/B3_record.json", on="2000-01-01")
    validate_status(ok, root)
    with pytest.raises(ProvenanceError, match="requires file"):
        MetadataFileRecord(
            "B4",
            False,
            "ucsf_pdgm_metadata",
            HashedFile("other.csv", "a" * 64, 1),
            "x",
            "https://x.invalid",
            "10.1/x",
            fake_stamp(),
        ).validate()


# ----- E. B5 needs B3/B4 provenance
def test_E_real_b5_requires_b3_b4_records(tmp_path: Path, repo_root: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(4))
    tree = root / "fake_work" / "images"
    with pytest.raises(ProvenanceError, match="B3 and B4 records"):
        stage_build_manifest(
            root,
            _synthetic_config(tmp_path, repo_root),
            tree,
            root / "evidence/B2_record.json",
            tmp_path / "B5.json",
            require_clean_commit=False,
        )


def test_E_b5_evidence_must_link_to_b2_b3_b4(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(4))
    b2 = read_acquisition_record(root / "evidence/B2_record.json")
    b3 = read_metadata_record(root / "evidence/B3_record.json")
    xw = root / "fake_work" / "metadata" / b3.file.file_name
    doc = build_raw_manifest(
        root / "fake_work" / "images",
        FAKE_SCHEMA,
        b2,
        fake_stamp(),
        metadata=[(xw, b3)],
        extra={"gate": "B5"},
    )
    rel = write_record_copy(root, "evidence/B5_unlinked.json", doc)
    raw = apply_transition(load_status(root).raw, "B5", "RUNNING")
    bad = apply_transition(raw, "B5", "PASSED", evidence=rel, on="2000-01-01")
    with pytest.raises(ConfigError, match="not linked to the B4"):
        validate_status(bad, root)
    good = apply_transition(
        raw, "B5", "PASSED", evidence="evidence/B5_manifest.json", on="2000-01-01"
    )
    validate_status(good, root)


# ----- F. B6 derives from the source
def test_F_b6_requires_an_actual_source(pre_execution_root: Path, tmp_path: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    stage_hash_metadata(
        repo_root,
        "B3",
        ds.crosswalk,
        source_url=SYN_URL,
        doi="10.0/x",
        out=tmp_path / "b3.json",
        synthetic=True,
    )
    missing = ds.root / "metadata" / "missing" / "BraTS2021_MappingToTCIA.xlsx"
    with pytest.raises(DataValidationError, match="input not found"):
        stage_derive_counts(
            repo_root,
            missing,
            tmp_path / "b3.json",
            _synthetic_config(tmp_path, repo_root),
            tmp_path / "b6.json",
            synthetic=True,
        )
    assert not (tmp_path / "b6.json").exists()
    with pytest.raises(ResearchGateError):  # real mode: blocked before anything else
        stage_derive_counts(
            repo_root,
            missing,
            tmp_path / "b3.json",
            _synthetic_config(tmp_path, repo_root),
            tmp_path / "b6.json",
        )


# ----- G. expected vs verified
def test_G_expected_and_verified_states_are_distinct(
    pre_execution_root: Path, tmp_path: Path
) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    block = build_count_block(repo_root, _raw(repo_root))
    assert block["status"] == "EXPECTED_BY_PROTOCOL"
    assert "counts" not in block
    ds = generate_synthetic_dataset(
        tmp_path / "syn", repo_root=repo_root, n_cases=1, crosswalk_counts=(511, 740)
    )
    stage_hash_metadata(
        repo_root,
        "B3",
        ds.crosswalk,
        source_url=SYN_URL,
        doi="10.0/x",
        out=tmp_path / "b3.json",
        synthetic=True,
    )
    rec = stage_derive_counts(
        repo_root,
        ds.crosswalk,
        tmp_path / "b3.json",
        _synthetic_config(tmp_path, repo_root),
        tmp_path / "b6.json",
        synthetic=True,
    )
    assert rec.status == "SYNTHETIC_TEST_ONLY"
    assert read_counts_record(tmp_path / "b6.json").status == "SYNTHETIC_TEST_ONLY"
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_ONLY or FAILED_VERIFICATION"):
        CountsRecord(
            "B6",
            True,
            "VERIFIED_FROM_SOURCE",
            rec.crosswalk_sha256,
            True,
            rec.b3_record_fingerprint,
            dict(B6_TARGETS),
            dict(B6_TARGETS),
            dict(rec.checks),
            [],
            {},
            "1",
            rec.development_ids_sha256,
            rec.hoi_ids_sha256,
            rec.stamp,
        ).validate()


def test_G_site_display_shows_verified_counts_only_from_passed_real_b6(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(6))
    block = build_count_block(root, _raw(root))
    assert block["status"] == "VERIFIED_FROM_SOURCE"
    assert block["counts"] == B6_TARGETS


# ----- H. B7 locked until B6 passes
def test_H_b7_locked_until_b6_passes(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(5))
    raw = apply_transition(load_status(root).raw, "B6", "RUNNING")
    failed = apply_transition(raw, "B6", "FAILED", evidence="evidence/gate.md")
    validate_status(failed, root)
    assert next(g for g in failed["gates"] if g["id"] == "B7")["status"] == "LOCKED"
    root6 = make_status_repo(tmp_path / "repo6", closed=_b(6))
    assert load_status(root6).gate("B7").status == "AUTHORIZED"


# ----- I. no skipping
def test_I_no_transition_skips_earlier_gates(repo_root: Path, tmp_path: Path) -> None:
    raw = load_status(repo_root).raw
    for gid, new in (
        ("B3", "PASSED"),
        ("B3", "AUTHORIZED"),
        ("B6", "RUNNING"),
        ("B7", "AUTHORIZED"),
    ):
        with pytest.raises(ConfigError):
            apply_transition(raw, gid, new, evidence="x", on="2000-01-01")
    root = make_status_repo(tmp_path / "repo", closed=_b(3))  # B4 AUTHORIZED, B5 LOCKED
    with pytest.raises(ConfigError, match="prerequisites"):
        apply_transition(load_status(root).raw, "B5", "AUTHORIZED")
    with pytest.raises(ConfigError, match="earlier gate"):
        check_invariants(
            {"B1": "PASSED", "B2": "PASSED", "B3": "RUNNING", "B4": "PASSED", "B5": "LOCKED"}
        )


# ----- J. FAILED never silently PASSED
def test_J_failed_cannot_become_passed(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    raw = apply_transition(load_status(root).raw, "B2", "RUNNING")
    failed = apply_transition(raw, "B2", "FAILED", evidence="evidence/gate.md")
    for new in ("PASSED", "AUTHORIZED", "RUNNING"):
        with pytest.raises(ConfigError, match="illegal transition"):
            apply_transition(failed, "B2", new, evidence="x", on="2000-01-01")
    with pytest.raises(ConfigError, match="requires an evidence document"):
        apply_transition(failed, "B2", "BLOCKED")
    blocked = apply_transition(failed, "B2", "BLOCKED", evidence="evidence/gate.md")
    with pytest.raises(ConfigError, match="requires an evidence document"):
        apply_transition(blocked, "B2", "AUTHORIZED")
    reauth = apply_transition(blocked, "B2", "AUTHORIZED", evidence="evidence/gate.md")
    validate_status(reauth, root)
    raw_fail = _raw(root)
    next(g for g in raw_fail["gates"] if g["id"] == "B2").update(status="BLOCKED", evidence=None)
    with pytest.raises(ConfigError, match="without an evidence document"):
        validate_status(raw_fail, root)


# ----- K. source change invalidates evidence
def test_K_changed_source_invalidates_integrity_evidence(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(4))
    b2 = read_acquisition_record(root / "evidence/B2_record.json")
    b3 = read_metadata_record(root / "evidence/B3_record.json")
    b4 = read_metadata_record(root / "evidence/B4_record.json")
    xw = root / "fake_work" / "metadata" / b3.file.file_name
    ucsf = root / "fake_work" / "metadata" / b4.file.file_name
    h = sha256_file(xw)
    xw.write_bytes(xw.read_bytes() + b"!")  # one byte appended after B3
    assert sha256_file(xw) != h
    with pytest.raises(DataValidationError, match="changed after gate B3"):
        build_raw_manifest(
            root / "fake_work" / "images",
            FAKE_SCHEMA,
            b2,
            fake_stamp(),
            metadata=[(xw, b3), (ucsf, b4)],
        )


# ----- L. config change -> config hash change
def test_L_config_change_changes_config_hash(repo_root: Path, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("a: 1\n", encoding="utf-8")
    s1 = make_stamp(repo_root, require_clean_commit=False, config_files=[cfg], environment={})
    cfg.write_text("a: 2\n", encoding="utf-8")
    s2 = make_stamp(repo_root, require_clean_commit=False, config_files=[cfg], environment={})
    assert s1.config_sha256 != s2.config_sha256
    assert list(s1.config_sha256) == ["cfg.yaml"]  # never an absolute path


# ----- M. manifest change -> hash change
def test_M_manifest_content_change_changes_hash(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(5))
    doc = json.loads((root / "evidence/B5_manifest.json").read_text(encoding="utf-8"))
    h = content_sha256(doc)
    assert h == doc["manifest_sha256"]
    doc["files"][0]["size_bytes"] += 1
    assert content_sha256(doc) != h
    doc2 = json.loads((root / "evidence/B5_manifest.json").read_text(encoding="utf-8"))
    doc2["stamp"]["created_at"] = "2099-01-01T00:00:00+00:00"  # provenance-only change
    assert content_sha256(doc2) == h


# ----- N. synthetic never research data
def test_N_synthetic_never_presented_as_research(repo_root: Path, tmp_path: Path) -> None:
    rec = stage_acquire(
        repo_root,
        SyntheticFixtureAdapter(repo_root, n_cases=1),
        storage_root=tmp_path / "acq",
        out_record=tmp_path / "b2.json",
        acquired_by="t",
        execute=True,
    )
    assert isinstance(rec, AcquisitionRecord)
    body = read_record_body(tmp_path / "b2.json")
    assert body["data_class"] == "SYNTHETIC_TEST_DATA"
    body["data_class"] = "REAL_RESEARCH_DATA"  # relabelling attempt
    (tmp_path / "relabelled.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="fingerprint mismatch"):
        read_record_body(tmp_path / "relabelled.json")
    body["synthetic"] = False  # full relabel: fingerprint still breaks
    (tmp_path / "relabelled2.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ProvenanceError):
        read_record_body(tmp_path / "relabelled2.json")


def test_N_synthetic_tree_tricks_cannot_unlock_real_mode(repo_root: Path, tmp_path: Path) -> None:
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    marker = json.loads((ds.root / "SYNTHETIC_TEST_DATA.json").read_text(encoding="utf-8"))
    marker["label"] = "REAL_RESEARCH_DATA"
    (ds.root / "SYNTHETIC_TEST_DATA.json").write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(ProvenanceError, match="invalid SYNTHETIC_TEST_DATA marker"):
        require_synthetic([ds.crosswalk], repo_root)
    # real mode never consults markers for permission: still gate-blocked
    with pytest.raises(ResearchGateError):
        stage_hash_metadata(
            repo_root, "B3", ds.crosswalk, source_url=SYN_URL, doi="10.0/x", out=tmp_path / "o.json"
        )
    assert check_action("record_crosswalk_hash", repo_root)  # B3 LOCKED in the real state


# ---------------------------------------------------------------- transition writer
def test_transition_writer_rejects_inconsistent_current_state(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    text = (root / "docs/project_status.yaml").read_text(encoding="utf-8")
    broken = text.replace("  acquired: false", "  acquired: true", 1)
    (root / "docs/project_status.yaml").write_text(broken, encoding="utf-8")
    ev = write_b1_evidence(root)
    with pytest.raises(ConfigError, match="acquired"):
        write_transition(
            root, "B1", "PASSED", evidence=ev, on="2000-01-01", approved_route=FAKE_ROUTE
        )


def test_transition_writer_b1_evidence_rules(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    for ev in (
        "docs/data/B1_DATA_ROUTE_AUTHORIZATION.md",
        "docs/data/TCIA_DATA_ROUTE_INQUIRY.md",
        "evidence/gate.md",
    ):
        with pytest.raises(ConfigError, match="B1_EVIDENCE"):
            write_transition(
                root, "B1", "PASSED", evidence=ev, on="2000-01-01", approved_route=FAKE_ROUTE
            )
    ev = write_b1_evidence(root, route="SOME OTHER ROUTE")
    with pytest.raises(ConfigError, match="Approved route"):
        write_transition(
            root, "B1", "PASSED", evidence=ev, on="2000-01-01", approved_route=FAKE_ROUTE
        )
    for bad in ("../outside.md", "/abs/path.md", "C:/x.md", "docs/data/B1_EVIDENCE_x;rm.md"):
        with pytest.raises(ConfigError):
            write_transition(
                root, "B1", "PASSED", evidence=bad, on="2000-01-01", approved_route=FAKE_ROUTE
            )


def test_transition_writer_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    ev = write_b1_evidence(root)
    before = (root / "docs/project_status.yaml").read_bytes()

    def boom(*a: object, **k: object) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="simulated"):
        write_transition(
            root,
            "B1",
            "PASSED",
            evidence=ev,
            on="2000-01-01",
            approved_route=FAKE_ROUTE,
            apply=True,
        )
    assert (root / "docs/project_status.yaml").read_bytes() == before


def test_full_chain_transitions_in_fake_repo(tmp_path: Path) -> None:
    """End-to-end: B1..B6 pass on fake evidence only via explicit transitions; B7 then eligible."""
    root = make_verbatim_status_repo(tmp_path / "repo")
    chain = build_fake_chain(root)
    ev1 = write_b1_evidence(root)
    write_transition(
        root, "B1", "PASSED", evidence=ev1, on="2000-01-01", approved_route=FAKE_ROUTE, apply=True
    )
    for gid in ("B2", "B3", "B4", "B5", "B6"):
        assert load_status(root).gate("B7").status == "LOCKED"
        write_transition(root, gid, "RUNNING", apply=True)
        write_transition(root, gid, "PASSED", evidence=chain[gid], on="2000-01-01", apply=True)
    st = load_status(root)
    assert [st.gate(f"B{i}").status for i in range(1, 8)] == ["PASSED"] * 6 + ["AUTHORIZED"]
    assert st.raw["data"]["acquired"] is True
    assert all(st.gate(f"B{i}").status == "LOCKED" for i in range(8, 13))


# ---------------------------------------------------------------- edge cases
def test_malformed_status_fails_safely(pre_execution_root: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    base = _raw(repo_root)
    for mutate, msg in [
        (lambda r: r.update(gates={"B1": "PENDING"}), "gates must be a list"),
        (lambda r: r["gates"].append({"id": "B99"}), "malformed gate entry"),
        (lambda r: r["gates"].append("B13"), "malformed gate entry"),
        (lambda r: r.update(data="pending"), "data must be a mapping"),
        (lambda r: r.pop("training"), "missing key"),
        (
            lambda r: next(g for g in r["gates"] if g["id"] == "B3").update(closed_on="2000-01-01"),
            "closed_on but is not closed",
        ),
    ]:
        raw = json.loads(json.dumps(base))
        mutate(raw)
        with pytest.raises(ConfigError, match=msg):
            validate_status(raw, repo_root)


def test_manifest_edge_cases(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(5))
    good = json.loads((root / "evidence/B5_manifest.json").read_text(encoding="utf-8"))
    validate_manifest_doc(good)
    for mutate, msg in [
        (
            lambda d: d.update(files=[], summary={**d["summary"], "n_files": 0}),
            "empty raw manifest",
        ),
        (lambda d: d["files"][0].pop("sha256"), "file entry missing"),
        (lambda d: d["files"][0].update(relpath="../escape.nii.gz"), "non-relative"),
        (lambda d: d["files"][0].update(relpath="/abs.nii.gz"), "non-relative"),
        (lambda d: d.update(data_class="SYNTHETIC_TEST_DATA"), "data_class"),
        (lambda d: d["metadata_records"].update(B9={"x": 1}), "malformed metadata_records"),
        (lambda d: d.pop("stamp"), "missing required"),
    ]:
        d = json.loads(json.dumps(good))
        mutate(d)
        with pytest.raises(DataValidationError, match=msg):
            validate_manifest_doc(d)


def test_partial_json_and_records_fail_safely(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(2))
    text = (root / "evidence/B2_record.json").read_text(encoding="utf-8")
    (tmp_path / "partial.json").write_text(text[: len(text) // 2], encoding="utf-8")
    with pytest.raises(ValueError):
        read_record_body(tmp_path / "partial.json")
    body = json.loads(text)
    body.pop("stamp")
    (tmp_path / "nostamp.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ProvenanceError):
        read_record_body(tmp_path / "nostamp.json")


def test_interrupted_json_write_leaves_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: object, **k: object) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_json(tmp_path / "x.json", {"a": 1})
    assert list(tmp_path.iterdir()) == []


def _try_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip(
            "OS file-symlink creation not permitted here (Windows without "
            "SeCreateSymbolicLinkPrivilege/Developer Mode); runs on Linux CI. Same refusal "
            "logic covered by test_file_link_entries_refused_on_every_platform and the "
            "directory-junction tests in test_b2_b6_final_audit.py"
        )


# Link-safety coverage is split explicitly by link kind:
#  1. test_file_symlinks_refused_posix: a real OS FILE symlink. Creating one needs
#     SeCreateSymbolicLinkPrivilege / Developer Mode on Windows, so it is skipped on
#     unprivileged Windows accounts and runs on Linux CI (.github/workflows/ci.yml).
#  2. test_file_link_entries_refused_on_every_platform: the same refusal branches,
#     driven through the shared ``is_link`` hook, on every OS.
#  3. tests/unit/test_b2_b6_final_audit.py: real OS DIRECTORY links (symlink or
#     Windows junction) for deliveries, data trees, synthetic trees, storage roots
#     and write targets, which do run on Windows.
def test_file_symlinks_refused_posix(repo_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    delivered = tmp_path / "delivered"
    delivered.mkdir()
    _try_symlink(delivered / "link.bin", outside)
    with pytest.raises(DataValidationError, match="symbolic links"):
        LocalImportAdapter(fake_source(), delivered).plan()
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    _try_symlink(ds.root / "metadata" / "link.csv", outside)
    with pytest.raises(ProvenanceError, match="symbolic links"):
        require_synthetic([ds.root / "metadata"], repo_root)


def test_file_link_entries_refused_on_every_platform(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every refusal branch for a FILE link entry fires, independent of OS privileges."""
    import brats_uncertainty.data.acquisition as acq
    import brats_uncertainty.data.integrity as integ
    import brats_uncertainty.data.manifest_doc as mdoc
    import brats_uncertainty.data.records as recs
    import brats_uncertainty.data.synthetic as syn
    import brats_uncertainty.utils.io as uio
    from brats_uncertainty.data.integrity import validate_dataset_tree
    from brats_uncertainty.data.records import inventory

    link_names = {"link.bin", "link.csv", "FAKE-001_t2.nii.gz", "target.json"}

    def fake_is_link(p: object) -> bool:
        return Path(str(p)).name in link_names

    for mod in (acq, integ, mdoc, recs, syn, uio):
        monkeypatch.setattr(mod, "is_link", fake_is_link)
    delivered = tmp_path / "delivered"
    delivered.mkdir()
    (delivered / "ok.bin").write_bytes(b"ok")
    (delivered / "link.bin").write_bytes(b"pretend link")
    with pytest.raises(DataValidationError, match="symbolic links"):
        LocalImportAdapter(fake_source(), delivered).plan()
    with pytest.raises(ProvenanceError, match="symbolic link"):
        inventory(delivered)
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    (ds.root / "metadata" / "link.csv").write_bytes(b"pretend link")
    with pytest.raises(ProvenanceError, match="symbolic links"):
        require_synthetic([ds.root / "metadata"], repo_root)
    case = tmp_path / "tree" / "FAKE-001"
    case.mkdir(parents=True)
    (case / "FAKE-001_t2.nii.gz").write_bytes(b"pretend link")
    report = validate_dataset_tree(tmp_path / "tree", FAKE_SCHEMA)
    assert any(i.code == "link" and i.path.endswith("_t2.nii.gz") for i in report.issues)
    with pytest.raises(DataValidationError, match="symbolic links"):
        mdoc.build_raw_manifest(
            tmp_path / "tree",
            FAKE_SCHEMA,
            read_acquisition_record(build_and_get(make_status_repo(tmp_path / "r", closed=_b(2)))),
            fake_stamp(),
        )
    with pytest.raises(FileExistsError, match="link"):
        write_json(tmp_path / "target.json", {"x": 1}, overwrite=True)


def test_real_storage_must_be_ignored_location(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    d = tmp_path / "d.bin"
    d.write_bytes(b"x")
    with pytest.raises(ProvenanceError, match="git-ignored data/"):
        stage_acquire(
            root,
            LocalImportAdapter(fake_source(), d),
            storage_root=root / "docs" / "raw",
            out_record=tmp_path / "r.json",
            acquired_by="t",
            execute=True,
            require_clean_commit=False,
        )
    rec = stage_acquire(
        root,
        LocalImportAdapter(fake_source(), d),
        storage_root=root / "data" / "raw" / "x",
        out_record=tmp_path / "r.json",
        acquired_by="t",
        execute=True,
        require_clean_commit=False,
    )
    assert isinstance(rec, AcquisitionRecord)
    assert rec.storage_location == "data/raw/x"


def test_no_fabricated_timestamps_in_real_mode(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(2))
    f = tmp_path / "BraTS2021_MappingToTCIA.xlsx"
    f.write_bytes(b"x")
    with pytest.raises(ProvenanceError, match="custom clock"):
        stage_hash_metadata(
            root,
            "B3",
            f,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "o.json",
            path_reference="x",
            require_clean_commit=False,
            clock=lambda: FIXED,
        )
    d = tmp_path / "d.bin"
    d.write_bytes(b"x")
    root1 = make_status_repo(tmp_path / "repo1", closed=_b(1))
    with pytest.raises(ProvenanceError, match="custom clock"):
        stage_acquire(
            root1,
            LocalImportAdapter(fake_source(), d),
            storage_root=tmp_path / "s",
            out_record=tmp_path / "r.json",
            acquired_by="t",
            execute=True,
            storage_label="x",
            require_clean_commit=False,
            clock=lambda: FIXED,
        )


def test_evidence_from_uncommitted_or_foreign_code_rejected(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    raw = apply_transition(load_status(root).raw, "B2", "RUNNING")
    stamp = fake_stamp()
    for bad_stamp, msg in [
        ({**stamp.__dict__, "code_dirty": True}, "clean committed"),
        ({**stamp.__dict__, "code_commit": None}, "clean committed"),
        ({**stamp.__dict__, "protocol_sha256": "0" * 64}, "frozen protocol"),
    ]:
        from brats_uncertainty.data.records import ProvenanceStamp

        rec = AcquisitionRecord(
            "B2",
            False,
            fake_source(),
            "local-import",
            "2000-01-01T00:00:00+00:00",
            "t",
            "data/raw/x",
            (read_acquisition_record(build_and_get(root))).inventory,
            ProvenanceStamp(**bad_stamp),
        )
        rel = f"evidence/B2_{abs(hash(msg)) % 1000}.json"
        if (root / rel).exists():
            (root / rel).unlink()
        write_record(root / rel, rec)
        bad = apply_transition(raw, "B2", "PASSED", evidence=rel, on="2000-01-01")
        with pytest.raises(ConfigError, match=msg):
            validate_status(bad, root)


def build_and_get(root: Path) -> Path:
    p = root / "evidence" / "B2_record.json"
    if not p.exists():
        build_fake_chain(root)
    return p


# ---------------------------------------------------------------- round trips
def test_round_trips(repo_root: Path, tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(6))
    for reader, name in (
        (read_acquisition_record, "B2_record.json"),
        (read_metadata_record, "B3_record.json"),
        (read_metadata_record, "B4_record.json"),
        (read_counts_record, "B6_record.json"),
    ):
        obj = reader(root / "evidence" / name)
        write_record(tmp_path / f"rt_{name}", obj)
        assert reader(tmp_path / f"rt_{name}") == obj
        assert (
            read_record_body(tmp_path / f"rt_{name}")["record_fingerprint"]
            == json.loads((root / "evidence" / name).read_text(encoding="utf-8"))[
                "record_fingerprint"
            ]
        )
    doc = json.loads((root / "evidence/B5_manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader(io.StringIO(manifest_to_csv(doc))))
    assert len(rows) == len(doc["files"])
    for row, f in zip(rows, doc["files"], strict=True):
        for k in CSV_COLUMNS:
            expected = "" if f[k] is None else str(f[k])
            assert row[k] == expected
    again = json.loads(json.dumps(doc))
    validate_manifest_doc(again)
    assert again == doc


def test_manifest_is_deterministic(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(4))
    b2 = read_acquisition_record(root / "evidence/B2_record.json")
    b3 = read_metadata_record(root / "evidence/B3_record.json")
    b4 = read_metadata_record(root / "evidence/B4_record.json")
    meta = root / "fake_work" / "metadata"
    args = (root / "fake_work" / "images", FAKE_SCHEMA, b2, fake_stamp())
    kw = {"metadata": [(meta / b3.file.file_name, b3), (meta / b4.file.file_name, b4)]}
    d1 = build_raw_manifest(*args, **kw)  # type: ignore[arg-type]
    d2 = build_raw_manifest(*args, metadata=list(reversed(kw["metadata"])))  # type: ignore[arg-type]
    assert d1["manifest_sha256"] == build_raw_manifest(*args, **kw)["manifest_sha256"]  # type: ignore[arg-type]
    assert d1["duplicates"] == d2["duplicates"]
    assert d1["metadata_records"] == d2["metadata_records"]


# ---------------------------------------------------------------- hashing
def test_hash_exactness_and_no_placeholder_hashes(repo_root: Path, tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    a.write_bytes(b"\x00\x01\x02")
    h1 = sha256_file(a)
    a.write_bytes(b"\x00\x01\x02")
    assert sha256_file(a) == h1  # same bytes, same hash
    a.write_bytes(b"\x00\x01\x03")
    assert sha256_file(a) != h1  # one byte changed
    assert h1 == sha256_bytes(b"\x00\x01\x02")
    with pytest.raises(ProvenanceError):  # records reject malformed/placeholder-shaped hashes
        SourceInfo("d", "v", "10.1/x", "https://x.invalid", "r").validate() or AcquisitionRecord(
            "B2",
            False,
            fake_source(),
            "a",
            "2000-01-01T00:00:00+00:00",
            "t",
            "x",
            (),
            fake_stamp(),
        ).validate()
    tracked = (repo_root / "docs").rglob("*")
    for p in tracked:
        if p.is_file() and p.suffix in (".md", ".yaml", ".json"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            assert "0" * 64 not in text and "deadbeef" not in text.lower(), p


# ---------------------------------------------------------------- repository checks
def test_repo_check_sniffs_imaging_content_regardless_of_name(tmp_path: Path) -> None:
    from brats_uncertainty.data.synthetic import write_nifti_header_file

    nii = write_nifti_header_file(tmp_path / "x.nii.gz")
    disguised = tmp_path / "notes.txt"
    disguised.write_bytes(nii.read_bytes())
    dicom = tmp_path / "scan.md"
    dicom.write_bytes(b"\x00" * 128 + b"DICM" + b"\x00" * 64)
    raw_nifti = tmp_path / "vol.dat"
    import gzip

    raw_nifti.write_bytes(gzip.decompress(nii.read_bytes()))
    assert sniff_imaging(disguised) is not None
    assert sniff_imaging(dicom) == "DICOM content"
    assert sniff_imaging(raw_nifti) == "NIfTI-1 content"
    found = {f.path for f in check_paths(["notes.txt", "scan.md", "vol.dat"], tmp_path)}
    assert found == {"notes.txt", "scan.md", "vol.dat"}


def test_https_adapter_rejects_path_traversal() -> None:
    for rel in ("../x.csv", "/abs.csv"):
        with pytest.raises(ProvenanceError, match="relative"):
            HttpsFileAdapter(fake_source(), {rel: "https://example.org/x.csv"})
    assert "urlopen" in acq_mod._https_open.__code__.co_names  # the only network call, gated


def test_safe_relpath_is_platform_independent() -> None:
    from brats_uncertainty.data.records import _check_location
    from brats_uncertainty.utils.paths import is_safe_relpath

    for ok in ("data/raw/x", "metadata/BraTS2021_MappingToTCIA.xlsx", "a.json"):
        assert is_safe_relpath(ok), ok
    bs = chr(92)
    for bad in (
        "",
        "/abs",
        bs + "abs",
        "C:/x",
        "c:x",
        "a/../b",
        "..",
        "./a",
        "a//b",
        "a" + bs + "b",
        bs * 2 + "srv/share",
    ):
        assert not is_safe_relpath(bad), bad
    for bad_loc in ("/abs", "C:/" + "Users/x", "data/..", "../up", "data/./x"):
        with pytest.raises(ProvenanceError):
            _check_location(bad_loc)
    _check_location("SYNTHETIC_TEST_DATA (temporary, outside repository)")
    _check_location("data/raw/brats2021")


def test_documentation_never_claims_b1_to_b6_complete(repo_root: Path) -> None:
    import re

    docs = [
        "docs/data/DATA_ACCESS.md",
        "docs/data/DATA_PROVENANCE.md",
        "docs/data/B1_DATA_ROUTE_AUTHORIZATION.md",
        "docs/data/TCIA_DATA_ROUTE_INQUIRY.md",
        "docs/reproducibility/REPRODUCIBILITY.md",
        "README.md",
        "data/README.md",
    ]
    # B1 is authorized (owner-approved alternative); B2-B6 must never be claimed complete
    claim = re.compile(
        r"(?i)\bB[2-6]\b\s*(?:=|:|is|has)\s*(?:now\s+)?(?:passed|closed|complete|completed|approved|verified)\b"
    )
    for rel in docs:
        text = (repo_root / rel).read_text(encoding="utf-8")
        assert not claim.search(text), (rel, claim.search(text))
    tcia_claim = re.compile(r"(?i)\bTCIA\s+(?:has\s+)?(?:approved|authori[sz]ed)\b")
    for rel in (
        "docs/data/DATA_ACCESS.md",
        "docs/data/DATA_PROVENANCE.md",
        "docs/data/B1_DATA_ROUTE_AUTHORIZATION.md",
        "docs/data/B1_EVIDENCE_2026-10-01.md",
        "README.md",
    ):
        text = (repo_root / rel).read_text(encoding="utf-8")
        assert "owner-approved alternative" in text.lower(), rel
        assert not tcia_claim.search(text), rel
        assert "no data" in text.lower() or "not executed" in text.lower(), rel
    assert (
        "not sent"
        in (repo_root / "docs/data/TCIA_DATA_ROUTE_INQUIRY.md").read_text(encoding="utf-8").lower()
    )
    for page in (repo_root / "website").rglob("*.tsx"):
        if "node_modules" in page.parts:
            continue
        text = page.read_text(encoding="utf-8")
        for hard_coded in (
            "No study data have been acquired",
            "no model has been trained",
            "Verified dataset counts",
        ):
            assert hard_coded not in text, (page, hard_coded)
