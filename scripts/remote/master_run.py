"""Master execution entry point: ``python scripts/remote/master_run.py [options]``.

Thin wrapper around ``brats-uncertainty master-run`` (logic and tests live in
``brats_uncertainty.orchestration``). Runs every permitted gate and run of the
frozen protocol in order, resumes across sessions, and stops only at a genuine
blocker, printing the exact gate, blocker and action. Typical use on the private
persistent GPU VM::

    export BRATS_WORK=/data/brats_work          # persistent private storage
    export BRATS_OFFICIAL_DELIVERY=/data/delivery   # official TCIA delivery (route B)
    python scripts/remote/master_run.py --resume --commit --push
"""

from __future__ import annotations

import sys

from brats_uncertainty.cli import main

if __name__ == "__main__":
    sys.exit(main(["master-run", *sys.argv[1:]]))
