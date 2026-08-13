"""Claim-conditioned comparability disposition.

This module decides what a particular *claim* is entitled to conclude from a
pair of evaluations. It owns no identity and opens no file: it takes
projections, not contracts. :class:`ComparisonFacts` records what a verifying
caller established against validated receipts, having already opened,
rehashed and recomputed everything this kernel never touches. A projection is
not trusted for being well typed: the record refuses values that could not
have come from the steps that produce them.

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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

_SHA256_LENGTH = 64
_HEX = frozenset("0123456789abcdef")
_SIDES = ("source", "target")


class ComparabilityError(ValueError):
    """A comparability fact or decision is malformed."""


def _require_sha256(value: object, *, field: str) -> None:
    if not isinstance(value, str) or len(value) != _SHA256_LENGTH or not _HEX.issuperset(value):
        raise ComparabilityError(f"{field} must be a lowercase 64-character sha256 digest")


def _require_flags(record: object, *, exclude: frozenset[str]) -> None:
    for name, value in vars(record).items():
        if name not in exclude and not isinstance(value, bool):
            raise ComparabilityError(f"{name} must be a bool, got {type(value).__name__}")


@dataclass(frozen=True)
class ComparisonFacts:
    """What a verifying caller established about one ordered evaluation pair.

    Every field is a decided fact about the two *measurements*. Nothing here
    is an allowlist, a contract or a policy: a policy permitting two protocols
    is not an undetermined measurement, and two evaluations sharing a support
    policy have not thereby earned a capability claim.

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
class ComparabilityDecision:
    """What one claim mode may conclude about one ordered evaluation pair."""

    claim_mode: str
    disposition: str
    source_identity: str
    target_identity: str
    reason_codes: tuple[str, ...]

    CLAIM_MODES: ClassVar[tuple[str, ...]] = ("scalar", "ordering", "capability")
    DISPOSITIONS: ClassVar[tuple[str, ...]] = (
        "identical",
        "rescore_required",
        "rerun_required",
        "target_mismatch",
        "unknown",
    )

    def __post_init__(self) -> None:
        if self.disposition not in self.DISPOSITIONS:
            raise ComparabilityError(f"unknown disposition {self.disposition!r}")


def assess_comparability(
    *,
    claim_mode: str,
    facts: ComparisonFacts,
) -> ComparabilityDecision:
    """Dispose of one ordered evaluation pair under one claim mode."""

    modes = ComparabilityDecision.CLAIM_MODES
    if claim_mode not in modes:
        raise ComparabilityError(f"claim_mode must be one of {modes}, got {claim_mode!r}")
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
        # sharing a support policy is not observing that either artifact
        # reached capability grade; only upstream admission can say that
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
    if rescore:
        return decide("rescore_required", rescore)
    return decide("identical", ())


__all__ = [
    "ComparabilityDecision",
    "ComparabilityError",
    "ComparisonFacts",
    "assess_comparability",
]
