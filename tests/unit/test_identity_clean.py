"""Amendment v1.0-A5 identity-clean cohort and its independent verifier (SYNTHETIC rows)."""

from __future__ import annotations

from typing import Any

from brats_uncertainty.grouping import identity_clean as ic
from brats_uncertainty.verification import identity_audit as ia

RENAMED = {315: 433}
TCGA = ["TCGA-GBM", "TCGA-LGG"]


def _cw(case: str, coll: str, site: float, pid: str, cohort: str = "Training") -> dict[str, Any]:
    return {
        "BraTS2021 ID": case,
        "Data Collection (as on TCIA+additional)": coll,
        "Site ID": site,
        "PatientID on TCIA Radiology Portal": pid,
        "Segmentation (Task 1) Cohort": cohort,
    }


CROSSWALK = [
    _cw("C01", "UCSF-PDGM", 18.0, "433"),
    _cw("C02", "UCSF-PDGM", 18.0, "315"),  # renamed follow-up of 433 (not in metadata here)
    _cw("C03", "UCSF-PDGM", 18.0, "12"),
    _cw("C04", "UCSF-PDGM_Additional", 18.0, ic.PLACEHOLDER),  # no identity -> quarantine
    _cw("C05", "TCGA-GBM", 4.0, "TCGA-02-0001"),
    _cw("C06", "TCGA-LGG", 4.0, "TCGA-02-0001"),  # same TCGA barcode across projects
    _cw("C07", "IvyGAP", 6.0, "W1"),
    _cw("C08", "Collection 5", 4.0, ic.PLACEHOLDER),
    _cw("C09", "UCSF-PDGM", 18.0, "429"),
    _cw("C10", "UCSF-PDGM", 18.0, "138"),
    _cw("C99", "UCSF-PDGM", 18.0, "1", cohort="Validation"),  # not a training case
]
UCSF = [
    {"ID": "UCSF-PDGM-429", "BraTS21 ID": "C09"},
    {"ID": "UCSF-PDGM-0429_FU003d", "BraTS21 ID": "C10"},
]
DEV = sorted(
    r["BraTS2021 ID"] for r in CROSSWALK if r["Segmentation (Task 1) Cohort"] == "Training"
)
VERIFIED = {"B": ["C09", "C10"]}


def _run() -> tuple[ic.CohortResult, dict[str, Any]]:
    ids = ic.case_identities(CROSSWALK, UCSF, renamed=RENAMED, tcga_collections=TCGA)
    res = ic.build_cohort(ids, DEV, VERIFIED, ic.follow_up_pairs(UCSF, DEV))
    ind = ia.identity_keys(CROSSWALK, UCSF, RENAMED, TCGA)
    p, q, g = ia.cohort_and_groups(ind, DEV, VERIFIED)
    return res, ia.reconcile(res.primary, res.quarantine, res.groups, p, q, g)


def test_cohorts_and_identity_groups() -> None:
    res, rec = _run()
    assert res.quarantine == ["C04", "C08"]  # no authoritative identity -> never grouped
    assert "C99" not in res.primary + res.quarantine
    groups = {tuple(g) for g in res.groups}
    assert ("C01", "C02") in groups  # official rename list links the follow-up
    assert ("C05", "C06") in groups  # one TCGA barcode namespace
    assert ("C09", "C10") in groups  # verified group and follow-up record
    assert ("C03",) in groups and ("C07",) in groups
    assert res.accepted, res.acceptance
    assert rec["status"] == "VERIFIED", rec
    s = ic.summary(res, DEV)
    assert s["n_primary"] == 8 and s["n_quarantine"] == 2 and s["n_patient_groups"] == 5
    assert s["sites_absent_from_primary"] == []


def test_verified_group_with_a_quarantined_member_fails() -> None:
    ids = ic.case_identities(CROSSWALK, UCSF, renamed=RENAMED, tcga_collections=TCGA)
    res = ic.build_cohort(ids, DEV, {"X": ["C03", "C04"]})
    assert not res.acceptance["verified_groups_intact"] and not res.accepted


def test_site1_case_in_development_fails() -> None:
    ids = ic.case_identities(
        [*CROSSWALK, _cw("C11", "UPENN-GBM", 1.0, "UPENN-1")],
        UCSF,
        renamed=RENAMED,
        tcga_collections=TCGA,
    )
    res = ic.build_cohort(ids, [*DEV, "C11"], VERIFIED)
    assert not res.acceptance["no_site1_in_development"]


def test_independent_verifier_detects_a_difference() -> None:
    res, _ = _run()
    ind = ia.identity_keys(CROSSWALK, UCSF, {}, TCGA)  # without the rename list
    p, q, g = ia.cohort_and_groups(ind, DEV, VERIFIED)
    rec = ia.reconcile(res.primary, res.quarantine, res.groups, p, q, g)
    assert rec["status"] == "FAILED" and not rec["checks"]["groups_identical"]
