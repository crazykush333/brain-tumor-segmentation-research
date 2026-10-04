"""BraTS (official nested layout) -> nnU-Net raw dataset writer: SYNTHETIC fixtures only."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

pytest.importorskip("nibabel")
import nibabel as nib
import numpy as np

from brats_uncertainty.data.acquisition import SyntheticFixtureAdapter, stage_acquire
from brats_uncertainty.data.nnunet_dataset import (
    CSV_FIELDS,
    PROVENANCE_CSV,
    PROVENANCE_NAME,
    _convert,
    conversion_config,
    write_nnunet_dataset,
)
from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.errors import (
    DataValidationError,
    ProvenanceError,
    ResearchGateError,
)
from brats_uncertainty.models.nnunet import build_dataset_json
from brats_uncertainty.preprocessing.labels import BRATS2021_TO_NNUNET
from brats_uncertainty.utils.hashing import sha256_file
from tests.conftest import make_status_repo
from tests.fixtures.nested_layout import NESTED_SCHEMA, write_volume_case

CASES = {
    "ACRIN-FMISO-Brain": ("BraTS2021_SYNTH001",),
    "UCSF-PDGM": ("BraTS2021_SYNTH002",),
    "UPENN-GBM": ("BraTS2021_SYNTH003",),
}
SUFFIX_OF = {"T1": "_t1", "T1c": "_t1ce", "T2": "_t2", "FLAIR": "_flair"}


def _tree(root: Path) -> Path:
    for i, (coll, ids) in enumerate(CASES.items()):
        for cid in ids:
            write_volume_case(root / coll / cid, cid, seed=i)
    return root


def _run(root: Path, out_parent: Path, **kw):  # type: ignore[no-untyped-def]
    args = {"dataset_id": 501, "dataset_name": "SynthTest", "case_ids": None}
    args.update(kw)
    return _convert(
        root,
        NESTED_SCHEMA,
        out_parent / f"Dataset{args['dataset_id']:03d}_{args['dataset_name']}",
        dataset_id=args["dataset_id"],
        dataset_name=args["dataset_name"],
        case_ids=args["case_ids"],
        synthetic=True,
        commit="f" * 40,
        training_root_reference="SYNTHETIC/BraTS2021_TrainingSet",
    )


def test_channels_labels_dataset_json_and_provenance(tmp_path: Path) -> None:
    src = _tree(tmp_path / "BraTS2021_TrainingSet")
    res = _run(src, tmp_path / "raw")
    out = res.out_dir
    assert res.n_cases == 3
    for coll, ids in CASES.items():
        cid = ids[0]
        for i, m in enumerate(("T1", "T1c", "T2", "FLAIR")):  # protocol channel order (§8)
            derived = out / "imagesTr" / f"{cid}_{i:04d}.nii.gz"
            source = src / coll / cid / f"{cid}{SUFFIX_OF[m]}.nii.gz"
            assert derived.read_bytes() == source.read_bytes()  # byte-for-byte copy
        lab_src = np.asanyarray(nib.load(str(src / coll / cid / f"{cid}_seg.nii.gz")).dataobj)
        lab_out = np.asanyarray(nib.load(str(out / "labelsTr" / f"{cid}.nii.gz")).dataobj)
        assert lab_out.dtype == np.uint8
        expected = np.vectorize(BRATS2021_TO_NNUNET.__getitem__)(lab_src)
        assert np.array_equal(lab_out, expected)
        assert set(np.unique(lab_out)) <= {0, 1, 2, 3}
    assert json.loads((out / "dataset.json").read_text(encoding="utf-8")) == build_dataset_json(
        3, dataset_name="SynthTest"
    )
    prov = json.loads((out / PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert prov["data_class"] == "SYNTHETIC_TEST_DATA" and prov["n_cases"] == 3
    assert prov["source_layout"] == "nested_collections"
    assert prov["conversion_config"] == conversion_config(501, "SynthTest")
    assert prov["conversion_config_sha256"] == res.conversion_config_sha256
    case2 = next(c for c in prov["cases"] if c["source_case"] == "BraTS2021_SYNTH002")
    assert case2["source_collection"] == "UCSF-PDGM"
    assert case2["source_relative_path"] == "UCSF-PDGM/BraTS2021_SYNTH002"
    assert len(prov["files"]) == 15  # 3 cases x (4 channels + label)
    for row in prov["files"]:
        assert row["source_relative_path"].startswith(
            f"{row['source_collection']}/{row['source_case']}/"
        )
        assert sha256_file(out / row["derived_filename"]) == row["derived_sha256"]
        assert sha256_file(src / row["source_relative_path"]) == row["source_sha256"]
    table = list(csv.DictReader(io.StringIO((out / PROVENANCE_CSV).read_text(encoding="utf-8"))))
    assert tuple(table[0]) == CSV_FIELDS and len(table) == 15
    assert not (out.parent / (out.name + ".part")).exists()


def test_conversion_is_deterministic(tmp_path: Path) -> None:
    src = _tree(tmp_path / "BraTS2021_TrainingSet")
    a = _run(src, tmp_path / "a").out_dir
    b = _run(src, tmp_path / "b").out_dir
    files = sorted(p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file())
    for f in files:
        assert (a / f).read_bytes() == (b / f).read_bytes(), f


def test_subset_selection_never_loses_or_invents_cases(tmp_path: Path) -> None:
    src = _tree(tmp_path / "BraTS2021_TrainingSet")
    res = _run(src, tmp_path / "s", case_ids=["BraTS2021_SYNTH003", "BraTS2021_SYNTH001"])
    names = sorted(p.name for p in (res.out_dir / "labelsTr").iterdir())
    assert names == ["BraTS2021_SYNTH001.nii.gz", "BraTS2021_SYNTH003.nii.gz"]
    for bad, msg in (
        (["BraTS2021_SYNTH001", "BraTS2021_SYNTH999"], "not in the source"),
        (["BraTS2021_SYNTH001", "BraTS2021_SYNTH001"], "duplicate case IDs"),
        ([], "no cases"),
    ):
        with pytest.raises(DataValidationError, match=msg):
            _run(src, tmp_path / f"bad{len(list(tmp_path.iterdir()))}", case_ids=bad)


@pytest.mark.parametrize(
    ("mutate", "msg"),
    [
        (lambda c: (c / "BraTS2021_SYNTH002_t2.nii.gz").unlink(), "T2 missing"),
        (lambda c: (c / "BraTS2021_SYNTH002_seg.nii.gz").unlink(), "label missing"),
        (
            lambda c: (c / "BraTS2021_SYNTH002_flair.nii.gz").write_bytes(b"not nifti"),
            "BraTS2021_SYNTH002_flair",
        ),
    ],
)
def test_incomplete_or_corrupt_case_fails_atomically(tmp_path: Path, mutate, msg: str) -> None:  # type: ignore[no-untyped-def]
    src = _tree(tmp_path / "BraTS2021_TrainingSet")
    mutate(src / "UCSF-PDGM" / "BraTS2021_SYNTH002")
    with pytest.raises(DataValidationError, match=msg):
        _run(src, tmp_path / "raw")
    assert not any((tmp_path / "raw").iterdir()) if (tmp_path / "raw").exists() else True


def test_unexpected_label_value_fails(tmp_path: Path) -> None:
    src = _tree(tmp_path / "BraTS2021_TrainingSet")
    seg = src / "UPENN-GBM" / "BraTS2021_SYNTH003" / "BraTS2021_SYNTH003_seg.nii.gz"
    nib.save(nib.Nifti1Image(np.full((6, 5, 4), 3, dtype=np.int16), np.eye(4)), str(seg))
    with pytest.raises(DataValidationError, match="unexpected BraTS 2021 label values"):
        _run(src, tmp_path / "raw")
    assert not (tmp_path / "raw" / "Dataset501_SynthTest").exists()


def test_layout_and_output_rules(tmp_path: Path) -> None:
    src = _tree(tmp_path / "BraTS2021_TrainingSet")
    write_volume_case(src / "UPENN-GBM" / "BraTS2021_SYNTH001", "BraTS2021_SYNTH001", seed=9)
    with pytest.raises(DataValidationError, match="duplicate_case_id"):
        _run(src, tmp_path / "raw")
    clean = _tree(tmp_path / "clean" / "BraTS2021_TrainingSet")
    with pytest.raises(DataValidationError, match="must be named"):
        _convert(
            clean,
            NESTED_SCHEMA,
            tmp_path / "raw" / "WrongName",
            dataset_id=501,
            dataset_name="SynthTest",
            case_ids=None,
            synthetic=True,
            commit=None,
            training_root_reference=None,
        )
    _run(clean, tmp_path / "once")
    with pytest.raises(FileExistsError):
        _run(clean, tmp_path / "once")
    flat_schema = DatasetSchema(**{**NESTED_SCHEMA.__dict__, "file_ending": ".nii"})
    with pytest.raises(DataValidationError, match=r".nii.gz"):
        _convert(
            clean,
            flat_schema,
            tmp_path / "x" / "Dataset501_SynthTest",
            dataset_id=501,
            dataset_name="SynthTest",
            case_ids=None,
            synthetic=True,
            commit=None,
            training_root_reference=None,
        )


# ================================================================ gated entry point
def _syn_tree(repo_root: Path, tmp_path: Path) -> Path:
    stage_acquire(
        repo_root,
        SyntheticFixtureAdapter(repo_root, n_cases=3, collections=("UCSF-PDGM", "UPENN-GBM")),
        storage_root=tmp_path / "syn",
        out_record=tmp_path / "S.json",
        acquired_by="pytest",
        execute=True,
    )
    return tmp_path / "syn" / "images"


def _syn_schema() -> DatasetSchema:
    return DatasetSchema(
        name="synthetic",
        case_id_pattern=r"SYN-\d{4}",
        modality_suffixes=dict(SUFFIX_OF),
        label_suffix="_seg",
        file_ending=".nii.gz",
        verified_on_files=False,
    )


def test_synthetic_mode_end_to_end(repo_root: Path, tmp_path: Path) -> None:
    images = _syn_tree(repo_root, tmp_path)
    res = write_nnunet_dataset(
        repo_root,
        images,
        _syn_schema(),
        tmp_path / "raw" / "Dataset777_Synth",
        dataset_id=777,
        dataset_name="Synth",
        synthetic=True,
    )
    prov = json.loads((res.out_dir / PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert prov["data_class"] == "SYNTHETIC_TEST_DATA" and res.n_cases == 3
    assert {c["source_collection"] for c in prov["cases"]} == {"UCSF-PDGM", "UPENN-GBM"}


def test_real_mode_is_gated_and_refuses_synthetic(repo_root: Path, tmp_path: Path) -> None:
    images = _syn_tree(repo_root, tmp_path)
    kw = {"dataset_id": 777, "dataset_name": "Synth"}
    with pytest.raises(ResearchGateError):  # real repository: train_main not authorized
        write_nnunet_dataset(
            repo_root, images, _syn_schema(), tmp_path / "o1" / "Dataset777_Synth", **kw
        )
    fake = make_status_repo(tmp_path / "repo", closed={"B1", "B2", "D1", "D2"})  # run_exp001 open
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_DATA cannot be converted"):
        write_nnunet_dataset(
            fake,
            images,
            _syn_schema(),
            tmp_path / "o2" / "Dataset777_Synth",
            gate_action="run_exp001",
            **kw,
        )
    plain = _tree(tmp_path / "plain" / "BraTS2021_TrainingSet")  # not a synthetic tree
    with pytest.raises(ProvenanceError):
        write_nnunet_dataset(
            repo_root,
            plain,
            NESTED_SCHEMA,
            tmp_path / "o3" / "Dataset501_SynthTest",
            dataset_id=501,
            dataset_name="SynthTest",
            synthetic=True,
        )
    with pytest.raises(ProvenanceError, match="never written into the repository"):
        write_nnunet_dataset(
            fake,
            plain,
            NESTED_SCHEMA,
            fake / "Dataset501_SynthTest",
            dataset_id=501,
            dataset_name="SynthTest",
            gate_action="run_exp001",
        )
