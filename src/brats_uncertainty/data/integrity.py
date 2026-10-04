"""Dataset integrity validation (supports gates B2/B5 and C2).

Produces a report of issues instead of stopping at the first problem, so the
whole tree is audited in one pass. Checks:

- expected file existence and file-naming conventions (dataset schema);
- modality completeness (T1, T1c, T2, FLAIR) and label availability;
- case discovery in a flat (``root/<case>``) or nested-collection
  (``root/<collection>/<case>``, the official TCIA delivery) tree, see
  ``data.layout``; the tree is never flattened;
- duplicate or colliding case IDs (also across collections); expected-vs-found
  case IDs; the configured layout (``layout.tree``);
- unexpected files and unexpected nesting (root, collections, case directories);
- corrupt files: gzip stream integrity (CRC) and NIfTI-1/2 header validity;
- dimensional consistency across a case's modalities and label;
- hash mismatches against a previously recorded manifest.

No image voxels are loaded: headers are parsed with the standard library, and
gzip integrity is checked by streaming. Must only be run on data acquired
through the B1-approved route (guarded action ``validate_data``).
"""

from __future__ import annotations

import gzip
import struct
import zlib
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from brats_uncertainty.data.layout import discover_cases
from brats_uncertainty.data.manifest import Manifest, verify_manifest
from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.preprocessing.modalities import MODALITIES
from brats_uncertainty.utils.paths import is_link

_CHUNK = 1 << 20


class CorruptFileError(Exception):
    """A file could not be decompressed or does not carry a valid NIfTI header."""


@dataclass(frozen=True)
class NiftiHeaderInfo:
    version: int
    shape: tuple[int, ...]
    datatype: int


def _open(path: Path) -> Any:
    return gzip.open(path, "rb") if path.name.endswith(".gz") else path.open("rb")


def check_gzip_stream(path: str | Path) -> None:
    """Read a .gz file to the end so that its CRC and length are verified."""
    p = Path(path)
    try:
        with gzip.open(p, "rb") as fh:
            while fh.read(_CHUNK):
                pass
    except (OSError, EOFError, zlib.error) as exc:
        raise CorruptFileError(f"{p.name}: corrupt gzip stream ({exc})") from exc


def read_nifti_header(path: str | Path) -> NiftiHeaderInfo:
    """Parse the NIfTI-1 or NIfTI-2 header (either byte order) without nibabel."""
    p = Path(path)
    try:
        with _open(p) as fh:
            head = fh.read(540)
    except (OSError, EOFError, zlib.error) as exc:
        raise CorruptFileError(f"{p.name}: unreadable ({exc})") from exc
    if len(head) < 348:
        raise CorruptFileError(f"{p.name}: file too short for a NIfTI header")
    for endian in ("<", ">"):
        (size,) = struct.unpack(f"{endian}i", head[:4])
        if size == 348 and head[344:348] in (b"n+1\x00", b"ni1\x00"):
            dims = struct.unpack(f"{endian}8h", head[40:56])
            (datatype,) = struct.unpack(f"{endian}h", head[70:72])
            return _info(p, 1, dims, datatype)
        if size == 540 and len(head) >= 540 and head[4:8] in (b"n+2\x00", b"ni2\x00"):
            (datatype,) = struct.unpack(f"{endian}h", head[12:14])
            dims = struct.unpack(f"{endian}8q", head[16:80])
            return _info(p, 2, dims, datatype)
    raise CorruptFileError(f"{p.name}: no valid NIfTI-1/2 header")


def _info(p: Path, version: int, dims: Sequence[int], datatype: int) -> NiftiHeaderInfo:
    ndim = int(dims[0])
    if not 1 <= ndim <= 7 or any(int(d) <= 0 for d in dims[1 : ndim + 1]):
        raise CorruptFileError(f"{p.name}: invalid dimensions {tuple(dims)}")
    return NiftiHeaderInfo(
        version=version, shape=tuple(int(d) for d in dims[1 : ndim + 1]), datatype=datatype
    )


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning"
    code: str
    path: str
    message: str


@dataclass
class IntegrityReport:
    dataset: str
    layout: str = "empty"
    collections: dict[str, int] = field(default_factory=dict)
    n_case_dirs: int = 0
    n_complete_cases: int = 0
    n_cases_with_label: int = 0
    shapes: dict[str, int] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def add(self, severity: str, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(severity, code, path, message))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        d["n_errors"] = len(self.errors)
        d["n_warnings"] = len(self.issues) - len(self.errors)
        return d


def validate_dataset_tree(
    data_root: str | Path,
    schema: DatasetSchema,
    *,
    require_labels: bool = True,
    deep: bool = True,
    expected_case_ids: Iterable[str] | None = None,
    expected_shape: Sequence[int] | None = None,
    manifest: Manifest | None = None,
    expected_layout: str | None = None,
) -> IntegrityReport:
    """Audit ``data_root/[<collection>/]<case_id>/`` against the dataset schema."""
    root = Path(data_root)
    report = IntegrityReport(dataset=schema.name)
    if not root.is_dir():
        report.add("error", "missing_root", str(root), "data root does not exist")
        return report
    found = discover_cases(root, schema)
    report.layout = found.layout
    report.collections = found.collections
    for issue in found.issues:
        report.add(issue.severity, issue.code, issue.path, issue.message)
    if expected_layout is not None and found.cases and found.layout != expected_layout:
        report.add(
            "error",
            "unexpected_layout",
            ".",
            f"tree layout {found.layout!r} differs from the configured {expected_layout!r}",
        )
    for case in found.cases:
        report.n_case_dirs += 1
        _validate_case(
            case.path,
            case.case_id,
            case.relpath,
            schema,
            report,
            require_labels,
            deep,
            expected_shape,
        )
    if expected_case_ids is not None:
        expected = set(expected_case_ids)
        present = {c.case_id for c in found.cases}
        for cid in sorted(expected - present):
            report.add("error", "missing_case", cid, "expected case not found")
        for cid in sorted(present - expected):
            report.add("error", "unexpected_case", cid, "case not in the expected list")
    if manifest is not None:
        for rel in verify_manifest(manifest, root):
            report.add(
                "error", "hash_mismatch", rel, "file missing or SHA-256 differs from manifest"
            )
    return report


def _validate_case(
    case_dir: Path,
    case_id: str,
    rel: str,
    schema: DatasetSchema,
    report: IntegrityReport,
    require_labels: bool,
    deep: bool,
    expected_shape: Sequence[int] | None,
) -> None:
    expected_names = {schema.image_name(case_id, m): m for m in MODALITIES}
    label_name = schema.label_name(case_id)
    children = sorted(case_dir.iterdir(), key=lambda p: p.name)
    for p in children:
        if is_link(p):
            report.add(
                "error", "link", f"{rel}/{p.name}", "symbolic link or junction (not followed)"
            )
        elif p.is_dir():
            report.add(
                "error",
                "unexpected_nested_structure",
                f"{rel}/{p.name}",
                "subdirectory inside a case directory",
            )
    present = {p.name for p in children if not is_link(p) and p.is_file()}
    for name in sorted(present - set(expected_names) - {label_name}):
        report.add("warning", "unexpected_file", f"{rel}/{name}", "file not in the dataset schema")
    complete = True
    shapes: dict[str, tuple[int, ...]] = {}
    for name, modality in expected_names.items():
        if name not in present:
            report.add("error", "missing_modality", f"{rel}/{name}", f"{modality} missing")
            complete = False
            continue
        shape = _check_file(case_dir / name, f"{rel}/{name}", report, deep)
        if shape is None:
            complete = False
        else:
            shapes[modality] = shape
    if label_name in present:
        report.n_cases_with_label += 1
        shape = _check_file(case_dir / label_name, f"{rel}/{label_name}", report, deep)
        if shape is not None:
            shapes["label"] = shape
    elif require_labels:
        report.add("error", "missing_label", f"{rel}/{label_name}", "label missing")
    distinct = set(shapes.values())
    if len(distinct) > 1:
        report.add("error", "dimension_mismatch", rel, f"shapes differ: {shapes}")
    for s in distinct:
        report.shapes[str(list(s))] = report.shapes.get(str(list(s)), 0) + 1
        if len(s) != 3:
            report.add("error", "not_3d", rel, f"volume is not 3-D: {s}")
        if expected_shape is not None and tuple(s) != tuple(expected_shape):
            report.add("warning", "unexpected_shape", rel, f"shape {s} != {tuple(expected_shape)}")
    if complete:
        report.n_complete_cases += 1


def _check_file(
    path: Path, rel: str, report: IntegrityReport, deep: bool
) -> tuple[int, ...] | None:
    try:
        if deep and path.name.endswith(".gz"):
            check_gzip_stream(path)
        info = read_nifti_header(path)
    except CorruptFileError as exc:
        report.add("error", "corrupt_file", rel, str(exc))
        return None
    return info.shape
