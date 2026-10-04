# Gate D1: owner authorization of EXP-001

| Field | Value |
|---|---|
| Gate | D1, "Owner authorization of EXP-001" (protocol v1.0, lifecycle gate D) |
| Authorized by | Ayush Kushwaha (project owner) |
| Date | 2026-10-04 |
| Form | Written instruction from the owner in the master orchestration task, asking that the master execution be run and that this instruction be recorded as D1 authorization |
| Scope | EXP-001 exactly as specified in [EXP-001_COMPUTE_PILOT_SPEC.md](../../experiments/EXP-001_COMPUTE_PILOT_SPEC.md) and `configs/experiments/EXP-001.yaml`; nothing else |

## What this authorizes

- Running the EXP-001 compute pilot once its other preconditions hold. The guarded
  action `run_exp001` also requires B1, B2 and D2 to be closed, so the pilot cannot
  start before the official data have been acquired through the approved route.
- Measurements only: timing, GPU utilisation and memory, preprocessing time, disk use,
  checkpoint/resume correctness, inference time, platform limits (spec §2).

## Conditions that still apply (not waived)

- D3: only development cases (crosswalk Site ID ≠ 1), N = 40, selection seed 101.
- D4: no label-based scientific metric is computed (no Dice, calibration, AURC or
  reliability metric).
- D5: no site-1 (UPenn HOI) and no BraTS-Africa data.
- D6: SR1, SR6 and SR8 are applied to the measured projection before main training.
- Pilot models are discarded, and no pilot output feeds any threshold, grouping or
  split decision.

This record authorizes EXP-001 only. It changes no part of the frozen protocol and
authorizes no main training, evaluation or data route.
