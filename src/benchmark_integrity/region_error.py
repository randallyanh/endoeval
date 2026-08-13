"""Exact masked-PSNR coverage decomposition and score transport.

One numerical owner for the relation between scoring a selected region with
its own denominator (``true exclusion``) and scoring the same squared error
over every pixel (``keep`` / masked-multiply). For selected fraction ``c``
and true-exclusion MSE ``m`` the keep MSE is exactly ``c * m``, so under a
no-epsilon convention the gap is ``-10 log10(c)`` and under an
epsilon-inside-log convention it is ``10 log10((m + eps) / (c*m + eps))`` —
error-dependent, and zero at perfect prediction.

PSNR itself is NOT recomputed here: every score comes from
:func:`benchmark_integrity.metric_conventions.psnr_from_mse`, and mean
handling of infinite frames comes from ``psnr_value_for_mean``. This module
owns only the decomposition, the two supported reductions, and the canonical
``keep_minus_true_db`` sign.

Supported reductions: ``"frame_mean"`` (unweighted mean of per-frame PSNR)
and ``"pooled"`` (pooled counts and SSE). They are different estimands and
are never mixed.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from benchmark_integrity.metric_conventions import (
    MetricConventionError,
    PsnrConvention,
    psnr_from_mse,
    psnr_value_for_mean,
)

_FRAME_MEAN = "frame_mean"
_POOLED = "pooled"
_REDUCTIONS = (_FRAME_MEAN, _POOLED)

_COMPLETE = "complete"
_EMPTY_REGION = "empty_region"
_TIED_PERFECT = "tied_perfect"
_UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RegionErrorStats:
    """Sufficient statistics for one frame's selected-region squared error.

    ``selected_sse`` sums squared error over the selected pixels across all
    ``channels``; MSE is therefore ``selected_sse / (channels * pixels)``.
    """

    total_pixels: int
    selected_pixels: int
    selected_sse: float
    complement_sse: float | None = None
    channels: int = 3

    def __post_init__(self) -> None:
        for name in ("total_pixels", "selected_pixels", "channels"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise MetricConventionError(f"{name} must be an integer")
        if self.total_pixels <= 0:
            raise MetricConventionError("total_pixels must be positive")
        if self.channels <= 0:
            raise MetricConventionError("channels must be positive")
        if not 0 <= self.selected_pixels <= self.total_pixels:
            raise MetricConventionError("selected_pixels must lie within [0, total_pixels]")
        for name in ("selected_sse", "complement_sse"):
            value = getattr(self, name)
            if value is None:
                continue
            # bool is an int subclass and str/Decimal are float()-able: accept
            # only real built-in numbers, then normalise to float
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MetricConventionError(
                    f"{name} must be a real number, got {type(value).__name__}"
                )
            number = float(value)
            if not math.isfinite(number) or number < 0:
                raise MetricConventionError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, number)
        # partition consistency: error can only live where pixels exist
        if self.selected_pixels == 0 and float(self.selected_sse) > 0:
            raise MetricConventionError("selected_sse must be zero when no pixel is selected")
        if (
            self.complement_sse is not None
            and self.selected_pixels == self.total_pixels
            and float(self.complement_sse) > 0
        ):
            raise MetricConventionError(
                "complement_sse must be zero when the region covers every pixel"
            )


@dataclass(frozen=True)
class PsnrDenominatorResult:
    """One decomposition outcome under one declared convention.

    ``keep_minus_true_db`` is the ONLY canonical sign: keep scores higher
    whenever the selected region is a strict subset, so the value is
    non-negative for the no-epsilon convention. Any inverse value is a
    derived quantity and must be named as such by its consumer.
    """

    status: str
    true_mse: float | None
    keep_mse: float | None
    true_psnr: float | None
    keep_psnr: float | None
    keep_minus_true_db: float | None


def compare_psnr_denominators(
    stats: RegionErrorStats,
    *,
    convention: PsnrConvention,
) -> PsnrDenominatorResult:
    """Decompose one frame's selected-region error under one convention."""

    if stats.selected_pixels == 0:
        return PsnrDenominatorResult(_EMPTY_REGION, None, None, None, None, None)
    true_mse = stats.selected_sse / (stats.channels * stats.selected_pixels)
    keep_mse = stats.selected_sse / (stats.channels * stats.total_pixels)
    return _resolve(
        true_mse=true_mse,
        keep_mse=keep_mse,
        true_psnr=psnr_from_mse(true_mse, convention=convention),
        keep_psnr=psnr_from_mse(keep_mse, convention=convention),
    )


def aggregate_region_errors(
    records: Sequence[RegionErrorStats],
    *,
    reduction: str,
    convention: PsnrConvention,
) -> PsnrDenominatorResult:
    """Reduce per-frame statistics by pooled counts/SSE or by frame mean."""

    if reduction not in _REDUCTIONS:
        raise MetricConventionError(f"reduction must be one of {_REDUCTIONS}, got {reduction!r}")
    if not records:
        raise MetricConventionError("records must not be empty")
    channels = {record.channels for record in records}
    if len(channels) != 1:
        raise MetricConventionError("records must share one channel count")
    if reduction == _POOLED:
        return _pooled(records, channels=channels.pop(), convention=convention)
    return _frame_mean(records, convention=convention)


def _pooled(
    records: Sequence[RegionErrorStats],
    *,
    channels: int,
    convention: PsnrConvention,
) -> PsnrDenominatorResult:
    total_pixels = sum(record.total_pixels for record in records)
    selected_pixels = sum(record.selected_pixels for record in records)
    selected_sse = math.fsum(record.selected_sse for record in records)
    if selected_pixels == 0:
        return PsnrDenominatorResult(_EMPTY_REGION, None, None, None, None, None)
    true_mse = selected_sse / (channels * selected_pixels)
    keep_mse = selected_sse / (channels * total_pixels)
    return _resolve(
        true_mse=true_mse,
        keep_mse=keep_mse,
        true_psnr=psnr_from_mse(true_mse, convention=convention),
        keep_psnr=psnr_from_mse(keep_mse, convention=convention),
    )


def _frame_mean(
    records: Sequence[RegionErrorStats],
    *,
    convention: PsnrConvention,
) -> PsnrDenominatorResult:
    frames = [compare_psnr_denominators(record, convention=convention) for record in records]
    if any(frame.status == _EMPTY_REGION for frame in frames):
        # an unweighted mean over a partially undefined frame set has no
        # definition here; silently dropping frames would hide a policy
        return PsnrDenominatorResult(_UNSUPPORTED, None, None, None, None, None)
    perfect = [frame.status == _TIED_PERFECT for frame in frames]
    if any(perfect) and convention.mean_inf_cap_db is None:
        # only an ALL-perfect set ties; one infinite member must never make a
        # mixed set look perfect (it would forge an invariance witness)
        if all(perfect):
            infinity = float("inf")
            return PsnrDenominatorResult(_TIED_PERFECT, None, None, infinity, infinity, None)
        return PsnrDenominatorResult(_UNSUPPORTED, None, None, None, None, None)
    true_psnr = _mean_psnr(frames, keep=False, convention=convention)
    keep_psnr = _mean_psnr(frames, keep=True, convention=convention)
    # a frame mean is not derived from one MSE and never reports one
    return _resolve(true_mse=None, keep_mse=None, true_psnr=true_psnr, keep_psnr=keep_psnr)


def _mean_psnr(
    frames: Sequence[PsnrDenominatorResult],
    *,
    keep: bool,
    convention: PsnrConvention,
) -> float:
    values = [
        psnr_value_for_mean(
            frame.keep_psnr if keep else frame.true_psnr,  # type: ignore[arg-type]
            convention=convention,
        )
        for frame in frames
    ]
    return math.fsum(values) / len(values)


def _resolve(
    *,
    true_mse: float | None,
    keep_mse: float | None,
    true_psnr: float,
    keep_psnr: float,
) -> PsnrDenominatorResult:
    """Never manufacture a finite gap from infinite scores."""

    infinite = (math.isinf(true_psnr), math.isinf(keep_psnr))
    if all(infinite):
        return PsnrDenominatorResult(_TIED_PERFECT, true_mse, keep_mse, true_psnr, keep_psnr, None)
    if any(infinite):  # pragma: no cover - zero selected SSE makes both infinite
        return PsnrDenominatorResult(_UNSUPPORTED, true_mse, keep_mse, true_psnr, keep_psnr, None)
    return PsnrDenominatorResult(
        _COMPLETE, true_mse, keep_mse, true_psnr, keep_psnr, keep_psnr - true_psnr
    )


__all__ = [
    "PsnrDenominatorResult",
    "RegionErrorStats",
    "aggregate_region_errors",
    "compare_psnr_denominators",
]
