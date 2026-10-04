"""SYNTHETIC_TEST_ONLY B1 authorization workflow (test mode).

Exercises the real B1 parser and content checks on a *synthetic* provider
response, and runs a separate test-only state machine::

    SYNTHETIC_TEST_B1: PENDING -> TEST_AUTHORIZED

It is deliberately disjoint from production:

- the test gate, ``SYNTHETIC_TEST_B1``, and the state ``TEST_AUTHORIZED`` do not exist in
  ``evaluation.lifecycle``, so they can never appear in ``docs/project_status.yaml``;
- the functions are pure: they read no status file and write nothing;
- the real gate B1 refuses every record carrying a synthetic marker
  (``evidence.check_b1_evidence``), so a synthetic record can never unlock B2 or
  let a real acquisition adapter execute.

The real gate's "authorized" state is ``PASSED``; ``AUTHORIZED`` is never reused for
synthetic authorization.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from brats_uncertainty.data.evidence import (
    SOURCE_CLASS_SYNTHETIC,
    SYNTHETIC_TEST_ONLY,
    B1Evidence,
    parse_b1_evidence,
    validate_b1_content,
)
from brats_uncertainty.errors import ConfigError

SYNTHETIC_B1_GATE = "SYNTHETIC_TEST_B1"
TEST_PENDING = "PENDING"
TEST_AUTHORIZED = "TEST_AUTHORIZED"
SYNTHETIC_B1_TRANSITIONS: dict[str, frozenset[str]] = {
    TEST_PENDING: frozenset({TEST_AUTHORIZED}),
    TEST_AUTHORIZED: frozenset(),
}
SYNTHETIC_OUTCOME = ("TEST_AUTHORIZED", "TEST_APPROVED")


@dataclass(frozen=True)
class SyntheticB1Outcome:
    gate: str
    previous: str
    status: str
    approved_route: str
    evidence: B1Evidence
    source_class: str = SOURCE_CLASS_SYNTHETIC
    synthetic: bool = True


def synthetic_b1_transition(
    text: str,
    *,
    identity: Mapping[str, Any],
    protocol_version: str,
    current: str = TEST_PENDING,
    target: str = TEST_AUTHORIZED,
) -> SyntheticB1Outcome:
    """Validate a SYNTHETIC_TEST_ONLY record and return the test-gate transition (no I/O)."""
    if target not in SYNTHETIC_B1_TRANSITIONS.get(current, frozenset()):
        raise ConfigError(f"{SYNTHETIC_B1_GATE}: illegal test transition {current} -> {target}")
    ev = parse_b1_evidence(text)
    if not ev.synthetic or ev.source_class != SOURCE_CLASS_SYNTHETIC:
        raise ConfigError(
            f"{SYNTHETIC_B1_GATE}: test mode accepts only {SOURCE_CLASS_SYNTHETIC} records; "
            "real evidence goes through `brats-uncertainty gate-transition B1 PASSED`"
        )
    if SYNTHETIC_TEST_ONLY not in text:
        raise ConfigError(f"{SYNTHETIC_B1_GATE}: record must be labelled {SYNTHETIC_TEST_ONLY}")
    validate_b1_content(
        ev,
        identity=identity,
        protocol_version=protocol_version,
        approved_route=ev.fields["Approved route"],
        outcome=SYNTHETIC_OUTCOME,
    )
    return SyntheticB1Outcome(
        gate=SYNTHETIC_B1_GATE,
        previous=current,
        status=target,
        approved_route=ev.fields["Approved route"],
        evidence=ev,
    )
