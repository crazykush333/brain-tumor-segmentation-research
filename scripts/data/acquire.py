"""B2 acquisition: dry run by default; real runs GATED (B1 PASSED + B2 AUTHORIZED).

Thin wrapper over `brats-uncertainty acquire`; see docs/data/DATA_PROVENANCE.md.
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["acquire", *sys.argv[1:]]))
