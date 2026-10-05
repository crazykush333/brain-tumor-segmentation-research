import Link from "next/link";
import { repoUrl, status } from "@/lib/data";

const LINKS: [string, string][] = [
  ["/research/", "Research"],
  ["/methodology/", "Methodology"],
  ["/protocol/", "Protocol"],
  ["/experiments/", "Experiments"],
  ["/results/", "Results"],
  ["/demo/", "Pipeline demo"],
  ["/reproducibility/", "Reproducibility"],
  ["/about/", "About"],
];

export function Nav() {
  return (
    <div className="border-b border-slate-200 dark:border-slate-800">
      <div className="bg-slate-900 px-4 py-1.5 text-center text-xs font-medium text-slate-100 dark:bg-slate-800">
        {status.headline}
      </div>
      <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-4">
        <Link href="/" className="mr-auto font-serif text-lg font-semibold text-slate-900 dark:text-slate-50">
          {status.project.short_title}
        </Link>
        {LINKS.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            className="text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          >
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

export function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-200 py-8 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
      <div className="mx-auto max-w-5xl space-y-1 px-4">
        <p>
          Protocol {status.protocol.version} ({status.protocol.status.toLowerCase()}, {status.protocol.frozen_on},
          tag <code className="mono">{status.protocol.git_tag}</code>). Status last updated {status.last_updated}.
        </p>
        <p>
          All status information on this site is generated from the repository&apos;s{" "}
          <code className="mono">docs/project_status.yaml</code>. This site contains no patient data.
        </p>
        <p>
          Source code, frozen protocol and gate records:{" "}
          <a href={repoUrl} className="underline">
            {repoUrl.replace("https://", "")}
          </a>
          . Scientific values are shown only after independent result verification.
        </p>
      </div>
    </footer>
  );
}
