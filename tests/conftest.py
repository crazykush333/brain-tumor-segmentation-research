from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.evaluation.lifecycle import B_GATES, unlock_eligible
from tests.fixtures.fake_evidence import FAKE_ROUTE, build_fake_chain, write_b1_evidence

REPO_ROOT = Path(__file__).resolve().parents[1]
# Pre-B1 baseline (B1 PENDING, B2-B12 LOCKED; the real status before 2026-10-01) for the fake
# test repositories, so the transition tests start from PENDING whatever the real state is.
PENDING_STATUS = REPO_ROOT / "tests/fixtures/project_status_b1_pending.yaml"
OWNER_ROUTE = (
    "Direct official TCIA access into a private, access-restricted computational environment"
)


def pending_raw() -> dict:  # type: ignore[type-arg]
    """The pre-B1 status mapping (validates against the real repository: it has no evidence)."""
    return yaml.safe_load(PENDING_STATUS.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


__all__ = [
    "FAKE_ROUTE",
    "OWNER_ROUTE",
    "PENDING_STATUS",
    "REPO_ROOT",
    "make_status_repo",
    "make_verbatim_status_repo",
    "pending_raw",
]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def _copy_basics(tmp_path: Path) -> None:
    (tmp_path / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "evidence" / "gate.md").write_text("fake test evidence\n", encoding="utf-8")
    (tmp_path / "docs/research").mkdir(parents=True, exist_ok=True)
    for rel in (
        "docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md",
        "docs/research/19_GATE_A_CLOSURE_AUDIT.md",
    ):
        shutil.copy(REPO_ROOT / rel, tmp_path / rel)
    (tmp_path / "docs/data").mkdir(parents=True, exist_ok=True)
    for rel in (
        "docs/data/B1_DATA_ROUTE_AUTHORIZATION.md",
        "docs/data/TCIA_DATA_ROUTE_INQUIRY.md",
        "docs/data/B1_EVIDENCE_TEMPLATE.md",
    ):
        shutil.copy(REPO_ROOT / rel, tmp_path / rel)
    (tmp_path / "configs/protocol").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "configs/protocol/protocol_v1.0.yaml", tmp_path / "configs/protocol/")
    # FAKE dataset identity for fake evidence (the real config names the real dataset)
    cfg = yaml.safe_load((REPO_ROOT / "configs/dataset/brats2021.yaml").read_text(encoding="utf-8"))
    cfg["evidence_identity"] = {
        "dataset": "FAKE",
        "doi": "10.0000/fake",
        "official_source_prefixes": ["https://fake.invalid/"],
    }
    (tmp_path / "configs/dataset").mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs/dataset/brats2021.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    shutil.copy(
        REPO_ROOT / "configs/dataset/brats2021_crosswalk.yaml", tmp_path / "configs/dataset/"
    )


def make_status_repo(tmp_path: Path, closed: set[str]) -> Path:
    """A temporary *fake* (non-git) repository whose status passes/closes the given gates.

    Used only to test positive paths. B1 gets fake B1 evidence; B2-B6 get a
    linked, schema-valid FAKE evidence chain (tests/fixtures/fake_evidence.py);
    other gates get a placeholder document. Newly eligible B gates are unlocked.
    """
    raw = yaml.safe_load(PENDING_STATUS.read_text(encoding="utf-8"))
    _copy_basics(tmp_path)
    chain = build_fake_chain(tmp_path) if closed & {"B2", "B3", "B4", "B5", "B6"} else {}
    for g in raw["gates"]:
        gid = g["id"]
        if gid in closed:
            g["status"] = "PASSED" if gid in B_GATES else "CLOSED"
            if gid == "B1":
                g["evidence"] = write_b1_evidence(tmp_path)
            else:
                g["evidence"] = chain.get(gid, "evidence/gate.md")
            g["closed_on"] = "2000-01-01"
    status_of = unlock_eligible({g["id"]: g["status"] for g in raw["gates"] if g["id"] in B_GATES})
    for g in raw["gates"]:
        if g["id"] in status_of:
            g["status"] = status_of[g["id"]]
    if "B1" in closed:
        raw["data"]["authorization"] = "APPROVED"
        raw["data"]["approved_route"] = FAKE_ROUTE
    if "B2" in closed:
        raw["data"]["acquired"] = True
    (tmp_path / "docs/project_status.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return tmp_path


def make_verbatim_status_repo(tmp_path: Path) -> Path:
    """Fake repository with a byte-identical copy of the pre-B1 status file (line-edit tests)."""
    _copy_basics(tmp_path)
    shutil.copy(PENDING_STATUS, tmp_path / "docs/project_status.yaml")
    return tmp_path


def dataset_cfg(repo_root: Path) -> dict:  # type: ignore[type-arg]
    """The real dataset config with the confirmed crosswalk mapping merged in (for
    synthetic configs written to a temporary path without the mapping file beside them)."""
    from brats_uncertainty.data.crosswalk import load_crosswalk_config

    path = repo_root / "configs/dataset/brats2021.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["crosswalk"] = load_crosswalk_config(path)
    return cfg  # type: ignore[no-any-return]


PRE_EXECUTION_STATUS = Path(__file__).parent / "fixtures/pre_execution/project_status.yaml"
_MIRROR_IGNORE = shutil.ignore_patterns(
    ".git",
    "node_modules",
    ".next",
    "out",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "*.egg-info",
)


@pytest.fixture(scope="session")
def pre_execution_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A non-git mirror of the repository frozen at its pre-execution state.

    ``docs/project_status.yaml`` is the exact file of commit 724d181 (B1 PASSED, B2
    AUTHORIZED, B3-B12 LOCKED, no data acquired), the B2-B6 execution records are
    absent and the website data are regenerated from that status. Lifecycle-rule tests
    use it so they do not depend on how far the real study has progressed; the live
    state is checked by the state-agnostic validation tests.
    """
    from brats_uncertainty.results.site_export import export_site_data

    root = tmp_path_factory.mktemp("pre_execution") / "repo"
    shutil.copytree(REPO_ROOT, root, ignore=_MIRROR_IGNORE)
    shutil.copy(PRE_EXECUTION_STATUS, root / "docs/project_status.yaml")
    for rec in (root / "docs/data/records").glob("*"):
        if rec.name.startswith(("B2", "B3", "B4", "B5", "B6", "B7")):
            shutil.rmtree(rec) if rec.is_dir() else rec.unlink()
    export_site_data(root)
    return root
