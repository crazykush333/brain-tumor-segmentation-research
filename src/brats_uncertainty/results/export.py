"""Copy public-safe artifacts from a remote run's export folder back toward the repository.

Only these file types are ever copied: ``.json .csv .md .png .svg .txt``. Everything
else (checkpoints, NIfTI/DICOM, archives, arrays, spreadsheets, licensed metadata,
credentials) is skipped and listed in the report, never copied. The export fails
closed (nothing copied) on symbolic links, on imaging/archive content disguised
under an allowed name (magic-byte sniffing), on files above the repository size
limit, on invalid or synthetic ``*.metrics.json`` files, on invalid
``run_manifest.json`` statuses and on synthetic demonstration files
(``brats_uncertainty.demo``): demo artifacts are never exported as research results.
Existing destination files are never overwritten.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from brats_uncertainty.compute.jobs import MANIFEST_NAME, RUN_STATUSES
from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.repo_checks import (
    MAX_FILE_BYTES,
    PROHIBITED_NAME_PATTERNS,
    PROHIBITED_NAMES,
    sniff_imaging,
)
from brats_uncertainty.results.metric_records import validate_metric_file
from brats_uncertainty.utils.paths import is_link

ALLOWED_SUFFIXES = (".json", ".csv", ".md", ".png", ".svg", ".txt")


@dataclass
class ExportReport:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def export_public_artifacts(source: Path, dest: Path) -> ExportReport:
    if is_link(source) or not source.is_dir():
        raise ProvenanceError("export source must be an existing directory (not a link)")
    report = ExportReport()
    plan: list[tuple[Path, str]] = []
    for p in sorted(source.rglob("*")):
        rel = p.relative_to(source).as_posix()
        if is_link(p):
            raise ProvenanceError(f"symbolic link in export: {rel}")
        if not p.is_file():
            continue
        name = p.name
        if (
            p.suffix.lower() not in ALLOWED_SUFFIXES
            or name in PROHIBITED_NAMES
            or any(pat.match(name) for pat in PROHIBITED_NAME_PATTERNS)
        ):
            report.skipped.append(rel)
            continue
        from brats_uncertainty.demo import is_demo_artifact

        if is_demo_artifact(p):
            raise ProvenanceError(
                f"{rel}: synthetic demonstration file; never exported as a result"
            )
        sniffed = sniff_imaging(p)
        if sniffed:
            raise ProvenanceError(f"{rel}: {sniffed} content under an allowed name")
        if p.stat().st_size > MAX_FILE_BYTES:
            raise ProvenanceError(f"{rel}: larger than the repository file-size limit")
        if name.endswith(".metrics.json"):
            validate_metric_file(p)  # refuses synthetic and malformed records
        if name == MANIFEST_NAME:
            status = json.loads(p.read_text(encoding="utf-8")).get("status")
            if status not in RUN_STATUSES:
                raise ProvenanceError(f"{rel}: invalid run status {status!r}")
        if (dest / rel).exists():
            raise FileExistsError(f"refusing to overwrite {rel}")
        plan.append((p, rel))
    for p, rel in plan:  # copy only after every file passed
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest / rel)
        report.copied.append(rel)
    return report
