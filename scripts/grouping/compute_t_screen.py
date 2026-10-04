"""[GATED: B1-B6] Compute T_screen from the two positive-control pairs only (gate B7).

The value is computed once, before the development similarity distribution is
examined, and written as a validated record. It is never typed by hand.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brats_uncertainty.data.manifest_doc import load_case_manifest
from brats_uncertainty.pipeline import stage_t_screen
from brats_uncertainty.utils.paths import find_repo_root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--data-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    manifest = load_case_manifest(a.manifest)
    rec = stage_t_screen(find_repo_root(), manifest, a.data_root, a.out)
    print(f"T_screen record written to {a.out} (controls: {sorted(rec.control_dice)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
