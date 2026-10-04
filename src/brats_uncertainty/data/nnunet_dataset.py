"""BraTS 2021 (official nested delivery) -> nnU-Net v2 raw dataset, with full provenance.

Reads ``<training root>/<collection>/<case_id>/`` (``data.layout``; never flattened
in the source), and writes the nnU-Net raw layout::

    Dataset<ID>_<Name>/
        imagesTr/<case_id>_0000.nii.gz   T1    (byte-for-byte copy)
        imagesTr/<case_id>_0001.nii.gz   T1c   (byte-for-byte copy)
        imagesTr/<case_id>_0002.nii.gz   T2    (byte-for-byte copy)
        imagesTr/<case_id>_0003.nii.gz   FLAIR (byte-for-byte copy)
        labelsTr/<case_id>.nii.gz        label, BraTS {0,1,2,4} -> nnU-Net {0,1,2,3}
        dataset.json                     models.nnunet.build_dataset_json
        conversion_provenance.json       every derived file -> source collection/case/path
        conversion_provenance.csv        the same file table

Channel order is the protocol order (§8: T1, T1c, T2, FLAIR). The label map is
``preprocessing.labels.BRATS2021_TO_NNUNET``; unexpected label values fail. Every
requested case must be present and complete; nothing is skipped silently. The
output is written to a temporary sibling and renamed only when complete, and
the gzip output of converted labels is deterministic (mtime 0).

Modes (as in ``data.stages``): real mode is gated (``train_main`` for the main
study, ``run_exp001`` for the compute pilot) and refuses SYNTHETIC_TEST_DATA;
synthetic mode accepts only a generator-listed SYNTHETIC_TEST_DATA tree and
writes outside the repository. Real data are never written into the repository.
"""

from __future__ import annotations

import csv
import gzip
import io
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from brats_uncertainty.data.integrity import CorruptFileError, read_nifti_header
from brats_uncertainty.data.layout import discover_cases
from brats_uncertainty.data.records import data_class
from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.data.synthetic import find_marker_root, require_synthetic
from brats_uncertainty.errors import DataValidationError, ProvenanceError
from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.models.nnunet import build_dataset_json
from brats_uncertainty.preprocessing.labels import BRATS2021_TO_NNUNET, convert_brats2021_to_nnunet
from brats_uncertainty.preprocessing.modalities import MODALITIES
from brats_uncertainty.utils.git import git_commit
from brats_uncertainty.utils.hashing import sha256_file, sha256_json
from brats_uncertainty.utils.io import write_json
from brats_uncertainty.utils.paths import is_link, is_within

CONVERSION_VERSION = 1
PROVENANCE_NAME = "conversion_provenance.json"
PROVENANCE_CSV = "conversion_provenance.csv"
_NAME = re.compile(r"^[A-Za-z0-9_]+$")
GATE_ACTIONS = ("train_main", "run_exp001")
CSV_FIELDS = (
    "derived_case",
    "derived_filename",
    "role",
    "modality",
    "channel",
    "source_collection",
    "source_case",
    "source_relative_path",
    "source_sha256",
    "derived_sha256",
    "conversion",
)


def conversion_config(dataset_id: int, dataset_name: str) -> dict[str, Any]:
    """Everything that determines the derived bytes (hashed into the provenance)."""
    template = build_dataset_json(1, dataset_name=dataset_name)
    template.pop("numTraining")
    return {
        "conversion_version": CONVERSION_VERSION,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "channel_order": list(MODALITIES),
        "label_map_brats2021_to_nnunet": {
            str(k): v for k, v in sorted(BRATS2021_TO_NNUNET.items())
        },
        "channel_conversion": "byte_copy",
        "label_conversion": "label_map_brats2021_to_nnunet; uint8; gzip mtime 0",
        "dataset_json_template": template,
    }


@dataclass(frozen=True)
class ConversionResult:
    out_dir: Path
    n_cases: int
    provenance_sha256: str
    conversion_config_sha256: str


def _write_label(src: Path, dest: Path) -> None:
    import nibabel as nib

    img: Any = nib.load(str(src))  # nibabel types load() too narrowly
    data = np.asanyarray(img.dataobj)
    if not np.all(np.equal(np.mod(data, 1), 0)):
        raise DataValidationError(f"{src.name}: non-integer label values")
    converted = convert_brats2021_to_nnunet(data.astype(np.int16))
    out = nib.Nifti1Image(converted, img.affine, header=img.header.copy())
    out.set_data_dtype(np.uint8)
    out.header.set_slope_inter(1.0, 0.0)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(out.to_bytes())
    dest.write_bytes(buf.getvalue())


def _convert(
    training_root: Path,
    schema: DatasetSchema,
    out_dir: Path,
    *,
    dataset_id: int,
    dataset_name: str,
    case_ids: Sequence[str] | None,
    synthetic: bool,
    commit: str | None,
    training_root_reference: str | None,
) -> ConversionResult:
    if not 1 <= dataset_id <= 999 or not _NAME.match(dataset_name):
        raise DataValidationError("dataset_id must be 1-999 and dataset_name [A-Za-z0-9_]+")
    if out_dir.name != f"Dataset{dataset_id:03d}_{dataset_name}":
        raise DataValidationError(
            f"nnU-Net folder must be named Dataset{dataset_id:03d}_{dataset_name}"
        )
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite an existing dataset: {out_dir.name}")
    if schema.file_ending != ".nii.gz":
        raise DataValidationError("the nnU-Net writer expects .nii.gz source files")
    found = discover_cases(training_root, schema)
    if found.errors:
        e = found.errors[0]
        raise DataValidationError(f"source layout invalid: {e.code} {e.path}")
    by_id = {c.case_id: c for c in found.cases}
    if case_ids is None:
        selected = sorted(by_id)
    else:
        if len(set(case_ids)) != len(case_ids):
            raise DataValidationError("duplicate case IDs requested")
        missing = sorted(set(case_ids) - set(by_id))
        if missing:
            raise DataValidationError(
                f"{len(missing)} requested case(s) not in the source (never skipped): {missing[:5]}"
            )
        selected = sorted(case_ids)
    if not selected:
        raise DataValidationError("no cases to convert")
    cfg = conversion_config(dataset_id, dataset_name)
    cfg_sha = sha256_json(cfg)
    tmp = out_dir.with_name(out_dir.name + ".part")
    if tmp.exists():
        shutil.rmtree(tmp)
    rows: list[dict[str, Any]] = []
    try:
        (tmp / "imagesTr").mkdir(parents=True)
        (tmp / "labelsTr").mkdir()
        for cid in selected:
            case = by_id[cid]
            shapes: dict[str, tuple[int, ...]] = {}
            label_src = case.path / schema.label_name(cid)
            sources = [
                (schema.image_name(cid, m), m, i, f"imagesTr/{cid}_{i:04d}.nii.gz")
                for i, m in enumerate(MODALITIES)
            ] + [(schema.label_name(cid), None, None, f"labelsTr/{cid}.nii.gz")]
            for name, modality, channel, derived in sources:
                src = case.path / name
                if is_link(src) or not src.is_file():
                    what = modality or "label"
                    raise DataValidationError(f"{case.relpath}: {what} missing ({name})")
                try:
                    shapes[modality or "label"] = read_nifti_header(src).shape
                except CorruptFileError as exc:
                    raise DataValidationError(f"{case.relpath}: {exc}") from exc
                dest = tmp / derived
                if modality is None:
                    _write_label(label_src, dest)
                    conversion = "label_map_brats2021_to_nnunet"
                else:
                    shutil.copyfile(src, dest)
                    conversion = "byte_copy"
                rows.append(
                    {
                        "derived_case": cid,
                        "derived_filename": derived,
                        "role": "label" if modality is None else "channel",
                        "modality": modality,
                        "channel": channel,
                        "source_collection": case.collection,
                        "source_case": cid,
                        "source_relative_path": f"{case.relpath}/{name}",
                        "source_sha256": sha256_file(src),
                        "derived_sha256": sha256_file(dest),
                        "conversion": conversion,
                    }
                )
            if len(set(shapes.values())) != 1:
                raise DataValidationError(f"{case.relpath}: shapes differ {shapes}")
        dataset_json = build_dataset_json(len(selected), dataset_name=dataset_name)
        write_json(tmp / "dataset.json", dataset_json)
        provenance = {
            "kind": "nnunet_raw_dataset_conversion",
            "synthetic": synthetic,
            "data_class": data_class(synthetic),
            "git_commit": commit,
            "conversion_config": cfg,
            "conversion_config_sha256": cfg_sha,
            "source_layout": found.layout,
            "training_root_reference": training_root_reference,
            "n_cases": len(selected),
            "cases": [
                {
                    "derived_case": cid,
                    "source_collection": by_id[cid].collection,
                    "source_case": cid,
                    "source_relative_path": by_id[cid].relpath,
                }
                for cid in selected
            ],
            "dataset_json_sha256": sha256_file(tmp / "dataset.json"),
            "files": rows,
        }
        write_json(tmp / PROVENANCE_NAME, provenance)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(CSV_FIELDS), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if r[k] is None else r[k] for k in CSV_FIELDS})
        (tmp / PROVENANCE_CSV).write_text(buf.getvalue(), encoding="utf-8", newline="\n")
        tmp.replace(out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return ConversionResult(out_dir, len(selected), sha256_file(out_dir / PROVENANCE_NAME), cfg_sha)


def write_nnunet_dataset(
    repo_root: Path,
    training_root: Path,
    schema: DatasetSchema,
    out_dir: Path,
    *,
    dataset_id: int,
    dataset_name: str,
    case_ids: Sequence[str] | None = None,
    gate_action: str = "train_main",
    training_root_reference: str | None = None,
    synthetic: bool = False,
) -> ConversionResult:
    """Gated conversion (see module docstring). Returns the provenance hash."""
    if is_link(training_root) or not training_root.is_dir():
        raise DataValidationError("training root not found or a link")
    if synthetic:
        require_synthetic([training_root], repo_root)
        if is_within(out_dir, repo_root):
            raise ProvenanceError("synthetic conversion output must be outside the repository")
    else:
        if gate_action not in GATE_ACTIONS:
            raise ValueError(f"gate_action must be one of {GATE_ACTIONS}")
        require_action(gate_action, repo_root)
        if find_marker_root(training_root) is not None:
            raise ProvenanceError("SYNTHETIC_TEST_DATA cannot be converted in real mode")
        if is_within(out_dir, repo_root):
            raise ProvenanceError("real derived data are never written into the repository")
    return _convert(
        training_root,
        schema,
        out_dir,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        case_ids=case_ids,
        synthetic=synthetic,
        commit=git_commit(repo_root),
        training_root_reference=training_root_reference,
    )
