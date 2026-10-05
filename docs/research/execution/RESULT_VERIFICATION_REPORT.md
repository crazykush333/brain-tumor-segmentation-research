# Result verification report

**Status: NOT_RUN.** No real scientific result exists: the pre-registered experiment has not been executed (the master run stops at gate B2 - no GPU environment holding the official BraTS 2021 data). Nothing has been verified and nothing is published.

The verification system ([RESULT_VERIFICATION_PROTOCOL.md](RESULT_VERIFICATION_PROTOCOL.md)) runs automatically after the real analysis (master-run step VERIFY). Until then no result is verified or published.

## Discrepancies found and corrected during development

- **THRESHOLDS** (2026-10-05): transfer bootstrap p-value for delta-coverage at tau_0.80 (synthetic test study): production 0.30 vs independent recomputation 0.32. Cause: production computed the condition-weighted coverage in floating point, so an exactly zero delta-coverage became +/- 1e-17 and was counted on the wrong side of zero in the bootstrap p-value. Correction: production weighted_coverage_risk (statistics/thresholds.py) now computes the equal-weight coverage exactly with rational arithmetic; the verifier does the same independently. Reruns: no real analysis had been run, so no real result was affected; the synthetic test study was re-run and every stage then passed.
