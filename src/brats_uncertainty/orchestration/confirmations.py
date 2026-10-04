"""Owner confirmations of the implementation choices (docs/reproducibility/REPRODUCIBILITY.md §4).

Each choice the protocol leaves open is fixed in code and "flagged for owner
confirmation before" a named gate. The owner records confirmations in
``docs/research/execution/IMPLEMENTATION_CONFIRMATIONS.yaml``::

    confirmed_by: Ayush Kushwaha
    items:
      5: {confirmed_on: "2026-10-05", decision: CONFIRMED}

The runner checks the items due before a step; it never fills them in. A choice the
owner does not confirm must be changed in code (and re-tested) before that gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brats_uncertainty.utils.io import read_yaml

CONFIRMATIONS_RELPATH = Path("docs/research/execution/IMPLEMENTATION_CONFIRMATIONS.yaml")
# step id -> REPRODUCIBILITY.md §4 item numbers due before it (forward-looking gates)
REQUIRED: dict[str, tuple[int, ...]] = {
    "B2": (16, 17, 20, 21),
    "B6": (18,),
    "B8": (5,),
    "B10": (6,),
    "PILOT": (22, 23),
    "TRAIN": (12, 13),
    "VALIDATION": (24,),
    "C5": (10,),
    "C6": (1, 2, 3, 4, 7, 8, 9, 11, 14, 25, 26, 27, 28),
}


def confirmed_items(repo_root: Path) -> dict[int, dict[str, Any]]:
    path = repo_root / CONFIRMATIONS_RELPATH
    if not path.is_file():
        return {}
    raw = read_yaml(path) or {}
    items = raw.get("items") or {}
    return {
        int(k): v
        for k, v in items.items()
        if isinstance(v, dict) and v.get("decision") == "CONFIRMED" and v.get("confirmed_on")
    }


def missing_confirmations(repo_root: Path, step: str) -> list[int]:
    key = "TRAIN" if step.startswith("TRAIN-") else step
    have = confirmed_items(repo_root)
    return [i for i in REQUIRED.get(key, ()) if i not in have]
