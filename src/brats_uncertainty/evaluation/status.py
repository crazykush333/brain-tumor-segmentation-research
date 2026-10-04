"""Load and validate ``docs/project_status.yaml`` (single source of project state).

The website, the README status line and the research-gate guards all read this
file. B gates follow the lifecycle state machine in
``brats_uncertainty.evaluation.lifecycle`` (LOCKED / PENDING / AUTHORIZED /
RUNNING / PASSED / FAILED / BLOCKED). A gate may only be recorded as closed
(CLOSED or PASSED) with an evidence path that exists in the repository and a
closure date. For B2-B6 the evidence must be a committed, NON-synthetic
execution record of that gate (for B6: status VERIFIED_FROM_SOURCE). The
``data``, ``training``, ``evaluation`` and ``results`` sections must be
consistent with the gates (e.g. data cannot be "acquired" before B2 passes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brats_uncertainty.data.evidence import (
    check_b1_evidence,
    check_evidence_committed,
    check_evidence_path,
    check_record_evidence,
    load_evidence_identity,
)
from brats_uncertainty.errors import ConfigError
from brats_uncertainty.evaluation.lifecycle import (
    LIFECYCLE_STATUSES,
    RECORD_EVIDENCE_GATES,
    allowed_statuses,
    check_invariants,
)
from brats_uncertainty.evaluation.lifecycle import is_closed as _is_closed
from brats_uncertainty.utils.git import GitView
from brats_uncertainty.utils.io import read_yaml
from brats_uncertainty.utils.paths import find_repo_root

STATUS_RELPATH = Path("docs/project_status.yaml")
GATE_STATUSES = tuple(
    dict.fromkeys(("CLOSED", "OWNER_WAIVED", "IN_PROGRESS", "NOT_STARTED", *LIFECYCLE_STATUSES))
)
AUTHORIZATION_STATUSES = ("PENDING", "APPROVED", "REFUSED")
STAGE_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "COMPLETED")
RESULTS_STATUSES = ("UNAVAILABLE", "AVAILABLE")
EXPERIMENT_STATUSES = ("PLANNED", "AUTHORIZED", "RUNNING", "COMPLETED", "FAILED", "INVALIDATED")
_GATE_ID = re.compile(r"^[A-D](\d{1,2})?$")


@dataclass(frozen=True)
class Gate:
    id: str
    group: str
    title: str
    status: str
    evidence: str | None
    closed_on: str | None

    @property
    def is_closed(self) -> bool:
        return _is_closed(self.status)


@dataclass(frozen=True)
class ProjectStatus:
    raw: dict[str, Any]
    gates: dict[str, Gate]
    repo_root: Path

    @property
    def headline(self) -> str:
        return str(self.raw["headline"])

    def gate(self, gate_id: str) -> Gate:
        if gate_id not in self.gates:
            raise ConfigError(f"unknown gate {gate_id!r}")
        return self.gates[gate_id]

    @property
    def results_available(self) -> bool:
        return bool(self.raw.get("results", {}).get("available", False))


def validate_status(raw: dict[str, Any], repo_root: Path) -> dict[str, Gate]:
    for key in (
        "schema_version",
        "headline",
        "protocol",
        "gates",
        "experiments",
        "results",
        "data",
        "training",
        "evaluation",
    ):
        if key not in raw:
            raise ConfigError(f"project_status.yaml missing key {key!r}")
    if not isinstance(raw["gates"], list):
        raise ConfigError("gates must be a list")
    for key in ("data", "training", "evaluation", "results", "experiments", "protocol"):
        if not isinstance(raw[key], dict):
            raise ConfigError(f"{key} must be a mapping")
    gates: dict[str, Gate] = {}
    evidence_paths: dict[str, Path] = {}
    for item in raw["gates"]:
        if not isinstance(item, dict) or "id" not in item or "status" not in item:
            raise ConfigError(f"malformed gate entry: {item!r}")
        gid = str(item["id"])
        if not _GATE_ID.match(gid):
            raise ConfigError(f"invalid gate id {gid!r}")
        if gid in gates:
            raise ConfigError(f"duplicate gate id {gid!r}")
        status = str(item["status"])
        if status not in GATE_STATUSES:
            raise ConfigError(f"gate {gid}: invalid status {status!r}")
        if status == "OWNER_WAIVED" and not gid.startswith("A"):
            raise ConfigError(f"gate {gid}: only gate-A items may be owner-waived")
        if status not in allowed_statuses(gid):
            raise ConfigError(
                f"gate {gid}: status {status!r} not allowed (allowed: {allowed_statuses(gid)})"
            )
        evidence = item.get("evidence")
        if status in ("CLOSED", "OWNER_WAIVED", "PASSED"):
            if not evidence or not item.get("closed_on"):
                raise ConfigError(f"gate {gid} is {status} without evidence and closed_on")
        elif item.get("closed_on"):
            raise ConfigError(f"gate {gid} has closed_on but is not closed")
        if status in ("FAILED", "BLOCKED") and gid.startswith("B") and not evidence:
            raise ConfigError(f"gate {gid} is {status} without an evidence document")
        if evidence:
            evidence_paths[gid] = check_evidence_path(gid, str(evidence), repo_root)
        gates[gid] = Gate(
            id=gid,
            group=gid[0],
            title=str(item.get("title", "")),
            status=status,
            evidence=str(evidence) if evidence else None,
            closed_on=str(item["closed_on"]) if item.get("closed_on") else None,
        )
    # lifecycle invariants: LOCKED iff prerequisites not PASSED; PASSED in protocol order
    check_invariants({g: gate.status for g, gate in gates.items() if g.startswith("B")})
    _validate_sections(raw, gates)
    # evidence content for passed B gates (B1 decision document; B2-B6 execution records)
    git = GitView(repo_root)
    check_evidence_committed({g: str(gates[g].evidence) for g in evidence_paths}, git)
    passed = {g: evidence_paths[g] for g, gate in gates.items() if gate.status == "PASSED"}
    if "B1" in passed:
        check_b1_evidence(
            str(gates["B1"].evidence),
            passed["B1"],
            raw["data"].get("approved_route"),
            identity=load_evidence_identity(repo_root),
            protocol_version=str(raw["protocol"].get("version", "")),
            owner=raw.get("project", {}).get("owner"),
        )
    protocol_sha = str(raw["protocol"].get("sha256", ""))
    if any(gid in passed for gid in RECORD_EVIDENCE_GATES):
        identity = load_evidence_identity(repo_root)
        for gid in RECORD_EVIDENCE_GATES:
            if gid in passed:
                check_record_evidence(
                    gid,
                    passed[gid],
                    git,
                    protocol_sha,
                    passed,
                    repo_root=repo_root,
                    identity=identity,
                )
    for exp_id, exp in raw["experiments"].items():
        if exp.get("status") not in EXPERIMENT_STATUSES:
            raise ConfigError(f"experiment {exp_id}: invalid status {exp.get('status')!r}")
    if raw["results"].get("available") and not raw["results"].get("evidence"):
        raise ConfigError("results.available is true without evidence")
    return gates


def _validate_sections(raw: dict[str, Any], gates: dict[str, Gate]) -> None:
    def closed(g: str) -> bool:
        return g in gates and gates[g].is_closed

    data = raw["data"]
    if data.get("authorization") not in AUTHORIZATION_STATUSES:
        raise ConfigError(f"data.authorization must be one of {AUTHORIZATION_STATUSES}")
    if (data["authorization"] == "APPROVED") != closed("B1"):
        raise ConfigError("data.authorization must be APPROVED exactly when gate B1 has PASSED")
    if data["authorization"] == "REFUSED" and gates["B1"].status not in ("FAILED", "BLOCKED"):
        raise ConfigError("data.authorization REFUSED requires gate B1 FAILED or BLOCKED")
    if data["authorization"] == "APPROVED" and not data.get("approved_route"):
        raise ConfigError("data.approved_route must name the route approved at B1")
    if data["authorization"] != "APPROVED" and data.get("approved_route"):
        raise ConfigError("data.approved_route is set but B1 authorization is not APPROVED")
    if bool(data.get("acquired")) != closed("B2"):
        raise ConfigError("data.acquired must be true exactly when gate B2 has PASSED")
    if raw["training"].get("status") not in STAGE_STATUSES:
        raise ConfigError(f"training.status must be one of {STAGE_STATUSES}")
    if raw["training"]["status"] != "NOT_STARTED" and not closed("B12"):
        raise ConfigError("training cannot have started before gate B12 is CLOSED")
    for k in ("internal", "external"):
        if raw["evaluation"].get(k) not in STAGE_STATUSES:
            raise ConfigError(f"evaluation.{k} must be one of {STAGE_STATUSES}")
    if raw["evaluation"]["internal"] != "NOT_STARTED" and not (closed("C5") and closed("C6")):
        raise ConfigError("internal evaluation cannot have started before C5 and C6 are CLOSED")
    if raw["evaluation"]["external"] != "NOT_STARTED" and not all(
        closed(f"C{i}") for i in range(1, 7)
    ):
        raise ConfigError("external evaluation cannot have started before C1-C6 are CLOSED")
    res = raw["results"]
    if res.get("status") not in RESULTS_STATUSES:
        raise ConfigError(f"results.status must be one of {RESULTS_STATUSES}")
    if (res["status"] == "AVAILABLE") != bool(res.get("available")):
        raise ConfigError("results.status and results.available disagree")


def load_status(repo_root: str | Path | None = None) -> ProjectStatus:
    root = Path(repo_root) if repo_root is not None else find_repo_root()
    path = root / STATUS_RELPATH
    if not path.is_file():
        raise ConfigError(f"missing {STATUS_RELPATH}")
    raw = read_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigError("project_status.yaml must be a mapping")
    return ProjectStatus(raw=raw, gates=validate_status(raw, root), repo_root=root)
