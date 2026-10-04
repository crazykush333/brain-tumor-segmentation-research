"""[GATED: B1-B2] integrity audit of acquired data.

Thin wrapper over `brats-uncertainty validate-data`; see docs/data/DATA_PROVENANCE.md.
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["validate-data", *sys.argv[1:]]))
