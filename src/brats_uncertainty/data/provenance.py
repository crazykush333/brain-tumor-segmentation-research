"""Dataset provenance records (gates B1-B5, C1-C3).

A provenance record states where data came from, under which terms and via
which approved route, with hashes of the files actually used. Every field is
required; validation fails loudly on anything missing so that no artifact can
claim a provenance it does not have.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from brats_uncertainty.errors import ProvenanceError

_HEX = set("0123456789abcdef")


@dataclass(frozen=True)
class DatasetProvenance:
    dataset: str
    source: str  # e.g. Synapse syn25829067 / TCIA collection page
    licence: str
    data_route: str  # the B1-approved route
    data_route_approval_ref: str  # evidence reference for the B1 decision
    acquired_on: str  # ISO date
    acquired_by: str
    manifest_sha256: str
    metadata_file_hashes: dict[str, str] = field(default_factory=dict)
    citations: tuple[str, ...] = ()

    def validate(self) -> None:
        for k, v in asdict(self).items():
            if v in (None, "", ()) and k not in ("metadata_file_hashes",):
                raise ProvenanceError(f"provenance field {k!r} is empty")
        for name, h in {"manifest": self.manifest_sha256, **self.metadata_file_hashes}.items():
            if len(h) != 64 or not set(h) <= _HEX:
                raise ProvenanceError(f"malformed SHA-256 for {name}")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
