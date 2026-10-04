import type { ReactNode } from "react";
import type { GateStatus } from "@/lib/data";

const STATUS_STYLE: Record<string, string> = {
  CLOSED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  OWNER_WAIVED: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
  DONE: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  COMPLETED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  IN_PROGRESS: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  RUNNING: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  PLANNED: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  AUTHORIZED: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300",
  NOT_STARTED: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  BLOCKED: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  FAILED: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  INVALIDATED: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  FROZEN: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  LOCKED: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  NOT_AVAILABLE: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  AVAILABLE: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  PASSED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  PREPARED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
};

export function StatusBadge({ status }: { status: GateStatus | string }) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.NOT_STARTED;
  return (
    <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${style}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function PageHeader({ title, lead }: { title: string; lead?: ReactNode }) {
  return (
    <header className="mb-8 border-b border-slate-200 pb-6 dark:border-slate-800">
      <h1 className="font-serif text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl dark:text-slate-50">
        {title}
      </h1>
      {lead ? <p className="mt-3 text-lg leading-7 text-slate-600 dark:text-slate-400">{lead}</p> : null}
    </header>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="my-6 rounded-md border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
      {children}
    </div>
  );
}

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 p-5 dark:border-slate-800">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </h3>
      <div className="text-slate-800 dark:text-slate-200">{children}</div>
    </section>
  );
}

export function KeyValue({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="table-base">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th className="w-1/3 font-medium text-slate-600 dark:text-slate-400">{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Mono({ children }: { children: ReactNode }) {
  return <code className="mono break-all">{children}</code>;
}
