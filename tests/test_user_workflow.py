from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = [sys.executable, "-I", "-S", "-B", "endoeval.py"]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMMAND, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class UserWorkflowTests(unittest.TestCase):
    def test_profile_validate_and_blocked_evaluate(self) -> None:
        listed = run("profiles")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        profiles = json.loads(listed.stdout)["profiles"]
        self.assertEqual([item["profile_id"] for item in profiles], ["endonerf-rgb-v1"])

        shown = run("profile", "endonerf-rgb-v1")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["status"], "draft_not_scoreable")

        submission = "examples/minimal-submission/submission.json"
        validated = run("validate", submission)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        validation = json.loads(validated.stdout)
        self.assertEqual(validation["status"], "valid")
        self.assertFalse(validation["method_specific_adapter_required"])

        evaluated = run("evaluate", submission)
        self.assertEqual(evaluated.returncode, 2)
        result = json.loads(evaluated.stdout)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["planned_outputs"],
            [
                "metrics.json",
                "evaluation_receipt.json",
                "paper_table.csv",
                "admission.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
