"""Primary H-W statistic and within-condition Delta-AURC (§2.1, §3, §13).

Delta-AURC_c = AURC_c(U1) - AURC_c(I). Within a condition I is constant, so
AURC_c(I) is the mean ET risk of condition c (in the sample or replicate).
Primary statistic = equal-weight mean of Delta-AURC_c over C4 = {-T1, -T1c,
-T2, -FLAIR}. Delta-AURC_Full is computed alongside as a separate control.
Decision rule (reported, not automated into a claim): H-W supported iff the 95%
CI of the primary statistic lies entirely below 0.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.metrics.selective import aurc
from brats_uncertainty.preprocessing.modalities import C4_NAMES
from brats_uncertainty.statistics.bootstrap import (
    PROTOCOL_REPLICATES,
    PROTOCOL_SEED,
    BootstrapResult,
    GroupIndex,
    group_bootstrap,
)
from brats_uncertainty.statistics.units import UnitTable


def delta_aurc_condition(
    units: UnitTable, idx: NDArray[np.intp], condition: str, score: str = "U1"
) -> float:
    sel = idx[units.condition[idx] == condition]
    if sel.size == 0:
        return float("nan")
    r = units.risk[sel]
    return aurc(units.score(score)[sel], r) - float(r.mean())


def mean_delta_aurc(
    units: UnitTable,
    idx: NDArray[np.intp],
    conditions: Sequence[str] = C4_NAMES,
    score: str = "U1",
) -> float:
    vals = [delta_aurc_condition(units, idx, c, score) for c in conditions]
    return float(np.mean(vals)) if all(np.isfinite(vals)) else float("nan")


@dataclass(frozen=True)
class PrimaryAnalysis:
    mean_c4: BootstrapResult
    per_condition: dict[str, BootstrapResult]

    def ci_entirely_below_zero(self) -> bool:
        return bool(self.mean_c4.ci_high < 0.0)


def run_primary(
    units: UnitTable,
    *,
    score: str = "U1",
    control_conditions: Sequence[str] = ("Full",),
    n_replicates: int = PROTOCOL_REPLICATES,
    seed: int = PROTOCOL_SEED,
) -> PrimaryAnalysis:
    """Mean-over-C4 Delta-AURC with per-condition components (incl. the Full control).

    Each statistic is bootstrapped with the same seed, hence identical group draws.
    """
    groups = GroupIndex(units.group_id)
    main = group_bootstrap(
        lambda i: mean_delta_aurc(units, i, C4_NAMES, score),
        groups,
        n_replicates=n_replicates,
        seed=seed,
    )
    per: dict[str, BootstrapResult] = {}

    def component(condition: str) -> Callable[[NDArray[np.intp]], float]:
        return lambda i: delta_aurc_condition(units, i, condition, score)

    for c in (*C4_NAMES, *control_conditions):
        if np.any(units.condition == c):
            per[c] = group_bootstrap(
                component(c),
                groups,
                n_replicates=n_replicates,
                seed=seed,
            )
    return PrimaryAnalysis(mean_c4=main, per_condition=per)
