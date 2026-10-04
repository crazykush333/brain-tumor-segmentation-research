# experiments/

One directory per registered experiment (`EXP-xxx/metadata.yaml`), validated by
`brats_uncertainty.experiments.metadata`. Status lifecycle:
PLANNED -> AUTHORIZED -> RUNNING -> COMPLETED | FAILED, and any of these -> INVALIDATED.
An experiment cannot be AUTHORIZED without an owner authorization record, and cannot be
COMPLETED without full provenance and output hashes.

| ID | Status | Description |
|---|---|---|
| EXP-001 | PLANNED (not authorized, not run) | Compute pilot; see docs/experiments/EXP-001_COMPUTE_PILOT_SPEC.md |

Remote execution packages (compute environments only; no data and no results are stored here):

- [`kaggle/`](kaggle/README.md): notebooks 00–06 (00 runnable now; the others are gated);
- [`vm/`](vm/README.md): private NVIDIA GPU VM, with the same CLI steps.

Training runs live outside the repository under `<results>/<experiment>/arm_<a>_seed_<s>/`, each with a `run_manifest.json` (statuses PLANNED, RUNNING, COMPLETED, FAILED and INVALIDATED). See [docs/reproducibility/REMOTE_COMPUTE.md](../docs/reproducibility/REMOTE_COMPUTE.md). **Scientific training has not been executed.**

`evaluation_ledger.jsonl` (created at the first tagged evaluation) records every
test-set and external evaluation (SR4).
