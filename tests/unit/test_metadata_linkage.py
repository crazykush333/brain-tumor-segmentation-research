"""Amendment v1.0-A4 metadata linkage and its independent verifier (SYNTHETIC rows only)."""

from __future__ import annotations

from typing import Any

from brats_uncertainty.grouping import metadata_linkage as ml
from brats_uncertainty.verification import linkage_audit as la

COL, SITE, PID = (
    "Data Collection (as on TCIA+additional)",
    "Site ID",
    "PatientID on TCIA Radiology Portal",
)


def _cw(case: str, coll: str, site: Any, pid: str) -> dict[str, Any]:
    return {"BraTS2021 ID": case, COL: coll, SITE: site, PID: pid}


CROSSWALK = [
    _cw("C01", "UCSF-PDGM", 18.0, "433"),
    _cw("C02", "UCSF-PDGM", 18.0, "1433"),  # follow-up record maps it to patient 433
    _cw("C03", "UCSF-PDGM", 18.0, "12"),
    _cw("C04", "UCSF-PDGM_Additional", 18.0, ml.PLACEHOLDER),
    _cw("C05", "TCGA-GBM", 4.0, "TCGA-01"),
    _cw("C06", "TCGA-GBM", 4.0, "TCGA-02"),
    _cw("C07", "Collection 5", 4.0, ml.PLACEHOLDER),
]
UCSF = [
    {"ID": "UCSF-PDGM-433", "BraTS21 ID": "C01", "Sex": "M", "IDH": "wildtype"},
    {"ID": "UCSF-PDGM-0433_FU007d", "BraTS21 ID": "C02", "Sex": "M", "IDH": "wildtype"},
    {"ID": "UCSF-PDGM-12", "BraTS21 ID": "C03", "Sex": "F", "IDH": "IDH1 p.R132H"},
]
DEV = [f"C0{i}" for i in range(1, 8)]
VERIFIED = {"A": ["C01", "C02"]}


def _run(flagged: list[tuple[str, str]], max_group: int = 8) -> tuple[Any, Any]:
    ids = ml.build_identities(CROSSWALK, UCSF)
    res = ml.adjudicate(DEV, flagged, ids, VERIFIED, max_group_size=max_group)
    iids = la.identities(CROSSWALK, UCSF)
    idec = la.decide(DEV, flagged, iids, VERIFIED)
    return res, la.reconcile(res.decisions, res.groups, idec, la.components(DEV, idec))


def test_rules_follow_up_linkage_and_order() -> None:
    flagged = [("C01", "C03"), ("C03", "C04"), ("C05", "C06"), ("C04", "C05"), ("C05", "C07")]
    res, rec = _run(flagged)
    d = {k: v for k, v in res.decisions.items()}
    assert d[("C01", "C02")][0] == ml.SAME  # verified group (also same UCSF base 433)
    assert d[("C01", "C03")] == (ml.DIFFERENT, "M4")  # different UCSF patients
    assert d[("C05", "C06")] == (ml.DIFFERENT, "M5")  # different real TCIA IDs, same collection
    assert d[("C04", "C05")] == (ml.DIFFERENT, "M7")  # different contributing site
    assert d[("C03", "C04")] == (ml.UNRESOLVED, "M8")  # no authoritative identity
    assert d[("C05", "C07")] == (ml.UNRESOLVED, "M8")
    assert res.accepted, res.acceptance
    assert rec["decisions_identical"] and rec["groups_identical"], rec


def test_unresolved_chaining_into_a_giant_group_stops() -> None:
    flagged = [("C03", "C04"), ("C05", "C07")]
    res, _ = _run(flagged, max_group=1)  # any multi-case group exceeds the limit here
    assert not res.accepted and not res.acceptance["max_group_size"]


def test_metadata_different_pairs_never_end_in_one_group() -> None:
    # C03-C04 (UNRESOLVED) and C04-C01 would chain two different UCSF patients via C04
    res, _ = _run([("C01", "C03"), ("C03", "C04"), ("C01", "C04")])
    assert res.acceptance["metadata_different_never_linked"] is False and not res.accepted


def test_summary_statistics() -> None:
    res, _ = _run([("C03", "C04")])
    s = ml.summary(res, len(DEV))
    assert s["n_groups"] == 5 and s["largest_group"] == 2 and s["singletons"] == 3
