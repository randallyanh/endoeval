# Internal staging status

This is a dedicated **private repository with clean history**. It replaces the unsafe Phase-0 branch that was a direct child of GP4DGS `main`.

## Rules

- Keep the repository private until double-blind and licence constraints permit disclosure.
- Do not add raw medical data, third-party source, model outputs, weights, checkpoints, or paper PDFs.
- Materialise scientific files only from exact Git object refs.
- Do not call this open source until explicit first-party licences are present.
- Do not claim raw replay until the authorised-input path is wired and exercised.
- Treat the exact repository commit as the external integrity anchor for `reproduce.py` and `CAPSULE_MANIFEST.json`.

## Phase 0 state

```text
clean-history private repository       complete
closed-tree manifest                   complete
minimal kernel snapshot                complete
formal literature-result snapshot      complete
Level-A executable verification        complete locally
minimal subprocess/tamper tests         complete locally
#103 final vectors/oracle               pending
#115 array adapter                      pending
Level-B raw replay                      blocked
licence decision                        pending
final release tags                      pending
```

GP4DGS issue #150 owns the final release scope and acceptance criteria.
