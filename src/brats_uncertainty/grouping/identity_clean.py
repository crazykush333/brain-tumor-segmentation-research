"""Gate B8 under amendment v1.0-A5: identity-clean primary cohort and quarantine.

Specification: ``configs/grouping/b8_identity_clean_v1.0-A5.yaml``.

A development case belongs to the **primary cohort** only if the provider metadata give
it an authoritative identity:
- for UCSF-PDGM cases, the base patient number, from the v5 metadata or the official
  follow-up rename list;
- for other collections, the real TCIA patient ID in its namespace (TCGA-GBM and
  TCGA-LGG share the TCGA barcode namespace).

**Patient groups** are the connected components of identical identity keys and the
protocol's verified groups. Cases without authoritative identity are **quarantined**,
never grouped. No image similarity, Dice value or study outcome is used.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

PLACEHOLDER = "new-not-previously-in-TCIA"
PRIMARY, QUARANTINE = "primary", "quarantine"
_UCSF = re.compile(r"^UCSF-PDGM-0*(\d+)(?:_FU\d+d)?$", re.IGNORECASE)
COHORT_FIELDS = ("case_id", "cohort", "identity_key", "group_id", "site", "collection")


@dataclass(frozen=True)
class CaseIdentity:
    case_id: str
    site: str
    collection: str
    key: str | None  # namespace-qualified authoritative identity, None if unknown


def _site(v: Any) -> str:
    s = str(v if v is not None else "").strip()
    return s[:-2] if s.endswith(".0") else s


def case_identities(
    crosswalk: Iterable[Mapping[str, Any]],
    ucsf_rows: Iterable[Mapping[str, Any]],
    *,
    renamed: Mapping[int, int],
    tcga_collections: Sequence[str],
) -> dict[str, CaseIdentity]:
    """Identity key per training case (Segmentation cohort = Training)."""
    ucsf_base: dict[str, int] = {}
    for r in ucsf_rows:
        b = str(r.get("BraTS21 ID") or "").strip()
        m = _UCSF.match(str(r.get("ID") or "").strip())
        if b and m:
            ucsf_base[b] = int(m.group(1))
    out: dict[str, CaseIdentity] = {}
    for r in crosswalk:
        if str(r.get("Segmentation (Task 1) Cohort") or "") != "Training":
            continue
        case = str(r.get("BraTS2021 ID") or "").strip()
        coll = str(r.get("Data Collection (as on TCIA+additional)") or "").strip()
        pid = str(r.get("PatientID on TCIA Radiology Portal") or "").strip()
        real = pid not in ("", "None", "none", PLACEHOLDER)
        key: str | None = None
        if case in ucsf_base:
            key = f"UCSF:{ucsf_base[case]}"
        elif coll == "UCSF-PDGM" and real and pid.isdigit():
            n = int(pid)
            key = f"UCSF:{renamed.get(n, n)}"
        elif real:
            namespace = "TCGA" if coll in tcga_collections else coll
            key = f"{namespace}:{pid}"
        out[case] = CaseIdentity(case, _site(r.get("Site ID")), coll, key)
    return out


@dataclass
class CohortResult:
    identities: dict[str, CaseIdentity]
    primary: list[str]
    quarantine: list[str]
    groups: list[list[str]]  # primary cohort only
    acceptance: dict[str, bool]

    @property
    def accepted(self) -> bool:
        return all(self.acceptance.values())

    def group_of(self) -> dict[str, str]:
        return {c: f"DEV{i + 1:04d}" for i, g in enumerate(self.groups) for c in g}


def follow_up_pairs(
    ucsf_rows: Iterable[Mapping[str, Any]], development: Iterable[str]
) -> list[tuple[str, str]]:
    """Official follow-up relations whose base and follow-up cases are both development cases."""
    base_case: dict[int, str] = {}
    fu_cases: list[tuple[int, str]] = []
    for r in ucsf_rows:
        b = str(r.get("BraTS21 ID") or "").strip()
        m = _UCSF.match(str(r.get("ID") or "").strip())
        if not (b and m):
            continue
        if "_FU" in str(r.get("ID")).upper():
            fu_cases.append((int(m.group(1)), b))
        else:
            base_case[int(m.group(1))] = b
    dev = set(development)
    return sorted(
        (base_case[n], b)
        for n, b in fu_cases
        if n in base_case and base_case[n] in dev and b in dev
    )


def build_cohort(
    identities: Mapping[str, CaseIdentity],
    development: Sequence[str],
    verified_groups: Mapping[str, Sequence[str]],
    follow_up_pairs: Iterable[tuple[str, str]] = (),
) -> CohortResult:
    dev = sorted(development)
    primary = [c for c in dev if identities[c].key is not None]
    quarantine = [c for c in dev if identities[c].key is None]
    parent = {c: c for c in primary}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_key: dict[str, list[str]] = {}
    for c in primary:
        by_key.setdefault(str(identities[c].key), []).append(c)
    for members in by_key.values():
        for m in members[1:]:
            union(members[0], m)
    vg_ok = True
    for vmembers in verified_groups.values():
        ms = [m for m in vmembers if m in parent]
        vg_ok &= len(ms) == len(vmembers)  # verified groups must be identity-clean
        for m in ms[1:]:
            union(ms[0], m)
    comp: dict[str, list[str]] = {}
    for c in primary:
        comp.setdefault(find(c), []).append(c)
    groups = sorted((sorted(g) for g in comp.values()), key=lambda g: (-len(g), g[0]))
    root = {c: find(c) for c in primary}
    acceptance = {
        "verified_groups_intact": vg_ok
        and all(len({root[m] for m in ms}) == 1 for ms in verified_groups.values()),
        "follow_up_links_intact": all(
            a in root and b in root and root[a] == root[b] for a, b in follow_up_pairs
        ),
        "different_identities_never_grouped": all(
            len({identities[c].key for c in g}) == 1
            or any(set(g) >= set(v) for v in verified_groups.values())
            for g in groups
        ),
        "no_site1_in_development": all(identities[c].site != "1" for c in dev),
        "cohorts_partition_development": sorted(primary + quarantine) == dev
        and not set(primary) & set(quarantine),
    }
    return CohortResult(dict(identities), primary, quarantine, groups, acceptance)


def summary(res: CohortResult, development: Sequence[str]) -> dict[str, Any]:
    sizes = sorted((len(g) for g in res.groups), reverse=True)
    ids = res.identities

    def by(attr: str, cases: Iterable[str]) -> dict[str, int]:
        return dict(sorted(Counter(getattr(ids[c], attr) for c in cases).items()))

    dev_sites = by("site", development)
    prim_sites = by("site", res.primary)
    return {
        "n_development_pool": len(development),
        "n_primary": len(res.primary),
        "n_quarantine": len(res.quarantine),
        "n_patient_groups": len(sizes),
        "n_multi_case_groups": sum(1 for s in sizes if s > 1),
        "n_singletons": sum(1 for s in sizes if s == 1),
        "largest_group": sizes[0] if sizes else 0,
        "group_size_counts": {str(k): v for k, v in sorted(Counter(sizes).items())},
        "multi_case_groups": [g for g in res.groups if len(g) > 1],
        "primary_by_collection": by("collection", res.primary),
        "quarantine_by_collection": by("collection", res.quarantine),
        "development_by_site": dev_sites,
        "primary_by_site": prim_sites,
        "identity_coverage_by_site": {
            s: round(prim_sites.get(s, 0) / n, 4) for s, n in dev_sites.items()
        },
        "sites_absent_from_primary": sorted(s for s in dev_sites if s not in prim_sites),
        "acceptance": res.acceptance,
        "accepted": res.accepted,
    }
