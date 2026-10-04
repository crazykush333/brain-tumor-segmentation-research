"""[GATED: B1-B9] Create the final patient-group split ONCE; run §6.3 assertions (B10-B12)."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from brats_uncertainty.data.crosswalk import parse_rows, read_xlsx_records
from brats_uncertainty.data.manifest_doc import load_case_manifest
from brats_uncertainty.grouping.groups import PatientGrouping
from brats_uncertainty.pipeline import stage_create_split
from brats_uncertainty.utils.io import read_yaml
from brats_uncertainty.utils.paths import find_repo_root


def _grouping(path: Path) -> PatientGrouping:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    groups: dict[str, list[str]] = {}
    for r in rows:
        groups.setdefault(r["group_id"], []).append(r["case_id"])
    return PatientGrouping(
        prefix="DEV",
        case_to_group={r["case_id"]: r["group_id"] for r in rows},
        groups={g: tuple(sorted(m)) for g, m in groups.items()},
        link_sources={},
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crosswalk", required=True, type=Path)
    p.add_argument("--dataset-config", default=Path("configs/dataset/brats2021.yaml"), type=Path)
    p.add_argument("--groups", required=True, type=Path, help="frozen patient_groups_dev.csv")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--data-root", required=True, type=Path)
    p.add_argument("--out-dir", default=Path("splits"), type=Path)
    a = p.parse_args()
    root = find_repo_root()
    cfg = read_yaml(a.dataset_config)["crosswalk"]
    rows = parse_rows(read_xlsx_records(a.crosswalk), cfg["columns"])
    manifest = load_case_manifest(a.manifest)
    labels = {e.case_id: a.data_root / e.label.relpath for e in manifest.entries if e.label}
    res = stage_create_split(root, rows, _grouping(a.groups), labels, a.out_dir)
    print(res.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
