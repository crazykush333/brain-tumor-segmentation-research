# Archival provenance

## What this repository is

This public repository is a **clean release snapshot** of the project: its file tree is the
audited state of the research repository at the time of release, published with a fresh
Git history (a single release commit by Ayush Kushwaha). It represents the audited state
of the project; it adds no result and changes no part of the frozen design.

## Where the development history is

The full development history (39 commits, both branches and the annotated protocol tag)
is **preserved unchanged** — nothing was rewritten:

| Item | Value |
|---|---|
| Archival repository | `https://github.com/crazykush333/brain-tumor-segmentation-research-archive` (the original repository, renamed; marked historical) |
| Complete local backup | `BRATS-Research-history.bundle` (`git bundle --all`), SHA-256 `aa9e7e7adc1e88f2d9d0269c0c72b54028129a55ec1e9c63d9a7e011f81303e6`, verified with `git bundle verify` |
| Archived execution HEAD before the release preparation | `6a7e0af6ef0e98c17d3d100c0f4a7c80097158f3` (branch `infra/reproducibility-infrastructure`) |
| Archived commit whose tree is this release | tag `public-release` in the archival repository |
| Archived `main` | `4ef7ef707abafce4314884c6f271969b5bfbec32` |
| Protocol freeze tag | `protocol-v1.0` (annotated tag object `0f46a8323cebab0a92d06a31885ae6b47924d361`) → commit `4ef7ef707abafce4314884c6f271969b5bfbec32` |

The release tree is exactly the tree of the archived commit tagged `public-release` in
the archival repository (an additional tag; `protocol-v1.0` is untouched), verifiable
with `git archive` (see "Verification" below). An earlier candidate tag,
`public-release-source`, differs only in the runner's push branch (`main` for the public
repository) and is superseded.

## The frozen protocol is byte-identical

`docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md` in this release is byte-identical
(LF-normalized) to the blob at `protocol-v1.0` in the archival history:

- SHA-256 (LF-normalized text, as checked by `brats-uncertainty verify-protocol` and the
  regression tests): `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811`
- frozen on 2026-09-28 (gate A9), tagged `protocol-v1.0`; amendment v1.0-A1
  (2026-10-01, data route, no scientific change) is logged in
  `docs/research/protocol-amendments/`.

The protocol text was not modified, regenerated or reworded for the new history.

## Historical commit references

Some files record commit IDs of the **archival** history; they remain valid provenance
there and are intentionally left unchanged:

| Reference | Where | Meaning |
|---|---|---|
| `7bb9e15` | frozen protocol (freeze basis) | commit of the frozen text before tagging |
| `4ef7ef7` | `tests/regression/test_frozen_protocol.py`, B1 evidence, B2–B6 readiness doc | the `protocol-v1.0` tag target |
| `211a5fc` | B1 evidence | repository commit when the B1 record was created |
| `6a7e0af` and earlier | `docs/research/execution/run_summary.json`, gate records | archived execution commits |

These commits are not part of this repository's history. The tests that resolve the
`protocol-v1.0` tag skip when the tag is absent (as in this release) and the byte identity
is still enforced through the SHA-256 check. Future execution records will cite commits of
this repository.

## Verification

```bash
# protocol hash (LF-normalized) in this repository
brats-uncertainty verify-protocol
# against the archive
git clone https://github.com/crazykush333/brain-tumor-segmentation-research-archive archive
git -C archive show protocol-v1.0:docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md | sha256sum
# release tree vs. the archived release commit
git -C archive archive public-release | tar -t | grep -v '/$' | sort > archive.txt
git ls-files | sort > release.txt && diff archive.txt release.txt
```
