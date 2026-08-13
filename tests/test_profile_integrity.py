"""The bundled profile and the unsafe-input boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endoeval.canonical import EndoEvalError, safe_relative_path
from endoeval.contracts import load_authority, load_profile


class ProfileIntegrityTests(unittest.TestCase):
    def test_bundled_profile_and_input_boundary(self) -> None:
        profile, _ = load_profile("endonerf-rgb-v1")
        authority, _ = load_authority(profile)
        self.assertEqual(profile["status"], "ready")
        self.assertEqual([len(scene.frames) for scene in authority.scenes], [20, 8])
        self.assertEqual(sum(len(scene.frames) for scene in authority.scenes), 28)
        self.assertEqual(
            authority.support_definition,
            "not(tool_mask > 0.5) AND not(invalid_mask > 0.5)",
        )
        for scene in authority.scenes:
            frame_ids = {frame.frame_id for frame in scene.frames}
            self.assertEqual(len(frame_ids), len(scene.frames))
            for frame in scene.frames:
                for digest in (
                    frame.reference_sha256,
                    frame.tool_mask_sha256,
                    frame.invalid_mask_sha256,
                ):
                    self.assertEqual(len(digest), 64)

        for unsafe in ("../outside", "a\\b", "/absolute", "C:\\outside", "a//b"):
            with self.assertRaises(EndoEvalError):
                safe_relative_path(unsafe, field="test")


if __name__ == "__main__":
    unittest.main()
