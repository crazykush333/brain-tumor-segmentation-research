"""Official nested BraTS 2021 layout (<collection>/<case_id>/), provider checksums, disk preflight.

SYNTHETIC trees only (tests/fixtures/nested_layout.py, pytest temporary
directories). The real project state is read-only here: B2 stays AUTHORIZED.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.cli import main
from brats_uncertainty.data import preflight as preflight_mod
from brats_uncertainty.data.acquisition import (
    LocalImportAdapter,
    SyntheticFixtureAdapter,
    stage_acquire,
)
from brats_uncertainty.data.checksums import parse_checksum_file, verify_checksums
from brats_uncertainty.data.integrity import validate_dataset_tree
from brats_uncertainty.data.layout import discover_cases
from brats_uncertainty.data.manifest_doc import (
    build_raw_manifest,
    manifest_to_csv,
    validate_manifest_doc,
)
from brats_uncertainty.data.preflight import GIB, require_free_space, storage_preflight
from brats_uncertainty.data.records import (
    CROSSWALK_FILENAME,
    UCSF_METADATA_FILENAME,
    AcquisitionRecord,
    inventory,
)
from brats_uncertainty.data.stages import (
    stage_build_manifest,
    stage_validate_data,
    stage_verify_checksums,
)
from brats_uncertainty.errors import DataValidationError, ProvenanceError, ResearchGateError
from brats_uncertainty.evaluation.status import load_status
from tests.conftest import FAKE_ROUTE, make_status_repo, make_verbatim_status_repo
from tests.fixtures.fake_evidence import fake_source, fake_stamp
from tests.fixtures.nested_layout import (
    DEFAULT_TREE,
    NESTED_SCHEMA,
    make_nested_training_tree,
    write_case,
)

COLLECTIONS = ("ACRIN-FMISO-Brain", "UCSF-PDGM", "UPENN-GBM")


def _codes(issues) -> set[str]:  # type: ignore[no-untyped-def]
    return {i.code for i in issues}


def _dir_link(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    pytest.skip("cannot create directory links on this system")


def _acq(root: Path) -> AcquisitionRecord:
    return AcquisitionRecord(
        gate="B2",
        synthetic=False,
        source=fake_source(),
        adapter="local-import",
        acquired_at="2000-01-01T00:00:00+00:00",
        acquired_by="pytest",
        storage_location="FAKE storage",
        inventory=inventory(root),
        stamp=fake_stamp(),
    )


# ================================================================ discovery
def test_nested_cases_discovered_with_collections_and_paths(tmp_path: Path) -> None:
    root = make_nested_training_tree(tmp_path / "BraTS2021_TrainingSet")
    found = discover_cases(root, NESTED_SCHEMA)
    assert not found.errors
    assert found.layout == "nested_collections"
    assert [(c.collection, c.case_id, c.relpath) for c in found.cases] == [
        ("ACRIN-FMISO-Brain", "BraTS2021_SYNTH001", "ACRIN-FMISO-Brain/BraTS2021_SYNTH001"),
        ("UCSF-PDGM", "BraTS2021_SYNTH002", "UCSF-PDGM/BraTS2021_SYNTH002"),
        ("UPENN-GBM", "BraTS2021_SYNTH003", "UPENN-GBM/BraTS2021_SYNTH003"),
    ]
    assert found.collections == dict.fromkeys(COLLECTIONS, 1)


def test_discovery_order_is_deterministic(tmp_path: Path) -> None:
    tree = {"UPENN-GBM": ("BraTS2021_SYNTH009", "BraTS2021_SYNTH004"), **DEFAULT_TREE}
    a = discover_cases(make_nested_training_tree(tmp_path / "a", tree), NESTED_SCHEMA)
    b = discover_cases(make_nested_training_tree(tmp_path / "b", tree, reverse=True), NESTED_SCHEMA)
    order = [c.relpath for c in a.cases]
    assert order == [c.relpath for c in b.cases] == sorted(order)


def test_duplicate_case_id_across_collections_detected(tmp_path: Path) -> None:
    root = make_nested_training_tree(tmp_path / "t")
    write_case(root / "UCSF-PDGM" / "BraTS2021_SYNTH001", "BraTS2021_SYNTH001")
    found = discover_cases(root, NESTED_SCHEMA)
    dup = [i for i in found.errors if i.code == "duplicate_case_id"]
    assert len(dup) == 1
    assert dup[0].path == "UCSF-PDGM/BraTS2021_SYNTH001"
    assert "ACRIN-FMISO-Brain/BraTS2021_SYNTH001" in dup[0].message
    with pytest.raises(DataValidationError, match="duplicate_case_id"):
        build_raw_manifest(root, NESTED_SCHEMA, _acq(root), fake_stamp())


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda r: (r / "UCSF-PDGM" / "notacase").mkdir(), "unexpected_nested_structure"),
        (
            lambda r: write_case(
                r / "UCSF-PDGM" / "deeper" / "BraTS2021_SYNTH007", "BraTS2021_SYNTH007"
            ),
            "unexpected_nested_structure",
        ),
        (lambda r: write_case(r / "not a case", "BraTS2021_SYNTH008"), "malformed_case_dir"),
        (lambda r: (r / "EMPTY-COLLECTION").mkdir(), "empty_collection"),
        (lambda r: (r / "bad name!").mkdir(), "invalid_collection_name"),
        (lambda r: write_case(r / "BraTS2021_SYNTH005", "BraTS2021_SYNTH005"), "mixed_layout"),
    ],
)
def test_malformed_structures_are_errors(tmp_path: Path, mutate, code: str) -> None:  # type: ignore[no-untyped-def]
    root = make_nested_training_tree(tmp_path / "t")
    mutate(root)
    assert code in _codes(discover_cases(root, NESTED_SCHEMA).errors)
    report = validate_dataset_tree(root, NESTED_SCHEMA, deep=True)
    assert code in _codes(report.errors) and not report.ok
    with pytest.raises(DataValidationError):
        build_raw_manifest(root, NESTED_SCHEMA, _acq(root), fake_stamp())


def test_subdirectory_inside_case_is_an_error(tmp_path: Path) -> None:
    root = make_nested_training_tree(tmp_path / "t")
    (root / "UCSF-PDGM" / "BraTS2021_SYNTH002" / "extra").mkdir()
    report = validate_dataset_tree(root, NESTED_SCHEMA)
    assert "unexpected_nested_structure" in _codes(report.errors)
    with pytest.raises(DataValidationError, match="subdirectories inside a case"):
        build_raw_manifest(root, NESTED_SCHEMA, _acq(root), fake_stamp())


def test_missing_modality_reported_with_nested_path(tmp_path: Path) -> None:
    root = make_nested_training_tree(tmp_path / "t")
    (root / "UCSF-PDGM" / "BraTS2021_SYNTH002" / "BraTS2021_SYNTH002_t2.nii.gz").unlink()
    report = validate_dataset_tree(root, NESTED_SCHEMA)
    miss = [i for i in report.errors if i.code == "missing_modality"]
    assert [i.path for i in miss] == ["UCSF-PDGM/BraTS2021_SYNTH002/BraTS2021_SYNTH002_t2.nii.gz"]


def test_corrupt_file_and_expected_case_ids(tmp_path: Path) -> None:
    root = make_nested_training_tree(tmp_path / "t")
    f = root / "UPENN-GBM" / "BraTS2021_SYNTH003" / "BraTS2021_SYNTH003_flair.nii.gz"
    f.write_bytes(f.read_bytes()[:10])
    report = validate_dataset_tree(
        root, NESTED_SCHEMA, expected_case_ids=["BraTS2021_SYNTH001", "BraTS2021_SYNTH099"]
    )
    assert {"corrupt_file", "missing_case", "unexpected_case"} <= _codes(report.errors)


@pytest.mark.parametrize("where", ["collection", "case"])
def test_linked_directories_fail(tmp_path: Path, where: str) -> None:
    root = make_nested_training_tree(tmp_path / "t")
    acq = _acq(root)  # recorded before the link appears (the inventory itself refuses links)
    outside = tmp_path / "outside" / "BraTS2021_SYNTH006"
    write_case(outside, "BraTS2021_SYNTH006")
    if where == "collection":
        _dir_link(root / "LINKED-COLLECTION", outside.parent)
    else:
        _dir_link(root / "UCSF-PDGM" / "BraTS2021_SYNTH006", outside)
    assert "link" in _codes(discover_cases(root, NESTED_SCHEMA).errors)
    assert "link" in _codes(validate_dataset_tree(root, NESTED_SCHEMA).errors)
    with pytest.raises(DataValidationError, match="link"):
        build_raw_manifest(root, NESTED_SCHEMA, acq, fake_stamp())
    with pytest.raises(ProvenanceError, match="symbolic link"):
        inventory(root)


def test_configured_layout_is_enforced(tmp_path: Path) -> None:
    nested = make_nested_training_tree(tmp_path / "n")
    flat = tmp_path / "f"
    write_case(flat / "BraTS2021_SYNTH001", "BraTS2021_SYNTH001")
    assert validate_dataset_tree(nested, NESTED_SCHEMA, expected_layout="nested_collections").ok
    r = validate_dataset_tree(flat, NESTED_SCHEMA, expected_layout="nested_collections")
    assert "unexpected_layout" in _codes(r.errors)  # a flattened copy is refused


def test_real_dataset_config_requires_the_nested_layout(repo_root: Path) -> None:
    cfg = yaml.safe_load((repo_root / "configs/dataset/brats2021.yaml").read_text(encoding="utf-8"))
    assert cfg["layout"]["tree"] == "nested_collections"


# ================================================================ manifest
def test_nested_manifest_preserves_collection_provenance(tmp_path: Path) -> None:
    root = make_nested_training_tree(tmp_path / "BraTS2021_TrainingSet")
    doc = build_raw_manifest(
        root,
        NESTED_SCHEMA,
        _acq(root),
        fake_stamp(),
        data_root_reference="RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet",
    )
    validate_manifest_doc(doc)
    assert doc["schema_version"] == 3
    assert doc["source_layout"] == {
        "layout": "nested_collections",
        "collections": dict.fromkeys(COLLECTIONS, 1),
        "data_root_reference": "RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet",
    }
    case = next(c for c in doc["cases"] if c["case_id"] == "BraTS2021_SYNTH002")
    assert case["collection"] == "UCSF-PDGM"
    assert case["relative_case_path"] == "UCSF-PDGM/BraTS2021_SYNTH002"
    assert (
        case["modalities"]["T1c"] == "UCSF-PDGM/BraTS2021_SYNTH002/BraTS2021_SYNTH002_t1ce.nii.gz"
    )
    assert case["label"] == "UCSF-PDGM/BraTS2021_SYNTH002/BraTS2021_SYNTH002_seg.nii.gz"
    assert case["n_files"] == 5
    for f in doc["files"]:
        assert f["relpath"].startswith(f"{f['collection']}/{f['case_id']}/")  # not flattened
    assert manifest_to_csv(doc).splitlines()[0].startswith("collection,case_id,")
    assert "UCSF-PDGM,BraTS2021_SYNTH002,image,T1," in manifest_to_csv(doc)


def test_nested_manifest_is_deterministic(tmp_path: Path) -> None:
    a = make_nested_training_tree(tmp_path / "a" / "BraTS2021_TrainingSet")
    b = make_nested_training_tree(tmp_path / "b" / "BraTS2021_TrainingSet", reverse=True)
    acq = _acq(a)
    da = build_raw_manifest(a, NESTED_SCHEMA, acq, fake_stamp(), data_root_reference="x")
    db = build_raw_manifest(b, NESTED_SCHEMA, acq, fake_stamp(), data_root_reference="x")
    assert da["manifest_sha256"] == db["manifest_sha256"]
    assert json.dumps(da, sort_keys=True) == json.dumps(db, sort_keys=True)


@pytest.mark.parametrize(
    ("mutate", "msg"),
    [
        (lambda d: d["files"][0].update(collection="UPENN-GBM"), "does not match its collection"),
        (lambda d: d["files"][0].update(collection="a/b"), "invalid collection"),
        (lambda d: d["files"][0].update(collection=".."), "invalid collection"),
        (lambda d: d["files"][0].update(relpath="../escape.nii.gz"), "non-relative"),
        (lambda d: d["cases"][0].update(relative_case_path="BraTS2021_SYNTH001"), "cases table"),
        (lambda d: d["source_layout"].update(layout="flat"), "layout inconsistent"),
        (lambda d: d["source_layout"].update(collections={}), "collections inconsistent"),
        (lambda d: d["source_layout"].update(data_root_reference="/abs"), "safe relative"),
        (lambda d: d["source_layout"].pop("collections"), "malformed source_layout"),
    ],
)
def test_nested_manifest_tampering_rejected(tmp_path: Path, mutate, msg: str) -> None:  # type: ignore[no-untyped-def]
    root = make_nested_training_tree(tmp_path / "t")
    doc = build_raw_manifest(root, NESTED_SCHEMA, _acq(root), fake_stamp(), data_root_reference="r")
    mutate(doc)
    with pytest.raises(DataValidationError, match=msg):
        validate_manifest_doc(doc)


# ================================================================ synthetic stages (end to end)
def _syn_cfg(repo_root: Path, tmp_path: Path) -> Path:
    cfg = yaml.safe_load((repo_root / "configs/dataset/brats2021.yaml").read_text(encoding="utf-8"))
    cfg["layout"]["case_id_pattern"] = r"SYN-\d{4}"
    assert cfg["layout"]["tree"] == "nested_collections"  # same layout rule as the real config
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


def test_synthetic_nested_b2_b5_preserves_hierarchy(repo_root: Path, tmp_path: Path) -> None:
    store = tmp_path / "acq"
    rec = stage_acquire(
        repo_root,
        SyntheticFixtureAdapter(repo_root, n_cases=4, collections=COLLECTIONS),
        storage_root=store,
        out_record=tmp_path / "B2.json",
        acquired_by="pytest",
        execute=True,
    )
    assert isinstance(rec, AcquisitionRecord)
    assert any(e.relpath.startswith("images/UCSF-PDGM/SYN-0001/") for e in rec.inventory)
    cfg = _syn_cfg(repo_root, tmp_path)
    report = stage_validate_data(repo_root, cfg, store / "images", synthetic=True)
    assert report.ok and report.layout == "nested_collections"
    assert report.collections == {"ACRIN-FMISO-Brain": 2, "UCSF-PDGM": 1, "UPENN-GBM": 1}
    doc = stage_build_manifest(
        repo_root,
        cfg,
        store / "images",
        tmp_path / "B2.json",
        tmp_path / "B5.json",
        data_root_reference="images",
        synthetic=True,
    )
    assert doc["synthetic"] is True and doc["data_class"] == "SYNTHETIC_TEST_DATA"
    assert [c["relative_case_path"] for c in doc["cases"]] == [
        "ACRIN-FMISO-Brain/SYN-0000",
        "ACRIN-FMISO-Brain/SYN-0003",
        "UCSF-PDGM/SYN-0001",
        "UPENN-GBM/SYN-0002",
    ]
    # B5 <-> B2: a wrong reference means the files are not the acquired ones
    with pytest.raises(ProvenanceError, match="not in the B2 inventory"):
        stage_build_manifest(
            repo_root,
            cfg,
            store / "images",
            tmp_path / "B2.json",
            tmp_path / "B5b.json",
            data_root_reference="elsewhere",
            synthetic=True,
        )


def test_real_b5_requires_a_data_root_reference(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed={"B1", "B2", "B3", "B4"})  # FAKE chain
    meta = root / "fake_work" / "metadata"
    with pytest.raises(ProvenanceError, match="data-root-reference"):
        stage_build_manifest(
            root,
            root / "configs/dataset/brats2021.yaml",
            root / "fake_work" / "images",
            root / "evidence/B2_record.json",
            tmp_path / "B5.json",
            metadata_files=[meta / CROSSWALK_FILENAME, meta / UCSF_METADATA_FILENAME],
            metadata_records=[root / "evidence/B3_record.json", root / "evidence/B4_record.json"],
            require_clean_commit=False,
        )
    assert not (tmp_path / "B5.json").exists()


def test_nested_synthetic_tree_refused_by_real_import(tmp_path: Path, repo_root: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed={"B1"})
    syn = tmp_path / "syn"
    stage_acquire(
        repo_root,
        SyntheticFixtureAdapter(repo_root, n_cases=2, collections=COLLECTIONS),
        storage_root=syn,
        out_record=tmp_path / "S.json",
        acquired_by="pytest",
        execute=True,
    )
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_DATA cannot be acquired"):
        stage_acquire(
            root,
            LocalImportAdapter(fake_source(), syn),
            storage_root=tmp_path / "store",
            out_record=tmp_path / "B2.json",
            acquired_by="pytest",
            execute=True,
            storage_label="x",
            require_clean_commit=False,
        )


# ======================================================= B2 local import keeps the hierarchy
def _official_delivery(base: Path) -> Path:
    make_nested_training_tree(base / "RSNA-ASNR-MICCAI-BraTS-2021" / "BraTS2021_TrainingSet")
    (base / "BraTS2021_MappingToTCIA.xlsx").write_bytes(b"FAKE crosswalk bytes")
    (base / "UCSF-PDGM-metadata_v5.csv").write_bytes(b"FAKE,csv\r\n")
    return base


def test_local_import_preserves_official_hierarchy(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed={"B1"})  # FAKE repo: B2 AUTHORIZED
    delivery = _official_delivery(tmp_path / "delivery")
    adapter = LocalImportAdapter(fake_source(), delivery)
    assert "official hierarchy preserved" in adapter.plan().describe()
    rec = stage_acquire(
        root,
        adapter,
        storage_root=tmp_path / "store",
        out_record=tmp_path / "B2.json",
        acquired_by="pytest",
        execute=True,
        storage_label="FAKE private storage",
        require_clean_commit=False,
    )
    assert isinstance(rec, AcquisitionRecord)
    rel = "RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet/UCSF-PDGM/BraTS2021_SYNTH002"
    assert (tmp_path / "store" / rel / "BraTS2021_SYNTH002_seg.nii.gz").is_file()
    src = sorted(p.relative_to(delivery).as_posix() for p in delivery.rglob("*") if p.is_file())
    assert [e.relpath for e in rec.inventory] == src  # byte-for-byte, same paths, nothing renamed
    for e in rec.inventory:
        assert (tmp_path / "store" / e.relpath).read_bytes() == (delivery / e.relpath).read_bytes()


def test_local_import_fails_closed_without_disk_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_status_repo(tmp_path / "repo", closed={"B1"})
    delivery = _official_delivery(tmp_path / "delivery")
    real = shutil.disk_usage
    monkeypatch.setattr(
        preflight_mod.shutil,
        "disk_usage",
        lambda p: real(p)._replace(free=10),  # 10 bytes free
    )
    with pytest.raises(DataValidationError, match="insufficient disk space"):
        stage_acquire(
            root,
            LocalImportAdapter(fake_source(), delivery),
            storage_root=tmp_path / "store",
            out_record=tmp_path / "B2.json",
            acquired_by="pytest",
            execute=True,
            storage_label="x",
            require_clean_commit=False,
        )
    store = tmp_path / "store"
    assert not any(store.rglob("*")) and not (tmp_path / "B2.json").exists()


# ================================================================ provider checksums
def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def _sums_fixture(tmp_path: Path, newline: bytes = b"\n") -> tuple[Path, Path]:
    base = _official_delivery(tmp_path / "delivery")
    pkg = "RSNA-ASNR-MICCAI-BraTS-2021"
    lines = []
    for p in sorted((base / pkg).rglob("*")):
        if p.is_file():
            lines.append(f"{_md5(p.read_bytes())}  {p.relative_to(base).as_posix()}".encode())
    lines.append(f"{'0' * 32}  {pkg}/BraTS2021_ValidationSet/x/y.nii.gz".encode())  # not selected
    sums = base / f"{pkg}.sums"
    sums.write_bytes(newline.join(lines) + newline)
    return sums, base


SELECT = "RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet"


@pytest.mark.parametrize(("newline", "endings"), [(b"\n", "LF"), (b"\r\n", "CRLF")])
def test_checksum_file_used_exactly_as_delivered(
    tmp_path: Path, newline: bytes, endings: str
) -> None:
    sums, base = _sums_fixture(tmp_path, newline)
    before = sums.read_bytes()
    parsed = parse_checksum_file(sums)
    assert sums.read_bytes() == before  # never rewritten
    assert parsed.sha256 == hashlib.sha256(before).hexdigest()  # hash of the raw bytes
    assert parsed.line_endings == endings and parsed.algorithms == ("md5",)
    report = verify_checksums(parsed, base, prefix=SELECT)
    assert report.ok
    assert (report.n_selected, report.n_verified, report.n_not_selected) == (15, 15, 1)


def test_checksum_formats_gnu_binary_and_bsd(tmp_path: Path) -> None:
    f = tmp_path / "a" / "x.bin"
    f.parent.mkdir()
    f.write_bytes(b"abc")
    sums = tmp_path / "s.sums"
    sha = hashlib.sha256(b"abc").hexdigest()
    sums.write_bytes(f"{_md5(b'abc')} *./a/x.bin\n".encode())
    assert verify_checksums(parse_checksum_file(sums), tmp_path, prefix="a").ok
    sums2 = tmp_path / "s2.sums"
    sums2.write_bytes(f"SHA256 (a/x.bin) = {sha.upper()}\n".encode())
    parsed = parse_checksum_file(sums2)
    assert parsed.entries[0].algorithm == "sha256" and parsed.entries[0].digest == sha
    assert verify_checksums(parsed, tmp_path, prefix="a").ok


def test_checksum_verification_detects_problems(tmp_path: Path) -> None:
    sums, base = _sums_fixture(tmp_path)
    case = base / SELECT / "UCSF-PDGM" / "BraTS2021_SYNTH002"
    (case / "BraTS2021_SYNTH002_t1.nii.gz").write_bytes(b"tampered")
    (case / "BraTS2021_SYNTH002_t2.nii.gz").unlink()
    (case / "extra.txt").write_bytes(b"not listed")
    report = verify_checksums(parse_checksum_file(sums), base, prefix=SELECT)
    assert not report.ok
    assert report.mismatched == [
        f"{SELECT}/UCSF-PDGM/BraTS2021_SYNTH002/BraTS2021_SYNTH002_t1.nii.gz"
    ]
    assert report.missing == [f"{SELECT}/UCSF-PDGM/BraTS2021_SYNTH002/BraTS2021_SYNTH002_t2.nii.gz"]
    assert report.unlisted == [f"{SELECT}/UCSF-PDGM/BraTS2021_SYNTH002/extra.txt"]


def test_checksum_verification_reports_links(tmp_path: Path) -> None:
    sums, base = _sums_fixture(tmp_path)
    outside = tmp_path / "outside"
    write_case(outside, "BraTS2021_SYNTH001")
    _dir_link(base / SELECT / "LINKED", outside)
    report = verify_checksums(parse_checksum_file(sums), base, prefix=SELECT)
    assert not report.ok and report.links


@pytest.mark.parametrize(
    ("content", "msg"),
    [
        (b"not a checksum line\n", "unrecognized format"),
        (b"\\abc  escaped\n", "unrecognized format"),
        (b"0123  short\n", "unrecognized format"),
        (b"d41d8cd98f00b204e9800998ecf8427e  ../escape\n", "unsafe"),
        (b"d41d8cd98f00b204e9800998ecf8427e  /abs/path\n", "unsafe"),
        (b"d41d8cd98f00b204e9800998ecf8427e  C:/x\n", "drive-letter|unsafe"),
        (b"d41d8cd98f00b204e9800998ecf8427e  a\\b\n", "unsafe"),
        (b"MD5 (a) = " + b"0" * 64 + b"\n", "digest length"),
        (
            b"d41d8cd98f00b204e9800998ecf8427e  a\nd41d8cd98f00b204e9800998ecf8427e  a\n",
            "duplicate",
        ),
        (b"\n\n", "no checksum entries"),
        (b"\xff\xfe  bad\n", "not UTF-8"),
    ],
)
def test_checksum_parser_fails_closed(tmp_path: Path, content: bytes, msg: str) -> None:
    sums = tmp_path / "x.sums"
    sums.write_bytes(content)
    with pytest.raises(DataValidationError, match=msg):
        parse_checksum_file(sums)


def test_checksum_prefix_rules(tmp_path: Path) -> None:
    sums, base = _sums_fixture(tmp_path)
    parsed = parse_checksum_file(sums)
    with pytest.raises(DataValidationError, match="no checksum entries under"):
        verify_checksums(parsed, base, prefix="RSNA-ASNR-MICCAI-BraTS-2021/Nothing")
    with pytest.raises(DataValidationError, match="safe relative"):
        verify_checksums(parsed, base, prefix="../outside")


def test_checksum_stage_is_gated(tmp_path: Path) -> None:
    sums, base = _sums_fixture(tmp_path)
    pending = make_verbatim_status_repo(tmp_path / "pending")
    with pytest.raises(ResearchGateError):
        stage_verify_checksums(pending, sums, base, prefix=SELECT, out=tmp_path / "r.json")
    assert not (tmp_path / "r.json").exists()


def test_checksum_stage_writes_report_and_fails_closed(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed={"B1"})  # FAKE repo: B2 AUTHORIZED
    sums, base = _sums_fixture(tmp_path)
    rep = stage_verify_checksums(
        root, sums, base, prefix=SELECT, out=tmp_path / "ok.json", require_clean_commit=False
    )
    assert rep.ok
    saved = json.loads((tmp_path / "ok.json").read_text(encoding="utf-8"))
    assert saved["ok"] is True and saved["checksum_file_sha256"] == rep.checksum_file_sha256
    (
        base / SELECT / "UPENN-GBM" / "BraTS2021_SYNTH003" / "BraTS2021_SYNTH003_t1.nii.gz"
    ).write_bytes(b"x")
    with pytest.raises(DataValidationError, match="1 mismatched"):
        stage_verify_checksums(
            root, sums, base, prefix=SELECT, out=tmp_path / "bad.json", require_clean_commit=False
        )
    assert json.loads((tmp_path / "bad.json").read_text(encoding="utf-8"))["ok"] is False


# ================================================================ disk-space preflight
def test_storage_preflight_same_and_separate_drives(tmp_path: Path) -> None:
    key = preflight_mod._drive_key(tmp_path)
    same = storage_preflight(
        20 * GIB,
        delivery_dir=tmp_path / "d",
        storage_dir=tmp_path / "s",
        free_bytes={key: 60 * GIB},
    )
    # download + import copy on one drive, each = (selection + metadata allowance) x 1.1,
    # plus the 10 GiB reserve: about 54 GiB <= 60
    meta = preflight_mod.DEFAULT_METADATA_BYTES
    assert same.ok and same.metadata_bytes == meta > 0
    assert same.drives[0].needed_bytes == 2 * int((20 * GIB + meta) * 1.1) + 10 * GIB
    # the metadata allowance is counted: a selection that just fits without it fails with it
    edge = int((60 * GIB - 10 * GIB) / 2 / 1.1)  # exactly fills the drive without metadata
    assert storage_preflight(
        edge,
        delivery_dir=tmp_path / "d",
        storage_dir=tmp_path / "s",
        free_bytes={key: 60 * GIB},
        metadata_bytes=0,
    ).ok
    assert not storage_preflight(
        edge,
        delivery_dir=tmp_path / "d",
        storage_dir=tmp_path / "s",
        free_bytes={key: 60 * GIB},
    ).ok
    with pytest.raises(ValueError, match="metadata_bytes"):
        storage_preflight(GIB, delivery_dir=tmp_path, storage_dir=None, metadata_bytes=-1)
    tight = storage_preflight(
        30 * GIB,
        delivery_dir=tmp_path / "d",
        storage_dir=tmp_path / "s",
        free_bytes={key: 60 * GIB},
    )
    assert not tight.ok and "PREFLIGHT FAILED" in tight.describe()
    only_download = storage_preflight(
        30 * GIB, delivery_dir=tmp_path / "d", storage_dir=None, free_bytes={key: 60 * GIB}
    )
    assert only_download.ok
    with pytest.raises(ValueError, match="positive"):
        storage_preflight(0, delivery_dir=tmp_path, storage_dir=None)


def test_storage_preflight_creates_nothing_and_cli_fails_when_short(tmp_path: Path) -> None:
    target = tmp_path / "not" / "created"
    assert storage_preflight(GIB, delivery_dir=target, storage_dir=target).drives
    assert not (tmp_path / "not").exists()
    rc = main(["storage-preflight", "--selected-gib", "100000000", "--delivery-dir", str(target)])
    assert rc == 1 and not (tmp_path / "not").exists()
    with pytest.raises(DataValidationError, match="insufficient disk space"):
        require_free_space(tmp_path, 1 << 62)


# ================================================================ real state untouched
def test_real_state_b2_ready_and_not_executed(repo_root: Path) -> None:
    st = load_status(repo_root)
    assert st.gate("B1").status == "PASSED"
    assert st.gate("B2").status in ("AUTHORIZED", "RUNNING")  # RUNNING once the runner started it
    assert all(st.gate(f"B{i}").status == "LOCKED" for i in range(3, 13))
    assert st.raw["data"]["acquired"] is False
    assert st.raw["data"]["approved_route"] != FAKE_ROUTE


def test_checksum_parser_accepts_tcia_single_space_format(tmp_path: Path) -> None:
    """The official TCIA .sums lists '<md5> <path>' with ONE space (observed 2026-10-06)."""
    import hashlib

    data = b"SYNTHETIC nifti bytes"
    rel = f"{SELECT}/ACRIN-FMISO-Brain/BraTS2021_SYNTH001/BraTS2021_SYNTH001_flair.nii.gz"
    sums = tmp_path / "RSNA-ASNR-MICCAI-BraTS-2021.sums"
    sums.write_bytes(
        f"{hashlib.md5(data).hexdigest()} {rel}\n".encode()
        + b"74e74fcd62aa74145bd6ad8fd6184807 RSNA-ASNR-MICCAI-BraTS-2021/"
        b"BraTS2021_TrainingSet_dcm/UPENN-GBM/0/Image-1.dcm\n"
    )
    parsed = parse_checksum_file(sums)
    assert parsed.entries[0].path == rel
    assert parsed.algorithms == ("md5",)
    base = tmp_path / "base"
    (base / rel).parent.mkdir(parents=True)
    (base / rel).write_bytes(data)
    report = verify_checksums(parsed, base, prefix=SELECT)
    assert report.ok and report.n_verified == 1 and report.n_not_selected == 1
