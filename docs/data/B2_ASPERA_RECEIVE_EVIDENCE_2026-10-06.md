# B2 receive-command evidence (IBM Aspera CLI, official TCIA Faspex package)

- Recorded: 2026-10-06, owner Ayush Kushwaha.
- Session: private Kaggle notebook `brats-00-environment-probe` (generated from `experiments/kaggle/00_environment_probe.ipynb`), repository commit `f95a35683bb8c564828a167b340523bf6a21c7b7`.
- Purpose: confirms `acquisition.receive_command` and `acquisition.selected_gib` in `configs/compute/master_run.yaml` from the installed official client's own help and behaviour. Nothing is guessed.
- Format: the excerpts below are **transcribed** from the session output. They are not a byte copy.

No BraTS data are stored here. The package link is not stored either: it embeds a package passcode. It is the "DOWNLOAD (142GB)" link of https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/, and the session supplies it at run time as `BRATS_TCIA_PACKAGE_URL`.

## Client

The client was installed as IBM's README describes (`gem install aspera-cli`, `ascli config transferd install`).

| Item | Value |
|---|---|
| `aspera-cli` | 4.27.3 |
| IBM Aspera Transfer SDK | 1.1.9, installed in `/root/.aspera/sdk` |
| `ascp` | `/root/.aspera/sdk/ascp`, version 4.4.8.2592 |

## Help excerpts

From `ascli faspex5 -h`:

```
COMMAND: faspex5
  SUBCOMMANDS:
    packages        Manage packages
```

From `ascli faspex5 packages -h`, filtered with `grep -n -i -E 'receive|browse|public|--url|to-folder|sources|SUBCOMMANDS'`:

```
94:    --to-folder=VALUE        Destination folder for transferred files
95:    --sources=VALUE          How list of transferred files is provided (@args,@ts,Array)
109:   --url=VALUE              URL of application, e.g. https://app.example.com/aspera/app
116: SUBCOMMANDS:
120:   browse           Browse package files
123:   receive          Receive a package
```

The global options also list `--ts=HASH`: "Override transfer spec values".

## Package listing (metadata only, `packages browse`)

The package root contains two entries:
- `/RSNA-ASNR-MICCAI-BraTS-2021.sums`, a file of 49,850,968 bytes;
- `/RSNA-ASNR-MICCAI-BraTS-2021/`, a directory.

`/RSNA-ASNR-MICCAI-BraTS-2021/` contains four directories:
- `BraTS2021_TrainingSet`
- `BraTS2021_TrainingSet_dcm`
- `BraTS2021_ValidationSet`
- `BraTS2021_ValidationSet_dcm`

`BraTS2021_TrainingSet` has eight collection directories:
- ACRIN-FMISO-Brain, CPTAC-GBM, IvyGAP, TCGA-GBM, TCGA-LGG, UCSF-PDGM, UPENN-GBM;
- new-not-previously-in-TCIA.

Each case is laid out as `<collection>/BraTS2021_xxxxx/BraTS2021_xxxxx_{flair,seg,t1,t1ce,t2}.nii.gz`.

A full recursive listing of `BraTS2021_TrainingSet` gave:

| Item | Count or size |
|---|---|
| Files | **6,255** (= 1,251 cases × 5) |
| Directories | **1,259** (= 8 collections + 1,251 cases) |
| Training set | **13,383,266,621 bytes** (12.464 GiB) |

The `.sums` file lists 6,255 `RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet/` entries, one MD5 and one relative path per line.

**selected_gib = 12.511.** The selection is the training set plus the `.sums` file: 13,433,117,589 bytes = 12.5106 GiB, rounded up.

## Receive behaviour (tested in the session with a small selection, then deleted)

| Command form | Result |
|---|---|
| `receive --url=<link> --to-folder=<d> --ts=@json:{"paths":[{"source":...}]}` (no `--sources`) | The selection was **ignored** and the whole package started arriving. Stopped after 379 MB; the partial data were deleted. |
| Same with `--sources=@ts` and `{"source":...}` items | Faspex returned HTTP 500 ("undefined method 'starts_with?' for nil"). |
| `--sources=@ts` with `{"path":P,"source":P}` items | rc 0. Exactly the selected items arrived: the `.sums` file and one case folder, 6 files, 69 MB. |
| The final two-step command (below), run through `shlex.split` with the delivery folder as cwd | rc 0. Produced `RSNA-ASNR-MICCAI-BraTS-2021.sums` and `RSNA-ASNR-MICCAI-BraTS-2021/<selected folder>/…`. |

The client places each selected item in `--to-folder` under its basename. The training set is therefore received into `RSNA-ASNR-MICCAI-BraTS-2021/`, which gives the official layout that the `.sums` paths and `acquisition.training_set` expect (`RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet`).

## Recorded command (`acquisition.receive_command`)

```
sh -c ': "${BRATS_TCIA_PACKAGE_URL:?...}" && ascli faspex5 packages receive --url="$BRATS_TCIA_PACKAGE_URL" --sources=@ts --to-folder=. --ts=@json:'{"paths":[{"path":"/RSNA-ASNR-MICCAI-BraTS-2021.sums","source":"/RSNA-ASNR-MICCAI-BraTS-2021.sums"}]}' && mkdir -p RSNA-ASNR-MICCAI-BraTS-2021 && ascli faspex5 packages receive --url="$BRATS_TCIA_PACKAGE_URL" --sources=@ts --to-folder=RSNA-ASNR-MICCAI-BraTS-2021 --ts=@json:'{"paths":[{"path":"/RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet","source":"/RSNA-ASNR-MICCAI-BraTS-2021/BraTS2021_TrainingSet"}]}''
```

The exact string, with its quoting, is the value in `configs/compute/master_run.yaml`.

The session test used the same selection items and the same two-step structure, with the URL passed literally rather than through `BRATS_TCIA_PACKAGE_URL`, and with one case folder in place of the training set. If the full receive fails, gate B2 stops; it is never retried with a different command.
