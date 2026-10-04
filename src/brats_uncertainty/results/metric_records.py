"""Result-artifact contract: one scientific number = one fully attributed metric record.

Every future scientific value (and nothing else) is published as a record in a
``*.metrics.json`` file: ``{"schema_version": 1, "records": [...]}``. The website and
README tables are generated from validated records only; no value is typed by hand.
JSON Schema: ``configs/schemas/result_metric.schema.json`` (kept in sync by tests).

Names come from the frozen protocol config (configs/protocol/protocol_v1.0.yaml):
conditions C5 = Full, -T1, -T1c, -T2, -FLAIR (C4 = the four missing-sequence
conditions, Full = control), the C4 equal-weight mean, C15 subsets (``subset:T1+T2``),
and the dataset roles validation / internal_test / upenn_hoi / brats_africa.
Synthetic (test-fixture) records are valid for tests but can never be exported.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from brats_uncertainty.errors import ProvenanceError
from brats_uncertainty.utils.io import read_json

METRIC_SCHEMA_VERSION = 1
C5_CONDITIONS = ("Full", "-T1", "-T1c", "-T2", "-FLAIR")
AGGREGATE_CONDITIONS = ("C4_mean",)
_SUBSET = re.compile(r"^subset:(T1|T1c|T2|FLAIR)(\+(T1|T1c|T2|FLAIR)){0,3}$")
DATASET_ROLES = ("validation", "internal_test", "upenn_hoi", "brats_africa")
ARMS = ("A", "B")
UNCERTAINTY_MEASURES = ("U1", "U2", "U3", "I")
SEED_OR_ENSEMBLE = re.compile(r"^(ensemble|seed:[012])$")
# metric -> (unit, lower bound, upper bound); bounds None = unbounded
METRICS: dict[str, tuple[str, float | None, float | None]] = {
    "dice_ET": ("proportion", 0.0, 1.0),
    "dice_TC": ("proportion", 0.0, 1.0),
    "dice_WT": ("proportion", 0.0, 1.0),
    "risk": ("proportion", 0.0, 1.0),
    "aurc": ("proportion", 0.0, 1.0),
    "delta_aurc": ("proportion", -1.0, 1.0),
    "coverage": ("proportion", 0.0, 1.0),
    "selective_risk": ("proportion", 0.0, 1.0),
    "delta_risk": ("proportion", -1.0, 1.0),
    "delta_coverage": ("proportion", -1.0, 1.0),
    "threshold_tau": ("dimensionless", None, None),
    "ece": ("proportion", 0.0, 1.0),
    "brier": ("proportion", 0.0, 1.0),
    "volume_relative_error": ("dimensionless", 0.0, None),
    "volume_failure_rate": ("proportion", 0.0, 1.0),
    "n_cases": ("count", 0.0, None),
    "n_patient_groups": ("count", 0.0, None),
}
REQUIRED = (
    "experiment_id",
    "condition",
    "metric",
    "value",
    "unit",
    "population",
    "dataset_role",
    "seed_or_ensemble",
    "arm",
    "protocol_version",
    "git_commit",
    "dataset_hash",
    "split_hash",
    "config_hash",
    "synthetic",
)
OPTIONAL = ("uncertainty", "ci_lower", "ci_upper", "ci_method", "p_value", "n", "notes")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_EXPERIMENT = re.compile(r"^[A-Z][A-Z0-9-]{1,31}$")


def _num(x: Any, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, int | float) or not math.isfinite(x):
        raise ProvenanceError(f"{name} must be a finite number")
    return float(x)


def validate_metric_record(rec: Mapping[str, Any]) -> None:
    """Strict validation of one metric record (fails closed on any deviation)."""
    missing = [k for k in REQUIRED if k not in rec]
    unknown = [k for k in rec if k not in REQUIRED and k not in OPTIONAL]
    if missing or unknown:
        raise ProvenanceError(f"metric record: missing {missing}, unknown {unknown}")
    if not _EXPERIMENT.match(str(rec["experiment_id"])):
        raise ProvenanceError("experiment_id malformed")
    cond = str(rec["condition"])
    if cond not in C5_CONDITIONS + AGGREGATE_CONDITIONS and not _SUBSET.match(cond):
        raise ProvenanceError(f"condition {cond!r} is not a protocol condition")
    metric = str(rec["metric"])
    if metric not in METRICS:
        raise ProvenanceError(f"metric {metric!r} not in the result contract")
    unit, lo, hi = METRICS[metric]
    if rec["unit"] != unit:
        raise ProvenanceError(f"{metric}: unit must be {unit!r}")
    value = _num(rec["value"], "value")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise ProvenanceError(f"{metric}: value {value} outside [{lo}, {hi}]")
    if unit == "count" and value != int(value):
        raise ProvenanceError(f"{metric}: counts are integers")
    if not str(rec["population"]).strip():
        raise ProvenanceError("population must be described")
    if rec["dataset_role"] not in DATASET_ROLES:
        raise ProvenanceError(f"dataset_role must be one of {DATASET_ROLES}")
    if not SEED_OR_ENSEMBLE.match(str(rec["seed_or_ensemble"])):
        raise ProvenanceError("seed_or_ensemble must be 'ensemble' or 'seed:0|1|2'")
    if rec["arm"] not in ARMS:
        raise ProvenanceError("arm must be A or B")
    if rec["protocol_version"] != "v1.0":
        raise ProvenanceError("protocol_version must be v1.0")
    if not _COMMIT.match(str(rec["git_commit"])):
        raise ProvenanceError("git_commit must be a full SHA")
    for h in ("dataset_hash", "split_hash", "config_hash"):
        if not _SHA.match(str(rec[h])):
            raise ProvenanceError(f"{h} must be a SHA-256")
    if not isinstance(rec["synthetic"], bool):
        raise ProvenanceError("synthetic must be a boolean")
    if rec.get("uncertainty") is not None and rec["uncertainty"] not in UNCERTAINTY_MEASURES:
        raise ProvenanceError(f"uncertainty must be one of {UNCERTAINTY_MEASURES}")
    if ("ci_lower" in rec) != ("ci_upper" in rec):
        raise ProvenanceError("ci_lower and ci_upper go together")
    if "ci_lower" in rec:
        if _num(rec["ci_lower"], "ci_lower") > _num(rec["ci_upper"], "ci_upper"):
            raise ProvenanceError("ci_lower > ci_upper")
        if rec.get("ci_method") not in ("percentile", "BCa"):
            raise ProvenanceError("ci_method must be 'percentile' or 'BCa' (protocol §13)")
    if "p_value" in rec and not 0.0 <= _num(rec["p_value"], "p_value") <= 1.0:
        raise ProvenanceError("p_value outside [0, 1]")
    if "n" in rec and (_num(rec["n"], "n") < 0 or rec["n"] != int(rec["n"])):
        raise ProvenanceError("n must be a non-negative integer")


def validate_metric_file(path: Path, *, allow_synthetic: bool = False) -> list[dict[str, Any]]:
    doc = read_json(path)
    if not isinstance(doc, dict) or doc.get("schema_version") != METRIC_SCHEMA_VERSION:
        raise ProvenanceError(f"{path.name}: schema_version must be {METRIC_SCHEMA_VERSION}")
    records = doc.get("records")
    if not isinstance(records, list) or not records:
        raise ProvenanceError(f"{path.name}: no records")
    for r in records:
        validate_metric_record(r)
        if r["synthetic"] and not allow_synthetic:
            raise ProvenanceError(f"{path.name}: synthetic records can never be published")
    keys = [
        (
            r["experiment_id"],
            r["condition"],
            r["metric"],
            r["dataset_role"],
            r["arm"],
            r["seed_or_ensemble"],
            r.get("uncertainty"),
            r["population"],
        )
        for r in records
    ]
    if len(set(keys)) != len(keys):
        raise ProvenanceError(f"{path.name}: duplicate metric records")
    return records
