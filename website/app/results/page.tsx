import type { Metadata } from "next";
import { Notice, PageHeader, StatusBadge } from "@/components/ui";
import { type VerifiedResult, repoUrl, results, status } from "@/lib/data";

export const metadata: Metadata = { title: "Results" };

/**
 * Scientific values on this page come only from results.verification.result_index, which the
 * exporter fills only after the independent result verification is VERIFIED. Each value carries
 * its verified result ID; the verifier reconciles the rendered page against that index.
 */
const DECIMALS = 3;
const FIELDS: [keyof VerifiedResult, string][] = [
  ["estimate", "Estimate"],
  ["ci_low", "95% CI low"],
  ["ci_high", "95% CI high"],
  ["p_value", "p (bootstrap)"],
  ["holm_p", "Holm-adjusted p"],
];

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
  const v = results.verification;
  return [
    ["Official data", stage(status.data.acquired)],
    ["Compute (EXP-001 pilot, D6)", stage(gateClosed("D6"))],
    ["Training (6 runs)", stage(rs.training_status === "COMPLETED", rs.training_status === "IN_PROGRESS")],
    ["Validation and threshold freeze (C5)", stage(gateClosed("C5"))],
    ["Internal evaluation", stage(rs.real_experiment_executed)],
    ["Statistics", stage(results.available)],
    ["Independent result verification", stage(v.scientific_status === "VERIFIED", v.scientific_status === "BLOCKED")],
  ];
}

function Value({ id, field, value }: { id: string; field: string; value: number }) {
  return (
    <span data-result-id={id} data-field={field} data-value={String(value)}>
      {value.toFixed(DECIMALS)}
    </span>
  );
}

function VerifiedTable({ index }: { index: Record<string, VerifiedResult> }) {
  return (
    <div className="mt-4 space-y-6">
      {Object.entries(index).map(([id, r]) => (
        <section key={id} className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-900 dark:text-slate-50">{r.title}</h3>
          <table className="table-base mt-2">
            <tbody>
              {FIELDS.filter(([f]) => typeof r[f] === "number").map(([f, label]) => (
                <tr key={f}>
                  <th>{label}</th>
                  <td>
                    <Value id={id} field={f} value={r[f] as number} />
                  </td>
                </tr>
              ))}
              {r.status || r.label ? (
                <tr>
                  <th>Pre-registered decision</th>
                  <td>{r.status ?? r.label}</td>
                </tr>
              ) : null}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">
            Verified result ID: <code className="mono">{id}</code> · {r.dataset}, arm {r.arm}, {r.region},{" "}
            {r.condition} · analysis {r.analysis_id}
          </p>
        </section>
      ))}
    </div>
  );
}

export default function ResultsPage() {
  const v = results.verification;
  const verified = results.available && v.scientific_status === "VERIFIED";
  const underVerification = !verified && (results.available || v.scientific_status === "BLOCKED");
  return (
    <article className="prose-block">
      <PageHeader
        title="Results"
        lead="Results of the pre-registered study, shown only after every value has been independently recomputed and verified."
      />

      <section>
        <h2 className="font-serif text-2xl font-semibold text-slate-900 dark:text-slate-50">Experimental results</h2>
        {verified ? (
          <>
            <p>
              Every value below was recomputed independently from the per-case outputs and matched the production
              analysis (verification {v.generated_at}). Certificate:{" "}
              <a href={`${repoUrl}/blob/main/${v.certificate}`} className="underline">
                {v.certificate}
              </a>
              .
            </p>
            <VerifiedTable index={v.result_index} />
          </>
        ) : underVerification ? (
          <Notice>
            <p className="text-lg font-semibold">Scientific results are being independently verified.</p>
            <p className="mt-1">{results.statement}</p>
          </Notice>
        ) : (
          <Notice>
            <p className="text-lg font-semibold">Results pending real experimental execution.</p>
            <p className="mt-1">{results.statement}</p>
            <p className="mt-1 text-sm">
              Scientific results will appear here after execution and independent verification, generated only from
              provenance-stamped artifacts of the frozen protocol. Negative and null findings will be reported with the
              same prominence as positive ones.
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
          These states describe the real study and are generated from docs/project_status.yaml and
          results/verification/verification_manifest.json (independent verification: {v.scientific_status}).
        </p>
      </section>
    </article>
  );
}
