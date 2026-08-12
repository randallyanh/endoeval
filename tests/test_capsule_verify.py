from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CapsuleVerifyTests(unittest.TestCase):
    def test_isolated_cli_verification(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", "reproduce.py", "verify"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["literature_headlines"]["measurement_judgements"], 162)
        self.assertEqual(
            report["literature_headlines"]["fully_specified_measurement_judgements"], 0
        )
        self.assertGreaterEqual(report["manifest"]["managed_files"], 20)

    def test_level_b_is_explicitly_blocked(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "reproduce.py",
                "raw",
                "--input-root",
                "/licensed-inputs",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 2)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("#103", report["reason"])
        self.assertIn("#115", report["reason"])


if __name__ == "__main__":
    unittest.main()
