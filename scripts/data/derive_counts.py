"""[GATED: B1-B5] B6 — counts from the hashed crosswalk.

Thin wrapper over `brats-uncertainty derive-counts`; see docs/data/DATA_PROVENANCE.md.
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["derive-counts", *sys.argv[1:]]))
