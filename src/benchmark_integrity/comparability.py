"""Claim-conditioned comparability disposition (issue #94).

This module decides what a particular *claim* is entitled to conclude from a
pair of evaluations. It owns no identity, opens no file, and imports nothing
but the standard library — deliberately, because the open-core boundary frozen
for #103 forbids the scientific kernel from reaching the comparison, evidence,
population, training, resource, claim or closure contract graph.

So it takes projections, not contracts. :class:`ComparisonFacts` and
:class:`PsnrTransportFacts` record what an upstream adapter (#97) established
against validated objects, having already opened, rehashed and recomputed
everything this kernel is not allowed to touch. Two consequences follow, and
both are enforced rather than documented:

* A comparison track states which protocols a lane *permits*; the one a
  concrete evaluation used is pinned by the scoring closure. Deciding from the
  allowlist would call a determined measurement ambiguous, and would compare
  lane policy where measurement identity belongs.
* A projection is not trusted for being well typed. Both records refuse values
  that could not have come from the steps that produce them, and a transport
  must name the very measurements it was computed for.

Precedence is fixed and total, most decisive first:

``target_mismatch``
    The two evaluations do not estimate the same output object. No agreement
    between metrics repairs that, so it outranks everything.
``unknown``
    A side's measurement is not determined. Two undetermined sides look alike,
    and that likeness must never read as agreement.
``rerun_required``
    A difference no re-scoring of the stored renders can fix, including a
    capability claim over artifacts upstream has not admitted as capability
    grade. Admission is never inferred here.
``rescore_required``
    A scoring difference over the same rendered support.
``identical``
    Nothing critical differs.

Exactly two positive non-identical dispositions exist, and only the PSNR
keep/true-exclusion transform licenses them. Both require the two protocols to
differ in the denominator ALONE — a fact #97 establishes by diffing the actual
protocols, since a resize, compression, data-range, backend or aggregation
difference is not transportable and must not be waved through by the mere
presence of a recomputation.

``exact_transport`` (scalar) needs no more than that: one number restated under
the other denominator is exact under any convention.

Both dispositions are statements about a *common scale*. ``invariant`` means
that once both methods are expressed under one denominator, choosing keep or
true exclusion as that shared scale does not change their order. It never
licenses comparing one method's keep score against another's true-exclusion
score: each method has its own ``keep_minus_true_db``, so mixed-scale raw
values can order differently even where the common-scale order is preserved.
Converting every value onto the target scale before any paired inference is
the caller's obligation, and a positive disposition here is permission to do
that conversion, not permission to skip it.

``invariant`` (ordering) depends on the reduction, and the two cases are not
the same theorem:

``pooled``
    Both scores are strictly decreasing functions of the one pooled error,
    ``K - 10 log10(m + eps)`` and ``K - 10 log10(c*m + eps)``, and shared
    support fixes ``c`` for every method. Order is therefore preserved even
    with an epsilon, and no mean cap participates in a pooled score.
``frame_mean``
    Each frame contributes its own shift ``10 log10((m_f + eps)/(c_f*m_f +
    eps))``, which depends on that method's error in that frame, so the
    aggregate order can move. Only an epsilon-free, uncapped mean reduces to
    one shared constant ``-10 log10(c)``.

Treating those two alike is how a true statement about pooled PSNR becomes a
false general claim, so the reduction is carried explicitly rather than
inferred.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

_SHA256_LENGTH = 64
_HEX = frozenset("0123456789abcdef")
_SIDES = ("source", "target")
# the only transform proven exact enough to move a score between protocols
_TRANSPORT_KIND = "psnr_keep_true"
# the vocabulary EvalProtocol already uses for mask_denominator
_DENOMINATORS = ("keep_denominator", "true_exclusion")
_POOLED = "pooled"
_FRAME_MEAN = "frame_mean"
_REDUCTIONS = (_FRAME_MEAN, _POOLED)
# A denominator change IS a protocol change: mask_denominator is a
# protocol-critical field, so the protocol difference must be present. A
# metric-definition difference is admitted only as its mechanical consequence.
_TRANSPORT_REQUIRES = "scoring_protocol_differs"
_TRANSPORTABLE = frozenset({_TRANSPORT_REQUIRES, "metric_definition_differs"})


def _require_sha256(value: object, *, field: str) -> None:
    if not isinstance(value, str) or len(value) != _SHA256_LENGTH or not _HEX.issuperset(value):
        raise ValueError(f"{field} must be a lowercase 64-character sha256 digest")


def _require_gap_db(value: object, *, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a real number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    if number < 0:
        # keep scores the same squared error over more pixels, so keep never
        # falls below true exclusion; a negative gap is #95's sign inverted
        raise ValueError(f"{field} must be non-negative in the canonical keep-minus-true sign")


def _require_flags(record: object, *, exclude: frozenset[str]) -> None:
    for name, value in vars(record).items():
        if name not in exclude and not isinstance(value, bool):
            raise ValueError(f"{name} must be a bool, got {type(value).__name__}")


@dataclass(frozen=True)
class ComparisonFacts:
    """What an upstream adapter established about one ordered evaluation pair.

    Every field is a decided fact about the two *measurements*. Nothing here
    is an allowlist, a contract or a policy: a lane permitting two protocols
    is not an undetermined measurement, and two lanes sharing a support policy
    have not thereby earned a capability claim.

    ``scoring_protocol_equal`` and ``metric_definition_equal`` are separate on
    purpose. A protocol carries compression, resize, backend, colour and
    aggregation semantics that no metric definition restates, so letting one
    flag stand for both would silently call two differently-scored numbers
    identical.
    """

    source_identity: str
    target_identity: str
    output_target_equal: bool
    source_measurement_determined: bool
    target_measurement_determined: bool
    frame_population_equal: bool
    mask_support_equal: bool
    scoring_protocol_equal: bool
    metric_definition_equal: bool
    reduction_equal: bool
    source_capability_admitted: bool = False
    target_capability_admitted: bool = False

    _IDENTITIES: ClassVar[frozenset[str]] = frozenset({"source_identity", "target_identity"})

    def __post_init__(self) -> None:
        for name in sorted(self._IDENTITIES):
            _require_sha256(getattr(self, name), field=name)
        _require_flags(self, exclude=self._IDENTITIES)


@dataclass(frozen=True)
class PsnrTransportFacts:
    """The one transform allowed to license a positive disposition.

    #97 constructs this only after verifying the sidecar's file digest,
    reading it, parsing the #96 v2 evidence, verifying its contract digest,
    rebinding the real authorities, recomputing through #95, and diffing the
    actual protocols to establish that they differ in the denominator alone.
    The type confers no trust; it records that those steps were taken and
    refuses values that could not have come from them.

    The two measurement digests are what tie this record to one specific pair.
    Without them a transport computed for some other pair of evaluations would
    license a positive disposition here.
    """

    source_measurement_sha256: str
    target_measurement_sha256: str
    source_denominator: str
    target_denominator: str
    source_evidence_contract_sha256: str
    target_evidence_contract_sha256: str
    source_keep_minus_true_db: float
    target_keep_minus_true_db: float
    reduction: str
    denominator_only_difference: bool
    same_support: bool
    epsilon_free: bool
    infinity_capped: bool
    transport_kind: str = _TRANSPORT_KIND

    _TEXTS: ClassVar[frozenset[str]] = frozenset(
        {"transport_kind", "reduction", "source_denominator", "target_denominator"}
    )
    _DIGESTS: ClassVar[frozenset[str]] = frozenset(
        {
            "source_measurement_sha256",
            "target_measurement_sha256",
            "source_evidence_contract_sha256",
            "target_evidence_contract_sha256",
        }
    )
    _GAPS: ClassVar[frozenset[str]] = frozenset(
        {"source_keep_minus_true_db", "target_keep_minus_true_db"}
    )

    def __post_init__(self) -> None:
        if self.transport_kind != _TRANSPORT_KIND:
            raise ValueError(f"transport_kind must be {_TRANSPORT_KIND!r}")
        if self.reduction not in _REDUCTIONS:
            raise ValueError(f"reduction must be one of {_REDUCTIONS}, got {self.reduction!r}")
        for side in _SIDES:
            if getattr(self, f"{side}_denominator") not in _DENOMINATORS:
                raise ValueError(f"{side}_denominator must be one of {_DENOMINATORS}")
            _require_gap_db(
                getattr(self, f"{side}_keep_minus_true_db"), field=f"{side}_keep_minus_true_db"
            )
        for name in sorted(self._DIGESTS):
            _require_sha256(getattr(self, name), field=name)
        if self.source_denominator == self.target_denominator:
            # nothing is being transported, so no protocol difference is
            # explained by this record
            raise ValueError("a transport must relate two different denominators")
        _require_flags(self, exclude=self._TEXTS | self._DIGESTS | self._GAPS)


@dataclass(frozen=True)
class ComparabilityDecision:
    """What one claim mode may conclude about one ordered evaluation pair."""

    claim_mode: str
    disposition: str
    source_identity: str
    target_identity: str
    reason_codes: tuple[str, ...]
    evidence_contract_sha256s: tuple[str, ...] = ()

    CLAIM_MODES: ClassVar[tuple[str, ...]] = ("scalar", "ordering", "capability")
    DISPOSITIONS: ClassVar[tuple[str, ...]] = (
        "identical",
        "exact_transport",
        "invariant",
        "rescore_required",
        "rerun_required",
        "target_mismatch",
        "unknown",
    )

    def __post_init__(self) -> None:
        if self.disposition not in self.DISPOSITIONS:
            raise ValueError(f"unknown disposition {self.disposition!r}")


def assess_comparability(
    *,
    claim_mode: str,
    facts: ComparisonFacts,
    transport: PsnrTransportFacts | None = None,
) -> ComparabilityDecision:
    """Dispose of one ordered evaluation pair under one claim mode."""

    modes = ComparabilityDecision.CLAIM_MODES
    if claim_mode not in modes:
        raise ValueError(f"claim_mode must be one of {modes}, got {claim_mode!r}")
    supplied: object = facts  # an annotation is not a guarantee at run time
    if not isinstance(supplied, ComparisonFacts):
        raise TypeError(f"facts must be ComparisonFacts, got {type(facts).__name__}")

    def decide(disposition: str, reason_codes: tuple[str, ...]) -> ComparabilityDecision:
        return ComparabilityDecision(
            claim_mode,
            disposition,
            facts.source_identity,
            facts.target_identity,
            reason_codes,
        )

    def unmet(flag: str, code: str) -> tuple[str, ...]:
        return tuple(f"{side}_{code}" for side in _SIDES if not getattr(facts, f"{side}_{flag}"))

    if not facts.output_target_equal:
        return decide("target_mismatch", ("output_target_differs",))
    undetermined = unmet("measurement_determined", "measurement_undetermined")
    if undetermined:
        return decide("unknown", undetermined)
    if not facts.frame_population_equal:
        return decide("rerun_required", ("frame_population_differs",))
    if claim_mode == "capability":
        # comparing two lanes' support policy is not observing that either
        # artifact reached capability grade; only upstream can say that
        unadmitted = unmet("capability_admitted", "capability_not_admitted")
        if unadmitted:
            return decide("rerun_required", unadmitted)
    rescore = tuple(
        code
        for code, equal in (
            ("mask_support_differs", facts.mask_support_equal),
            ("scoring_protocol_differs", facts.scoring_protocol_equal),
            ("metric_definition_differs", facts.metric_definition_equal),
            ("reduction_differs", facts.reduction_equal),
        )
        if not equal
    )
    if not rescore:
        return decide("identical", ())
    transported = _transported(claim_mode, rescore, facts, transport)
    if transported is None or transport is None:
        return decide("rescore_required", rescore)
    return ComparabilityDecision(
        claim_mode,
        transported,
        facts.source_identity,
        facts.target_identity,
        rescore,
        (transport.source_evidence_contract_sha256, transport.target_evidence_contract_sha256),
    )


def _transported(
    claim_mode: str,
    reason_codes: tuple[str, ...],
    facts: ComparisonFacts,
    transport: PsnrTransportFacts | None,
) -> str | None:
    """Name the positive disposition this transform licenses, if any.

    A capability claim is never one of them: restating a score under another
    denominator says nothing about how either method was trained.
    """

    codes = set(reason_codes)
    if claim_mode == "capability" or _TRANSPORT_REQUIRES not in codes:
        return None
    if not _TRANSPORTABLE.issuperset(codes):
        return None
    if not isinstance(transport, PsnrTransportFacts):
        return None
    if (transport.source_measurement_sha256, transport.target_measurement_sha256) != (
        facts.source_identity,
        facts.target_identity,
    ):
        # a transport computed for some other pair explains nothing here
        return None
    if not (transport.denominator_only_difference and transport.same_support):
        return None
    if claim_mode == "scalar":
        return "exact_transport"
    if transport.reduction == _POOLED:
        # both scores are strictly decreasing in the one pooled error and
        # shared support fixes c, so the order survives even with an epsilon
        return "invariant"
    if transport.epsilon_free and not transport.infinity_capped:
        # only then does the per-frame shift collapse to one shared constant
        return "invariant"
    return None


__all__ = [
    "ComparabilityDecision",
    "ComparisonFacts",
    "PsnrTransportFacts",
    "assess_comparability",
]
