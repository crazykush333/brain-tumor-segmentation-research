# Administrative entry: remote compute environment for the B1 route

Entry type: ADMINISTRATIVE / OPERATIONAL (not a design change)
Date: 2026-10-01
Owner: Ayush Kushwaha
Relates to: amendment v1.0-A1 (B1 operational data route); protocol §17, §24; SR7, SR8
Test-set data seen: No

## Owner instruction

The owner instructed, on 2026-10-01, that the study is to be executed in a private remote GPU environment. The local machine cannot run it: no CUDA GPU, insufficient RAM, and no study data. The instruction names a private GPU VM, a private Kaggle notebook runtime or Colab as candidate environments, under these conditions:
- the official source must be accessible directly from the environment;
- the data stay ephemeral or private;
- no persistent Kaggle Dataset, mirror, upload or redistribution is created;
- the official transfer route must actually work in that environment, and the environment is tested first.

## Clarification of the approved route

Amendment v1.0-A1 approves *direct official TCIA access into a private, access-restricted computational environment*. An **owner-controlled private GPU environment** is such an environment, whether a private VM, a private Kaggle notebook session or a private Colab runtime, provided that all of the following hold:
- data are downloaded directly from the official TCIA source into that environment's private storage, which is ephemeral for Kaggle and Colab;
- no Kaggle Dataset, mirror, shared copy or upload of the data is created, and raw data are never saved as notebook output;
- only records, reports, checkpoints and result artifacts leave the environment;
- each session that re-downloads the data verifies it against the committed B2 inventory before use.

This does **not** authorize private third-party re-hosting (for example a private Kaggle Dataset), which protocol §5.1 still reserves for TCIA confirmation. External provider authorization remains NONE.

## Impact

- **Scientific and methodological impact:** none.
- **Compute:** if the platform's hardware or quota differ from the plan, SR8 applies (recompute the budget).
- **Status:** no gate changes.
