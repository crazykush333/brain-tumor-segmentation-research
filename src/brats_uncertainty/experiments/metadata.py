"""Experiment metadata (protocol §24) with an enforced status lifecycle.

Statuses: PLANNED -> AUTHORIZED -> RUNNING -> COMPLETED | FAILED; COMPLETED or
FAILED (or an earlier state) -> INVALIDATED. AUTHORIZED requires an owner
authorization record; COMPLETED requires full provenance and output hashes.
Nothing may be marked COMPLETED without the evidence of having run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from brats_uncertainty.errors import ConfigError, ProvenanceError, ResearchGateError
from brats_uncertainty.utils.io import read_yaml

STATUSES = ("PLANNED", "AUTHORIZED", "RUNNING", "COMPLETED", "FAILED", "INVALIDATED")
TRANSITIONS: dict[str, frozenset[str]] = {
    "PLANNED": frozenset({"AUTHORIZED", "INVALIDATED"}),
    "AUTHORIZED": frozenset({"RUNNING", "INVALIDATED"}),
    "RUNNING": frozenset({"COMPLETED", "FAILED"}),
    "COMPLETED": frozenset({"INVALIDATED"}),
    "FAILED": frozenset({"INVALIDATED"}),
    "INVALIDATED": frozenset(),
}
EXP_ID = re.compile(r"^EXP-\d{3}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_PROVENANCE = (
    "git_commit",
    "config_sha256",
    "protocol_sha256",
    "environment",
    "started_at",
    "finished_at",
)


@dataclass
class ExperimentMetadata:
    experiment_id: str
    title: str
    status: str
    protocol_version: str
    protocol_sections: list[str]
    required_gates: list[str]
    authorization: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    outputs: dict[str, str] = field(default_factory=dict)  # relpath -> sha256
    history: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def validate(self) -> None:
        if not EXP_ID.match(self.experiment_id):
            raise ConfigError(f"invalid experiment id {self.experiment_id!r}")
        if self.status not in STATUSES:
            raise ConfigError(f"invalid status {self.status!r}")
        if self.protocol_version != "v1.0":
            raise ConfigError("experiments must reference protocol v1.0")
        if self.status in ("AUTHORIZED", "RUNNING", "COMPLETED", "FAILED"):
            auth = self.authorization or {}
            if not all(auth.get(k) for k in ("authorized_by", "authorized_on", "reference")):
                raise ResearchGateError(
                    f"{self.experiment_id}: status {self.status} requires authorization"
                )
        if self.status == "COMPLETED":
            prov = self.provenance or {}
            missing = [k for k in REQUIRED_PROVENANCE if not prov.get(k)]
            if missing:
                raise ProvenanceError(
                    f"{self.experiment_id}: COMPLETED without provenance {missing}"
                )
            if not _COMMIT.match(str(prov["git_commit"])):
                raise ProvenanceError("git_commit must be a full 40-character SHA")
            if not self.outputs:
                raise ProvenanceError(f"{self.experiment_id}: COMPLETED without output hashes")
            bad = [p for p, h in self.outputs.items() if not _SHA.match(h)]
            if bad:
                raise ProvenanceError(f"malformed output hashes: {bad}")

    def transition(self, new_status: str, *, on: str, by: str, reason: str) -> None:
        if new_status not in TRANSITIONS.get(self.status, frozenset()):
            raise ResearchGateError(
                f"{self.experiment_id}: illegal transition {self.status} -> {new_status}"
            )
        old = self.status
        self.status = new_status
        try:
            self.validate()
        except Exception:
            self.status = old
            raise
        self.history.append({"from": old, "to": new_status, "on": on, "by": by, "reason": reason})

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "experiment_id": self.experiment_id,
            "title": self.title,
            "status": self.status,
            "protocol_version": self.protocol_version,
            "protocol_sections": self.protocol_sections,
            "required_gates": self.required_gates,
            "authorization": self.authorization,
            "provenance": self.provenance,
            "outputs": self.outputs,
            "history": self.history,
            "notes": self.notes,
        }


def load_experiment(path: str | Path) -> ExperimentMetadata:
    raw = read_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: not a mapping")
    try:
        meta = ExperimentMetadata(**raw)
    except TypeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    meta.validate()
    return meta


def save_experiment(path: str | Path, meta: ExperimentMetadata) -> None:
    Path(path).write_text(
        yaml.safe_dump(meta.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
