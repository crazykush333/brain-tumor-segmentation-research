"""Automated, deterministic gate-B8 adjudication (protocol v1.0 amendment v1.0-A3).

Replaces exhaustive manual review of the §6.2 flagged pairs with pre-specified rules.
The frozen T_screen rule and flagging are unchanged. Inputs are only the protocol's
permitted pre-split inputs:
- the four MRI sequences;
- the ground-truth WT labels, used only to exclude the lesion from the comparison;
- the TCIA crosswalk (collection, real TCIA patient ID);
- UCSF-PDGM metadata (Sex, IDH class).

No model prediction, segmentation performance, split, validation, test or other study
result is read.

Every constant comes from ``configs/grouping/b8_automated_v1.0-A3.yaml``. The rules
(R1-R8), the thresholds (tau_neg from metadata-certified different-patient pairs,
tau_ctrl from the verified same-patient pairs) and the acceptance criteria are
documented there and in the amendment.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from brats_uncertainty.grouping.similarity import pair_key
from brats_uncertainty.metrics.morphology import dilate

SAME, DIFFERENT, UNRESOLVED = "SAME_PATIENT", "DIFFERENT_PATIENT", "UNRESOLVED"
LINKED = frozenset({SAME, UNRESOLVED})
PLACEHOLDER_TCIA_ID = "new-not-previously-in-TCIA"
CONFIG_RELPATH = Path("configs/grouping/b8_automated_v1.0-A3.yaml")
DECISION_FIELDS = ("case_a", "case_b", "decision", "rule", "similarity", "coverage")


# ------------------------------------------------------------------------- configuration
@dataclass(frozen=True)
class AutoB8Config:
    raw: Mapping[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path) -> AutoB8Config:
        from brats_uncertainty.utils.io import read_yaml

        return cls(read_yaml(path), hashlib.sha256(path.read_bytes()).hexdigest())

    @property
    def modalities(self) -> tuple[str, ...]:
        return tuple(self.raw["modalities"])

    @property
    def block(self) -> int:
        return int(self.raw["block_size_voxels"])


# ------------------------------------------------------------------------- metadata
@dataclass(frozen=True)
class CaseMeta:
    collection: str
    site: str
    tcia_id: str | None  # real TCIA patient ID, None for the placeholder or blank
    sex: str | None = None  # UCSF-PDGM metadata only
    idh: str | None = None  # "wildtype" / "mutant" / None (unknown)


def idh_class(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    if not v or v == "unknown":
        return None
    if v == "wildtype":
        return "wildtype"
    if "mut" in v or "p.r" in v or "p.arg" in v:
        return "mutant"
    return None


def real_tcia_id(value: str | None) -> str | None:
    v = (value or "").strip()
    return None if not v or v == PLACEHOLDER_TCIA_ID or v.lower() == "none" else v


def metadata_rule(
    a: str,
    b: str,
    meta: Mapping[str, CaseMeta],
    verified_groups: Mapping[str, Sequence[str]],
) -> tuple[str, str] | None:
    """R1-R4 (metadata); ``None`` when metadata does not decide the pair."""
    for members in verified_groups.values():
        if a in members and b in members:
            return SAME, "R1"
    ma, mb = meta[a], meta[b]
    if ma.tcia_id and mb.tcia_id:
        if ma.tcia_id == mb.tcia_id:
            return SAME, "R2"
        if ma.collection == mb.collection:
            return DIFFERENT, "R3"
    if ma.sex and mb.sex and ma.sex != mb.sex:
        return DIFFERENT, "R4"
    if ma.idh and mb.idh and ma.idh != mb.idh:
        return DIFFERENT, "R4"
    return None


# ------------------------------------------------------------------------- anatomy descriptor
@dataclass(frozen=True)
class Descriptor:
    values: NDArray[np.float32]  # (n_modalities, n_blocks)
    valid: NDArray[np.bool_]  # blocks with non-tumour brain
    n_brain_blocks: int


def _block_mean(x: NDArray[Any], b: int) -> NDArray[np.float64]:
    pad = [(0, (-s) % b) for s in x.shape]
    x = np.pad(x, pad)
    s = x.shape
    return np.asarray(
        x.reshape(s[0] // b, b, s[1] // b, b, s[2] // b, b).mean(axis=(1, 3, 5)), dtype=np.float64
    )


def case_descriptor(
    images: Mapping[str, NDArray[Any]], wt_label: NDArray[Any], cfg: AutoB8Config
) -> Descriptor:
    """Block-averaged, brain-standardized intensities outside the dilated WT lesion."""
    mods = cfg.modalities
    vols = [np.asarray(images[m], dtype=np.float64) for m in mods]
    brain = np.logical_and.reduce([v > 0 for v in vols])
    excl = dilate(np.asarray(wt_label) > 0, int(cfg.raw["exclusion_dilation_voxels"]))
    valid = brain & ~excl
    b, frac = cfg.block, float(cfg.raw["block_min_valid_fraction"])
    vfrac = _block_mean(valid.astype(np.float64), b)
    bfrac = _block_mean(brain.astype(np.float64), b)
    vblock = vfrac >= frac
    out = []
    for v in vols:
        mu, sd = float(v[brain].mean()), float(v[brain].std())
        z = np.where(valid, (v - mu) / (sd if sd > 0 else 1.0), 0.0)
        s = _block_mean(z, b)
        out.append(np.where(vblock, s / np.maximum(vfrac, 1e-12), 0.0).ravel())
    return Descriptor(np.asarray(out, dtype=np.float32), vblock.ravel(), int((bfrac >= frac).sum()))


def pair_similarity(da: Descriptor, db: Descriptor, cfg: AutoB8Config) -> tuple[float, float, int]:
    """(S, coverage, shared blocks); S = mean Pearson r over the four sequences."""
    m = da.valid & db.valid
    n = int(m.sum())
    denom = min(da.n_brain_blocks, db.n_brain_blocks)
    cov = n / denom if denom else 0.0
    if n < 3:
        return math.nan, cov, n
    rs = []
    for k in range(da.values.shape[0]):
        x = da.values[k][m].astype(np.float64)
        y = db.values[k][m].astype(np.float64)
        x, y = x - x.mean(), y - y.mean()
        d = math.sqrt(float((x * x).sum()) * float((y * y).sum()))
        rs.append(float((x * y).sum()) / d if d > 0 else math.nan)
    return float(np.mean(rs)), cov, n


# ------------------------------------------------------------------------- adjudication
@dataclass
class Adjudication:
    decisions: dict[tuple[str, str], dict[str, Any]]
    tau_neg: float
    tau_ctrl: float
    control_similarity: dict[str, dict[str, float]]
    n_reference: int
    groups: list[list[str]]
    acceptance: dict[str, bool]
    audit: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return all(self.acceptance.values())


def reference_negative_pairs(
    cases: Sequence[str],
    meta: Mapping[str, CaseMeta],
    verified_groups: Mapping[str, Sequence[str]],
    cfg: AutoB8Config,
) -> list[tuple[str, str]]:
    """Development pairs certified DIFFERENT by metadata (R3/R4); deterministic sample."""
    ids = sorted(cases)
    cert = [
        (a, b)
        for i, a in enumerate(ids)
        for b in ids[i + 1 :]
        if (r := metadata_rule(a, b, meta, verified_groups)) is not None and r[0] == DIFFERENT
    ]
    ref = cfg.raw["reference_negatives"]
    n = int(ref["max_pairs"])
    if len(cert) <= n:
        return cert
    rng = np.random.default_rng(int(ref["sampling_seed"]))
    idx = np.sort(rng.choice(len(cert), size=n, replace=False))
    return [cert[int(i)] for i in idx]


def _components(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[list[str]]:
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups: dict[str, list[str]] = {}
    for n in parent:
        groups.setdefault(find(n), []).append(n)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


def adjudicate(
    flagged: Sequence[tuple[str, str]],
    development: Sequence[str],
    meta: Mapping[str, CaseMeta],
    verified_groups: Mapping[str, Sequence[str]],
    descriptor: Callable[[str], Descriptor],
    cfg: AutoB8Config,
) -> Adjudication:
    """Apply R1-R8 to every flagged pair; thresholds come only from the references."""
    cache: dict[str, Descriptor] = {}

    def desc(c: str) -> Descriptor:
        if c not in cache:
            cache[c] = descriptor(c)
        return cache[c]

    def sim(a: str, b: str) -> tuple[float, float, int]:
        return pair_similarity(desc(a), desc(b), cfg)

    cov_min, min_blocks = float(cfg.raw["coverage_min"]), int(cfg.raw["min_shared_blocks"])
    ok = lambda s, c, n: not math.isnan(s) and c >= cov_min and n >= min_blocks  # noqa: E731
    # references (fixed before any flagged pair is scored)
    refs = reference_negative_pairs(development, meta, verified_groups, cfg)
    ref_s = [s for s, c, n in (sim(a, b) for a, b in refs) if ok(s, c, n)]
    q = float(cfg.raw["reference_negatives"]["quantile"])
    tau_neg = float(np.quantile(np.asarray(ref_s), q, method="higher")) if ref_s else math.nan
    controls: dict[str, dict[str, float]] = {}
    for name, members in sorted(verified_groups.items()):
        a, b = sorted(members)[:2]
        s, c, n = sim(a, b)
        controls[name] = {"similarity": s, "coverage": c, "shared_blocks": float(n)}
    tau_ctrl = min((v["similarity"] for v in controls.values()), default=math.nan)
    decisions: dict[tuple[str, str], dict[str, Any]] = {}
    for a0, b0 in flagged:
        a, b = pair_key(a0, b0)
        md = metadata_rule(a, b, meta, verified_groups)
        if md is not None:
            decisions[(a, b)] = {"decision": md[0], "rule": md[1], "similarity": "", "coverage": ""}
            continue
        s, c, n = sim(a, b)
        if not ok(s, c, n):
            d, r = UNRESOLVED, "R5"
        elif s >= tau_ctrl:
            d, r = SAME, "R6"
        elif s > tau_neg:
            d, r = UNRESOLVED, "R7"
        else:
            d, r = DIFFERENT, "R8"
        decisions[(a, b)] = {
            "decision": d,
            "rule": r,
            "similarity": f"{s:.4f}" if not math.isnan(s) else "nan",
            "coverage": f"{c:.3f}",
        }
    linked = [k for k, v in decisions.items() if v["decision"] in LINKED]
    verified_edges = [(sorted(m)[0], x) for m in verified_groups.values() for x in sorted(m)[1:]]
    groups = _components(development, [*linked, *verified_edges])
    acc = cfg.raw["acceptance"]
    case_group = {c: i for i, g in enumerate(groups) for c in g}
    acceptance = {
        "controls_above_tau_neg": all(v["similarity"] > tau_neg for v in controls.values())
        if not math.isnan(tau_neg)
        else False,
        "controls_min_coverage": all(v["coverage"] >= cov_min for v in controls.values()),
        "max_group_size": max((len(g) for g in groups), default=0) <= int(acc["max_group_size"]),
        "verified_groups_intact": all(
            len({case_group[m] for m in ms if m in case_group}) == 1
            for ms in verified_groups.values()
        ),
        "every_flagged_pair_decided": len(decisions) == len({pair_key(*p) for p in flagged}),
        "no_site1_in_development": all(meta[c].site != "1" for c in development),
    }
    return Adjudication(decisions, tau_neg, tau_ctrl, controls, len(ref_s), groups, acceptance)


def summary(adj: Adjudication, n_development: int) -> dict[str, Any]:
    sizes = [len(g) for g in adj.groups]
    by_rule = Counter(v["rule"] for v in adj.decisions.values())
    by_dec = Counter(v["decision"] for v in adj.decisions.values())
    return {
        "n_development": n_development,
        "n_flagged": len(adj.decisions),
        "decisions": dict(sorted(by_dec.items())),
        "rules": dict(sorted(by_rule.items())),
        "tau_neg": adj.tau_neg,
        "tau_ctrl": adj.tau_ctrl,
        "controls": adj.control_similarity,
        "n_reference_negatives_scored": adj.n_reference,
        "n_groups": len(sizes),
        "largest_group": max(sizes, default=0),
        "median_group": float(np.median(sizes)) if sizes else 0.0,
        "group_size_counts": {str(k): v for k, v in sorted(Counter(sizes).items())},
        "multi_case_groups": [g for g in adj.groups if len(g) > 1],
        "acceptance": adj.acceptance,
        "accepted": adj.accepted,
    }
