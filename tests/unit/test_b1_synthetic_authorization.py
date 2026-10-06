"""SYNTHETIC_TEST_ONLY B1 authorization: exercised in test mode, never authorizes real data.

The synthetic provider response (tests/fixtures/synthetic_b1/) is NOT an actual
TCIA response. These tests check that it can drive the parser, the content
checks and the test-only state machine, and that it can never pass the real
gate B1, unlock B2 or let a real acquisition adapter execute. The real
repository status is only read here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.data.acquisition import LocalImportAdapter, stage_acquire
from brats_uncertainty.data.evidence import (
    SOURCE_CLASS_EXTERNAL,
    SOURCE_CLASS_OWNER,
    SOURCE_CLASS_SYNTHETIC,
    SYNTHETIC_TEST_ONLY,
    b1_source_class,
    is_synthetic_b1_text,
    load_evidence_identity,
    parse_b1_evidence,
    validate_b1_content,
)
from brats_uncertainty.data.synthetic_b1 import (
    SYNTHETIC_B1_GATE,
    SYNTHETIC_OUTCOME,
    TEST_AUTHORIZED,
    synthetic_b1_transition,
)
from brats_uncertainty.errors import ConfigError, ResearchGateError
from brats_uncertainty.evaluation.lifecycle import LIFECYCLE_STATUSES, apply_transition
from brats_uncertainty.evaluation.status import load_status, validate_status
from brats_uncertainty.evaluation.transitions import write_transition
from brats_uncertainty.repo_checks import check_paths
from tests.conftest import OWNER_ROUTE, REPO_ROOT, make_status_repo, make_verbatim_status_repo
from tests.fixtures.fake_evidence import b1_evidence_text, fake_source

FIXTURE = REPO_ROOT / "tests/fixtures/synthetic_b1/SYNTHETIC_TEST_ONLY_B1_AUTHORIZATION.md"
REFUSED = "synthetic authorization cannot authorize real-data acquisition"
REAL_IDENTITY = load_evidence_identity(REPO_ROOT)


def _text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _real_identity_repo(tmp_path: Path) -> Path:
    """Fake repo whose dataset identity is the real BraTS 2021 one (strongest negative test)."""
    root = make_verbatim_status_repo(tmp_path / "repo")
    shutil.copy(REPO_ROOT / "configs/dataset/brats2021.yaml", root / "configs/dataset/")
    shutil.copy(REPO_ROOT / "configs/dataset/brats2021_crosswalk.yaml", root / "configs/dataset/")
    return root


# ---------------------------------------------------------------- 1. parser
def test_synthetic_record_is_parsed_and_extracted() -> None:
    ev = parse_b1_evidence(_text())
    assert ev.synthetic is True
    assert ev.source_class == SOURCE_CLASS_SYNTHETIC
    f = ev.fields
    assert f["Dataset"] == "RSNA-ASNR-MICCAI-BraTS-2021"
    assert f["DOI"] == "10.7937/jc8x-9874"
    assert f["Response date"] == "2026-10-01"
    assert f["Route category"] == "A"
    assert "help@example.invalid" in f["Provider/source"]
    assert (
        "RE: Request for confirmation of permitted computational access route"
        in (f["Evidence reference"])
    )
    assert "No public redistribution" in f["Restrictions"]
    assert "attribution and citation" in f["Attribution requirements"]
    assert "duration of the approved analysis" in f["Conditions"]
    assert f["Approved route"].startswith(SYNTHETIC_TEST_ONLY)
    # the provider wording is preserved verbatim, in order
    assert ev.wording[0] == "From: TCIA Help Desk <help@example.invalid>"
    assert ev.wording[1] == "Date: 2026-10-01"
    assert ev.wording[-1] == "Synthetic Test Environment"
    assert "This synthetic message is not an actual TCIA authorization and must" in ev.wording
    assert "   access-restricted computational environment used solely for the" in ev.wording


def test_fixture_is_labelled_and_outside_the_real_evidence_location() -> None:
    text = _text()
    assert text.count(SYNTHETIC_TEST_ONLY) >= 3
    assert "NOT an actual TCIA response" in text
    rel = FIXTURE.relative_to(REPO_ROOT).as_posix()
    assert rel.startswith("tests/fixtures/") and "B1_EVIDENCE_" not in rel


# ---------------------------------------------------------------- 2. content/schema checks
def test_synthetic_record_passes_content_checks_only_with_test_outcome() -> None:
    ev = parse_b1_evidence(_text())
    kw = {"identity": REAL_IDENTITY, "protocol_version": "v1.0"}
    validate_b1_content(
        ev, approved_route=ev.fields["Approved route"], outcome=SYNTHETIC_OUTCOME, **kw
    )
    with pytest.raises(ConfigError, match="Authorization status: AUTHORIZED"):
        validate_b1_content(
            ev, approved_route=ev.fields["Approved route"], outcome=("AUTHORIZED", "APPROVED"), **kw
        )
    with pytest.raises(ConfigError, match="Protocol version"):
        validate_b1_content(
            ev,
            approved_route=ev.fields["Approved route"],
            outcome=SYNTHETIC_OUTCOME,
            identity=REAL_IDENTITY,
            protocol_version="v0.9",
        )


@pytest.mark.parametrize("field", ["Conditions", "Restrictions", "Source class", "Response date"])
def test_synthetic_record_with_missing_field_is_refused(field: str) -> None:
    broken = "\n".join(ln for ln in _text().splitlines() if not ln.startswith(f"{field}:"))
    with pytest.raises(ConfigError, match=f"exactly one '{field}:'"):
        parse_b1_evidence(broken)


# ---------------------------------------------------------------- 3. test-mode transition
def test_synthetic_transition_pending_to_test_authorized_without_touching_production() -> None:
    status_file = REPO_ROOT / "docs/project_status.yaml"
    before = status_file.read_bytes()
    out = synthetic_b1_transition(_text(), identity=REAL_IDENTITY, protocol_version="v1.0")
    assert (out.gate, out.previous, out.status) == (SYNTHETIC_B1_GATE, "PENDING", TEST_AUTHORIZED)
    assert out.synthetic is True and out.source_class == SOURCE_CLASS_SYNTHETIC
    assert out.approved_route.startswith(SYNTHETIC_TEST_ONLY)
    assert status_file.read_bytes() == before
    # the real B1 basis stays the owner-approved alternative, never the synthetic record
    real = load_status(REPO_ROOT)
    evidence = (REPO_ROOT / str(real.gate("B1").evidence)).read_text(encoding="utf-8")
    assert b1_source_class(evidence) == SOURCE_CLASS_OWNER


def test_test_state_is_distinct_from_real_authorized() -> None:
    assert TEST_AUTHORIZED != "AUTHORIZED"
    assert TEST_AUTHORIZED not in LIFECYCLE_STATUSES
    assert SYNTHETIC_B1_GATE not in {g.id for g in load_status(REPO_ROOT).gates.values()}
    raw = load_status(REPO_ROOT).raw
    with pytest.raises(ConfigError):
        apply_transition(raw, "B1", TEST_AUTHORIZED)
    raw = load_status(REPO_ROOT).raw
    next(g for g in raw["gates"] if g["id"] == "B1")["status"] = TEST_AUTHORIZED
    with pytest.raises(ConfigError):
        validate_status(raw, REPO_ROOT)


def test_test_mode_rejects_illegal_transitions_and_real_records() -> None:
    kw = {"identity": REAL_IDENTITY, "protocol_version": "v1.0"}
    with pytest.raises(ConfigError, match="illegal test transition"):
        synthetic_b1_transition(_text(), current=TEST_AUTHORIZED, **kw)
    with pytest.raises(ConfigError, match="illegal test transition"):
        synthetic_b1_transition(_text(), target="AUTHORIZED", **kw)
    real_format = b1_evidence_text(Dataset=REAL_IDENTITY["dataset"], DOI=REAL_IDENTITY["doi"])
    with pytest.raises(ConfigError, match="test mode accepts only"):
        synthetic_b1_transition(real_format, **kw)


# ---------------------------------------------------------------- 4. real-acquisition blocking
def test_synthetic_record_cannot_pass_real_b1(tmp_path: Path) -> None:
    root = _real_identity_repo(tmp_path)
    route = parse_b1_evidence(_text()).fields["Approved route"]
    ev = "docs/data/B1_EVIDENCE_2026-10-01.md"
    variants = {
        "verbatim": _text(),
        "source class relabelled": _text().replace(
            f"Source class: {SOURCE_CLASS_SYNTHETIC}", f"Source class: {SOURCE_CLASS_EXTERNAL}"
        ),
        "only Synthetic flag left": b1_evidence_text(Dataset=REAL_IDENTITY["dataset"])
        + "\nSynthetic: true\n",
    }
    for name, text in variants.items():
        (root / ev).write_text(text, encoding="utf-8")
        with pytest.raises(ConfigError, match=REFUSED):
            write_transition(
                root, "B1", "PASSED", evidence=ev, on="2026-10-01", approved_route=route
            )
        assert load_status(root).gate("B1").status == "PENDING", name
        assert load_status(root).gate("B2").status == "LOCKED", name


def _synthetic_b1_status_repo(tmp_path: Path) -> Path:
    """Hand-crafted status (bypassing the transition writer): B1 PASSED on synthetic evidence."""
    root = make_status_repo(tmp_path / "repo", closed={"B1"})
    raw = yaml.safe_load((root / "docs/project_status.yaml").read_text(encoding="utf-8"))
    b1 = next(g for g in raw["gates"] if g["id"] == "B1")
    (root / str(b1["evidence"])).write_text(_text(), encoding="utf-8")
    return root


def test_real_acquisition_with_synthetic_b1_fails_closed(tmp_path: Path) -> None:
    root = _synthetic_b1_status_repo(tmp_path)
    delivered = tmp_path / "delivered"
    delivered.mkdir()
    (delivered / "file.bin").write_bytes(b"synthetic bytes")
    store = tmp_path / "store"
    adapter = LocalImportAdapter(fake_source(), delivered)
    with pytest.raises(ResearchGateError, match=REFUSED):
        adapter.execute(store, repo_root=root)
    with pytest.raises(ResearchGateError, match=REFUSED):
        stage_acquire(
            root,
            adapter,
            storage_root=store,
            out_record=tmp_path / "B2_record.json",
            acquired_by="pytest",
            execute=True,
            require_clean_commit=False,
        )
    assert not store.exists()
    assert not (tmp_path / "B2_record.json").exists()
    with pytest.raises(ConfigError, match=REFUSED):
        load_status(root)


def test_same_repo_with_external_evidence_is_not_refused_as_synthetic(tmp_path: Path) -> None:
    """Control: the refusal above is caused by the synthetic record, not by the fake repo."""
    root = make_status_repo(tmp_path / "repo", closed={"B1"})
    assert load_status(root).gate("B1").status == "PASSED"
    assert load_status(root).gate("B2").status == "AUTHORIZED"


def test_repository_scan_flags_synthetic_content_in_real_evidence_location(
    tmp_path: Path,
) -> None:
    rel = "docs/data/B1_EVIDENCE_2026-10-01.md"
    (tmp_path / "docs/data").mkdir(parents=True)
    (tmp_path / rel).write_text(_text(), encoding="utf-8")
    findings = check_paths([rel], tmp_path)
    assert any("synthetic authorization" in f.problem for f in findings)
    assert not [f for f in check_paths([FIXTURE.relative_to(REPO_ROOT).as_posix()], REPO_ROOT)]


# ---------------------------------------------------------------- 5. production state
def test_production_state_is_owner_approved_not_synthetic(pre_execution_root: Path) -> None:
    """SYNTHETIC TEST STATE never leaks into the REAL OWNER-APPROVED PRODUCTION STATE."""
    repo_root = pre_execution_root  # frozen pre-execution snapshot (tests/conftest.py)
    st = load_status(repo_root)
    assert st.gate("B1").status == "PASSED"
    assert st.gate("B2").status in (
        "AUTHORIZED",
        "RUNNING",
    )  # authorized; RUNNING once the runner started it
    assert all(st.gate(f"B{i}").status == "LOCKED" for i in range(3, 13))
    assert st.raw["data"]["authorization"] == "APPROVED"
    assert st.raw["data"]["approved_route"] == OWNER_ROUTE
    assert SYNTHETIC_TEST_ONLY not in st.raw["data"]["approved_route"]
    assert st.raw["data"]["acquired"] is False
    for p in (repo_root / "docs/data").glob("B1_EVIDENCE_2*"):
        text = p.read_text(encoding="utf-8")
        assert not is_synthetic_b1_text(text), p
        assert b1_source_class(text) == SOURCE_CLASS_OWNER, p
    template = (repo_root / "docs/data/B1_EVIDENCE_TEMPLATE.md").read_text(encoding="utf-8")
    assert SOURCE_CLASS_SYNTHETIC not in template and SYNTHETIC_TEST_ONLY not in template
