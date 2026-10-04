from __future__ import annotations

from pathlib import Path

import pytest

from brats_uncertainty.data.crosswalk import (
    PLACEHOLDER_TCIA_ID,
    derive_cohorts,
    parse_rows,
    shared_tcia_id_groups,
)
from brats_uncertainty.data.manifest import (
    Manifest,
    build_manifest,
    duplicate_content,
    verify_manifest,
)
from brats_uncertainty.data.provenance import DatasetProvenance
from brats_uncertainty.data.schema import DatasetSchema, load_schema
from brats_uncertainty.errors import ConfigError, DataValidationError, ProvenanceError

# Synthetic layout using a non-imaging file ending so no image-like files are created.
SCHEMA = DatasetSchema(
    name="synthetic",
    case_id_pattern=r"SYN-\d{3}",
    modality_suffixes={"T1": "_t1", "T1c": "_t1c", "T2": "_t2", "FLAIR": "_flair"},
    label_suffix="_seg",
    file_ending=".synthetic",
    verified_on_files=False,
)


def _make_dataset(root: Path, n: int = 3) -> None:
    for i in range(n):
        cid = f"SYN-{i:03d}"
        d = root / cid
        d.mkdir(parents=True)
        for m in ("T1", "T1c", "T2", "FLAIR"):
            (d / SCHEMA.image_name(cid, m)).write_bytes(f"synthetic {cid} {m}".encode())
        (d / SCHEMA.label_name(cid)).write_bytes(f"synthetic label {cid}".encode())


def test_build_and_verify_manifest(tmp_path: Path) -> None:
    _make_dataset(tmp_path)
    m = build_manifest(tmp_path, SCHEMA)
    assert m.case_ids == ("SYN-000", "SYN-001", "SYN-002")
    assert all(len(r.sha256) == 64 for e in m.entries for r in e.images.values())
    assert verify_manifest(m, tmp_path) == []
    assert Manifest.from_dict(m.to_dict()).sha256 == m.sha256
    (tmp_path / "SYN-001" / SCHEMA.image_name("SYN-001", "T2")).write_bytes(b"changed")
    assert verify_manifest(m, tmp_path) == ["SYN-001/SYN-001_t2.synthetic"]


def test_manifest_missing_modality_and_bad_id(tmp_path: Path) -> None:
    _make_dataset(tmp_path, 1)
    (tmp_path / "SYN-000" / SCHEMA.image_name("SYN-000", "FLAIR")).unlink()
    with pytest.raises(DataValidationError, match="missing file"):
        build_manifest(tmp_path, SCHEMA)
    other = tmp_path / "other"
    (other / "not_a_case").mkdir(parents=True)  # neither a case nor a collection with cases
    with pytest.raises(DataValidationError, match="empty_collection not_a_case"):
        build_manifest(other, SCHEMA)
    bad = tmp_path / "bad"
    (bad / "not_a_case").mkdir(parents=True)
    (bad / "not_a_case" / ("x" + SCHEMA.file_ending)).write_bytes(b"x")  # data, invalid name
    with pytest.raises(DataValidationError, match="malformed_case_dir not_a_case"):
        build_manifest(bad, SCHEMA)


def test_duplicate_content_detected(tmp_path: Path) -> None:
    _make_dataset(tmp_path, 2)
    src = tmp_path / "SYN-000" / SCHEMA.image_name("SYN-000", "T1")
    (tmp_path / "SYN-001" / SCHEMA.image_name("SYN-001", "T1")).write_bytes(src.read_bytes())
    dups = duplicate_content(build_manifest(tmp_path, SCHEMA))
    assert dups == [["SYN-000/SYN-000_t1.synthetic", "SYN-001/SYN-001_t1.synthetic"]]


def test_dataset_configs_parse(repo_root: Path) -> None:
    s = load_schema(repo_root / "configs/dataset/brats2021.yaml")
    assert s.is_valid_case_id("BraTS2021_00626")
    assert not s.is_valid_case_id("BraTS2021_626")
    assert s.image_name("BraTS2021_00001", "T1c") == "BraTS2021_00001_t1ce.nii.gz"
    assert s.verified_on_files is False
    a = load_schema(repo_root / "configs/dataset/brats_africa.yaml")
    assert a.verified_on_files is False
    with pytest.raises(ConfigError):
        DatasetSchema("x", ".*", {"T1": "a"}, "s", ".e", False)


COLS = {
    "case_id": "BraTS2021 ID",
    "site_id": "Site ID",
    "collection": "Data Collection",
    "tcia_subject_id": "TCIA PatientID",
}


def _rows(n_site1: int, n_other: int) -> list[dict[str, object]]:
    recs: list[dict[str, object]] = []
    for i in range(n_site1 + n_other):
        recs.append(
            {
                "BraTS2021 ID": f"SYN-{i:03d}",
                "Site ID": 1.0 if i < n_site1 else 18,
                "Data Collection": "synthetic",
                "TCIA PatientID": PLACEHOLDER_TCIA_ID,
            }
        )
    recs.append({"BraTS2021 ID": None})  # blank row ignored
    return recs


def test_crosswalk_cohorts_and_counts() -> None:
    rows = parse_rows(_rows(3, 5), COLS)
    c = derive_cohorts(
        rows, hoi_site_id="1", expected_total=8, expected_hoi=3, expected_development=5
    )
    assert len(c.held_out_institution) == 3 and len(c.development) == 5
    with pytest.raises(DataValidationError, match="SR3"):
        derive_cohorts(
            rows, hoi_site_id="1", expected_total=8, expected_hoi=4, expected_development=4
        )


def test_shared_tcia_ids_ignore_placeholder() -> None:
    recs = _rows(0, 4)
    recs[0]["TCIA PatientID"] = "SYN-P1"
    recs[1]["TCIA PatientID"] = "SYN-P1"
    rows = parse_rows(recs, COLS)
    assert shared_tcia_id_groups(rows) == [["SYN-000", "SYN-001"]]


def test_provenance_requires_all_fields() -> None:
    p = DatasetProvenance(
        dataset="synthetic",
        source="s",
        licence="l",
        data_route="r",
        data_route_approval_ref="ref",
        acquired_on="2000-01-01",
        acquired_by="tester",
        manifest_sha256="a" * 64,
        citations=("c",),
    )
    assert p.to_dict()["dataset"] == "synthetic"
    with pytest.raises(ProvenanceError):
        DatasetProvenance("d", "s", "l", "", "ref", "2000", "t", "a" * 64).validate()
    with pytest.raises(ProvenanceError):
        DatasetProvenance(
            "d", "s", "l", "r", "ref", "2000", "t", "xyz", citations=("c",)
        ).validate()
