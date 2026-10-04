"""EXP-001 pilot case selection and the D3/D5 constraint checks (spec §1, gates D3-D5).

Selection (spec §1): N_pilot = 40 development cases (site != 1), fixed seed 101, by
sorted BraTS ID, before and independently of the final split. [Implementation of
"by sorted BraTS ID": the sorted development IDs are permuted with
``numpy.random.default_rng(101)`` and the first 40 are taken, then sorted.]

D3/D5 are checked on the selected IDs before anything runs; D4 (no label-based
scientific metric) is a property of the measurement harness, which never reads
labels for metrics (spec §2 item 9 times metric code on synthetic volumes only).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from brats_uncertainty.errors import ProtocolDeviationError

HOI_SITE_ID = "1"
BRATS2021_PREFIX = "BraTS2021_"


def select_pilot_cases(rows: Sequence[Any], *, n: int, seed: int) -> list[str]:
    pool = sorted(r.case_id for r in rows if str(r.site_id) != HOI_SITE_ID)
    if len(pool) < n:
        raise ProtocolDeviationError(f"development pool has {len(pool)} cases < N_pilot={n}")
    order = np.random.default_rng(seed).permutation(len(pool))
    return sorted(pool[i] for i in order[:n])


def verify_pilot_pool(cases: Sequence[str], rows: Sequence[Any]) -> dict[str, bool]:
    """D3 and D5 on the selected IDs; raises on any violation."""
    site = {r.case_id: str(r.site_id) for r in rows}
    unknown = [c for c in cases if c not in site]
    hoi = [c for c in cases if site.get(c) == HOI_SITE_ID]
    foreign = [c for c in cases if not c.startswith(BRATS2021_PREFIX)]
    if unknown or hoi or foreign or len(set(cases)) != len(cases):
        raise ProtocolDeviationError(
            f"pilot pool violates D3/D5: unknown={unknown[:3]} site1={hoi[:3]} "
            f"non-BraTS2021={foreign[:3]} duplicates={len(cases) - len(set(cases))}"
        )
    return {"D3": True, "D5": True}
