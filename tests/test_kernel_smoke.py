from __future__ import annotations

import unittest

import reproduce


class KernelSmokeTests(unittest.TestCase):
    def test_kernel_claim_boundaries(self) -> None:
        report = reproduce.verify_kernel()
        self.assertEqual(report["dispositions"]["ordering"], "identical")
        self.assertEqual(report["dispositions"]["capability"], "rerun_required")
        self.assertEqual(report["dispositions"]["target_mismatch"], "target_mismatch")
        self.assertEqual(report["dispositions"]["unknown"], "unknown")
        self.assertEqual(report["dispositions"]["rescore"], "rescore_required")
        self.assertEqual(report["transport_dispositions"]["scalar"], "exact_transport")
        self.assertEqual(report["transport_dispositions"]["ordering"], "invariant")
        self.assertEqual(report["transport_dispositions"]["capability"], "rerun_required")


if __name__ == "__main__":
    unittest.main()
