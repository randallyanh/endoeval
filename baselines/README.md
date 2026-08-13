# Baseline receipts

Verified `endonerf-rgb-v1` evaluations of three publicly released dynamic
endoscopic reconstruction methods, scored on author-produced render sets.

| method           | render set                                   | aggregate PSNR (dB) |
| ---------------- | -------------------------------------------- | ------------------- |
| surgicalgaussian | official code, retrained, iteration 3000     | 19.262859           |
| endogaussian     | official code, retrained, iteration 3000     | 17.988208           |
| endo4dgs         | released pretrained checkpoint, iteration 3000 | 11.208336         |

Each directory holds one complete evaluation output set. Every receipt
verifies offline against the bundled profile:

```bash
endoeval verify baselines/<method>/evaluation_receipt.json
```

All three pairwise comparisons under `--claim ordering` return disposition
`identical` — the measurement identities are equal — so the ordering
surgicalgaussian > endogaussian > endo4dgs is admitted for these render sets.

Render sets covering only one scene (deform3dgs, endosurf) cannot receive a
receipt under this two-scene profile and are not listed.

## Claim boundary

These receipts certify the scores of the specific rendered artifact sets named
in each receipt (`prediction_set_sha256`), under one frozen measurement. The
render sets are low-iteration retrains or released checkpoints, not the
methods' best published configurations; per each `admission.json`, no
capability claim about any method is admitted. Comparing a number here against
a paper's self-reported score is exactly the protocol mismatch this evaluator
exists to make visible.
