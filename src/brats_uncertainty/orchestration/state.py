"""Persistent master-run state (outside notebook memory; survives crashed sessions).

The authoritative records stay where they are: gate states in
docs/project_status.yaml (committed), training runs in their own
``run_manifest.json``. This file is the runner's journal: the derived status
of every step, attempts, stops and resumes. On every start the runner re-derives
step statuses from the authoritative records, so losing this file loses history
only, never verified work.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_FILENAME = "master_state.json"
SCHEMA_VERSION = 1

LOCKED = "LOCKED"
READY = "READY"
RUNNING = "RUNNING"
PASSED = "PASSED"
FAILED = "FAILED"
BLOCKED = "BLOCKED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
STEP_STATUSES = (LOCKED, READY, RUNNING, PASSED, FAILED, BLOCKED, REVIEW_REQUIRED)
STOP_STATUSES = frozenset({FAILED, BLOCKED, REVIEW_REQUIRED})


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class Outcome:
    """Result of executing (or reconciling) one step."""

    status: str
    summary: str
    action_needed: str | None = None
    evidence: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in STEP_STATUSES:
            raise ValueError(f"invalid step status {self.status!r}")
        if self.status in STOP_STATUSES and not self.action_needed:
            raise ValueError(f"a {self.status} outcome must name the exact action needed")


@dataclass
class StepRecord:
    status: str = LOCKED
    summary: str = ""
    action_needed: str | None = None
    evidence: list[str] = field(default_factory=list)
    attempts: int = 0
    last_started: str | None = None
    last_finished: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MasterState:
    created_at: str
    updated_at: str
    steps: dict[str, StepRecord] = field(default_factory=dict)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(cls) -> MasterState:
        now = utc_now()
        return cls(created_at=now, updated_at=now)

    def step(self, sid: str) -> StepRecord:
        return self.steps.setdefault(sid, StepRecord())

    def event(self, kind: str, step: str | None = None, **info: Any) -> None:
        self.events.append({"at": utc_now(), "kind": kind, "step": step, **info})

    def start_session(self, info: dict[str, Any]) -> str:
        sid = uuid.uuid4().hex[:12]
        resumed = bool(self.sessions)
        self.sessions.append({"id": sid, "started_at": utc_now(), "resumed": resumed, **info})
        self.event("session_start", session=sid, resumed=resumed)
        return sid

    def end_session(self, stops: list[dict[str, Any]]) -> None:
        if self.sessions:
            self.sessions[-1].update(ended_at=utc_now(), stops=stops)
        self.event("session_end", stops=[s["step"] for s in stops])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": {k: asdict(v) for k, v in self.steps.items()},
            "sessions": self.sessions,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MasterState:
        if d.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported master state schema {d.get('schema_version')!r}")
        return cls(
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            steps={k: StepRecord(**v) for k, v in d.get("steps", {}).items()},
            sessions=list(d.get("sessions", [])),
            events=list(d.get("events", [])),
        )


def load_state(state_dir: Path) -> MasterState:
    path = state_dir / STATE_FILENAME
    if not path.is_file():
        return MasterState.new()
    return MasterState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(state_dir: Path, state: MasterState) -> Path:
    """Atomic write: the previous file stays intact until the new one is complete."""
    state_dir.mkdir(parents=True, exist_ok=True)
    state.updated_at = utc_now()
    path = state_dir / STATE_FILENAME
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path
