"""[GATED: B1-B8] Freeze patient groups from verified groups, TCIA IDs and reviews (gate B9)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brats_uncertainty.data.crosswalk import parse_rows, read_xlsx_records
from brats_uncertainty.pipeline import stage_freeze_groups
from brats_uncertainty.protocol import load_protocol
from brats_uncertainty.utils.io import read_yaml
from brats_uncertainty.utils.paths import find_repo_root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--crosswalk", required=True, type=Path, help="local licensed file; not committed"
    )
    p.add_argument("--dataset-config", default=Path("configs/dataset/brats2021.yaml"), type=Path)
    p.add_argument("--flagged", required=True, type=Path)
    p.add_argument("--reviews", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    a = p.parse_args()
    root = find_repo_root()
    cfg = read_yaml(a.dataset_config)["crosswalk"]
    rows = parse_rows(read_xlsx_records(a.crosswalk), cfg["columns"])
    hoi = str(load_protocol(root).raw["cohorts"]["hoi_site_id"])
    development = [r for r in rows if r.site_id != hoi]
    g = stage_freeze_groups(root, development, a.flagged, a.reviews, a.out_dir)
    print(g.audit())
    return 0


if __name__ == "__main__":
    sys.exit(main())
