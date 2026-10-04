"""The master runner: one pass over every step, in dependency order, every session.

Per step:

1. LOCKED while any dependency has not PASSED;
2. FAILED steps stay FAILED (never silently re-run) unless the owner passes
   ``--retry <STEP>``;
3. a step whose project gate is already closed is PASSED (authoritative record);
4. otherwise the compute requirements of its job are checked (NOT_READY -> BLOCKED),
   it is journaled as RUNNING and executed; its outcome is journaled.

Independent steps continue after a stop; dependants stay LOCKED. At the end of the
session the run summary and website data are regenerated and committed (with
``--commit``) and pushed (with ``--push``). The report lists each stop with its
exact gate, blocker and action.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from brats_uncertainty.evaluation.lifecycle import CLOSED_STATUSES
from brats_uncertainty.orchestration.state import (
    FAILED,
    LOCKED,
    PASSED,
    READY,
    RUNNING,
    STOP_STATUSES,
    MasterState,
    Outcome,
    load_state,
    save_state,
    utc_now,
)
from brats_uncertainty.orchestration.steps import Context, Step, compute_ready, run_guarded


@dataclass
class RunReport:
    statuses: dict[str, str]
    stops: list[dict[str, Any]] = field(default_factory=list)
    passed_now: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    state_path: Path | None = None
    planned: bool = False

    def describe(self) -> str:
        if self.planned:
            lines = ["master-run plan (nothing executed):"]
            lines += [f"  {sid:<16} {st}" for sid, st in self.statuses.items()]
            return "\n".join(lines)
        lines = ["master-run step status:"]
        lines += [f"  {sid:<16} {st}" for sid, st in self.statuses.items()]
        if self.passed_now:
            lines.append(f"passed this session: {', '.join(self.passed_now)}")
        if self.commits:
            lines.append(f"commits this session: {', '.join(c[:7] for c in self.commits)}")
        for s in self.stops:
            lines += [
                f"STOP {s['status']} at {s['step']} (gate {s['gate'] or '-'}):",
                f"  blocker: {s['blocker']}",
                f"  action:  {s['action']}",
            ]
        if not self.stops:
            lines.append("no stop: every reachable step has PASSED")
        return "\n".join(lines)


def validate_order(steps: Sequence[Step]) -> None:
    seen: set[str] = set()
    for s in steps:
        missing = [d for d in s.needs if d not in seen]
        if missing or s.id in seen:
            raise ValueError(
                f"step {s.id}: dependencies {missing} must precede it (or duplicate id)"
            )
        seen.add(s.id)


def plan(ctx: Context, steps: Sequence[Step], state: MasterState) -> dict[str, str]:
    """Statuses without executing anything (read-only)."""
    out: dict[str, str] = {}
    for s in steps:
        rec = state.steps.get(s.id)
        if s.gate and ctx.ops.gate_status(s.gate) in CLOSED_STATUSES:
            out[s.id] = PASSED
        elif rec is not None and rec.status == FAILED:
            out[s.id] = FAILED
        elif any(out.get(d) != PASSED for d in s.needs):
            out[s.id] = LOCKED
        elif rec is not None and rec.status == PASSED and not s.gate and s.id != "ENV":
            out[s.id] = PASSED
        else:
            out[s.id] = READY
    return out


def _record(state: MasterState, step: Step, outcome: Outcome) -> None:
    rec = state.step(step.id)
    rec.status, rec.summary = outcome.status, outcome.summary
    rec.action_needed, rec.evidence = outcome.action_needed, list(outcome.evidence)
    rec.details = outcome.details
    rec.last_finished = utc_now()
    state.event("step_outcome", step.id, status=outcome.status, summary=outcome.summary)


def run(
    ctx: Context,
    steps: Sequence[Step],
    *,
    retry: Sequence[str] = (),
    until: str | None = None,
    session_info: dict[str, Any] | None = None,
) -> RunReport:
    validate_order(steps)
    state = load_state(ctx.state_dir)
    state.start_session(session_info or {})
    for sid in retry:
        if sid in state.steps and state.steps[sid].status == FAILED:
            state.event("owner_retry", sid)
            state.steps[sid].status = READY
    save_state(ctx.state_dir, state)
    report = RunReport(statuses={})
    for s in steps:
        rec = state.step(s.id)
        if any(report.statuses.get(d) != PASSED for d in s.needs):
            report.statuses[s.id] = LOCKED
            if rec.status not in (FAILED,):
                rec.status = LOCKED
            continue
        if rec.status == FAILED:
            report.statuses[s.id] = FAILED
            report.stops.append(_stop(s, rec.summary, rec.action_needed or "owner review", FAILED))
            continue
        if s.gate and ctx.ops.gate_status(s.gate) in CLOSED_STATUSES:
            if rec.status != PASSED:
                rec.status, rec.summary = PASSED, f"gate {s.gate} closed (project status)"
            report.statuses[s.id] = PASSED
            continue
        not_ready = compute_ready(ctx, s)
        if not_ready is not None:
            _record(state, s, not_ready)
            report.statuses[s.id] = not_ready.status
            report.stops.append(
                _stop(s, not_ready.summary, not_ready.action_needed, not_ready.status)
            )
            save_state(ctx.state_dir, state)
            continue
        rec.status, rec.attempts, rec.last_started = RUNNING, rec.attempts + 1, utc_now()
        state.event("step_start", s.id, attempt=rec.attempts)
        save_state(ctx.state_dir, state)  # a crash from here leaves RUNNING -> resumed next time
        outcome = run_guarded(ctx, s)
        was_passed = rec.status == PASSED
        _record(state, s, outcome)
        save_state(ctx.state_dir, state)
        report.statuses[s.id] = outcome.status
        if outcome.status == PASSED and not was_passed and s.id != "ENV":
            report.passed_now.append(s.id)
        if outcome.status in STOP_STATUSES:
            report.stops.append(_stop(s, outcome.summary, outcome.action_needed, outcome.status))
        if until is not None and s.id == until:
            break
    for s in steps:  # steps after --until
        report.statuses.setdefault(s.id, state.step(s.id).status)
    state.end_session(report.stops)
    report.state_path = save_state(ctx.state_dir, state)
    return report


def _stop(step: Step, blocker: str, action: str | None, status: str) -> dict[str, Any]:
    return {
        "step": step.id,
        "gate": step.gate,
        "status": status,
        "blocker": blocker,
        "action": action or "owner review",
    }
