"""Manual-review records for flagged pairs (§6.2 step 4).

Record per pair: pair IDs, decision, reviewer, timestamp, reason (IDs only).
Decisions: SAME_PATIENT / DIFFERENT_PATIENT / UNRESOLVED.

Resolution rule. The primary reviewer reviews every flagged pair. The second
reviewer reviews disagreements independently. [Implementation of "if the pair
is still not resolved, it is classified as UNRESOLVED": a second review that
agrees with the primary decision confirms it; one that differs makes the pair
UNRESOLVED. To be confirmed by the owner before B8.]
SAME_PATIENT and UNRESOLVED are linked for grouping (conservative).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.grouping.similarity import pair_key

DECISIONS = ("SAME_PATIENT", "DIFFERENT_PATIENT", "UNRESOLVED")
LINKED_DECISIONS = frozenset({"SAME_PATIENT", "UNRESOLVED"})
ROUNDS = ("primary", "second")
CSV_FIELDS = ("case_a", "case_b", "decision", "reviewer", "round", "timestamp", "reason")


@dataclass(frozen=True)
class ReviewRecord:
    case_a: str
    case_b: str
    decision: str
    reviewer: str
    round: str
    timestamp: str
    reason: str

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise DataValidationError(f"invalid decision {self.decision!r}")
        if self.round not in ROUNDS:
            raise DataValidationError(f"invalid review round {self.round!r}")
        if not self.timestamp or not self.reason.strip():
            raise DataValidationError(
                f"review of {self.case_a}/{self.case_b} lacks timestamp or reason"
            )

    @property
    def key(self) -> tuple[str, str]:
        return pair_key(self.case_a, self.case_b)


def read_reviews(path: str | Path) -> list[ReviewRecord]:
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise DataValidationError(f"review CSV header must be {CSV_FIELDS}")
        return [ReviewRecord(**{k: row[k] for k in CSV_FIELDS}) for row in reader]


def write_reviews(path: str | Path, records: Iterable[ReviewRecord]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in sorted(records, key=lambda r: (r.key, ROUNDS.index(r.round))):
            w.writerow({k: getattr(r, k) for k in CSV_FIELDS})


def resolve_reviews(
    flagged: Sequence[tuple[str, str]],
    records: Iterable[ReviewRecord],
    reviewers: tuple[str, str],
) -> dict[tuple[str, str], str]:
    """Final decision per flagged pair; raises on any missing or out-of-procedure review."""
    primary_name, second_name = reviewers
    flagged_keys = {pair_key(a, b) for a, b in flagged}
    by_key: dict[tuple[str, str], dict[str, ReviewRecord]] = {}
    for r in records:
        if r.key not in flagged_keys:
            raise ProtocolDeviationError(f"review for a pair that was not flagged: {r.key}")
        expected = primary_name if r.round == "primary" else second_name
        if r.reviewer != expected:
            raise ProtocolDeviationError(
                f"{r.round} review of {r.key} by {r.reviewer!r}; protocol reviewer is {expected!r}"
            )
        slot = by_key.setdefault(r.key, {})
        if r.round in slot:
            raise DataValidationError(f"duplicate {r.round} review for {r.key}")
        slot[r.round] = r
    missing = sorted(k for k in flagged_keys if "primary" not in by_key.get(k, {}))
    if missing:
        raise DataValidationError(
            f"{len(missing)} flagged pairs lack a primary review, e.g. {missing[:3]}"
        )
    final: dict[tuple[str, str], str] = {}
    for k in sorted(flagged_keys):
        slot = by_key[k]
        p = slot["primary"].decision
        if "second" in slot:
            s = slot["second"].decision
            final[k] = p if s == p else "UNRESOLVED"
        else:
            final[k] = p
    return final


def read_automated_decisions(
    path: str | Path, flagged: Sequence[tuple[str, str]]
) -> dict[tuple[str, str], str]:
    """Amendment v1.0-A3 decisions: exactly one valid decision per flagged pair."""
    with Path(path).open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    final: dict[tuple[str, str], str] = {}
    for r in rows:
        k = pair_key(r["case_a"], r["case_b"])
        if r["decision"] not in DECISIONS:
            raise DataValidationError(f"invalid automated decision {r['decision']!r} for {k}")
        if k in final:
            raise DataValidationError(f"duplicate automated decision for {k}")
        final[k] = r["decision"]
    flagged_keys = {pair_key(a, b) for a, b in flagged}
    if set(final) != flagged_keys:
        raise ProtocolDeviationError(
            "automated decisions do not cover exactly the flagged pairs "
            f"({len(set(final) - flagged_keys)} extra, {len(flagged_keys - set(final))} missing)"
        )
    return final


def linked_pairs(decisions: Mapping[tuple[str, str], str]) -> list[tuple[str, str]]:
    return sorted(k for k, d in decisions.items() if d in LINKED_DECISIONS)
