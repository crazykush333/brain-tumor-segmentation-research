import type { Metadata } from "next";
import { KeyValue, Mono, PageHeader } from "@/components/ui";
import { protocol } from "@/lib/data";

export const metadata: Metadata = { title: "Methodology" };

export default function MethodologyPage() {
  const p = protocol.parameters;
  const s = p.statistics;
  const t = p.threshold_transfer;
  return (
    <article className="prose-block">
      <PageHeader
        title="Methodology"
        lead={`All parameters on this page are read from the machine-readable mirror of protocol ${protocol.version}.`}
      />

      <h2>Inputs and missingness</h2>
      <KeyValue
        rows={[
          ["Channel order", <Mono key="c">[{p.modalities.channel_order.join(", ")}]</Mono>],
          ["Missing sequence", "normalized channel set to 0 (training and inference)"],
          ["Evaluation conditions C5", p.conditions.C5.join(", ")],
          ["Primary estimand subset C4", p.conditions.C4.join(", ")],
          ["Control condition", `${p.conditions.control} (not in the primary estimand; not used for thresholds)`],
          ["C15 scope", `all 15 non-empty subsets; ${p.conditions.C15_scope.sets.join(", ")}; arm ${p.conditions.C15_scope.arm}`],
          ["Arm B dropout policy", `full input with probability ${p.modality_dropout.p_full}; otherwise ${p.modality_dropout.other_subsets}; applied ${p.modality_dropout.applied}; not tuned`],
        ]}
      />

      <h2>Model</h2>
      <KeyValue
        rows={[
          ["Framework", `${p.model.framework}, ${p.model.configuration}, region-based`],
          ["Schedule", `${p.model.epochs} epochs; checkpoint ${p.model.checkpoint}`],
          ["Arms", "A: no modality dropout; B: modality dropout"],
          ["Seeds", p.model.seeds.join(", ")],
          ["Inference", `sliding window step ${p.model.inference.sliding_window_step}; mirroring ${p.model.inference.mirroring ? "on" : "off"}; threshold ${p.model.inference.threshold}`],
          ["Ensemble", p.model.ensemble],
        ]}
      />

      <h2>Confidence scores</h2>
      <KeyValue
        rows={[
          ["U1 (primary)", p.uncertainty.U1],
          ["U2 (descriptive)", p.uncertainty.U2],
          ["U3 (exploratory)", p.uncertainty.U3],
          ["I (baseline)", p.uncertainty.I],
        ]}
      />

      <h2>Endpoint and AURC</h2>
      <p>
        Risk is {p.metrics.risk}. Dice convention: both masks empty gives {p.metrics.dice_empty_convention.both_empty};
        exactly one empty gives {p.metrics.dice_empty_convention.one_empty}. AURC is the mean selective risk over
        coverages k/n when units are ranked by descending confidence. Ties are resolved by the expected value under
        random tie-breaking, so a score that is constant within a condition (I) has AURC equal to the condition&apos;s
        mean risk.
      </p>

      <h2>Statistics</h2>
      <KeyValue
        rows={[
          ["Bootstrap", `${s.bootstrap_replicates.toLocaleString("en-US")} replicates, seed ${s.bootstrap_seed}, unit: ${s.bootstrap_unit.replace("_", " ")}`],
          ["Confidence intervals", `${s.ci_level * 100}% ${s.ci_method}; ${s.ci_sensitivity} as sensitivity analysis`],
          ["Two-sided p-value", s.p_value],
          ["Significance level α", String(s.alpha)],
          ["Multiplicity", s.multiplicity],
          ["Primary decision rule", "H-W is supported if the 95% CI of the mean ΔAURC over C4 lies entirely below 0"],
        ]}
      />
      <h3>Hypothesis families</h3>
      <div className="overflow-x-auto">
        <table className="table-base">
          <tbody>
            {Object.entries(s.families as Record<string, string>).map(([k, v]) => (
              <tr key={k}>
                <th className="w-20 font-mono">{k}</th>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Threshold transfer</h2>
      <KeyValue
        rows={[
          ["Rule", t.rule],
          ["Target coverage", `${t.q_primary} (primary); ${t.q_sensitivity.join(", ")} (sensitivity)`],
          ["Estimation population", `validation ${t.population} units, ${t.condition_weighting} condition weighting; Full used: ${t.full_used_for_tau ? "yes" : "no"}`],
          ["Confident-failure analysis", `threshold at q = ${t.failure_analysis_q} (descriptive)`],
          ["Transfer quantities", "Δrisk and Δcoverage (target minus validation) with independent patient-group bootstraps"],
        ]}
      />

      {protocol.population && (
        <>
          <h2>Study population (amendment {protocol.population.amendment})</h2>
          <p>{protocol.population.note}</p>
          <KeyValue
            rows={[
              ["Original development pool (site ≠ 1)", String(protocol.population.development_pool)],
              ["Identity-clean primary cohort", String(protocol.population.primary_identity_clean)],
              ["Identity-uncertain quarantine cohort", `${protocol.population.quarantine} (excluded from training, validation, thresholds and primary inference)`],
              ...(protocol.population.sites_absent_from_primary
                ? [["Sites absent from the primary cohort", protocol.population.sites_absent_from_primary.join(", ") || "none"] as [string, string]]
                : []),
              ["Reason", protocol.population.reason],
              ["Limitation", "reduced, metadata-selected development cohort; possible selection bias"],
            ]}
          />
        </>
      )}

      <h2>Patient grouping and split</h2>
      <KeyValue
        rows={[
          ["Verified same-patient groups", Object.entries(p.grouping.verified_groups as Record<string, string[]>).map(([k, v]) => `${k}: ${v.join(" + ")}`).join("; ")],
          ["Screen threshold rule", `${p.grouping.t_screen_rule} (value computed once at gate B7; not yet computed)`],
          ["Linked review decisions", p.grouping.linked_decisions.join(", ")],
          ["Split", `unit: patient group; ${["train", "validation", "internal_test"].map((k) => `${k.replace("_", " ")} ${p.split.proportions[k]}`).join(", ")}; seed ${p.split.seed}`],
          ["Stratification", p.split.stratification.join("; ")],
        ]}
      />
    </article>
  );
}
