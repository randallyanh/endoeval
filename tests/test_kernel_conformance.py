"""The load-bearing numerical and claim-admission kernel boundary."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchmark_integrity.comparability import ComparisonFacts, assess_comparability
from benchmark_integrity.metric_conventions import FINITE_PSNR_CONVENTION, psnr_from_mse
from benchmark_integrity.region_error import RegionErrorStats, compare_psnr_denominators


class KernelConformanceTests(unittest.TestCase):
    def test_load_bearing_boundary(self) -> None:
        self.assertTrue(
            math.isclose(
                psnr_from_mse(0.01, convention=FINITE_PSNR_CONVENTION),
                19.99999995657055,
                rel_tol=0,
                abs_tol=1e-12,
            )
        )

        decomposition = compare_psnr_denominators(
            RegionErrorStats(
                total_pixels=4, selected_pixels=2, selected_sse=0.06, complement_sse=0.12
            ),
            convention=FINITE_PSNR_CONVENTION,
        )
        self.assertEqual(decomposition.status, "complete")

        agreeing = {
            "source_identity": "0" * 64,
            "target_identity": "1" * 64,
            "output_target_equal": True,
            "source_measurement_determined": True,
            "target_measurement_determined": True,
            "frame_population_equal": True,
            "mask_support_equal": True,
            "scoring_protocol_equal": True,
            "metric_definition_equal": True,
            "reduction_equal": True,
        }
        identical = assess_comparability(claim_mode="ordering", facts=ComparisonFacts(**agreeing))
        self.assertEqual(identical.disposition, "identical")

        differing_support = {**agreeing, "mask_support_equal": False}
        rescore = assess_comparability(
            claim_mode="ordering", facts=ComparisonFacts(**differing_support)
        )
        self.assertEqual(rescore.disposition, "rescore_required")
        rerun = assess_comparability(
            claim_mode="capability", facts=ComparisonFacts(**differing_support)
        )
        self.assertEqual(rerun.disposition, "rerun_required")


if __name__ == "__main__":
    unittest.main()
