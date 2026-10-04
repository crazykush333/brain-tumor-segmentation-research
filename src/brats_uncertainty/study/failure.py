"""Failure analysis (protocol §19, rule-based; per condition and dataset).

- Confident failure: U1 >= tau_0.20 (frozen at C5) and ET Dice < 0.5.
- Hallucinated ET: GT ET empty, predicted ET present (broken down by condition,
  especially -T1c). Missed ET: GT ET present, predicted ET empty.
- Region false negatives / false positives (05 §6) for WT/TC/ET.

Figure cases are selected by rule (seed 7), never by hand: per category, the
sorted case IDs are permuted with ``numpy.random.default_rng(7)`` and up to
``per_category`` are taken; at most 20 in total (§17). [Implementation of the
rule; flagged for owner confirmation at C6.] Only IDs are recorded: patient images
are never exported.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

FIGURE_SEED = 7
MAX_FIGURE_CASES = 20
CONFIDENT_FAILURE_DICE = 0.5


def categorize(rows: Sequence[Mapping[str, str]], tau_020: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cond in sorted({r["condition"] for r in rows}):
        sel = [r for r in rows if r["condition"] == cond]
        et = [r for r in sel if r["region"] == "ET"]
        cats: dict[str, list[str]] = {
            "confident_failure": sorted(
                r["case_id"]
                for r in et
                if float(r["U1"]) >= tau_020 and float(r["dice"]) < CONFIDENT_FAILURE_DICE
            ),
            "hallucinated_ET": sorted(
                r["case_id"] for r in et if int(r["gt_voxels"]) == 0 and int(r["pred_voxels"]) > 0
            ),
            "missed_ET": sorted(
                r["case_id"] for r in et if int(r["gt_voxels"]) > 0 and int(r["pred_voxels"]) == 0
            ),
        }
        for region in ("WT", "TC"):
            reg = [r for r in sel if r["region"] == region]
            cats[f"false_negative_{region}"] = sorted(
                r["case_id"] for r in reg if int(r["gt_voxels"]) > 0 and int(r["pred_voxels"]) == 0
            )
            cats[f"false_positive_{region}"] = sorted(
                r["case_id"] for r in reg if int(r["gt_voxels"]) == 0 and int(r["pred_voxels"]) > 0
            )
        out[cond] = {
            "n_cases": len(et),
            "counts": {k: len(v) for k, v in cats.items()},
            "cases": cats,
        }
    return out


def figure_cases(categories: Mapping[str, Any], per_category: int = 3) -> list[dict[str, str]]:
    """Rule-based figure-case selection (seed 7); IDs only."""
    rng = np.random.default_rng(FIGURE_SEED)
    chosen: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for cond in sorted(categories):
        for cat in ("confident_failure", "hallucinated_ET", "missed_ET"):
            ids = list(categories[cond]["cases"][cat])
            for i in rng.permutation(len(ids))[:per_category]:
                key = (ids[i], cond)
                if key not in seen and len(chosen) < MAX_FIGURE_CASES:
                    seen.add(key)
                    chosen.append({"case_id": ids[i], "condition": cond, "category": cat})
    return chosen
