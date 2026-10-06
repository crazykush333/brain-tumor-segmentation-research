"""Independent re-implementation of the v1.0-A5 identity-clean cohort, for verification.

This module does not import ``brats_uncertainty.grouping``. It re-derives identities
from the raw provider rows, assigns the primary and quarantine cohorts, and builds
patient groups by breadth-first search over shared identity keys and the verified
groups. ``reconcile`` then requires exact agreement with the production output.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _base(ucsf_id: str) -> int | None:
    s = ucsf_id.strip().upper()
    if not s.startswith("UCSF-PDGM-"):
        return None
    num = s[len("UCSF-PDGM-") :].split("_FU")[0]
    return int(num) if num.isdigit() else None


def identity_keys(
    crosswalk: Iterable[Mapping[str, Any]],
    ucsf_rows: Iterable[Mapping[str, Any]],
    renamed: Mapping[int, int],
    tcga_collections: Sequence[str],
) -> dict[str, tuple[str, str, str | None]]:
    """case -> (site, collection, key or None)."""
    from_meta = {
        str(r.get("BraTS21 ID")).strip(): _base(str(r.get("ID") or ""))
        for r in ucsf_rows
        if str(r.get("BraTS21 ID") or "").strip()
    }
    out: dict[str, tuple[str, str, str | None]] = {}
    for r in crosswalk:
        if r.get("Segmentation (Task 1) Cohort") != "Training":
            continue
        case = str(r.get("BraTS2021 ID")).strip()
        site_raw = r.get("Site ID")
        site = str(int(float(site_raw))) if site_raw not in (None, "") else ""
        coll = str(r.get("Data Collection (as on TCIA+additional)") or "").strip()
        pid = str(r.get("PatientID on TCIA Radiology Portal") or "").strip()
        key: str | None
        if from_meta.get(case) is not None:
            key = "UCSF:" + str(from_meta[case])
        elif pid in ("", "None", "none", "new-not-previously-in-TCIA"):
            key = None
        elif coll == "UCSF-PDGM" and pid.isdigit():
            key = "UCSF:" + str(renamed.get(int(pid), int(pid)))
        else:
            key = ("TCGA" if coll in tcga_collections else coll) + ":" + pid
        out[case] = (site, coll, key)
    return out


def cohort_and_groups(
    ids: Mapping[str, tuple[str, str, str | None]],
    development: Sequence[str],
    verified: Mapping[str, Sequence[str]],
) -> tuple[set[str], set[str], list[set[str]]]:
    primary = {c for c in development if ids[c][2] is not None}
    quarantine = set(development) - primary
    adj: dict[str, set[str]] = {c: set() for c in primary}
    by_key: dict[str, list[str]] = {}
    for c in primary:
        by_key.setdefault(str(ids[c][2]), []).append(c)
    for members in [*by_key.values(), *verified.values()]:
        ms = [m for m in members if m in adj]
        for a in ms:
            adj[a].update(x for x in ms if x != a)
    seen: set[str] = set()
    groups: list[set[str]] = []
    for c in sorted(primary):
        if c in seen:
            continue
        comp, q = {c}, deque([c])
        seen.add(c)
        while q:
            for n in adj[q.popleft()]:
                if n not in seen:
                    seen.add(n)
                    comp.add(n)
                    q.append(n)
        groups.append(comp)
    return primary, quarantine, groups


def reconcile(
    prod_primary: Sequence[str],
    prod_quarantine: Sequence[str],
    prod_groups: Sequence[Sequence[str]],
    ind_primary: set[str],
    ind_quarantine: set[str],
    ind_groups: Sequence[set[str]],
) -> dict[str, Any]:
    checks = {
        "primary_identical": set(prod_primary) == ind_primary,
        "quarantine_identical": set(prod_quarantine) == ind_quarantine,
        "groups_identical": sorted(sorted(g) for g in prod_groups)
        == sorted(sorted(g) for g in ind_groups),
    }
    return {
        "status": "VERIFIED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "n_primary": [len(prod_primary), len(ind_primary)],
        "n_quarantine": [len(prod_quarantine), len(ind_quarantine)],
        "n_groups": [len(prod_groups), len(ind_groups)],
    }
