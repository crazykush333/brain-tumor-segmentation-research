import type { Metadata } from "next";
import { GateTable } from "@/components/Gates";
import { CountVerification, StageOverview } from "@/components/Overview";
import { KeyValue, Mono, PageHeader, StatusBadge } from "@/components/ui";
import { protocol, sourceLink, status } from "@/lib/data";

export const metadata: Metadata = { title: "Protocol" };

export default function ProtocolPage() {
  const link = sourceLink(status.protocol.file);
  return (
    <article className="prose-block">
      <PageHeader title="Protocol" lead="The study is pre-registered. Its protocol is frozen and version-controlled." />

      <KeyValue
        rows={[
          ["Version", protocol.version],
          ["Status", <StatusBadge key="s" status={status.protocol.status} />],
          ["Frozen on", protocol.frozen_on],
          ["Git tag", <Mono key="t">{protocol.git_tag}</Mono>],
          [
            "File",
            link ? (
              <a key="f" href={link} className="text-blue-700 underline dark:text-blue-400">
                {status.protocol.file}
              </a>
            ) : (
              <Mono key="f">{status.protocol.file}</Mono>
            ),
          ],
          ["SHA-256 (LF-normalized text)", <Mono key="h">{protocol.sha256}</Mono>],
        ]}
      />

      <h2>Freeze rule</h2>
      <p>
        The frozen protocol is never edited. Any design change requires a logged amendment recording the date,
        version, sections, change, reason and whether any test data had been seen. No change is allowed after any
        test-set evaluation. Execution records from gates B–D (hashes, counts, the screening threshold value,
        patient groups, split hashes, compute measurements) are appended as administrative entries and do not
        change the design.
      </p>
      <p>
        The research software verifies the protocol file&apos;s hash every time it loads the design parameters, and
        refuses to run if the file has changed.
      </p>

      <h2>Amendments</h2>
      {protocol.amendments.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {protocol.amendments.map((a) => {
            const href = sourceLink(a.file);
            return (
              <li key={a.id}>
                <strong>{a.id}</strong> ({a.date}, {a.type}):{" "}
                {href ? (
                  <a href={href} className="text-blue-700 underline dark:text-blue-400">
                    {a.title}
                  </a>
                ) : (
                  a.title
                )}
                . The frozen v1.0 text and its tag are unchanged.
              </li>
            );
          })}
        </ul>
      )}

      <h2>Stage overview</h2>
      <StageOverview />

      <h2>Gate B6 count verification</h2>
      <CountVerification />

      <h2>Lifecycle gates</h2>
      {["A", "B", "C", "D"].map((g) => (
        <GateTable key={g} group={g} />
      ))}
    </article>
  );
}
