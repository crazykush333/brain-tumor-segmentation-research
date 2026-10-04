"""[GATED: B1-B2 (B3) / B1-B3 (B4)] B3/B4 — exact SHA-256 of the crosswalk / UCSF-PDGM metadata.

Thin wrapper over `brats-uncertainty hash-metadata`; see docs/data/DATA_PROVENANCE.md.
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["hash-metadata", *sys.argv[1:]]))
