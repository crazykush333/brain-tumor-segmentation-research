"""SR2 sanity rule and the validation-only freeze of tau_q and I (gate C5).

- SR2 (§20): if arm A's full-input mean ET Dice on **validation** is < 0.75, stop
  and debug before any test evaluation. [Implementation: the Dice of the arm-A
  3-member ensemble (the evaluated model, §9), averaged over validation cases.]
- C5: tau_q for q in {0.80, 0.70, 0.90} (S7) and 0.20 (§19), from the arm-B ET U1 of
  the validation C4 units with the deterministic >= rule (``statistics.thresholds``);
  I = -(validation mean risk) per arm, region and C5 condition (§11). Nothing here
  reads test or external units.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.preprocessing.modalities import C4_NAMES, C5_NAMES
from brats_uncertainty.statistics.thresholds import FAILURE_ANALYSIS_Q, PROTOCOL_Q, select_tau
from brats_uncertainty.statistics.units import UnitTable
from brats_uncertainty.study.units import REGIONS

SR2_THRESHOLD = 0.75
FREEZE_Q = (*PROTOCOL_Q, FAILURE_ANALYSIS_Q)


def unit_table(
    rows: Sequence[Mapping[str, str]], region: str, conditions: Sequence[str] | None = None
) -> UnitTable:
    sel = [
        r
        for r in rows
        if r["region"] == region and (conditions is None or r["condition"] in conditions)
    ]
    if not sel:
        raise DataValidationError(f"no units for region {region} and conditions {conditions}")
    scores = {
        s: [float(r[s]) for r in sel]
        for s in ("U1", "U2", "U3", "I")
        if all(r[s] != "" for r in sel)
    }
    return UnitTable.from_columns(
        [r["case_id"] for r in sel],
        [r["group_id"] for r in sel],
        [r["condition"] for r in sel],
        [float(r["risk"]) for r in sel],
        scores,
    )


def _only(rows: Sequence[Mapping[str, str]], dataset: str, arm: str) -> None:
    bad = {(r["dataset"], r["arm"]) for r in rows} - {(dataset, arm)}
    if bad:
        raise ProtocolDeviationError(
            f"expected only {dataset} arm {arm} units, found {sorted(bad)}"
        )


def sr2_check(validation_arm_a: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    _only(validation_arm_a, "validation", "A")
    d = [
        float(r["dice"])
        for r in validation_arm_a
        if r["condition"] == "Full" and r["region"] == "ET"
    ]
    if not d:
        raise DataValidationError("no arm-A Full ET validation units")
    mean = float(np.mean(d))
    return {
        "rule": "SR2: arm A full-input mean ET Dice on validation >= 0.75",
        "mean_et_dice": mean,
        "n_cases": len(d),
        "threshold": SR2_THRESHOLD,
        "passed": mean >= SR2_THRESHOLD,
    }


def freeze_c5(
    validation_arm_a: Sequence[Mapping[str, str]],
    validation_arm_b: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """The frozen C5 record (tau_q and I); computed from validation units only."""
    _only(validation_arm_a, "validation", "A")
    _only(validation_arm_b, "validation", "B")
    et_b = unit_table(validation_arm_b, "ET", C4_NAMES)
    taus = {}
    for q in FREEZE_Q:
        t = select_tau(et_b.score("U1"), et_b.condition, q)
        taus[f"{q:.2f}"] = {"tau": t.tau, "realized_validation_coverage": t.realized_coverage}
    indicator: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for arm, rows in (("A", validation_arm_a), ("B", validation_arm_b)):
        indicator[arm] = {}
        for region in REGIONS:
            indicator[arm][region] = {}
            for cond in C5_NAMES:
                r = [
                    float(x["risk"])
                    for x in rows
                    if x["region"] == region and x["condition"] == cond
                ]
                if not r:
                    raise DataValidationError(f"no validation units: arm {arm} {region} {cond}")
                mean_risk = float(np.mean(r))
                indicator[arm][region][cond] = {"mean_risk": mean_risk, "I": -mean_risk}
    return {
        "gate": "C5",
        "population": "internal validation; tau from arm-B ET U1 on C4 (equal condition weighting)",
        "tau_q": taus,
        "indicator": indicator,
        "n_validation_cases": len({r["case_id"] for r in validation_arm_b}),
    }


def apply_indicator(
    rows: Sequence[Mapping[str, str]], frozen: Mapping[str, Any]
) -> list[dict[str, str]]:
    """Fill the I column from the frozen validation record (C5 conditions only)."""
    out = []
    for r in rows:
        row = dict(r)
        cond_map = frozen["indicator"][r["arm"]][r["region"]]
        if r["condition"] in cond_map:
            row["I"] = repr(float(cond_map[r["condition"]]["I"]))
        out.append(row)
    return out
