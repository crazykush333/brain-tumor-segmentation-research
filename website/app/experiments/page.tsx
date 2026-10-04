import type { Metadata } from "next";
import { Notice, PageHeader, StatusBadge } from "@/components/ui";
import { derivedFacts, experiments, protocol } from "@/lib/data";

export const metadata: Metadata = { title: "Experiments" };

const LIFECYCLE = ["PLANNED", "AUTHORIZED", "RUNNING", "COMPLETED", "FAILED", "INVALIDATED"];

export default function ExperimentsPage() {
  const m = protocol.parameters.model;
  return (
    <article className="prose-block">
      <PageHeader title="Experiments" lead="Registered experiments and their lifecycle status." />

      <Notice>
        {experiments.every((e) => e.status === "PLANNED")
          ? "No experiment has been authorized or run."
          : `Experiment statuses: ${experiments.map((e) => `${e.id} ${e.status.toLowerCase()}`).join(", ")}.`}{" "}
        {derivedFacts().slice(1).join(" ")}
      </Notice>

      <h2>Registered experiments</h2>
      <div className="overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Status</th>
              <th>Requires gates</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((e) => (
              <tr key={e.id}>
                <td className="font-mono">{e.id}</td>
                <td>
                  {e.title}
                  <p className="mt-1 text-sm text-slate-500">{e.notes}</p>
                </td>
                <td>
                  <StatusBadge status={e.status} />
                </td>
                <td className="font-mono text-sm">{e.required_gates.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Planned main training runs (not authorized)</h2>
      <p>
        Two arms × {m.seeds.length} seeds = {2 * m.seeds.length} runs of {m.framework} {m.configuration},{" "}
        {m.epochs} epochs each. Arm A is trained without modality dropout and arm B with it. The runs are blocked
        until gates B1–B12 and D1–D6 are closed.
      </p>

      <h2>Lifecycle</h2>
      <p className="flex flex-wrap gap-2">
        {LIFECYCLE.map((s) => (
          <StatusBadge key={s} status={s} />
        ))}
      </p>
      <p>
        An experiment can be authorized only with an owner authorization record. It can be marked completed only
        with full provenance (commit, configuration hash, protocol hash, environment) and hashes of its outputs.
      </p>
    </article>
  );
}
