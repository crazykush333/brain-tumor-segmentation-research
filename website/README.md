# Research website

A Next.js (App Router) + TypeScript + Tailwind CSS site built as a **static export** (`out/`). It needs no server runtime, no database and no secrets.

## Data flow

The website does not contain hand-typed project status or numbers. Everything comes from `website/data/*.json`:

```
docs/project_status.yaml ─┐
configs/protocol/*.yaml ──┼─► brats-uncertainty export-site-data ─► website/data/{status,protocol,experiments,results}.json ─► pages
experiments/*/metadata ───┤
results/index.json ───────┘   (provenance-checked; synthetic artifacts refused)
```

After changing any source, regenerate and commit the JSON:

```bash
brats-uncertainty export-site-data          # from the repository root
```

CI (`export-site-data --check` and `tests/integration/test_site_data_sync.py`) fails if the committed JSON is stale. While `results.available` is false, the Results page shows only: *"Scientific results are not yet available. Experimental execution is pending."*

## Local development

```bash
cd website
npm ci
npm run dev          # http://localhost:3000
npm run build        # static export to website/out
npm run typecheck
```

Requires Node.js ≥ 20.

## Pages

`/` (status, next step, timeline) · `/research` · `/methodology` · `/protocol` (identity, freeze rule, gates) · `/experiments` · `/results` · `/reproducibility` · `/about`

## Deployment

### Vercel

1. Import the repository and set **Root Directory** to `website`.
2. Framework preset: Next.js. `vercel.json` sets the build command and the `out` output directory.
3. Optional environment variable: `NEXT_PUBLIC_REPO_URL`, the public repository URL used to link source files.

### Netlify

1. Set **Base directory** to `website`. `netlify.toml` sets `npm run build` and publishes `out`.
2. Optionally set `NEXT_PUBLIC_REPO_URL`.

### Environment variables

| Variable | Secret? | Purpose |
|---|---|---|
| `NEXT_PUBLIC_REPO_URL` | **No** (public by design) | builds links to repository files |

**Never put a secret in a `NEXT_PUBLIC_*` variable.** These values are embedded in the public JavaScript bundle. The site needs no secrets at all.

## Content rules

- Status text must match `docs/project_status.yaml`. It must never claim an experiment or result that does not exist.
- Synthetic test data are never shown as research results.
- No patient images or data of any kind.
