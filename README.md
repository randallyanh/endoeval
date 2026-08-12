# Paper 3 Reproducibility Capsule — Private Staging

This private repository is the clean-history staging surface for the minimal reproducibility capsule associated with Paper 3:

> *When Do Reproducible Scores Support a Valid Comparison in Dynamic Endoscopic Reconstruction?*

It is not yet a public release or an open-source grant.

## What works now

The current **Level A / Phase 0** path is standard-library only and runs without a GP4DGS checkout, network access, raw medical images, or third-party method code:

```bash
python -I reproduce.py verify
python -m unittest discover -s tests -v
```

It verifies:

- a closed file manifest for the complete private staging tree;
- exact local identities and frozen source metadata for the copied numerical and comparison kernel;
- PSNR convention and selected-region denominator mathematics;
- claim-conditioned `scalar`, `ordering`, and `capability` dispositions;
- the frozen formal literature-audit result and its declared headline counts.

## Deliberately pending

The capsule does **not** yet claim:

- the final #103 public conformance vectors or independent oracle;
- the post-#115 RGB/mask-to-sufficient-statistics adapter;
- seven-row replay, common-support rescore, or sensitivity regeneration;
- complete literature-result regeneration from all first/second-pass records;
- raw-image replay;
- a first-party code or records licence;
- public-release readiness.

The raw command fails closed by design:

```bash
python -I reproduce.py raw --input-root /path/to/licensed-inputs
```

## Integrity model

`CAPSULE_MANIFEST.json` closes the managed file set and binds each file's SHA-256 and size. `SOURCE_REFS.json` records the exact upstream repository refs, paths, Git blob identities, and source SHA-256 values for unmodified scientific snapshots.

The runtime verifier detects accidental or isolated file tampering. The repository commit SHA is the external anchor for the verifier and manifest themselves; no self-contained program can establish integrity after an attacker has replaced both its code and its expectations.

## Release boundary

No dataset bytes, paper PDFs, external source archives, model weights, checkpoints, renders, references, masks, or third-party method outputs are included. See `RELEASE_SCOPE.md`, `LICENSE_PENDING.md`, and `THIRD_PARTY_NOTICES_DRAFT.md`.
