"""Patient-group-level bootstrap (§13, §15).

- 10,000 replicates, seed 12345, 95% percentile CI; BCa as sensitivity.
- Resampling unit = patient group; all units (cases x conditions) of a sampled
  group are kept.
- Two-sided p = 2 * min(P*(delta >= 0), P*(delta <= 0)), capped at 1, reported
  as approximate.
- RNG: ``numpy.random.default_rng(seed)`` (PCG64); per replicate, G group
  indices are drawn with ``Generator.integers(0, G, size=G)``, groups being
  ordered by sorted group ID. [Implementation choice, fixed here and hashed
  into run metadata.]
- Replicates where the statistic is undefined (NaN) are counted and excluded;
  the count is always reported.
- Canonical resamples: the complete (replicates x groups) index matrix is generated once
  by ``canonical_draws`` (``Generator.integers(0, G, size=(R, G))``, identical to drawing
  replicate by replicate) and identified by ``draws_sha256`` (SHA-256 of its int64
  little-endian bytes). The production analysis and the independent verifier use these
  exact resamples; the digest is recorded with every bootstrap result.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm

PROTOCOL_REPLICATES = 10_000
PROTOCOL_SEED = 12_345
PROTOCOL_CI_LEVEL = 0.95

Statistic = Callable[[NDArray[np.intp]], float]


class GroupIndex:
    """Maps patient groups to the unit indices they contain."""

    def __init__(self, group_ids: Sequence[str] | NDArray[np.str_]) -> None:
        gids = np.asarray(group_ids, dtype=str)
        if gids.size == 0:
            raise ValueError("no units")
        self.groups: NDArray[np.str_] = np.unique(gids)  # sorted
        self.members: list[NDArray[np.intp]] = [np.flatnonzero(gids == g) for g in self.groups]
        self.n_units = gids.size

    def __len__(self) -> int:
        return len(self.groups)

    def all_indices(self) -> NDArray[np.intp]:
        return np.arange(self.n_units, dtype=np.intp)

    def resample(self, rng: np.random.Generator) -> NDArray[np.intp]:
        draw = rng.integers(0, len(self.groups), size=len(self.groups))
        return np.concatenate([self.members[g] for g in draw])

    def from_draw(self, draw: NDArray[np.int64]) -> NDArray[np.intp]:
        """Unit indices of one resample (a row of the canonical draw matrix)."""
        return np.concatenate([self.members[g] for g in draw])

    def leave_one_out(self, g: int) -> NDArray[np.intp]:
        return np.concatenate([m for i, m in enumerate(self.members) if i != g])


def canonical_draws(n_groups: int, n_replicates: int, seed: int) -> NDArray[np.int64]:
    """The declared resample index matrix: row b = the groups (sorted order) drawn in b."""
    if n_groups < 1 or n_replicates < 1:
        raise ValueError("n_groups and n_replicates must be >= 1")
    rng = np.random.default_rng(seed)
    return np.asarray(rng.integers(0, n_groups, size=(n_replicates, n_groups)), dtype=np.int64)


def canonical_transfer_draws(
    n_validation_groups: int, n_target_groups: int, n_replicates: int, seed: int
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Independent validation/target resamples from one generator (validation first, per
    replicate), as used by the S7 threshold-transfer bootstrap."""
    rng = np.random.default_rng(seed)
    v = np.empty((n_replicates, n_validation_groups), dtype=np.int64)
    t = np.empty((n_replicates, n_target_groups), dtype=np.int64)
    for b in range(n_replicates):
        v[b] = rng.integers(0, n_validation_groups, size=n_validation_groups)
        t[b] = rng.integers(0, n_target_groups, size=n_target_groups)
    return v, t


def draws_sha256(*draws: NDArray[np.int64]) -> str:
    h = hashlib.sha256()
    for d in draws:
        h.update(np.ascontiguousarray(d, dtype="<i8").tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class BootstrapResult:
    estimate: float
    replicates: NDArray[np.float64]
    ci_low: float
    ci_high: float
    p_value: float
    n_replicates: int
    n_undefined: int
    seed: int
    ci_method: str = "percentile"
    draws_sha256: str = ""

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "estimate": self.estimate,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "p_value_two_sided_approx": self.p_value,
            "n_replicates": self.n_replicates,
            "n_undefined": self.n_undefined,
            "seed": self.seed,
            "ci_method": self.ci_method,
            "draws_sha256": self.draws_sha256,
        }


def two_sided_p(replicates: NDArray[np.float64]) -> float:
    r = replicates[np.isfinite(replicates)]
    if r.size == 0:
        return float("nan")
    return min(1.0, 2.0 * min(float(np.mean(r >= 0.0)), float(np.mean(r <= 0.0))))


def percentile_ci(
    replicates: NDArray[np.float64], level: float = PROTOCOL_CI_LEVEL
) -> tuple[float, float]:
    r = replicates[np.isfinite(replicates)]
    if r.size == 0:
        return float("nan"), float("nan")
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(r, [a, 1.0 - a])
    return float(lo), float(hi)


def bca_ci(
    replicates: NDArray[np.float64],
    estimate: float,
    jackknife: NDArray[np.float64],
    level: float = PROTOCOL_CI_LEVEL,
) -> tuple[float, float]:
    """Bias-corrected and accelerated CI; acceleration from a group jackknife."""
    r = replicates[np.isfinite(replicates)]
    jk = jackknife[np.isfinite(jackknife)]
    if r.size == 0 or jk.size < 2:
        return float("nan"), float("nan")
    prop = np.mean(r < estimate)
    if prop <= 0.0 or prop >= 1.0:
        return float("nan"), float("nan")
    z0 = float(norm.ppf(prop))
    d = jk.mean() - jk
    denom = 6.0 * float(np.sum(d**2)) ** 1.5
    acc = float(np.sum(d**3)) / denom if denom > 0 else 0.0
    alphas = []
    for a in ((1.0 - level) / 2.0, 1.0 - (1.0 - level) / 2.0):
        z = float(norm.ppf(a))
        alphas.append(float(norm.cdf(z0 + (z0 + z) / (1.0 - acc * (z0 + z)))))
    lo, hi = np.quantile(r, alphas)
    return float(lo), float(hi)


def group_bootstrap(
    statistic: Statistic,
    groups: GroupIndex,
    *,
    n_replicates: int = PROTOCOL_REPLICATES,
    seed: int = PROTOCOL_SEED,
    level: float = PROTOCOL_CI_LEVEL,
) -> BootstrapResult:
    """Percentile bootstrap of ``statistic(unit_indices)`` over patient groups."""
    if n_replicates < 1:
        raise ValueError("n_replicates must be >= 1")
    draws = canonical_draws(len(groups), n_replicates, seed)
    estimate = float(statistic(groups.all_indices()))
    reps = np.empty(n_replicates, dtype=np.float64)
    for b in range(n_replicates):
        reps[b] = statistic(groups.from_draw(draws[b]))
    lo, hi = percentile_ci(reps, level)
    return BootstrapResult(
        estimate=estimate,
        replicates=reps,
        ci_low=lo,
        ci_high=hi,
        p_value=two_sided_p(reps),
        n_replicates=n_replicates,
        n_undefined=int(np.sum(~np.isfinite(reps))),
        seed=seed,
        draws_sha256=draws_sha256(draws),
    )


def group_jackknife(statistic: Statistic, groups: GroupIndex) -> NDArray[np.float64]:
    return np.array([statistic(groups.leave_one_out(g)) for g in range(len(groups))])


def bca_from_result(
    result: BootstrapResult,
    statistic: Statistic,
    groups: GroupIndex,
    level: float = PROTOCOL_CI_LEVEL,
) -> tuple[float, float]:
    """BCa sensitivity interval for an existing bootstrap result."""
    return bca_ci(result.replicates, result.estimate, group_jackknife(statistic, groups), level)
