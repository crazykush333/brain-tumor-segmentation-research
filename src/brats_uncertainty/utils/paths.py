"""Repository-root discovery. No absolute paths are hard-coded anywhere."""

from __future__ import annotations

import os
from pathlib import Path

ENV_ROOT = "BRATS_UNCERTAINTY_ROOT"
_MARKERS = ("pyproject.toml", "configs/protocol")


def find_repo_root(start: str | Path | None = None) -> Path:
    """Locate the repository root.

    Order: the ``BRATS_UNCERTAINTY_ROOT`` environment variable, then the first
    ancestor of ``start`` (default: current directory) containing both
    ``pyproject.toml`` and ``configs/protocol``.
    """
    env = os.environ.get(ENV_ROOT)
    if env:
        root = Path(env).expanduser().resolve()
        if not all((root / m).exists() for m in _MARKERS):
            raise FileNotFoundError(f"{ENV_ROOT}={root} is not a brats-uncertainty repository root")
        return root
    here = Path(start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if all((candidate / m).exists() for m in _MARKERS):
            return candidate
    raise FileNotFoundError(
        "repository root not found; run inside the repository or set " + ENV_ROOT
    )


def is_within(path: str | Path, parent: str | Path) -> bool:
    """True if ``path`` resolves to a location inside ``parent``."""
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def is_safe_relpath(rel: str) -> bool:
    """Platform-independent check for a safe POSIX-style relative path.

    Rejects: empty paths, absolute paths on ANY platform (leading ``/`` or
    ``\\``, drive letters, UNC), backslashes, ``:`` and ``..`` components.
    (``pathlib`` alone is platform-dependent: ``/x`` is not absolute on Windows.)
    """
    if not rel or rel.startswith(("/", "\\")) or "\\" in rel or ":" in rel:
        return False
    parts = rel.split("/")
    return all(p not in ("", ".", "..") for p in parts)


def is_link(path: str | Path) -> bool:
    """True for symbolic links (including broken ones) AND Windows directory junctions.

    ``Path.is_symlink`` does not report junctions, which can also point outside a
    permitted root; every link check in the data layer uses this function.
    """
    p = Path(path)
    if p.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python >= 3.12
    if isjunction is not None:
        return bool(isjunction(p))
    try:  # Python 3.11 fallback: reparse-point attribute (Windows only)
        attrs = getattr(os.lstat(p), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
