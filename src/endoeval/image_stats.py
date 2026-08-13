"""RGB and mask decoding boundary for EndoEval."""

from __future__ import annotations

import numpy as np

from benchmark_integrity.region_error import RegionErrorStats


def region_error_source_stats(
    rendered: np.ndarray,
    reference: np.ndarray,
    selected_region: np.ndarray,
) -> RegionErrorStats:
    """Convert one RGB pair and binary support into sufficient statistics."""

    rendered_f = _to_rgb01(rendered)
    reference_f = _to_rgb01(reference)
    _check_image_pair(rendered_f, reference_f)
    selected = _checked_mask(selected_region, reference_f.shape[:2])
    difference = rendered_f.astype(np.float64) - reference_f.astype(np.float64)
    squared_error = difference * difference
    return RegionErrorStats(
        total_pixels=int(selected.size),
        selected_pixels=int(np.count_nonzero(selected)),
        selected_sse=float(np.sum(squared_error[selected], dtype=np.float64)),
        complement_sse=float(np.sum(squared_error[~selected], dtype=np.float64)),
    )


def _checked_mask(mask: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    mask_b = np.asarray(mask).astype(bool)
    if mask_b.shape != target_hw:
        raise ValueError(f"mask shape {mask_b.shape} != target image shape {target_hw}")
    return mask_b


def _check_image_pair(rendered: np.ndarray, reference: np.ndarray) -> None:
    if rendered.shape != reference.shape:
        raise ValueError(f"rendered shape {rendered.shape} != reference shape {reference.shape}")
    if rendered.ndim != 3 or rendered.shape[2] != 3:
        raise ValueError(f"metric inputs must be HxWx3 RGB arrays, got {rendered.shape}")


def _to_rgb01(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    out = array.astype(np.float64) / 255.0 if array.dtype == np.uint8 else array.astype(np.float64)
    if not np.all(np.isfinite(out)):
        raise ValueError("metric input contains non-finite values")
    if out.size and (float(out.min()) < 0.0 or float(out.max()) > 1.0):
        raise ValueError("metric input must lie in the closed range [0, 1]")
    return out


__all__ = ["region_error_source_stats"]
