import { status } from "@/lib/data";

/** Stage overview derived by the exporter from docs/project_status.yaml (never hand-edited). */
const ICON: Record<string, { icon: string; label: string; tone: string }> = {
  FROZEN: { icon: "✓", label: "Frozen", tone: "text-emerald-700 dark:text-emerald-400" },
  PREPARED: { icon: "✓", label: "Prepared", tone: "text-emerald-700 dark:text-emerald-400" },
  COMPLETED: { icon: "✓", label: "Completed", tone: "text-emerald-700 dark:text-emerald-400" },
  PASSED: { icon: "✓", label: "Passed", tone: "text-emerald-700 dark:text-emerald-400" },
  CLOSED: { icon: "✓", label: "Closed", tone: "text-emerald-700 dark:text-emerald-400" },
  AVAILABLE: { icon: "✓", label: "Available", tone: "text-emerald-700 dark:text-emerald-400" },
  PENDING: { icon: "⏳", label: "Pending", tone: "text-amber-700 dark:text-amber-400" },
  ROUTE_AUTHORIZED: { icon: "✓", label: "Authorized", tone: "text-emerald-700 dark:text-emerald-400" },
  AUTHORIZED: { icon: "🔓", label: "Ready", tone: "text-sky-700 dark:text-sky-400" },
  RUNNING: { icon: "⏳", label: "Running", tone: "text-sky-700 dark:text-sky-400" },
  IN_PROGRESS: { icon: "⏳", label: "In progress", tone: "text-sky-700 dark:text-sky-400" },
  NOT_STARTED: { icon: "○", label: "Not started", tone: "text-slate-500 dark:text-slate-400" },
  NOT_AVAILABLE: { icon: "○", label: "Not available", tone: "text-slate-500 dark:text-slate-400" },
  LOCKED: { icon: "🔒", label: "Locked", tone: "text-slate-600 dark:text-slate-400" },
  FAILED: { icon: "✕", label: "Failed", tone: "text-rose-700 dark:text-rose-400" },
  BLOCKED: { icon: "✕", label: "Blocked", tone: "text-rose-700 dark:text-rose-400" },
};

export function StageOverview() {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="table-base">
        <caption className="sr-only">Project stage overview</caption>
        <tbody>
          {status.overview.map((o) => {
            const s = ICON[o.status] ?? { icon: "?", label: o.status, tone: "" };
            return (
              <tr key={o.key}>
                <th scope="row" className="w-1/3 pl-4 font-medium">
                  {o.label}
                </th>
                <td className={`whitespace-nowrap font-medium ${s.tone}`}>
                  <span aria-hidden="true" className="mr-2 inline-block w-5 text-center">
                    {s.icon}
                  </span>
                  {o.status_label ?? s.label}
                </td>
                <td className="hidden text-sm text-slate-500 sm:table-cell">{o.detail}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const COUNT_LABELS: Record<string, string> = {
  total: "BraTS 2021 training cases (total)",
  held_out_institution: "Site 1 (held-out institution)",
  development: "Development (site ≠ 1)",
};

/** B6 counts. Shown as protocol verification targets until a verified B6 record exists. */
export function CountVerification() {
  const c = status.count_verification;
  const verified = c.status === "VERIFIED_FROM_SOURCE";
  return (
    <div className="my-4 rounded-lg border border-slate-200 p-4 dark:border-slate-800">
      <p className="mb-2 text-sm font-semibold">{c.label}</p>
      <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">
        Targets: {c.status.replace(/_/g, " ")} · B6 verification: {c.verification.replace(/_/g, " ")}
      </p>
      <table className="table-base">
        <thead>
          <tr>
            <th>Cohort</th>
            <th>{verified ? "Verified count" : "Protocol verification target"}</th>
          </tr>
        </thead>
        <tbody>
          {Object.keys(COUNT_LABELS).map((k) => (
            <tr key={k}>
              <td>{COUNT_LABELS[k]}</td>
              <td className="font-mono">{verified && c.counts ? c.counts[k] : c.targets[k]}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!verified ? (
        <p className="mt-3 text-xs text-slate-500">
          These are design targets from the frozen protocol, not results. They become verified only when gate B6
          derives them from the hashed crosswalk file.
        </p>
      ) : null}
    </div>
  );
}
