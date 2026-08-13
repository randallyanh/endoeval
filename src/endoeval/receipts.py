"""Offline receipt verification and claim-conditioned comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from benchmark_integrity.comparability import ComparisonFacts, assess_comparability
from endoeval.canonical import EndoEvalError, canonical_sha256, file_sha256, load_json
from endoeval.contracts import OUTPUT_ARTIFACTS, load_authority, load_profile

_RECEIPT_NAME = "evaluation_receipt.json"
_HASHED_OUTPUTS = frozenset(OUTPUT_ARTIFACTS) - {_RECEIPT_NAME}
_RECEIPT_KEYS = frozenset(
    {
        "artifact",
        "schema_version",
        "profile_id",
        "profile_sha256",
        "authority_sha256",
        "submission_sha256",
        "method",
        "artifact_sha256",
        "prediction_set_sha256",
        "measurement",
        "measurement_sha256",
        "aggregate_psnr_db",
        "outputs",
        "receipt_sha256",
    }
)


def verify_receipt(receipt_path: Path) -> dict[str, Any]:
    receipt_path = receipt_path.expanduser().resolve()
    receipt = load_json(receipt_path)
    if not isinstance(receipt, dict):
        raise EndoEvalError("receipt must be a JSON object")
    if set(receipt) != _RECEIPT_KEYS:
        raise EndoEvalError(
            f"receipt keys differ: extra={sorted(set(receipt) - _RECEIPT_KEYS)}, "
            f"missing={sorted(_RECEIPT_KEYS - set(receipt))}"
        )
    if receipt["artifact"] != "endoeval_evaluation_receipt" or receipt["schema_version"] != 1:
        raise EndoEvalError("receipt has an unsupported identity")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    actual_receipt_sha256 = canonical_sha256(unsigned)
    if actual_receipt_sha256 != receipt["receipt_sha256"]:
        raise EndoEvalError("receipt_sha256 does not match the receipt content")
    if canonical_sha256(receipt["measurement"]) != receipt["measurement_sha256"]:
        raise EndoEvalError("measurement_sha256 does not match its components")
    profile, profile_path = load_profile(receipt["profile_id"])
    _, authority_path = load_authority(profile)
    if file_sha256(profile_path) != receipt["profile_sha256"]:
        raise EndoEvalError("the installed profile differs from the evaluated profile")
    if file_sha256(authority_path) != receipt["authority_sha256"]:
        raise EndoEvalError("the installed authority differs from the evaluated authority")
    output_dir = receipt_path.parent
    outputs = receipt["outputs"]
    if not isinstance(outputs, dict) or set(outputs) != _HASHED_OUTPUTS:
        raise EndoEvalError("receipt output set differs from the profile contract")
    for name, expected in outputs.items():
        path = output_dir / name
        if not path.is_file():
            raise EndoEvalError(f"receipt output is missing: {path}")
        actual = file_sha256(path)
        if actual != expected:
            raise EndoEvalError(f"receipt output changed: {name}")
    metrics = load_json(output_dir / "metrics.json")
    admission = load_json(output_dir / "admission.json")
    if metrics.get("profile_id") != receipt["profile_id"]:
        raise EndoEvalError("metrics/profile mismatch")
    if admission.get("measurement_sha256") != receipt["measurement_sha256"]:
        raise EndoEvalError("admission/measurement mismatch")
    # both floats come from the same evaluation through json.dumps, and Python
    # float repr round-trips exactly, so identity — not tolerance — is correct
    if metrics.get("aggregate", {}).get("psnr_db") != receipt["aggregate_psnr_db"]:
        raise EndoEvalError("receipt aggregate differs from metrics.json")
    return {
        "artifact": "endoeval_receipt_verification",
        "status": "valid",
        "profile": receipt["profile_id"],
        "method": receipt["method"]["name"],
        "receipt_sha256": receipt["receipt_sha256"],
        "measurement_sha256": receipt["measurement_sha256"],
        "artifact_sha256": receipt["artifact_sha256"],
        "aggregate_psnr_db": receipt["aggregate_psnr_db"],
        "receipt": receipt,
    }


def compare_receipts(
    left_path: Path,
    right_path: Path,
    *,
    claim: str,
) -> dict[str, Any]:
    left = verify_receipt(left_path)
    right = verify_receipt(right_path)
    left_receipt = left["receipt"]
    right_receipt = right["receipt"]
    left_measurement = left_receipt["measurement"]
    right_measurement = right_receipt["measurement"]
    facts = ComparisonFacts(
        source_identity=left_receipt["measurement_sha256"],
        target_identity=right_receipt["measurement_sha256"],
        output_target_equal=(
            left_measurement["output_target_sha256"] == right_measurement["output_target_sha256"]
        ),
        source_measurement_determined=True,
        target_measurement_determined=True,
        frame_population_equal=(
            left_measurement["frame_population_sha256"]
            == right_measurement["frame_population_sha256"]
        ),
        mask_support_equal=(
            left_measurement["mask_support_sha256"] == right_measurement["mask_support_sha256"]
        ),
        scoring_protocol_equal=(
            left_measurement["scoring_protocol_sha256"]
            == right_measurement["scoring_protocol_sha256"]
        ),
        metric_definition_equal=(
            left_measurement["metric_definition_sha256"]
            == right_measurement["metric_definition_sha256"]
        ),
        reduction_equal=(
            left_measurement["reduction_sha256"] == right_measurement["reduction_sha256"]
        ),
        source_capability_admitted=False,
        target_capability_admitted=False,
    )
    decision = assess_comparability(claim_mode=claim, facts=facts)
    difference = left["aggregate_psnr_db"] - right["aggregate_psnr_db"]
    ordering = None
    if decision.disposition == "identical" and claim == "ordering":
        if difference > 0:
            ordering = f"{left['method']} > {right['method']}"
        elif difference < 0:
            ordering = f"{right['method']} > {left['method']}"
        else:
            ordering = f"{left['method']} == {right['method']}"
    return {
        "artifact": "endoeval_comparison",
        "status": "complete",
        "claim": claim,
        "left": left["method"],
        "right": right["method"],
        "left_psnr_db": left["aggregate_psnr_db"],
        "right_psnr_db": right["aggregate_psnr_db"],
        "left_minus_right_db": difference,
        "disposition": decision.disposition,
        "reason_codes": list(decision.reason_codes),
        "artifact_ordering": ordering,
    }


__all__ = ["compare_receipts", "verify_receipt"]
