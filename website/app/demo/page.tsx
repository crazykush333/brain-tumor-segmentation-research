import type { Metadata } from "next";
import { Card, PageHeader } from "@/components/ui";
import { demo, repoUrl } from "@/lib/data";

export const metadata: Metadata = { title: "Pipeline demonstration" };

const fmt = (x: number | undefined, d = 3) => (typeof x === "number" ? x.toFixed(d) : "–");

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
    <section className="mt-6">
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

export default function DemoPage() {
  return (
    <article className="prose-block">
      <PageHeader
        title="Pipeline demonstration"
        lead="A synthetic demonstration of the result pipeline. It is kept on this separate page so that the Results page never shows a synthetic number."
      />
      {demo.available ? <DemoSection /> : <p>No synthetic demonstration has been generated.</p>}
    </article>
  );
}
