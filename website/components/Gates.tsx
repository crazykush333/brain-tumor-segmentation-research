import { StatusBadge } from "@/components/ui";
import { status, type TimelineItem } from "@/lib/data";

export function GateTable({ group }: { group: string }) {
  const gates = status.gates.filter((g) => g.group === group);
  return (
    <div className="my-4 overflow-x-auto">
      <p className="mb-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
        {group}. {status.gate_groups[group]}
      </p>
      <table className="table-base">
        <thead>
          <tr>
            <th>Gate</th>
            <th>Requirement</th>
            <th>Status</th>
            <th>Closed</th>
          </tr>
        </thead>
        <tbody>
          {gates.map((g) => (
            <tr key={g.id}>
              <td className="font-mono">{g.id}</td>
              <td>{g.title}</td>
              <td>
                <StatusBadge status={g.status} />
              </td>
              <td className="whitespace-nowrap text-slate-500">{g.closed_on ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Timeline({ items = status.timeline }: { items?: TimelineItem[] }) {
  return (
    <ol className="relative my-6 border-l border-slate-300 dark:border-slate-700">
      {items.map((t, i) => (
        <li key={`${t.title}-${i}`} className="mb-5 ml-5">
          <span
            className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white dark:border-slate-950 ${
              t.status === "DONE" ? "bg-emerald-500" : t.status === "PENDING" ? "bg-amber-500" : "bg-slate-300 dark:bg-slate-600"
            }`}
          />
          <div className="flex flex-wrap items-center gap-2">
            <time className="font-mono text-xs text-slate-500">{t.date ?? "not scheduled"}</time>
            <StatusBadge status={t.status} />
          </div>
          <p className="mt-1 text-slate-800 dark:text-slate-200">{t.title}</p>
        </li>
      ))}
    </ol>
  );
}
