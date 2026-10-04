import type { Metadata } from "next";
import { Card, Notice, PageHeader, StatusBadge } from "@/components/ui";
import { type Estimate, type ResultArtifact, demo, repoUrl, results, status } from "@/lib/data";

export const metadata: Metadata = { title: "Results" };

const fmt = (x: number | undefined, d = 3) => (typeof x === "number" ? x.toFixed(d) : "–");

function gateClosed(id: string): boolean {
  const g = status.gates.find((x) => x.id === id);
  return !!g && (g.status === "CLOSED" || g.status === "PASSED");
}

function stage(done: boolean, running = false): string {
  return done ? "COMPLETED" : running ? "IN_PROGRESS" : "PENDING";
}

/** Real-study states, derived only from the repository's status records. */
function realTimeline(): [string, string][] {
  const rs = status.results_status;
  return [
    ["Official data", stage(status.data.acquired)],
    ["Compute (EXP-001 pilot, D6)", stage(gateClosed("D6"))],
    ["Training (6 runs)", stage(rs.training_status === "COMPLETED", rs.training_status === "IN_PROGRESS")],
    ["Validation and threshold freeze (C5)", stage(gateClosed("C5"))],
    ["Internal evaluation", stage(rs.real_experiment_executed)],
    ["External validation", stage(results.available)],
    ["Statistics", stage(results.available)],
  ];
}

function DemoTag() {
  return (
    <span className="ml-2 inline-flex gap-1 align-middle">
      {["DEMO", "SYNTHETIC", "NOT SCIENTIFIC RESULT"].map((t) => (
        <span key={t} className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-rose-800 dark:bg-rose-900/50 dark:text-rose-200">
          {t}
        </span>
      ))}
    </span>
  );
}

function find(name: string): ResultArtifact | undefined {
  return results.artifacts.find((a) => a.name === name);
}

/** Rendered only when real, provenance-checked result artifacts exist. */
function RealResults() {
  const internal = find("internal_test_analysis");
  if (!internal) return null;
  const p = internal.payload.primary_HW as Estimate & { supported: boolean };
  return (
    <p>
      Primary endpoint (internal test, arm B, ET): mean within-condition ΔAURC over C4 = {fmt(p.estimate)} (95%
      patient-group bootstrap CI {fmt(p.ci_low)} to {fmt(p.ci_high)}); H-W {p.supported ? "supported" : "not supported"}{" "}
      by the pre-registered rule. Generated from commit {internal.provenance.git_commit.slice(0, 12)} (eval-v1).
    </p>
  );
}

const FIGURE_TITLES: Record<string, string> = {
  "synthetic_risk_coverage.svg": "Risk–coverage curves per single-missing condition (U1 vs I)",
  "synthetic_calibration.svg": "Voxel-level calibration (reliability diagram)",
  "synthetic_uncertainty_vs_error.svg": "Case-level uncertainty (U1) vs ET Dice",
  "synthetic_failure_analysis.svg": "Failure categories per condition",
};

function DemoSection() {
  if (!demo.available) return null;
  const p = demo.example_primary_statistic;
  const t = demo.example_threshold_transfer_q080;
  return (
    <section className="mt-14">
      <h2 className="font-serif text-2xl font-semibold text-slate-900 dark:text-slate-50">
        Synthetic Results Demonstration
        <DemoTag />
      </h2>
      <p className="mt-2 text-slate-600 dark:text-slate-400">
        Illustrative outputs generated from deterministic synthetic data. These are not BraTS scientific results.
      </p>
      <div className="my-4 rounded-md border-2 border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
        <strong>{demo.label}.</strong> {demo.disclaimer} The study&apos;s own metric, statistics and figure code was
        run on {demo.synthetic_study?.validation_cases} + {demo.synthetic_study?.test_cases} synthetic toy cases (seed{" "}
        {demo.demo_seed}, {demo.bootstrap_replicates} bootstrap replicates) to show what this page will contain once the
        real experiment has run. No value here supports or rejects any hypothesis.
      </div>
      <p>
        <a
          href={`${repoUrl}/tree/main/${demo.artifacts_path}`}
          className="inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900"
        >
          View demo artifacts
        </a>
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {(demo.figures ?? []).map((f) => (
          <figure key={f} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/demo/${f}`} alt={`${FIGURE_TITLES[f] ?? f} (synthetic demonstration)`} className="w-full bg-white" />
            <figcaption className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              {FIGURE_TITLES[f] ?? f}
              <DemoTag />
            </figcaption>
          </figure>
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card title="Example within-condition ET ΔAURC (U1 − I) · synthetic">
          <table className="table-base">
            <tbody>
              {p ? (
                <tr>
                  <th>Mean over C4</th>
                  <td>
                    {fmt(p.estimate)} [{fmt(p.ci_low)}, {fmt(p.ci_high)}]
                  </td>
                </tr>
              ) : null}
              {Object.entries(demo.example_delta_aurc_by_condition ?? {}).map(([c, v]) => (
                <tr key={c}>
                  <th>{c}</th>
                  <td>{fmt(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{demo.disclaimer}</p>
        </Card>
        <Card title="Example threshold transfer at τ0.80 · synthetic">
          <table className="table-base">
            <tbody>
              <tr>
                <th>τ0.80 (validation C4)</th>
                <td>{fmt(demo.example_tau_q?.["0.80"])}</td>
              </tr>
              <tr>
                <th>Coverage validation → target</th>
                <td>
                  {fmt(t?.validation_coverage)} → {fmt(t?.target_coverage)}
                </td>
              </tr>
              <tr>
                <th>Δrisk / Δcoverage</th>
                <td>
                  {fmt(t?.delta_risk)} / {fmt(t?.delta_coverage)}
                </td>
              </tr>
            </tbody>
          </table>
          <p className="mt-2 text-xs text-rose-700 dark:text-rose-300">{demo.disclaimer}</p>
        </Card>
      </div>
      <p className="mt-4 text-xs text-slate-500">
        Demo provenance: generated {demo.generated_at}; code commit {demo.git_commit?.slice(0, 12)}; demo=true,
        synthetic=true, scientific_result=false.
      </p>
    </section>
  );
}

export default function ResultsPage() {
  return (
    <article className="prose-block">
      <PageHeader
        title="Results"
        lead="Real results of the pre-registered study and, clearly separated, a synthetic demonstration of the result pipeline."
      />

      <section>
        <h2 className="font-serif text-2xl font-semibold text-slate-900 dark:text-slate-50">Real experimental results</h2>
        {results.available ? (
          <>
            <p>{results.artifacts.length} provenance-checked result artifact(s) are available.</p>
            <RealResults />
          </>
        ) : (
          <Notice>
            <p className="text-lg font-semibold">Results pending real experimental execution.</p>
            <p className="mt-1">{results.statement}</p>
            <p className="mt-1 text-sm">
              Scientific results will appear here after execution, generated only from provenance-stamped artifacts of
              the frozen protocol. Negative and null findings will be reported with the same prominence as positive
              ones.
            </p>
          </Notice>
        )}
        <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-slate-500">Real-study states</h3>
        <ol className="mt-2 divide-y divide-slate-200 rounded-lg border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {realTimeline().map(([label, s]) => (
            <li key={label} className="flex items-center justify-between px-4 py-2">
              <span>{label}</span>
              <StatusBadge status={s} />
            </li>
          ))}
        </ol>
        <p className="mt-2 text-xs text-slate-500">
          These states describe the real study and are generated from docs/project_status.yaml.
        </p>
      </section>

      <DemoSection />
    </article>
  );
}
