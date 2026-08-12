from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = [sys.executable, "-I", "-S", "-B", "endoeval.py", "validate"]


class ProfileIntegrityTests(unittest.TestCase):
    def test_invalid_submission_contracts_fail_closed(self) -> None:
        cases = [
            {
                "artifact": "endoeval_submission",
                "schema_version": 1,
                "profile": "endonerf-rgb-v1",
                "method": {"name": "x"},
                "scenes": [
                    {"scene": "cutting", "predictions": "../outside"},
                    {"scene": "pulling", "predictions": "predictions/pulling"},
                ],
            },
            {
                "artifact": "endoeval_submission",
                "schema_version": 1,
                "profile": "unknown-profile",
                "method": {"name": "x"},
                "scenes": [],
            },
        ]
        for index, document in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "submission.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                completed = subprocess.run(
                    [*COMMAND, str(path)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 1)
                error = json.loads(completed.stderr)
                self.assertEqual(error["status"], "error")


if __name__ == "__main__":
    unittest.main()
