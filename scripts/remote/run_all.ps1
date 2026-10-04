# Run (or resume) the whole frozen protocol on this machine (Windows PowerShell).
# Stops only at a genuine blocker and prints the exact gate, blocker and action.
# Requires $env:BRATS_WORK (persistent private storage outside the repository).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
if (-not $env:BRATS_WORK) { throw "set BRATS_WORK to persistent private storage outside the repository" }
python -m brats_uncertainty.cli verify-protocol
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m brats_uncertainty.cli check-repo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python scripts/remote/master_run.py --resume --commit --push @args
exit $LASTEXITCODE
