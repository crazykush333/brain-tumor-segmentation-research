"""Per-unit metric rows (protocol §24): one row per case-condition-region unit.

For each case, condition and region the row holds:

- ensemble Dice (mean of the 3 members' probabilities, threshold 0.5; §9) and risk
  = 1 - Dice (§3 empty-mask convention), plus each member's Dice (seed variation,
  descriptive §13);
- U1, U2, U3 (§11) from the three members' probabilities; I is filled only after
  the validation-derived freeze (gate C5) and stays empty before;
- voxel counts and volumes; for ET the absolute volume error and the S5 binary
  volume failures at 40 % / 65 % (empty when GT ET < 1 mL);
- ECE / Brier on the ensemble-mean probability within the protocol ROI (S4);
- HD95 only from the evaluator pinned at gate C6 (empty until then; §4 S3).

No metric is computed against labels for EXP-001 (D4): this module is used only
for validation, test and external evaluation.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.errors import DataValidationError, ProtocolDeviationError
from brats_uncertainty.inference.ensemble import PROTOCOL_N_MEMBERS, binarize, ensemble_mean
from brats_uncertainty.metrics.calibration import case_calibration
from brats_uncertainty.metrics.dice import dice, risk_from_dice
from brats_uncertainty.metrics.volume import (
    PRIMARY_REL_THRESHOLD,
    SENSITIVITY_REL_THRESHOLD,
    volume_failure_from_counts,
)
from brats_uncertainty.uncertainty.scores import case_scores

REGIONS = ("WT", "TC", "ET")
DATASETS = ("validation", "internal_test", "upenn_hoi", "brats_africa")
UNIT_FIELDS = (
    "case_id",
    "group_id",
    "dataset",
    "arm",
    "condition",
    "region",
    "dice",
    "risk",
    "dice_member_0",
    "dice_member_1",
    "dice_member_2",
    "U1",
    "U2",
    "U3",
    "I",
    "gt_voxels",
    "pred_voxels",
    "gt_ml",
    "pred_ml",
    "abs_vol_err_ml",
    "vol_fail_40",
    "vol_fail_65",
    "ece",
    "brier",
    "roi_voxels",
    "hd95",
)
Hd95Fn = Callable[[NDArray[np.bool_], NDArray[np.bool_], tuple[float, float, float]], float]


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return "" if math.isnan(v) else repr(v)
    return str(v)


def unit_rows(
    *,
    case_id: str,
    group_id: str,
    dataset: str,
    arm: str,
    condition: str,
    member_probs: Mapping[str, Sequence[NDArray[np.floating]]],
    gt: Mapping[str, NDArray[np.bool_]],
    spacing_mm: tuple[float, float, float] = (1.0, 1.0, 1.0),
    hd95: Hd95Fn | None = None,
) -> list[dict[str, str]]:
    """Rows for one case and one condition (all three regions)."""
    if dataset not in DATASETS:
        raise DataValidationError(f"unknown dataset {dataset!r}")
    if arm not in ("A", "B"):
        raise ProtocolDeviationError(f"unknown arm {arm!r}")
    voxel_ml = float(np.prod(spacing_mm)) / 1000.0
    rows: list[dict[str, str]] = []
    for region in REGIONS:
        probs = member_probs[region]
        if len(probs) != PROTOCOL_N_MEMBERS:
            raise ProtocolDeviationError(f"{region}: exactly {PROTOCOL_N_MEMBERS} members needed")
        g = np.asarray(gt[region], dtype=bool)
        mean = ensemble_mean(probs)
        if mean.shape != g.shape:
            raise DataValidationError(
                f"{case_id}/{region}: prediction {mean.shape} vs GT {g.shape}"
            )
        pred = binarize(mean)
        d = dice(pred, g)
        scores = case_scores(probs)
        cal = case_calibration(mean, g)
        gt_vox, pred_vox = int(g.sum()), int(pred.sum())
        row: dict[str, Any] = {
            "case_id": case_id,
            "group_id": group_id,
            "dataset": dataset,
            "arm": arm,
            "condition": condition,
            "region": region,
            "dice": d,
            "risk": risk_from_dice(d),
            **{f"dice_member_{i}": dice(binarize(p), g) for i, p in enumerate(probs)},
            "U1": scores["U1"],
            "U2": scores["U2"],
            "U3": scores["U3"],
            "I": None,
            "gt_voxels": gt_vox,
            "pred_voxels": pred_vox,
            "gt_ml": gt_vox * voxel_ml,
            "pred_ml": pred_vox * voxel_ml,
            "ece": cal["ece"],
            "brier": cal["brier"],
            "roi_voxels": int(cal["roi_voxels"]),
            "hd95": None if hd95 is None else float(hd95(pred, g, spacing_mm)),
        }
        if region == "ET":
            row["abs_vol_err_ml"] = abs(pred_vox - gt_vox) * voxel_ml
            row["vol_fail_40"] = volume_failure_from_counts(
                pred_vox, gt_vox, voxel_ml, PRIMARY_REL_THRESHOLD
            )
            row["vol_fail_65"] = volume_failure_from_counts(
                pred_vox, gt_vox, voxel_ml, SENSITIVITY_REL_THRESHOLD
            )
        rows.append({k: _fmt(row.get(k)) for k in UNIT_FIELDS})
    return rows


def write_units(path: Path, rows: Iterable[Mapping[str, str]]) -> Path:
    """Write rows (one file per dataset x arm); refuses to overwrite."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path.name}")
    rows = list(rows)
    keys = {(r["case_id"], r["condition"], r["region"]) for r in rows}
    if len(keys) != len(rows):
        raise DataValidationError("duplicate case-condition-region units")
    if len({(r["dataset"], r["arm"]) for r in rows}) > 1:
        raise DataValidationError("one units file holds exactly one dataset and one arm")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=UNIT_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["case_id"], r["condition"], r["region"])):
            w.writerow({k: r.get(k, "") for k in UNIT_FIELDS})
    tmp.replace(path)
    return path


def read_unit_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != UNIT_FIELDS:
            raise DataValidationError(f"{path.name}: unexpected header")
        return list(reader)


def units_filename(dataset: str, arm: str, subsets: str = "C5") -> str:
    return f"units_{dataset}_arm{arm}_{subsets}.csv"
