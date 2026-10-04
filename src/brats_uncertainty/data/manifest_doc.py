"""Gate B5 manifest documents: RAW DATA MANIFEST vs DERIVED/PROCESSED DATA MANIFEST.

Both are machine-readable JSON (with a CSV export of the file table) and follow
the JSON Schemas in ``configs/schemas/``:

- ``raw_data_manifest.schema.json`` covers files exactly as acquired (images,
  labels, metadata), linked to the B2 acquisition record fingerprint.
- ``derived_data_manifest.schema.json`` covers files computed from a raw
  manifest, linked to the parent ``manifest_sha256`` and the derivation
  tool/configuration.

Schema version 3 supports the official nested TCIA delivery
(``<collection>/<case_id>/``): every file records its ``collection`` and its
path relative to the data root, the derived ``cases`` table maps each case to
its collection and ``relative_case_path``, and ``source_layout`` records the
detected layout, the per-collection case counts and where the data root lies
inside the B2 delivery (``data_root_reference``). Nothing is flattened.

``manifest_sha256`` is the SHA-256 of the canonical JSON of the manifest
content without its provenance stamp, so it depends only on the data and the
source description. Manifests of real data are private research artifacts
(``data/manifests/``). Only their hash and summary are published after owner
review.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from brats_uncertainty.data.layout import LAYOUTS, case_relpath, discover_cases
from brats_uncertainty.data.manifest import FileRecord, Manifest, ManifestEntry, validate_manifest
from brats_uncertainty.data.records import (
    AcquisitionRecord,
    MetadataFileRecord,
    ProvenanceStamp,
    data_class,
    record_body,
)
from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.modalities import MODALITIES
from brats_uncertainty.utils.hashing import sha256_file, sha256_json
from brats_uncertainty.utils.paths import is_link, is_safe_relpath

MANIFEST_DOC_SCHEMA_VERSION = 3
FILE_TYPES = ("image", "label", "metadata", "other", "derived")
CSV_COLUMNS = (
    "collection",
    "case_id",
    "file_type",
    "modality",
    "filename",
    "relpath",
    "size_bytes",
    "sha256",
)

RAW_REQUIRED = (
    "manifest_type",
    "schema_version",
    "synthetic",
    "data_class",
    "dataset",
    "dataset_version",
    "doi",
    "source_url",
    "acquisition",
    "metadata_records",
    "source_layout",
    "cases",
    "files",
    "summary",
    "duplicates",
    "manifest_sha256",
    "stamp",
)
DERIVED_REQUIRED = (
    "manifest_type",
    "schema_version",
    "synthetic",
    "data_class",
    "parent_manifest_sha256",
    "derivation",
    "files",
    "summary",
    "duplicates",
    "manifest_sha256",
    "stamp",
)
FILE_REQUIRED = CSV_COLUMNS
_CONTENT_EXCLUDE = ("manifest_sha256", "stamp")


def _classify(case_id: str, name: str, schema: DatasetSchema) -> tuple[str, str | None]:
    for m in MODALITIES:
        if name == schema.image_name(case_id, m):
            return "image", m
    if name == schema.label_name(case_id):
        return "label", None
    return "other", None


def _entry(
    root: Path,
    p: Path,
    case_id: str | None,
    ftype: str,
    modality: str | None,
    collection: str | None = None,
) -> dict[str, Any]:
    if is_link(p):
        raise DataValidationError(f"symbolic links are not allowed in manifests: {p.name}")
    return {
        "collection": collection,
        "case_id": case_id,
        "file_type": ftype,
        "modality": modality,
        "filename": p.name,
        "relpath": p.relative_to(root).as_posix(),
        "size_bytes": p.stat().st_size,
        "sha256": sha256_file(p),
    }


def _duplicates(files: list[dict[str, Any]]) -> list[list[str]]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for f in files:
        by_hash[f["sha256"]].append(f["relpath"])
    return sorted(sorted(v) for v in by_hash.values() if len(v) > 1)


def _summary(files: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "n_files": len(files),
        "n_cases": len({f["case_id"] for f in files if f["case_id"]}),
        "n_images": sum(f["file_type"] == "image" for f in files),
        "n_labels": sum(f["file_type"] == "label" for f in files),
        "total_bytes": sum(int(f["size_bytes"]) for f in files),
    }


def _cases(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Case table derived from the image/label entries (collection, case path, files)."""
    cases: dict[tuple[str | None, str], dict[str, Any]] = {}
    for f in files:
        if not f["case_id"] or f["file_type"] not in ("image", "label"):
            continue
        key = (f["collection"], str(f["case_id"]))
        c = cases.setdefault(
            key,
            {
                "collection": f["collection"],
                "case_id": f["case_id"],
                "relative_case_path": case_relpath(f["collection"], str(f["case_id"])),
                "modalities": {},
                "label": None,
                "n_files": 0,
                "total_bytes": 0,
            },
        )
        if f["file_type"] == "label":
            c["label"] = f["relpath"]
        else:
            c["modalities"][f["modality"]] = f["relpath"]
        c["n_files"] += 1
        c["total_bytes"] += int(f["size_bytes"])
    out = []
    for c in sorted(cases.values(), key=lambda c: str(c["relative_case_path"])):
        c["modalities"] = dict(sorted(c["modalities"].items()))
        out.append(c)
    return out


def _collection_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in cases:
        if c["collection"] is not None:
            out[c["collection"]] = out.get(c["collection"], 0) + 1
    return dict(sorted(out.items()))


def _finish(doc: dict[str, Any]) -> dict[str, Any]:
    doc["manifest_sha256"] = content_sha256(doc)
    validate_manifest_doc(doc)
    return doc


def content_sha256(doc: dict[str, Any]) -> str:
    return sha256_json({k: v for k, v in doc.items() if k not in _CONTENT_EXCLUDE})


def build_raw_manifest(
    data_root: str | Path,
    schema: DatasetSchema,
    acquisition: AcquisitionRecord,
    stamp: ProvenanceStamp,
    *,
    metadata: list[tuple[Path, MetadataFileRecord]] | None = None,
    extra: dict[str, Any] | None = None,
    data_root_reference: str | None = None,
) -> dict[str, Any]:
    """Raw manifest of ``data_root/[<collection>/]<case_id>/...`` plus B3/B4 metadata files.

    The tree is discovered with ``data.layout`` (flat or nested-collection) and
    is never flattened: relpaths are relative to ``data_root`` and keep the
    collection directory. Any layout error fails closed. ``data_root_reference``
    is the data root's path inside the B2 delivery (logical, never absolute).

    Each metadata file must still hash to the value in its B3/B4 record (a file
    changed after hashing invalidates the manifest), and each record's data
    class must match the acquisition.
    """
    root = Path(data_root)
    if data_root_reference is not None and not is_safe_relpath(data_root_reference):
        raise DataValidationError("data_root_reference must be a safe relative path")
    files: list[dict[str, Any]] = []
    for p in root.rglob("*"):
        if is_link(p):
            raise DataValidationError(f"symbolic links are not allowed in the data tree: {p.name}")
    found = discover_cases(root, schema)
    if found.errors:
        e = found.errors[0]
        raise DataValidationError(
            f"data tree layout invalid ({len(found.errors)} error(s)); first: {e.code} {e.path}"
        )
    for case in found.cases:
        children = sorted(case.path.iterdir(), key=lambda x: x.name)
        nested = [x.name for x in children if x.is_dir()]
        if nested:
            raise DataValidationError(f"{case.relpath}: subdirectories inside a case: {nested}")
        for p in children:
            ftype, modality = _classify(case.case_id, p.name, schema)
            files.append(_entry(root, p, case.case_id, ftype, modality, case.collection))
    for collection, p in found.stray_files:
        files.append(_entry(root, p, None, "other", None, collection))
    metadata_records: dict[str, dict[str, str]] = {}
    for m, rec in metadata or []:
        if rec.synthetic != acquisition.synthetic:
            raise DataValidationError(f"{rec.gate} record data class differs from the acquisition")
        if m.name != rec.file.file_name:
            raise DataValidationError(f"{m.name} does not match the {rec.gate} record file name")
        entry = _entry(m.parent, m, None, "metadata", None)
        if entry["sha256"] != rec.file.sha256:
            raise DataValidationError(
                f"{m.name} changed after gate {rec.gate}: SHA-256 differs from the record"
            )
        if rec.gate in metadata_records:
            raise DataValidationError(f"duplicate {rec.gate} metadata record")
        entry["relpath"] = f"metadata/{m.name}"
        files.append(entry)
        metadata_records[rec.gate] = {
            "file_name": rec.file.file_name,
            "sha256": rec.file.sha256,
            "record_fingerprint": str(record_body(rec)["record_fingerprint"]),
        }
    doc = {
        "manifest_type": "raw",
        "schema_version": MANIFEST_DOC_SCHEMA_VERSION,
        "synthetic": acquisition.synthetic,
        "data_class": data_class(acquisition.synthetic),
        "dataset": acquisition.source.dataset,
        "dataset_version": acquisition.source.dataset_version,
        "doi": acquisition.source.doi,
        "source_url": acquisition.source.source_url,
        "acquisition": {
            "record_fingerprint": _acq_fingerprint(acquisition),
            "acquired_at": acquisition.acquired_at,
            "storage_location": acquisition.storage_location,
            "route": acquisition.source.route,
        },
        "metadata_records": dict(sorted(metadata_records.items())),
        "source_layout": {
            "layout": found.layout,
            "collections": found.collections,
            "data_root_reference": data_root_reference,
        },
        "cases": _cases(files),
        "files": files,
        "summary": _summary(files),
        "duplicates": _duplicates(files),
        "stamp": asdict(stamp),
        **(extra or {}),
    }
    return _finish(doc)


def _acq_fingerprint(acquisition: AcquisitionRecord) -> str:
    return str(record_body(acquisition)["record_fingerprint"])


def build_derived_manifest(
    files_root: str | Path,
    parent: dict[str, Any],
    *,
    tool: str,
    description: str,
    config_sha256: dict[str, str],
    stamp: ProvenanceStamp,
) -> dict[str, Any]:
    """Manifest of processed files, linked to its raw (or derived) parent manifest."""
    validate_manifest_doc(parent)
    root = Path(files_root)
    files = [_entry(root, p, None, "derived", None) for p in sorted(root.rglob("*")) if p.is_file()]
    doc = {
        "manifest_type": "derived",
        "schema_version": MANIFEST_DOC_SCHEMA_VERSION,
        "synthetic": bool(parent["synthetic"]),
        "data_class": data_class(bool(parent["synthetic"])),
        "parent_manifest_sha256": parent["manifest_sha256"],
        "derivation": {
            "tool": tool,
            "description": description,
            "config_sha256": dict(config_sha256),
        },
        "files": files,
        "summary": _summary(files),
        "duplicates": _duplicates(files),
        "stamp": asdict(stamp),
    }
    return _finish(doc)


def validate_manifest_doc(doc: dict[str, Any]) -> None:
    """Validate a manifest document against the schema rules (mirrors configs/schemas)."""
    mtype = doc.get("manifest_type")
    if mtype not in ("raw", "derived"):
        raise DataValidationError("manifest_type must be 'raw' or 'derived'")
    required = RAW_REQUIRED if mtype == "raw" else DERIVED_REQUIRED
    missing = [k for k in required if k not in doc]
    if missing:
        raise DataValidationError(f"manifest missing required fields: {missing}")
    if doc["schema_version"] != MANIFEST_DOC_SCHEMA_VERSION:
        raise DataValidationError("unsupported manifest schema_version")
    if not isinstance(doc["synthetic"], bool):
        raise DataValidationError("synthetic must be a boolean")
    if doc["data_class"] != data_class(doc["synthetic"]):
        raise DataValidationError("data_class inconsistent with the synthetic flag")
    if mtype == "raw" and not doc["files"]:
        raise DataValidationError("empty raw manifest: no acquired files")
    if mtype == "raw":
        for gate, meta in doc["metadata_records"].items():
            if gate not in ("B3", "B4") or set(meta) != {
                "file_name",
                "sha256",
                "record_fingerprint",
            }:
                raise DataValidationError(f"malformed metadata_records entry {gate!r}")
    seen_paths: set[str] = set()
    seen_slots: set[tuple[str, str]] = set()
    for f in doc["files"]:
        miss = [k for k in FILE_REQUIRED if k not in f]
        if miss:
            raise DataValidationError(f"file entry missing {miss}")
        if f["file_type"] not in FILE_TYPES:
            raise DataValidationError(f"invalid file_type {f['file_type']!r}")
        if f["modality"] is not None and f["modality"] not in MODALITIES:
            raise DataValidationError(f"invalid modality {f['modality']!r}")
        sha = str(f["sha256"])
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise DataValidationError(f"malformed sha256 for {f['relpath']}")
        rel = str(f["relpath"])
        if not is_safe_relpath(rel):
            raise DataValidationError(f"non-relative path {rel}")
        if rel in seen_paths:
            raise DataValidationError(f"duplicate relpath {rel}")
        seen_paths.add(rel)
        if not isinstance(f["size_bytes"], int) or f["size_bytes"] < 0:
            raise DataValidationError(f"invalid size for {rel}")
        if f["file_type"] in ("image", "label") and f["case_id"]:
            slot = (str(f["case_id"]), str(f["modality"] or "label"))
            if slot in seen_slots:
                raise DataValidationError(f"duplicate {slot[1]} for case {slot[0]}")
            seen_slots.add(slot)
    if doc["summary"] != _summary(doc["files"]):
        raise DataValidationError("manifest summary inconsistent with files")
    if doc["duplicates"] != _duplicates(doc["files"]):
        raise DataValidationError("manifest duplicate groups inconsistent with files")
    if mtype == "raw":
        _validate_layout(doc)  # after the per-file path and summary checks
    if doc["manifest_sha256"] != content_sha256(doc):
        raise DataValidationError("manifest_sha256 does not match the manifest content")


def _validate_layout(doc: dict[str, Any]) -> None:
    """Collection/case provenance of a raw manifest (nested or flat; never flattened)."""
    layout = doc["source_layout"]
    if not isinstance(layout, dict) or set(layout) != {
        "layout",
        "collections",
        "data_root_reference",
    }:
        raise DataValidationError("malformed source_layout")
    if layout["layout"] not in LAYOUTS or layout["layout"] == "mixed":
        raise DataValidationError(f"invalid source_layout.layout {layout['layout']!r}")
    ref = layout["data_root_reference"]
    if ref is not None and not is_safe_relpath(str(ref)):
        raise DataValidationError("data_root_reference must be a safe relative path")
    for f in doc["files"]:
        coll = f.get("collection")
        if coll is not None and (
            not isinstance(coll, str) or "/" in coll or "\\" in coll or not coll.strip(".")
        ):
            raise DataValidationError(f"invalid collection {coll!r}")
        if f["file_type"] in ("image", "label") and f["case_id"]:
            expected = f"{case_relpath(coll, str(f['case_id']))}/{f['filename']}"
            if f["relpath"] != expected:
                raise DataValidationError(
                    f"{f['relpath']}: path does not match its collection/case ({expected})"
                )
    if doc["cases"] != _cases(doc["files"]):
        raise DataValidationError("manifest cases table inconsistent with files")
    if layout["collections"] != _collection_counts(doc["cases"]):
        raise DataValidationError("source_layout.collections inconsistent with cases")
    has_coll = any(c["collection"] is not None for c in doc["cases"])
    has_flat = any(c["collection"] is None for c in doc["cases"])
    if has_coll and has_flat:
        raise DataValidationError("mixed flat and nested cases in one manifest")
    if doc["cases"] and layout["layout"] != ("nested_collections" if has_coll else "flat"):
        raise DataValidationError("source_layout.layout inconsistent with cases")


def manifest_to_csv(doc: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(CSV_COLUMNS), lineterminator="\n")
    w.writeheader()
    for f in doc["files"]:
        w.writerow({k: ("" if f[k] is None else f[k]) for k in CSV_COLUMNS})
    return buf.getvalue()


def case_manifest_from_doc(doc: dict[str, Any], dataset: str) -> Manifest:
    """Case-level view (4 modalities + label per case) used by the B7+ stages."""
    validate_manifest_doc(doc)
    cases: dict[str, dict[str, FileRecord]] = defaultdict(dict)
    labels: dict[str, FileRecord] = {}
    for f in doc["files"]:
        if not f["case_id"] or f["file_type"] not in ("image", "label"):
            continue
        rec = FileRecord(relpath=f["relpath"], sha256=f["sha256"], size_bytes=int(f["size_bytes"]))
        if f["file_type"] == "label":
            labels[f["case_id"]] = rec
        else:
            cases[f["case_id"]][f["modality"]] = rec
    entries = tuple(
        ManifestEntry(case_id=c, images=dict(cases[c]), label=labels.get(c)) for c in sorted(cases)
    )
    m = Manifest(dataset=dataset, schema_version=1, entries=entries)
    validate_manifest(m)
    return m


def load_case_manifest(path: str | Path) -> Manifest:
    """Load a B5 raw manifest document (or a legacy case manifest) as a case-level Manifest."""
    from brats_uncertainty.utils.io import read_json

    raw = read_json(path)
    if isinstance(raw, dict) and raw.get("manifest_type") == "raw":
        return case_manifest_from_doc(raw, str(raw["dataset"]))
    if isinstance(raw, dict) and "manifest" in raw:
        return Manifest.from_dict(raw["manifest"])
    return Manifest.from_dict(raw)
