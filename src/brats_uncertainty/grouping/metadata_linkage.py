"""Gate B8 under amendment v1.0-A4: authoritative metadata linkage (no image similarity).

The procedure is pre-specified in ``configs/grouping/b8_metadata_linkage_v1.0-A4.yaml``.

**SAME_PATIENT links** are taken over all development pairs, from authoritative identity
evidence only:
- M1: the protocol's verified groups;
- M2: the same UCSF-PDGM base patient number (TCIA follow-up records ``_FU<k>d``);
- M3: the same real TCIA patient ID within the same TCIA collection.

**Residual screen.** The B7 flagged pairs that are not linked are decided by:
- M4: different UCSF base numbers → DIFFERENT;
- M5: different real TCIA IDs in the same collection → DIFFERENT;
- M6: UCSF Sex or IDH discordance → DIFFERENT;
- M7: different contributing site → DIFFERENT;
- M8: anything else → UNRESOLVED.

UNRESOLVED is linked (conservative). No anatomy, intensity or Dice value is used.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

SAME, DIFFERENT, UNRESOLVED = "SAME_PATIENT", "DIFFERENT_PATIENT", "UNRESOLVED"
LINKED = frozenset({SAME, UNRESOLVED})
PLACEHOLDER = "new-not-previously-in-TCIA"
UCSF_COLLECTION = "UCSF-PDGM"
_UCSF_ID = re.compile(r"^UCSF-PDGM-0*(\d+)(?:_FU\d+d)?$", re.IGNORECASE)
DECISION_FIELDS = ("case_a", "case_b", "decision", "rule")


@dataclass(frozen=True)
class Identity:
    site: str
    collection: str
    tcia_id: str | None  # real TCIA patient ID (None for blank / placeholder)
    ucsf_base: int | None
    sex: str | None
    idh: str | None


def _idh(value: str) -> str | None:
    v = value.strip().lower()
    if v == "wildtype":
        return "wildtype"
    if v and v != "unknown" and ("mut" in v or "p.r" in v or "p.arg" in v):
        return "mutant"
    return None


def build_identities(
    crosswalk: Iterable[Mapping[str, Any]],
    ucsf_rows: Iterable[Mapping[str, Any]],
    *,
    case_col: str = "BraTS2021 ID",
    site_col: str = "Site ID",
    collection_col: str = "Data Collection (as on TCIA+additional)",
    tcia_col: str = "PatientID on TCIA Radiology Portal",
) -> dict[str, Identity]:
    """Identity keys per training case from the two authoritative TCIA metadata files."""
    ucsf: dict[str, Mapping[str, Any]] = {}
    for r in ucsf_rows:
        b = str(r.get("BraTS21 ID") or "").strip()
        if b:
            ucsf[b] = r
    out: dict[str, Identity] = {}
    for r in crosswalk:
        case = str(r.get(case_col) or "").strip()
        if not case:
            continue
        site = str(r.get(site_col) or "").strip()
        site = site[:-2] if site.endswith(".0") else site
        collection = str(r.get(collection_col) or "").strip()
        raw = str(r.get(tcia_col) or "").strip()
        tcia = None if not raw or raw == PLACEHOLDER or raw.lower() == "none" else raw
        base: int | None = None
        u = ucsf.get(case)
        if u is not None and (m := _UCSF_ID.match(str(u.get("ID") or "").strip())):
            base = int(m.group(1))
        elif collection == UCSF_COLLECTION and tcia and tcia.isdigit():
            base = int(tcia)
        out[case] = Identity(
            site=site,
            collection=collection,
            tcia_id=tcia,
            ucsf_base=base,
            sex=(str(u.get("Sex") or "").strip() or None) if u else None,
            idh=_idh(str(u.get("IDH") or "")) if u else None,
        )
    return out


def _key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def metadata_same_links(
    development: Sequence[str],
    ids: Mapping[str, Identity],
    verified_groups: Mapping[str, Sequence[str]],
) -> dict[tuple[str, str], str]:
    """M1-M3 over all development pairs: chains within each identity key."""
    links: dict[tuple[str, str], str] = {}
    dev = set(development)
    for members in verified_groups.values():
        ms = sorted(m for m in members if m in dev)
        for m in ms[1:]:
            links.setdefault(_key(ms[0], m), "M1")
    by_ucsf: dict[int, list[str]] = {}
    by_tcia: dict[tuple[str, str], list[str]] = {}
    for c in sorted(dev):
        i = ids[c]
        if i.ucsf_base is not None:
            by_ucsf.setdefault(i.ucsf_base, []).append(c)
        if i.tcia_id is not None:
            by_tcia.setdefault((i.collection, i.tcia_id), []).append(c)
    for ms in by_ucsf.values():
        for a in ms:
            for b in ms:
                if a < b:
                    links.setdefault(_key(a, b), "M2")
    for ms2 in by_tcia.values():
        for a in ms2:
            for b in ms2:
                if a < b:
                    links.setdefault(_key(a, b), "M3")
    return links


def residual_rule(a: str, b: str, ids: Mapping[str, Identity]) -> tuple[str, str]:
    ia, ib = ids[a], ids[b]
    if ia.ucsf_base is not None and ib.ucsf_base is not None and ia.ucsf_base != ib.ucsf_base:
        return DIFFERENT, "M4"
    if (
        ia.tcia_id is not None
        and ib.tcia_id is not None
        and ia.collection == ib.collection
        and ia.tcia_id != ib.tcia_id
    ):
        return DIFFERENT, "M5"
    if (ia.sex and ib.sex and ia.sex != ib.sex) or (ia.idh and ib.idh and ia.idh != ib.idh):
        return DIFFERENT, "M6"
    if ia.site != ib.site:
        return DIFFERENT, "M7"
    return UNRESOLVED, "M8"


@dataclass
class LinkageResult:
    decisions: dict[tuple[str, str], tuple[str, str]]  # pair -> (decision, rule)
    groups: list[list[str]]
    acceptance: dict[str, bool]

    @property
    def accepted(self) -> bool:
        return all(self.acceptance.values())


def adjudicate(
    development: Sequence[str],
    flagged: Iterable[tuple[str, str]],
    ids: Mapping[str, Identity],
    verified_groups: Mapping[str, Sequence[str]],
    *,
    max_group_size: int = 8,
) -> LinkageResult:
    same = metadata_same_links(development, ids, verified_groups)
    decisions: dict[tuple[str, str], tuple[str, str]] = {k: (SAME, r) for k, r in same.items()}
    flagged_keys = sorted({_key(a, b) for a, b in flagged})
    for k in flagged_keys:
        if k not in decisions:
            decisions[k] = residual_rule(k[0], k[1], ids)
    parent = {c: c for c in development}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), (d, _r) in sorted(decisions.items()):
        if d in LINKED:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    comp: dict[str, list[str]] = {}
    for c in development:
        comp.setdefault(find(c), []).append(c)
    groups = sorted((sorted(g) for g in comp.values()), key=lambda g: (-len(g), g[0]))
    root = {c: find(c) for c in development}
    acceptance = {
        "max_group_size": max((len(g) for g in groups), default=0) <= max_group_size,
        "verified_groups_intact": all(
            len({root[m] for m in ms}) == 1 for ms in verified_groups.values()
        ),
        "no_site1_in_development": all(ids[c].site != "1" for c in development),
        "every_flagged_pair_decided": all(k in decisions for k in flagged_keys),
        "metadata_different_never_linked": all(
            root[a] != root[b] for (a, b), (_d, r) in decisions.items() if r in ("M4", "M5", "M6")
        ),
    }
    return LinkageResult(decisions, groups, acceptance)


def summary(res: LinkageResult, n_development: int) -> dict[str, Any]:
    sizes = sorted((len(g) for g in res.groups), reverse=True)
    q95 = sizes[int(0.05 * (len(sizes) - 1))] if sizes else 0
    return {
        "n_development": n_development,
        "decisions": dict(sorted(Counter(d for d, _ in res.decisions.values()).items())),
        "rules": dict(sorted(Counter(r for _, r in res.decisions.values()).items())),
        "metadata_same_links": sum(1 for _, r in res.decisions.values() if r in ("M1", "M2", "M3")),
        "n_groups": len(sizes),
        "largest_group": sizes[0] if sizes else 0,
        "median_group": sizes[len(sizes) // 2] if sizes else 0,
        "p95_group": q95,
        "singletons": sum(1 for s in sizes if s == 1),
        "group_size_counts": {str(k): v for k, v in sorted(Counter(sizes).items())},
        "acceptance": res.acceptance,
        "accepted": res.accepted,
    }
