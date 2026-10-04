import Link from "next/link";
import type { ReactNode } from "react";
import { Timeline } from "@/components/Gates";
import { StageOverview } from "@/components/Overview";
import { Card, Notice, StatusBadge } from "@/components/ui";
import { demo, repoUrl, results, status } from "@/lib/data";

function H2({ children }: { children: ReactNode }) {
  return <h2 className="mb-3 font-serif text-2xl font-semibold text-slate-900 dark:text-slate-50">{children}</h2>;
}

function StatusCard({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <Card title={title}>
      <StatusBadge status={value} />
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{detail}</p>
    </Card>
  );
}

export default function HomePage() {
  const rs = status.results_status;
  return (
    <div>
      {/* HERO */}
      <section className="mb-10">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <StatusBadge status={status.protocol.status} />
          <span className="text-sm text-slate-500">
            Pre-registered protocol {status.protocol.version}, frozen {status.protocol.frozen_on}
          </span>
        </div>
        <h1 className="font-serif text-3xl font-semibold leading-tight tracking-tight text-slate-900 sm:text-4xl dark:text-slate-50">
          {status.project.title}
        </h1>
        <blockquote className="mt-6 border-l-4 border-blue-400 pl-4 text-lg text-slate-800 dark:text-slate-200">
          {status.project.central_question}
        </blockquote>
        <div className="mt-6 flex flex-wrap gap-3 text-sm">
          <a href={repoUrl} className="rounded-md bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900">
            GitHub repository
          </a>
          <Link href="/protocol/" className="rounded-md border border-slate-300 px-4 py-2 font-medium dark:border-slate-700">
            Frozen protocol
          </Link>
          <Link href="/results/" className="rounded-md border border-slate-300 px-4 py-2 font-medium dark:border-slate-700">
            Results status
          </Link>
        </div>
      </section>

      <Notice>
        <strong>Real experiment status: </strong>
        {rs.real_brats_data_processed
          ? `official data acquired; training ${rs.training_status.toLowerCase().replace(/_/g, " ")}.`
          : "pending official data acquisition and suitable GPU execution."}{" "}
        {results.statement}
      </Notice>

      {/* STATUS CARDS */}
      <section className="my-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatusCard title="Research protocol" value="FROZEN" detail={`v${status.protocol.version.replace(/^v/, "")}, tag ${status.protocol.git_tag}`} />
        <StatusCard
          title="Real scientific results"
          value={rs.scientific_results_available ? "AVAILABLE" : "PENDING"}
          detail="Appear only after the pre-registered experiment has been executed."
        />
        <StatusCard
          title="Experiment readiness"
          value={status.data.acquired ? "IN_PROGRESS" : "PENDING"}
          detail={status.data.acquired ? "Official data acquired." : "Awaiting official BraTS data and a GPU environment (gate B2)."}
        />
        <StatusCard
          title="Synthetic pipeline demo"
          value={demo.available ? "AVAILABLE" : "NOT_AVAILABLE"}
          detail="Deterministic synthetic toy data; clearly labelled, never a scientific result."
        />
        <StatusCard title="Reproducibility" value="PREPARED" detail="One master runner, gated stages, resume, provenance, safe export." />
        <StatusCard title="Public artifacts" value="PREPARED" detail="Code, protocol, gate records and status are public; no patient data." />
      </section>

      {/* WHY */}
      <section className="my-10">
        <H2>Why this matters</H2>
        <p>
          Clinical MRI protocols are often incomplete: a contrast-enhanced T1, a T2 or a FLAIR sequence may be missing or
          unusable. Segmentation models can be trained to tolerate missing sequences, but a radiologist also needs to know{" "}
          <em>which individual cases</em> to trust. Knowing only <em>which</em> sequence is missing already says that
          some conditions are harder than others; the open question is whether model uncertainty identifies unreliable
          enhancing-tumour segmentations <em>within</em> the same missing-sequence condition, and whether that signal and
          its operating threshold transfer to a new institution and a new population.
        </p>
      </section>

      {/* METHOD + DESIGN */}
      <section className="my-10 grid gap-6 lg:grid-cols-2">
        <Card title="Method (frozen protocol)">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li>nnU-Net v2, 3d_fullres, region-based (WT / TC / ET); 250 epochs; seeds 0, 1, 2.</li>
            <li>Missing sequences simulated by zeroing the normalized channel.</li>
            <li>3-member ensembles; confidence U1 = mean pairwise Dice of the members.</li>
            <li>Baseline I = the missing-sequence indicator (random ranking within a condition).</li>
            <li>Primary endpoint: mean within-condition ET ΔAURC (U1 − I) over the four single-missing conditions.</li>
          </ul>
        </Card>
        <Card title="Experimental design">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li>Arm A: standard training. Arm B: modality-dropout training (primary).</li>
            <li>C4 = {"{−T1, −T1c, −T2, −FLAIR}"} (primary); Full is a control.</li>
            <li>Development: 740 BraTS 2021 non-UPenn cases, patient-group split 70/10/20 (seed 20260927).</li>
            <li>External: UPenn held-out institution (511) and BraTS-Africa (≤ 95), analysed separately.</li>
            <li>Patient-group bootstrap, 10,000 replicates (seed 12345); Holm within secondary families.</li>
          </ul>
        </Card>
      </section>

      {/* REPRODUCIBILITY */}
      <section className="my-10">
        <H2>Reproducibility</H2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Master runner", "One command runs every permitted step in protocol order."],
            ["Gate system", "Each data, split, compute and evaluation gate needs committed evidence."],
            ["Resume", "Crashed sessions resume from verified state; nothing silently restarts."],
            ["Provenance", "Every record carries commit, protocol hash, config and input hashes."],
            ["Safe export", "Only public-safe file types; imaging, checkpoints and demo files refused."],
          ].map(([t, d]) => (
            <Card key={t} title={t}>
              <p className="text-sm">{d}</p>
            </Card>
          ))}
        </div>
        <p className="mt-3 text-sm">
          <Link href="/reproducibility/" className="text-blue-700 underline dark:text-blue-400">
            Reproducibility details
          </Link>
        </p>
      </section>

      {/* CURRENT STATUS */}
      <section className="my-10">
        <H2>Current status</H2>
        <StageOverview />
        <p className="mt-3 text-sm text-slate-500">
          Data authorization: {status.data.authorization.toLowerCase()}
          {status.data.authorization_basis === "OWNER_APPROVED_ALTERNATIVE"
            ? " (owner-approved alternative; no external TCIA authorization is claimed)"
            : ""}
          . Data acquired: {status.data.acquired ? "yes" : "no"}. {status.data.statement}
        </p>
        {status.next_step ? (
          <p className="mt-3">
            <strong>Next step:</strong> <span className="mono">{status.next_step.gate}</span>. {status.next_step.description}
          </p>
        ) : null}
      </section>

      <section className="my-10">
        <H2>Research timeline</H2>
        <Timeline />
      </section>
    </div>
  );
}
