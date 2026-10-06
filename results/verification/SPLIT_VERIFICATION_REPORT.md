# Independent split verification (gates B8-B12)

OVERALL_SPLIT_VERIFICATION = VERIFIED

Produced by `brats-uncertainty audit-split` (`brats_uncertainty.verification.split_audit`), which re-derives the patient groups from committed records without importing the production grouping or split code.

- B8 procedure: identity_clean_v1.0-A5
- development pool 740: primary (identity-clean) 497, quarantine 243 (never split)
- patient groups: 495 over 497 cases; largest 2; size counts {'1': 493, '2': 2}
- split seed: 20260927
- cases per partition: {'internal_test': 100, 'train': 347, 'validation': 50}
- groups per partition: {'internal_test': 99, 'train': 346, 'validation': 50}
- sites per partition: {'internal_test': {'10': 2, '11': 3, '12': 1, '13': 8, '14': 1, '15': 2, '16': 8, '18': 55, '20': 7, '5': 6, '6': 3, '7': 1, '8': 2, '9': 1}, 'train': {'10': 6, '11': 8, '12': 9, '13': 22, '14': 5, '15': 10, '16': 20, '18': 181, '19': 4, '20': 22, '5': 14, '6': 29, '7': 10, '8': 4, '9': 3}, 'validation': {'11': 3, '12': 1, '13': 5, '15': 1, '16': 2, '18': 27, '20': 4, '5': 2, '6': 2, '7': 1, '8': 2}}
- split_all.csv SHA-256: `393726596f1f34011d14f3e0e2daf543f09a7ee36501e687a6bddd6cd0d60005`
- groups crossing partitions: 0

| Check | Result |
|---|---|
| a5_config_hash | PASS |
| a5_acceptance_passed | PASS |
| a5_independent_identity_verification | PASS |
| a5_primary_plus_quarantine_equals_b6_development | PASS |
| a5_quarantine_has_no_identity_key | PASS |
| b9_groups_equal_independent_recomputation | PASS |
| b9_covers_exactly_the_primary_cohort | PASS |
| split_covers_exactly_development | PASS |
| split_groups_equal_b9_groups | PASS |
| split_partitions_are_train_validation_test | PASS |
| no_patient_group_crosses_partitions | PASS |
| verified_groups_A_B_intact | PASS |
| split_seed_20260927 | PASS |
| b12_split_hash_matches_file | PASS |
| b12_groups_hash_matches_file | PASS |
| b12_partition_id_hashes_match | PASS |
| a5_cohort_sites_match_b6_site_counts | PASS |
| no_site1_in_split | PASS |
