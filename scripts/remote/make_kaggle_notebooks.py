"""Generate experiments/kaggle/*.ipynb from this file (reproducible; do not hand-edit them).

The notebooks are a COMPUTE ENVIRONMENT, not a dataset mirror:
- raw data live only in ephemeral session storage (WORK = /tmp/brats) and are deleted
  with the session; they are never saved as notebook output or as a Kaggle Dataset;
- only records, reports, run manifests, checkpoints and result artifacts are written to
  /kaggle/working; the owner copies public-safe artifacts with `export-artifacts` and
  commits evidence from the owner's checkout (gates move only there);
- every research step is the repository's gated CLI at an exact commit; every notebook
  after 00 starts with a gate check and stops if the gate is not open.
The same CLI steps run unchanged on a private VM (experiments/vm/).

Usage: python scripts/remote/make_kaggle_notebooks.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "experiments" / "kaggle"

HEADER = (
    "**Private compute session - not a dataset mirror.** Raw BraTS data come only from "
    "the official TCIA source into ephemeral session storage (`WORK`) and are never "
    "written to notebook output, a Kaggle Dataset, GitHub or the website. B1 basis: "
    "owner-approved alternative (amendment v1.0-A1); no TCIA authorization is claimed. "
    "Enable **GPU** and **Internet** in the notebook settings. Never paste credentials "
    "into a cell; use Kaggle Secrets if a private repository needs a token."
)

PARAMS = """# PARAMETERS - set before running (no secrets here)
REPO_URL = ""   # https URL of this research repository (GitHub)
COMMIT = ""     # exact commit SHA or tag to run (never a moving branch)
WORK = "/tmp/brats"                     # ephemeral session storage (raw data stay here)
EXPORT = "/kaggle/working/export"       # records/reports/artifacts only - never raw data
assert REPO_URL, "set REPO_URL"
assert COMMIT, "set COMMIT"
"""

SETUP = """import os
import subprocess

os.makedirs(WORK, exist_ok=True)
os.makedirs(EXPORT, exist_ok=True)
!git clone --quiet {REPO_URL} /kaggle/working/repo
%cd /kaggle/working/repo
!git checkout --quiet {COMMIT}
!git rev-parse HEAD
!pip install --quiet -e ".[io,nnunet]"
!brats-uncertainty verify-protocol"""


def gate(action: str) -> str:
    return (
        f'r = subprocess.run(["brats-uncertainty", "check-action", "{action}"], '
        "capture_output=True, text=True)\n"
        "print(r.stdout)\n"
        f'assert r.returncode == 0, "gate not open for {action}: stop here"'
    )


def _nb(title: str, cells: list[tuple[str, str]]) -> dict[str, object]:
    out: list[dict[str, object]] = [
        {"cell_type": "markdown", "metadata": {}, "source": f"# {title}\n\n{HEADER}"}
    ]
    for kind, src in cells:
        cell: dict[str, object] = {"cell_type": kind, "metadata": {}, "source": src}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        out.append(cell)
    return {
        "cells": out,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


NOTEBOOKS: dict[str, dict[str, object]] = {
    "00_environment_probe.ipynb": _nb(
        "00 - Environment probe and official-transfer-client test (NO data download)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            (
                "markdown",
                "## Compute preflight\nMeasured GPU/VRAM/CUDA/CPU/RAM/disk/OS/Python/PyTorch/"
                "nnU-Net/git. `NOT_READY` means this environment cannot run the job.",
            ),
            (
                "code",
                "!brats-uncertainty compute-preflight --work-dir {WORK} "
                "--json {EXPORT}/probe_general.json\n"
                "!brats-uncertainty compute-preflight --job JOB-02 --work-dir {WORK} "
                "--json {EXPORT}/probe_JOB-02.json",
            ),
            (
                "markdown",
                "## Official transfer client (IBM Aspera CLI)\nInstalls IBM's official "
                "command-line client into this ephemeral session (IBM/aspera-cli README: "
                "`gem install aspera-cli`, `ascli config transferd install`) and prints its "
                "own Faspex 5 help. **Nothing is transferred here.** Record from the help text "
                "how a public package link is received and whether one folder can be selected. "
                "Notebook 01 uses only a command confirmed this way; otherwise the manual "
                "official delivery path (private VM) applies.",
            ),
            (
                "code",
                "!apt-get -qq update && apt-get -qq install -y ruby-full > /dev/null\n"
                "!gem install aspera-cli --no-document\n"
                "!ascli config transferd install\n"
                "!ascli --version\n"
                "# ascp is installed in ascli's SDK folder, not on PATH (IBM aspera-cli manual)\n"
                "!ascli config ascp show\n"
                "!ascli config ascp info\n"
                "!ascli faspex5 -h 2>&1 | head -200",
            ),
            (
                "code",
                "!brats-uncertainty compute-preflight --job JOB-01 --work-dir {WORK} "
                "--json {EXPORT}/probe_JOB-01.json",
            ),
            (
                "markdown",
                "## Result\nDownload `/kaggle/working/export/` (probe JSON) and the cell "
                "output. They contain no data and no credentials.",
            ),
            (
                "code",
                "# STOP: this notebook only probes. No data transfer, no research step.\n"
                'print("Probe finished. Nothing was downloaded. Continue with notebook 01 only '
                'after the owner has reviewed the probe output.")',
            ),
        ],
    ),
    "01_data_access_and_b2.ipynb": _nb(
        "01 - JOB-01: official data access and B2 (gated: acquire_data)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            ("code", gate("acquire_data")),
            (
                "code",
                "!brats-uncertainty compute-preflight --job JOB-01 --work-dir {WORK} "
                "--json {EXPORT}/probe_JOB-01.json",
            ),
            (
                "markdown",
                "## Storage preflight\nEnter the selection size the transfer client reports "
                "for `BraTS2021_TrainingSet` + `RSNA-ASNR-MICCAI-BraTS-2021.sums`. Never guess. "
                "Continue only on `PREFLIGHT OK`.",
            ),
            (
                "code",
                "SELECTED_GIB = None  # from the transfer client listing\n"
                'assert SELECTED_GIB, "enter the measured selection size"\n'
                'DELIVERY = f"{WORK}/delivery"\n'
                "!brats-uncertainty storage-preflight --selected-gib {SELECTED_GIB} "
                "--delivery-dir {DELIVERY} --storage-dir {WORK}/raw",
            ),
            (
                "markdown",
                "## Official delivery\nSource: the **DOWNLOAD (142GB)** public package on "
                "https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ "
                "(TCIA Faspex). Select ONLY `RSNA-ASNR-MICCAI-BraTS-2021.sums` and "
                "`RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet`; keep the hierarchy "
                "exactly as delivered.\n\n- **A. Runtime acquisition:** set `RECEIVE_CMD` to "
                "the exact command confirmed by notebook 00.\n- **B. Manual official "
                "delivery (private VM):** leave `RECEIVE_CMD` empty; the owner's download must "
                "already be in `DELIVERY`. (Not possible on Kaggle: uploading data would "
                "create a dataset.)",
            ),
            (
                "code",
                'RECEIVE_CMD = ""  # A: confirmed command; B: leave empty\n'
                "os.makedirs(DELIVERY, exist_ok=True)\n"
                "if RECEIVE_CMD:\n"
                "    !{RECEIVE_CMD}\n"
                'pkg = os.path.join(DELIVERY, "RSNA-ASNR-MICCAI-BraTS-2021", '
                '"BraTS2021_TrainingSet")\n'
                'assert os.path.isdir(pkg), "official delivery not found in DELIVERY"',
            ),
            (
                "code",
                "# The two official B3/B4 files, saved byte-for-byte (never opened or re-saved)\n"
                "import urllib.request\n\n"
                "for name, url in [\n"
                '    ("BraTS2021_MappingToTCIA.xlsx", "https://www.cancerimagingarchive.net/'
                'wp-content/uploads/BraTS2021_MappingToTCIA.xlsx"),\n'
                '    ("UCSF-PDGM-metadata_v5.csv", "https://www.cancerimagingarchive.net/'
                'wp-content/uploads/UCSF-PDGM-metadata_v5.csv"),\n'
                "]:\n"
                '    if not os.path.exists(f"{DELIVERY}/{name}"):\n'
                '        urllib.request.urlretrieve(url, f"{DELIVERY}/{name}")\n'
                "!ls -la {DELIVERY}",
            ),
            (
                "code",
                "!brats-uncertainty verify-checksums --sums {DELIVERY}/"
                "RSNA-ASNR-MICCAI-BraTS-2021.sums --root {DELIVERY} "
                "--select RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet "
                "--out {EXPORT}/B2_provider_checksums.json",
            ),
            (
                "code",
                'ROUTE = "Direct official TCIA access into a private, access-restricted '
                'computational environment"\n'
                'ACQUIRED_BY = ""  # owner name\n'
                'VERSION = "Version 1 (2023/08/25)"\n'
                "assert ACQUIRED_BY\n"
                "common = (\n"
                '    f"--adapter local-import --delivered {DELIVERY} "\n'
                '    f\'--dataset-version "{VERSION}" --route "{ROUTE}" \'\n'
                '    f"--storage-root {WORK}/raw "\n'
                "    f'--storage-label \"private compute session storage\" '\n"
                "    f'--acquired-by \"{ACQUIRED_BY}\" --out {EXPORT}/B2.json'\n"
                ")\n"
                "print(common)\n"
                "!brats-uncertainty acquire {common}   # dry run",
            ),
            ("code", "!brats-uncertainty acquire {common} --execute"),
            (
                "markdown",
                "## Hand-over\nDownload `export/` (`B2.json`, `B2_provider_checksums.json`, "
                "probe JSON). The owner reviews them, commits them as evidence and moves B2 "
                "with `gate-transition` in the owner's checkout. Later sessions re-download "
                "and must pass `brats-uncertainty verify-inventory --record B2.json --root "
                "<raw>` before using the data. B3-B6 then follow DATA_PROVENANCE.md §3.",
            ),
        ],
    ),
    "02_grouping_and_split.ipynb": _nb(
        "02 - B7-B12: patient grouping and final split (gated: after B6)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            ("code", gate("compute_t_screen")),
            (
                "markdown",
                "Runs only after B1-B6 have PASSED. Order (protocol §6): B7 T_screen from the "
                "frozen positive-control rule and the pairwise screen -> **B8 manual review "
                "by the two named reviewers (human-only; never automated)** -> B9 frozen "
                "IDs-only groups -> B10 split created once (seed 20260927) -> B11 assertions "
                "-> B12 hashes. Each step is a gated script; outputs go to `EXPORT` for owner "
                "review and commit.",
            ),
            (
                "code",
                "!python scripts/grouping/compute_t_screen.py --help\n"
                "!python scripts/grouping/run_pairwise_screen.py --help\n"
                "!python scripts/grouping/freeze_patient_groups.py --help\n"
                "!python scripts/splitting/create_split.py --help",
            ),
        ],
    ),
    "03_compute_pilot.ipynb": _nb(
        "03 - EXP-001 compute pilot (gated: run_exp001 = B1, B2, D1, D2)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            ("code", gate("run_exp001")),
            (
                "markdown",
                "Specification: docs/experiments/EXP-001_COMPUTE_PILOT_SPEC.md. Development "
                "cases only (site != 1), N = 40 (seed 101), 5-epoch timing runs, no label-based "
                "metric, pilot models discarded. Requires the owner's D1 authorization. The "
                "pilot's raw dataset is built with `build-nnunet-dataset --gate-action "
                "run_exp001` and its runs live under the EXP-001 namespace.",
            ),
            (
                "code",
                "!brats-uncertainty compute-preflight --job JOB-PILOT --work-dir {WORK} "
                "--json {EXPORT}/probe_JOB-PILOT.json",
            ),
        ],
    ),
    "04_training_job.ipynb": _nb(
        "04 - JOB-02..07: one resumable training run (gated: train_main = B1-B12, D1-D6)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            ("code", gate("train_main")),
            (
                "code",
                'JOB = ""             # JOB-02 ... JOB-07 (arm/seed from remote_compute.yaml)\n'
                "DATASET_ID = None    # nnU-Net dataset id\n"
                'DATASET_NAME = ""    # e.g. BraTS2021Dev\n'
                'MANIFEST_SHA256 = ""  # committed B5 manifest_sha256\n'
                'SPLIT_SHA256 = ""     # committed B12 split hash\n'
                'CASE_IDS = ""         # file with the frozen train+validation IDs (B10)\n'
                "RESUME = False       # True only to continue this run's own checkpoint\n"
                'RESULTS_ROOT = "/kaggle/working/nnunet_results"  # run dirs persist as output\n'
                "assert JOB\n"
                "assert DATASET_ID\n"
                "assert MANIFEST_SHA256\n"
                "assert SPLIT_SHA256",
            ),
            (
                "markdown",
                "1. Re-acquire the official files (notebook 01) and run `verify-inventory` "
                "against the committed B2 record.\n2. Build the nnU-Net raw dataset with "
                "provenance, then let nnU-Net plan/preprocess.\n3. To resume after a session "
                "ended: attach the previous output, copy `nnunet_results/` back, set "
                "`RESUME = True`.",
            ),
            (
                "code",
                'RAW = f"{WORK}/nnUNet_raw/Dataset{DATASET_ID:03d}_{DATASET_NAME}"\n'
                'os.environ["nnUNet_raw"] = f"{WORK}/nnUNet_raw"\n'
                'os.environ["nnUNet_preprocessed"] = f"{WORK}/nnUNet_preprocessed"\n'
                "if not os.path.isdir(RAW):\n"
                "    !brats-uncertainty build-nnunet-dataset --training-root "
                "{WORK}/raw/RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet --out {RAW} "
                "--dataset-id {DATASET_ID} --dataset-name {DATASET_NAME} --case-ids {CASE_IDS}\n"
                "    !nnUNetv2_plan_and_preprocess -d {DATASET_ID} -c 3d_fullres "
                "--verify_dataset_integrity",
            ),
            (
                "code",
                'RESUME_FLAG = "--resume" if RESUME else ""\n'
                "!brats-uncertainty compute-preflight --job {JOB} --work-dir {WORK}\n"
                "!brats-uncertainty job-run {JOB} --dataset-id {DATASET_ID} "
                "--results-root {RESULTS_ROOT} --dataset-provenance {RAW}/"
                "conversion_provenance.json --manifest-sha256 {MANIFEST_SHA256} "
                "--split-sha256 {SPLIT_SHA256} {RESUME_FLAG}",
            ),
        ],
    ),
    "05_evaluation_job.ipynb": _nb(
        "05 - JOB-08: evaluation (gated: C gates and the eval-v1 tag)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            ("code", gate("evaluate_internal_test")),
            (
                "markdown",
                "Runs only after B1-B12, D1-D6 and C1-C6 are closed, from the commit tagged "
                "`eval-v1` (SR4). Thresholds come from internal validation only and are frozen "
                "(C5) before any test or external evaluation. Results are written as "
                "`*.metrics.json` (configs/schemas/result_metric.schema.json).",
            ),
            ("code", "!python scripts/evaluation/analyze_primary.py --help"),
        ],
    ),
    "06_results_export.ipynb": _nb(
        "06 - Results export (public-safe artifacts only)",
        [
            ("code", PARAMS),
            ("code", SETUP),
            (
                "markdown",
                "Validates every `*.metrics.json` (synthetic records are refused) and copies "
                "only `.json .csv .md .png .svg .txt` into `export/public`. Checkpoints, "
                "images, labels, archives and raw data are skipped and listed - never copied. "
                "The owner downloads `export/public`, runs `brats-uncertainty export-artifacts` "
                "again into the repository's `results/`, reviews and commits.",
            ),
            (
                "code",
                "# STOP if there are no actual result artifacts: nothing is ever invented\n"
                'RESULTS = "/kaggle/working/results"\n'
                "has_results = os.path.isdir(RESULTS) and any(\n"
                '    name.endswith(".metrics.json") for _, _, names in os.walk(RESULTS) '
                "for name in names\n"
                ")\n"
                'assert has_results, "no *.metrics.json result artifacts exist: stop here"',
            ),
            (
                "code",
                "!brats-uncertainty export-artifacts --source {RESULTS} --dest {EXPORT}/public",
            ),
        ],
    ),
    "99_master_pipeline.ipynb": _nb(
        "99 - Master pipeline launcher (the runner decides every next step)",
        [
            (
                "markdown",
                "Launches `scripts/remote/master_run.py`, the single entry point. The runner "
                "(brats_uncertainty.orchestration, tested) re-derives every gate from "
                "`docs/project_status.yaml`, runs each permitted step in protocol order, "
                "resumes interrupted work, commits and pushes milestones (allow-listed, "
                "public-safe paths only), and stops only at a genuine blocker with the exact "
                "gate, blocker and action. **The preferred full-study environment is a private "
                "persistent GPU VM** (`scripts/remote/run_all.sh`); Kaggle session storage is "
                "ephemeral, so raw data are re-acquired per session and verified against the "
                "committed B2 inventory.",
            ),
            (
                "code",
                "# PARAMETERS - set before running (no secrets here)\n"
                'REPO_URL = ""   # https URL of this research repository (GitHub)\n'
                'BRANCH = "main"  # the runner pushes milestones here\n'
                'WORK = "/tmp/brats"                          # ephemeral raw-data storage\n'
                'STATE = "/kaggle/working/master_state"       # runner journal (output)\n'
                'assert REPO_URL, "set REPO_URL"',
            ),
            (
                "code",
                "import os\n\n"
                "!git clone --quiet --branch {BRANCH} {REPO_URL} /kaggle/working/repo\n"
                "%cd /kaggle/working/repo\n"
                "!git rev-parse HEAD\n"
                '!pip install --quiet -e ".[io,nnunet]"\n'
                "!brats-uncertainty verify-protocol\n"
                'os.environ["BRATS_WORK"] = WORK\n'
                'os.environ["BRATS_STATE_DIR"] = STATE',
            ),
            (
                "code",
                "# Push credential from Kaggle Secrets (never printed, never written to disk)\n"
                "try:\n"
                "    from kaggle_secrets import UserSecretsClient\n\n"
                '    os.environ["GITHUB_TOKEN"] = UserSecretsClient().get_secret("GITHUB_TOKEN")\n'
                "except Exception:\n"
                '    print("no GITHUB_TOKEN secret: milestones are committed but not pushed")',
            ),
            (
                "code",
                "# Official IBM Aspera CLI (needed only for a runtime receive at B2)\n"
                "!apt-get -qq update && apt-get -qq install -y ruby-full > /dev/null\n"
                "!gem install aspera-cli --no-document\n"
                "!ascli config transferd install\n"
                "!ascli config ascp show",
            ),
            (
                "code",
                'PUSH = "--push" if os.environ.get("GITHUB_TOKEN") else ""\n'
                "!python scripts/remote/master_run.py --resume --commit {PUSH}",
            ),
        ],
    ),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in sorted(OUT.glob("*.ipynb")):
        if stale.name not in NOTEBOOKS:
            stale.unlink()
            print(f"removed stale {stale.name}")
    for name, nb in NOTEBOOKS.items():
        (OUT / name).write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
