import type { Metadata } from "next";
import { KeyValue, PageHeader } from "@/components/ui";
import { protocol, repoUrl, status } from "@/lib/data";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return (
    <article className="prose-block">
      <PageHeader title="About" />
      <KeyValue
        rows={[
          ["Project", status.project.title],
          ["Type", status.project.type],
          ["Owner", status.project.owner],
          ["Same-patient review: primary reviewer", protocol.parameters.grouping.primary_reviewer],
          ["Same-patient review: second reviewer", protocol.parameters.grouping.second_reviewer],
          ["Software version", status.package_version],
          ["Repository", repoUrl ? <a key="r" href={repoUrl} className="text-blue-700 underline dark:text-blue-400">{repoUrl}</a> : "not yet public"],
        ]}
      />

      <h2>Licence and citation</h2>
      <p>
        The code is planned to be released under the Apache License 2.0. The licence choice is pending owner
        confirmation. The licence covers code only; each dataset keeps its own terms. The repository&apos;s{" "}
        <code className="mono">CITATION.cff</code> describes how to cite the software. No paper exists yet.
      </p>

      <h2>Data acknowledgement</h2>
      <p>
        This study is designed to use the RSNA-ASNR-MICCAI BraTS 2021 challenge data and the TCIA BraTS-Africa
        collection, under their respective terms and citation requirements. No data from either source are hosted
        on this website or in the repository.
      </p>
    </article>
  );
}
