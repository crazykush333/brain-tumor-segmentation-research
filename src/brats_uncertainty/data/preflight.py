"""Disk-space preflight for gate B2 (download + local-import copy). Reads no data.

The selection size comes from the transfer client (for TCIA: the IBM Aspera
client shows the size of the selected folders) and is entered by the operator;
it is never assumed. The B3/B4 metadata files (crosswalk XLSX, UCSF-PDGM CSV) are
downloaded separately and counted with an explicit allowance (``metadata_bytes``).
The download needs selection + metadata on the delivery drive, and the
local-import copy needs the same again on the storage drive. Both are increased
by a safety margin, and a minimum of free space must remain afterwards. When
delivery and storage share a drive, the needs add up.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

GIB = 1 << 30
DEFAULT_MARGIN = 0.10  # +10 % of the selection
DEFAULT_RESERVE_BYTES = 10 * GIB  # free space that must remain on each drive
# B3/B4 files downloaded separately over HTTPS (crosswalk XLSX 78.12 KB on the official page;
# UCSF-PDGM CSV): a generous allowance, overridable when their sizes are known
DEFAULT_METADATA_BYTES = 16 << 20


def _existing_ancestor(path: Path) -> Path:
    p = Path(path).absolute()
    while not p.exists():
        if p.parent == p:
            break
        p = p.parent
    return p


def _drive_key(path: Path) -> str:
    anchor = _existing_ancestor(path)
    return (anchor.drive or anchor.anchor or str(anchor)).upper()


@dataclass(frozen=True)
class DriveNeed:
    drive: str
    free_bytes: int
    needed_bytes: int
    purposes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.free_bytes >= self.needed_bytes


@dataclass(frozen=True)
class StoragePreflight:
    selected_bytes: int
    metadata_bytes: int
    margin: float
    reserve_bytes: int
    drives: tuple[DriveNeed, ...]

    @property
    def ok(self) -> bool:
        return all(d.ok for d in self.drives)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}

    def describe(self) -> str:
        lines = [
            f"selection: {self.selected_bytes / GIB:.2f} GiB + B3/B4 metadata allowance "
            f"{self.metadata_bytes / (1 << 20):.0f} MiB "
            f"(+{self.margin:.0%} margin, {self.reserve_bytes / GIB:.0f} GiB reserve per drive)"
        ]
        for d in self.drives:
            state = "OK" if d.ok else "INSUFFICIENT"
            lines.append(
                f"  {d.drive} {state}: free {d.free_bytes / GIB:.1f} GiB, "
                f"needed {d.needed_bytes / GIB:.1f} GiB ({', '.join(d.purposes)})"
            )
        lines.append("PREFLIGHT OK" if self.ok else "PREFLIGHT FAILED: do not start the transfer")
        return "\n".join(lines)


def storage_preflight(
    selected_bytes: int,
    *,
    delivery_dir: Path,
    storage_dir: Path | None,
    margin: float = DEFAULT_MARGIN,
    reserve_bytes: int = DEFAULT_RESERVE_BYTES,
    metadata_bytes: int = DEFAULT_METADATA_BYTES,
    free_bytes: dict[str, int] | None = None,
) -> StoragePreflight:
    """Is there room for the download (delivery) and the import copy (storage)?

    Each copy needs the client-reported selection (training set + ``.sums``) plus the
    separately downloaded B3/B4 metadata files (``metadata_bytes``), plus the margin.
    ``free_bytes`` overrides the measured free space per drive key (tests only).
    """
    if selected_bytes <= 0:
        raise ValueError("selected_bytes must be the positive size shown by the transfer client")
    if not 0 <= margin <= 1:
        raise ValueError("margin must be between 0 and 1")
    if metadata_bytes < 0:
        raise ValueError("metadata_bytes must not be negative")
    per_copy = int((selected_bytes + metadata_bytes) * (1 + margin))
    needs: dict[str, list[str]] = {}
    dirs: dict[str, Path] = {}
    for purpose, d in (("download", delivery_dir), ("import copy", storage_dir)):
        if d is None:
            continue
        key = _drive_key(d)
        needs.setdefault(key, []).append(purpose)
        dirs.setdefault(key, d)
    drives = []
    for key, purposes in sorted(needs.items()):
        free = (
            free_bytes[key]
            if free_bytes is not None
            else shutil.disk_usage(_existing_ancestor(dirs[key])).free
        )
        drives.append(
            DriveNeed(key, free, per_copy * len(purposes) + reserve_bytes, tuple(purposes))
        )
    return StoragePreflight(selected_bytes, metadata_bytes, margin, reserve_bytes, tuple(drives))


def require_free_space(target: Path, needed_bytes: int, *, reserve_bytes: int = 0) -> None:
    """Fail closed before copying if ``target``'s drive lacks ``needed_bytes`` (+ reserve)."""
    from brats_uncertainty.errors import DataValidationError

    free = shutil.disk_usage(_existing_ancestor(target)).free
    need = needed_bytes + reserve_bytes
    if free < need:
        raise DataValidationError(
            f"insufficient disk space for the import copy: need {need / GIB:.1f} GiB, "
            f"free {free / GIB:.1f} GiB"
        )
