"""Repository hygiene checks: prohibited files, secrets and protocol integrity.

Run in CI and before every commit (``brats-uncertainty check-repo``). Scans all
tracked files plus untracked files that are not git-ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from brats_uncertainty.data.evidence import is_synthetic_b1_text
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.utils.git import git_tracked_files

PROHIBITED_SUFFIXES = (
    ".nii",
    ".nii.gz",
    ".dcm",
    ".mha",
    ".mhd",
    ".nrrd",
    ".mgz",
    ".h5",
    ".hdf5",
    ".npz",
    ".npy",
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".pem",
    ".key",
    ".zip",
    ".tar",
    ".tgz",
    ".7z",
    ".xlsx",
    ".xls",
)
PROHIBITED_NAMES = (
    "kaggle.json",
    ".env",
    ".synapseConfig",
    ".netrc",
    "BraTS2021_MappingToTCIA.xlsx",
)
PROHIBITED_NAME_PATTERNS = (
    re.compile(r"^UCSF-PDGM-metadata.*\.csv$"),
    re.compile(r"^BraTS-Africa_TCIA_datainfo.*\.xlsx$"),
    re.compile(r"^credentials.*\.json$"),
    re.compile(r"^\.env\..+$"),
)
ALLOWED_NAMES = (".env.example",)
# real B1 evidence location: must never hold SYNTHETIC_TEST_ONLY content
_B1_EVIDENCE_NAME = re.compile(r"^docs/data/B1_EVIDENCE_[^/]*\.md$")
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key block", re.compile("-----BEGIN [A-Z ]*" + "PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Kaggle API key", re.compile(r"\"key\"\s*:\s*\"[0-9a-f]{32}\"")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "generic API key assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]"
        ),
    ),
    (
        "Kaggle/TCIA credential assignment",
        re.compile(
            r"(?i)\b(kaggle_key|kaggle_username|tcia_(?:password|token|api_key)|synapse_(?:auth)?token)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"
        ),
    ),
    (
        "hard-coded personal path",
        re.compile(
            r"[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z]|/Users/[A-Za-z][^/\s]*/|/home/(?!researcher/)[a-z][^/\s]*/"
        ),
    ),
)
MAX_FILE_BYTES = 5 * 1024 * 1024
TEXT_SUFFIXES = (
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".txt",
    ".cfg",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".css",
    ".csv",
    ".sh",
    ".ini",
    ".cff",
    "Makefile",
    "Dockerfile",
)
FROZEN_PROTOCOL = "docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md"
_PROTOCOL_NAME = re.compile(r"(?i)FINAL_RESEARCH_PROTOCOL")


def sniff_imaging(path: Path) -> str | None:
    """Detect imaging/archive content by magic bytes, regardless of the file name."""
    try:
        with path.open("rb") as fh:
            head = fh.read(560)
    except OSError:
        return None
    if len(head) >= 132 and head[128:132] == b"DICM":
        return "DICOM content"
    if len(head) >= 348 and head[344:348] in (b"n+1\x00", b"ni1\x00"):
        return "NIfTI-1 content"
    if len(head) >= 8 and head[4:8] in (b"n+2\x00", b"ni2\x00"):
        return "NIfTI-2 content"
    if head[:2] == b"\x1f\x8b":
        return "gzip-compressed content (possible NIfTI/archive)"
    if head[:4] == b"PK\x03\x04":
        return "ZIP/XLSX container content"
    return None


@dataclass(frozen=True)
class Finding:
    path: str
    problem: str


def _is_text(path: str) -> bool:
    return path.endswith(TEXT_SUFFIXES)


def check_paths(files: list[str], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for rel in files:
        name = Path(rel).name
        low = rel.lower()
        if name in ALLOWED_NAMES:
            continue
        if low.endswith(PROHIBITED_SUFFIXES):
            findings.append(Finding(rel, "prohibited file type (imaging/array/checkpoint/key)"))
        if name in PROHIBITED_NAMES or any(p.match(name) for p in PROHIBITED_NAME_PATTERNS):
            findings.append(Finding(rel, "prohibited file (credentials or licensed metadata)"))
        if (
            _PROTOCOL_NAME.search(name)
            and rel != FROZEN_PROTOCOL
            and not rel.startswith("docs/research/archive/")
        ):
            findings.append(Finding(rel, "file could be mistaken for the active protocol"))
        p = root / rel
        if p.is_file():
            sniffed = sniff_imaging(p)
            if sniffed:
                findings.append(Finding(rel, f"prohibited binary: {sniffed}"))
            if p.stat().st_size > MAX_FILE_BYTES:
                findings.append(
                    Finding(rel, f"file larger than {MAX_FILE_BYTES // (1024 * 1024)} MiB")
                )
            if _is_text(rel):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for label, pat in SECRET_PATTERNS:
                    if pat.search(text):
                        findings.append(Finding(rel, f"possible secret: {label}"))
                if _B1_EVIDENCE_NAME.match(rel) and is_synthetic_b1_text(text):
                    findings.append(
                        Finding(rel, "synthetic authorization in a real B1 evidence location")
                    )
    return findings


def check_repository(root: str | Path) -> list[Finding]:
    root = Path(root)
    findings = check_paths(git_tracked_files(root), root)
    if not (root / FROZEN_PROTOCOL).is_file():
        findings.append(Finding(FROZEN_PROTOCOL, "frozen protocol missing"))
    else:
        try:
            load_protocol(root)
        except Exception as exc:  # report, do not crash the scan
            findings.append(Finding(FROZEN_PROTOCOL, f"protocol integrity: {exc}"))
    return findings
