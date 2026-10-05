"""Verification statuses, checks and stages."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

PASS = "PASS"
PASS_TOL = "PASS_WITH_FLOAT_TOLERANCE"
FAIL = "FAIL"
NOT_PERFORMED = "NOT_PERFORMED"
NOT_APPLICABLE = "NOT_APPLICABLE"
OK = frozenset({PASS, PASS_TOL})
ABS_TOL = 1e-12
REL_TOL = 1e-9


@dataclass
class Check:
    name: str
    status: str
    production: Any = None
    recomputed: Any = None
    max_abs_diff: float = 0.0
    max_rel_diff: float = 0.0
    detail: str = ""


@dataclass
class Stage:
    id: str
    title: str
    checks: list[Check] = field(default_factory=list)
    status: str = PASS
    detail: str = ""

    def add(self, check: Check) -> Check:
        self.checks.append(check)
        return check

    def finish(self) -> Stage:
        if self.status in (NOT_PERFORMED, NOT_APPLICABLE) and not self.checks:
            return self
        statuses = [c.status for c in self.checks]
        if any(s == FAIL for s in statuses) or any(s == NOT_PERFORMED for s in statuses):
            self.status = FAIL
        elif not statuses:
            self.status = FAIL
            self.detail = self.detail or "no check was executed"
        elif all(s in (PASS, NOT_APPLICABLE) for s in statuses):
            self.status = PASS
        else:
            self.status = PASS_TOL
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "n_checks": len(self.checks),
            "n_failed": sum(c.status == FAIL for c in self.checks),
        }


def compare_number(name: str, production: Any, recomputed: Any, *, exact: bool = False) -> Check:
    """PASS if equal, PASS_WITH_FLOAT_TOLERANCE within the declared tolerance, else FAIL."""
    try:
        p, r = float(production), float(recomputed)
    except (TypeError, ValueError):
        return Check(name, FAIL, production, recomputed, detail="not a number")
    if math.isnan(p) and math.isnan(r):
        return Check(name, PASS, production, recomputed)
    if p == r:
        return Check(name, PASS, production, recomputed)
    d = abs(p - r)
    rel = d / max(abs(p), abs(r)) if max(abs(p), abs(r)) > 0 else math.inf
    if not exact and (d <= ABS_TOL or rel <= REL_TOL):
        return Check(name, PASS_TOL, production, recomputed, d, rel)
    return Check(
        name,
        FAIL,
        production,
        recomputed,
        d,
        rel,
        "difference exceeds tolerance" if not exact else "must be exact",
    )


def compare_series(name: str, production: list[float], recomputed: list[float]) -> Check:
    """Element-wise comparison; reports mismatches and the maximum differences."""
    if len(production) != len(recomputed):
        return Check(name, FAIL, len(production), len(recomputed), detail="length differs")
    worst_abs = worst_rel = 0.0
    mismatches = 0
    tol = False
    for p, r in zip(production, recomputed, strict=True):
        c = compare_number(name, p, r)
        worst_abs, worst_rel = max(worst_abs, c.max_abs_diff), max(worst_rel, c.max_rel_diff)
        if c.status == FAIL:
            mismatches += 1
        elif c.status == PASS_TOL:
            tol = True
    status = FAIL if mismatches else (PASS_TOL if tol else PASS)
    return Check(
        name, status, f"{len(production)} values", f"{mismatches} mismatching", worst_abs, worst_rel
    )


def expect(name: str, condition: bool, detail: str = "") -> Check:
    return Check(name, PASS if condition else FAIL, detail=detail)
