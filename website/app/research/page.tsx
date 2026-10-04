import type { Metadata } from "next";
import { Notice, PageHeader } from "@/components/ui";
import { protocol, status } from "@/lib/data";

export const metadata: Metadata = { title: "Research" };

export default function ResearchPage() {
  const p = protocol.parameters;
  const c = p.cohorts;
  return (
    <article className="prose-block">
      <PageHeader title="Research" lead={status.project.type} />

      <h2>Research question</h2>
      <blockquote className="border-l-4 border-slate-300 pl-4 italic dark:border-slate-700">
        {status.project.research_question}
      </blockquote>
      <p>
        In deployment, the identity of the missing sequence is known from the acquisition protocol or the DICOM
        header. A quality-control signal is therefore useful only if it separates good from bad segmentations{" "}
        <em>given</em> that knowledge. Within a fixed condition, a rule based only on the missing sequence assigns
        every case the same score, so any discrimination there must come from the uncertainty signal itself.
      </p>

      <h2>Hypotheses (pre-registered)</h2>
      <h3>Primary: H-W</h3>
      <p>
        On the internal test set, for the modality-dropout (arm B) ensemble, the equal-weight mean over the four
        single-missing conditions C4 = {"{"}
        {p.conditions.C4.join(", ")}
        {"}"} of the within-condition enhancing-tumour ΔAURC is below zero, where ΔAURC<sub>c</sub> = AURC
        <sub>c</sub>(U1) − AURC<sub>c</sub>(I). U1 is the ensemble pairwise-Dice confidence, I is the
        missingness-indicator baseline, and risk is {p.metrics.risk}. The Full condition is a supporting control
        and is not part of the estimand.
      </p>
      <h3>Key secondary</h3>
      <ul>
        <li>
          <strong>H-W(−T1c):</strong> the −T1c component, reported as the key secondary result.
        </li>
        <li>
          <strong>H-W-ext:</strong> the same mean over C4 on the held-out institution and on BraTS-Africa, analysed
          separately and never pooled.
        </li>
        <li>
          <strong>H-T:</strong> whether there is evidence of adverse transfer of the validation-derived U1 operating
          threshold (target coverage {p.threshold_transfer.q_primary}) to the internal test, held-out institution
          and external sets. A non-significant result establishes neither safety nor equivalence.
        </li>
        <li>
          <strong>H4 (descriptive):</strong> arm A within-condition ΔAURC, reported without a confirmatory test.
        </li>
      </ul>

      <h2>Datasets (design{status.data.acquired ? "" : "; not yet acquired"})</h2>
      <div className="overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>Role</th>
              <th>Source</th>
              <th>Planned size</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Development (train / validation / internal test)</td>
              <td>BraTS 2021 training cases not from site {c.hoi_site_id}</td>
              <td>{c.development_count_before_grouping} cases before patient grouping</td>
            </tr>
            <tr>
              <td>Held-out institution</td>
              <td>BraTS 2021 site {c.hoi_site_id} (UPenn-origin) cases</td>
              <td>{c.hoi_count} cases</td>
            </tr>
            <tr>
              <td>External population</td>
              <td>TCIA BraTS-Africa, adult glioma cases</td>
              <td>at most {c.brats_africa_max_eligible} cases (count pending file-level verification)</td>
            </tr>
          </tbody>
        </table>
      </div>
      <Notice>
        These are design parameters and metadata-derived counts from the frozen protocol. They are re-derived from
        hashed files at gates B6 and C3. Current B6 state:{" "}
        {status.count_verification.status.replace(/_/g, " ").toLowerCase()}. {status.data.statement}
      </Notice>

      <h2>What this study is not</h2>
      <ul>
        <li>It does not propose a new segmentation architecture, calibration method or fusion module.</li>
        <li>
          It simulates missing sequences by zeroing normalized channels. Real missing or degraded acquisitions are
          not studied.
        </li>
        <li>It makes no claim before the pre-registered analyses have been run.</li>
      </ul>
    </article>
  );
}
