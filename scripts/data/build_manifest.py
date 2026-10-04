"""[GATED: B1-B2] Hash a locally acquired dataset into a manifest (gate B5).

Usage:
  python scripts/data/build_manifest.py --dataset-config configs/dataset/brats2021.yaml \
      --data-root "$BRATS2021_DATA_ROOT" --out <outside-repo>/manifest_brats2021.json
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["build-manifest", *sys.argv[1:]]))
