import type { Metadata } from "next";
import { KeyValue, Mono, PageHeader } from "@/components/ui";
import { protocol, status } from "@/lib/data";

export const metadata: Metadata = { title: "Reproducibility" };

export default function ReproducibilityPage() {
  const seeds = protocol.parameters.seeds;
  return (
    <article className="prose-block">
      <PageHeader title="Reproducibility" lead="How the study is made auditable before any data are touched." />

      <h2>Sources of truth</h2>
      <KeyValue
        rows={[
          ["Scientific design", <Mono key="p">{status.protocol.file}</Mono>],
          ["Design parameters for code", <Mono key="c">configs/protocol/protocol_v1.0.yaml</Mono>],
          ["Project and gate state", <Mono key="s">docs/project_status.yaml</Mono>],
          ["This website's data", <Mono key="w">website/data/*.json (generated; never hand-edited)</Mono>],
        ]}
      />

      <h2>Seeds</h2>
      <KeyValue
        rows={[
          ["Training", seeds.training.join(", ")],
          ["Split", String(seeds.split)],
          ["Bootstrap", String(seeds.bootstrap)],
          ["Figure-case sampling", String(seeds.figure_case_sampling)],
        ]}
      />

      <h2>Safeguards</h2>
      <ul>
        <li>
          Every data, training and evaluation step checks the protocol gates first and refuses to run until they
          are closed, with evidence.
        </li>
        <li>
          Test-set and external evaluation require the exact commit tagged <Mono>eval-v1</Mono>. Each evaluation is
          recorded in a single-evaluation ledger.
        </li>
        <li>
          The screening threshold is computed only from the two verified positive-control pairs, and the split is
          created once with seed {seeds.split}.
        </li>
        <li>
          Every stored result carries its commit, configuration hash, protocol hash and input hashes. Synthetic test
          data are refused as results.
        </li>
        <li>
          Continuous integration runs linting, type checking, the test suite, the frozen-protocol hash check, a
          prohibited-file and secret scan, and a check that this website&apos;s data is in sync.
        </li>
      </ul>

      <h2>Data policy</h2>
      <p>
        The repository and this website contain no MRI scans, no NIfTI files, no patient-level labels, no licensed
        metadata files, no credentials and no model checkpoints. Data must be obtained from the official providers
        under their terms.
      </p>

      <h2>Verify a checkout</h2>
      <pre className="overflow-x-auto rounded bg-slate-100 p-4 text-sm dark:bg-slate-900">
        {`pip install -e ".[dev]"
brats-uncertainty verify-protocol
pytest
brats-uncertainty check-repo
brats-uncertainty export-site-data --check`}
      </pre>
    </article>
  );
}
