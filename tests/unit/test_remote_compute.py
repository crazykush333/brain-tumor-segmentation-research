"""Remote compute package: probe classification, resumable training jobs, re-acquisition check,
Kaggle notebooks. No GPU, no network and no data are used (facts are injected)."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from brats_uncertainty.cli import main
from brats_uncertainty.compute.jobs import (
    invalidate_run,
    load_jobs,
    read_manifest,
    run_training_job,
)
from brats_uncertainty.compute.probe import (
    COMPUTE_CONFIG,
    GIB,
    STATUSES,
    classify,
    collect_facts,
    detect_environment,
    locate_transfer_client,
)
from brats_uncertainty.data.records import InventoryEntry, inventory, verify_inventory
from brats_uncertainty.errors import ProvenanceError, ResearchGateError
from brats_uncertainty.models.nnunet import (
    RunSpec,
    run_namespace,
    train_command,
    train_environment,
)
from brats_uncertainty.results.site_export import list_amendments
from tests.conftest import REPO_ROOT

CFG = yaml.safe_load((REPO_ROOT / COMPUTE_CONFIG).read_text(encoding="utf-8"))
H = "a" * 64


def _facts(**over: Any) -> dict[str, Any]:
    f: dict[str, Any] = {
        "environment": "vm",
        "python": "3.11.0",
        "platform": "Linux",
        "cpu_count": 8,
        "ram_total_bytes": 32 * GIB,
        "ram_available_bytes": 28 * GIB,
        "work_dir": "/tmp/brats",
        "disk_free_bytes": 200 * GIB,
        "disk_total_bytes": 500 * GIB,
        "gpu": {
            "source": "torch",
            "cuda_available": True,
            "name": "SYNTHETIC GPU",
            "vram_bytes": 16 * GIB,
            "cuda_version": "12.1",
        },
        "packages": {"torch": "2.3.0", "nnunetv2": "2.5.1", "nibabel": "5.2", "openpyxl": "3.1"},
        "transfer_client": {"ascli": True, "ascp": True},
        "internet": {u: "HTTP 200" for u in CFG["requirements"]["internet"]["probe_urls"]},
        "git": {"commit": "f" * 40, "dirty": False},
        "protocol": {"version": "v1.0", "verified": True},
    }
    f.update(over)
    return f


# ================================================================ probe classification
def test_ready_vm_and_kaggle_limits() -> None:
    assert classify(_facts(), CFG, "JOB-02").status == "READY"
    k = classify(_facts(environment="kaggle"), CFG, "JOB-02")
    assert k.status == "READY_WITH_LIMITS"
    assert any("session_limit_h" in x for x in k.limits)


@pytest.mark.parametrize(
    ("over", "job", "needle"),
    [
        (
            {"gpu": {"cuda_available": False, "name": None, "vram_bytes": None}},
            "JOB-02",
            "no CUDA GPU",
        ),
        (
            {"gpu": {"cuda_available": True, "name": "x", "vram_bytes": 8 * GIB}},
            "JOB-02",
            "GPU memory 8.0 GiB < minimum",
        ),
        ({"ram_total_bytes": int(7.4 * GIB)}, "JOB-02", "RAM 7.4 GiB < minimum"),
        ({"packages": {"torch": "2.3", "nnunetv2": None}}, "JOB-02", "nnunetv2 not installed"),
        ({"disk_free_bytes": 10 * GIB}, "JOB-02", "free disk 10.0 GiB"),
        ({"transfer_client": {"ascli": False, "ascp": False}}, "JOB-01", "transfer client"),
        (
            {"internet": {"https://faspex.cancerimagingarchive.net/": "UNREACHABLE (x)"}},
            "JOB-01",
            "unreachable",
        ),
        ({"protocol": {"verified": False, "error": "hash"}}, "JOB-02", "frozen protocol"),
    ],
)
def test_blockers_make_environment_not_ready(over: dict[str, Any], job: str, needle: str) -> None:
    r = classify(_facts(**over), CFG, job)
    assert r.status == "NOT_READY"
    assert any(needle in b for b in r.blockers), r.blockers


def test_b2_job_needs_no_gpu_but_needs_the_transfer_client() -> None:
    no_gpu = {"gpu": {"cuda_available": False, "name": None, "vram_bytes": None}}
    assert classify(_facts(**no_gpu, packages={}), CFG, "JOB-01").status == "READY"
    r = classify(_facts(**no_gpu), CFG, "JOB-02")
    assert r.status == "NOT_READY"


def test_transfer_client_ascp_located_by_ascli_when_not_on_path(tmp_path: Path) -> None:
    # SYNTHETIC: ascp lives in ascli's SDK folder (not on PATH), as `transferd install` leaves it
    ascp = tmp_path / "sdk" / "ascp"
    ascp.parent.mkdir()
    ascp.write_text("synthetic", encoding="utf-8")
    tc = CFG["requirements"]["transfer_client"]
    on_path = {"ascli": "/synthetic/bin/ascli"}
    calls: list[list[str]] = []

    class _Res:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def run_ok(cmd: list[str], **_: Any) -> _Res:
        calls.append(cmd)
        return _Res(f"{ascp}\n")

    found = locate_transfer_client(tc, which=on_path.get, run=run_ok)
    assert found == {"ascli": "/synthetic/bin/ascli", "ascp": str(ascp)}
    assert calls == [["/synthetic/bin/ascli", "config", "ascp", "show"]]
    # a reported path that is not an existing file does not count
    gone = locate_transfer_client(tc, which=on_path.get, run=lambda c, **_: _Res("/nope/ascp"))
    assert gone["ascp"] is None
    # without ascli nothing is asked and ascp stays missing
    assert locate_transfer_client(tc, which=lambda _: None, run=run_ok)["ascp"] is None
    assert len(calls) == 1
    # ascp already on PATH: the locator is not run
    both = {"ascli": "/b/ascli", "ascp": "/b/ascp"}
    assert locate_transfer_client(tc, which=both.get, run=run_ok)["ascp"] == "/b/ascp"
    assert len(calls) == 1


def test_soft_limits_and_offline() -> None:
    r = classify(_facts(ram_total_bytes=16 * GIB, internet=None), CFG, "JOB-02")
    assert r.status == "READY_WITH_LIMITS"
    assert any("below the recommended" in x for x in r.limits)
    assert any("--offline" in x for x in r.limits)
    down = {"https://pypi.org/simple/nnunetv2/": "UNREACHABLE (x)"}
    assert classify(_facts(internet=down), CFG, "JOB-02").status == "READY_WITH_LIMITS"
    assert classify(_facts(git={"commit": "f" * 40, "dirty": True}), CFG, "JOB-02").limits
    with pytest.raises(ValueError, match="unknown job"):
        classify(_facts(), CFG, "JOB-99")


def test_detect_environment() -> None:
    assert detect_environment({"KAGGLE_KERNEL_RUN_TYPE": "Interactive"}) == "kaggle"
    assert detect_environment({"COLAB_RELEASE_TAG": "x"}) == "colab"
    assert detect_environment({}) == "vm"


def test_collect_facts_uses_head_requests_only(tmp_path: Path) -> None:
    seen: list[str] = []

    def fake_head(url: str, timeout: float) -> str:
        seen.append(url)
        return "HTTP 200"

    facts = collect_facts(REPO_ROOT, tmp_path, head=fake_head)
    assert seen == CFG["requirements"]["internet"]["probe_urls"]
    assert all(u.startswith("https://") for u in seen)
    assert facts["protocol"]["verified"] is True
    assert set(facts) >= {"gpu", "ram_total_bytes", "disk_free_bytes", "packages", "git"}
    assert collect_facts(REPO_ROOT, tmp_path, offline=True, head=fake_head)["internet"] is None
    assert len(seen) == len(CFG["requirements"]["internet"]["probe_urls"])


def test_compute_preflight_cli_writes_report(tmp_path: Path) -> None:
    out = tmp_path / "probe.json"
    rc = main(["compute-preflight", "--offline", "--work-dir", str(tmp_path), "--json", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] in STATUSES
    assert rc == (1 if report["status"] == "NOT_READY" else 0)


# ================================================================ training runs
def test_run_namespaces_never_collide(tmp_path: Path) -> None:
    runs = [RunSpec(a, s) for a in "AB" for s in (0, 1, 2)]
    dirs = {run_namespace(tmp_path, e, r) for e in ("MAIN", "EXP-001") for r in runs}
    dirs |= {run_namespace(tmp_path, "EXP-001", r, label="P2") for r in runs}
    assert len(dirs) == 18  # 6 runs x (MAIN, EXP-001, EXP-001/P2): all distinct
    assert run_namespace(tmp_path, "MAIN", RunSpec("B", 2)) == tmp_path / "MAIN" / "arm_b_seed_2"
    for bad in ("main", "../X", "MAIN/x", ""):
        with pytest.raises(ValueError):
            run_namespace(tmp_path, bad, RunSpec("A", 0))
    with pytest.raises(ValueError):
        run_namespace(tmp_path, "EXP-001", RunSpec("A", 0), label="../x")
    env = train_environment(RunSpec("B", 2), tmp_path / "MAIN" / "arm_b_seed_2")
    assert env["nnUNet_results"].endswith("arm_b_seed_2") and env["BRATS_UNC_SEED"] == "2"
    assert "nnUNet_results" not in train_environment(RunSpec("A", 0))
    assert train_command(501, RunSpec("A", 0))[-1] != "--c"
    assert train_command(501, RunSpec("A", 0), resume=True)[-1] == "--c"


def test_job_plan_comes_from_the_frozen_training_config() -> None:
    jobs = load_jobs(REPO_ROOT)
    training = [j for j in jobs.values() if j.kind == "training"]
    assert sorted((j.arm, j.seed) for j in training) == [
        ("A", 0),
        ("A", 1),
        ("A", 2),
        ("B", 0),
        ("B", 1),
        ("B", 2),
    ]
    assert {j.experiment_id for j in training} == {"MAIN"}
    assert all(j.gated_action == "train_main" for j in training)
    assert jobs["JOB-PILOT"].experiment_id == "EXP-001"
    assert jobs["JOB-PILOT"].gated_action == "run_exp001"
    assert jobs["JOB-GROUPING"].gated_action == "compute_t_screen"
    assert jobs["JOB-01"].gated_action == "acquire_data" and not jobs["JOB-01"].needs_gpu
    tc = yaml.safe_load((REPO_ROOT / "configs/experiments/main_training.yaml").read_text("utf-8"))
    assert tc["epochs"] == 250 and tc["seeds"] == [0, 1, 2]
    assert tc["configuration"] == "3d_fullres"
    assert tc["arms"]["B"]["modality_dropout"]["p_full"] == 0.5
    assert {j.run.trainer for j in training} == {
        tc["arms"]["A"]["trainer"],
        tc["arms"]["B"]["trainer"],
    }


def _prov(tmp_path: Path, data_class: str = "SYNTHETIC_TEST_DATA") -> Path:
    p = tmp_path / f"prov_{data_class}.json"
    p.write_text(
        json.dumps({"kind": "nnunet_raw_dataset_conversion", "data_class": data_class}),
        encoding="utf-8",
    )
    return p


def _kw(tmp_path: Path, **over: Any) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "dataset_id": 501,
        "results_root": tmp_path / "res",
        "dataset_provenance": _prov(tmp_path),
        "manifest_sha256": H,
        "split_sha256": "b" * 64,
        "synthetic_test_mode": True,
    }
    kw.update(over)
    return kw


def _ckpt(run_dir: Path, name: str, content: bytes = b"synthetic checkpoint") -> Path:
    p = run_dir / "Dataset501_X" / "Trainer__plans__3d_fullres" / "fold_0" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_resume_requires_flag_and_verified_checkpoint(tmp_path: Path) -> None:
    job = load_jobs(REPO_ROOT)["JOB-05"]  # arm B seed 0
    run_dir = tmp_path / "res" / "MAIN" / "arm_b_seed_0"
    calls: list[list[str]] = []

    def stops(cmd: list[str], env: dict[str, str]) -> int:
        calls.append(list(cmd))
        assert env["nnUNet_results"] == str(run_dir)
        _ckpt(run_dir, "checkpoint_latest.pth")
        return 1

    def finishes(cmd: list[str], env: dict[str, str]) -> int:
        calls.append(list(cmd))
        _ckpt(run_dir, "checkpoint_final.pth")
        return 0

    m = run_training_job(REPO_ROOT, job, runner=stops, **_kw(tmp_path))  # type: ignore[arg-type]
    assert m["status"] == "FAILED" and "--c" not in calls[0]
    assert m["checkpoint"]["path"].endswith("checkpoint_latest.pth")
    with pytest.raises(ProvenanceError, match="pass --resume"):  # never silently continued
        run_training_job(REPO_ROOT, job, runner=finishes, **_kw(tmp_path))  # type: ignore[arg-type]
    m = run_training_job(  # type: ignore[arg-type]
        REPO_ROOT, job, runner=finishes, resume=True, **_kw(tmp_path)
    )
    assert m["status"] == "COMPLETED" and calls[-1][-1] == "--c"
    assert m["attempts"][1]["resumed_from"].endswith("checkpoint_latest.pth")
    assert m["checkpoint_path"].endswith("checkpoint_final.pth")
    assert {"checkpoint_final.pth", "checkpoint_latest.pth"} <= {
        Path(a).name for a in m["artifact_paths"]
    }
    for field in (
        "experiment_id",
        "arm",
        "seed",
        "protocol_version",
        "git_commit",
        "dataset_manifest_sha256",
        "split_sha256",
        "config_sha256",
        "environment_hash",
        "hardware",
        "start_time",
        "end_time",
        "status",
        "checkpoint_path",
        "artifact_paths",
    ):
        assert field in m, field
    assert read_manifest(run_dir) == m
    with pytest.raises(ProvenanceError, match="COMPLETED"):
        run_training_job(  # type: ignore[arg-type]
            REPO_ROOT, job, runner=finishes, resume=True, **_kw(tmp_path)
        )


def test_checkpoint_and_identity_mismatch_fail_closed(tmp_path: Path) -> None:
    job = load_jobs(REPO_ROOT)["JOB-02"]
    run_dir = tmp_path / "res" / "MAIN" / "arm_a_seed_0"

    def stops(cmd: list[str], env: dict[str, str]) -> int:
        _ckpt(run_dir, "checkpoint_latest.pth")
        return 1

    run_training_job(REPO_ROOT, job, runner=stops, **_kw(tmp_path))  # type: ignore[arg-type]
    ok = lambda c, e: 0  # noqa: E731
    with pytest.raises(ProvenanceError, match="belongs to another configuration"):
        run_training_job(  # type: ignore[arg-type]
            REPO_ROOT, job, runner=ok, resume=True, **_kw(tmp_path, split_sha256="c" * 64)
        )
    with pytest.raises(ProvenanceError, match="belongs to another configuration"):
        run_training_job(  # type: ignore[arg-type]
            REPO_ROOT, job, runner=ok, resume=True, **_kw(tmp_path, manifest_sha256="d" * 64)
        )
    _ckpt(run_dir, "checkpoint_latest.pth", b"swapped checkpoint")
    with pytest.raises(ProvenanceError, match="checkpoint changed"):
        run_training_job(REPO_ROOT, job, runner=ok, resume=True, **_kw(tmp_path))  # type: ignore[arg-type]
    invalidate_run(run_dir, "checkpoint swapped (test)")
    with pytest.raises(ProvenanceError, match="INVALIDATED"):
        run_training_job(REPO_ROOT, job, runner=ok, resume=True, **_kw(tmp_path))  # type: ignore[arg-type]


def test_foreign_checkpoints_and_bad_resume_are_refused(tmp_path: Path) -> None:
    job = load_jobs(REPO_ROOT)["JOB-03"]
    run_dir = tmp_path / "res" / "MAIN" / "arm_a_seed_1"
    _ckpt(run_dir, "checkpoint_latest.pth")  # appeared without a run manifest
    with pytest.raises(ProvenanceError, match="unknown provenance"):
        run_training_job(REPO_ROOT, job, resume=True, **_kw(tmp_path))
    job2 = load_jobs(REPO_ROOT)["JOB-04"]
    with pytest.raises(ProvenanceError, match="no earlier attempt"):
        run_training_job(REPO_ROOT, job2, resume=True, **_kw(tmp_path))


def test_failure_without_checkpoint_needs_explicit_restart(tmp_path: Path) -> None:
    job = load_jobs(REPO_ROOT)["JOB-06"]
    m = run_training_job(REPO_ROOT, job, runner=lambda c, e: 2, **_kw(tmp_path))  # type: ignore[arg-type]
    assert m["status"] == "FAILED" and m["checkpoint"] is None
    with pytest.raises(ProvenanceError, match="never silent"):
        run_training_job(REPO_ROOT, job, runner=lambda c, e: 0, **_kw(tmp_path))  # type: ignore[arg-type]

    def crash(c: list[str], e: dict[str, str]) -> int:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_training_job(  # type: ignore[arg-type]
            REPO_ROOT, job, runner=crash, restart_without_checkpoint=True, **_kw(tmp_path)
        )
    m2 = read_manifest(tmp_path / "res" / "MAIN" / "arm_b_seed_1")
    assert m2 is not None and m2["status"] == "FAILED"
    assert [a["action"] for a in m2["attempts"]] == ["start", "restart"]


def test_seeds_and_experiments_keep_separate_manifests(tmp_path: Path) -> None:
    jobs = load_jobs(REPO_ROOT)
    for jid in ("JOB-02", "JOB-03", "JOB-04"):
        run_training_job(REPO_ROOT, jobs[jid], runner=lambda c, e: 1, **_kw(tmp_path))  # type: ignore[arg-type]
    seeds = sorted(
        read_manifest(d)["seed"]  # type: ignore[index]
        for d in (tmp_path / "res" / "MAIN").iterdir()
    )
    assert seeds == [0, 1, 2]


def test_modes_and_gates(tmp_path: Path, repo_root: Path) -> None:
    job = load_jobs(repo_root)["JOB-02"]
    with pytest.raises(ResearchGateError):  # real mode: train_main is not authorized now
        run_training_job(
            repo_root,
            job,
            runner=lambda c, e: pytest.fail("must not run"),  # type: ignore[arg-type]
            **_kw(tmp_path, synthetic_test_mode=False),
        )
    with pytest.raises(ProvenanceError, match="SYNTHETIC_TEST_DATA in this mode"):
        run_training_job(  # synthetic test mode never accepts a real dataset record
            repo_root,
            job,
            **_kw(tmp_path, dataset_provenance=_prov(tmp_path, "REAL_RESEARCH_DATA")),
        )
    with pytest.raises(ProvenanceError, match="outside the repository"):
        run_training_job(repo_root, job, **_kw(tmp_path, results_root=repo_root / "x"))
    with pytest.raises(ProvenanceError, match="SHA-256"):
        run_training_job(repo_root, job, **_kw(tmp_path, manifest_sha256="abc"))
    assert not (repo_root / "x").exists()


# ================================================================ re-acquisition check
def test_verify_inventory(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.bin").write_bytes(b"x")
    (tmp_path / "y.bin").write_bytes(b"y")
    inv = inventory(tmp_path)
    assert verify_inventory(inv, tmp_path) == {"missing": [], "mismatched": [], "unexpected": []}
    (tmp_path / "a" / "x.bin").write_bytes(b"changed")
    (tmp_path / "y.bin").unlink()
    (tmp_path / "z.bin").write_bytes(b"z")
    assert verify_inventory(inv, tmp_path) == {
        "missing": ["y.bin"],
        "mismatched": ["a/x.bin"],
        "unexpected": ["z.bin"],
    }
    assert verify_inventory([InventoryEntry("q", "0" * 64, 1)], tmp_path)["missing"] == ["q"]


# ================================================================ notebooks and docs
def _load_generator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "mk", REPO_ROOT / "scripts/remote/make_kaggle_notebooks.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_notebooks_are_generated_and_safe() -> None:
    gen = _load_generator()
    kdir = REPO_ROOT / "experiments/kaggle"
    for name, nb in gen.NOTEBOOKS.items():
        on_disk = json.loads((kdir / name).read_text(encoding="utf-8"))
        assert on_disk == json.loads(json.dumps(nb)), f"{name} is stale: rerun the generator"
        text = (kdir / name).read_text(encoding="utf-8")
        for bad in ("kaggle datasets", "kaggle.json", "password", "api_key", "dataset-metadata"):
            assert bad not in text.lower(), (name, bad)
        hosts = set(re.findall(r"https://([a-z0-9.-]+)", text))
        assert hosts <= {"www.cancerimagingarchive.net"}, (name, hosts)
    assert sorted(p.name for p in kdir.glob("*.ipynb")) == sorted(gen.NOTEBOOKS)
    assert sorted(gen.NOTEBOOKS) == [
        "00_environment_probe.ipynb",
        "01_data_access_and_b2.ipynb",
        "02_grouping_and_split.ipynb",
        "03_compute_pilot.ipynb",
        "04_training_job.ipynb",
        "05_evaluation_job.ipynb",
        "06_results_export.ipynb",
        "99_master_pipeline.ipynb",
    ]
    master = json.loads((kdir / "99_master_pipeline.ipynb").read_text(encoding="utf-8"))
    master_code = "\n".join(c["source"] for c in master["cells"] if c["cell_type"] == "code")
    assert "scripts/remote/master_run.py --resume --commit" in master_code
    assert "print(os.environ" not in master_code and "--force" not in master_code
    probe_nb = json.loads((kdir / "00_environment_probe.ipynb").read_text(encoding="utf-8"))
    code = "\n".join(c["source"] for c in probe_nb["cells"] if c["cell_type"] == "code")
    for downloading in ("acquire", "urlretrieve", "RECEIVE_CMD", "--execute", "packages receive"):
        assert downloading not in code, downloading  # the probe notebook transfers no data
    gates = {
        "01_data_access_and_b2.ipynb": "acquire_data",
        "02_grouping_and_split.ipynb": "compute_t_screen",
        "03_compute_pilot.ipynb": "run_exp001",
        "04_training_job.ipynb": "train_main",
        "05_evaluation_job.ipynb": "evaluate_internal_test",
    }
    for name, action in gates.items():
        cells = json.loads((kdir / name).read_text(encoding="utf-8"))["cells"]
        code_cells = [c["source"] for c in cells if c["cell_type"] == "code"]
        # the gate check runs right after parameters + setup, before any other step
        assert f'"check-action", "{action}"' in code_cells[2], name
        assert "assert r.returncode == 0" in code_cells[2], name


def _python_of(cell: str) -> str:
    """Notebook cell -> plain Python: IPython shell/magic lines become `pass` (indent kept)."""
    out = []
    for line in cell.splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        out.append(f"{indent}pass" if stripped.startswith(("!", "%")) else line)
    return "\n".join(out) + "\n"


def test_notebook_code_cells_are_valid_python() -> None:
    for nb_path in sorted((REPO_ROOT / "experiments/kaggle").glob("*.ipynb")):
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        assert nb["nbformat"] == 4 and nb["cells"][0]["cell_type"] == "markdown"
        for i, cell in enumerate(nb["cells"]):
            assert cell["cell_type"] in ("markdown", "code"), (nb_path.name, i)
            if cell["cell_type"] == "code":
                assert cell["outputs"] == [] and cell["execution_count"] is None
                compile(_python_of(cell["source"]), f"{nb_path.name}[{i}]", "exec")


def test_every_notebook_has_explicit_gate_or_stop_behaviour() -> None:
    kdir = REPO_ROOT / "experiments/kaggle"

    def code(name: str) -> list[str]:
        cells = json.loads((kdir / name).read_text(encoding="utf-8"))["cells"]
        return [c["source"] for c in cells if c["cell_type"] == "code"]

    for name in sorted(p.name for p in kdir.glob("*.ipynb")):
        cells = code(name)
        assert 'assert REPO_URL, "set REPO_URL"' in cells[0], name  # stops without a target
        if name == "99_master_pipeline.ipynb":
            # the runner commits milestones, so it works on the branch; every record it
            # writes is stamped with the exact commit (printed right after checkout)
            assert "BRANCH = " in cells[0] and "git rev-parse HEAD" in cells[1]
            continue
        assert 'assert COMMIT, "set COMMIT"' in cells[0], name
    assert "STOP: this notebook only probes" in code("00_environment_probe.ipynb")[-1]
    export = code("06_results_export.ipynb")
    stop = next(i for i, c in enumerate(export) if "no *.metrics.json result artifacts" in c)
    run = next(i for i, c in enumerate(export) if "export-artifacts" in c)
    assert stop < run  # export only after real result artifacts are confirmed to exist


def test_amendment_list_excludes_administrative_entries(repo_root: Path) -> None:
    assert [a["id"] for a in list_amendments(repo_root)] == ["v1.0-A1", "v1.0-A2"]
    assert (
        repo_root / "docs/research/protocol-amendments/2026-10-01_compute-environment.md"
    ).is_file()
