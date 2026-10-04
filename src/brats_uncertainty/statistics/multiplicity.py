"""Holm step-down correction within a single family (§14).

Holm is applied within each family only (F1, F2, F3, F3b, F4); no global FWER
control is claimed. F5 is descriptive and must not be Holm-corrected.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

INFERENTIAL_FAMILIES = ("F1", "F2", "F3", "F3b", "F4")
DESCRIPTIVE_FAMILIES = ("F5",)
FAMILY_SIZES = {"F1": 4, "F2": 2, "F3": 3, "F3b": 3, "F4": 2}


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    """Holm-adjusted p-values (monotone, capped at 1)."""
    keys = list(p_values)
    p = np.array([p_values[k] for k in keys], dtype=np.float64)
    if np.any(~np.isfinite(p)) or np.any((p < 0) | (p > 1)):
        raise ValueError("p-values must be finite and in [0, 1]")
    m = p.size
    order = np.argsort(p, kind="stable")
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[idx]))
        adj[idx] = running
    return {k: float(adj[i]) for i, k in enumerate(keys)}


def holm_family(family: str, p_values: Mapping[str, float]) -> dict[str, float]:
    """Holm within a named protocol family, checking the family is inferential and complete."""
    if family in DESCRIPTIVE_FAMILIES:
        raise ValueError(f"{family} is descriptive only; no p-values are used for claims")
    if family not in FAMILY_SIZES:
        raise ValueError(f"unknown family {family!r}")
    if len(p_values) != FAMILY_SIZES[family]:
        raise ValueError(
            f"family {family} must contain {FAMILY_SIZES[family]} tests, got {len(p_values)}"
        )
    return holm_adjust(p_values)
