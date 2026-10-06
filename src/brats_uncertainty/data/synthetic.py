"""SYNTHETIC_TEST_DATA: tiny generated datasets for exercising B2-B6 software.

Synthetic data are never BraTS data and never results. Safeguards:

- Every synthetic tree has a root marker file ``SYNTHETIC_TEST_DATA.json`` that
  lists the SHA-256 of every file the generator wrote.
- Generation refuses any destination inside the repository (so synthetic
  files can never be committed or mistaken for ``data/raw``).
- The only "developer override" in the data stages is synthetic mode. It
  accepts an input only if the input is listed in its tree's marker **with a
  matching hash**. Arbitrary real files therefore cannot be processed through
  it, and the resulting records carry ``synthetic: true``. Records with that
  flag can never be used as gate evidence (``evaluation.status``).
- Case IDs use the ``SYN-`` prefix. Values in synthetic metadata files are
  generated, not copied from any source.
"""

from __future__ import annotations

import csv
import gzip
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from brats_uncertainty import __version__
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.utils.hashing import sha256_file
from brats_uncertainty.utils.paths import is_link, is_within

SYNTHETIC_LABEL = "SYNTHETIC_TEST_DATA"
MARKER_NAME = "SYNTHETIC_TEST_DATA.json"
SYNTHETIC_ROUTE = "SYNTHETIC_TEST_DATA (generated locally; not a data route)"
SYNTHETIC_MODALITY_SUFFIXES = {"T1": "_t1", "T1c": "_t1ce", "T2": "_t2", "FLAIR": "_flair"}
SYNTHETIC_LABEL_SUFFIX = "_seg"


def write_nifti_header_file(path: Path, shape: tuple[int, ...] = (4, 4, 3)) -> Path:
    """Write a minimal all-zero gzip NIfTI-1 file (a few hundred bytes)."""
    ndim = len(shape)
    dims = [ndim, *shape] + [1] * (7 - ndim)
    hdr = bytearray(348)
    struct.pack_into("<i", hdr, 0, 348)
    struct.pack_into("<8h", hdr, 40, *dims)
    struct.pack_into("<h", hdr, 70, 2)
    struct.pack_into("<h", hdr, 72, 8)
    struct.pack_into("<f", hdr, 108, 352.0)
    hdr[344:348] = b"n+1\x00"
    n_vox = 1
    for s in shape:
        n_vox *= s
    path.parent.mkdir(parents=True, exist_ok=True)
    # empty stored filename and mtime=0 -> identical content gives identical bytes
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as fh:
        fh.write(bytes(hdr) + b"\x00" * 4 + b"\x00" * n_vox)
    return path


@dataclass(frozen=True)
class SyntheticDataset:
    root: Path
    images_root: Path
    crosswalk: Path
    ucsf_metadata: Path
    case_ids: tuple[str, ...]


def generate_synthetic_dataset(
    dest: str | Path,
    *,
    repo_root: str | Path,
    n_cases: int = 3,
    crosswalk_counts: tuple[int, int] = (2, 1),
    shape: tuple[int, ...] = (4, 4, 3),
    collections: tuple[str, ...] | None = None,
) -> SyntheticDataset:
    """Generate a SYNTHETIC_TEST_DATA tree outside the repository.

    With ``collections`` the cases are spread round-robin over
    ``images/<collection>/<case_id>/`` (the official nested TCIA layout);
    otherwise ``images/<case_id>/``.

    ``crosswalk_counts`` = (number of site-1 rows, number of other-site rows)
    in the synthetic crosswalk. It is independent of ``n_cases`` so that the
    B6 logic can be tested at the protocol's target sizes without writing
    thousands of image files.
    """
    root = Path(dest).resolve()
    if is_within(root, repo_root):
        raise ProvenanceError("synthetic data must be generated outside the repository")
    if root.exists() and any(root.iterdir()):
        raise ProvenanceError(f"destination is not empty: {root}")
    images = root / "images"
    case_ids = tuple(f"SYN-{i:04d}" for i in range(n_cases))
    for i, cid in enumerate(case_ids):
        case_dir = images / collections[i % len(collections)] / cid if collections else images / cid
        for suffix in (*SYNTHETIC_MODALITY_SUFFIXES.values(), SYNTHETIC_LABEL_SUFFIX):
            write_nifti_header_file(case_dir / f"{cid}{suffix}.nii.gz", shape)
    crosswalk = root / "metadata" / "BraTS2021_MappingToTCIA.xlsx"
    _write_synthetic_crosswalk(crosswalk, *crosswalk_counts)
    ucsf = root / "metadata" / "UCSF-PDGM-metadata_v5.csv"
    with ucsf.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["ID", "Label"])
        w.writerow(["SYN-P0001", SYNTHETIC_LABEL])
    files = {
        p.relative_to(root).as_posix(): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    marker = {
        "label": SYNTHETIC_LABEL,
        "warning": "Synthetic test data. Not BraTS. Never a research result.",
        "generator": "brats_uncertainty.data.synthetic.generate_synthetic_dataset",
        "package_version": __version__,
        "files": files,
    }
    (root / MARKER_NAME).write_text(json.dumps(marker, indent=2, sort_keys=True), encoding="utf-8")
    return SyntheticDataset(root, images, crosswalk, ucsf, case_ids)


def _write_synthetic_crosswalk(path: Path, n_site1: int, n_other: int) -> None:
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "install the optional extra: pip install 'brats-uncertainty[io]'"
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SYNTHETIC_LABEL
    ws.append(
        [
            "Data Collection (as on TCIA+additional)",
            "Site ID",
            "PatientID on TCIA Radiology Portal",
            "BraTS2021 ID",
            "Segmentation (Task 1) Cohort",
        ]
    )  # the official header layout (confirmed 2026-10-06); values are SYNTHETIC
    for i in range(n_site1 + n_other):
        site = 1 if i < n_site1 else 18
        ws.append([SYNTHETIC_LABEL, site, f"SYN-P{i:04d}", f"SYN-{i:04d}", "Training"])
    ws.append([SYNTHETIC_LABEL, 18, "SYN-PV", "SYN-VALIDATION", "Validation"])  # filtered out
    wb.properties.creator = SYNTHETIC_LABEL
    wb.save(path)


def find_marker_root(path: str | Path) -> Path | None:
    p = Path(path).resolve()
    for candidate in (p, *p.parents):
        if (candidate / MARKER_NAME).is_file():
            return candidate
    return None


def require_synthetic(paths: list[Path], repo_root: str | Path) -> Path:
    """Verify that every path is a generator-listed file of one synthetic tree.

    For a directory, every file below it must be listed. Returns the tree root.
    """
    roots = {find_marker_root(p) for p in paths}
    if None in roots or len(roots) != 1:
        raise ProvenanceError("synthetic mode requires inputs inside one SYNTHETIC_TEST_DATA tree")
    root = roots.pop()
    assert root is not None
    if is_within(root, repo_root):
        raise ProvenanceError("synthetic trees may not live inside the repository")
    marker = json.loads((root / MARKER_NAME).read_text(encoding="utf-8"))
    if marker.get("label") != SYNTHETIC_LABEL:
        raise ProvenanceError("invalid SYNTHETIC_TEST_DATA marker")
    listed: dict[str, str] = marker["files"]
    for p in paths:
        p = Path(p)
        if is_link(p):
            raise ProvenanceError("symbolic links are not SYNTHETIC_TEST_DATA files")
        p = p.resolve()
        targets = [f for f in p.rglob("*") if f.is_file() or is_link(f)] if p.is_dir() else [p]
        for f in targets:
            if is_link(f):
                raise ProvenanceError("symbolic links are not SYNTHETIC_TEST_DATA files")
            try:
                rel = f.relative_to(root).as_posix()
            except ValueError as exc:
                raise ProvenanceError("input escapes its SYNTHETIC_TEST_DATA tree") from exc
            if rel == MARKER_NAME:
                continue
            if rel not in listed or listed[rel] != sha256_file(f):
                raise ProvenanceError(
                    f"{rel}: not a generator-listed synthetic file (or modified); "
                    "synthetic mode cannot be used for other files"
                )
    return root
