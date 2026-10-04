"""[GATED: B1-B6] Exhaustive pairwise WT-label screen of development cases (gate B7).

Outputs flagged pair IDs only (no similarity distribution) for manual review (B8).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brats_uncertainty.data.manifest_doc import load_case_manifest
from brats_uncertainty.pipeline import stage_screen
from brats_uncertainty.utils.paths import find_repo_root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--data-root", required=True, type=Path)
    p.add_argument("--t-screen", required=True, type=Path, help="record from compute_t_screen.py")
    p.add_argument("--development-ids", required=True, type=Path, help="text file, one ID per line")
    p.add_argument("--out-dir", required=True, type=Path)
    a = p.parse_args()
    ids = [
        x.strip() for x in a.development_ids.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    res = stage_screen(
        find_repo_root(),
        load_case_manifest(a.manifest),
        a.data_root,
        a.t_screen,
        ids,
        a.out_dir,
    )
    print(f"compared {res.n_pairs_compared} pairs; flagged {len(res.flagged)} for review")
    return 0


if __name__ == "__main__":
    sys.exit(main())
