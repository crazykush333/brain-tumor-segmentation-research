"""Independent re-implementation of the v1.0-A4 metadata linkage, for verification.

This module does not import ``brats_uncertainty.grouping``. It parses the raw rows
itself, applies the rule list in its own code and finds connected components by
breadth-first search instead of union-find. ``reconcile`` compares the result with the
production output.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

_FU = re.compile(r"UCSF-PDGM-(\d+)(_FU\d+d)?", re.IGNORECASE)


def _norm_site(v: Any) -> str:
    s = str(v if v is not None else "").strip()
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else s
    except ValueError:
        return s


def identities(
    crosswalk: Iterable[Mapping[str, Any]], ucsf_rows: Iterable[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    ucsf_by_case = {
        str(r.get("BraTS21 ID")).strip(): r
        for r in ucsf_rows
        if str(r.get("BraTS21 ID") or "").strip()
    }
    out: dict[str, dict[str, Any]] = {}
    for r in crosswalk:
        case = str(r.get("BraTS2021 ID") or "").strip()
        if not case:
            continue
        coll = str(r.get("Data Collection (as on TCIA+additional)") or "").strip()
        pid = str(r.get("PatientID on TCIA Radiology Portal") or "").strip()
        real = pid not in ("", "None", "none", "new-not-previously-in-TCIA")
        u = ucsf_by_case.get(case)
        base = None
        if u is not None:
            m = _FU.fullmatch(str(u.get("ID") or "").strip())
            base = int(m.group(1)) if m else None
        if base is None and coll == "UCSF-PDGM" and real and pid.isdigit():
            base = int(pid)
        idh_raw = str((u or {}).get("IDH") or "").strip().lower()
        idh = (
            "wildtype"
            if idh_raw == "wildtype"
            else (
                "mutant"
                if idh_raw not in ("", "unknown")
                and ("mut" in idh_raw or "p.r" in idh_raw or "p.arg" in idh_raw)
                else None
            )
        )
        out[case] = {
            "site": _norm_site(r.get("Site ID")),
            "coll": coll,
            "pid": pid if real else None,
            "base": base,
            "sex": (str(u.get("Sex") or "").strip() or None) if u else None,
            "idh": idh if u else None,
        }
    return out


def decide(
    development: Sequence[str],
    flagged: Iterable[tuple[str, str]],
    ids: Mapping[str, Mapping[str, Any]],
    verified: Mapping[str, Sequence[str]],
) -> dict[frozenset[str], str]:
    """frozenset(pair) -> decision, independently."""
    dev = sorted(development)
    out: dict[frozenset[str], str] = {}
    for members in verified.values():
        ms = [m for m in members if m in set(dev)]
        for i, a in enumerate(ms):
            for b in ms[i + 1 :]:
                out[frozenset((a, b))] = "SAME_PATIENT"
    for i, a in enumerate(dev):
        for b in dev[i + 1 :]:
            x, y = ids[a], ids[b]
            same_base = x["base"] is not None and x["base"] == y["base"]
            same_pid = x["pid"] is not None and x["pid"] == y["pid"] and x["coll"] == y["coll"]
            if same_base or same_pid:
                out[frozenset((a, b))] = "SAME_PATIENT"
    for a, b in flagged:
        k = frozenset((a, b))
        if k in out:
            continue
        x, y = ids[a], ids[b]
        evidence_against_identity = (
            (x["base"] is not None and y["base"] is not None and x["base"] != y["base"]),
            bool(x["pid"] and y["pid"] and x["coll"] == y["coll"] and x["pid"] != y["pid"]),
            bool(x["sex"] and y["sex"] and x["sex"] != y["sex"]),
            bool(x["idh"] and y["idh"] and x["idh"] != y["idh"]),
            x["site"] != y["site"],
        )
        out[k] = "DIFFERENT_PATIENT" if any(evidence_against_identity) else "UNRESOLVED"
    return out


def components(
    development: Sequence[str], decisions: Mapping[frozenset[str], str]
) -> list[set[str]]:
    adj: dict[str, set[str]] = {c: set() for c in development}
    for k, d in decisions.items():
        if d in ("SAME_PATIENT", "UNRESOLVED"):
            a, b = sorted(k)
            adj[a].add(b)
            adj[b].add(a)
    seen: set[str] = set()
    comps: list[set[str]] = []
    for c in sorted(development):
        if c in seen:
            continue
        q, comp = deque([c]), {c}
        seen.add(c)
        while q:
            for n in adj[q.popleft()]:
                if n not in seen:
                    seen.add(n)
                    comp.add(n)
                    q.append(n)
        comps.append(comp)
    return comps


def reconcile(
    production_decisions: Mapping[tuple[str, str], tuple[str, str]],
    production_groups: Sequence[Sequence[str]],
    independent_decisions: Mapping[frozenset[str], str],
    independent_groups: Sequence[set[str]],
) -> dict[str, Any]:
    prod = {frozenset(k): d for k, (d, _r) in production_decisions.items()}
    diff = sorted(
        tuple(sorted(k))
        for k in set(prod) | set(independent_decisions)
        if prod.get(k) != independent_decisions.get(k)
    )
    pg = sorted(sorted(g) for g in production_groups)
    ig = sorted(sorted(g) for g in independent_groups)
    return {
        "decisions_identical": not diff,
        "n_decision_differences": len(diff),
        "first_differences": [list(d) for d in diff[:5]],
        "groups_identical": pg == ig,
        "n_groups_production": len(pg),
        "n_groups_independent": len(ig),
    }
