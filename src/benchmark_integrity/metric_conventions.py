"""Metric-convention primitives for auditable benchmark numbers."""

from __future__ import annotations

import math
from dataclasses import dataclass

PSNR_ZERO_POLICY_EPS = "eps"
PSNR_ZERO_POLICY_INF = "inf"
PSNR_ZERO_POLICIES = (PSNR_ZERO_POLICY_EPS, PSNR_ZERO_POLICY_INF)


class MetricConventionError(ValueError):
    """A metric convention or metric input is malformed."""


@dataclass(frozen=True)
class PsnrConvention:
    """Explicit PSNR convention, especially for zero-MSE frames."""

    name: str
    zero_policy: str
    eps: float | None = None
    data_range: float = 1.0
    mean_inf_cap_db: float | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise MetricConventionError("PSNR convention name must be non-empty")
        if self.zero_policy not in PSNR_ZERO_POLICIES:
            raise MetricConventionError(
                f"zero_policy must be one of {PSNR_ZERO_POLICIES}, got {self.zero_policy!r}"
            )
        if not math.isfinite(float(self.data_range)) or float(self.data_range) <= 0:
            raise MetricConventionError("data_range must be finite and positive")
        if self.zero_policy == PSNR_ZERO_POLICY_EPS and (
            self.eps is None or not math.isfinite(float(self.eps)) or float(self.eps) <= 0
        ):
            raise MetricConventionError("eps zero_policy requires a finite positive eps")
        if self.zero_policy == PSNR_ZERO_POLICY_INF and self.eps is not None:
            raise MetricConventionError("inf zero_policy must not set eps")
        if self.mean_inf_cap_db is not None and not math.isfinite(float(self.mean_inf_cap_db)):
            raise MetricConventionError("mean_inf_cap_db must be finite when set")


FINITE_PSNR_CONVENTION = PsnrConvention(
    name="psnr_mse_eps_1e-10",
    zero_policy=PSNR_ZERO_POLICY_EPS,
    eps=1e-10,
)


def psnr_from_mse(
    mse: float,
    *,
    convention: PsnrConvention = FINITE_PSNR_CONVENTION,
) -> float:
    """Compute PSNR from an MSE under an explicit zero-MSE convention."""

    value = float(mse)
    if math.isnan(value) or value < 0:
        raise MetricConventionError(f"mse must be non-negative, got {mse!r}")
    data_range_term = 20.0 * math.log10(float(convention.data_range))
    if convention.zero_policy == PSNR_ZERO_POLICY_INF:
        if value <= 0:
            return float("inf")
        return data_range_term - 10.0 * math.log10(value)
    if convention.eps is None:
        raise MetricConventionError("eps zero_policy requires eps")
    return data_range_term - 10.0 * math.log10(value + float(convention.eps))


def psnr_value_for_mean(value: float, *, convention: PsnrConvention) -> float:
    """Return a PSNR value suitable for means under the convention's inf policy."""

    score = float(value)
    if math.isinf(score) and score > 0 and convention.mean_inf_cap_db is not None:
        return float(convention.mean_inf_cap_db)
    return score


__all__ = [
    "FINITE_PSNR_CONVENTION",
    "MetricConventionError",
    "PSNR_ZERO_POLICIES",
    "PSNR_ZERO_POLICY_EPS",
    "PSNR_ZERO_POLICY_INF",
    "PsnrConvention",
    "psnr_from_mse",
    "psnr_value_for_mean",
]
