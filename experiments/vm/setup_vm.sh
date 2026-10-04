#!/usr/bin/env bash
# Private GPU VM / workstation setup for protocol v1.0 (Linux + NVIDIA CUDA).
# Installs the research package at an exact commit and probes the environment.
# Downloads NO study data. The official transfer client is installed by the owner
# (IBM aspera-cli README: `gem install aspera-cli`, `ascli config transferd install`).
#
# Usage: REPO_URL=<https url> COMMIT=<sha or tag> WORK=/data/brats bash setup_vm.sh
set -euo pipefail
: "${REPO_URL:?set REPO_URL}"
: "${COMMIT:?set COMMIT (exact sha or tag, never a moving branch)}"
WORK="${WORK:-$HOME/brats_private}"   # private, access-restricted disk; never a shared/public path
mkdir -p "$WORK" "$WORK/export"
chmod 700 "$WORK"

if [ ! -d "$WORK/repo/.git" ]; then
  git clone --quiet "$REPO_URL" "$WORK/repo"
fi
cd "$WORK/repo"
git fetch --quiet --all --tags
git checkout --quiet "$COMMIT"
git rev-parse HEAD

python3 -m venv "$WORK/venv"
# shellcheck disable=SC1091
source "$WORK/venv/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -e ".[io,nnunet]"

brats-uncertainty verify-protocol
brats-uncertainty compute-preflight --work-dir "$WORK" --json "$WORK/export/probe_general.json" || true
brats-uncertainty compute-preflight --job JOB-01 --work-dir "$WORK" --json "$WORK/export/probe_JOB-01.json" || true
brats-uncertainty compute-preflight --job JOB-02 --work-dir "$WORK" --json "$WORK/export/probe_JOB-02.json" || true
echo "Probe reports: $WORK/export (no data, no credentials). Next: docs/reproducibility/REMOTE_COMPUTE.md"
