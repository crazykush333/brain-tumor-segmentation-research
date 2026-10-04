"""Gate lifecycle state machine for the data/split gates B1-B12.

Statuses (B gates):

- ``LOCKED``      a prerequisite gate has not PASSED; the gate cannot run.
- ``PENDING``     awaiting an external decision (B1 data-route authorization).
- ``AUTHORIZED``  all prerequisites PASSED; the gate's action may be executed.
- ``RUNNING``     execution has started (set deliberately by the owner).
- ``PASSED``      completed; evidence (a non-synthetic execution record) is committed.
- ``FAILED``      executed and failed (e.g. B6 counts do not match; SR3 applies).
- ``BLOCKED``     halted by a stopping rule or an owner decision.

Dependency graph (protocol lifecycle; B3 and B4 both follow B2)::

    B1 -> B2 -> {B3, B4} -> B5 -> B6 -> B7 -> B8 -> B9 -> B10 -> B11 -> B12

Invariants (checked on every load of docs/project_status.yaml):

1. A gate whose prerequisites have not all PASSED is LOCKED (or BLOCKED).
2. A gate whose prerequisites have all PASSED is not LOCKED.
3. PASSED gates close in protocol order (B1, B2, ..., B12).
4. Software never advances a gate because files exist: transitions are explicit
   (``apply_transition``) and PASSED requires committed, non-synthetic evidence.

Gate-A items use CLOSED / OWNER_WAIVED; C and D gates use the simpler set
NOT_STARTED / IN_PROGRESS / PENDING / BLOCKED / CLOSED (``CD_TRANSITIONS``;
closing needs evidence, a date and the ``CD_PREREQUISITES`` closed). ``CLOSED``
and ``PASSED`` both count as closed.
"""

from __future__ import annotations

import copy
from typing import Any

from brats_uncertainty.errors import ConfigError

LIFECYCLE_STATUSES = ("LOCKED", "PENDING", "AUTHORIZED", "RUNNING", "PASSED", "FAILED", "BLOCKED")
B1_STATUSES = ("PENDING", "PASSED", "FAILED", "BLOCKED")
A_STATUSES = ("CLOSED", "OWNER_WAIVED")
CD_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "PENDING", "BLOCKED", "CLOSED")
CLOSED_STATUSES = frozenset({"CLOSED", "PASSED"})

B_GATES = tuple(f"B{i}" for i in range(1, 13))
PREREQUISITES: dict[str, tuple[str, ...]] = {
    "B1": (),
    "B2": ("B1",),
    "B3": ("B2",),
    "B4": ("B2",),
    "B5": ("B3", "B4"),
    "B6": ("B5",),
    **{f"B{i}": (f"B{i - 1}",) for i in range(7, 13)},
}
# Gates whose PASSED evidence must be a machine-readable execution record.
RECORD_EVIDENCE_GATES = ("B2", "B3", "B4", "B5", "B6")
# Statuses (and transitions out of BLOCKED) that must carry an evidence document.
EVIDENCE_STATUSES = frozenset({"PASSED", "FAILED", "BLOCKED"})

TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"PASSED", "FAILED", "BLOCKED"}),
    "LOCKED": frozenset({"AUTHORIZED", "BLOCKED"}),
    "AUTHORIZED": frozenset({"RUNNING", "BLOCKED"}),
    "RUNNING": frozenset({"PASSED", "FAILED", "BLOCKED"}),
    # FAILED never leads back to execution directly: the owner must first block the
    # gate with a documented decision, then unblock it with a further decision.
    "FAILED": frozenset({"BLOCKED"}),
    "BLOCKED": frozenset({"AUTHORIZED", "LOCKED", "PENDING"}),
    "PASSED": frozenset(),
}


C_GATES = tuple(f"C{i}" for i in range(1, 7))
D_GATES = tuple(f"D{i}" for i in range(1, 7))
# C/D transitions: CLOSED needs evidence and a date; BLOCKED, and leaving BLOCKED,
# need an evidence document (as for the B gates).
CD_TRANSITIONS: dict[str, frozenset[str]] = {
    "NOT_STARTED": frozenset({"IN_PROGRESS", "PENDING", "BLOCKED", "CLOSED"}),
    "PENDING": frozenset({"IN_PROGRESS", "BLOCKED", "CLOSED"}),
    "IN_PROGRESS": frozenset({"BLOCKED", "CLOSED"}),
    "BLOCKED": frozenset({"NOT_STARTED", "IN_PROGRESS"}),
    "CLOSED": frozenset(),
}
# Gates that must be closed before a C/D gate may close (protocol lifecycle text):
# D gates follow B1 approval (D2 "Approved data route (B1)"); the pilot constraints
# D3-D5 and the compute decision D6 follow D1/D2; C4 uses the frozen §6.2 procedure
# (B9); C5 thresholds come from validation, i.e. after the split and D6.
CD_PREREQUISITES: dict[str, tuple[str, ...]] = {
    "D1": ("B1",),
    "D2": ("B1",),
    "D3": ("D1", "D2"),
    "D4": ("D1", "D2"),
    "D5": ("D1", "D2"),
    "D6": ("D1", "D2", "D3", "D4", "D5"),
    "C4": ("B9",),
    "C5": (*B_GATES, *D_GATES),
}


def allowed_statuses(gid: str) -> tuple[str, ...]:
    if gid.startswith("A"):
        return A_STATUSES
    if gid == "B1":
        return B1_STATUSES
    if gid in B_GATES:
        return tuple(s for s in LIFECYCLE_STATUSES if s != "PENDING")
    return CD_STATUSES


def is_closed(status: str) -> bool:
    return status in CLOSED_STATUSES


def prerequisites_passed(gid: str, status_of: dict[str, str]) -> bool:
    return all(status_of.get(p) == "PASSED" for p in PREREQUISITES.get(gid, ()))


def check_invariants(status_of: dict[str, str]) -> None:
    """Raise ConfigError if the B-gate statuses violate the lifecycle invariants."""
    for gid in B_GATES:
        if gid not in status_of:
            continue
        s = status_of[gid]
        if s not in allowed_statuses(gid):
            raise ConfigError(
                f"gate {gid}: status {s!r} not allowed (allowed: {allowed_statuses(gid)})"
            )
        if gid == "B1":
            continue
        ready = prerequisites_passed(gid, status_of)
        if not ready and s not in ("LOCKED", "BLOCKED"):
            missing = [p for p in PREREQUISITES[gid] if status_of.get(p) != "PASSED"]
            raise ConfigError(
                f"gate {gid} is {s} but prerequisite(s) {missing} have not PASSED; "
                "it must be LOCKED"
            )
        if ready and s == "LOCKED":
            raise ConfigError(f"gate {gid} is LOCKED although its prerequisites have PASSED")
    open_seen = None
    for gid in B_GATES:
        if gid not in status_of:
            continue
        if is_closed(status_of[gid]) and open_seen is not None:
            raise ConfigError(f"gate {gid} is PASSED while earlier gate {open_seen} is not")
        if not is_closed(status_of[gid]) and open_seen is None:
            open_seen = gid


def unlock_eligible(status_of: dict[str, str]) -> dict[str, str]:
    """Return a copy with every LOCKED gate whose prerequisites PASSED set to AUTHORIZED."""
    out = dict(status_of)
    changed = True
    while changed:
        changed = False
        for gid in B_GATES[1:]:
            if out.get(gid) == "LOCKED" and prerequisites_passed(gid, out):
                out[gid] = "AUTHORIZED"
                changed = True
    return out


def relock(status_of: dict[str, str]) -> dict[str, str]:
    """Return a copy where gates whose prerequisites no longer all PASSED become LOCKED."""
    out = dict(status_of)
    for gid in B_GATES[1:]:
        if out.get(gid) in ("AUTHORIZED",) and not prerequisites_passed(gid, out):
            out[gid] = "LOCKED"
    return out


def apply_transition(
    raw: dict[str, Any],
    gid: str,
    new_status: str,
    *,
    evidence: str | None = None,
    on: str | None = None,
    approved_route: str | None = None,
) -> dict[str, Any]:
    """Return a new status mapping with ``gid`` moved to ``new_status``.

    Enforces the transition table, then unlocks newly eligible gates. PASSED
    needs evidence and a date; passing B1 also needs the approved route and
    sets ``data.authorization`` to APPROVED. The result must still pass
    ``validate_status`` before it is written.
    """
    out = copy.deepcopy(raw)
    gates = {g["id"]: g for g in out["gates"]}
    if gid not in gates:
        raise ConfigError(f"unknown gate {gid!r}")
    if gid in C_GATES or gid in D_GATES:
        if approved_route:
            raise ConfigError("approved_route may only be set when B1 passes")
        return _apply_cd_transition(out, gates, gid, new_status, evidence=evidence, on=on)
    if gid not in B_GATES:
        raise ConfigError("the lifecycle state machine governs gates B1-B12, C1-C6 and D1-D6")
    current = str(gates[gid]["status"])
    if new_status not in TRANSITIONS.get(current, frozenset()):
        raise ConfigError(f"illegal transition for {gid}: {current} -> {new_status}")
    status_of = {k: str(v["status"]) for k, v in gates.items()}
    if (
        new_status in ("AUTHORIZED", "RUNNING", "PASSED")
        and gid != "B1"
        and not prerequisites_passed(gid, status_of)
    ):
        raise ConfigError(f"{gid} cannot become {new_status}: prerequisites have not PASSED")
    if new_status == "PASSED":
        if not evidence or not on:
            raise ConfigError(f"{gid} -> PASSED requires evidence and a date")
        gates[gid]["evidence"] = evidence
        gates[gid]["closed_on"] = on
    elif new_status in EVIDENCE_STATUSES or current == "BLOCKED":
        if not evidence:
            raise ConfigError(
                f"{gid}: {current} -> {new_status} requires an evidence document "
                "(failure record or owner decision)"
            )
        if on:
            raise ConfigError("a date (closed_on) is only recorded when a gate PASSES")
        gates[gid]["evidence"] = evidence
    elif evidence or on:
        raise ConfigError(f"{gid}: {current} -> {new_status} takes no evidence or date")
    if gid == "B1":
        if new_status == "PASSED":
            if not approved_route:
                raise ConfigError("B1 -> PASSED requires the approved data route")
            out["data"]["authorization"] = "APPROVED"
            out["data"]["approved_route"] = approved_route
        elif new_status == "FAILED":
            out["data"]["authorization"] = "REFUSED"
    elif approved_route:
        raise ConfigError("approved_route may only be set when B1 passes")
    if gid == "B2" and new_status == "PASSED":
        out["data"]["acquired"] = True
    status_of[gid] = new_status
    status_of = relock(unlock_eligible(status_of))
    for k, g in gates.items():
        g["status"] = status_of[k]
    return out


def _apply_cd_transition(
    out: dict[str, Any],
    gates: dict[str, dict[str, Any]],
    gid: str,
    new_status: str,
    *,
    evidence: str | None,
    on: str | None,
) -> dict[str, Any]:
    current = str(gates[gid]["status"])
    if new_status not in CD_TRANSITIONS.get(current, frozenset()):
        raise ConfigError(f"illegal transition for {gid}: {current} -> {new_status}")
    if new_status in ("IN_PROGRESS", "CLOSED"):
        open_prereqs = [
            p for p in CD_PREREQUISITES.get(gid, ()) if not is_closed(str(gates[p]["status"]))
        ]
        if open_prereqs:
            raise ConfigError(f"{gid} cannot become {new_status}: {open_prereqs} not closed")
    if new_status == "CLOSED":
        if not evidence or not on:
            raise ConfigError(f"{gid} -> CLOSED requires evidence and a date")
        gates[gid]["evidence"] = evidence
        gates[gid]["closed_on"] = on
    elif new_status == "BLOCKED" or current == "BLOCKED":
        if not evidence:
            raise ConfigError(f"{gid}: {current} -> {new_status} requires an evidence document")
        if on:
            raise ConfigError("a date (closed_on) is only recorded when a gate closes")
        gates[gid]["evidence"] = evidence
    elif evidence or on:
        raise ConfigError(f"{gid}: {current} -> {new_status} takes no evidence or date")
    gates[gid]["status"] = new_status
    return out
