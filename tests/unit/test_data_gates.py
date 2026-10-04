"""Data integrity validators, metadata parsing and git-ignore rules (synthetic files only).

B2-B6 stages, records, manifests and the gate state machine are tested in
test_b2_b6_software.py.
"""

from __future__ import annotations

import gzip
import subprocess
from pathlib import Path

import pytest

from brats_uncertainty.data.crosswalk import parse_rows, read_table_records
from brats_uncertainty.data.integrity import (
    CorruptFileError,
    check_gzip_stream,
    read_nifti_header,
    validate_dataset_tree,
)
from brats_uncertainty.data.manifest import build_manifest
from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.errors import (
    DataValidationError,
)
from tests.fixtures.synthetic import write_synthetic_nifti

SCHEMA = DatasetSchema(
    name="synthetic",
    case_id_pattern=r"SYN-\d{3}",
    modality_suffixes={"T1": "_t1", "T1c": "_t1c", "T2": "_t2", "FLAIR": "_flair"},
    label_suffix="_seg",
    file_ending=".nii.gz",
    verified_on_files=False,
)
SYN_SOURCE_URL = "https://example.org/synthetic-source"  # test-only placeholder URL


def _tree(root: Path, n: int = 3, shape: tuple[int, ...] = (4, 4, 3)) -> Path:
    for i in range(n):
        cid = f"SYN-{i:03d}"
        for m in ("T1", "T1c", "T2", "FLAIR"):
            write_synthetic_nifti(root / cid / SCHEMA.image_name(cid, m), shape)
        write_synthetic_nifti(root / cid / SCHEMA.label_name(cid), shape)
    return root


def _codes(report: object) -> set[str]:
    return {i.code for i in report.issues}  # type: ignore[attr-defined]


# ---------------------------------------------------------------- headers
@pytest.mark.parametrize(("version", "endian"), [(1, "<"), (1, ">"), (2, "<"), (2, ">")])
def test_nifti_header_parsing(tmp_path: Path, version: int, endian: str) -> None:
    p = write_synthetic_nifti(tmp_path / "x.nii.gz", (5, 6, 7), version=version, endian=endian)
    info = read_nifti_header(p)
    assert info.version == version
    assert info.shape == (5, 6, 7)


def test_corrupt_files_detected(tmp_path: Path) -> None:
    p = write_synthetic_nifti(tmp_path / "x.nii.gz")
    data = p.read_bytes()
    (tmp_path / "trunc.nii.gz").write_bytes(data[: len(data) // 2])
    with pytest.raises(CorruptFileError):
        check_gzip_stream(tmp_path / "trunc.nii.gz")
    with gzip.open(tmp_path / "bad.nii.gz", "wb") as fh:
        fh.write(b"not a nifti header" * 30)
    with pytest.raises(CorruptFileError, match="NIfTI"):
        read_nifti_header(tmp_path / "bad.nii.gz")
    (tmp_path / "plain.nii.gz").write_bytes(b"\x00" * 10)
    with pytest.raises(CorruptFileError):
        read_nifti_header(tmp_path / "plain.nii.gz")


# ---------------------------------------------------------------- integrity
def test_clean_tree_passes(tmp_path: Path) -> None:
    r = validate_dataset_tree(
        _tree(tmp_path), SCHEMA, expected_case_ids=["SYN-000", "SYN-001", "SYN-002"]
    )
    assert r.ok, r.issues
    assert r.n_case_dirs == r.n_complete_cases == r.n_cases_with_label == 3
    assert r.shapes == {"[4, 4, 3]": 3}


def test_integrity_issue_detection(tmp_path: Path) -> None:
    root = _tree(tmp_path, n=5)
    (root / "SYN-000" / SCHEMA.image_name("SYN-000", "T2")).unlink()  # missing modality
    (root / "SYN-001" / SCHEMA.label_name("SYN-001")).unlink()  # missing label
    write_synthetic_nifti(
        root / "SYN-002" / SCHEMA.image_name("SYN-002", "FLAIR"), (4, 4, 4)
    )  # dims
    target = root / "SYN-003" / SCHEMA.image_name("SYN-003", "T1")
    target.write_bytes(target.read_bytes()[:20])  # corrupt
    (root / "SYN-004" / "notes.txt").write_text("x", encoding="utf-8")  # unexpected in case
    (root / "readme.txt").write_text("x", encoding="utf-8")  # unexpected top level
    (root / "bad_case").mkdir()  # not a case ID and holds no cases: empty collection
    (root / "bad case 2").mkdir()  # data files under an invalid case name
    (root / "bad case 2" / ("x" + SCHEMA.file_ending)).write_bytes(b"x")
    r = validate_dataset_tree(
        root, SCHEMA, expected_case_ids=["SYN-000", "SYN-001", "SYN-002", "SYN-003", "SYN-009"]
    )
    codes = _codes(r)
    assert {
        "missing_modality",
        "missing_label",
        "dimension_mismatch",
        "corrupt_file",
        "unexpected_file",
        "empty_collection",
        "malformed_case_dir",
        "missing_case",
        "unexpected_case",
    } <= codes
    assert not r.ok
    assert r.to_dict()["n_errors"] == len(r.errors)


def test_hash_mismatch_against_manifest(tmp_path: Path) -> None:
    root = _tree(tmp_path, n=2)
    manifest = build_manifest(root, SCHEMA)
    write_synthetic_nifti(root / "SYN-001" / SCHEMA.label_name("SYN-001"), (4, 4, 3), endian=">")
    r = validate_dataset_tree(root, SCHEMA, manifest=manifest)
    assert "hash_mismatch" in _codes(r)


def test_expected_shape_warning(tmp_path: Path) -> None:
    r = validate_dataset_tree(_tree(tmp_path, n=1), SCHEMA, expected_shape=(240, 240, 155))
    assert r.ok
    assert "unexpected_shape" in _codes(r)


def test_missing_root(tmp_path: Path) -> None:
    assert not validate_dataset_tree(tmp_path / "nope", SCHEMA).ok


# ---------------------------------------------------------------- metadata
COLS = {
    "case_id": "BraTS2021 ID",
    "site_id": "Site ID",
    "collection": "Data Collection",
    "tcia_subject_id": "TCIA PatientID",
}


def test_malformed_crosswalk_detected() -> None:
    good = {
        "BraTS2021 ID": "SYN-001",
        "Site ID": "18",
        "Data Collection": "x",
        "TCIA PatientID": "y",
    }
    with pytest.raises(DataValidationError, match="missing expected columns"):
        parse_rows([{"BraTS2021 ID": "SYN-001"}], COLS)
    with pytest.raises(DataValidationError, match="malformed case ID"):
        parse_rows([{**good, "BraTS2021 ID": "bad id"}], COLS, case_id_pattern=r"SYN-\d{3}")
    with pytest.raises(DataValidationError, match="missing site ID"):
        parse_rows([{**good, "Site ID": " "}], COLS)
    with pytest.raises(DataValidationError, match="duplicate"):
        parse_rows([good, good], COLS)
    with pytest.raises(DataValidationError, match="incomplete"):
        parse_rows([good], {**COLS, "site_id": ""})
    with pytest.raises(DataValidationError, match="no records"):
        parse_rows([], COLS)
    rows = parse_rows([{**good, "Site ID": "1.0"}], COLS)
    assert rows[0].site_id == "1"


def test_read_table_records_formats(tmp_path: Path) -> None:
    (tmp_path / "t.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    assert read_table_records(tmp_path / "t.csv") == [{"a": "1", "b": "2"}]
    (tmp_path / "t.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataValidationError, match="unsupported"):
        read_table_records(tmp_path / "t.json")
    with pytest.raises(DataValidationError, match="not found"):
        read_table_records(tmp_path / "missing.csv")


def test_private_data_paths_are_gitignored(repo_root: Path) -> None:
    paths = [
        "data/raw/BraTS2021_00001/BraTS2021_00001_t1.nii.gz",
        "data/raw/BraTS2021_00001_seg.nii",
        "data/manifests/B5_manifest.json",
        "data/derived/x.npy",
        "data/cache/tmp.bin",
        "BraTS2021_MappingToTCIA.xlsx",
        "meta/UCSF-PDGM-metadata_v5.csv",
        "kaggle.json",
        ".kaggle/kaggle.json",
        ".env",
        "archive.zip",
        "scan.dcm",
        "model.pth",
    ]
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--no-index", *paths],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except OSError:
        pytest.skip("git not available")
    ignored = set(proc.stdout.split())
    assert ignored == set(paths)
    readme = subprocess.run(
        ["git", "check-ignore", "--no-index", "data/README.md"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert readme.returncode == 1  # README is NOT ignored
