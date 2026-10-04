# B2–B6 software readiness: final sign-off

> **Snapshot of 2026-09-30.** The status tables below describe the state at sign-off. Since 2026-10-01, B1 has been AUTHORIZED through the owner-approved alternative (amendment v1.0-A1; external provider authorization NONE) and B2 is AUTHORIZED (ready, not executed). For the current state see [B1_DATA_ROUTE_AUTHORIZATION.md](B1_DATA_ROUTE_AUTHORIZATION.md).

**Result: SOFTWARE_B2_B6_READY**, meaning the software infrastructure is technically ready to execute *authorized* B2–B6 workflows. This is a statement about **software**, not about the study.

**No scientific experiment step has been completed.** No real data have been acquired. B2–B6 have **not** been executed on real data. No real B3/B4 hash, B5 manifest or B6 count verification exists. Real-data execution remains **BLOCKED** pending B1 data-route authorization.

## 1. Scope

- **In scope:** final validation of the B2–B6 software infrastructure:
  - acquisition layer and gate state machine;
  - evidence and provenance records;
  - hashing, manifests and B6 count logic;
  - path, link and atomicity safety;
  - repository hygiene, protocol and tag integrity;
  - the website status display.
- **Out of scope, and not done:**
  - acquiring or downloading any data;
  - real B2–B6 runs, B7, patient grouping, splits;
  - training, evaluation or any scientific analysis.

## 2. Protocol version

`docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md`, **v1.0, FROZEN**, git tag `protocol-v1.0`. It was not modified. No amendment has been introduced.

## 3. Software audit scope

Reviewed together:

- `data/`: `acquisition.py`, `stages.py`, `records.py`, `evidence.py`, `manifest_doc.py`, `integrity.py`, `synthetic.py`;
- `evaluation/`: `lifecycle.py`, `transitions.py`, `status.py`, `guards.py`;
- `utils/git.py`, `utils/paths.py`, `utils/io.py`;
- `results/site_export.py`, the CLI;
- tests: `test_b2_b6_software.py`, `test_b2_b6_audit.py`, `test_b2_b6_final_audit.py`, `test_data_gates.py`.

## 4. State-machine audit

- **Graph:** `B1 → B2 → {B3, B4} → B5 → B6 → B7 → … → B12`.
- **B gate states:** LOCKED, PENDING (B1 only), AUTHORIZED, RUNNING, PASSED, FAILED, BLOCKED.
- **Invariants, validated on every status load:**
  - a gate is LOCKED exactly while one of its prerequisites has not PASSED;
  - PASSED follows protocol order.
- **Rejected (tested):**
  - B1 PENDING→AUTHORIZED; B1 can only be authorized by reaching PASSED with machine-checkable evidence;
  - B2 LOCKED→AUTHORIZED before B1;
  - LOCKED→PASSED; any skipped prerequisite;
  - B4 passing before B3; B7 before B6 has PASSED;
  - FAILED→PASSED, FAILED→AUTHORIZED, FAILED→RUNNING;
  - FAILED or BLOCKED without evidence; unblocking without an owner-decision document.
- **Transition writer:**
  - validates the current file before applying anything;
  - fully re-validates the result, including evidence contents;
  - edits only the affected lines, and the re-parsed file must equal the validated mapping exactly;
  - writes atomically, and only with `--apply`.

## 5. Evidence audit

- **B1:** `docs/data/B1_EVIDENCE_<response date>.md` recording external written authorization: every template field exactly once and filled in, an external `Evidence type:`, `Authorization status: AUTHORIZED`, `Conclusion: APPROVED`, the provider's exact wording, and an `Approved route:` equal to `data.approved_route` (tightened after sign-off by the B1 workflow finalization, 2026-09-30). The B1 record, the inquiry and the template are rejected.
- **B2–B6:** each gate needs its own execution record. The rejected cases below are tested:

| Requirement | Rejected (tested) |
|---|---|
| schema and fingerprint re-validated by the typed reader | hand-written JSON; edited record; non-object JSON |
| record belongs to the gate | another gate's record |
| `data_class: REAL_RESEARCH_DATA`, `synthetic: false` | synthetic or relabelled records |
| clean committed checkout; commit exists and is an ancestor of HEAD | dirty tree; unknown commit; commit from a rewritten/orphan history |
| frozen protocol version and hash | `v0.5`; other hash |
| hashed configuration unchanged (staleness) | configuration edited or removed after the record |
| dataset identity (name, DOI) from `configs/dataset/brats2021.yaml` `evidence_identity`; official source | another dataset or DOI; mirror URL |
| committed or staged, not git-ignored, safe in-repo path | untracked; git-ignored (even if force-added); traversal, absolute or drive paths |
| links: B5 → B2/B3/B4 fingerprints; B6 → B3 fingerprint and crosswalk SHA-256; B6 `VERIFIED_FROM_SOURCE` | unlinked B5; B6 with another crosswalk hash; failed B6 |

## 6. Acquisition safety

- **Dry run is the default.** Without `--execute`, `acquire` only returns a plan: no network, no disk writes.
- **Real acquisition fails closed** unless all of these hold:
  - B1 PASSED;
  - B2 AUTHORIZED/RUNNING;
  - `data.authorization: APPROVED`;
  - adapter route equal to `data.approved_route`;
  - default clock;
  - storage root that is not a link, is empty and, inside the repository, only under the git-ignored `data/`.
- **The gate is enforced inside every real adapter's `execute()`**, so calling an adapter directly also fails with "Real-data acquisition is locked…" (fixed and tested in this pass).
- **Hidden-downloader scan (all tracked files):**

| Reference | Classification |
|---|---|
| `urllib.request.urlopen` in `data/acquisition.py` | gated acquisition infrastructure (`HttpsFileAdapter`, only after the gate) |
| `subprocess` in `scripts/experiments/train.py` | gated (`train_main`: B1–B12, D1–D6) nnU-Net launch; dry run unless `--execute`; not a downloader |
| `subprocess` in `utils/git.py` | read-only git queries (rev-parse, ls-files, check-ignore, merge-base, cat-file) |
| `subprocess`/git in tests | test-only |
| URLs and download words in `docs/` | documentation |
| `pip install` / `npm ci` in CI workflows | dependency installation, no study data |

- **Not found anywhere:** `requests`, Kaggle API, boto/GCS/Azure SDKs, wget/curl commands, `shell=True`, `os.system`, notebooks. The data and evaluation packages read no environment variables. The CLI has no force, skip, bypass or override options.

## 7. Synthetic/real isolation

- Every record and manifest carries an explicit `data_class`. Relabelling breaks the fingerprint.
- Synthetic mode accepts only unmodified files listed with their SHA-256 in a `SYNTHETIC_TEST_DATA.json` marker, outside the repository.
- **Rejected (tested):**
  - marker removed;
  - marker copied next to an unrelated real-looking file;
  - marker label edited;
  - modified synthetic file;
  - synthetic input in real mode;
  - synthetic tree through the real `local-import` adapter;
  - a marker appearing in real storage.
- A synthetic B6 success is `SYNTHETIC_TEST_ONLY` and can never close a gate.

## 8. Hash integrity

SHA-256 is computed over exact file bytes:

- same bytes give the same hash;
- changing one byte gives a different hash;
- a renamed copy has the same content hash;
- a missing file raises "input not found";
- a wrong file raises "requires the file".

Malformed values such as `TODO-hash` are rejected by record validation. **No real B3/B4 hash exists** in the repository. Placeholder-shaped values appear only in tests and temporary fake repositories.

## 9. Manifest integrity

- **Tested end to end:** synthetic source → inventory → hashes → provenance → schema validation → manifest → `manifest_sha256` → reload.
- **Deterministic:** two independent runs over identical bytes gave identical files, ordering, duplicates and hash.
- **Hash computed last:** after all final fields, including `gate`, `integrity` and `metadata_records`; any later change fails validation.
- **Metadata links:** real B5 requires the B3/B4 records, and metadata changed after hashing is rejected.
- **Raw vs derived:** derived manifests link to their parent hash.
- **Rejected:** empty and partial manifests, duplicate paths or slots, unsafe paths.

## 10. B6 verification logic

| State | Meaning | Tested |
|---|---|---|
| EXPECTED_BY_PROTOCOL | the protocol targets 1,251 / 511 / 740, always shown as "Protocol verification targets" | yes |
| UNAVAILABLE | no source processed (current state; also when B6 is AUTHORIZED but not run) | yes |
| VERIFIED_FROM_SOURCE | only a PASSED B6 whose REAL_RESEARCH_DATA record derived the counts from the hashed crosswalk | yes (fake repository) |
| FAILED_VERIFICATION | wrong counts or crosswalk ≠ B3 hash (record with diagnostics; stop per SR3) | yes |
| SYNTHETIC_TEST_ONLY | synthetic source matching the targets (software test only) | yes |

The targets alone can never yield VERIFIED_FROM_SOURCE. The counts record validator, the evidence validator and the display layer each refuse it.

## 11. Path and link safety

- **Links refused everywhere:** `is_link` detects symbolic links (including broken ones) and Windows directory junctions. It is used for deliveries, storage inventories, data trees, synthetic trees, stage inputs, storage roots and write targets.
- **Integrity audit:** reports links as errors without following them.
- **Relative paths:** one platform-independent rule rejects `/abs`, `\abs`, `C:/`, `..`, `.` and backslashes on every OS.
- **Write targets** that are existing files, directories, links or broken links are refused.
- **Tested with real OS links on this Windows machine** using directory junctions.

## 12. Atomicity

- **Atomic writes:**
  - JSON: temp file plus `os.replace`;
  - status file: `.part` plus `os.replace`, with the `.part` always removed;
  - manifest CSV and acquisition copies: `.part` then rename.
- **Simulated interruptions (tested):**
  - the previous status file stays byte-identical and valid;
  - no `.part`, partial JSON or partial CSV remains;
  - status never changes without validated evidence.

## 13. Test results

From the final run on 2026-09-30:

| Check | Result |
|---|---|
| pytest | **277 passed, 0 failed, 1 skipped** |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS (165 files) |
| `mypy` (configured: `files = ["src"]`, strict defs) | PASS (72 files) |
| package build + import | PASS (sdist and wheel; 71/71 modules import) |
| website production build | PASS |
| `brats-uncertainty check-repo` | PASS |

## 14. Skipped-test explanation

- **Skipped test:** `tests/unit/test_b2_b6_audit.py::test_file_symlinks_refused_posix`.
- **Why:** it creates a real OS **file** symbolic link. On Windows that requires SeCreateSymbolicLinkPrivilege or Developer Mode, which this account lacks, so `symlink_to` raises and the test skips with an explicit reason. It runs on Linux CI (`.github/workflows/ci.yml`, ubuntu-latest).
- **Equivalent coverage of the same safety property** (link entries are refused and never followed), both of which ran here:
  - `test_file_link_entries_refused_on_every_platform` drives every file-level refusal branch through the shared `is_link` hook, on every OS: delivery plan, storage inventory, synthetic tree, integrity audit, raw manifest and write target.
  - `test_b2_b6_final_audit.py` creates real OS **directory** links (Windows junctions here, symlinks on POSIX) and verifies refusal for deliveries, data trees, synthetic trees, storage roots, write targets and broken links.
- **Verdict: PASS.** Equivalent coverage exists. The only part not executed on this machine is the OS primitive that reports a file symlink (`Path.is_symlink`, standard library), which the POSIX run covers.

## 15. Repository scan

Tracked files were checked directly, and the working tree including ignored paths was also scanned. Findings:

- no imaging (NIfTI, DICOM, NRRD, MHA), arrays, checkpoints or weights;
- no archives or spreadsheets, and no gzip, ZIP, NIfTI or DICOM magic bytes in any tracked file;
- no CSV files;
- no patient-level ID lists;
- no split, result files or evaluation ledger;
- no credentials, tokens, private keys, `.env` or `kaggle.json`;
- no leftover `.part` files;
- `data/` contains only its README.

Synthetic fixtures are generated at test time in temporary directories (`tests/fixtures/`), never committed as data.

## 16. Protocol integrity

| | SHA-256 | Bytes |
|---|---|---|
| working tree `docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md` | `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811` | 69,163 |
| `git show protocol-v1.0:docs/research/FINAL_RESEARCH_PROTOCOL_v1.0.md` | `704c0b495917344f44b93e7548ade0e32a71220265419516a2c83d626fcd9811` | 69,163 |

**Byte-for-byte identical (`cmp`).**

Note: at the start of this pass the Windows working copy carried CRLF line endings (69,790 bytes). That came from the original `core.autocrlf` checkout, before `.gitattributes` set `eol=lf`. Git reported no change. With the owner's approval, the working copy was re-checked out from git. There was no commit and no content change; git status stayed clean.

## 17. Tag integrity

- `protocol-v1.0` = annotated tag object `0f46a8323cebab0a92d06a31885ae6b47924d361`, pointing to commit `4ef7ef707abafce4314884c6f271969b5bfbec32` (the freeze commit).
- The tag commit is an ancestor of HEAD, and no later commit touched the protocol file.
- No move, retag or history rewrite.

## 18. Website build

- The production static export passes.
- The stage overview renders:
  - Protocol v1.0 ✓ Frozen;
  - Data-route documentation ✓ Prepared;
  - B1 ⏳ Pending;
  - B2, B3, B4, B5, B6, B7 and Final split 🔒 Locked;
  - Training ○ Not started; Evaluation ○ Not started; Results ○ Not available.
- The targets 1,251 / 511 / 740 appear only as "Protocol verification target". "Verified dataset counts" and "Verified results" appear nowhere.
- B6 verification shows UNAVAILABLE. No empirical result appears.

## 19. Current gate state (`docs/project_status.yaml`)

| Item | State |
|---|---|
| Protocol | v1.0, FROZEN |
| Data | authorization PENDING; acquired false; approved route none |
| B1 | PENDING (no `B1_EVIDENCE_<date>.md` exists; TCIA inquiry prepared, not sent) |
| B2–B12 | LOCKED |
| Training | NOT_STARTED |
| Evaluation | internal NOT_STARTED, external NOT_STARTED |
| Results | UNAVAILABLE |

## 20. Known limitations

1. **Unkeyed fingerprints.** They detect accidental, stale, synthetic and mismatched evidence, not deliberate fraud by someone with write access and a real commit. Git history and review are the control.
2. **Private methods can be called in Python.** Adapter `_materialize` methods are not blocked by the language. All public interfaces (CLI, scripts, `stage_acquire`, `adapter.execute`) are gated.
3. **PASSED is terminal.** Invalidating a passed gate (SR5) requires a logged administrative entry and a validated manual status edit.
4. **Config edits invalidate evidence.** Changing `configs/dataset/brats2021.yaml` after B5/B6 evidence exists makes that evidence stale by design. Finalize `expected_shape` and confirm the crosswalk headers before B5/B6.
5. **Aspera compatibility unconfirmed.** The TCIA challenge download requires IBM Aspera Connect; whether it works with a runtime-only route is part of the TCIA inquiry.
6. **nnU-Net trainer template.** The trainer glue is still an unverified template (a D1/M1 concern, outside B2–B6).
7. **File-symlink primitive untested here.** OS file-symlink detection is exercised only on Linux CI (see §14).

---

Software B2–B6 infrastructure is READY for authorized execution. Real-data execution remains BLOCKED pending B1 data-route authorization.

Next authorized step: obtain and record B1 data-route authorization. After B1 is genuinely authorized, execute B2–B6 real-data verification as a separate controlled stage.
