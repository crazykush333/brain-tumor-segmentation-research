# A5 identity verification

A5_IDENTITY_VERIFICATION = VERIFIED

Independent re-implementation (`brats_uncertainty.verification.identity_audit`, which does not import the production grouping code) versus the production cohort (`brats_uncertainty.grouping.identity_clean`).

- primary cohort identical: True (production 497, independent 497)
- quarantine identical: True (production 243, independent 243)
- patient groups identical: True (production 495, independent 495)
