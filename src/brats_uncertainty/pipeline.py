"""Gated pipeline stages for gates B7-B12 (same-patient screen -> grouping -> split).

The data-gate stages B2-B6 live in ``brats_uncertainty.data.stages``.

Every stage calls ``require_action`` first and therefore fails with
``ResearchGateError`` until the preceding protocol gates are legitimately
closed in ``docs/project_status.yaml``. Stages write outputs once and refuse to
overwrite them. No stage here trains, predicts or evaluates.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.data.crosswalk import CrosswalkRow, derive_cohorts, shared_tcia_id_groups
from brats_uncertainty.data.manifest import Manifest
from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.grouping.groups import PatientGrouping, build_groups
from brats_uncertainty.grouping.review import linked_pairs, read_reviews, resolve_reviews
from brats_uncertainty.grouping.similarity import MaskIndex, ScreenResult
from brats_uncertainty.grouping.tscreen import TScreenRecord, compute_t_screen, run_screen
from brats_uncertainty.metrics.volume import volume_ml
from brats_uncertainty.preprocessing.labels import BRATS2021_REGIONS
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.splitting.split import (
    SplitResult,
    assert_split,
    group_features,
    stratified_group_split,
)
from brats_uncertainty.utils.io import read_json, write_json


def load_label(path: Path) -> NDArray[np.integer]:
    try:
        import nibabel as nib
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "install the optional extra: pip install 'brats-uncertainty[io]'"
        ) from exc
    img: Any = nib.load(str(path))  # nibabel types load() too narrowly
    return np.asarray(img.dataobj).astype(np.int16)


def wt_mask(label: NDArray[np.integer]) -> NDArray[np.bool_]:
    return np.isin(label, BRATS2021_REGIONS["WT"])


def _label_paths(manifest: Manifest, data_root: Path) -> dict[str, tuple[Path, str]]:
    out = {}
    for e in manifest.entries:
        if e.label is None:
            raise DataValidationError(f"{e.case_id}: label required for the §6.2 screen")
        out[e.case_id] = (data_root / e.label.relpath, e.label.sha256)
    return out


def stage_t_screen(
    repo_root: Path, manifest: Manifest, data_root: Path, out: Path
) -> TScreenRecord:
    """Gate B7 (first half): T_screen from the two positive-control pairs only."""
    require_action("compute_t_screen", repo_root)
    spec = load_protocol(repo_root)
    labels = _label_paths(manifest, data_root)
    controls = {k: (v[0], v[1]) for k, v in spec.verified_groups.items()}
    needed = sorted({c for pair in controls.values() for c in pair})
    masks = {c: MaskIndex.from_mask(c, wt_mask(load_label(labels[c][0]))) for c in needed}
    record = compute_t_screen(masks, {c: labels[c][1] for c in needed}, controls)
    write_json(out, record.to_dict())
    return record


def stage_screen(
    repo_root: Path,
    manifest: Manifest,
    data_root: Path,
    t_screen_path: Path,
    development_ids: list[str],
    out_dir: Path,
) -> ScreenResult:
    """Gate B7 (second half): exhaustive pairwise WT-label screen of development cases."""
    require_action("pairwise_screen", repo_root)
    raw = read_json(t_screen_path)
    record = TScreenRecord(
        value=float(raw["value"]),
        control_dice={k: float(v) for k, v in raw["control_dice"].items()},
        control_pairs={k: (v[0], v[1]) for k, v in raw["control_pairs"].items()},
        label_sha256=dict(raw["label_sha256"]),
        computed_at=str(raw["computed_at"]),
    )
    labels = _label_paths(manifest, data_root)
    masks = {
        c: MaskIndex.from_mask(c, wt_mask(load_label(labels[c][0])))
        for c in sorted(development_ids)
    }
    controls = {k: (v[0], v[1]) for k, v in load_protocol(repo_root).verified_groups.items()}
    result = run_screen(masks, record, controls)
    out_dir.mkdir(parents=True, exist_ok=True)
    flagged_csv = out_dir / "flagged_pairs.csv"
    if flagged_csv.exists():
        raise FileExistsError(f"refusing to overwrite {flagged_csv}")
    with flagged_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_a", "case_b"])  # IDs only; Dice values are not needed for review
        for p in result.flagged:
            w.writerow([p.case_a, p.case_b])
    write_json(
        out_dir / "screen_summary.json",
        {
            "t_screen": result.t_screen,
            "n_cases": result.n_cases,
            "n_pairs_compared": result.n_pairs_compared,
            "n_flagged": len(result.flagged),
        },
    )
    return result


def stage_freeze_groups(
    repo_root: Path,
    development: list[CrosswalkRow],
    flagged_csv: Path,
    reviews_csv: Path | None,
    out_dir: Path,
    prefix: str = "DEV",
    *,
    automated_decisions: Path | None = None,
) -> PatientGrouping:
    """Gate B9: transitive grouping from verified groups, shared TCIA IDs and B8 decisions.

    B8 decisions come from the reviewers' CSV (section 6.2) or, under amendment v1.0-A3,
    from the automated adjudication record (``automated_decisions``).
    """
    require_action("freeze_patient_groups", repo_root)
    spec = load_protocol(repo_root)
    with flagged_csv.open(encoding="utf-8", newline="") as fh:
        flagged = [(r["case_a"], r["case_b"]) for r in csv.DictReader(fh)]
    if automated_decisions is not None:
        from brats_uncertainty.grouping.review import read_automated_decisions

        decisions = read_automated_decisions(automated_decisions, flagged)
    else:
        assert reviews_csv is not None
        decisions = resolve_reviews(flagged, read_reviews(reviews_csv), spec.reviewers)
    grouping = build_groups(
        [r.case_id for r in development],
        prefix=prefix,
        verified_groups=spec.verified_groups,
        shared_tcia_groups=shared_tcia_id_groups(development),
        linked_review_pairs=linked_pairs(decisions),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    groups_csv = out_dir / f"patient_groups_{prefix.lower()}.csv"
    if groups_csv.exists():
        raise FileExistsError(f"refusing to overwrite {groups_csv}")
    with groups_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case_id", "group_id"], lineterminator="\n")
        w.writeheader()
        w.writerows(grouping.to_rows())
    write_json(
        out_dir / f"grouping_audit_{prefix.lower()}.json",
        {**grouping.audit(), "decisions": {f"{a}|{b}": d for (a, b), d in decisions.items()}},
    )
    return grouping


def stage_create_split(
    repo_root: Path,
    crosswalk_rows: list[CrosswalkRow],
    grouping: PatientGrouping,
    labels: Mapping[str, Path],
    out_dir: Path,
) -> SplitResult:
    """Gates B10-B12: create the split once, assert, write IDs and hashes."""
    require_action("create_split", repo_root)
    spec = load_protocol(repo_root)
    cohorts_cfg: dict[str, Any] = spec.raw["cohorts"]
    derive_cohorts(
        crosswalk_rows,
        hoi_site_id=str(cohorts_cfg["hoi_site_id"]),
        expected_total=int(cohorts_cfg["brats2021_training_total"]),
        expected_hoi=int(cohorts_cfg["hoi_count"]),
        expected_development=int(cohorts_cfg["development_count_before_grouping"]),
    )
    if (out_dir / "split_all.csv").exists():
        raise FileExistsError("the split already exists; it is created once only (§6.3)")
    et_present: dict[str, bool] = {}
    wt_ml: dict[str, float] = {}
    for c in grouping.case_to_group:
        lab = load_label(labels[c])
        et_present[c] = bool(np.isin(lab, BRATS2021_REGIONS["ET"]).any())
        wt_ml[c] = volume_ml(wt_mask(lab))
    result = stratified_group_split(group_features(grouping.groups, et_present, wt_ml))
    assert_split(
        result,
        site_of_case={r.case_id: r.site_id for r in crosswalk_rows},
        hoi_site_id=str(cohorts_cfg["hoi_site_id"]),
        expected_development_count=int(cohorts_cfg["development_count_before_grouping"]),
        verified_groups=spec.verified_groups,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "split_all.csv").write_bytes(result.csv_bytes())
    write_json(out_dir / "split_summary.json", result.summary())
    return result
