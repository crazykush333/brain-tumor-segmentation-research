"""SHA-256 helpers. Hashes are only ever computed from real bytes, never stated."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return the hex SHA-256 of a file, streamed in 1 MiB chunks.

    Raises FileNotFoundError if the file does not exist, so a hash can never be
    produced for a file that was not actually read.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"cannot hash missing file: {p}")
    digest = hashlib.sha256()
    with p.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text_lf(path: str | Path) -> str:
    """SHA-256 of a text file after normalizing CRLF to LF.

    Git may check text files out with CRLF on Windows (``core.autocrlf``). The
    LF-normalized bytes equal the committed git blob, so this hash is identical
    on every platform and matches ``git show <tag>:<file> | sha256sum``.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"cannot hash missing file: {p}")
    return sha256_bytes(p.read_bytes().replace(b"\r\n", b"\n"))


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_json(obj: Any) -> str:
    """SHA-256 of the canonical JSON encoding of ``obj``."""
    return sha256_bytes(canonical_json(obj).encode("utf-8"))
