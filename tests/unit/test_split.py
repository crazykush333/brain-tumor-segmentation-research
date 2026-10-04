from __future__ import annotations

import numpy as np
import pytest

from brats_uncertainty.errors import ProtocolDeviationError
from brats_uncertainty.splitting.split import (
    PROTOCOL_SPLIT_SEED,
    GroupFeatures,
    assert_split,
    group_features,
    largest_remainder,
    stratified_group_split,
)


def _synthetic_groups(n: int = 120, seed: int = 0) -> list[GroupFeatures]:
    rng = np.random.default_rng(seed)
    groups = {
        f"SYN-G{i:03d}": tuple(f"SYN-{i:03d}-{k}" for k in range(1 + (i % 7 == 0)))
        for i in range(n)
    }
    cases = [c for m in groups.values() for c in m]
    et = {c: bool(rng.random() < 0.9) for c in cases}
    wt = {c: float(rng.lognormal(3.5, 0.5)) for c in cases}
    return group_features(groups, et, wt)


def test_largest_remainder() -> None:
    assert largest_remainder(10, (0.7, 0.1, 0.2)) == [7, 1, 2]
    assert sum(largest_remainder(7, (0.7, 0.1, 0.2))) == 7
    assert largest_remainder(1, (0.7, 0.1, 0.2)) == [1, 0, 0]


def test_split_deterministic_and_groups_intact() -> None:
    feats = _synthetic_groups()
    a = stratified_group_split(feats)
    b = stratified_group_split(list(reversed(feats)))
    assert a.assignments == b.assignments
    assert a.hashes() == b.hashes()
    for f in feats:
        assert len({a.assignments[c] for c in f.members}) == 1
    counts = a.counts()
    total_groups = sum(v["groups"] for v in counts.values())
    assert total_groups == len(feats)
    assert abs(counts["train"]["groups"] / total_groups - 0.7) < 0.05
    assert abs(counts["internal_test"]["groups"] / total_groups - 0.2) < 0.05


def test_split_rejects_non_protocol_seed() -> None:
    with pytest.raises(ProtocolDeviationError):
        stratified_group_split(_synthetic_groups(), seed=PROTOCOL_SPLIT_SEED + 1)
    with pytest.raises(ProtocolDeviationError):
        stratified_group_split(_synthetic_groups(), proportions=(0.8, 0.1, 0.1))


def test_split_assertions() -> None:
    feats = _synthetic_groups(30)
    res = stratified_group_split(feats)
    sites = {c: "18" for c in res.assignments}
    n = len(res.assignments)
    assert_split(res, site_of_case=sites, hoi_site_id="1", expected_development_count=n)
    with pytest.raises(ProtocolDeviationError, match="development count"):
        assert_split(res, site_of_case=sites, hoi_site_id="1", expected_development_count=n + 1)
    bad_sites = dict(sites)
    bad_sites[next(iter(res.assignments))] = "1"
    with pytest.raises(ProtocolDeviationError, match="site-1"):
        assert_split(res, site_of_case=bad_sites, hoi_site_id="1", expected_development_count=n)
    # a verified group split across partitions must fail
    parts = {}
    for c, p in res.assignments.items():
        parts.setdefault(p, c)
    a, b = parts["train"], parts["internal_test"]
    with pytest.raises(ProtocolDeviationError, match="verified"):
        assert_split(
            res,
            site_of_case=sites,
            hoi_site_id="1",
            expected_development_count=n,
            verified_groups={"X": (a, b)},
        )


def test_split_csv_contains_ids_only() -> None:
    res = stratified_group_split(_synthetic_groups(20))
    header = res.csv_bytes().decode().splitlines()[0]
    assert header == "case_id,group_id,partition"
