# Private GPU VM execution

The same package and CLI as the Kaggle notebooks, on a private NVIDIA GPU VM or workstation under the owner's control. Nothing here is Kaggle-specific, and paths come from environment variables.

1. **Setup.** This installs the package at an exact commit and probes the environment. It downloads no data.

   ```bash
   REPO_URL=<https url> COMMIT=<sha or tag> WORK=/private/disk/brats bash experiments/vm/setup_vm.sh
   ```

   The script writes `probe_general.json`, `probe_JOB-01.json` and `probe_JOB-02.json` to `$WORK/export/`.
2. **B2.**
   - Manual official delivery: the owner downloads `BraTS2021_TrainingSet` and the `.sums` file with the official Aspera client into `$WORK/delivery`. Alternatively, a command confirmed from the client's help can be used.
   - Run `storage-preflight`, then `verify-checksums`.
   - Run `acquire --adapter local-import` (dry run, then `--execute`) as in `experiments/kaggle/01_data_access_and_b2.ipynb`.
3. **Later jobs:** the same cells as notebooks 02–06, run as shell commands. Every job starts with `brats-uncertainty check-action <action>`, and the gates are never bypassed.
4. **Synchronise:** run `brats-uncertainty export-artifacts --source $WORK/export --dest <owner checkout>/results/<EXPERIMENT>` and commit from the owner's checkout ([GITHUB_SETUP.md](../../docs/reproducibility/GITHUB_SETUP.md)).

Keep `$WORK` on a private, access-restricted disk (`chmod 700`, as `setup_vm.sh` sets). Never put it on a shared or public bucket.
