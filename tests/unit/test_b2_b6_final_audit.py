"""Final B2-B6 audit: stale evidence, identity, git history, atomicity, links, B6 states.

Everything runs on SYNTHETIC_TEST_DATA or FAKE evidence inside pytest temporary
directories (including throw-away git repositories). The real repository is
only read.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from brats_uncertainty.data.acquisition import (
    LocalImportAdapter,
    SyntheticFixtureAdapter,
    stage_acquire,
)
from brats_uncertainty.data.integrity import validate_dataset_tree
from brats_uncertainty.data.manifest_doc import content_sha256, validate_manifest_doc
from brats_uncertainty.data.records import (
    B6_TARGETS,
    COUNT_STATES,
    AcquisitionRecord,
    CountsRecord,
    HashedFile,
    InventoryEntry,
    ProvenanceStamp,
    SourceInfo,
    read_counts_record,
    read_record_body,
    record_body,
    write_record,
)
from brats_uncertainty.data.stages import (
    stage_build_manifest,
    stage_hash_metadata,
    stage_validate_data,
)
from brats_uncertainty.data.synthetic import (
    MARKER_NAME,
    generate_synthetic_dataset,
    require_synthetic,
)
from brats_uncertainty.errors import ConfigError, DataValidationError, ProvenanceError
from brats_uncertainty.evaluation.lifecycle import apply_transition
from brats_uncertainty.evaluation.status import load_status, validate_status
from brats_uncertainty.evaluation.transitions import write_transition
from brats_uncertainty.results.site_export import build_count_block, count_verification_state
from brats_uncertainty.utils.hashing import sha256_bytes, sha256_file
from brats_uncertainty.utils.io import write_json
from brats_uncertainty.utils.paths import is_link
from tests.conftest import (
    FAKE_ROUTE,
    make_status_repo,
    make_verbatim_status_repo,
    pending_raw,
)
from tests.fixtures.fake_evidence import (
    FAKE_SCHEMA,
    PROTOCOL_SHA,
    fake_source,
    fake_stamp,
    write_b1_evidence,
)

SYN_URL = "https://synthetic.invalid/source"
FIXED = datetime(2000, 1, 1, tzinfo=UTC)
SRC = Path(__file__).resolve().parents[2] / "src" / "brats_uncertainty"


def _clock() -> datetime:
    return FIXED


def _b(n: int) -> set[str]:
    return {f"B{i}" for i in range(1, n + 1)}


def _passing_b2(root: Path, rel: str, **changes: object) -> dict:  # type: ignore[type-arg]
    """Write a B2 record into the fake repo and return a status mapping that passes B2 on it."""
    base = AcquisitionRecord(
        gate="B2",
        synthetic=False,
        source=fake_source(),
        adapter="local-import",
        acquired_at="2000-01-01T00:00:00+00:00",
        acquired_by="pytest",
        storage_location="data/raw/fake",
        inventory=(InventoryEntry("fake.bin", sha256_bytes(b"fake"), 4),),
        stamp=fake_stamp(),
    )
    rec = dataclasses.replace(base, **changes)  # type: ignore[arg-type]
    write_record(root / rel, rec)
    raw = apply_transition(load_status(root).raw, "B2", "RUNNING")
    return apply_transition(raw, "B2", "PASSED", evidence=rel, on="2000-01-01")


def _dir_link(link: Path, target: Path) -> None:
    """Directory symlink, or a Windows junction (no privilege needed); else skip."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    pytest.skip("cannot create directory links on this system")


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=pytest", "-c", "user.email=pytest@invalid", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return out.stdout.strip()


# =========================================================== evidence integrity / stale evidence
@pytest.mark.parametrize(
    ("changes", "msg"),
    [
        (
            {
                "source": SourceInfo(
                    "OTHER-DATASET", "v", "10.0000/fake", "https://fake.invalid/x", FAKE_ROUTE
                )
            },
            "describes dataset",
        ),
        (
            {
                "source": SourceInfo(
                    "FAKE", "v", "10.9999/other", "https://fake.invalid/x", FAKE_ROUTE
                )
            },
            "describes dataset",
        ),
        (
            {
                "source": SourceInfo(
                    "FAKE", "v", "10.0000/fake", "https://mirror.example.org/x", FAKE_ROUTE
                )
            },
            "not an official source",
        ),
        ({"stamp": dataclasses.replace(fake_stamp(), protocol_sha256="1" * 64)}, "frozen protocol"),
        ({"stamp": dataclasses.replace(fake_stamp(), protocol_version="v0.5")}, "frozen protocol"),
        ({"stamp": dataclasses.replace(fake_stamp(), code_dirty=True)}, "clean committed"),
        ({"synthetic": True}, "synthetic"),
    ],
)
def test_wrong_dataset_source_protocol_or_class_is_rejected(
    tmp_path: Path, changes: dict, msg: str
) -> None:  # type: ignore[type-arg]
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    bad = _passing_b2(root, "evidence/B2_bad.json", **changes)
    with pytest.raises(ConfigError, match=msg):
        validate_status(bad, root)


def test_valid_fake_b2_evidence_is_accepted(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    validate_status(_passing_b2(root, "evidence/B2_ok.json"), root)


def test_stale_configuration_is_rejected(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    cfg = root / "configs/dataset/brats2021.yaml"
    stamp = dataclasses.replace(
        fake_stamp(), config_sha256={"configs/dataset/brats2021.yaml": sha256_file(cfg)}
    )
    ok = _passing_b2(root, "evidence/B2_cfg.json", stamp=stamp)
    validate_status(ok, root)
    cfg.write_text(
        cfg.read_text(encoding="utf-8") + "# edited after the record\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="stale evidence: configuration"):
        validate_status(ok, root)
    cfg.unlink()
    with pytest.raises(ConfigError, match=r"no longer exists|evidence identity missing"):
        validate_status(ok, root)


def test_wrong_hash_link_between_b3_and_b6_is_rejected(tmp_path: Path) -> None:
    root = make_status_repo(tmp_path / "repo", closed=_b(5))
    good = read_counts_record(root / "evidence/B6_record.json")
    wrong = dataclasses.replace(good, crosswalk_sha256=sha256_bytes(b"a different crosswalk"))
    write_record(root / "evidence/B6_wrong.json", wrong)
    raw = apply_transition(load_status(root).raw, "B6", "RUNNING")
    bad = apply_transition(raw, "B6", "PASSED", evidence="evidence/B6_wrong.json", on="2000-01-01")
    with pytest.raises(ConfigError, match="crosswalk SHA-256 differs"):
        validate_status(bad, root)
    unlinked = dataclasses.replace(good, b3_record_fingerprint=sha256_bytes(b"x"))
    write_record(root / "evidence/B6_unlinked.json", unlinked)
    bad2 = apply_transition(
        raw, "B6", "PASSED", evidence="evidence/B6_unlinked.json", on="2000-01-01"
    )
    with pytest.raises(ConfigError, match="not linked to the B3"):
        validate_status(bad2, root)


def test_evidence_must_be_committed_and_from_current_history(tmp_path: Path) -> None:
    """Real git repository: untracked, ignored, foreign-history and unknown commits are rejected."""
    if shutil.which("git") is None:
        pytest.skip("git not available")
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    (root / ".gitignore").write_text("private/\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fake repo")
    head = _git(root, "rev-parse", "HEAD")
    stamp = dataclasses.replace(fake_stamp(), code_commit=head)
    # 1. untracked evidence
    raw = _passing_b2(root, "evidence/B2_git.json", stamp=stamp)
    with pytest.raises(ConfigError, match="committed or staged"):
        validate_status(raw, root)
    # 2. tracked evidence from the current history: accepted
    _git(root, "add", "evidence/B2_git.json")
    validate_status(raw, root)
    # 3. git-ignored evidence (even if force-added)
    (root / "private").mkdir()
    shutil.copy(root / "evidence/B2_git.json", root / "private/B2.json")
    _git(root, "add", "-f", "private/B2.json")
    ignored = apply_transition(
        apply_transition(load_status(root).raw, "B2", "RUNNING"),
        "B2",
        "PASSED",
        evidence="private/B2.json",
        on="2000-01-01",
    )
    with pytest.raises(ConfigError, match="git-ignored"):
        validate_status(ignored, root)
    # 4. commit that does not exist
    unknown = dataclasses.replace(fake_stamp(), code_commit="e" * 40)
    raw_u = _passing_b2(root, "evidence/B2_unknown.json", stamp=unknown)
    _git(root, "add", "evidence/B2_unknown.json")
    with pytest.raises(ConfigError, match="does not exist"):
        validate_status(raw_u, root)
    # 5. commit from another history (orphan branch): stale
    _git(root, "commit", "-q", "-m", "evidence")
    _git(root, "checkout", "-q", "--orphan", "rewritten")
    _git(root, "commit", "-q", "-m", "rewritten history")
    with pytest.raises(ConfigError, match="not in the history of HEAD"):
        validate_status(raw, root)


def test_b1_pending_to_authorized_or_passed_requires_machine_checkable_evidence(
    repo_root: Path, tmp_path: Path
) -> None:
    raw = pending_raw()  # pre-B1 baseline
    with pytest.raises(ConfigError, match="illegal transition"):
        apply_transition(raw, "B1", "AUTHORIZED")  # B1's authorized state is PASSED, with evidence
    with pytest.raises(ConfigError, match="prerequisites"):
        apply_transition(raw, "B2", "AUTHORIZED")
    root = make_verbatim_status_repo(tmp_path / "repo")
    (root / "docs/data/B1_EVIDENCE_2000-01-01.md").write_text(
        "We have permission, trust me.\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="exactly one"):
        write_transition(
            root,
            "B1",
            "PASSED",
            evidence="docs/data/B1_EVIDENCE_2000-01-01.md",
            on="2000-01-01",
            approved_route=FAKE_ROUTE,
        )


# =========================================================== atomicity
def test_failed_transition_leaves_valid_status_and_no_partial_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_verbatim_status_repo(tmp_path / "repo")
    ev = write_b1_evidence(root)
    before = (root / "docs/project_status.yaml").read_bytes()

    def boom(*a: object, **k: object) -> None:
        raise OSError("simulated power loss")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_transition(
            root,
            "B1",
            "PASSED",
            evidence=ev,
            on="2000-01-01",
            approved_route=FAKE_ROUTE,
            apply=True,
        )
    monkeypatch.undo()
    assert (root / "docs/project_status.yaml").read_bytes() == before
    assert not list((root / "docs").glob("*.part"))
    load_status(root)  # still valid
    assert load_status(root).gate("B1").status == "PENDING"


def test_failed_manifest_csv_write_leaves_no_partial(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = stage_acquire(
        repo_root,
        SyntheticFixtureAdapter(repo_root, n_cases=1),
        storage_root=tmp_path / "acq",
        out_record=tmp_path / "B2.json",
        acquired_by="t",
        execute=True,
        clock=_clock,
    )
    assert isinstance(rec, AcquisitionRecord)
    cfg = yaml.safe_load((repo_root / "configs/dataset/brats2021.yaml").read_text(encoding="utf-8"))
    cfg["layout"]["case_id_pattern"] = r"SYN-\d{4}"
    cfg["layout"]["tree"] = "flat"  # flat synthetic fixture (nested: test_nested_layout.py)
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    real_replace = Path.replace

    def boom(self: Path, target: object) -> Path:
        if str(self).endswith(".csv.part"):
            raise OSError("simulated interruption")
        return real_replace(self, target)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError):
        stage_build_manifest(
            repo_root,
            cfg_path,
            tmp_path / "acq" / "images",
            tmp_path / "B2.json",
            tmp_path / "B5.json",
            out_csv=tmp_path / "B5.csv",
            synthetic=True,
            clock=_clock,
        )
    assert not (tmp_path / "B5.csv").exists()
    assert not (tmp_path / "B5.csv.part").exists()


# =========================================================== path and link safety
def test_write_targets_fail_closed(tmp_path: Path) -> None:
    write_json(tmp_path / "a.json", {"x": 1})
    with pytest.raises(FileExistsError):
        write_json(tmp_path / "a.json", {"x": 2})  # destination already exists
    (tmp_path / "adir").mkdir()
    with pytest.raises(IsADirectoryError):
        write_json(tmp_path / "adir", {"x": 1}, overwrite=True)  # destination is a directory
    target = tmp_path / "protected"
    target.mkdir()
    _dir_link(tmp_path / "link.json", target)
    with pytest.raises(FileExistsError, match="link"):
        write_json(tmp_path / "link.json", {"x": 1}, overwrite=True)  # destination is a link
    assert json.loads((tmp_path / "a.json").read_text(encoding="utf-8")) == {"x": 1}


def test_links_outside_the_permitted_root_are_never_followed(
    repo_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside_protected"
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"data outside the acquisition root")
    # delivered tree containing a link to another directory
    delivered = tmp_path / "delivered"
    delivered.mkdir()
    (delivered / "ok.bin").write_bytes(b"ok")
    _dir_link(delivered / "escape", outside)
    assert is_link(delivered / "escape")
    with pytest.raises(DataValidationError, match="symbolic links"):
        LocalImportAdapter(fake_source(), delivered).plan()
    # the delivered path itself is a link
    _dir_link(tmp_path / "delivered_link", delivered)
    with pytest.raises(DataValidationError, match="link"):
        LocalImportAdapter(fake_source(), tmp_path / "delivered_link").plan()
    # data tree with a linked case directory: reported, not followed
    tree = tmp_path / "tree"
    tree.mkdir()
    _dir_link(tree / "FAKE-001", outside)
    report = validate_dataset_tree(tree, FAKE_SCHEMA)
    assert any(i.code == "link" for i in report.issues)
    assert not report.ok
    # synthetic tree with a link
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    _dir_link(ds.root / "images" / "escape", outside)
    with pytest.raises(ProvenanceError, match="symbolic links"):
        require_synthetic([ds.root / "images"], repo_root)
    with pytest.raises(ProvenanceError, match="symbolic links"):
        stage_validate_data(
            repo_root,
            repo_root / "configs/dataset/brats2021.yaml",
            ds.root / "images",
            synthetic=True,
        )


def test_broken_link_and_linked_storage_root_are_refused(tmp_path: Path) -> None:
    gone = tmp_path / "gone"
    gone.mkdir()
    _dir_link(tmp_path / "broken", gone)
    gone.rmdir()
    assert is_link(tmp_path / "broken")
    with pytest.raises(FileExistsError, match="link"):
        write_json(tmp_path / "broken", {"x": 1}, overwrite=True)
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    target = root / "data" / "real_target"
    target.mkdir(parents=True)
    _dir_link(root / "data" / "linked_store", target)
    d = tmp_path / "d.bin"
    d.write_bytes(b"x")
    with pytest.raises(ProvenanceError, match="storage root may not be a link"):
        stage_acquire(
            root,
            LocalImportAdapter(fake_source(), d),
            storage_root=root / "data" / "linked_store",
            out_record=tmp_path / "r.json",
            acquired_by="t",
            execute=True,
            require_clean_commit=False,
        )


# =========================================================== synthetic / real boundary
def test_synthetic_real_boundary(repo_root: Path, tmp_path: Path) -> None:
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    # synthetic fixture in expected location: accepted by the synthetic pathway
    require_synthetic([ds.crosswalk], repo_root)
    # synthetic file through the REAL acquisition adapter: refused
    root = make_status_repo(tmp_path / "repo", closed=_b(1))
    with pytest.raises(ProvenanceError, match="cannot be acquired through a real-data adapter"):
        stage_acquire(
            root,
            LocalImportAdapter(fake_source(), ds.root),
            storage_root=root / "data" / "raw" / "x",
            out_record=tmp_path / "r.json",
            acquired_by="t",
            execute=True,
            require_clean_commit=False,
        )
    assert not (root / "data" / "raw" / "x").exists()
    # marker copied next to an unrelated real-looking file: refused
    other = tmp_path / "other"
    other.mkdir()
    shutil.copy(ds.root / MARKER_NAME, other / MARKER_NAME)
    (other / "BraTS2021_MappingToTCIA.xlsx").write_bytes(b"real-looking, not generated")
    with pytest.raises(ProvenanceError, match="not a generator-listed"):
        require_synthetic([other / "BraTS2021_MappingToTCIA.xlsx"], repo_root)
    # marker removed: no longer synthetic -> synthetic pathway refuses
    (ds.root / MARKER_NAME).unlink()
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_DATA tree"):
        require_synthetic([ds.crosswalk], repo_root)


# =========================================================== B3/B4 hashing
def test_b3_b4_hash_semantics(repo_root: Path, tmp_path: Path) -> None:
    ds = generate_synthetic_dataset(tmp_path / "syn", repo_root=repo_root, n_cases=1)
    renamed = tmp_path / "renamed_copy.xlsx"
    shutil.copy(ds.crosswalk, renamed)
    assert sha256_file(renamed) == sha256_file(ds.crosswalk)  # rename: same content hash
    assert HashedFile.from_path(renamed).sha256 == HashedFile.from_path(ds.crosswalk).sha256
    with pytest.raises(DataValidationError, match="input not found"):  # missing file
        stage_hash_metadata(
            repo_root,
            "B3",
            ds.root / "metadata" / "nope" / "BraTS2021_MappingToTCIA.xlsx",
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "b3.json",
            synthetic=True,
        )
    with pytest.raises(DataValidationError, match="requires the file"):  # wrong file
        stage_hash_metadata(
            repo_root,
            "B3",
            ds.ucsf_metadata,
            source_url=SYN_URL,
            doi="10.0/x",
            out=tmp_path / "b3.json",
            synthetic=True,
        )
    assert not (tmp_path / "b3.json").exists()


# =========================================================== B5 end to end
def test_b5_end_to_end_deterministic_manifest(repo_root: Path, tmp_path: Path) -> None:
    runs = []
    for k in ("a", "b"):
        base = tmp_path / k
        stage_acquire(
            repo_root,
            SyntheticFixtureAdapter(repo_root, n_cases=2),
            storage_root=base / "acq",
            out_record=base / "B2.json",
            acquired_by="t",
            execute=True,
            clock=_clock,
        )
        # copy the tree of run "a" into run "b" so both manifests describe identical bytes
        if k == "b":
            shutil.rmtree(base / "acq")
            shutil.copytree(tmp_path / "a" / "acq", base / "acq")
            shutil.copy(tmp_path / "a" / "B2.json", base / "B2_a.json")
        meta = base / "acq" / "metadata"
        for gate, name in (
            ("B3", "BraTS2021_MappingToTCIA.xlsx"),
            ("B4", "UCSF-PDGM-metadata_v5.csv"),
        ):
            stage_hash_metadata(
                repo_root,
                gate,
                meta / name,
                source_url=SYN_URL,
                doi="10.0/x",
                out=base / f"{gate}.json",
                synthetic=True,
                clock=_clock,
            )
        cfg = yaml.safe_load(
            (repo_root / "configs/dataset/brats2021.yaml").read_text(encoding="utf-8")
        )
        cfg["layout"]["case_id_pattern"] = r"SYN-\d{4}"
        cfg["layout"]["tree"] = "flat"  # flat synthetic fixture (nested: test_nested_layout.py)
        (base / "cfg.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        acq = base / ("B2_a.json" if k == "b" else "B2.json")
        doc = stage_build_manifest(
            repo_root,
            base / "cfg.yaml",
            base / "acq" / "images",
            acq,
            base / "B5.json",
            out_csv=base / "B5.csv",
            metadata_files=[
                meta / "BraTS2021_MappingToTCIA.xlsx",
                meta / "UCSF-PDGM-metadata_v5.csv",
            ],
            metadata_records=[base / "B3.json", base / "B4.json"],
            synthetic=True,
            clock=_clock,
        )
        reloaded = json.loads((base / "B5.json").read_text(encoding="utf-8"))
        validate_manifest_doc(reloaded)  # schema + hash recomputed from the final fields
        assert reloaded["manifest_sha256"] == content_sha256(reloaded) == doc["manifest_sha256"]
        assert reloaded["data_class"] == "SYNTHETIC_TEST_DATA"
        assert set(reloaded["metadata_records"]) == {"B3", "B4"}
        assert [f["relpath"] for f in reloaded["files"]] == sorted(
            [f["relpath"] for f in reloaded["files"] if f["file_type"] != "metadata"]
        ) + [f["relpath"] for f in reloaded["files"] if f["file_type"] == "metadata"]
        runs.append(reloaded)
    a, b = runs
    assert a["files"] == b["files"]  # deterministic inventory, ordering and hashes
    assert a["duplicates"] == b["duplicates"]
    assert a["manifest_sha256"] == b["manifest_sha256"]
    tampered = json.loads(json.dumps(a))
    tampered["summary"]["total_bytes"] += 1
    with pytest.raises(DataValidationError):
        validate_manifest_doc(tampered)


# =========================================================== B6 states
def test_b6_all_states(repo_root: Path, tmp_path: Path) -> None:
    assert {
        "EXPECTED_BY_PROTOCOL",
        "VERIFIED_FROM_SOURCE",
        "FAILED_VERIFICATION",
        "UNAVAILABLE",
    } <= set(COUNT_STATES)
    # UNAVAILABLE + EXPECTED_BY_PROTOCOL (current repository: nothing processed)
    blk = build_count_block(repo_root, load_status(repo_root).raw)
    assert (blk["status"], blk["verification"]) == ("EXPECTED_BY_PROTOCOL", "UNAVAILABLE")
    assert "counts" not in blk
    # still UNAVAILABLE when B6 is AUTHORIZED but has not run
    r5 = make_status_repo(tmp_path / "r5", closed=_b(5))
    assert count_verification_state(r5, load_status(r5).raw)[0] == "UNAVAILABLE"
    # VERIFIED_FROM_SOURCE only from a PASSED real B6 record
    r6 = make_status_repo(tmp_path / "r6", closed=_b(6))
    blk6 = build_count_block(r6, load_status(r6).raw)
    assert (blk6["status"], blk6["verification"]) == (
        "VERIFIED_FROM_SOURCE",
        "VERIFIED_FROM_SOURCE",
    )
    # FAILED_VERIFICATION after a failed B6
    raw = apply_transition(load_status(r5).raw, "B6", "RUNNING")
    failed = apply_transition(raw, "B6", "FAILED", evidence="evidence/gate.md")
    validate_status(failed, r5)
    assert count_verification_state(r5, failed)[0] == "FAILED_VERIFICATION"
    assert build_count_block(r5, failed)["status"] == "FAILED_VERIFICATION"


def test_expected_counts_can_never_produce_verified(tmp_path: Path) -> None:
    stamp = fake_stamp()
    # counts equal to the targets but the crosswalk is not the hashed B3 file -> cannot be VERIFIED
    with pytest.raises(ProvenanceError):
        CountsRecord(
            "B6",
            False,
            "VERIFIED_FROM_SOURCE",
            "a" * 64,
            False,
            "b" * 64,
            dict(B6_TARGETS),
            dict(B6_TARGETS),
            {k: True for k in B6_TARGETS},
            [],
            {},
            "1",
            "c" * 64,
            "d" * 64,
            stamp,
        ).validate()
    # a PASSED B6 whose evidence is not a verified real record is refused by the display layer
    r6 = make_status_repo(tmp_path / "r6", closed=_b(6))
    body = read_record_body(r6 / "evidence/B6_record.json")
    body["status"] = "SYNTHETIC_TEST_ONLY"
    (r6 / "evidence/B6_record.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ProvenanceError):
        build_count_block(
            r6, yaml.safe_load((r6 / "docs/project_status.yaml").read_text(encoding="utf-8"))
        )
    with pytest.raises(ConfigError):
        load_status(r6)  # and the status file itself no longer validates


# =========================================================== no hidden bypass
def test_no_environment_or_hidden_bypass_in_gated_code() -> None:
    """Gated modules read no environment variables and contain no alternative network paths."""
    gated = ["data", "evaluation"]
    for pkg in gated:
        for py in (SRC / pkg).glob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"))
            names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            names |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            assert "environ" not in names and "getenv" not in names, py
            text = py.read_text(encoding="utf-8")
            for forbidden in (
                "import requests",
                "import kaggle",
                "kaggleapi",
                "import boto",
                "wget ",
                "curl ",
                "shell=true",
                "os.system",
                "subprocess",
            ):
                assert forbidden not in text.lower(), (py, forbidden)
    net = sorted(
        (py for py in SRC.rglob("*.py") if "urlopen" in py.read_text(encoding="utf-8")),
        key=lambda p: p.name,
    )
    # the single gated data download, plus the compute probe's HEAD-only reachability check
    assert [p.name for p in net] == ["acquisition.py", "probe.py"]
    probe = (SRC / "compute" / "probe.py").read_text(encoding="utf-8")
    assert probe.count("urlopen(") == 1 and 'method="HEAD"' in probe  # downloads nothing
    for tree_dir in ("scripts", "website"):
        root = SRC.parents[1] / tree_dir
        for f in root.rglob("*"):
            if (
                f.is_file()
                and f.suffix in (".py", ".ts", ".tsx", ".mjs", ".js")
                and "node_modules" not in f.parts
                and ".next" not in f.parts
                and "out" not in f.parts
            ):
                t = f.read_text(encoding="utf-8", errors="ignore")
                assert "urlopen" not in t and "fetch(" not in t and "requests." not in t, f
    # notebooks only as the generated remote-compute package (equality with the generator and
    # official-host-only URLs are tested in test_remote_compute.py); no alternative tooling
    notebooks = [
        p
        for p in SRC.parents[1].rglob("*.ipynb")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    ]
    for nb in notebooks:
        assert nb.parent == SRC.parents[1] / "experiments" / "kaggle", nb
        t = nb.read_text(encoding="utf-8").lower()
        for forbidden in (
            "requests.",
            "import kaggle",
            "kaggle datasets",
            "kaggleapi",
            "boto",
            "wget ",
        ):
            assert forbidden not in t, (nb.name, forbidden)


def test_record_constructor_hash_shape_is_validated() -> None:
    with pytest.raises(ProvenanceError, match="malformed"):
        AcquisitionRecord(
            "B2",
            False,
            fake_source(),
            "local-import",
            "2000-01-01T00:00:00+00:00",
            "t",
            "data/raw/x",
            (InventoryEntry("a.bin", "TODO-hash", 1),),
            fake_stamp(),
        ).validate()
    stamp = ProvenanceStamp("t", "f" * 40, False, "0.1.0", "v1.0", PROTOCOL_SHA, {}, {})
    assert (
        record_body(
            AcquisitionRecord(
                "B2",
                False,
                fake_source(),
                "local-import",
                "2000-01-01T00:00:00+00:00",
                "t",
                "data/raw/x",
                (InventoryEntry("a.bin", sha256_bytes(b"a"), 1),),
                stamp,
            )
        )["data_class"]
        == "REAL_RESEARCH_DATA"
    )


def test_adapters_cannot_be_executed_directly_without_authorization(
    repo_root: Path, tmp_path: Path
) -> None:
    """Calling adapter.execute() outside stage_acquire still enforces the B1/B2 gate."""
    from brats_uncertainty.data.acquisition import HttpsFileAdapter
    from brats_uncertainty.errors import ResearchGateError

    calls: list[str] = []

    def opener(url: str):  # type: ignore[no-untyped-def]
        calls.append(url)
        raise AssertionError("network must not be reached")

    delivered = tmp_path / "d.bin"
    delivered.write_bytes(b"x")
    pending = make_verbatim_status_repo(tmp_path / "pending")
    for adapter in (
        HttpsFileAdapter(fake_source(), {"m.csv": "https://fake.invalid/m.csv"}, opener=opener),
        LocalImportAdapter(fake_source(), delivered),
    ):
        # before B1 (pre-B1 baseline): locked
        with pytest.raises(ResearchGateError, match="Real-data acquisition is locked"):
            adapter.execute(tmp_path / "store", repo_root=pending)
        # real state (B1 owner-approved, B2 ready): only the approved route may execute
        with pytest.raises(ResearchGateError, match="not the B1-approved route"):
            adapter.execute(tmp_path / "store", repo_root=repo_root)
    assert calls == []
    assert not (tmp_path / "store").exists()
    # the synthetic adapter needs no authorization but still cannot write into the repository
    with pytest.raises(ProvenanceError, match="outside the repository"):
        SyntheticFixtureAdapter(repo_root).execute(
            repo_root / "data" / "raw" / "x", repo_root=repo_root
        )
