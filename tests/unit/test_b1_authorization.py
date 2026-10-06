"""Gate B1: PENDING -> AUTHORIZED (lifecycle PASSED) only on a recorded, accepted basis.

The external-evidence rules are exercised with FAKE evidence in temporary
repositories that start from the pre-B1 baseline. The real repository is
read-only here; its genuine state is B1 PASSED via the owner-approved
alternative (amendment v1.0-A1), with no external provider authorization.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from brats_uncertainty.data.evidence import (
    SOURCE_CLASS_EXTERNAL,
    SOURCE_CLASS_OWNER,
    b1_source_class,
)
from brats_uncertainty.errors import ConfigError
from brats_uncertainty.evaluation.status import load_status
from brats_uncertainty.evaluation.transitions import write_transition
from brats_uncertainty.results.site_export import build_overview
from tests.conftest import FAKE_ROUTE, OWNER_ROUTE, make_status_repo, make_verbatim_status_repo
from tests.fixtures.fake_evidence import B1_FAKE_FIELDS, b1_evidence_text, write_b1_evidence

AMENDMENT = "docs/research/protocol-amendments/2026-10-01_B1_data-route.md"
TEMPLATE = "docs/data/B1_EVIDENCE_TEMPLATE.md"
INQUIRY = "docs/data/TCIA_DATA_ROUTE_INQUIRY.md"
RECORD = "docs/data/B1_DATA_ROUTE_AUTHORIZATION.md"
NON_EVIDENCE = (
    "publicly downloadable",
    "TCIA web page",
    "CC BY 4.0 licence",
    "Kaggle availability",
    "successful test download",
    "API availability",
)


def _dry_run(root: Path, text: str) -> list[str]:
    ev = write_b1_evidence(root, text=text)
    return write_transition(
        root, "B1", "PASSED", evidence=ev, on="2000-01-01", approved_route=FAKE_ROUTE
    )


def _refused(root: Path, text: str, match: str = "gate B1") -> None:
    with pytest.raises(ConfigError, match=match):
        _dry_run(root, text)


def _without_line(text: str, field: str) -> str:
    return re.sub(rf"(?m)^{re.escape(field)}:.*\n", "", text, count=1)


# ---------------------------------------------------------------- real repository state
# REAL OWNER-APPROVED PRODUCTION STATE (2026-10-01): B1 PASSED via the owner-approved
# alternative (amendment v1.0-A1); no external provider evidence exists.
def test_real_b1_is_owner_approved_with_no_external_authorization(pre_execution_root: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    st = load_status(repo_root)
    assert st.gate("B1").status == "PASSED"
    assert st.gate("B1").evidence == "docs/data/B1_EVIDENCE_2026-10-01.md"
    assert st.gate("B2").status in (
        "AUTHORIZED",
        "RUNNING",
    )  # authorized; RUNNING once the runner started it
    assert all(st.gate(f"B{i}").status == "LOCKED" for i in range(3, 13))
    assert st.raw["data"]["authorization"] == "APPROVED"
    assert st.raw["data"]["approved_route"] == OWNER_ROUTE
    assert st.raw["data"]["inquiry_sent"] is False
    assert st.raw["data"]["acquired"] is False
    assert st.raw["data"]["b1_evidence_template"] == TEMPLATE
    evidence = list((repo_root / "docs/data").glob("B1_EVIDENCE_2*.md"))
    assert [p.name for p in evidence] == ["B1_EVIDENCE_2026-10-01.md"]
    text = evidence[0].read_text(encoding="utf-8")
    assert b1_source_class(text) == SOURCE_CLASS_OWNER
    assert re.search(r"(?m)^External provider authorization: NONE$", text)
    assert SOURCE_CLASS_EXTERNAL not in text.split("## 1.")[0]  # header fields: owner class only
    assert "docs/research/protocol-amendments/2026-10-01_B1_data-route.md" in text


def test_real_overview_shows_owner_approved_b1_and_ready_b2(pre_execution_root: Path) -> None:
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    st = load_status(repo_root)
    rows = build_overview(st.raw, {g.id: g.status for g in st.gates.values()}, repo_root)
    b1 = next(r for r in rows if r["key"] == "b1")
    assert (b1["label"], b1["status"]) == ("B1 Data route", "ROUTE_AUTHORIZED")
    assert b1["status_label"] == "Authorized — Owner-approved alternative"
    b2 = next(r for r in rows if r["key"] == "b2")["status"]
    assert b2 in ("AUTHORIZED", "RUNNING") and b2 == st.gate("B2").status
    site = (repo_root / "website/data/status.json").read_text(encoding="utf-8")
    assert "TCIA approved" not in site
    assert "Owner-approved alternative" in site


def test_amendment_records_the_owner_decision(repo_root: Path) -> None:
    text = (repo_root / AMENDMENT).read_text(encoding="utf-8")
    for needle in (
        "Amendment ID: v1.0-A1",
        "Amendment type: DATA-ROUTE / OPERATIONAL",
        "Date: 2026-10-01",
        "Owner: Ayush Kushwaha",
        "Test-set data seen before amendment: No",
        "## Previous state",
        "pending an external TCIA response",
        "**New state:** owner-approved direct official TCIA access into a private, "
        "access-restricted computational environment",
        "**Scientific impact:** none.",
        "**Methodological impact:** none.",
        "| External provider authorization | NONE.",
        "| TCIA response | NONE |",
        "| Third-party re-hosting | Not authorized |",
        "| Kaggle mirroring | Not authorized |",
        "| Public redistribution | Not authorized |",
    ):
        assert needle in text, needle
    index = (repo_root / "docs/research/protocol-amendments/README.md").read_text(encoding="utf-8")
    assert "v1.0-A1 — 2026-10-01 — DATA-ROUTE / OPERATIONAL" in index
    assert "[2026-10-01_B1_data-route.md](2026-10-01_B1_data-route.md)" in index


# ---------------------------------------------------------------- documents
def test_template_is_pending_and_not_evidence(repo_root: Path) -> None:
    text = (repo_root / TEMPLATE).read_text(encoding="utf-8")
    assert "TEMPLATE - NOT EVIDENCE" in text
    assert "STATUS = PENDING" in text
    assert re.search(r"(?m)^Authorization status: PENDING$", text)
    assert re.search(r"(?m)^Conclusion: PENDING$", text)
    assert "## Exact provider wording" in text
    for field in B1_FAKE_FIELDS:
        assert len(re.findall(rf"(?m)^{re.escape(field)}:", text)) == 1, field
    for cat in ("**A:**", "**B:**", "**C:**"):
        assert cat in text
    for item in NON_EVIDENCE:
        assert item.split()[0].lower() in text.lower()


def test_inquiry_is_ready_to_send_manually(repo_root: Path) -> None:
    text = (repo_root / INQUIRY).read_text(encoding="utf-8")
    assert "NOT SENT" in text
    assert "help@cancerimagingarchive.net" in text
    for n in range(1, 7):
        assert re.search(rf"(?m)^{n}\. ", text), n
    assert not re.search(r"(?m)^7\. ", text)
    for term in ("Private computational storage", "Public redistribution", "Runtime-only access"):
        assert term in text
    for placeholder in ("[Date]", "[Full name]", "[Affiliation / institution]", "[Contact email]"):
        assert placeholder in text
    assert "CLOSED" not in text  # B1's authorized state is PASSED, not the gate-A CLOSED


def test_b1_record_states_the_owner_approved_basis_and_the_rules(repo_root: Path) -> None:
    text = (repo_root / RECORD).read_text(encoding="utf-8")
    assert "| **Status** | **AUTHORIZED: owner-approved alternative**" in text
    assert "| Source class | `OWNER_APPROVED_ALTERNATIVE` |" in text
    assert "| External provider authorization | **NONE." in text
    assert "no TCIA authorization is claimed" in text
    for url in (
        "https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/",
        "https://www.cancerimagingarchive.net/tcia-data-analysis-center/",
        "https://www.cancerimagingarchive.net/support/",
        "https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/",
    ):
        assert url in text
    assert "verified 2026-09-29; re-verified 2026-09-30 and 2026-10-01" in text
    for item in ("publicly downloadable", "CC BY 4.0 licence alone", "Kaggle availability"):
        assert item in text


# ---------------------------------------------------------------- validator: refusals
def test_template_copied_to_an_evidence_name_is_refused(repo_root: Path, tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    template = (repo_root / TEMPLATE).read_text(encoding="utf-8")
    _refused(root, template, "template")
    _refused(root, template.replace("TEMPLATE - NOT EVIDENCE", ""), "template")


def test_placeholders_and_empty_values_are_refused(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    for field in B1_FAKE_FIELDS:
        for bad in ("<route>", "TBD", "TODO", "PENDING", "?", ""):
            _refused(root, b1_evidence_text(**{field: bad}), "empty or a placeholder|exactly one")


def test_missing_or_duplicated_fields_are_refused(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    good = b1_evidence_text()
    for field in B1_FAKE_FIELDS:
        _refused(root, _without_line(good, field), f"exactly one '{re.escape(field)}:'")
        _refused(root, good + f"{field}: {B1_FAKE_FIELDS[field]}\n", "exactly one")


@pytest.mark.parametrize(
    "etype",
    [
        "Owner-approved alternative",
        "TCIA written confirmation",
        "Public download",
        "TCIA web page",
        "CC BY 4.0 licence",
        "Kaggle availability",
        "Successful test download",
        "API availability",
    ],
)
def test_non_external_evidence_types_are_refused(tmp_path: Path, etype: str) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    _refused(root, b1_evidence_text(**{"Evidence type": etype}), "Evidence type")


def test_not_authorized_or_not_approved_is_refused(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    _refused(root, b1_evidence_text(**{"Authorization status": "NOT AUTHORIZED"}), "AUTHORIZED")
    _refused(root, b1_evidence_text(Conclusion="NOT APPROVED"), "APPROVED")


def test_identity_route_and_dates_are_checked(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    for kw, match in (
        ({"Protocol version": "v0.9"}, "Protocol version"),
        ({"Dataset": "BraTS-2023"}, "dataset"),
        ({"DOI": "10.7937/other"}, "DOI"),
        ({"Route category": "D"}, "Route category"),
        ({"Approved route": "SOME OTHER ROUTE"}, "Approved route"),
        ({"Inquiry date": "01/12/1999"}, "YYYY-MM-DD"),
        ({"Inquiry date": "2000-01-02"}, "precedes"),
        ({"Response date": "2000-01-02", "Inquiry date": "1999-12-01"}, "file name"),
    ):
        _refused(root, b1_evidence_text(**kw), match)


def test_provider_wording_must_be_quoted(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    for wording in ("", ">", "> ", "paraphrase without quoting"):
        _refused(root, b1_evidence_text(wording=wording), "exact wording")
    no_heading = b1_evidence_text().replace("## Exact provider wording", "## Wording")
    _refused(root, no_heading, "exact wording")


def test_documentation_is_never_b1_evidence(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    for ev in (RECORD, INQUIRY, TEMPLATE):
        with pytest.raises(ConfigError, match="B1_EVIDENCE"):
            write_transition(
                root, "B1", "PASSED", evidence=ev, on="2000-01-01", approved_route=FAKE_ROUTE
            )


# ---------------------------------------------------------------- validator: positive (FAKE)
def test_recorded_external_evidence_passes_b1_and_shows_authorized(tmp_path: Path) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    changes = _dry_run(root, b1_evidence_text())
    assert "B1.status: PENDING -> PASSED" in changes
    assert "B2.status: LOCKED -> AUTHORIZED" in changes
    passed = make_status_repo(tmp_path / "repo2", closed={"B1"})
    st = load_status(passed)
    rows = build_overview(st.raw, {g.id: g.status for g in st.gates.values()}, passed)
    b1 = next(r for r in rows if r["key"] == "b1")
    assert (b1["label"], b1["status"]) == ("B1 Data route", "ROUTE_AUTHORIZED")
    assert b1["status_label"] == "Authorized — external provider authorization"
