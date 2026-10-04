"""Evaluation-unit table: one row per case-condition unit for one region.

Mirrors the per-unit metric CSV of protocol §24 (case ID, patient-group ID,
condition, region, metrics, scores).
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError


@dataclass(frozen=True)
class UnitTable:
    case_id: NDArray[np.str_]
    group_id: NDArray[np.str_]
    condition: NDArray[np.str_]
    risk: NDArray[np.float64]
    scores: Mapping[str, NDArray[np.float64]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.case_id)
        arrays = {"group_id": self.group_id, "condition": self.condition, "risk": self.risk}
        arrays.update({f"score:{k}": v for k, v in self.scores.items()})
        for name, arr in arrays.items():
            if len(arr) != n:
                raise DataValidationError(f"column {name} has length {len(arr)} != {n}")
        if n and (
            np.any(self.risk < 0) or np.any(self.risk > 1) or not np.all(np.isfinite(self.risk))
        ):
            raise DataValidationError("risk must be finite and in [0, 1]")
        # a case must belong to exactly one patient group
        pairs = {(c, g) for c, g in zip(self.case_id.tolist(), self.group_id.tolist(), strict=True)}
        cases = [c for c, _ in pairs]
        if len(cases) != len(set(cases)):
            raise DataValidationError("a case is assigned to more than one patient group")
        # one unit per case-condition
        keys = list(zip(self.case_id.tolist(), self.condition.tolist(), strict=True))
        if len(keys) != len(set(keys)):
            raise DataValidationError("duplicate case-condition units")

    @classmethod
    def from_columns(
        cls,
        case_id: Sequence[str],
        group_id: Sequence[str],
        condition: Sequence[str],
        risk: Sequence[float],
        scores: Mapping[str, Sequence[float]] | None = None,
    ) -> UnitTable:
        return cls(
            case_id=np.asarray(case_id, dtype=str),
            group_id=np.asarray(group_id, dtype=str),
            condition=np.asarray(condition, dtype=str),
            risk=np.asarray(risk, dtype=np.float64),
            scores={k: np.asarray(v, dtype=np.float64) for k, v in (scores or {}).items()},
        )

    def __len__(self) -> int:
        return len(self.case_id)

    def score(self, name: str) -> NDArray[np.float64]:
        if name not in self.scores:
            raise KeyError(f"score {name!r} not present; available: {sorted(self.scores)}")
        return self.scores[name]


UNIT_CSV_REQUIRED = ("case_id", "group_id", "condition", "region", "risk")
UNIT_CSV_SCORES = ("U1", "U2", "U3", "I")


def read_units_csv(path: str | Path, region: str) -> UnitTable:
    """Read the per-unit metric CSV of protocol §24 and select one region."""
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = tuple(reader.fieldnames or ())
        missing = [c for c in UNIT_CSV_REQUIRED if c not in header]
        if missing:
            raise DataValidationError(f"{path}: missing columns {missing}")
        rows = [r for r in reader if r["region"] == region]
    if not rows:
        raise DataValidationError(f"{path}: no units for region {region!r}")
    scores = {
        s: [float(r[s]) for r in rows] for s in UNIT_CSV_SCORES if s in header and rows[0][s] != ""
    }
    return UnitTable.from_columns(
        [r["case_id"] for r in rows],
        [r["group_id"] for r in rows],
        [r["condition"] for r in rows],
        [float(r["risk"]) for r in rows],
        scores,
    )
