"""Versioned profile, dataset authority, and submission contracts."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from endoeval.canonical import (
    EndoEvalError,
    load_json,
    resolve_inside,
    safe_relative_path,
)

_PROFILE_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
_SHA256 = re.compile(r"[0-9a-f]{64}")

OUTPUT_ARTIFACTS = (
    "metrics.json",
    "evaluation_receipt.json",
    "paper_table.csv",
    "admission.json",
)


def profile_root() -> Path:
    """Locate the installed profiles, honouring ENDOEVAL_PROFILE_ROOT."""

    override = os.environ.get("ENDOEVAL_PROFILE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent / "profiles"


def _require_exact_keys(document: object, expected: set[str], *, name: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise EndoEvalError(f"{name} must be a JSON object")
    keys = set(document)
    if keys != expected:
        raise EndoEvalError(
            f"{name} keys differ: extra={sorted(keys - expected)}, "
            f"missing={sorted(expected - keys)}"
        )
    return document


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EndoEvalError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _profile_path(profile_id: str) -> Path:
    if not _PROFILE_ID.fullmatch(profile_id):
        raise EndoEvalError(f"invalid profile id: {profile_id!r}")
    path = profile_root() / f"{profile_id}.json"
    if not path.is_file():
        raise EndoEvalError(f"unknown profile: {profile_id}")
    return path


def load_profile(profile_id: str) -> tuple[dict[str, Any], Path]:
    """Load one scoreable profile together with the file that defines it."""

    path = _profile_path(profile_id)
    profile = _require_exact_keys(
        load_json(path),
        {
            "artifact",
            "schema_version",
            "profile_id",
            "status",
            "domain",
            "task",
            "dataset",
            "submission",
            "measurement",
            "outputs",
        },
        name=f"profile {profile_id}",
    )
    if profile["artifact"] != "endoeval_profile" or profile["schema_version"] != 1:
        raise EndoEvalError(f"profile {profile_id} has an unsupported identity")
    if profile["profile_id"] != profile_id:
        raise EndoEvalError(f"profile file/name mismatch for {profile_id}")
    if profile["status"] != "ready":
        raise EndoEvalError(f"profile {profile_id} is not scoreable: {profile['status']!r}")
    dataset = _require_exact_keys(
        profile["dataset"], {"name", "release", "authority"}, name="profile.dataset"
    )
    safe_relative_path(dataset["authority"], field="profile.dataset.authority")
    submission = _require_exact_keys(
        profile["submission"], {"input", "path_template", "image_encoding"},
        name="profile.submission",
    )
    if submission != {
        "input": "rendered_rgb_images",
        "path_template": "predictions/{scene}/{frame_id}.png",
        "image_encoding": "png_rgb",
    }:
        raise EndoEvalError("profile submission contract moved")
    measurement = _require_exact_keys(
        profile["measurement"],
        {"output_target", "support", "metric", "frame_reduction", "scene_reduction"},
        name="profile.measurement",
    )
    metric = _require_exact_keys(
        measurement["metric"],
        {"family", "convention", "denominator", "data_range"},
        name="profile.measurement.metric",
    )
    if metric != {
        "family": "PSNR",
        "convention": "psnr_mse_eps_1e-10",
        "denominator": "true_exclusion",
        "data_range": 1.0,
    }:
        raise EndoEvalError("unsupported metric contract")
    if measurement["frame_reduction"] != "unweighted_frame_mean":
        raise EndoEvalError("unsupported frame reduction")
    if measurement["scene_reduction"] != "equal_scene_weight":
        raise EndoEvalError("unsupported scene reduction")
    if tuple(profile["outputs"]) != OUTPUT_ARTIFACTS:
        raise EndoEvalError("profile output contract moved")
    return profile, path


@dataclass(frozen=True)
class AuthorityFrame:
    """One frozen evaluation frame and the byte identities that define it."""

    frame_id: str
    native_frame_id: int
    reference_sha256: str
    tool_mask_sha256: str
    invalid_mask_sha256: str


@dataclass(frozen=True)
class AuthorityScene:
    """One scene's dataset binding and its frozen frame population."""

    scene: str
    dataset_scene: str
    reference_template: str
    tool_mask_template: str
    invalid_mask_template: str
    frames: tuple[AuthorityFrame, ...]


@dataclass(frozen=True)
class DatasetAuthority:
    """A profile's frozen dataset facts: dimensions, support, and frames."""

    dataset_release: str
    dimensions_wh: tuple[int, int]
    support_definition: str
    support_threshold: float
    scenes: tuple[AuthorityScene, ...]


def load_authority(profile: dict[str, Any]) -> tuple[DatasetAuthority, Path]:
    """Load a profile's frozen dataset authority together with its file."""

    profile_id = profile["profile_id"]
    authority_name = safe_relative_path(
        profile["dataset"]["authority"], field="profile.dataset.authority"
    )
    path = resolve_inside(profile_root(), authority_name, field="profile.dataset.authority")
    authority = _require_exact_keys(
        load_json(path),
        {
            "artifact",
            "schema_version",
            "profile_id",
            "dataset_release",
            "dimensions_wh",
            "support",
            "scenes",
            "source",
        },
        name=f"authority for {profile_id}",
    )
    if authority["artifact"] != "endoeval_dataset_authority" or authority["schema_version"] != 1:
        raise EndoEvalError("authority has an unsupported identity")
    if authority["profile_id"] != profile_id:
        raise EndoEvalError("authority/profile mismatch")
    if authority["dataset_release"] != profile["dataset"]["release"]:
        raise EndoEvalError("authority dataset release differs from profile")
    dimensions = authority["dimensions_wh"]
    if dimensions != [640, 512]:
        raise EndoEvalError(f"unsupported image dimensions: {dimensions!r}")
    support = _require_exact_keys(
        authority["support"], {"definition", "threshold"}, name="authority.support"
    )
    if support != {
        "definition": "not(tool_mask > 0.5) AND not(invalid_mask > 0.5)",
        "threshold": 0.5,
    }:
        raise EndoEvalError("authority support definition moved")
    raw_scenes = authority["scenes"]
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise EndoEvalError("authority.scenes must be a non-empty array")
    seen_scenes: set[str] = set()
    scenes: list[AuthorityScene] = []
    for scene_index, raw_scene in enumerate(raw_scenes):
        scene = _require_exact_keys(
            raw_scene,
            {
                "scene",
                "dataset_scene",
                "reference_template",
                "tool_mask_template",
                "invalid_mask_template",
                "frames",
            },
            name=f"authority.scenes[{scene_index}]",
        )
        scene_name = scene["scene"]
        if not isinstance(scene_name, str) or not scene_name or scene_name in seen_scenes:
            raise EndoEvalError("authority scene names must be unique non-empty strings")
        seen_scenes.add(scene_name)
        for field in ("dataset_scene", "reference_template", "tool_mask_template", "invalid_mask_template"):
            safe_relative_path(scene[field], field=f"authority.{scene_name}.{field}")
        raw_frames = scene["frames"]
        if not isinstance(raw_frames, list) or not raw_frames:
            raise EndoEvalError(f"authority scene {scene_name} has no frames")
        seen_frames: set[str] = set()
        frames: list[AuthorityFrame] = []
        for frame_index, raw_frame in enumerate(raw_frames):
            frame = _require_exact_keys(
                raw_frame,
                {
                    "frame_id",
                    "native_frame_id",
                    "reference_sha256",
                    "tool_mask_sha256",
                    "invalid_mask_sha256",
                },
                name=f"authority.{scene_name}.frames[{frame_index}]",
            )
            frame_id = frame["frame_id"]
            if not isinstance(frame_id, str) or not re.fullmatch(r"[0-9]{6}", frame_id):
                raise EndoEvalError("authority frame_id must be six decimal digits")
            if frame_id in seen_frames:
                raise EndoEvalError(f"duplicate frame id {frame_id} in {scene_name}")
            seen_frames.add(frame_id)
            if frame["native_frame_id"] != int(frame_id):
                raise EndoEvalError(f"native_frame_id differs from frame_id in {scene_name}/{frame_id}")
            for digest_field in ("reference_sha256", "tool_mask_sha256", "invalid_mask_sha256"):
                _require_sha256(frame[digest_field], field=f"{scene_name}/{frame_id}/{digest_field}")
            frames.append(
                AuthorityFrame(
                    frame_id=frame_id,
                    native_frame_id=frame["native_frame_id"],
                    reference_sha256=frame["reference_sha256"],
                    tool_mask_sha256=frame["tool_mask_sha256"],
                    invalid_mask_sha256=frame["invalid_mask_sha256"],
                )
            )
        scenes.append(
            AuthorityScene(
                scene=scene_name,
                dataset_scene=scene["dataset_scene"],
                reference_template=scene["reference_template"],
                tool_mask_template=scene["tool_mask_template"],
                invalid_mask_template=scene["invalid_mask_template"],
                frames=tuple(frames),
            )
        )
    return (
        DatasetAuthority(
            dataset_release=authority["dataset_release"],
            dimensions_wh=(dimensions[0], dimensions[1]),
            support_definition=support["definition"],
            support_threshold=support["threshold"],
            scenes=tuple(scenes),
        ),
        path,
    )


def list_profiles() -> list[dict[str, Any]]:
    """Summarise every profile installed under the profile root."""

    root = profile_root()
    profiles: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if path.name.endswith("-authority.json"):
            continue
        profile, _ = load_profile(path.stem)
        authority, _ = load_authority(profile)
        profiles.append(
            {
                "profile_id": profile["profile_id"],
                "status": profile["status"],
                "dataset": profile["dataset"]["name"],
                "task": profile["task"],
                "scenes": len(authority.scenes),
                "frames": sum(len(scene.frames) for scene in authority.scenes),
            }
        )
    if not profiles:
        raise EndoEvalError(f"no profiles are installed under {root}")
    return profiles


@dataclass(frozen=True)
class SceneBinding:
    """One submission scene bound to its declared prediction directory."""

    scene: str
    predictions: str


@dataclass(frozen=True)
class ValidatedSubmission:
    """One submission validated against its profile and dataset authority."""

    path: Path
    document: dict[str, Any]
    profile: dict[str, Any]
    profile_path: Path
    authority: DatasetAuthority
    authority_path: Path
    scenes: tuple[SceneBinding, ...]


def validate_submission(submission_path: Path) -> ValidatedSubmission:
    """Validate one submission document against the profile it names."""

    submission_path = submission_path.expanduser().resolve()
    submission = _require_exact_keys(
        load_json(submission_path),
        {"artifact", "schema_version", "profile", "method", "scenes"},
        name="submission",
    )
    if submission["artifact"] != "endoeval_submission" or submission["schema_version"] != 1:
        raise EndoEvalError("submission has an unsupported identity")
    profile_id = submission["profile"]
    if not isinstance(profile_id, str):
        raise EndoEvalError("submission.profile must be a string")
    profile, profile_path = load_profile(profile_id)
    authority, authority_path = load_authority(profile)
    method = submission["method"]
    if not isinstance(method, dict) or not set(method).issubset({"name", "version", "source_commit"}):
        raise EndoEvalError("submission.method contains unsupported fields")
    if not isinstance(method.get("name"), str) or not method["name"].strip():
        raise EndoEvalError("submission.method.name must be non-empty")
    for optional in ("version", "source_commit"):
        if optional in method and (
            not isinstance(method[optional], str) or not method[optional].strip()
        ):
            raise EndoEvalError(f"submission.method.{optional} must be non-empty")
    if "source_commit" in method and not re.fullmatch(r"[0-9a-f]{7,64}", method["source_commit"]):
        raise EndoEvalError("submission.method.source_commit must be a lowercase Git object id")
    raw_scenes = submission["scenes"]
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise EndoEvalError("submission.scenes must be a non-empty array")
    expected = {scene.scene for scene in authority.scenes}
    seen: set[str] = set()
    bindings: list[SceneBinding] = []
    for index, raw_scene in enumerate(raw_scenes):
        scene = _require_exact_keys(raw_scene, {"scene", "predictions"}, name=f"submission.scenes[{index}]")
        name = scene["scene"]
        if not isinstance(name, str) or not name or name in seen:
            raise EndoEvalError("submission scene names must be unique non-empty strings")
        seen.add(name)
        predictions = safe_relative_path(
            scene["predictions"], field=f"submission.scenes[{index}].predictions"
        )
        bindings.append(SceneBinding(scene=name, predictions=predictions))
    if seen != expected:
        raise EndoEvalError(
            f"submission scenes differ from profile: extra={sorted(seen - expected)}, "
            f"missing={sorted(expected - seen)}"
        )
    return ValidatedSubmission(
        path=submission_path,
        document=submission,
        profile=profile,
        profile_path=profile_path,
        authority=authority,
        authority_path=authority_path,
        scenes=tuple(bindings),
    )


def expected_prediction_files(authority_scene: AuthorityScene) -> set[str]:
    """Name the prediction files a scene's frozen frames require."""

    return {f"{frame.frame_id}.png" for frame in authority_scene.frames}


def validate_prediction_directories(validated: ValidatedSubmission) -> dict[str, list[str]]:
    """Require every bound prediction directory to hold exactly the expected frames."""

    base = validated.path.parent
    authority_by_scene = {scene.scene: scene for scene in validated.authority.scenes}
    result: dict[str, list[str]] = {}
    for binding in validated.scenes:
        directory = resolve_inside(base, binding.predictions, field=f"predictions[{binding.scene}]")
        if not directory.is_dir():
            raise EndoEvalError(f"prediction directory is missing: {directory}")
        expected = expected_prediction_files(authority_by_scene[binding.scene])
        actual = {path.name for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".png"}
        if actual != expected:
            raise EndoEvalError(
                f"prediction files differ for {binding.scene}: "
                f"extra={sorted(actual - expected)}, missing={sorted(expected - actual)}"
            )
        result[binding.scene] = sorted(actual)
    return result


__all__ = [
    "AuthorityFrame",
    "AuthorityScene",
    "DatasetAuthority",
    "OUTPUT_ARTIFACTS",
    "SceneBinding",
    "ValidatedSubmission",
    "expected_prediction_files",
    "list_profiles",
    "load_authority",
    "load_profile",
    "profile_root",
    "validate_prediction_directories",
    "validate_submission",
]
