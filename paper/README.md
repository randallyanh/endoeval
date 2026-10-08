# Workshop manuscript

**When Do Reproducible Scores Support a Valid Comparison in Dynamic Endoscopic Reconstruction?**

Author: Hua Yan. Workshop: Joint AE-CAI | CARE | OR 2.0 | PRiSM Workshop @
MICCAI 2026, 27 September 2026, Strasbourg, France. The official program lists
this title as Paper 8 in Short Oral #1: Endoscopic Reconstruction & Depth.

- [Revised manuscript (6-page Wiley PDF)](paper8-revised-manuscript-clean.pdf)
- [Reading copy (10-page PDF)](when-do-reproducible-scores-support-a-valid-comparison.pdf)
- [Conference presentation](../presentation/README.md)
- [Workshop homepage](https://workshops.ap-lab.ca/aecai2026/)
- [Official program](https://workshops.ap-lab.ca/aecai2026/program/)

## Primary manuscript: six-page Wiley revision

The six-page clean revised manuscript was located through the conference
presentation production record. Its SHA-256 is
`276db2c8341310a2cf129fe7f9507be503db0482f7e39d56e9cb5d351f091ac1`,
which matches the manuscript identity recorded when the final video was made.
It has the current workshop title and retains the anonymous author line.
The original PDF is copied without modification. It is the manuscript used
for presentation preparation, not a newly typeset reconstruction. Exact final
CMT-upload byte identity and journal publication remain unverified.

## Secondary version: ten-page reading copy

This is the existing 10-page available-source reading copy, rebuilt on
27 September 2026 from revised manuscript source commit
`cc650da5ef50f8c4ded895b88fa36a1bb9481bcc`. It retains the original reading-copy
notice and anonymous author line; the file has not been edited or re-typeset
for this repository. It is not certified as byte-identical to the final CMT
upload and is not a publisher's version of record. No DOI or journal publication
status is asserted here.

The PDF was copied byte-for-byte from the existing research artifact
`output/pdf/companion_available_revision_cc650da5.pdf` in `randallyanh/GP4DGS`
(branch `paper/benchmark-validity-full`).

SHA-256: `5d5c49e5c6eb54b3cefda3d9028ed58e2d7a7192b98255c65f80e43dd7a35ac5`

The earlier July submission had a different title, “Are Surgical 4D
Reconstruction Leaderboards Comparable? Protocol-Hash Auditing for Endoscopic
Scene Reconstruction”; that superseded manuscript is not the PDF linked here.

The manuscript and code retain their respective rights. Adding this PDF does
not grant an open-source or Creative Commons licence; see
[the current licence status](../LICENSE_PENDING.md).

## Follow-up verification (8 October 2026)

- The official workshop program confirms the current title, CMT Paper 8, and
  Short Oral #1 session. Program inclusion establishes presentation context;
  it does not establish journal acceptance or publication.
- [The frozen revision record](https://github.com/randallyanh/GP4DGS/pull/139)
  describes a 6-page clean Wiley double-column manuscript. The PDF stored here
  is the 10-page article-class reading copy, not that original layout.
- The reading-copy build inputs for the abstract, body and bibliography were
  compared byte-for-byte with source commit `cc650da5`; all three match. The
  reading-copy wrapper imports those files and adds its version notice.
- The PDF bytes remain unchanged from the existing reading-copy artifact.
  This verification does not certify the final CMT-uploaded bytes, or rule out
  a later revision. Direct CMT download remains unverified because the
  available browser session requires login.

The initial check located only the reading copy. The later video-source check
located the six-page clean revision described above and promoted it to the main
README link. This corrects the earlier incomplete search; the reading-copy
checks remain valid. See [the source verification record](verification.json).
