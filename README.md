# EndoEval — Private Product Foundation

**EndoEval** is a profile-driven evaluation tool for dynamic endoscopic reconstruction.

Its intended author workflow is:

```text
render predictions
→ choose one versioned evaluation profile
→ run one command
→ receive canonical metrics, a paper table, a measurement receipt, and an admission decision
```

This repository is private pre-release work. It is not yet an open-source release, an official challenge evaluator, or an established community standard.

## Quick start

```bash
python -I -S -B endoeval.py profiles
python -I -S -B endoeval.py profile endonerf-rgb-v1
python -I -S -B endoeval.py validate examples/minimal-submission/submission.json
python -I -S -B endoeval.py evaluate examples/minimal-submission/submission.json
```

The first three commands work in the private foundation. `evaluate` currently exits with a machine-readable `blocked` disposition because the final EndoNeRF frame/support authorities and the maintained RGB/mask-to-statistics adapter are not yet frozen. It never fabricates a score.

## Why method authors should use it

- **Output-first:** normal integration supplies rendered outputs; it does not modify training code.
- **Method-agnostic:** NeRF, 3DGS/4DGS, diffusion-assisted, and future representations use the same submission contract.
- **Versioned:** a profile change creates a new profile ID instead of silently changing old scores.
- **Paper-ready:** a completed evaluation will produce exactly four outputs:

```text
metrics.json
evaluation_receipt.json
paper_table.csv
admission.json
```

- **Reviewable:** the receipt records the cases, evaluation region, metric convention, reduction, and artifact/source identities needed to interpret a comparison.

## Direct users

1. **Method authors** want a zero-training-change path from renders to paper-ready results.
2. **Paper reviewers** want to verify a receipt and see the strongest comparison claim the evidence supports.
3. **Challenge organisers** want immutable profiles and benchmark-owned rescoring rules.
4. **Maintainers** want a small, licensed, provenance-bound release surface.

Clinical and translational readers are served primarily by the paper and workshop presentation. This CLI is not a clinical product.

## Repository structure

```text
endoeval.py                    user-facing command
src/endoeval/                  profile and submission contract
profiles/                      versioned evaluation profiles
examples/                      method-independent submission example
src/benchmark_integrity/       numerical and claim-admission kernel
tests/                         exactly three focused test files
```

The Paper 3 reproducibility capsule remains a separate evidence surface while this product foundation is reviewed. It will be imported later under a bounded `paper3/` path rather than defining the root user experience.

## Current profile

`endonerf-rgb-v1` fixes the intended dynamic-endoscopic RGB task, two EndoNeRF scenes, the output-directory contract, the measurement fields that must be closed, and the four output artifacts. Its status is currently `draft_not_scoreable`.

## Default-tool adoption gates

EndoEval will be called the field default only after all of the following are observed:

- a new method connects in **10 minutes or less**;
- normal integration changes **zero training-code lines**;
- one NeRF, one 3DGS/4DGS, and one independently owned new method use the same evaluator path without method-specific branches;
- one command produces all four outputs with no hand-edited paper numbers;
- an external author uses it in a submission or revision;
- a reviewer verifies a receipt;
- a challenge organiser accepts or pilots the profile.

Until then it is a **candidate default/reference evaluator**.

## Test boundary

The repository keeps exactly three test files:

```text
test_user_workflow.py
test_kernel_conformance.py
test_profile_integrity.py
```

New cases extend these files. There is no hosted CI policy, coverage threshold, mutation framework, gate registry, or proof plane.
