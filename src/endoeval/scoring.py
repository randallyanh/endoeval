"""Canonical EndoEval scoring and four-artifact output generation."""

from __future__ import annotations

import csv
import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from benchmark_integrity.metric_conventions import FINITE_PSNR_CONVENTION
from benchmark_integrity.region_error import (
    PsnrDenominatorResult,
    RegionErrorStats,
    aggregate_region_errors,
    compare_psnr_denominators,
)
from endoeval.contracts import (
    EndoEvalError,
    OUTPUT_ARTIFACTS,
    canonical_sha256,
    file_sha256,
    resolve_inside,
    validate_prediction_directories,
    validate_submission,
    write_json,
)
from endoeval.image_stats import region_error_source_stats

_SCOREABLE_STATUSES = frozenset({"complete", "tied_perfect"})


@dataclass(frozen=True)
class FrameMeasurement:
    """One frame's score together with the identities that produced it."""

    scene: str
    frame_id: str
    native_frame_id: int
    stats: RegionErrorStats
    psnr_db: float
    prediction_sha256: str
    reference_sha256: str
    support_sha256: str

    @property
    def key(self) -> str:
        return f"{self.scene}/{self.frame_id}"

    @property
    def coverage(self) -> float:
        return self.stats.selected_pixels / self.stats.total_pixels


@dataclass(frozen=True)
class SceneMeasurement:
    """One scene's unweighted frame-mean score over its frozen frames."""

    scene: str
    psnr_db: float
    frames: tuple[FrameMeasurement, ...]
    prediction_files: tuple[str, ...]

    @property
    def coverage_mean(self) -> float:
        return math.fsum(frame.coverage for frame in self.frames) / len(self.frames)


def _load_rgb(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"), dtype=np.uint8)
    except OSError as exc:
        raise EndoEvalError(f"cannot decode RGB image {path}: {exc}") from exc


def _load_mask(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("L"), dtype=np.float64) / 255.0
    except OSError as exc:
        raise EndoEvalError(f"cannot decode mask {path}: {exc}") from exc


def _format_dataset_path(
    dataset_root: Path,
    scene: dict[str, Any],
    template_field: str,
    frame: dict[str, Any],
) -> Path:
    try:
        relative = scene[template_field].format(
            dataset_scene=scene["dataset_scene"],
            frame_id=frame["frame_id"],
            native_frame_id=frame["native_frame_id"],
        )
    except (KeyError, ValueError) as exc:
        raise EndoEvalError(f"invalid authority template {template_field}: {exc}") from exc
    return resolve_inside(dataset_root, relative, field=f"authority.{template_field}")


def _require_file(path: Path, expected_sha256: str, *, role: str) -> None:
    if not path.is_file():
        raise EndoEvalError(f"{role} is missing: {path}")
    actual = file_sha256(path)
    if actual != expected_sha256:
        raise EndoEvalError(
            f"{role} identity differs for {path}: expected {expected_sha256}, got {actual}"
        )


def _prepare_output_directory(path: Path, *, overwrite: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    existing = {item.name for item in path.iterdir()}
    if not existing:
        return
    unknown = existing - set(OUTPUT_ARTIFACTS)
    if unknown:
        raise EndoEvalError(f"output directory contains unrelated files: {sorted(unknown)}")
    if not overwrite:
        raise EndoEvalError("output directory already contains an evaluation; pass --overwrite")
    for name in existing:
        target = path / name
        if not target.is_file():
            raise EndoEvalError(f"refusing to overwrite non-file output entry: {target}")
        target.unlink()


def _keyed_digest(records: list[dict[str, Any]]) -> str:
    keys = [record["key"] for record in records]
    if len(keys) != len(set(keys)):
        raise EndoEvalError("identity records contain duplicate keys")
    return canonical_sha256(sorted(records, key=lambda item: item["key"]))


def _require_scoreable(score: PsnrDenominatorResult, *, subject: str) -> float:
    """Require a defined PSNR under the profile's finite convention."""

    if score.status not in _SCOREABLE_STATUSES or score.true_psnr is None:
        raise EndoEvalError(f"PSNR is undefined for {subject}: {score.status}")
    return score.true_psnr


def _score_frame(
    authority_scene: dict[str, Any],
    frame: dict[str, Any],
    *,
    prediction_dir: Path,
    dataset_root: Path,
    dimensions_wh: tuple[int, int],
    support_threshold: float,
) -> FrameMeasurement:
    """Measure one frame against its byte-verified reference and support."""

    scene_name = authority_scene["scene"]
    frame_id = frame["frame_id"]
    prediction_path = prediction_dir / f"{frame_id}.png"
    reference_path = _format_dataset_path(dataset_root, authority_scene, "reference_template", frame)
    tool_mask_path = _format_dataset_path(dataset_root, authority_scene, "tool_mask_template", frame)
    invalid_mask_path = _format_dataset_path(dataset_root, authority_scene, "invalid_mask_template", frame)
    _require_file(reference_path, frame["reference_sha256"], role="reference image")
    _require_file(tool_mask_path, frame["tool_mask_sha256"], role="tool mask")
    _require_file(invalid_mask_path, frame["invalid_mask_sha256"], role="invalid-region mask")

    prediction = _load_rgb(prediction_path)
    reference = _load_rgb(reference_path)
    tool_mask = _load_mask(tool_mask_path)
    invalid_mask = _load_mask(invalid_mask_path)
    if (prediction.shape[1], prediction.shape[0]) != dimensions_wh:
        raise EndoEvalError(
            f"prediction {scene_name}/{frame_id} has dimensions "
            f"{prediction.shape[1]}x{prediction.shape[0]}, expected "
            f"{dimensions_wh[0]}x{dimensions_wh[1]}"
        )
    if reference.shape != prediction.shape:
        raise EndoEvalError(f"reference and prediction shapes differ for {scene_name}/{frame_id}")
    support = (tool_mask <= support_threshold) & (invalid_mask <= support_threshold)
    try:
        stats = region_error_source_stats(prediction, reference, support)
        score = compare_psnr_denominators(stats, convention=FINITE_PSNR_CONVENTION)
    except ValueError as exc:
        raise EndoEvalError(f"cannot score {scene_name}/{frame_id}: {exc}") from exc
    return FrameMeasurement(
        scene=scene_name,
        frame_id=frame_id,
        native_frame_id=frame["native_frame_id"],
        stats=stats,
        psnr_db=_require_scoreable(score, subject=f"{scene_name}/{frame_id}"),
        prediction_sha256=file_sha256(prediction_path),
        reference_sha256=frame["reference_sha256"],
        support_sha256=hashlib.sha256(
            np.ascontiguousarray(support, dtype=np.uint8).tobytes()
        ).hexdigest(),
    )


def _score_scene(
    authority_scene: dict[str, Any],
    *,
    prediction_dir: Path,
    prediction_files: Sequence[str],
    dataset_root: Path,
    dimensions_wh: tuple[int, int],
    support_threshold: float,
) -> SceneMeasurement:
    """Measure one scene as the unweighted mean over its frozen frames."""

    scene_name = authority_scene["scene"]
    frames = tuple(
        _score_frame(
            authority_scene,
            frame,
            prediction_dir=prediction_dir,
            dataset_root=dataset_root,
            dimensions_wh=dimensions_wh,
            support_threshold=support_threshold,
        )
        for frame in authority_scene["frames"]
    )
    try:
        score = aggregate_region_errors(
            [frame.stats for frame in frames],
            reduction="frame_mean",
            convention=FINITE_PSNR_CONVENTION,
        )
    except ValueError as exc:
        raise EndoEvalError(f"cannot aggregate scene {scene_name}: {exc}") from exc
    return SceneMeasurement(
        scene=scene_name,
        psnr_db=_require_scoreable(score, subject=f"scene {scene_name}"),
        frames=frames,
        prediction_files=tuple(prediction_files),
    )


def _measurement_identity(
    profile: dict[str, Any],
    scenes: Sequence[SceneMeasurement],
    *,
    profile_sha256: str,
    authority_sha256: str,
) -> dict[str, str]:
    """Assemble the named digests that identify one measurement."""

    frames = [frame for scene in scenes for frame in scene.frames]
    frame_population_sha256 = _keyed_digest(
        [{"key": frame.key, "native_frame_id": frame.native_frame_id} for frame in frames]
    )
    reference_rgb_sha256 = _keyed_digest(
        [{"key": frame.key, "sha256": frame.reference_sha256} for frame in frames]
    )
    mask_support_sha256 = _keyed_digest(
        [{"key": frame.key, "sha256": frame.support_sha256} for frame in frames]
    )
    metric_definition_sha256 = canonical_sha256(profile["measurement"]["metric"])
    reduction_sha256 = canonical_sha256(
        {
            "frame_reduction": profile["measurement"]["frame_reduction"],
            "scene_reduction": profile["measurement"]["scene_reduction"],
        }
    )
    output_target_sha256 = canonical_sha256(
        {
            "task": profile["task"],
            "dataset": profile["dataset"]["name"],
            "release": profile["dataset"]["release"],
            "frame_population_sha256": frame_population_sha256,
        }
    )
    scoring_protocol_sha256 = canonical_sha256(
        {
            "profile_sha256": profile_sha256,
            "authority_sha256": authority_sha256,
            "reference_rgb_sha256": reference_rgb_sha256,
            "mask_support_sha256": mask_support_sha256,
            "metric_definition_sha256": metric_definition_sha256,
            "reduction_sha256": reduction_sha256,
            "image_decoder": "Pillow RGB/L uint8",
        }
    )
    return {
        "output_target_sha256": output_target_sha256,
        "frame_population_sha256": frame_population_sha256,
        "mask_support_sha256": mask_support_sha256,
        "reference_rgb_sha256": reference_rgb_sha256,
        "scoring_protocol_sha256": scoring_protocol_sha256,
        "metric_definition_sha256": metric_definition_sha256,
        "reduction_sha256": reduction_sha256,
    }


def _frame_document(frame: FrameMeasurement) -> dict[str, Any]:
    return {
        "frame_id": frame.frame_id,
        "native_frame_id": frame.native_frame_id,
        "psnr_db": frame.psnr_db,
        "selected_pixels": frame.stats.selected_pixels,
        "total_pixels": frame.stats.total_pixels,
        "coverage": frame.coverage,
        "prediction_sha256": frame.prediction_sha256,
    }


def _metrics_document(
    profile: dict[str, Any],
    method: dict[str, str],
    scenes: Sequence[SceneMeasurement],
    *,
    aggregate_psnr: float,
) -> dict[str, Any]:
    return {
        "artifact": "endoeval_metrics",
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "method": method,
        "metric": profile["measurement"]["metric"],
        "scene_reduction": profile["measurement"]["scene_reduction"],
        "scenes": {
            scene.scene: {
                "psnr_db": scene.psnr_db,
                "n_frames": len(scene.frames),
                "coverage_mean": scene.coverage_mean,
                "frames": [_frame_document(frame) for frame in scene.frames],
                "prediction_files": list(scene.prediction_files),
            }
            for scene in scenes
        },
        "aggregate": {
            "psnr_db": aggregate_psnr,
            "n_scenes": len(scenes),
            "n_frames": sum(len(scene.frames) for scene in scenes),
        },
    }


def _admission_document(profile_id: str, measurement_sha256: str) -> dict[str, Any]:
    return {
        "artifact": "endoeval_admission",
        "schema_version": 1,
        "profile_id": profile_id,
        "measurement_sha256": measurement_sha256,
        "claims": {
            "scalar": {
                "admitted": True,
                "basis": "complete evaluation under one identified measurement",
            },
            "artifact_ordering": {
                "admitted": True,
                "condition": "the compared receipt has the same measurement identity",
            },
            "capability": {
                "admitted": False,
                "disposition": "rerun_required",
                "reason": "an output-only evaluation does not establish training or capability equivalence",
            },
        },
    }


def _write_paper_table(
    path: Path,
    *,
    profile_id: str,
    method_name: str,
    scenes: Sequence[SceneMeasurement],
    aggregate_psnr: float,
) -> None:
    total_frames = sum(len(scene.frames) for scene in scenes)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["profile", "method", "scene", "psnr_db", "n_frames"])
        for scene in scenes:
            writer.writerow(
                [profile_id, method_name, scene.scene, f"{scene.psnr_db:.6f}", len(scene.frames)]
            )
        writer.writerow(
            [profile_id, method_name, "equal_scene_mean", f"{aggregate_psnr:.6f}", total_frames]
        )


def evaluate(
    submission_path: Path,
    *,
    dataset_root: Path,
    output: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Score one validated submission and write the four output artifacts."""

    validated = validate_submission(submission_path)
    prediction_files = validate_prediction_directories(validated)
    dataset_root = dataset_root.expanduser().resolve()
    if not dataset_root.is_dir():
        raise EndoEvalError(f"dataset root is not a directory: {dataset_root}")
    output_dir = (
        output.expanduser().resolve()
        if output is not None
        else (validated.path.parent / "endoeval-output").resolve()
    )
    _prepare_output_directory(output_dir, overwrite=overwrite)

    authority = validated.authority
    dimensions_wh = tuple(authority["dimensions_wh"])
    support_threshold = authority["support"]["threshold"]
    bindings = {binding.scene: binding for binding in validated.scenes}
    scenes = [
        _score_scene(
            authority_scene,
            prediction_dir=resolve_inside(
                validated.path.parent,
                bindings[authority_scene["scene"]].predictions,
                field=f"predictions[{authority_scene['scene']}]",
            ),
            prediction_files=prediction_files[authority_scene["scene"]],
            dataset_root=dataset_root,
            dimensions_wh=dimensions_wh,
            support_threshold=support_threshold,
        )
        for authority_scene in authority["scenes"]
    ]
    aggregate_psnr = math.fsum(scene.psnr_db for scene in scenes) / len(scenes)

    profile = validated.profile
    method = validated.document["method"]
    profile_sha256 = file_sha256(validated.profile_path)
    authority_sha256 = file_sha256(validated.authority_path)
    measurement = _measurement_identity(
        profile, scenes, profile_sha256=profile_sha256, authority_sha256=authority_sha256
    )
    measurement_sha256 = canonical_sha256(measurement)
    frames = [frame for scene in scenes for frame in scene.frames]
    prediction_set_sha256 = _keyed_digest(
        [{"key": frame.key, "sha256": frame.prediction_sha256} for frame in frames]
    )
    artifact_sha256 = canonical_sha256(
        {
            "method": method,
            "profile_id": profile["profile_id"],
            "prediction_set_sha256": prediction_set_sha256,
        }
    )

    metrics_path = output_dir / "metrics.json"
    admission_path = output_dir / "admission.json"
    table_path = output_dir / "paper_table.csv"
    write_json(metrics_path, _metrics_document(profile, method, scenes, aggregate_psnr=aggregate_psnr))
    write_json(admission_path, _admission_document(profile["profile_id"], measurement_sha256))
    _write_paper_table(
        table_path,
        profile_id=profile["profile_id"],
        method_name=method["name"],
        scenes=scenes,
        aggregate_psnr=aggregate_psnr,
    )

    receipt = {
        "artifact": "endoeval_evaluation_receipt",
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha256,
        "authority_sha256": authority_sha256,
        "submission_sha256": file_sha256(validated.path),
        "method": method,
        "artifact_sha256": artifact_sha256,
        "prediction_set_sha256": prediction_set_sha256,
        "measurement": measurement,
        "measurement_sha256": measurement_sha256,
        "aggregate_psnr_db": aggregate_psnr,
        "outputs": {
            "metrics.json": file_sha256(metrics_path),
            "paper_table.csv": file_sha256(table_path),
            "admission.json": file_sha256(admission_path),
        },
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_path = output_dir / "evaluation_receipt.json"
    write_json(receipt_path, receipt)
    return {
        "artifact": "endoeval_evaluation",
        "status": "complete",
        "profile": profile["profile_id"],
        "method": method["name"],
        "aggregate_psnr_db": aggregate_psnr,
        "measurement_sha256": measurement_sha256,
        "artifact_sha256": artifact_sha256,
        "receipt": str(receipt_path),
        "outputs": list(OUTPUT_ARTIFACTS),
    }


__all__ = ["evaluate"]
