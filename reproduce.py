#!/usr/bin/env python3
"""Verify the private Paper 3 reproducibility-capsule staging repository.

Level A is intentionally dependency-free. It closes the managed source surface,
checks imported scientific-source identities, exercises the numerical and
claim-admission kernel, and validates frozen record-level headlines. Level B
raw replay remains blocked until the final #103/#115 boundaries, authorised
input manifest, immutable Paper 3 refs, and licences exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
ROOT_RESOLVED = ROOT.resolve()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MANIFEST = ROOT / "CAPSULE_MANIFEST.json"
SOURCE_REFS = ROOT / "SOURCE_REFS.json"
HEADLINES = ROOT / "records" / "HEADLINES.json"
LITERATURE_RESULT = ROOT / "records" / "paper3_literature_audit_result.json"

_ENVIRONMENT_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "build",
        "dist",
    }
)
_IGNORED_NAMES = frozenset({".DS_Store"})
_FORBIDDEN_CACHE_DIRS = frozenset({"__pycache__"})
_FORBIDDEN_CACHE_SUFFIXES = frozenset({".pyc", ".pyo"})
_AUTHORED_ORIGIN = {"type": "authored_private_staging"}
_SOURCE_ORIGIN_KEYS = frozenset(
    {
        "git_blob_sha1",
        "source_path",
        "source_ref",
        "source_repository",
        "source_sha256",
        "transformation",
    }
)
_SNAPSHOT_KINDS = frozenset({"source_snapshot", "record_snapshot"})
_EXPECTED_MANAGED_FILES: dict[str, tuple[str, str]] = {
    ".gitattributes": ("packaging", "100644"),
    ".gitignore": ("packaging", "100644"),
    "INTERNAL_STAGING.md": ("policy", "100644"),
    "LICENSE_PENDING.md": ("policy", "100644"),
    "README.md": ("documentation", "100644"),
    "RELEASE_SCOPE.md": ("policy", "100644"),
    "SOURCE_REFS.json": ("provenance", "100644"),
    "THIRD_PARTY_NOTICES_DRAFT.md": ("policy", "100644"),
    "data/ACQUISITION.md": ("policy", "100644"),
    "data/expected_inputs.json": ("policy", "100644"),
    "pyproject.toml": ("packaging", "100644"),
    "records/HEADLINES.json": ("verification_policy", "100644"),
    "records/paper3_literature_audit_result.json": ("record_snapshot", "100644"),
    "reproduce.py": ("verifier", "100755"),
    "src/benchmark_integrity/__init__.py": ("staging_support", "100644"),
    "src/benchmark_integrity/comparability.py": ("source_snapshot", "100644"),
    "src/benchmark_integrity/metric_conventions.py": ("source_snapshot", "100644"),
    "src/benchmark_integrity/region_error.py": ("source_snapshot", "100644"),
    "tests/test_capsule_tamper.py": ("test", "100644"),
    "tests/test_capsule_verify.py": ("test", "100644"),
    "tests/test_kernel_smoke.py": ("test", "100644"),
    "uv.lock": ("packaging", "100644"),
}
_REQUIRED_MANAGED_PATHS = frozenset(_EXPECTED_MANAGED_FILES)

_EXPECTED_HEADLINE_CHECKS: tuple[dict[str, Any], ...] = (
    {
        "name": "result_units",
        "path": ["population", "predefined_result_units"],
        "expected": 27,
    },
    {
        "name": "formal_judgements",
        "path": ["population", "result_unit_by_dimension_judgements"],
        "expected": 189,
    },
    {
        "name": "measurement_judgements",
        "path": ["measurement_definition", "judgements"],
        "expected": 162,
    },
    {
        "name": "fully_specified_measurement_judgements",
        "path": ["measurement_definition", "verdicts", "fully_specified"],
        "expected": 0,
    },
    {
        "name": "strong_attribution_denominator",
        "path": ["attribution", "denominator"],
        "expected": 27,
    },
    {
        "name": "strong_result_to_run_attribution",
        "path": ["attribution", "strong_inspectable_result_to_run_linkage"],
        "expected": 0,
    },
    {
        "name": "adjudicated_rows_changed_from_first_pass",
        "path": [
            "answer_withheld_rederivation",
            "adjudicated_rows_changed_from_first_pass",
        ],
        "expected": 71,
    },
    {
        "name": "exact_evaluation_support_closed",
        "path": ["field_level_closures", "exact_evaluation_support"],
        "expected": 17,
    },
)
_EXPECTED_HEADLINE_INTERPRETATION = (
    "These are frozen record-level checks. They do not independently repeat "
    "source searches, decode omitted images, or prove method capability."
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1_bytes(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError(f"duplicate JSON key: {key!r}")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _load(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_json_constant,
    )


def _require_hex_digest(value: object, *, field: str, length: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a lowercase {length}-character hex digest")
    return value


def _safe_posix_relative_path(value: object, *, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if "\0" in value or "\\" in value:
        raise ValueError(f"{field} is not a canonical POSIX relative path: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"{field} contains an empty, dot, or parent component: {value!r}")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or posix.as_posix() != value
    ):
        raise ValueError(f"{field} is not a canonical safe relative path: {value!r}")
    return posix


def _safe_relative_path(value: object, *, field: str) -> str:
    posix = _safe_posix_relative_path(value, field=field)
    candidate = ROOT.joinpath(*posix.parts).resolve(strict=False)
    try:
        candidate.relative_to(ROOT_RESOLVED)
    except ValueError as exc:
        raise ValueError(f"{field} escapes the capsule root: {value!r}") from exc
    return posix.as_posix()


def _managed_file(path: str) -> Path:
    posix = _safe_posix_relative_path(path, field="managed path")
    return ROOT.joinpath(*posix.parts)


def _enumerate_managed_tree() -> set[str]:
    actual: set[str] = set()
    for directory, dirnames, filenames in os.walk(ROOT, followlinks=False):
        base = Path(directory)
        relative_base = base.relative_to(ROOT)
        kept_dirs: list[str] = []
        for name in dirnames:
            candidate = base / name
            rel = PurePosixPath((relative_base / name).as_posix())
            if candidate.is_symlink():
                raise ValueError(f"symlink directory is forbidden: {rel}")
            if name in _FORBIDDEN_CACHE_DIRS:
                raise ValueError(f"source bytecode cache is forbidden: {rel}")
            if name not in _ENVIRONMENT_DIRS:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            candidate = base / name
            rel = PurePosixPath((relative_base / name).as_posix())
            if candidate.is_symlink():
                raise ValueError(f"symlink file is forbidden: {rel}")
            if rel.parts and rel.parts[0] == ".git":
                continue
            if rel.name in _IGNORED_NAMES:
                continue
            if rel.suffix in _FORBIDDEN_CACHE_SUFFIXES:
                raise ValueError(f"source bytecode file is forbidden: {rel}")
            actual.add(rel.as_posix())
    return actual


def _validate_source_origin(origin: object, *, field: str) -> dict[str, Any]:
    if not isinstance(origin, dict) or set(origin) != _SOURCE_ORIGIN_KEYS:
        raise ValueError(f"{field} must contain the exact source-origin fields")
    if origin.get("transformation") != "none":
        raise ValueError(f"{field}.transformation must be 'none' in Phase 0")
    repository = origin.get("source_repository")
    if repository != "randallyanh/GP4DGS":
        raise ValueError(f"{field}.source_repository is unexpected: {repository!r}")
    _safe_posix_relative_path(origin.get("source_path"), field=f"{field}.source_path")
    _require_hex_digest(origin.get("source_ref"), field=f"{field}.source_ref", length=40)
    _require_hex_digest(
        origin.get("git_blob_sha1"),
        field=f"{field}.git_blob_sha1",
        length=40,
    )
    _require_hex_digest(
        origin.get("source_sha256"),
        field=f"{field}.source_sha256",
        length=64,
    )
    return origin


def _validate_manifest_entry(path: str, entry: object) -> None:
    expected_kind, expected_mode = _EXPECTED_MANAGED_FILES[path]
    if not isinstance(entry, dict):
        raise ValueError(f"manifest entry must be an object: {path}")
    required_keys = {"kind", "mode", "origin", "sha256", "size"}
    if set(entry) != required_keys:
        raise ValueError(f"{path}: manifest entry keys must be {sorted(required_keys)}")
    if entry.get("kind") != expected_kind:
        raise ValueError(f"{path}: kind must be {expected_kind!r}")
    if entry.get("mode") != expected_mode:
        raise ValueError(f"{path}: mode must be {expected_mode!r}")
    _require_hex_digest(entry.get("sha256"), field=f"{path}.sha256", length=64)
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError(f"{path}: size must be a non-negative integer")
    if expected_kind in _SNAPSHOT_KINDS:
        _validate_source_origin(entry.get("origin"), field=f"{path}.origin")
    elif entry.get("origin") != _AUTHORED_ORIGIN:
        raise ValueError(f"{path}: authored files require the private-staging origin")


def _verify_posix_mode(path: str, expected_mode: str) -> bool:
    if os.name != "posix":
        return False
    permissions = stat.S_IMODE(_managed_file(path).stat().st_mode)
    expected_permissions = int(expected_mode[-3:], 8)
    if permissions != expected_permissions:
        raise ValueError(
            f"{path}: mode mismatch: expected {expected_mode}, got 100{permissions:03o}"
        )
    return True


def _validated_manifest() -> tuple[dict[str, Any], dict[str, Any]]:
    document = _load(MANIFEST)
    if not isinstance(document, dict):
        raise ValueError("CAPSULE_MANIFEST.json must contain an object")
    expected_top_level = {
        "artifact",
        "external_anchor",
        "files",
        "schema_version",
        "self_path",
        "status",
    }
    if set(document) != expected_top_level:
        raise ValueError("CAPSULE_MANIFEST.json has unexpected top-level fields")
    if document.get("artifact") != "paper3_private_capsule_manifest":
        raise ValueError("CAPSULE_MANIFEST.json has an unexpected artifact type")
    if document.get("schema_version") != 1:
        raise ValueError("CAPSULE_MANIFEST.json schema_version must be 1")
    if document.get("status") != "private_staging_not_release":
        raise ValueError("CAPSULE_MANIFEST.json status must remain private_staging_not_release")
    if document.get("self_path") != "CAPSULE_MANIFEST.json":
        raise ValueError("manifest self_path must be CAPSULE_MANIFEST.json")
    if document.get("external_anchor") != "the exact Git commit containing this manifest":
        raise ValueError("manifest external_anchor moved")

    files = document.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files must be an object")
    declared = frozenset(
        _safe_relative_path(raw_path, field="manifest path") for raw_path in files
    )
    if declared != _REQUIRED_MANAGED_PATHS:
        extra = sorted(declared - _REQUIRED_MANAGED_PATHS)
        missing = sorted(_REQUIRED_MANAGED_PATHS - declared)
        raise ValueError(f"manifest allowlist mismatch: extra={extra}, missing={missing}")

    verified: dict[str, dict[str, Any]] = {}
    modes_verified = True
    for path in sorted(declared):
        entry = files[path]
        _validate_manifest_entry(path, entry)
        file_path = _managed_file(path)
        if not file_path.is_file() or file_path.is_symlink():
            raise ValueError(f"declared regular file is missing or unsafe: {path}")
        payload = file_path.read_bytes()
        actual_sha = sha256_bytes(payload)
        if len(payload) != entry["size"] or actual_sha != entry["sha256"]:
            raise ValueError(
                f"{path}: identity mismatch: expected {entry['size']} bytes/"
                f"{entry['sha256']}, got {len(payload)} bytes/{actual_sha}"
            )
        modes_verified = _verify_posix_mode(path, entry["mode"]) and modes_verified
        verified[path] = {"sha256": actual_sha, "size": len(payload)}

    actual = _enumerate_managed_tree()
    expected = set(declared) | {"CAPSULE_MANIFEST.json"}
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(f"closed-tree mismatch: extra={extra}, missing={missing}")

    return document, {
        "managed_files": len(declared),
        "manifest_sha256": sha256_bytes(MANIFEST.read_bytes()),
        "modes_verified_on_posix": modes_verified,
        "verified": verified,
    }


def verify_manifest() -> dict[str, Any]:
    return _validated_manifest()[1]


def verify_source_refs(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if manifest is None:
        manifest = _validated_manifest()[0]
    refs = _load(SOURCE_REFS)
    expected_top_level = {
        "artifact",
        "materialised_files",
        "planned_not_materialised",
        "release_blockers",
        "schema_version",
        "source_repository",
        "status",
    }
    if not isinstance(refs, dict) or set(refs) != expected_top_level:
        raise ValueError("SOURCE_REFS.json has unexpected top-level fields")
    if (
        refs.get("artifact") != "paper3_private_capsule_source_refs"
        or refs.get("schema_version") != 2
    ):
        raise ValueError("SOURCE_REFS.json has an unsupported identity")
    if refs.get("status") != "private_staging_not_release":
        raise ValueError("SOURCE_REFS.json status must remain private_staging_not_release")
    if refs.get("source_repository") != "randallyanh/GP4DGS":
        raise ValueError("SOURCE_REFS.json source_repository moved")
    if not isinstance(refs.get("planned_not_materialised"), list) or not isinstance(
        refs.get("release_blockers"), list
    ):
        raise ValueError("SOURCE_REFS.json blocker lists must remain arrays")

    materialised = refs.get("materialised_files")
    if not isinstance(materialised, dict):
        raise ValueError("SOURCE_REFS.json materialised_files must be an object")
    source_manifest_entries = {
        path: entry["origin"]
        for path, entry in manifest["files"].items()
        if entry["kind"] in _SNAPSHOT_KINDS
    }
    materialised_paths = frozenset(
        _safe_relative_path(path, field="source-ref path") for path in materialised
    )
    if materialised_paths != frozenset(source_manifest_entries):
        extra = sorted(materialised_paths - frozenset(source_manifest_entries))
        missing = sorted(frozenset(source_manifest_entries) - materialised_paths)
        raise ValueError(f"source-ref coverage mismatch: extra={extra}, missing={missing}")

    verified: dict[str, dict[str, str]] = {}
    for path in sorted(materialised_paths):
        record = _validate_source_origin(
            materialised[path],
            field=f"SOURCE_REFS.json[{path!r}]",
        )
        if record != source_manifest_entries[path]:
            raise ValueError(f"{path}: manifest origin and SOURCE_REFS.json disagree")
        payload = _managed_file(path).read_bytes()
        actual_git = git_blob_sha1_bytes(payload)
        actual_sha = sha256_bytes(payload)
        if (
            actual_git != record["git_blob_sha1"]
            or actual_sha != record["source_sha256"]
        ):
            raise ValueError(f"{path}: local bytes no longer match frozen source metadata")
        verified[path] = {
            "git_blob_sha1": actual_git,
            "sha256": actual_sha,
            "source_ref": record["source_ref"],
        }
    return {
        "verified": verified,
        "scope": (
            "local bytes match the commit-anchored manifest and frozen source metadata; "
            "the private exporter must independently read the named Git objects"
        ),
    }


def verify_kernel() -> dict[str, Any]:
    from benchmark_integrity.comparability import (
        ComparisonFacts,
        PsnrTransportFacts,
        assess_comparability,
    )
    from benchmark_integrity.metric_conventions import (
        FINITE_PSNR_CONVENTION,
        psnr_from_mse,
    )
    from benchmark_integrity.region_error import (
        RegionErrorStats,
        aggregate_region_errors,
        compare_psnr_denominators,
    )

    psnr = psnr_from_mse(0.01, convention=FINITE_PSNR_CONVENTION)
    if not math.isclose(psnr, 19.99999995657055, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"unexpected finite PSNR: {psnr}")

    stats = RegionErrorStats(
        total_pixels=4,
        selected_pixels=2,
        selected_sse=0.06,
        complement_sse=0.12,
        channels=3,
    )
    denominator = compare_psnr_denominators(stats, convention=FINITE_PSNR_CONVENTION)
    if denominator.status != "complete" or denominator.keep_minus_true_db is None:
        raise ValueError(f"synthetic denominator comparison did not close: {denominator.status}")
    if not math.isclose(
        denominator.keep_minus_true_db,
        3.010299913210364,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(f"unexpected keep-minus-true gap: {denominator.keep_minus_true_db}")
    pooled = aggregate_region_errors(
        [stats, stats],
        reduction="pooled",
        convention=FINITE_PSNR_CONVENTION,
    )
    if pooled.status != "complete" or not math.isclose(
        pooled.keep_minus_true_db or math.nan,
        denominator.keep_minus_true_db,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("pooled sufficient-statistics reduction drifted")

    common = ComparisonFacts(
        source_identity="0" * 64,
        target_identity="1" * 64,
        output_target_equal=True,
        source_measurement_determined=True,
        target_measurement_determined=True,
        frame_population_equal=True,
        mask_support_equal=True,
        scoring_protocol_equal=True,
        metric_definition_equal=True,
        reduction_equal=True,
    )
    cases = {
        "ordering": assess_comparability(claim_mode="ordering", facts=common),
        "capability": assess_comparability(claim_mode="capability", facts=common),
        "target_mismatch": assess_comparability(
            claim_mode="ordering",
            facts=replace(common, output_target_equal=False),
        ),
        "unknown": assess_comparability(
            claim_mode="ordering",
            facts=replace(common, source_measurement_determined=False),
        ),
        "rerun": assess_comparability(
            claim_mode="ordering",
            facts=replace(common, frame_population_equal=False),
        ),
        "rescore": assess_comparability(
            claim_mode="ordering",
            facts=replace(common, mask_support_equal=False),
        ),
    }
    expected = {
        "ordering": "identical",
        "capability": "rerun_required",
        "target_mismatch": "target_mismatch",
        "unknown": "unknown",
        "rerun": "rerun_required",
        "rescore": "rescore_required",
    }
    actual = {name: decision.disposition for name, decision in cases.items()}
    if actual != expected:
        raise ValueError(f"claim-disposition smoke mismatch: expected {expected}, got {actual}")

    transport_facts = replace(
        common,
        scoring_protocol_equal=False,
        metric_definition_equal=False,
    )
    transport = PsnrTransportFacts(
        source_measurement_sha256=common.source_identity,
        target_measurement_sha256=common.target_identity,
        source_denominator="keep_denominator",
        target_denominator="true_exclusion",
        source_evidence_contract_sha256="2" * 64,
        target_evidence_contract_sha256="3" * 64,
        source_keep_minus_true_db=1.0,
        target_keep_minus_true_db=1.0,
        reduction="pooled",
        denominator_only_difference=True,
        same_support=True,
        epsilon_free=False,
        infinity_capped=False,
    )
    transported = {
        mode: assess_comparability(
            claim_mode=mode,
            facts=transport_facts,
            transport=transport,
        ).disposition
        for mode in ("scalar", "ordering", "capability")
    }
    if transported != {
        "scalar": "exact_transport",
        "ordering": "invariant",
        "capability": "rerun_required",
    }:
        raise ValueError(f"transport claim boundaries drifted: {transported}")

    return {
        "finite_psnr_db": psnr,
        "keep_minus_true_db": denominator.keep_minus_true_db,
        "dispositions": actual,
        "transport_dispositions": transported,
    }


def _value_at(document: Any, path: list[str]) -> Any:
    current = document
    for component in path:
        if not isinstance(current, dict) or component not in current:
            raise ValueError(f"missing path component {component!r} in {path!r}")
        current = current[component]
    return current


def verify_headlines() -> dict[str, Any]:
    policy = _load(HEADLINES)
    if policy.get("artifact") != "paper3_private_capsule_expected_headlines":
        raise ValueError("HEADLINES.json has an unexpected artifact")
    if (
        policy.get("schema_version") != 1
        or policy.get("source_record")
        != "records/paper3_literature_audit_result.json"
    ):
        raise ValueError("HEADLINES.json schema or source record moved")
    if policy.get("checks") != list(_EXPECTED_HEADLINE_CHECKS):
        raise ValueError("HEADLINES.json checks do not match the frozen Phase-0 policy")
    if policy.get("interpretation") != _EXPECTED_HEADLINE_INTERPRETATION:
        raise ValueError("HEADLINES.json interpretation boundary moved")

    result = _load(LITERATURE_RESULT)
    checked: dict[str, Any] = {}
    for check in _EXPECTED_HEADLINE_CHECKS:
        actual = _value_at(result, check["path"])
        if actual != check["expected"]:
            raise ValueError(
                f"{check['name']}: expected {check['expected']!r}, got {actual!r}"
            )
        checked[check["name"]] = actual
    return checked


def verify() -> dict[str, Any]:
    manifest_document, manifest_report = _validated_manifest()
    source_refs = verify_source_refs(manifest_document)
    return {
        "artifact": "paper3_private_capsule_verification",
        "status": "pass",
        "level": "A-private-phase0",
        "manifest": manifest_report,
        "source_refs": source_refs,
        "kernel": verify_kernel(),
        "literature_headlines": verify_headlines(),
        "limitations": [
            "the repository commit externally anchors the verifier and manifest themselves",
            "official #103 conformance vectors and independent oracle are not yet materialised",
            "the Level-B raw-image replay path is not yet wired",
            "record checks do not independently repeat literature searches",
            "the Python interpreter and virtual environment are outside the managed source surface",
            "no public licence or redistribution grant is asserted",
        ],
    }


def raw_status(input_root: Path) -> dict[str, Any]:
    return {
        "artifact": "paper3_private_capsule_raw_replay",
        "status": "blocked",
        "input_root": str(input_root),
        "reason": (
            "Level B is intentionally unavailable until #103 and #115 close, final source refs "
            "are frozen, and a licensed expected-input manifest is reviewed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify", help="run the private Level-A verifier")
    raw_parser = subparsers.add_parser("raw", help="show the explicit Level-B blocker")
    raw_parser.add_argument("--input-root", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "raw":
        print(json.dumps(raw_status(args.input_root), indent=2, sort_keys=True))
        return 2
    try:
        print(json.dumps(verify(), indent=2, sort_keys=True))
    except Exception as exc:  # one public fail-closed boundary
        print(
            json.dumps(
                {
                    "artifact": "paper3_private_capsule_verification",
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
