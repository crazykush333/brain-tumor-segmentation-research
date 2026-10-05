"""Provider checksum files (e.g. ``RSNA-ASNR-MICCAI-BraTS-2021.sums``) for gate B2.

The official TCIA package ships a checksum list next to the data. It is used
exactly as delivered: the file is never rewritten, its own SHA-256 is computed
over its raw bytes, and line endings are only tolerated while *parsing* (a
trailing CR is ignored per line; the bytes on disk are untouched).

Supported line formats (detected per line; the digest length or the BSD tag
gives the algorithm):

- GNU coreutils: ``<hexdigest>  <path>`` or ``<hexdigest> *<path>``;
- single-space:  ``<hexdigest> <path>``, the format of the official TCIA
  ``RSNA-ASNR-MICCAI-BraTS-2021.sums`` (MD5, one space; observed 2026-10-06, see
  docs/data/B2_ASPERA_RECEIVE_EVIDENCE_2026-10-06.md);
- BSD tagged:    ``<ALGO> (<path>) = <hexdigest>``.

Anything else (including GNU escaped lines starting with ``\\``) fails closed with
the line number, so an unknown provider format is never guessed: extend the
parser and its tests instead. Listed paths must be safe relative POSIX paths
(no absolute paths, drive letters, ``..`` or backslashes); a leading ``./`` is
accepted.

``verify_checksums`` checks the files listed under a selected prefix (e.g.
``RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet``) against a local root,
streams each file through the listed algorithm, and reports mismatches,
missing files, unlisted files under the prefix, links and the number of
listed entries outside the selection (not downloaded on purpose).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.utils.hashing import sha256_file
from brats_uncertainty.utils.paths import is_link, is_safe_relpath

_CHUNK = 1 << 20
_BY_LENGTH = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
_BSD_TAGS = {"MD5": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
# GNU (two spaces or " *") and the single-space TCIA form; the path never starts with a space
_GNU = re.compile(r"^([0-9A-Fa-f]+) [ *]?([^ ].*)$")
_BSD = re.compile(r"^(MD5|SHA1|SHA256|SHA512) \((.+)\) = ([0-9A-Fa-f]+)$")


@dataclass(frozen=True)
class ChecksumEntry:
    algorithm: str
    digest: str  # lower-case hex
    path: str  # POSIX path as listed (leading "./" removed)


@dataclass(frozen=True)
class ChecksumFile:
    file_name: str
    sha256: str  # of the raw bytes, as delivered
    size_bytes: int
    line_endings: str  # "LF" | "CRLF" | "mixed" | "none"
    entries: tuple[ChecksumEntry, ...]

    @property
    def algorithms(self) -> tuple[str, ...]:
        return tuple(sorted({e.algorithm for e in self.entries}))


def _clean_path(raw: str, lineno: int) -> str:
    path = raw[2:] if raw.startswith("./") else raw
    if "\\" in path or not path or not is_safe_relpath(path) or Path(path).is_absolute():
        raise DataValidationError(f"checksum line {lineno}: unsafe or unsupported path {raw!r}")
    if ":" in path.split("/")[0]:
        raise DataValidationError(f"checksum line {lineno}: drive-letter path {raw!r}")
    return path


def parse_checksum_file(path: str | Path) -> ChecksumFile:
    """Parse a provider checksum file without modifying it (fails closed on unknown lines)."""
    p = Path(path)
    if is_link(p) or not p.is_file():
        raise DataValidationError(f"checksum file not found or a link: {p.name}")
    data = p.read_bytes()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    crlf = sum(1 for ln in lines if ln.endswith(b"\r"))
    endings = (
        "none" if not lines else "CRLF" if crlf == len(lines) else "LF" if crlf == 0 else "mixed"
    )
    entries: list[ChecksumEntry] = []
    seen: set[str] = set()
    for lineno, raw_line in enumerate(lines, start=1):
        try:
            line = raw_line.removesuffix(b"\r").decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DataValidationError(f"checksum line {lineno}: not UTF-8") from exc
        if not line.strip():
            continue
        if m := _BSD.match(line):
            algo, rel, digest = _BSD_TAGS[m.group(1)], m.group(2), m.group(3)
            if _BY_LENGTH.get(len(digest)) != algo:
                raise DataValidationError(f"checksum line {lineno}: digest length != {algo}")
        elif (m := _GNU.match(line)) and len(m.group(1)) in _BY_LENGTH:
            digest, rel = m.group(1), m.group(2)
            algo = _BY_LENGTH[len(digest)]
        else:
            raise DataValidationError(
                f"checksum line {lineno}: unrecognized format (supported: GNU '<digest>  <path>', "
                "single-space '<digest> <path>', BSD 'ALGO (path) = digest'); extend the parser "
                "rather than guessing"
            )
        rel = _clean_path(rel, lineno)
        if rel in seen:
            raise DataValidationError(f"checksum line {lineno}: duplicate entry for {rel}")
        seen.add(rel)
        entries.append(ChecksumEntry(algo, digest.lower(), rel))
    if not entries:
        raise DataValidationError(f"{p.name}: no checksum entries")
    return ChecksumFile(p.name, sha256_file(p), p.stat().st_size, endings, tuple(entries))


def _digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ChecksumReport:
    checksum_file: str
    checksum_file_sha256: str
    selected_prefix: str
    algorithms: tuple[str, ...]
    n_listed: int = 0
    n_selected: int = 0
    n_verified: int = 0
    n_not_selected: int = 0
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    unlisted: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.n_selected > 0
            and self.n_verified == self.n_selected
            and not (self.missing or self.mismatched or self.unlisted or self.links)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "checksum_file": self.checksum_file,
            "checksum_file_sha256": self.checksum_file_sha256,
            "selected_prefix": self.selected_prefix,
            "algorithms": list(self.algorithms),
            "n_listed": self.n_listed,
            "n_selected": self.n_selected,
            "n_verified": self.n_verified,
            "n_not_selected": self.n_not_selected,
            "missing": self.missing,
            "mismatched": self.mismatched,
            "unlisted": self.unlisted,
            "links": self.links,
            "ok": self.ok,
        }


def verify_checksums(sums: ChecksumFile, root: str | Path, *, prefix: str) -> ChecksumReport:
    """Verify every listed file under ``prefix`` (relative to ``root``); nothing is modified."""
    prefix = prefix.strip("/")
    if not is_safe_relpath(prefix):
        raise DataValidationError("selected prefix must be a safe relative path")
    base = Path(root)
    report = ChecksumReport(sums.file_name, sums.sha256, prefix, sums.algorithms)
    report.n_listed = len(sums.entries)
    listed: set[str] = set()
    for e in sums.entries:
        if not e.path.startswith(prefix + "/"):
            report.n_not_selected += 1
            continue
        report.n_selected += 1
        listed.add(e.path)
        f = base / e.path
        if is_link(f):
            report.links.append(e.path)
        elif not f.is_file():
            report.missing.append(e.path)
        elif _digest(f, e.algorithm) != e.digest:
            report.mismatched.append(e.path)
        else:
            report.n_verified += 1
    selected_dir = base / prefix
    if selected_dir.is_dir():
        for p in sorted(selected_dir.rglob("*")):
            rel = p.relative_to(base).as_posix()
            if is_link(p):
                if rel not in report.links:
                    report.links.append(rel)
            elif p.is_file() and rel not in listed:
                report.unlisted.append(rel)
    if report.n_selected == 0:
        raise DataValidationError(
            f"no checksum entries under {prefix!r}: check the selected prefix and the root"
        )
    return report
