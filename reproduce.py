#!/usr/bin/env python3
"""Verify the private Paper 3 reproducibility-capsule staging repository.

Level A is intentionally dependency-free. It closes the managed file set,
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
import sys
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MANIFEST = ROOT / "CAPSULE_MANIFEST.json"
SOURCE_REFS = ROOT / "SOURCE_REFS.json"
HEADLINES = ROOT / "records" / "HEADLINES.json"
LITERATURE_RESULT = ROOT / "records" / "paper3_literature_audit_result.json"

_IGNORED_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
    }
)
_IGNORED_NAMES = frozenset({".DS_Store"})
_REQUIRED_MANAGED_PATHS = frozenset(
    {
        ".gitattributes",
        ".gitignore",
        "INTERNAL_STAGING.md",
        "LICENSE_PENDING.md",
        "README.md",
        "RELEASE_SCOPE.md",
        "SOURCE_REFS.json",
        "THIRD_PARTY_NOTICES_DRAFT.md",
        "data/ACQUISITION.md",
        "data/expected_inputs.json",
        "pyproject.toml",
        "records/HEADLINES.json",
        "records/paper3_literature_audit_result.json",
        "reproduce.py",
        "src/benchmark_integrity/__init__.py",
        "src/benchmark_integrity/comparability.py",
        "src/benchmark_integrity/metric_conventions.py",
        "src/benchmark_integrity/region_error.py",
        "tests/test_capsule_tamper.py",
        "tests/test_capsule_verify.py",
        "tests/test_kernel_smoke.py",
        "uv.lock",
    }
)

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


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != value:
        raise ValueError(f"{field} is not a canonical safe relative path: {value!r}")
    return value


def _is_generated(relative: PurePosixPath) -> bool:
    return bool(_IGNORED_PARTS.intersection(relative.parts)) or relative.name in _IGNORED_NAMES or relative.suffix in {".pyc", ".pyo"}


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
            if not _is_generated(rel):
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            candidate = base / name
            rel = PurePosixPath((relative_base / name).as_posix())
            if candidate.is_symlink():
                raise ValueError(f"symlink file is forbidden: {rel}")
            if not _is_generated(rel):
                actual.add(rel.as_posix())
    return actual


def verify_manifest() -> dict[str, Any]:
    document = _load(MANIFEST)
    if document.get("artifact") != "paper3_private_capsule_manifest":
        raise ValueError("CAPSULE_MANIFEST.json has an unexpected artifact type")
    if document.get("schema_version") != 1:
        raise ValueError("CAPSULE_MANIFEST.json schema_version must be 1")
    if document.get("status") != "private_staging_not_release":
        raise ValueError("CAPSULE_MANIFEST.json status must remain private_staging_not_release")
    if document.get("self_path") != "CAPSULE_MANIFEST.json":
        raise ValueError("manifest self_path must be CAPSULE_MANIFEST.json")
    files = document.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("manifest files must be a non-empty object")

    declared: set[str] = set()
    verified: dict[str, dict[str, Any]] = {}
    for raw_path, entry in files.items():
        path = _safe_relative_path(raw_path, field="manifest path")
        if path == "CAPSULE_MANIFEST.json":
            raise ValueError("the manifest must not list itself in files")
        if path in declared:
            raise ValueError(f"duplicate manifest path: {path}")
        declared.add(path)
        if not isinstance(entry, dict):
            raise ValueError(f"manifest entry must be an object: {path}")
        expected_sha = entry.get("sha256")
        expected_size = entry.get("size")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError(f"invalid SHA-256 for {path}")
        if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
            raise ValueError(f"invalid size for {path}")
        file_path = ROOT / path
        if not file_path.is_file() or file_path.is_symlink():
            raise ValueError(f"declared regular file is missing or unsafe: {path}")
        payload = file_path.read_bytes()
        actual_sha = sha256_bytes(payload)
        if len(payload) != expected_size or actual_sha != expected_sha:
            raise ValueError(
                f"{path}: identity mismatch: expected {expected_size} bytes/{expected_sha}, "
                f"got {len(payload)} bytes/{actual_sha}"
            )
        verified[path] = {"sha256": actual_sha, "size": len(payload)}

    if not _REQUIRED_MANAGED_PATHS.issubset(declared):
        missing_required = sorted(_REQUIRED_MANAGED_PATHS - declared)
        raise ValueError(f"manifest omits required managed files: {missing_required}")

    actual = _enumerate_managed_tree()
    expected = declared | {"CAPSULE_MANIFEST.json"}
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(f"closed-tree mismatch: extra={extra}, missing={missing}")

    return {
        "managed_files": len(declared),
        "manifest_sha256": sha256_bytes(MANIFEST.read_bytes()),
        "verified": verified,
    }


def verify_source_refs() -> dict[str, Any]:
    refs = _load(SOURCE_REFS)
    if refs.get("artifact") != "paper3_private_capsule_source_refs" or refs.get("schema_version") != 2:
        raise ValueError("SOURCE_REFS.json has an unsupported identity")
    if refs.get("status") != "private_staging_not_release":
        raise ValueError("SOURCE_REFS.json status must remain private_staging_not_release")
    materialised = refs.get("materialised_files")
    if not isinstance(materialised, dict) or not materialised:
        raise ValueError("SOURCE_REFS.json materialised_files must be non-empty")

    verified: dict[str, dict[str, str]] = {}
    for raw_path, record in materialised.items():
        path = _safe_relative_path(raw_path, field="source-ref path")
        if not isinstance(record, dict) or record.get("transformation") != "none":
            raise ValueError(f"{path}: only unmodified source snapshots are admitted in Phase 0")
        for name in ("source_repository", "source_path", "source_ref"):
            if not isinstance(record.get(name), str) or not record[name]:
                raise ValueError(f"{path}: missing {name}")
        payload = (ROOT / path).read_bytes()
        actual_git = git_blob_sha1_bytes(payload)
        actual_sha = sha256_bytes(payload)
        if actual_git != record.get("git_blob_sha1") or actual_sha != record.get("source_sha256"):
            raise ValueError(f"{path}: local bytes no longer match frozen source metadata")
        verified[path] = {
            "git_blob_sha1": actual_git,
            "sha256": actual_sha,
            "source_ref": record["source_ref"],
        }
    return {
        "verified": verified,
        "scope": (
            "local bytes match frozen source metadata; the repository commit is the external "
            "anchor for the export receipt and manifest"
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
    if not math.isclose(denominator.keep_minus_true_db, 3.010299913210364, abs_tol=1e-12):
        raise ValueError(f"unexpected keep-minus-true gap: {denominator.keep_minus_true_db}")
    pooled = aggregate_region_errors([stats, stats], reduction="pooled", convention=FINITE_PSNR_CONVENTION)
    if pooled.status != "complete" or not math.isclose(
        pooled.keep_minus_true_db or math.nan,
        denominator.keep_minus_true_db,
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
            claim_mode="ordering", facts=replace(common, output_target_equal=False)
        ),
        "unknown": assess_comparability(
            claim_mode="ordering", facts=replace(common, source_measurement_determined=False)
        ),
        "rerun": assess_comparability(
            claim_mode="ordering", facts=replace(common, frame_population_equal=False)
        ),
        "rescore": assess_comparability(
            claim_mode="ordering", facts=replace(common, mask_support_equal=False)
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
        mode: assess_comparability(claim_mode=mode, facts=transport_facts, transport=transport).disposition
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
    if policy.get("schema_version") != 1 or policy.get("source_record") != "records/paper3_literature_audit_result.json":
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
    manifest = verify_manifest()
    source_refs = verify_source_refs()
    return {
        "artifact": "paper3_private_capsule_verification",
        "status": "pass",
        "level": "A-private-phase0",
        "manifest": manifest,
        "source_refs": source_refs,
        "kernel": verify_kernel(),
        "literature_headlines": verify_headlines(),
        "limitations": [
            "the repository commit externally anchors the verifier and manifest themselves",
            "official #103 conformance vectors and independent oracle are not yet materialised",
            "the Level-B raw-image replay path is not yet wired",
            "record checks do not independently repeat literature searches",
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
