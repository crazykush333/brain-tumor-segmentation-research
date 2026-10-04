"""Stratified patient-group split with the §6.3 assertions.

Frozen by the protocol: unit = patient group; proportions 70/10/20
(train/validation/internal_test); seed 20260927; strata = (ET present in any
member vs absent in all) x (tertile of mean member WT volume), labels only.

Fixed algorithm (implementation of §6.3; documented in
docs/reproducibility/REPRODUCIBILITY.md):
1. Group-level features: ``et_any`` and ``wt_mean`` (mL) over members.
2. Tertile cut points = ``numpy.quantile(wt_mean over all groups, [1/3, 2/3])``
   (default linear method); tertile = 0 if v <= q1, 1 if v <= q2, else 2.
3. Strata are processed in sorted order of (et_any, tertile). Within a stratum,
   group IDs are sorted, then permuted with one ``numpy.random.default_rng(20260927)``
   generator shared across strata.
4. Per stratum, counts are allocated by largest remainder of n * (0.7, 0.1, 0.2);
   remainder ties go to train, then validation, then internal_test.
5. The first n_train permuted groups -> train, the next n_val -> validation,
   the rest -> internal_test.

Assertions (SR3 stops training on failure): no site-1 case in development;
development case count == 740; every patient group lies in exactly one
partition; every development case is assigned exactly once.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.utils.hashing import sha256_bytes

PARTITIONS = ("train", "validation", "internal_test")
PROTOCOL_PROPORTIONS = (0.70, 0.10, 0.20)
PROTOCOL_SPLIT_SEED = 20260927


@dataclass(frozen=True)
class GroupFeatures:
    group_id: str
    members: tuple[str, ...]
    et_any: bool
    wt_mean_ml: float


def group_features(
    groups: Mapping[str, tuple[str, ...]],
    et_present: Mapping[str, bool],
    wt_volume_ml: Mapping[str, float],
) -> list[GroupFeatures]:
    out = []
    for gid in sorted(groups):
        members = tuple(sorted(groups[gid]))
        out.append(
            GroupFeatures(
                group_id=gid,
                members=members,
                et_any=any(bool(et_present[c]) for c in members),
                wt_mean_ml=float(np.mean([wt_volume_ml[c] for c in members])),
            )
        )
    return out


def largest_remainder(n: int, proportions: tuple[float, ...]) -> list[int]:
    raw = [n * p for p in proportions]
    base = [int(np.floor(x)) for x in raw]
    rem = n - sum(base)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:rem]:
        base[i] += 1
    return base


@dataclass(frozen=True)
class SplitResult:
    assignments: dict[str, str]  # case_id -> partition
    case_to_group: dict[str, str]
    seed: int
    strata_counts: dict[str, dict[str, int]]
    tertile_cuts: tuple[float, float]

    def csv_bytes(self, partition: str | None = None) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["case_id", "group_id", "partition"])
        for c in sorted(self.assignments):
            if partition is None or self.assignments[c] == partition:
                w.writerow([c, self.case_to_group[c], self.assignments[c]])
        return buf.getvalue().encode("utf-8")

    def hashes(self) -> dict[str, str]:
        h = {"all": sha256_bytes(self.csv_bytes())}
        h.update({p: sha256_bytes(self.csv_bytes(p)) for p in PARTITIONS})
        return h

    def counts(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for p in PARTITIONS:
            cases = [c for c, q in self.assignments.items() if q == p]
            out[p] = {"cases": len(cases), "groups": len({self.case_to_group[c] for c in cases})}
        return out

    def summary(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "counts": self.counts(),
            "strata_counts": self.strata_counts,
            "tertile_cuts_ml": list(self.tertile_cuts),
            "sha256": self.hashes(),
        }


def stratified_group_split(
    features: list[GroupFeatures],
    *,
    seed: int = PROTOCOL_SPLIT_SEED,
    proportions: tuple[float, ...] = PROTOCOL_PROPORTIONS,
) -> SplitResult:
    if seed != PROTOCOL_SPLIT_SEED or tuple(proportions) != PROTOCOL_PROPORTIONS:
        raise ProtocolDeviationError("split seed and proportions are fixed by protocol §6.3")
    if not features:
        raise ValueError("no groups to split")
    vols = np.array([f.wt_mean_ml for f in features])
    q1, q2 = (float(x) for x in np.quantile(vols, [1 / 3, 2 / 3]))

    def tertile(v: float) -> int:
        return 0 if v <= q1 else (1 if v <= q2 else 2)

    strata: dict[tuple[int, int], list[GroupFeatures]] = {}
    for f in features:
        strata.setdefault((int(f.et_any), tertile(f.wt_mean_ml)), []).append(f)
    rng = np.random.default_rng(seed)
    assignments: dict[str, str] = {}
    case_to_group: dict[str, str] = {}
    strata_counts: dict[str, dict[str, int]] = {}
    for key in sorted(strata):
        members = sorted(strata[key], key=lambda f: f.group_id)
        perm = rng.permutation(len(members))
        n_tr, n_va, n_te = largest_remainder(len(members), proportions)
        labels = ["train"] * n_tr + ["validation"] * n_va + ["internal_test"] * n_te
        strata_counts[f"et{key[0]}_t{key[1]}"] = {
            "train": n_tr,
            "validation": n_va,
            "internal_test": n_te,
        }
        for pos, idx in enumerate(perm):
            g = members[int(idx)]
            for c in g.members:
                if c in assignments:
                    raise ProtocolDeviationError(f"case {c} appears in more than one group")
                assignments[c] = labels[pos]
                case_to_group[c] = g.group_id
    return SplitResult(
        assignments=assignments,
        case_to_group=case_to_group,
        seed=seed,
        strata_counts=strata_counts,
        tertile_cuts=(q1, q2),
    )


def assert_split(
    result: SplitResult,
    *,
    site_of_case: Mapping[str, str],
    hoi_site_id: str,
    expected_development_count: int,
    verified_groups: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    """The §6.3 split-script assertions. Any failure -> stop, do not train (SR3)."""
    site1 = sorted(c for c in result.assignments if site_of_case.get(c) == hoi_site_id)
    if site1:
        raise ProtocolDeviationError(f"site-{hoi_site_id} cases in development: {site1[:5]}")
    unknown = sorted(c for c in result.assignments if c not in site_of_case)
    if unknown:
        raise ProtocolDeviationError(f"cases without a crosswalk site: {unknown[:5]}")
    if len(result.assignments) != expected_development_count:
        raise ProtocolDeviationError(
            f"development count {len(result.assignments)} != {expected_development_count}"
        )
    partition_of_group: dict[str, set[str]] = {}
    for c, p in result.assignments.items():
        partition_of_group.setdefault(result.case_to_group[c], set()).add(p)
    crossing = sorted(g for g, ps in partition_of_group.items() if len(ps) > 1)
    if crossing:
        raise ProtocolDeviationError(f"patient groups spanning partitions: {crossing[:5]}")
    for name, members in (verified_groups or {}).items():
        parts = {result.assignments.get(c) for c in members}
        if None in parts or len(parts) != 1:
            raise ProtocolDeviationError(
                f"verified same-patient group {name} is not within one partition"
            )
