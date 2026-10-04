"""Transitive patient grouping (§6.2 step 5) and the grouping audit record.

Links = verified groups A/B + shared real TCIA IDs + SAME_PATIENT/UNRESOLVED
pairs. Groups are the connected components (union-find). Group IDs are
deterministic: components are ordered by their smallest case ID and numbered
``<prefix>-0001`` ...
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from brats_uncertainty.errors import DataValidationError
from brats_uncertainty.utils.hashing import sha256_json


class UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent: dict[str, str] = {i: i for i in items}

    def find(self, x: str) -> str:
        if x not in self.parent:
            raise DataValidationError(f"unknown case {x!r} in link")
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb))
            self.parent[hi] = lo

    def components(self) -> list[list[str]]:
        comps: dict[str, list[str]] = {}
        for x in self.parent:
            comps.setdefault(self.find(x), []).append(x)
        return sorted((sorted(c) for c in comps.values()), key=lambda c: c[0])


@dataclass(frozen=True)
class PatientGrouping:
    prefix: str
    case_to_group: dict[str, str]
    groups: dict[str, tuple[str, ...]]
    link_sources: dict[str, list[list[str]]]

    @property
    def sha256(self) -> str:
        return sha256_json({"groups": {k: list(v) for k, v in self.groups.items()}})

    def to_rows(self) -> list[dict[str, str]]:
        return [{"case_id": c, "group_id": g} for c, g in sorted(self.case_to_group.items())]

    def audit(self) -> dict[str, Any]:
        sizes = [len(v) for v in self.groups.values()]
        return {
            "prefix": self.prefix,
            "n_cases": len(self.case_to_group),
            "n_groups": len(self.groups),
            "n_multi_case_groups": sum(1 for s in sizes if s > 1),
            "max_group_size": max(sizes) if sizes else 0,
            "links": {k: len(v) for k, v in self.link_sources.items()},
            "grouping_sha256": self.sha256,
        }


def build_groups(
    case_ids: Sequence[str],
    *,
    prefix: str,
    verified_groups: Mapping[str, Sequence[str]],
    shared_tcia_groups: Sequence[Sequence[str]],
    linked_review_pairs: Sequence[tuple[str, str]],
) -> PatientGrouping:
    ids = list(case_ids)
    if len(ids) != len(set(ids)):
        raise DataValidationError("duplicate case IDs")
    uf = UnionFind(ids)
    sources: dict[str, list[list[str]]] = {"verified": [], "shared_tcia_id": [], "review": []}
    for members in verified_groups.values():
        present = [m for m in members if m in uf.parent]
        if present and len(present) != len(members):
            raise DataValidationError(
                f"verified group only partly present in cohort: {list(members)}"
            )
        for m in present[1:]:
            uf.union(present[0], m)
        if present:
            sources["verified"].append(sorted(present))
    for members in shared_tcia_groups:
        for m in members[1:]:
            uf.union(members[0], m)
        sources["shared_tcia_id"].append(sorted(members))
    for a, b in linked_review_pairs:
        uf.union(a, b)
        sources["review"].append(sorted((a, b)))
    comps = uf.components()
    width = max(4, len(str(len(comps))))
    groups = {f"{prefix}-{i + 1:0{width}d}": tuple(c) for i, c in enumerate(comps)}
    case_to_group = {c: g for g, members in groups.items() for c in members}
    return PatientGrouping(
        prefix=prefix, case_to_group=case_to_group, groups=groups, link_sources=sources
    )
