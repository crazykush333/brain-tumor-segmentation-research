"""Export website/data/*.json from docs/project_status.yaml, configs and results.

Usage: python scripts/reporting/export_site_data.py [--check]
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["export-site-data", *sys.argv[1:]]))
