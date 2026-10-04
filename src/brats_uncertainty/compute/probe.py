"""Compute-environment probe (``brats-uncertainty compute-preflight``).

Collects measured facts about the current machine and classifies it against
``configs/compute/remote_compute.yaml``:

- ``READY``: every requirement is met;
- ``READY_WITH_LIMITS``: usable, with listed limits (e.g. session time limits,
  RAM below the recommendation, a dirty checkout);
- ``NOT_READY``: a hard requirement fails (no CUDA GPU, too little VRAM, RAM or
  disk, a missing package, no internet where a job needs it, protocol hash
  mismatch). The blockers are listed.

The probe never downloads data, never installs anything and never reads
credentials. Internet checks are HEAD requests to the configured URLs.
"""

from __future__ import annotations

import ctypes
import importlib.metadata
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from brats_uncertainty.utils.git import git_commit, git_is_dirty
from brats_uncertainty.utils.io import read_yaml

GIB = 1 << 30
COMPUTE_CONFIG = Path("configs/compute/remote_compute.yaml")
STATUSES = ("READY", "READY_WITH_LIMITS", "NOT_READY")


def detect_environment(env: Mapping[str, str] | None = None) -> str:
    e = os.environ if env is None else env
    if "KAGGLE_KERNEL_RUN_TYPE" in e or "KAGGLE_URL_BASE" in e:
        return "kaggle"
    if "COLAB_RELEASE_TAG" in e or "COLAB_GPU" in e:
        return "colab"
    return "vm"


def _ram_bytes() -> tuple[int | None, int | None]:
    """(total, available) physical memory, or None where it cannot be measured."""
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        vals = {}
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition(":")
            if v.strip().endswith("kB"):
                vals[k] = int(v.split()[0]) * 1024
        return vals.get("MemTotal"), vals.get("MemAvailable")
    if sys.platform == "win32":

        class _Mem(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        windll = getattr(ctypes, "windll")  # noqa: B009 - platform-specific attribute
        if windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return int(m.ullTotalPhys), int(m.ullAvailPhys)
    return None, None


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def _gpu_facts() -> dict[str, Any]:
    """GPU facts from PyTorch if installed, else from nvidia-smi (if present)."""
    out: dict[str, Any] = {
        "source": None,
        "cuda_available": False,
        "name": None,
        "vram_bytes": None,
        "cuda_version": None,
    }
    if importlib.util.find_spec("torch") is not None:
        try:
            import torch

            out["source"] = "torch"
            out["cuda_version"] = torch.version.cuda
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                out.update(cuda_available=True, name=props.name, vram_bytes=int(props.total_memory))
                out["device_count"] = torch.cuda.device_count()
            return out
        except Exception as exc:  # report, do not crash the probe
            out["error"] = f"torch import/query failed: {exc}"
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            res = subprocess.run(
                [smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            first = res.stdout.strip().splitlines()[0]
            name, mem_mib = (s.strip() for s in first.split(","))
            out.update(
                source="nvidia-smi",
                cuda_available=True,
                name=name,
                vram_bytes=int(float(mem_mib)) * (1 << 20),
            )
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            out["error"] = f"nvidia-smi failed: {exc}"
    return out


def _head(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "brats-uncertainty"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:  # reachable, but HEAD refused or redirected
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        return f"UNREACHABLE ({exc})"


def locate_transfer_client(
    tc: Mapping[str, Any],
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, str | None]:
    """Path of each transfer-client executable, or None.

    PATH first. The IBM Aspera CLI installs ``ascp`` into its own SDK folder, not on
    PATH, so an executable with a ``locate`` command is then asked of the client
    itself; the answer counts only if it is an existing file.
    """
    out: dict[str, str | None] = {}
    for exe in tc["executables"]:
        path = which(exe)
        cmd = tc.get("locate", {}).get(exe)
        tool = which(cmd[0]) if path is None and cmd else None
        if tool:
            try:
                res = run([tool, *cmd[1:]], capture_output=True, text=True, timeout=60, check=True)
                lines = [s.strip() for s in str(res.stdout).splitlines() if s.strip()]
                if lines and Path(lines[-1]).is_file():
                    path = lines[-1]
            except (OSError, subprocess.SubprocessError):
                pass
        out[exe] = path
    return out


def collect_facts(
    repo_root: Path,
    work_dir: Path,
    *,
    offline: bool = False,
    head: Callable[[str, float], str] = _head,
) -> dict[str, Any]:
    """Measured facts about this environment (no data access, no installation)."""
    cfg = read_yaml(repo_root / COMPUTE_CONFIG)
    ram_total, ram_avail = _ram_bytes()
    disk = shutil.disk_usage(work_dir if work_dir.exists() else repo_root)
    protocol: dict[str, Any] = {"version": cfg.get("protocol_version")}
    try:
        from brats_uncertainty.protocol import load_protocol

        p = load_protocol(repo_root)  # verifies the frozen file's SHA-256 or raises
        protocol.update(verified=True, sha256=str(p.raw["protocol"]["sha256"]))
    except Exception as exc:  # report, do not crash the probe
        protocol.update(verified=False, error=str(exc))
    urls = cfg["requirements"]["internet"]["probe_urls"]
    client = locate_transfer_client(cfg["requirements"]["transfer_client"])
    return {
        "environment": detect_environment(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "ram_total_bytes": ram_total,
        "ram_available_bytes": ram_avail,
        "work_dir": str(work_dir),
        "disk_free_bytes": disk.free,
        "disk_total_bytes": disk.total,
        "gpu": _gpu_facts(),
        "packages": {d: _version(d) for d in ("torch", "nnunetv2", "nibabel", "openpyxl")},
        "transfer_client": {exe: p is not None for exe, p in client.items()},
        "transfer_client_paths": client,
        "internet": None if offline else {u: head(u, 15.0) for u in urls},
        "git": {"commit": git_commit(repo_root), "dirty": git_is_dirty(repo_root)},
        "protocol": protocol,
    }


@dataclass
class ComputeReport:
    status: str
    environment: str
    job: str | None
    blockers: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def describe(self) -> str:
        f = self.facts
        gpu = f["gpu"]
        lines = [
            f"environment: {self.environment}   job: {self.job or '(none)'}",
            f"python {f['python']}  cpu {f['cpu_count']}  "
            f"RAM {_gib(f['ram_total_bytes'])} (available {_gib(f['ram_available_bytes'])})",
            f"GPU: {gpu['name'] or 'none'}  VRAM {_gib(gpu['vram_bytes'])}  "
            f"CUDA {gpu['cuda_version'] or '-'} (via {gpu['source'] or '-'})",
            f"disk free at {f['work_dir']}: {_gib(f['disk_free_bytes'])}",
            f"packages: {f['packages']}",
            f"transfer client: {f.get('transfer_client_paths', f['transfer_client'])}",
            f"internet: {'not checked (--offline)' if f['internet'] is None else f['internet']}",
            f"git: {f['git']}   protocol: {f['protocol']}",
            *(f"BLOCKER: {b}" for b in self.blockers),
            *(f"LIMIT: {x}" for x in self.limits),
            f"STATUS: {self.status}",
        ]
        return "\n".join(lines)


def _gib(b: int | None) -> str:
    return "unknown" if b is None else f"{b / GIB:.1f} GiB"


def classify(facts: dict[str, Any], cfg: dict[str, Any], job: str | None = None) -> ComputeReport:
    """Apply the configured requirements to measured facts (pure; unit-tested)."""
    req = cfg["requirements"]
    env = str(facts.get("environment", "vm"))
    blockers: list[str] = []
    limits: list[str] = []
    spec = cfg["jobs"].get(job) if job else None
    if job and spec is None:
        raise ValueError(f"unknown job {job!r}; known: {sorted(cfg['jobs'])}")
    needs_gpu = bool(spec["needs_gpu"]) if spec else True
    gpu = facts["gpu"]
    if needs_gpu:
        if not gpu.get("cuda_available"):
            blockers.append("no CUDA GPU available (nnU-Net v2 3d_fullres training/inference)")
        elif gpu.get("vram_bytes") is not None:
            vram = gpu["vram_bytes"] / GIB
            vmin = req["gpu"]["min_vram_gib"]
            if vram < vmin:
                blockers.append(f"GPU memory {vram:.1f} GiB < minimum {vmin} GiB (ESTIMATE)")
            elif vram < req["gpu"]["recommended_vram_gib"]:
                limits.append(f"GPU memory {vram:.1f} GiB below the recommended amount")
        for pkg in ("torch", "nnunetv2"):
            if not facts["packages"].get(pkg):
                blockers.append(f"{pkg} not installed (run the environment setup step)")
    ram = facts.get("ram_total_bytes")
    if ram is None:
        limits.append("system RAM could not be measured")
    elif ram / GIB < req["ram"]["min_gib"]:
        blockers.append(f"RAM {ram / GIB:.1f} GiB < minimum {req['ram']['min_gib']} GiB (ESTIMATE)")
    elif ram / GIB < req["ram"]["recommended_gib"]:
        limits.append(
            f"RAM {ram / GIB:.1f} GiB below the recommended {req['ram']['recommended_gib']} GiB"
        )
    if spec is not None:
        need = float(spec["estimate_min_free_disk_gib"])
        free = facts["disk_free_bytes"] / GIB
        if free < need:
            blockers.append(
                f"free disk {free:.1f} GiB < {need:.0f} GiB needed for {job} (ESTIMATE; "
                "B2 uses the measured selection size via storage-preflight)"
            )
    if facts.get("internet") is None:
        limits.append("internet not checked (--offline)")
    else:
        down = [u for u, r in facts["internet"].items() if r.startswith("UNREACHABLE")]
        if down:
            msg = f"unreachable: {down}"
            if spec is None or spec["kind"] == "b2_acquisition":
                blockers.append(msg)
            else:
                limits.append(msg)
    if spec is not None and spec["kind"] == "b2_acquisition":
        missing = [k for k, ok in facts["transfer_client"].items() if not ok]
        if missing:
            blockers.append(
                f"official transfer client not installed: {missing} "
                f"(install: {' && '.join(req['transfer_client']['install'])})"
            )
    if not facts["protocol"].get("verified"):
        blockers.append(f"frozen protocol not verified: {facts['protocol'].get('error')}")
    if facts["git"].get("commit") is None:
        limits.append("not a git checkout: runs cannot be stamped with a commit")
    elif facts["git"].get("dirty"):
        limits.append("working tree is dirty: real-mode records require a clean commit")
    for name, value in cfg["environments"].get(env, {}).get("planning_limits", {}).items():
        limits.append(f"{env} {name} = {value} (planning value; verify in the account)")
    status = "NOT_READY" if blockers else "READY_WITH_LIMITS" if limits else "READY"
    return ComputeReport(status, env, job, blockers, limits, facts)


def compute_preflight(
    repo_root: Path, *, work_dir: Path | None = None, job: str | None = None, offline: bool = False
) -> ComputeReport:
    cfg = read_yaml(repo_root / COMPUTE_CONFIG)
    facts = collect_facts(repo_root, work_dir or Path.cwd(), offline=offline)
    return classify(facts, cfg, job)
