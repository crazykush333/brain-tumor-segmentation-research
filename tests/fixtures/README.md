# Test fixtures: synthetic only

Everything in this directory is **synthetic**. It is generated in memory by
`synthetic.py` from fixed random seeds for software tests only.

- It is **not BraTS data**, not derived from BraTS data and not derived from any
  patient data.
- Synthetic case IDs use the prefix `SYN-` and never the BraTS naming pattern,
  except for the fixed protocol positive-control IDs where a test needs them. Those
  IDs are paired with synthetic masks and prove only that the code handles the IDs.
- No file here is an image, label volume or array dump. Volumes are created at test
  time in memory or in pytest's temporary directories.
- Synthetic numbers produced by tests are **never** results. They must not be
  written to `results/`, exported to the website or reported anywhere.
- `synthetic_b1/SYNTHETIC_TEST_ONLY_B1_AUTHORIZATION.md` is a **synthetic** provider
  response (source class `SYNTHETIC_TEST_AUTHORIZATION`), **not** an actual TCIA
  response. It drives the B1 parser and the test-only state
  `SYNTHETIC_TEST_B1: PENDING -> TEST_AUTHORIZED` (`data/synthetic_b1.py`). The real
  gate B1, real acquisition and the repository scan all refuse it. Never copy it to
  `docs/data/B1_EVIDENCE_<date>.md`.
- `nested_layout.py` builds, at test time and only in pytest temporary
  directories, a synthetic tree in the official nested TCIA layout
  (`<collection>/<case_id>/`). Its case IDs (`BraTS2021_SYNTH001` ...) are
  clearly synthetic and do not match the real `BraTS2021_<5 digits>` pattern.
  The files are tiny all-zero NIfTI headers and are never committed.
