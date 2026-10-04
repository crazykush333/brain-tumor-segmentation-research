"""Load and verify the machine-readable mirror of the frozen protocol v1.0.

The protocol text (``docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md``) is the
scientific source of truth. ``configs/protocol/protocol_v1.0.yaml`` mirrors its
design parameters for code. Loading always verifies the protocol file's SHA-256
so that code can never run against an edited protocol without failing loudly.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from brats_uncertainty import PROTOCOL_VERSION
from brats_uncertainty.errors import ProtocolIntegrityError
from brats_uncertainty.utils.hashing import sha256_text_lf
from brats_uncertainty.utils.io import read_yaml
from brats_uncertainty.utils.paths import find_repo_root

PROTOCOL_CONFIG_RELPATH = Path("configs/protocol/protocol_v1.0.yaml")


@dataclass(frozen=True)
class ProtocolSpec:
    """Typed view of the protocol parameters used by the code."""

    raw: dict[str, Any]
    repo_root: Path

    @property
    def version(self) -> str:
        return str(self.raw["protocol"]["version"])

    @property
    def channel_order(self) -> tuple[str, ...]:
        return tuple(self.raw["modalities"]["channel_order"])

    @property
    def c5(self) -> tuple[str, ...]:
        return tuple(self.raw["conditions"]["C5"])

    @property
    def c4(self) -> tuple[str, ...]:
        return tuple(self.raw["conditions"]["C4"])

    @property
    def training_seeds(self) -> tuple[int, ...]:
        return tuple(int(s) for s in self.raw["model"]["seeds"])

    @property
    def split_seed(self) -> int:
        return int(self.raw["split"]["seed"])

    @property
    def split_proportions(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.raw["split"]["proportions"].items()}

    @property
    def bootstrap_replicates(self) -> int:
        return int(self.raw["statistics"]["bootstrap_replicates"])

    @property
    def bootstrap_seed(self) -> int:
        return int(self.raw["statistics"]["bootstrap_seed"])

    @property
    def alpha(self) -> float:
        return float(self.raw["statistics"]["alpha"])

    @property
    def q_primary(self) -> float:
        return float(self.raw["threshold_transfer"]["q_primary"])

    @property
    def q_sensitivity(self) -> tuple[float, ...]:
        return tuple(float(q) for q in self.raw["threshold_transfer"]["q_sensitivity"])

    @property
    def failure_analysis_q(self) -> float:
        return float(self.raw["threshold_transfer"]["failure_analysis_q"])

    @property
    def verified_groups(self) -> dict[str, tuple[str, ...]]:
        return {k: tuple(v) for k, v in self.raw["grouping"]["verified_groups"].items()}

    @property
    def reviewers(self) -> tuple[str, str]:
        g = self.raw["grouping"]
        return str(g["primary_reviewer"]), str(g["second_reviewer"])

    @property
    def dropout_p_full(self) -> float:
        return float(self.raw["modality_dropout"]["p_full"])

    @property
    def inference(self) -> dict[str, Any]:
        return dict(self.raw["model"]["inference"])

    @property
    def roi_dilation_voxels(self) -> int:
        return int(self.raw["uncertainty"]["roi_dilation_voxels"])

    @property
    def ece_bins(self) -> int:
        return int(self.raw["metrics"]["ece"]["bins"])


def verify_protocol_file(repo_root: Path, raw: dict[str, Any]) -> str:
    """Check the frozen protocol exists and its LF-normalized SHA-256 matches the record."""
    rel = raw["protocol"]["file"]
    expected = raw["protocol"]["sha256"]
    path = repo_root / rel
    if not path.is_file():
        raise ProtocolIntegrityError(f"frozen protocol file missing: {path}")
    actual = sha256_text_lf(path)
    if actual != expected:
        raise ProtocolIntegrityError(
            f"frozen protocol SHA-256 mismatch for {rel}: expected {expected}, found {actual}. "
            "The frozen protocol must not be edited; changes require a logged amendment."
        )
    return actual


@lru_cache(maxsize=4)
def _load_cached(root_str: str) -> ProtocolSpec:
    root = Path(root_str)
    cfg = root / PROTOCOL_CONFIG_RELPATH
    if not cfg.is_file():
        raise ProtocolIntegrityError(f"protocol parameter file missing: {cfg}")
    raw = read_yaml(cfg)
    if not isinstance(raw, dict):
        raise ProtocolIntegrityError("protocol parameter file is not a mapping")
    if raw.get("protocol", {}).get("version") != PROTOCOL_VERSION:
        raise ProtocolIntegrityError(
            f"protocol parameter file version {raw.get('protocol', {}).get('version')!r} "
            f"does not match package protocol version {PROTOCOL_VERSION!r}"
        )
    if raw["protocol"].get("status") != "frozen":
        raise ProtocolIntegrityError("protocol parameter file does not declare status 'frozen'")
    verify_protocol_file(root, raw)
    return ProtocolSpec(raw=raw, repo_root=root)


def load_protocol(repo_root: str | Path | None = None) -> ProtocolSpec:
    """Load protocol parameters and verify the frozen protocol file hash."""
    root = Path(repo_root) if repo_root is not None else find_repo_root()
    return _load_cached(str(root.resolve()))
