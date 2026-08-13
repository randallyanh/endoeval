"""Command-line interface for EndoEval."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from endoeval.contracts import (
    EndoEvalError,
    expected_prediction_files,
    list_profiles,
    load_authority,
    load_profile,
    validate_prediction_directories,
    validate_submission,
    write_json,
)
from endoeval.receipts import compare_receipts, verify_receipt
from endoeval.scoring import evaluate


def _print(document: object, *, stream: TextIO = sys.stdout) -> None:
    print(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False), file=stream)


def _profiles_command(args: argparse.Namespace) -> dict[str, Any]:
    return {"artifact": "endoeval_profiles", "profiles": list_profiles()}


def _profile_command(args: argparse.Namespace) -> dict[str, Any]:
    profile, _ = load_profile(args.profile_id)
    authority, authority_path = load_authority(profile)
    return {
        "artifact": "endoeval_profile_summary",
        "profile": profile,
        "authority": {
            "path": str(authority_path),
            "dataset_release": authority["dataset_release"],
            "dimensions_wh": authority["dimensions_wh"],
            "support": authority["support"],
            "scenes": [
                {"scene": scene["scene"], "frames": len(scene["frames"])}
                for scene in authority["scenes"]
            ],
        },
    }


def _init_command(args: argparse.Namespace) -> dict[str, Any]:
    profile, _ = load_profile(args.profile)
    authority, _ = load_authority(profile)
    destination = args.directory.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise EndoEvalError(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    scenes = []
    for scene in authority["scenes"]:
        relative = f"predictions/{scene['scene']}"
        directory = destination / relative
        directory.mkdir(parents=True, exist_ok=True)
        expected = sorted(expected_prediction_files(scene))
        (directory / "EXPECTED_FRAMES.txt").write_text("\n".join(expected) + "\n", encoding="utf-8")
        scenes.append({"scene": scene["scene"], "predictions": relative})
    method: dict[str, str] = {"name": args.method}
    if args.method_version:
        method["version"] = args.method_version
    if args.source_commit:
        method["source_commit"] = args.source_commit
    submission = {
        "artifact": "endoeval_submission",
        "schema_version": 1,
        "profile": profile["profile_id"],
        "method": method,
        "scenes": scenes,
    }
    submission_path = destination / "submission.json"
    write_json(submission_path, submission)
    return {
        "artifact": "endoeval_initialization",
        "status": "complete",
        "submission": str(submission_path),
        "profile": profile["profile_id"],
        "method": args.method,
        "next": [
            "write one PNG for every name in each EXPECTED_FRAMES.txt",
            f"endoeval validate {submission_path} --check-paths",
            f"endoeval evaluate {submission_path} --dataset-root /path/to/EndoNeRF",
        ],
    }


def _validate_command(args: argparse.Namespace) -> dict[str, Any]:
    validated = validate_submission(args.submission)
    files = validate_prediction_directories(validated) if args.check_paths else None
    return {
        "artifact": "endoeval_submission_validation",
        "status": "valid",
        "profile": validated.profile["profile_id"],
        "method": validated.document["method"]["name"],
        "scenes": [binding.scene for binding in validated.scenes],
        "filesystem_checked": args.check_paths,
        "prediction_files": files,
    }


def _evaluate_command(args: argparse.Namespace) -> dict[str, Any]:
    return evaluate(
        args.submission,
        dataset_root=args.dataset_root,
        output=args.output,
        overwrite=args.overwrite,
    )


def _verify_command(args: argparse.Namespace) -> dict[str, Any]:
    result = verify_receipt(args.receipt)
    result.pop("receipt", None)
    return result


def _compare_command(args: argparse.Namespace) -> dict[str, Any]:
    return compare_receipts(args.left, args.right, claim=args.claim)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="endoeval",
        description="Canonical evaluation for dynamic endoscopic reconstruction outputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    profiles_parser = subparsers.add_parser("profiles", help="list installed evaluation profiles")
    profiles_parser.set_defaults(run=_profiles_command)

    profile_parser = subparsers.add_parser("profile", help="show one versioned profile")
    profile_parser.add_argument("profile_id")
    profile_parser.set_defaults(run=_profile_command)

    init_parser = subparsers.add_parser("init", help="create a method-independent submission")
    init_parser.add_argument("directory", type=Path)
    init_parser.add_argument("--profile", required=True)
    init_parser.add_argument("--method", required=True)
    init_parser.add_argument("--method-version")
    init_parser.add_argument("--source-commit")
    init_parser.set_defaults(run=_init_command)

    validate_parser = subparsers.add_parser("validate", help="validate a submission")
    validate_parser.add_argument("submission", type=Path)
    validate_parser.add_argument("--check-paths", action="store_true")
    validate_parser.set_defaults(run=_validate_command)

    evaluate_parser = subparsers.add_parser("evaluate", help="score rendered outputs")
    evaluate_parser.add_argument("submission", type=Path)
    evaluate_parser.add_argument("--dataset-root", type=Path, required=True)
    evaluate_parser.add_argument("--output", type=Path)
    evaluate_parser.add_argument("--overwrite", action="store_true")
    evaluate_parser.set_defaults(run=_evaluate_command)

    verify_parser = subparsers.add_parser("verify", help="verify an evaluation receipt")
    verify_parser.add_argument("receipt", type=Path)
    verify_parser.set_defaults(run=_verify_command)

    compare_parser = subparsers.add_parser("compare", help="compare two verified receipts")
    compare_parser.add_argument("left", type=Path)
    compare_parser.add_argument("right", type=Path)
    compare_parser.add_argument("--claim", choices=("scalar", "ordering", "capability"), default="ordering")
    compare_parser.set_defaults(run=_compare_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = args.run(args)
    except (EndoEvalError, ValueError) as exc:
        _print(
            {"artifact": "endoeval_error", "status": "error", "error": str(exc)},
            stream=sys.stderr,
        )
        return 1
    _print(result)
    return 0


__all__ = ["main"]
