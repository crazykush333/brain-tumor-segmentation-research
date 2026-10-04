"""Machine-readable execution records for gates B2-B6 (schema version 3).

Every record is created by code from files that actually exist on disk. No
constructor path accepts a hash as input: hashes are always computed here from
the bytes read. Every record carries:

- ``synthetic`` (bool, explicit): true only for SYNTHETIC_TEST_DATA runs. Such
  records can never be gate evidence;
- a ``ProvenanceStamp``: code commit and clean flag, package version, protocol
  version and hash, the SHA-256 of every configuration file used, and the
  environment;
- a deterministic ``record_fingerprint``: the SHA-256 of the canonical JSON of
  the record without its volatile fields (``stamp.created_at``,
  ``stamp.environment``, ``acquired_at``). The same inputs, code and
  configuration give the same fingerprint.

Records contain only identifiers, relative paths, sizes, hashes, counts and
aggregate metadata: never images, labels or patient-level clinical data.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brats_uncertainty import __version__
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.utils.environment import capture_environment
from brats_uncertainty.utils.git import git_commit, git_is_dirty
from brats_uncertainty.utils.hashing import sha256_file, sha256_json
from brats_uncertainty.utils.io import read_json, write_json
from brats_uncertainty.utils.paths import is_link, is_safe_relpath

RECORD_SCHEMA_VERSION = 3
_SHA = re.compile(r"^[0-9a-f]{64}$")
# logical storage labels (e.g. "SYNTHETIC_TEST_DATA (temporary, outside repository)")
_LOGICAL = re.compile(r"^[A-Za-z][A-Za-z0-9_ ()\-]*(/[A-Za-z0-9_. ()\-]+)*$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

# Exact file names fixed by the protocol (§5, gates B3/B4).
CROSSWALK_FILENAME = "BraTS2021_MappingToTCIA.xlsx"
UCSF_METADATA_FILENAME = "UCSF-PDGM-metadata_v5.csv"

# B6 verification targets: design parameters of the frozen protocol, NOT facts
# verified from the source until a VERIFIED_FROM_SOURCE record exists.
B6_TARGETS = {"total": 1251, "held_out_institution": 511, "development": 740}
COUNT_STATES = (
    "EXPECTED_BY_PROTOCOL",  # targets only; no source processed
    "VERIFIED_FROM_SOURCE",  # REAL_RESEARCH_DATA crosswalk matched all targets
    "SYNTHETIC_TEST_ONLY",  # SYNTHETIC_TEST_DATA crosswalk matched (software test; never evidence)
    "FAILED_VERIFICATION",  # any mismatch
    "UNAVAILABLE",  # no source has been processed (gate B6 not executed)
)
# Explicit data classes, recorded in every record and manifest (not inferred from names).
SYNTHETIC_TEST_DATA = "SYNTHETIC_TEST_DATA"
REAL_RESEARCH_DATA = "REAL_RESEARCH_DATA"


def data_class(synthetic: bool) -> str:
    return SYNTHETIC_TEST_DATA if synthetic else REAL_RESEARCH_DATA


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ProvenanceStamp:
    created_at: str
    code_commit: str | None
    code_dirty: bool | None
    package_version: str
    protocol_version: str
    protocol_sha256: str
    config_sha256: dict[str, str]
    environment: dict[str, Any]


def make_stamp(
    repo_root: Path,
    *,
    require_clean_commit: bool = True,
    config_files: Sequence[Path] = (),
    clock: Clock = utc_now,
    environment: Mapping[str, Any] | None = None,
) -> ProvenanceStamp:
    """Stamp a record with the exact code, protocol and configuration state.

    Real-data records require a clean, committed checkout so that the record is
    reproducible from the recorded commit.
    """
    spec = load_protocol(repo_root)
    commit = git_commit(repo_root)
    dirty = git_is_dirty(repo_root)
    if require_clean_commit and (commit is None or dirty is not False):
        raise ProvenanceError(
            "B2-B6 records must be produced from a clean, committed checkout "
            f"(commit={commit}, dirty={dirty}). Commit or stash changes first."
        )
    configs: dict[str, str] = {}
    for c in config_files:
        p = Path(c)
        try:
            key = p.resolve().relative_to(Path(repo_root).resolve()).as_posix()
        except ValueError:
            key = p.name  # never record absolute paths
        configs[key] = sha256_file(p)
    return ProvenanceStamp(
        created_at=clock().isoformat(),
        code_commit=commit,
        code_dirty=dirty,
        package_version=__version__,
        protocol_version=spec.version,
        protocol_sha256=str(spec.raw["protocol"]["sha256"]),
        config_sha256=configs,
        environment=dict(environment) if environment is not None else capture_environment(),
    )


@dataclass(frozen=True)
class HashedFile:
    file_name: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_path(cls, path: str | Path) -> HashedFile:
        p = Path(path)
        return cls(file_name=p.name, sha256=sha256_file(p), size_bytes=p.stat().st_size)


@dataclass(frozen=True)
class InventoryEntry:
    relpath: str
    sha256: str
    size_bytes: int


def verify_inventory(expected: Iterable[InventoryEntry], root: str | Path) -> dict[str, list[str]]:
    """Compare a (re-)acquired tree with a recorded B2 inventory (nothing is modified).

    Ephemeral remote sessions (Kaggle/Colab) re-download the official files in every
    session; before use, the tree must be byte-identical to the committed B2 record.
    Returns ``missing``, ``mismatched`` (hash or size) and ``unexpected`` relpaths.
    """
    found = {e.relpath: e for e in inventory(root)}
    want = {e.relpath: e for e in expected}
    return {
        "missing": sorted(set(want) - set(found)),
        "mismatched": sorted(
            r
            for r in set(want) & set(found)
            if (want[r].sha256, want[r].size_bytes) != (found[r].sha256, found[r].size_bytes)
        ),
        "unexpected": sorted(set(found) - set(want)),
    }


def inventory(root: str | Path) -> tuple[InventoryEntry, ...]:
    """SHA-256 inventory of every file below ``root`` (sorted relative paths).

    Symbolic links are refused: they could point outside the storage root.
    """
    r = Path(root)
    entries = []
    for p in sorted(r.rglob("*")):
        if is_link(p):
            raise ProvenanceError(f"symbolic link in storage is not allowed: {p.relative_to(r)}")
        if p.is_file():
            entries.append(
                InventoryEntry(p.relative_to(r).as_posix(), sha256_file(p), p.stat().st_size)
            )
    return tuple(entries)


@dataclass(frozen=True)
class SourceInfo:
    """Where the data came from. Entered by the operator from the official page."""

    dataset: str
    dataset_version: str
    doi: str
    source_url: str
    route: str  # must be the route approved at gate B1 (real data)

    def validate(self) -> None:
        for k, v in asdict(self).items():
            if not str(v).strip():
                raise ProvenanceError(f"source field {k!r} is empty")
        if not self.source_url.startswith("https://"):
            raise ProvenanceError("source_url must be an https URL of the official source")
        if not self.doi.startswith("10."):
            raise ProvenanceError("doi must be a DOI (10.xxxx/...)")


@dataclass(frozen=True)
class AcquisitionRecord:
    """Gate B2: files acquired via the approved route, with their inventory."""

    gate: str
    synthetic: bool
    source: SourceInfo
    adapter: str
    acquired_at: str
    acquired_by: str
    storage_location: str  # repository-relative or logical label; never an absolute path
    inventory: tuple[InventoryEntry, ...]
    stamp: ProvenanceStamp
    schema_version: int = RECORD_SCHEMA_VERSION
    notes: str = ""

    def validate(self) -> None:
        if self.gate != "B2":
            raise ProvenanceError("acquisition records belong to gate B2")
        self.source.validate()
        if not _ISO_DATETIME.match(self.acquired_at):
            raise ProvenanceError("acquired_at must be an ISO-8601 timestamp")
        if not self.acquired_by.strip() or not self.adapter.strip():
            raise ProvenanceError("acquired_by and adapter are required")
        _check_location(self.storage_location)
        if not self.inventory:
            raise ProvenanceError("an acquisition record must inventory at least one file")
        _check_entries(self.inventory)


@dataclass(frozen=True)
class MetadataFileRecord:
    """Gates B3/B4: exact SHA-256 of a metadata file as used."""

    gate: str
    synthetic: bool
    kind: str
    file: HashedFile
    path_reference: str
    source_url: str
    doi: str
    stamp: ProvenanceStamp
    schema_version: int = RECORD_SCHEMA_VERSION

    def validate(self) -> None:
        expected = {
            "B3": ("crosswalk", CROSSWALK_FILENAME),
            "B4": ("ucsf_pdgm_metadata", UCSF_METADATA_FILENAME),
        }
        if self.gate not in expected:
            raise ProvenanceError("metadata file records belong to gate B3 or B4")
        kind, name = expected[self.gate]
        if self.kind != kind or self.file.file_name != name:
            raise ProvenanceError(f"gate {self.gate} requires file {name!r} (kind {kind!r})")
        if not self.source_url.startswith("https://"):
            raise ProvenanceError("source_url must be an https URL of the official source")
        _check_location(self.path_reference)
        _check_entries(
            (InventoryEntry(self.file.file_name, self.file.sha256, self.file.size_bytes),)
        )


@dataclass(frozen=True)
class CountsRecord:
    """Gate B6: counts derived from the hashed crosswalk and checked against the protocol."""

    gate: str
    synthetic: bool
    status: str  # VERIFIED_FROM_SOURCE (real) | SYNTHETIC_TEST_ONLY | FAILED_VERIFICATION
    crosswalk_sha256: str
    crosswalk_matches_b3: bool
    b3_record_fingerprint: str
    counts: dict[str, int]
    targets: dict[str, int]
    checks: dict[str, bool]
    diagnostics: list[str]
    site_counts: dict[str, int]
    hoi_site_id: str
    development_ids_sha256: str
    hoi_ids_sha256: str
    stamp: ProvenanceStamp
    schema_version: int = RECORD_SCHEMA_VERSION

    def validate(self) -> None:
        if self.gate != "B6":
            raise ProvenanceError("counts records belong to gate B6")
        for h in (
            self.crosswalk_sha256,
            self.b3_record_fingerprint,
            self.development_ids_sha256,
            self.hoi_ids_sha256,
        ):
            if not _SHA.match(h):
                raise ProvenanceError("malformed SHA-256 in counts record")
        success = "SYNTHETIC_TEST_ONLY" if self.synthetic else "VERIFIED_FROM_SOURCE"
        if self.status not in (success, "FAILED_VERIFICATION"):
            raise ProvenanceError(
                f"counts record status must be {success} or FAILED_VERIFICATION "
                f"for {data_class(self.synthetic)}"
            )
        if self.targets != B6_TARGETS:
            raise ProvenanceError("B6 targets differ from the frozen protocol targets")
        expected_checks = {k: self.counts.get(k) == v for k, v in self.targets.items()}
        if self.checks != expected_checks:
            raise ProvenanceError("counts record checks inconsistent with counts and targets")
        ok = all(self.checks.values()) and self.crosswalk_matches_b3
        if (self.status == success) != ok:
            raise ProvenanceError("counts record status inconsistent with its checks")
        if not ok and not self.diagnostics:
            raise ProvenanceError("a failed verification must carry diagnostics")


def protocol_count_targets() -> dict[str, Any]:
    """The B6 targets in the EXPECTED_BY_PROTOCOL state (not verified from any source)."""
    return {
        "status": "EXPECTED_BY_PROTOCOL",
        "label": "Protocol verification targets (not yet verified from the source file)",
        "targets": dict(B6_TARGETS),
    }


def _check_location(loc: str) -> None:
    if not loc.strip():
        raise ProvenanceError("storage location / path reference is required")
    parts = loc.replace("\\", "/").split("/")
    if any(p.strip() in (".", "..") for p in parts) or (
        not is_safe_relpath(loc.replace(" ", "_")) and not _LOGICAL.match(loc)
    ):
        raise ProvenanceError(
            "record locations must be repository-relative or logical, never absolute"
        )


def _check_entries(entries: Sequence[InventoryEntry]) -> None:
    seen: set[str] = set()
    for e in entries:
        if not _SHA.match(e.sha256):
            raise ProvenanceError(f"malformed SHA-256 for {e.relpath}")
        if e.size_bytes <= 0:
            raise ProvenanceError(f"empty file recorded: {e.relpath}")
        if e.relpath in seen:
            raise ProvenanceError(f"duplicate path in inventory: {e.relpath}")
        seen.add(e.relpath)


Record = AcquisitionRecord | MetadataFileRecord | CountsRecord
_VOLATILE = (("stamp", "created_at"), ("stamp", "environment"), ("acquired_at",))


def fingerprint(body: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 of a record body without volatile fields."""
    b = copy.deepcopy(dict(body))
    b.pop("record_fingerprint", None)
    for path in _VOLATILE:
        node: Any = b
        for k in path[:-1]:
            node = node.get(k, {}) if isinstance(node, dict) else {}
        if isinstance(node, dict):
            node.pop(path[-1], None)
    return sha256_json(b)


def record_body(record: Record) -> dict[str, Any]:
    """Validated record as a dict with its explicit data class and fingerprint (computed last)."""
    record.validate()
    body = asdict(record)
    body["data_class"] = data_class(record.synthetic)
    body["record_fingerprint"] = fingerprint(body)
    return body


def write_record(path: str | Path, record: Record) -> Path:
    return write_json(path, record_body(record))


def read_record_body(path: str | Path) -> dict[str, Any]:
    body: dict[str, Any] = read_json(path)
    if not isinstance(body, dict):
        raise ProvenanceError(f"{path}: a record must be a JSON object")
    if body.get("schema_version") != RECORD_SCHEMA_VERSION:
        raise ProvenanceError(f"{path}: unsupported record schema {body.get('schema_version')!r}")
    if body.get("record_fingerprint") != fingerprint(body):
        raise ProvenanceError(f"{path}: record fingerprint mismatch (record was modified)")
    if not isinstance(body.get("synthetic"), bool) or body.get("data_class") != data_class(
        body["synthetic"]
    ):
        raise ProvenanceError(f"{path}: data_class inconsistent with the synthetic flag")
    return body


def _stamp(d: Mapping[str, Any]) -> ProvenanceStamp:
    return ProvenanceStamp(**dict(d))


def read_metadata_record(path: str | Path) -> MetadataFileRecord:
    raw = read_record_body(path)
    rec = MetadataFileRecord(
        gate=raw["gate"],
        synthetic=bool(raw["synthetic"]),
        kind=raw["kind"],
        file=HashedFile(**raw["file"]),
        path_reference=raw["path_reference"],
        source_url=raw["source_url"],
        doi=raw["doi"],
        stamp=_stamp(raw["stamp"]),
        schema_version=int(raw["schema_version"]),
    )
    rec.validate()
    return rec


def read_counts_record(path: str | Path) -> CountsRecord:
    raw = read_record_body(path)
    rec = CountsRecord(
        gate=raw["gate"],
        synthetic=bool(raw["synthetic"]),
        status=raw["status"],
        crosswalk_sha256=raw["crosswalk_sha256"],
        crosswalk_matches_b3=bool(raw["crosswalk_matches_b3"]),
        b3_record_fingerprint=raw["b3_record_fingerprint"],
        counts=dict(raw["counts"]),
        targets=dict(raw["targets"]),
        checks=dict(raw["checks"]),
        diagnostics=list(raw["diagnostics"]),
        site_counts=dict(raw["site_counts"]),
        hoi_site_id=raw["hoi_site_id"],
        development_ids_sha256=raw["development_ids_sha256"],
        hoi_ids_sha256=raw["hoi_ids_sha256"],
        stamp=_stamp(raw["stamp"]),
        schema_version=int(raw["schema_version"]),
    )
    rec.validate()
    return rec


def read_acquisition_record(path: str | Path) -> AcquisitionRecord:
    raw = read_record_body(path)
    rec = AcquisitionRecord(
        gate=raw["gate"],
        synthetic=bool(raw["synthetic"]),
        source=SourceInfo(**raw["source"]),
        adapter=raw["adapter"],
        acquired_at=raw["acquired_at"],
        acquired_by=raw["acquired_by"],
        storage_location=raw["storage_location"],
        inventory=tuple(InventoryEntry(**e) for e in raw["inventory"]),
        stamp=_stamp(raw["stamp"]),
        schema_version=int(raw["schema_version"]),
        notes=raw.get("notes", ""),
    )
    rec.validate()
    return rec


__all__ = [
    "B6_TARGETS",
    "COUNT_STATES",
    "CROSSWALK_FILENAME",
    "REAL_RESEARCH_DATA",
    "SYNTHETIC_TEST_DATA",
    "UCSF_METADATA_FILENAME",
    "AcquisitionRecord",
    "Clock",
    "CountsRecord",
    "HashedFile",
    "InventoryEntry",
    "MetadataFileRecord",
    "ProvenanceStamp",
    "SourceInfo",
    "data_class",
    "fingerprint",
    "inventory",
    "make_stamp",
    "protocol_count_targets",
    "read_acquisition_record",
    "read_counts_record",
    "read_metadata_record",
    "read_record_body",
    "record_body",
    "utc_now",
    "write_record",
]
