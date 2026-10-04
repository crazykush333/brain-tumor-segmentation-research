"""Prohibited-file, secret and protocol-integrity scan (safe; used in CI)."""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["check-repo", *sys.argv[1:]]))
