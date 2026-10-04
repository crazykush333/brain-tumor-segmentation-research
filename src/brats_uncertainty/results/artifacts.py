"""Result artifacts: every stored number carries its provenance.

- ``write_artifact`` refuses artifacts without complete provenance.
- Synthetic (test-fixture) artifacts are refused inside the repository's public
  ``results/`` tree and can never be exported to the website.
- Artifacts are written atomically and never overwritten silently.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.utils.hashing import sha256_json
from brats_uncertainty.utils.io import read_json, write_json
from brats_uncertainty.utils.paths import is_within

_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
KINDS = (
    "metric_table",
    "bootstrap_result",
    "figure_data",
    "report",
    "manifest_summary",
    "split_summary",
)


@dataclass(frozen=True)
class ArtifactProvenance:
    experiment_id: str
    git_commit: str
    config_sha256: str
    protocol_sha256: str
    input_sha256: dict[str, str]
    generated_at: str
    synthetic: bool

    def validate(self) -> None:
        if not self.experiment_id:
            raise ProvenanceError("experiment_id is required")
        if not _COMMIT.match(self.git_commit):
            raise ProvenanceError("git_commit must be a full 40-character SHA")
        for name, h in {
            "config": self.config_sha256,
            "protocol": self.protocol_sha256,
            **self.input_sha256,
        }.items():
            if not _SHA.match(h):
                raise ProvenanceError(f"malformed SHA-256 for {name}")
        if not self.input_sha256:
            raise ProvenanceError("input_sha256 must list the hashed inputs")
        if not self.generated_at:
            raise ProvenanceError("generated_at is required")


@dataclass(frozen=True)
class ResultArtifact:
    kind: str
    name: str
    payload: dict[str, Any]
    provenance: ArtifactProvenance

    def to_dict(self) -> dict[str, Any]:
        if self.kind not in KINDS:
            raise ProvenanceError(f"unknown artifact kind {self.kind!r}")
        self.provenance.validate()
        body = {
            "kind": self.kind,
            "name": self.name,
            "payload": self.payload,
            "provenance": asdict(self.provenance),
        }
        body["content_sha256"] = sha256_json(
            {k: body[k] for k in ("kind", "name", "payload", "provenance")}
        )
        return body


def write_artifact(
    path: str | Path, artifact: ResultArtifact, *, repo_root: str | Path | None = None
) -> Path:
    body = artifact.to_dict()
    if (
        artifact.provenance.synthetic
        and repo_root is not None
        and is_within(path, Path(repo_root) / "results")
    ):
        raise ProvenanceError(
            "synthetic artifacts must never be written to the public results/ tree"
        )
    return write_json(path, body)


def read_artifact(path: str | Path) -> dict[str, Any]:
    body = read_json(path)
    expected = sha256_json({k: body[k] for k in ("kind", "name", "payload", "provenance")})
    if body.get("content_sha256") != expected:
        raise ProvenanceError(f"artifact content hash mismatch: {path}")
    prov = ArtifactProvenance(**body["provenance"])
    prov.validate()
    return body
