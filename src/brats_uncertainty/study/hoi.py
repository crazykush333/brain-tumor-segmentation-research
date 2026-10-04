"""Gate C4: HOI patient grouping with the same frozen §6.2 rule and procedure.

The pairwise WT-label screen runs within the 511 HOI (site-1) cases with the
T_screen value computed once at B7 from the development positive controls (never
recomputed); flagged pairs go to the same human review (two named reviewers); SAME
PATIENT and UNRESOLVED pairs and shared real TCIA IDs are grouped transitively. The
groups only define bootstrap units; they have no effect on training (§6.2).
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from brats_uncertainty.data.crosswalk import CrosswalkRow, shared_tcia_id_groups
from brats_uncertainty.evaluation.guards import require_action
from brats_uncertainty.grouping.groups import PatientGrouping, build_groups
from brats_uncertainty.grouping.review import linked_pairs, read_reviews, resolve_reviews
from brats_uncertainty.grouping.similarity import MaskIndex, pairwise_screen
from brats_uncertainty.utils.io import read_json, write_json

HOI_PREFIX = "HOI"


def screen_hoi(
    repo_root: Path,
    masks: Mapping[str, MaskIndex],
    t_screen_record: Path,
    out_dir: Path,
) -> list[tuple[str, str]]:
    require_action("hoi_grouping", repo_root)
    value = float(read_json(t_screen_record)["value"])  # frozen at B7
    result = pairwise_screen(masks, value)
    out_dir.mkdir(parents=True, exist_ok=True)
    flagged = sorted(p.key for p in result.flagged)
    path = out_dir / "flagged_pairs_hoi.csv"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path.name}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_a", "case_b"])
        w.writerows(flagged)
    write_json(
        out_dir / "screen_summary_hoi.json",
        {
            "t_screen": value,
            "n_cases": result.n_cases,
            "n_pairs_compared": result.n_pairs_compared,
            "n_flagged": len(flagged),
        },
    )
    return flagged


def freeze_hoi_groups(
    repo_root: Path,
    hoi_rows: Sequence[CrosswalkRow],
    flagged: Sequence[tuple[str, str]],
    reviews_csv: Path | None,
    reviewers: tuple[str, str],
    out_csv: Path,
) -> PatientGrouping:
    require_action("hoi_grouping", repo_root)
    decisions: dict[tuple[str, str], str] = {}
    if flagged:
        if reviews_csv is None:
            raise FileNotFoundError("HOI review decisions are required for the flagged pairs")
        decisions = resolve_reviews(flagged, read_reviews(reviews_csv), reviewers)
    grouping = build_groups(
        [r.case_id for r in hoi_rows],
        prefix=HOI_PREFIX,
        verified_groups={},
        shared_tcia_groups=shared_tcia_id_groups(hoi_rows),
        linked_review_pairs=linked_pairs(decisions),
    )
    if out_csv.exists():
        raise FileExistsError(f"refusing to overwrite {out_csv.name}")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case_id", "group_id"], lineterminator="\n")
        w.writeheader()
        w.writerows(grouping.to_rows())
    return grouping


def grouping_audit(grouping: PatientGrouping, decisions: Mapping[str, str]) -> dict[str, Any]:
    return {**grouping.audit(), "decisions": dict(decisions)}
