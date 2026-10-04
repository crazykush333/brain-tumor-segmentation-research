#!/usr/bin/env bash
# Run (or resume) the whole frozen protocol on this machine. Stops only at a genuine
# blocker and prints the exact gate, blocker and action. Requires BRATS_WORK (persistent
# private storage outside the repository). Credentials: an existing git credential
# helper, or GITHUB_TOKEN in the environment (never written anywhere).
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${BRATS_WORK:?set BRATS_WORK to persistent private storage outside the repository}"
python -m brats_uncertainty.cli verify-protocol
python -m brats_uncertainty.cli check-repo
exec python scripts/remote/master_run.py --resume --commit --push "$@"
