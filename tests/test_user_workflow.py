"""The complete author workflow: init, validate, evaluate, verify, compare."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-B", str(REPO_ROOT / "endoeval.py")]
SCENES = (("a", "scene_a"), ("b", "scene_b"))
OUTPUT_ARTIFACTS = {"metrics.json", "evaluation_receipt.json", "paper_table.csv", "admission.json"}

# The numerical lock. The kernel is repo-owned rather than provenance-frozen,
# so these pinned scores are what holds the measurement still: a perfect
# prediction scores the eps-capped 100 dB, and a uniform +5/255 shift scores
# -10 * log10((5/255)^2 + 1e-10).
PERFECT_PSNR_DB = 100.0
SHIFTED_PSNR_DB = 34.151402392358925


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UserWorkflowTests(unittest.TestCase):
    def test_init_validate_evaluate_verify_compare(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset"
            profile_root = root / "profiles"
            profile_root.mkdir()
            self._write_profile(profile_root, self._write_dataset(dataset))
            environment = {
                **os.environ,
                "ENDOEVAL_PROFILE_ROOT": str(profile_root),
                "PYTHONPATH": str(REPO_ROOT / "src"),
            }

            receipts = [
                self._evaluate_method(root, dataset, environment, method=method, offset=offset)
                for method, offset in (("perfect", 0), ("shifted", 5))
            ]

            comparison = json.loads(
                self._run(
                    ["compare", str(receipts[0]), str(receipts[1]), "--claim", "ordering"],
                    environment,
                ).stdout
            )
            self.assertEqual(comparison["disposition"], "identical")
            self.assertEqual(comparison["artifact_ordering"], "perfect > shifted")
            self.assertTrue(
                math.isclose(comparison["left_psnr_db"], PERFECT_PSNR_DB, rel_tol=0, abs_tol=1e-9)
            )
            self.assertTrue(
                math.isclose(comparison["right_psnr_db"], SHIFTED_PSNR_DB, rel_tol=0, abs_tol=1e-9)
            )

            metrics = receipts[0].parent / "metrics.json"
            metrics.write_text(metrics.read_text() + "\n")
            self._run(["verify", str(receipts[0])], environment, expect_success=False)

    def _run(
        self,
        arguments: list[str],
        environment: dict[str, str],
        *,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            CLI + arguments, cwd=REPO_ROOT, env=environment, text=True, capture_output=True
        )
        if expect_success and completed.returncode != 0:
            raise AssertionError(
                f"{arguments}\nstdout={completed.stdout}\nstderr={completed.stderr}"
            )
        if not expect_success and completed.returncode == 0:
            raise AssertionError(f"expected failure: {arguments}")
        return completed

    def _write_dataset(self, dataset: Path) -> list[dict[str, object]]:
        scenes: list[dict[str, object]] = []
        for scene, dataset_scene in SCENES:
            for folder in ("images", "gt_masks", "masks"):
                (dataset / dataset_scene / folder).mkdir(parents=True, exist_ok=True)
            reference = np.zeros((512, 640, 3), dtype=np.uint8)
            reference[..., 0] = 40 if scene == "a" else 80
            tool_mask = np.zeros((512, 640), dtype=np.uint8)
            tool_mask[:10, :] = 255
            invalid_mask = np.zeros((512, 640), dtype=np.uint8)
            invalid_mask[-10:, :] = 255
            Image.fromarray(reference).save(dataset / dataset_scene / "images" / "000001.png")
            Image.fromarray(tool_mask).save(dataset / dataset_scene / "gt_masks" / "000001.png")
            Image.fromarray(invalid_mask).save(dataset / dataset_scene / "masks" / "000001.png")
            scenes.append(
                {
                    "scene": scene,
                    "dataset_scene": dataset_scene,
                    "reference_template": f"{dataset_scene}/images/{{frame_id}}.png",
                    "tool_mask_template": f"{dataset_scene}/gt_masks/{{frame_id}}.png",
                    "invalid_mask_template": f"{dataset_scene}/masks/{{frame_id}}.png",
                    "frames": [
                        {
                            "frame_id": "000001",
                            "native_frame_id": 1,
                            "reference_sha256": _file_sha256(
                                dataset / dataset_scene / "images" / "000001.png"
                            ),
                            "tool_mask_sha256": _file_sha256(
                                dataset / dataset_scene / "gt_masks" / "000001.png"
                            ),
                            "invalid_mask_sha256": _file_sha256(
                                dataset / dataset_scene / "masks" / "000001.png"
                            ),
                        }
                    ],
                }
            )
        return scenes

    def _write_profile(self, profile_root: Path, scenes: list[dict[str, object]]) -> None:
        profile = {
            "artifact": "endoeval_profile",
            "schema_version": 1,
            "profile_id": "test-rgb-v1",
            "status": "ready",
            "domain": "dynamic_endoscopic_reconstruction",
            "task": "rgb_reconstruction",
            "dataset": {
                "name": "Synthetic",
                "release": "test-v1",
                "authority": "test-rgb-v1-authority.json",
            },
            "submission": {
                "input": "rendered_rgb_images",
                "path_template": "predictions/{scene}/{frame_id}.png",
                "image_encoding": "png_rgb",
            },
            "measurement": {
                "output_target": "RGB reconstruction",
                "support": "dataset-valid non-tool tissue",
                "metric": {
                    "family": "PSNR",
                    "convention": "psnr_mse_eps_1e-10",
                    "denominator": "true_exclusion",
                    "data_range": 1.0,
                },
                "frame_reduction": "unweighted_frame_mean",
                "scene_reduction": "equal_scene_weight",
            },
            "outputs": [
                "metrics.json",
                "evaluation_receipt.json",
                "paper_table.csv",
                "admission.json",
            ],
        }
        authority = {
            "artifact": "endoeval_dataset_authority",
            "schema_version": 1,
            "profile_id": "test-rgb-v1",
            "dataset_release": "test-v1",
            "dimensions_wh": [640, 512],
            "support": {
                "definition": "not(tool_mask > 0.5) AND not(invalid_mask > 0.5)",
                "threshold": 0.5,
            },
            "scenes": scenes,
            "source": {"test": True},
        }
        (profile_root / "test-rgb-v1.json").write_text(json.dumps(profile))
        (profile_root / "test-rgb-v1-authority.json").write_text(json.dumps(authority))

    def _evaluate_method(
        self,
        root: Path,
        dataset: Path,
        environment: dict[str, str],
        *,
        method: str,
        offset: int,
    ) -> Path:
        submission_dir = root / method
        self._run(
            ["init", str(submission_dir), "--profile", "test-rgb-v1", "--method", method],
            environment,
        )
        for scene, dataset_scene in SCENES:
            reference = np.asarray(
                Image.open(dataset / dataset_scene / "images" / "000001.png").convert("RGB"),
                dtype=np.uint8,
            )
            rendered = np.clip(reference.astype(np.int16) + offset, 0, 255).astype(np.uint8)
            Image.fromarray(rendered).save(submission_dir / "predictions" / scene / "000001.png")
        submission = submission_dir / "submission.json"
        self._run(["validate", str(submission), "--check-paths"], environment)
        self._run(["evaluate", str(submission), "--dataset-root", str(dataset)], environment)
        output_dir = submission_dir / "endoeval-output"
        self.assertEqual({path.name for path in output_dir.iterdir()}, OUTPUT_ARTIFACTS)
        receipt = output_dir / "evaluation_receipt.json"
        self._run(["verify", str(receipt)], environment)
        return receipt


if __name__ == "__main__":
    unittest.main()
