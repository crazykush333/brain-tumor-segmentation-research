"""EXP-001 budget projection and the compute stopping rules SR1, SR6 and SR8 (gate D6).

Implements docs/experiments/EXP-001_COMPUTE_PILOT_SPEC.md §3 and protocol §17/§20
exactly; nothing here is tuned:

    T_train_run   = median_epoch_s x epochs / 3600 x (1 + overhead_frac)
    T_train_total = 6 x T_train_run  (/ concurrency gain if P3 shows >= 1.6x and not CPU-bound)
    T_infer_prim  = infer_s x 828 cases x 5 conditions x 6 models / 3 / 3600  (+ GPU metric term)
    T_infer_C15   = infer_s x 148 x 10 x 3 / 3 / 3600
    T_total       = T_train_total + T_infer_prim + T_infer_C15

- SR1: T_train_run > 25 GPU-h -> all six runs to 150 epochs; still > 25 -> consult the owner.
- SR6: T_total > 220 GPU-h -> in order, re-projecting after each: (1) arm A external
  inference on Full, -T1c, -FLAIR only; (2) drop C15; (3) 150 epochs; (4) consult the owner.
- SR8: the budget is always recomputed from the measured platform; a measured quota or
  session limit that differs from the planning values is reported as an SR8 event.

Case counts are the protocol's planning counts (val ~74, test ~148, UPenn 511,
Africa <= 95); the realised counts after B12/C3 replace them in a re-projection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

CAP_GPU_H = 220.0
SR1_RUN_CAP_GPU_H = 25.0
PROTOCOL_EPOCHS = 250
REDUCED_EPOCHS = 150
N_RUNS = 6
MODELS_PER_ARM = 3
CONCURRENCY_MIN_GAIN = 1.6
PLANNING_QUOTA_H_WEEK = 30.0
PLANNING_SESSION_LIMIT_H = 12.0
CASES = {"validation": 74, "internal_test": 148, "upenn_hoi": 511, "brats_africa": 95}
C5_CONDITIONS = 5
ARM_A_EXTERNAL_REDUCED_CONDITIONS = 3  # Full, -T1c, -FLAIR (SR6 step 1)
C15_EXTRA_CONDITIONS = 10  # the 15 subsets minus the 5 C5 conditions
SR6_STEPS = (
    "arm A external inference on Full, -T1c and -FLAIR only",
    "drop C15",
    "switch all six runs to 150 epochs",
    "consult the owner",
)


@dataclass(frozen=True)
class PilotMeasurements:
    """Measured EXP-001 quantities used by the projection (spec §2, §3)."""

    median_epoch_s: float
    overhead_frac: float
    infer_s_per_case_condition: float
    metric_s_per_case_condition_on_gpu: float = 0.0
    concurrency_gain: float | None = None  # P3 throughput vs P2; None if not measured
    cpu_bound: bool = False
    quota_h_week: float | None = None  # None: no quota (private VM)
    session_limit_h: float | None = None
    resume_pass: bool = False
    peak_mem_fits_default_plan: bool = False
    platform: str = ""

    def __post_init__(self) -> None:
        for name in ("median_epoch_s", "infer_s_per_case_condition"):
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be a positive measurement")
        if self.overhead_frac < 0 or self.metric_s_per_case_condition_on_gpu < 0:
            raise ValueError("overhead_frac and metric time cannot be negative")


@dataclass(frozen=True)
class Plan:
    epochs: int = PROTOCOL_EPOCHS
    arm_a_external_conditions: int = C5_CONDITIONS
    c15: bool = True


@dataclass
class Projection:
    plan: Plan
    t_train_run: float
    t_train_total: float
    t_infer_prim: float
    t_infer_c15: float
    t_total: float
    concurrency_applied: bool

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


@dataclass
class BudgetDecision:
    status: str  # FEASIBLE | OWNER_CONSULTATION
    final: Projection
    steps: list[dict[str, Any]] = field(default_factory=list)
    sr1_applied: bool = False
    sr6_steps_applied: list[str] = field(default_factory=list)
    sr8_events: list[str] = field(default_factory=list)
    acceptance_failures: list[str] = field(default_factory=list)
    calendar_weeks: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "final": self.final.as_dict(),
            "steps": self.steps,
            "sr1_applied": self.sr1_applied,
            "sr6_steps_applied": self.sr6_steps_applied,
            "sr8_events": self.sr8_events,
            "acceptance_failures": self.acceptance_failures,
            "calendar_weeks": None
            if self.calendar_weeks is None
            else round(self.calendar_weeks, 2),
            "cap_gpu_h": CAP_GPU_H,
            "count_convention": "ensemble passes per member; 3 members loaded together (spec §3)",
        }


def project(m: PilotMeasurements, plan: Plan) -> Projection:
    t_run = m.median_epoch_s * plan.epochs / 3600 * (1 + m.overhead_frac)
    conc = bool(
        m.concurrency_gain is not None
        and m.concurrency_gain >= CONCURRENCY_MIN_GAIN
        and not m.cpu_bound
    )
    t_train_total = N_RUNS * t_run / (m.concurrency_gain if conc and m.concurrency_gain else 1.0)
    per_case_condition = m.infer_s_per_case_condition + m.metric_s_per_case_condition_on_gpu
    internal = CASES["validation"] + CASES["internal_test"]
    external = CASES["upenn_hoi"] + CASES["brats_africa"]
    # one ensemble pass per arm per case-condition (6 models / 3 members loaded together)
    arm_b = (internal + external) * C5_CONDITIONS
    arm_a = internal * C5_CONDITIONS + external * plan.arm_a_external_conditions
    t_prim = per_case_condition * (arm_a + arm_b) / 3600
    t_c15 = (
        m.infer_s_per_case_condition
        * CASES["internal_test"]
        * C15_EXTRA_CONDITIONS
        * MODELS_PER_ARM
        / MODELS_PER_ARM
        / 3600
        if plan.c15
        else 0.0
    )
    return Projection(
        plan, t_run, t_train_total, t_prim, t_c15, t_train_total + t_prim + t_c15, conc
    )


def decide(m: PilotMeasurements) -> BudgetDecision:
    """Apply SR1, then SR6 in order, re-projecting after each step; record SR8 events."""
    plan = Plan()
    p = project(m, plan)
    steps: list[dict[str, Any]] = [{"step": "baseline", **p.as_dict()}]
    sr1 = False
    status = "FEASIBLE"
    if p.t_train_run > SR1_RUN_CAP_GPU_H:
        sr1 = True
        plan = replace(plan, epochs=REDUCED_EPOCHS)
        p = project(m, plan)
        steps.append({"step": "SR1: all six runs to 150 epochs", **p.as_dict()})
        if p.t_train_run > SR1_RUN_CAP_GPU_H:
            status = "OWNER_CONSULTATION"
            steps.append({"step": "SR1: still infeasible at 150 epochs -> consult the owner"})
    applied: list[str] = []
    if status == "FEASIBLE" and p.t_total > CAP_GPU_H:
        for i, label in enumerate(SR6_STEPS):
            if p.t_total <= CAP_GPU_H:
                break
            if i == 3:
                status = "OWNER_CONSULTATION"
                applied.append(label)
                steps.append({"step": f"SR6 step 4: {label}"})
                break
            plan = (
                replace(plan, arm_a_external_conditions=ARM_A_EXTERNAL_REDUCED_CONDITIONS)
                if i == 0
                else replace(plan, c15=False)
                if i == 1
                else replace(plan, epochs=REDUCED_EPOCHS)
            )
            p = project(m, plan)
            applied.append(label)
            steps.append({"step": f"SR6 step {i + 1}: {label}", **p.as_dict()})
    sr8: list[str] = []
    if m.quota_h_week is not None and m.quota_h_week != PLANNING_QUOTA_H_WEEK:
        sr8.append(
            f"weekly quota {m.quota_h_week} h differs from planning {PLANNING_QUOTA_H_WEEK} h"
        )
    if m.session_limit_h is not None and m.session_limit_h != PLANNING_SESSION_LIMIT_H:
        sr8.append(
            f"session limit {m.session_limit_h} h differs from planning "
            f"{PLANNING_SESSION_LIMIT_H} h"
        )
    acceptance = []
    if not m.resume_pass:
        acceptance.append("resume check did not pass")
    if not m.peak_mem_fits_default_plan:
        acceptance.append(
            "peak memory does not fit the default plan (a change would be an amendment)"
        )
    if acceptance:
        status = "OWNER_CONSULTATION"
    weeks = p.t_total / m.quota_h_week if m.quota_h_week else None
    return BudgetDecision(status, p, steps, sr1, applied, sr8, acceptance, weeks)
