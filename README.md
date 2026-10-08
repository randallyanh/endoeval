# EndoEval — Reference Evaluator

EndoEval evaluates rendered RGB outputs from dynamic endoscopic reconstruction methods under a versioned, inspectable measurement profile.

The repository is organised around one author workflow:

```text
render predictions
→ validate the expected frames
→ score one frozen profile
→ receive metrics, a paper table, a receipt, and a claim boundary
```

It is pre-release work accompanying the workshop paper linked below. It is not yet an open-source release, an official challenge evaluator, or a community standard. Adoption as a field default is tracked separately from the quality and completeness of this implementation.

## Paper and MICCAI 2026 workshop

**When Do Reproducible Scores Support a Valid Comparison in Dynamic Endoscopic Reconstruction?**

Hua Yan · Paper 8 · Joint AE-CAI | CARE | OR 2.0 | PRiSM Workshop @ MICCAI 2026

- [Read the revised manuscript (6-page Wiley PDF)](paper/paper8-revised-manuscript-clean.pdf)
- [Watch the conference presentation (MP4, 3:21)](presentation/paper8_video_final.mp4)
- [English captions (SRT)](presentation/paper8_video_final.srt)
- [Workshop homepage](https://workshops.ap-lab.ca/aecai2026/)
- [Official program — Paper 8, Short Oral #1: Endoscopic Reconstruction & Depth](https://workshops.ap-lab.ca/aecai2026/program/)
- [MICCAI 2026 conference](https://conferences.miccai.org/2026/)

The workshop took place on 27 September 2026 in Strasbourg, France. The
6-page revised manuscript is the source used for the conference presentation.
It preserves the anonymous review title page. Its identity matches the existing
presentation production record; final CMT-upload byte identity and journal
publication remain unverified. A separate 10-page reading copy is retained in
[the version and provenance note](paper/README.md).

## Install

Python 3.13 is the verified baseline.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-build-isolation --no-deps -e .
```

## Evaluate a method

Create a submission without changing training code:

```bash
endoeval init my-submission \
  --profile endonerf-rgb-v1 \
  --method my-method \
  --method-version paper-submission
```

Copy one RGB PNG for every name in the generated `EXPECTED_FRAMES.txt` files, then run:

```bash
endoeval validate my-submission/submission.json --check-paths

endoeval evaluate my-submission/submission.json \
  --dataset-root /path/to/EndoNeRF \
  --output my-submission/endoeval-output
```

A completed evaluation writes exactly:

```text
metrics.json
paper_table.csv
evaluation_receipt.json
admission.json
```

Verify the result without re-running the model:

```bash
endoeval verify my-submission/endoeval-output/evaluation_receipt.json
```

Compare two verified outputs:

```bash
endoeval compare \
  method-a/endoeval-output/evaluation_receipt.json \
  method-b/endoeval-output/evaluation_receipt.json \
  --claim ordering
```

## Current profile

`endonerf-rgb-v1` is a scoreable RGB profile with:

- EndoNeRF `cutting` and `pulling` scenes;
- 28 frozen dataset-native evaluation frames;
- 640×512 RGB inputs;
- dataset-valid, non-tool tissue support;
- PSNR with epsilon `1e-10`, true-exclusion denominator;
- unweighted frame mean and equal scene weight.

The profile verifies the reference image, tool mask, and invalid-region mask bytes before scoring. Prediction files are method-owned and are bound into the evaluation receipt.

## Nomenclature

- **prediction** — one method-owned rendered RGB frame under evaluation.
- **reference** — the dataset-owned ground-truth RGB frame with the same frame id.
- **support** — the pixel set a score is computed over: dataset-valid, non-tool tissue.
- **measurement** — the identified scoring configuration a receipt binds: output target, frame population, support, protocol, metric, and reduction.
- **receipt** — the sealed record binding one prediction set to one measurement and its outputs.

## Claim boundary

EndoEval directly supports:

- a scalar score under one identified measurement;
- an ordering between two fixed output sets when their measurement identities are equal.

An output-only evaluation does not establish training equivalence, method capability, clinical utility, or state of the art. `admission.json` and `endoeval compare` make that boundary explicit.

`baselines/` holds verified receipts for three public methods' render sets, with the same boundary applied; see `baselines/README.md`.

## Structure

```text
endoeval.py                         source-checkout entry
src/endoeval/cli.py                 user commands only
src/endoeval/canonical.py           canonical encoding, digests, path safety
src/endoeval/contracts.py           profile, authority, and submission contracts
src/endoeval/scoring.py             frame and scene measurements, four outputs
src/endoeval/receipts.py            offline verification and comparison
src/endoeval/image_stats.py         RGB/mask → sufficient statistics
src/endoeval/profiles/              versioned profile and authority
src/benchmark_integrity/            numerical and claim-admission kernel
baselines/                          verified receipts for public baseline render sets
examples/                           method-independent submission example
tests/                              three necessary integration boundaries
```

## Direct users

- Method authors: one output contract and paper-ready results.
- Reviewers: verify a receipt and inspect the strongest supported claim.
- Challenge organisers: reuse immutable profiles and organiser-owned rescoring.
- Maintainers: preserve source, profile, dataset, and licence boundaries.

Clinical and translational readers are served primarily by the paper and workshop presentation; this command-line evaluator is not a clinical product.

## Tests

The test surface is deliberately small:

```bash
python -B -m unittest discover -s tests -v
```

It contains exactly three top-level tests:

1. the full author workflow (`init → validate → evaluate → verify → compare`);
2. the load-bearing numerical and claim-admission boundary;
3. the bundled profile and unsafe-input boundary.

There is no coverage gate, mutation framework, hosted CI policy, benchmark server, database, GUI, plugin framework, or proof plane.
