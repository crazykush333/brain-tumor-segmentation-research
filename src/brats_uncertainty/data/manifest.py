"""Data manifest: one row per case with relative paths and SHA-256 of every file.

Hashes are computed from the bytes on disk only. A manifest cannot be built for
files that do not exist, and there is no API to set a hash by hand.
The manifest itself is hashed (canonical JSON) and the hash is recorded at B5.
Manifests of real data contain case IDs and file hashes only, never images or
labels; they are committed only if the data licence permits (see
docs/data/DATA_ACCESS.md).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.preprocessing.modalities import MODALITIES
from brats_uncertainty.utils.hashing import sha256_file, sha256_json

MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FileRecord:
    relpath: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ManifestEntry:
    case_id: str
    images: dict[str, FileRecord]  # keyed by protocol modality
    label: FileRecord | None


@dataclass(frozen=True)
class Manifest:
    dataset: str
    schema_version: int
    entries: tuple[ManifestEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "schema_version": self.schema_version,
            "entries": [asdict(e) for e in self.entries],
        }

    @property
    def sha256(self) -> str:
        return sha256_json(self.to_dict())

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(e.case_id for e in self.entries)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Manifest:
        entries = []
        for e in d["entries"]:
            label = FileRecord(**e["label"]) if e.get("label") else None
            entries.append(
                ManifestEntry(
                    case_id=e["case_id"],
                    images={k: FileRecord(**v) for k, v in e["images"].items()},
                    label=label,
                )
            )
        m = cls(
            dataset=d["dataset"], schema_version=int(d["schema_version"]), entries=tuple(entries)
        )
        validate_manifest(m)
        return m


def _record(root: Path, path: Path) -> FileRecord:
    if not path.is_file():
        raise DataValidationError(f"missing file: {path.relative_to(root).as_posix()}")
    return FileRecord(
        relpath=path.relative_to(root).as_posix(),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def build_manifest(
    data_root: str | Path, schema: DatasetSchema, *, require_labels: bool = True
) -> Manifest:
    """Scan ``data_root/[<collection>/]<case_id>/`` directories and hash every expected file.

    Flat and nested-collection trees are both supported (``data.layout``); relpaths keep
    the collection directory. Any layout error fails closed.
    """
    from brats_uncertainty.data.layout import discover_cases

    root = Path(data_root).resolve()
    if not root.is_dir():
        raise DataValidationError(f"data root does not exist: {root}")
    found = discover_cases(root, schema)
    if found.errors:
        e = found.errors[0]
        raise DataValidationError(f"invalid data tree for {schema.name}: {e.code} {e.path}")
    entries: list[ManifestEntry] = []
    for case in found.cases:
        case_dir, case_id = case.path, case.case_id
        images = {m: _record(root, case_dir / schema.image_name(case_id, m)) for m in MODALITIES}
        label_path = case_dir / schema.label_name(case_id)
        label = _record(root, label_path) if require_labels or label_path.exists() else None
        entries.append(ManifestEntry(case_id=case_id, images=images, label=label))
    manifest = Manifest(
        dataset=schema.name, schema_version=MANIFEST_SCHEMA_VERSION, entries=tuple(entries)
    )
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Manifest) -> None:
    """Structural checks: unique IDs, 4 modalities, well-formed hashes, relative paths."""
    ids = [e.case_id for e in manifest.entries]
    dup_ids = sorted({i for i in ids if ids.count(i) > 1})
    if dup_ids:
        raise DataValidationError(f"duplicate case IDs: {dup_ids[:10]}")
    for e in manifest.entries:
        if set(e.images) != set(MODALITIES):
            raise DataValidationError(
                f"{e.case_id}: modalities {sorted(e.images)} != {sorted(MODALITIES)}"
            )
        for rec in (*e.images.values(), *([e.label] if e.label else [])):
            if len(rec.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in rec.sha256):
                raise DataValidationError(f"{e.case_id}: malformed sha256 for {rec.relpath}")
            if Path(rec.relpath).is_absolute() or ".." in Path(rec.relpath).parts:
                raise DataValidationError(f"{e.case_id}: non-relative path {rec.relpath}")
    # Identical contents are reported by duplicate_content() and must be reviewed
    # and logged by the caller; they are not silently dropped or auto-resolved.


def duplicate_content(manifest: Manifest) -> list[list[str]]:
    """Groups of files with identical SHA-256 (identical-image-hash check, §7)."""
    by_hash: dict[str, list[str]] = defaultdict(list)
    for e in manifest.entries:
        for rec in (*e.images.values(), *([e.label] if e.label else [])):
            by_hash[rec.sha256].append(rec.relpath)
    return [sorted(v) for v in by_hash.values() if len(v) > 1]


def cross_manifest_duplicates(a: Manifest, b: Manifest) -> list[tuple[str, str]]:
    """Image files with identical hashes across two datasets (e.g. BraTS-Africa vs BraTS 2021)."""
    ha = {r.sha256: r.relpath for e in a.entries for r in e.images.values()}
    return sorted(
        (ha[r.sha256], r.relpath) for e in b.entries for r in e.images.values() if r.sha256 in ha
    )


def verify_manifest(manifest: Manifest, data_root: str | Path) -> list[str]:
    """Re-hash files on disk; return relpaths whose hash or presence differs."""
    root = Path(data_root).resolve()
    bad: list[str] = []
    for e in manifest.entries:
        for rec in (*e.images.values(), *([e.label] if e.label else [])):
            p = root / rec.relpath
            if not p.is_file() or sha256_file(p) != rec.sha256:
                bad.append(rec.relpath)
    return bad
