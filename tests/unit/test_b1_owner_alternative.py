"""B1 via the owner-approved alternative of the frozen B1 wording (amendment-backed).

Exercised in temporary FAKE repositories that start from the pre-B1 baseline,
so these tests do not depend on the real project state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brats_uncertainty.errors import ConfigError
from brats_uncertainty.evaluation.status import load_status
from brats_uncertainty.evaluation.transitions import write_transition
from brats_uncertainty.results.site_export import build_overview
from tests.conftest import make_verbatim_status_repo

ROUTE = "Direct official TCIA access into a private, access-restricted computational environment"
EV = "docs/data/B1_EVIDENCE_2000-01-01.md"
AMENDMENT = "docs/research/protocol-amendments/2000-01-01_B1_fake.md"
FIELDS = {
    "Source class": "OWNER_APPROVED_ALTERNATIVE",
    "Evidence basis": f"Formal owner decision recorded in {AMENDMENT}",
    "Protocol version": "v1.0",
    "Dataset": "FAKE",
    "DOI": "10.0000/fake",
    "Owner": "Ayush Kushwaha",
    "Date": "2000-01-01",
    "Approval basis": "Frozen B1 wording permits an owner-approved alternative",
    "Approved route": ROUTE,
    "Official source": "https://fake.invalid/brats",
    "Download mechanism": "official FAKE download link",
    "Third-party mirroring": "NO",
    "Public redistribution": "NO",
    "Repository data storage": "NO",
    "Website data exposure": "NO",
    "External provider authorization": "NONE",
    "Conditions": "private, access-restricted environment only",
    "Restrictions": "no mirror; no redistribution",
    "Attribution requirements": "cite the FAKE DOI",
    "B1 status": "AUTHORIZED",
    "Authorization status": "AUTHORIZED",
    "Conclusion": "APPROVED",
}


def _text(extra: str = "", **overrides: str) -> str:
    values = {**FIELDS, **overrides}
    return "# FAKE owner decision\n\n" + "".join(f"{k}: {v}\n" for k, v in values.items()) + extra


def _repo(tmp_path: Path, text: str, *, amendment: bool = True) -> Path:
    root = make_verbatim_status_repo(tmp_path / "repo")
    (root / EV).write_text(text, encoding="utf-8")
    if amendment:
        (root / AMENDMENT).parent.mkdir(parents=True, exist_ok=True)
        (root / AMENDMENT).write_text("# FAKE amendment\n", encoding="utf-8")
    return root


def _transition(root: Path, *, apply: bool = False, route: str = ROUTE) -> list[str]:
    return write_transition(
        root, "B1", "PASSED", evidence=EV, on="2000-01-01", approved_route=route, apply=apply
    )


def test_owner_alternative_authorizes_b1_and_only_readies_b2(tmp_path: Path) -> None:
    root = _repo(tmp_path, _text())
    changes = _transition(root)
    assert "B1.status: PENDING -> PASSED" in changes
    assert "B2.status: LOCKED -> AUTHORIZED" in changes
    assert not any(c.startswith(("B3", "B4", "B5", "B6", "B7", "data.acquired")) for c in changes)
    _transition(root, apply=True)
    st = load_status(root)
    assert st.gate("B1").status == "PASSED"
    assert st.gate("B2").status == "AUTHORIZED"  # ready, not executed
    assert all(st.gate(f"B{i}").status == "LOCKED" for i in range(3, 13))
    assert st.raw["data"]["authorization"] == "APPROVED"
    assert st.raw["data"]["acquired"] is False
    rows = {
        r["key"]: r
        for r in build_overview(st.raw, {g.id: g.status for g in st.gates.values()}, root)
    }
    assert rows["b1"]["status"] == "ROUTE_AUTHORIZED"
    assert rows["b1"]["status_label"] == "Authorized — Owner-approved alternative"
    assert "no external TCIA authorization is claimed" in rows["b1"]["detail"]
    assert rows["b2"]["status"] == "AUTHORIZED"
    assert [rows[f"b{i}"]["status"] for i in range(3, 8)] == ["LOCKED"] * 5
    assert "TCIA approved" not in str(rows)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"Third-party mirroring": "YES"}, "Third-party mirroring: NO"),
        ({"Public redistribution": "YES"}, "Public redistribution: NO"),
        ({"Repository data storage": "YES"}, "Repository data storage: NO"),
        ({"Website data exposure": "YES"}, "Website data exposure: NO"),
        ({"External provider authorization": "TCIA email"}, "External provider authorization"),
        ({"Approval basis": "owner decided"}, "Approval basis"),
        ({"Owner": "Someone Else"}, "project owner"),
        ({"Date": "2000-01-02"}, "file name"),
        ({"Official source": "https://unofficial.example/brats"}, "Official source"),
        ({"Evidence basis": "owner decision (no amendment)"}, "amendment"),
        ({"Protocol version": "v0.9"}, "Protocol version"),
        ({"DOI": "10.7937/other"}, "DOI"),
        ({"B1 status": "PASSED"}, "B1 status: AUTHORIZED"),
        ({"Conclusion": "NOT APPROVED"}, "Conclusion: APPROVED"),
    ],
)
def test_owner_alternative_field_rules(
    tmp_path: Path, overrides: dict[str, str], match: str
) -> None:
    root = _repo(tmp_path, _text(**overrides))
    with pytest.raises(ConfigError, match=match):
        _transition(root)
    assert load_status(root).gate("B1").status == "PENDING"


@pytest.mark.parametrize(
    "route",
    [
        "Private Kaggle dataset holding the official files",
        "Private mirror of the official TCIA files",
        "Re-hosting in a private bucket",
        "Upload to a private Hugging Face dataset",
    ],
)
def test_owner_alternative_cannot_approve_mirroring_or_uploads(tmp_path: Path, route: str) -> None:
    root = _repo(tmp_path, _text(**{"Approved route": route}))
    with pytest.raises(ConfigError, match="mirroring, re-hosting or uploads"):
        _transition(root, route=route)


def test_owner_alternative_must_not_claim_tcia_approval(tmp_path: Path) -> None:
    for i, claim in enumerate(("TCIA approved this route.", "TCIA has authorized this route.")):
        root = _repo(tmp_path / f"c{i}", _text(extra=f"\n{claim}\n"))
        with pytest.raises(ConfigError, match="must not claim TCIA approval"):
            _transition(root)


def test_stale_owner_evidence_for_another_route_is_refused(tmp_path: Path) -> None:
    """Evidence naming a different route than the one being recorded is refused."""
    root = _repo(tmp_path, _text())
    with pytest.raises(ConfigError, match=r"must equal data\.approved_route"):
        _transition(root, route="Direct official TCIA access into another environment")


def test_owner_alternative_requires_the_logged_amendment_file(tmp_path: Path) -> None:
    root = _repo(tmp_path, _text(), amendment=False)
    with pytest.raises(ConfigError, match="amendment"):
        _transition(root)


def test_owner_alternative_missing_field_and_unknown_class(tmp_path: Path) -> None:
    text = _text().replace("Website data exposure: NO\n", "")
    with pytest.raises(ConfigError, match="exactly one 'Website data exposure:'"):
        _transition(_repo(tmp_path / "a", text))
    with pytest.raises(ConfigError, match="Source class"):
        _transition(_repo(tmp_path / "b", _text(**{"Source class": "OWNER_SAYS_SO"})))


def test_synthetic_markers_still_refused_on_owner_records(tmp_path: Path) -> None:
    root = _repo(tmp_path, _text(extra="\nSynthetic: true\n"))
    with pytest.raises(ConfigError, match="synthetic authorization cannot authorize"):
        _transition(root)
