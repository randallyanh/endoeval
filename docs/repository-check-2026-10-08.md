# Repository check — 8 October 2026

Audited code and assets at `59eae3d509b7c9c65cf5782a45800f66cce9415e`.
The accompanying changes correct documentation; evaluator code, scores, PDFs,
and video bytes are unchanged.

## Results

- Fresh Python 3.13 environment: locked dependency installation and editable
  package installation succeeded; `pip check` found no broken requirements.
- `python -B -m unittest discover -s tests -v`: all three tests passed without
  skips, including synthetic scoring, receipt tampering, and claim boundaries.
- Installed `endoeval profiles` worked from outside the source checkout.
- All three bundled baseline receipts verified. All three pairwise ordering
  comparisons returned `identical`; all capability comparisons returned
  `rerun_required` with capability-not-admitted reasons.
- Both PDFs, the MP4, and captions matched their recorded SHA-256 hashes.
  The primary manuscript has six pages and the reading copy has ten pages.
- Full MP4 decoding with `ffmpeg -v error -i ... -f null -` passed.
  All 39 SRT entries have sequential identifiers and ordered, non-overlapping
  timestamps within the 201.3-second video duration.
- All 13 relative Markdown file links present before these documentation
  corrections resolved. Workshop homepage and program were retrieved;
  the MICCAI conference URL returned HTTP 200 in a direct request.
- The [official program](https://workshops.ap-lab.ca/aecai2026/program/)
  lists the manuscript title as Paper 8 in Short Oral #1. The
  [workshop homepage](https://workshops.ap-lab.ca/aecai2026/) gives
  27 September 2026, Strasbourg, and identifies the planned Wiley special issue.
- GitHub metadata confirms `randallyanh/endoeval`, private visibility, and
  default branch `main`. The clone uses the renamed repository URL.

## Corrections

Clarified the two stored manuscript versions, removed outdated double-blind
release wording, documented existing dependencies and numeric baseline outputs,
and distinguished receipt verification from recomputation. Added clone commands,
paper/video entries to the repository map, and an ignore rule for generated
Python package metadata.

## Limits

The original baseline images and dataset were not used to recompute baseline
scores during this check; scoring was exercised with synthetic fixtures.
Receipt consistency alone is not independent certification of those scores.
The six-page manuscript matches the conference video production record, but
exact final CMT-upload bytes and journal acceptance/publication remain unverified.
The sent video's attachment bytes have not been independently downloaded and
compared. Licence selection and a complete public-release rights review remain
unresolved. This check does not change repository visibility or grant a licence.
