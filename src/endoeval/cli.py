"""Profile-driven command line contract for EndoEval."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "profiles"
_PROFILE_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
_PROFILE_KEYS = frozenset(
    {
        "artifact",
        "blocked_by",
        "dataset",
        "domain",
        "measurement",
        "outputs",
        "profile_id",
        "schema_version",
        "status",
        "submission",
        "task",
    }
)
_SUBMISSION_KEYS = frozenset(
    {"artifact", "method", "profile", "scenes", "schema_version"}
)
_METHOD_KEYS = frozenset({"name", "source_commit", "version"})
_SCENE_KEYS = frozenset({"predictions", "scene"})


class EndoEvalError(ValueError):
    """A user-visible profile or submission error."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EndoEvalError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise EndoEvalError(f"non-finite JSON constant is forbidden: {value}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except OSError as exc:
        raise EndoEvalError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EndoEvalError(f"invalid JSON in {path}: {exc}") from exc


def _safe_relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise EndoEvalError(f"{field} must be a non-empty relative path")
    if "\0" in value or "\\" in value:
        raise EndoEvalError(f"{field} must use canonical POSIX separators")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise EndoEvalError(f"{field} contains an empty, dot, or parent component")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise EndoEvalError(f"{field} must remain inside the submission directory")
    return posix.as_posix()


def _require_keys(document: object, expected: frozenset[str], *, name: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise EndoEvalError(f"{name} must be a JSON object")
    keys = frozenset(document)
    if keys != expected:
        extra = sorted(keys - expected)
        missing = sorted(expected - keys)
        raise EndoEvalError(f"{name} keys differ: extra={extra}, missing={missing}")
    return document


def _profile_path(profile_id: str) -> Path:
    if not _PROFILE_ID.fullmatch(profile_id):
        raise EndoEvalError(f"invalid profile id: {profile_id!r}")
    path = PROFILES / f"{profile_id}.json"
    if not path.is_file():
        raise EndoEvalError(f"unknown profile: {profile_id}")
    return path


def load_profile(profile_id: str) -> dict[str, Any]:
    profile = _require_keys(
        _load_json(_profile_path(profile_id)),
        _PROFILE_KEYS,
        name=f"profile {profile_id}",
    )
    if profile["artifact"] != "endoeval_profile" or profile["schema_version"] != 1:
        raise EndoEvalError(f"profile {profile_id} has an unsupported identity")
    if profile["profile_id"] != profile_id:
        raise EndoEvalError(
            f"profile file/name mismatch: expected {profile_id!r}, "
            f"got {profile['profile_id']!r}"
        )
    if profile["status"] not in {"draft_not_scoreable", "ready"}:
        raise EndoEvalError(f"profile {profile_id} has an unsupported status")
    dataset = profile["dataset"]
    if not isinstance(dataset, dict) or set(dataset) != {"name", "release", "scenes"}:
        raise EndoEvalError(f"profile {profile_id} has an invalid dataset contract")
    scenes = dataset["scenes"]
    if (
        not isinstance(scenes, list)
        or not scenes
        or any(not isinstance(scene, str) or not scene for scene in scenes)
        or len(scenes) != len(set(scenes))
    ):
        raise EndoEvalError(f"profile {profile_id} scenes must be unique non-empty strings")
    outputs = profile["outputs"]
    if outputs != [
        "metrics.json",
        "evaluation_receipt.json",
        "paper_table.csv",
        "admission.json",
    ]:
        raise EndoEvalError(f"profile {profile_id} output contract moved")
    return profile


def list_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in sorted(PROFILES.glob("*.json")):
        profile = load_profile(path.stem)
        profiles.append(
            {
                "profile_id": profile["profile_id"],
                "status": profile["status"],
                "dataset": profile["dataset"]["name"],
                "task": profile["task"],
            }
        )
    if not profiles:
        raise EndoEvalError("no evaluation profiles are installed")
    return profiles


def validate_submission(
    submission_path: Path,
    *,
    check_paths: bool = False,
) -> dict[str, Any]:
    submission_path = submission_path.resolve()
    submission = _require_keys(
        _load_json(submission_path),
        _SUBMISSION_KEYS,
        name="submission",
    )
    if submission["artifact"] != "endoeval_submission" or submission["schema_version"] != 1:
        raise EndoEvalError("submission has an unsupported identity")
    profile_id = submission["profile"]
    if not isinstance(profile_id, str):
        raise EndoEvalError("submission.profile must be a string")
    profile = load_profile(profile_id)

    method = submission["method"]
    if not isinstance(method, dict) or not set(method).issubset(_METHOD_KEYS):
        raise EndoEvalError("submission.method contains unsupported fields")
    if "name" not in method or not isinstance(method["name"], str) or not method["name"].strip():
        raise EndoEvalError("submission.method.name must be non-empty")
    for optional in ("version", "source_commit"):
        if optional in method and (
            not isinstance(method[optional], str) or not method[optional].strip()
        ):
            raise EndoEvalError(f"submission.method.{optional} must be a non-empty string")
    if "source_commit" in method and not re.fullmatch(
        r"[0-9a-f]{40}", method["source_commit"]
    ):
        raise EndoEvalError("submission.method.source_commit must be a lowercase Git SHA-1")

    raw_scenes = submission["scenes"]
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise EndoEvalError("submission.scenes must be a non-empty array")
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    base = submission_path.parent
    for index, raw_scene in enumerate(raw_scenes):
        scene = _require_keys(raw_scene, _SCENE_KEYS, name=f"submission.scenes[{index}]")
        name = scene["scene"]
        if not isinstance(name, str) or not name:
            raise EndoEvalError(f"submission.scenes[{index}].scene must be non-empty")
        if name in seen:
            raise EndoEvalError(f"duplicate scene: {name}")
        seen.add(name)
        predictions = _safe_relative_path(
            scene["predictions"],
            field=f"submission.scenes[{index}].predictions",
        )
        if check_paths and not (base / predictions).is_dir():
            raise EndoEvalError(f"prediction directory is missing: {predictions}")
        normalized.append({"scene": name, "predictions": predictions})

    expected_scenes = set(profile["dataset"]["scenes"])
    if seen != expected_scenes:
        raise EndoEvalError(
            f"submission scenes differ from profile: "
            f"extra={sorted(seen - expected_scenes)}, "
            f"missing={sorted(expected_scenes - seen)}"
        )

    return {
        "artifact": "endoeval_submission_validation",
        "status": "valid",
        "profile": profile_id,
        "profile_status": profile["status"],
        "method": method["name"],
        "scenes": normalized,
        "filesystem_checked": check_paths,
        "method_specific_adapter_required": False,
    }


def evaluation_status(submission_path: Path, *, output: Path | None = None) -> dict[str, Any]:
    validation = validate_submission(submission_path, check_paths=False)
    profile = load_profile(validation["profile"])
    if profile["status"] != "ready":
        return {
            "artifact": "endoeval_evaluation",
            "status": "blocked",
            "profile": profile["profile_id"],
            "reason": (
                "the profile is draft_not_scoreable; final frame/support authorities "
                "and the maintained RGB/mask-to-statistics adapter are not yet frozen"
            ),
            "blocked_by": profile["blocked_by"],
            "planned_outputs": profile["outputs"],
            "output_directory": str(output) if output is not None else None,
        }
    return {
        "artifact": "endoeval_evaluation",
        "status": "blocked",
        "profile": profile["profile_id"],
        "reason": "the ready-profile scorer is not materialised in this private foundation",
        "planned_outputs": profile["outputs"],
        "output_directory": str(output) if output is not None else None,
    }


def _print(document: object, *, stream: Any = sys.stdout) -> None:
    print(json.dumps(document, indent=2, sort_keys=True), file=stream)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Canonical evaluation profiles for dynamic endoscopic reconstruction."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("profiles", help="list installed evaluation profiles")

    profile_parser = subparsers.add_parser("profile", help="show one versioned profile")
    profile_parser.add_argument("profile_id")

    validate_parser = subparsers.add_parser(
        "validate",
        help="validate a method-independent submission manifest",
    )
    validate_parser.add_argument("submission", type=Path)
    validate_parser.add_argument(
        "--check-paths",
        action="store_true",
        help="also require each prediction directory to exist",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="run a profile or report the exact scientific blocker",
    )
    evaluate_parser.add_argument("submission", type=Path)
    evaluate_parser.add_argument("--output", type=Path)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "profiles":
            _print({"artifact": "endoeval_profiles", "profiles": list_profiles()})
            return 0
        if args.command == "profile":
            _print(load_profile(args.profile_id))
            return 0
        if args.command == "validate":
            _print(validate_submission(args.submission, check_paths=args.check_paths))
            return 0
        status = evaluation_status(args.submission, output=args.output)
        _print(status)
        return 0 if status["status"] == "complete" else 2
    except EndoEvalError as exc:
        _print(
            {
                "artifact": "endoeval_error",
                "status": "error",
                "error": str(exc),
            },
            stream=sys.stderr,
        )
        return 1


__all__ = [
    "EndoEvalError",
    "evaluation_status",
    "list_profiles",
    "load_profile",
    "main",
    "validate_submission",
]
