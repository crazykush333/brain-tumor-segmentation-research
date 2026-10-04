"""Evaluation ledger (SR4): each test/external set is evaluated once with tagged code.

A second evaluation of the same (dataset, arm) is refused unless a
re-evaluation reason is given; both evaluations then remain in the append-only
ledger and must both be reported.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from brats_uncertainty.errors import ResearchGateError

LEDGER_RELPATH = Path("experiments/evaluation_ledger.jsonl")
EVALUATION_SETS = ("internal_test", "upenn_hoi", "brats_africa")


@dataclass(frozen=True)
class LedgerEntry:
    dataset: str
    arm: str
    git_commit: str
    eval_tag: str
    timestamp: str
    reevaluation_reason: str | None = None


def read_ledger(path: Path) -> list[LedgerEntry]:
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(LedgerEntry(**json.loads(line)))
    return entries


def record_evaluation(
    path: Path,
    dataset: str,
    arm: str,
    git_commit: str,
    eval_tag: str,
    reevaluation_reason: str | None = None,
) -> LedgerEntry:
    if dataset not in EVALUATION_SETS:
        raise ValueError(f"unknown evaluation set {dataset!r}")
    previous = [e for e in read_ledger(path) if e.dataset == dataset and e.arm == arm]
    if previous and not reevaluation_reason:
        raise ResearchGateError(
            f"{dataset} (arm {arm}) was already evaluated at {previous[0].timestamp}. "
            "SR4: re-evaluation must be logged with a reason and both results reported."
        )
    entry = LedgerEntry(
        dataset=dataset,
        arm=arm,
        git_commit=git_commit,
        eval_tag=eval_tag,
        timestamp=datetime.now(UTC).isoformat(),
        reevaluation_reason=reevaluation_reason,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
    return entry
