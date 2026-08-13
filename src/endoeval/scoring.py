"""Canonical EndoEval scoring and four-artifact output generation."""

from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from benchmark_integrity.metric_conventions import FINITE_PSNR_CONVENTION
from benchmark_integrity.region_error import aggregate_region_errors, compare_psnr_denominators
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


def evaluate(
    submission_path: Path,
    *,
    dataset_root: Path,
    output: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    validated = validate_submission(submission_path)
    prediction_files = validate_prediction_directories(validated)
    submission_path = validated["path"]
    dataset_root = dataset_root.expanduser().resolve()
    if not dataset_root.is_dir():
        raise EndoEvalError(f"dataset root is not a directory: {dataset_root}")
    output_dir = (
        output.expanduser().resolve()
        if output is not None
        else (submission_path.parent / "endoeval-output").resolve()
    )
    _prepare_output_directory(output_dir, overwrite=overwrite)

    profile = validated["profile"]
    authority = validated["authority"]
    profile_sha256 = file_sha256(validated["profile_path"])
    authority_sha256 = file_sha256(validated["authority_path"])
    submission_sha256 = file_sha256(submission_path)
    dimensions_wh = tuple(authority["dimensions_wh"])
    support_threshold = authority["support"]["threshold"]
    scene_inputs = {scene["scene"]: scene for scene in validated["scenes"]}

    scene_results: dict[str, Any] = {}
    prediction_identity_records: list[dict[str, Any]] = []
    reference_identity_records: list[dict[str, Any]] = []
    support_identity_records: list[dict[str, Any]] = []
    frame_population_records: list[dict[str, Any]] = []

    for authority_scene in authority["scenes"]:
        scene_name = authority_scene["scene"]
        submission_scene = scene_inputs[scene_name]
        prediction_dir = resolve_inside(
            submission_path.parent,
            submission_scene["predictions"],
            field=f"predictions[{scene_name}]",
        )
        statistics = []
        per_frame: list[dict[str, Any]] = []
        for frame in authority_scene["frames"]:
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
                raise EndoEvalError(
                    f"reference and prediction shapes differ for {scene_name}/{frame_id}"
                )
            selected = (tool_mask <= support_threshold) & (invalid_mask <= support_threshold)
            stats = region_error_source_stats(prediction, reference, selected)
            frame_score = compare_psnr_denominators(
                stats, convention=FINITE_PSNR_CONVENTION
            )
            if frame_score.status not in _SCOREABLE_STATUSES or frame_score.true_psnr is None:
                raise EndoEvalError(
                    f"PSNR is undefined for {scene_name}/{frame_id}: {frame_score.status}"
                )
            statistics.append(stats)
            prediction_sha256 = file_sha256(prediction_path)
            selection_sha256 = hashlib.sha256(
                np.ascontiguousarray(selected, dtype=np.uint8).tobytes()
            ).hexdigest()
            key = f"{scene_name}/{frame_id}"
            prediction_identity_records.append({"key": key, "sha256": prediction_sha256})
            reference_identity_records.append({"key": key, "sha256": frame["reference_sha256"]})
            support_identity_records.append({"key": key, "sha256": selection_sha256})
            frame_population_records.append({"key": key, "native_frame_id": frame["native_frame_id"]})
            per_frame.append(
                {
                    "frame_id": frame_id,
                    "native_frame_id": frame["native_frame_id"],
                    "psnr_db": frame_score.true_psnr,
                    "selected_pixels": stats.selected_pixels,
                    "total_pixels": stats.total_pixels,
                    "coverage": stats.selected_pixels / stats.total_pixels,
                    "prediction_sha256": prediction_sha256,
                }
            )
        scene_score = aggregate_region_errors(
            statistics,
            reduction="frame_mean",
            convention=FINITE_PSNR_CONVENTION,
        )
        if scene_score.status not in _SCOREABLE_STATUSES or scene_score.true_psnr is None:
            raise EndoEvalError(f"scene PSNR is undefined for {scene_name}: {scene_score.status}")
        scene_results[scene_name] = {
            "psnr_db": scene_score.true_psnr,
            "n_frames": len(statistics),
            "coverage_mean": math.fsum(
                row.selected_pixels / row.total_pixels for row in statistics
            )
            / len(statistics),
            "frames": per_frame,
            "prediction_files": prediction_files[scene_name],
        }

    aggregate_psnr = math.fsum(
        result["psnr_db"] for result in scene_results.values()
    ) / len(scene_results)
    frame_population_sha256 = _keyed_digest(frame_population_records)
    reference_rgb_sha256 = _keyed_digest(reference_identity_records)
    mask_support_sha256 = _keyed_digest(support_identity_records)
    prediction_set_sha256 = _keyed_digest(prediction_identity_records)
    output_target_sha256 = canonical_sha256(
        {
            "task": profile["task"],
            "dataset": profile["dataset"]["name"],
            "release": profile["dataset"]["release"],
            "frame_population_sha256": frame_population_sha256,
        }
    )
    metric_definition_sha256 = canonical_sha256(profile["measurement"]["metric"])
    reduction_sha256 = canonical_sha256(
        {
            "frame_reduction": profile["measurement"]["frame_reduction"],
            "scene_reduction": profile["measurement"]["scene_reduction"],
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
    measurement_components = {
        "output_target_sha256": output_target_sha256,
        "frame_population_sha256": frame_population_sha256,
        "mask_support_sha256": mask_support_sha256,
        "reference_rgb_sha256": reference_rgb_sha256,
        "scoring_protocol_sha256": scoring_protocol_sha256,
        "metric_definition_sha256": metric_definition_sha256,
        "reduction_sha256": reduction_sha256,
    }
    measurement_sha256 = canonical_sha256(measurement_components)
    method = validated["document"]["method"]
    artifact_sha256 = canonical_sha256(
        {
            "method": method,
            "profile_id": profile["profile_id"],
            "prediction_set_sha256": prediction_set_sha256,
        }
    )

    metrics = {
        "artifact": "endoeval_metrics",
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "method": method,
        "metric": profile["measurement"]["metric"],
        "scene_reduction": profile["measurement"]["scene_reduction"],
        "scenes": scene_results,
        "aggregate": {
            "psnr_db": aggregate_psnr,
            "n_scenes": len(scene_results),
            "n_frames": sum(result["n_frames"] for result in scene_results.values()),
        },
    }
    admission = {
        "artifact": "endoeval_admission",
        "schema_version": 1,
        "profile_id": profile["profile_id"],
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
    metrics_path = output_dir / "metrics.json"
    admission_path = output_dir / "admission.json"
    table_path = output_dir / "paper_table.csv"
    write_json(metrics_path, metrics)
    write_json(admission_path, admission)
    with table_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["profile", "method", "scene", "psnr_db", "n_frames"])
        for scene_name, result in scene_results.items():
            writer.writerow(
                [profile["profile_id"], method["name"], scene_name, f"{result['psnr_db']:.6f}", result["n_frames"]]
            )
        writer.writerow(
            [profile["profile_id"], method["name"], "equal_scene_mean", f"{aggregate_psnr:.6f}", metrics["aggregate"]["n_frames"]]
        )

    receipt = {
        "artifact": "endoeval_evaluation_receipt",
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile_sha256,
        "authority_sha256": authority_sha256,
        "submission_sha256": submission_sha256,
        "method": method,
        "artifact_sha256": artifact_sha256,
        "prediction_set_sha256": prediction_set_sha256,
        "measurement": measurement_components,
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
