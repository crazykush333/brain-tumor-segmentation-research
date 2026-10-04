"""Case discovery for acquired training trees (gates B2/B5): flat or nested-collection layout.

The official TCIA BraTS 2021 delivery (B2 pre-flight, 2026-10-01) is::

    BraTS2021_TrainingSet/<collection>/<case_id>/<case_id>_<suffix>.nii.gz

where ``<collection>`` is a source group (ACRIN-FMISO-Brain, ..., UPENN-GBM,
new-not-previously-in-TCIA). The tree is never flattened or rearranged: each
case keeps its collection and its path relative to the training root.

Discovery is deterministic (entries sorted by name) and reports issues
instead of guessing:

- ``link``: a symbolic link or junction anywhere (never followed);
- ``duplicate_case_id``: the same case ID (case-insensitive) twice, also
  across collections;
- ``malformed_case_dir``: a directory holding data files whose name is not a
  valid case ID;
- ``invalid_collection_name``: a collection name with unsafe characters;
- ``empty_collection``: a collection directory without cases;
- ``unexpected_nested_structure``: deeper nesting than root/<collection>/<case>;
- ``mixed_layout``: case directories both at the root and inside collections;
- ``unexpected_file``: a stray file at the root or in a collection (warning).

Case-directory *contents* (modalities, label, corrupt files) are validated by
``data.integrity``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from brats_uncertainty.data.schema import DatasetSchema
from brats_uncertainty.utils.paths import is_link

LAYOUTS = ("flat", "nested_collections", "empty", "mixed")
_COLLECTION_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class CaseLocation:
    """One case directory: its collection (None in a flat tree) and path below the root."""

    collection: str | None
    case_id: str
    relpath: str  # POSIX path relative to the training root, e.g. "UCSF-PDGM/BraTS2021_00026"
    path: Path


@dataclass(frozen=True)
class LayoutIssue:
    severity: str  # "error" | "warning"
    code: str
    path: str
    message: str


@dataclass
class Discovery:
    cases: list[CaseLocation] = field(default_factory=list)
    issues: list[LayoutIssue] = field(default_factory=list)
    stray_files: list[tuple[str | None, Path]] = field(default_factory=list)  # (collection, path)
    layout: str = "empty"

    @property
    def errors(self) -> list[LayoutIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def collections(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.cases:
            if c.collection is not None:
                out[c.collection] = out.get(c.collection, 0) + 1
        return dict(sorted(out.items()))


def _holds_data_files(d: Path, schema: DatasetSchema) -> bool:
    return any(
        p.is_file() and not is_link(p) and p.name.endswith(schema.file_ending) for p in d.iterdir()
    )


def discover_cases(data_root: str | Path, schema: DatasetSchema) -> Discovery:
    """Find case directories at ``root/<case>`` or ``root/<collection>/<case>`` (see module doc)."""
    root = Path(data_root)
    out = Discovery()
    seen: dict[str, str] = {}

    def add_case(collection: str | None, d: Path, rel: str) -> None:
        key = d.name.lower()
        if key in seen:
            out.issues.append(
                LayoutIssue("error", "duplicate_case_id", rel, f"case ID also at {seen[key]}")
            )
            return
        seen[key] = rel
        out.cases.append(CaseLocation(collection, d.name, rel, d))

    flat = nested = 0
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        rel = entry.name
        if is_link(entry):
            out.issues.append(LayoutIssue("error", "link", rel, "symbolic link or junction"))
            continue
        if entry.is_file():
            out.issues.append(
                LayoutIssue("warning", "unexpected_file", rel, "file at the training root")
            )
            out.stray_files.append((None, entry))
            continue
        if schema.is_valid_case_id(entry.name):
            flat += 1
            add_case(None, entry, rel)
            continue
        if _holds_data_files(entry, schema):
            out.issues.append(
                LayoutIssue(
                    "error",
                    "malformed_case_dir",
                    rel,
                    "directory holds data files but its name is not a valid case ID",
                )
            )
            continue
        if not _COLLECTION_NAME.match(entry.name):
            out.issues.append(
                LayoutIssue("error", "invalid_collection_name", rel, "unsafe collection name")
            )
            continue
        n_before = len(out.cases)
        for sub in sorted(entry.iterdir(), key=lambda p: p.name):
            srel = f"{rel}/{sub.name}"
            if is_link(sub):
                out.issues.append(LayoutIssue("error", "link", srel, "symbolic link or junction"))
            elif sub.is_file():
                out.issues.append(
                    LayoutIssue("warning", "unexpected_file", srel, "file inside a collection")
                )
                out.stray_files.append((entry.name, sub))
            elif schema.is_valid_case_id(sub.name):
                nested += 1
                add_case(entry.name, sub, srel)
            else:
                out.issues.append(
                    LayoutIssue(
                        "error",
                        "unexpected_nested_structure",
                        srel,
                        "directory inside a collection is not a case directory (not followed)",
                    )
                )
        if len(out.cases) == n_before and not any(
            i.path.startswith(f"{rel}/") and i.code == "duplicate_case_id" for i in out.issues
        ):
            out.issues.append(LayoutIssue("error", "empty_collection", rel, "no case directories"))
    if flat and nested:
        out.issues.append(
            LayoutIssue(
                "error", "mixed_layout", ".", "case directories at the root and inside collections"
            )
        )
        out.layout = "mixed"
    elif nested:
        out.layout = "nested_collections"
    elif flat:
        out.layout = "flat"
    return out


def case_relpath(collection: str | None, case_id: str) -> str:
    return case_id if collection is None else f"{collection}/{case_id}"
