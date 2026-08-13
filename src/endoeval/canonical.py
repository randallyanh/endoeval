"""Canonical encoding, digests, and path safety beneath every EndoEval artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class EndoEvalError(ValueError):
    """A user-visible EndoEval contract or evaluation error."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EndoEvalError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise EndoEvalError(f"non-finite JSON constant is forbidden: {value}")


def load_json(path: Path) -> Any:
    """Read strict JSON: duplicate keys and non-finite constants are refused."""

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


def canonical_json_bytes(value: object) -> bytes:
    """Serialise one value into its canonical byte form."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def bytes_sha256(data: bytes) -> str:
    """Digest raw bytes."""

    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: object) -> str:
    """Digest one value's canonical byte form."""

    return bytes_sha256(canonical_json_bytes(value))


def file_sha256(path: Path) -> str:
    """Digest one file's bytes in streaming blocks."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise EndoEvalError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Write one document as stable, human-readable JSON."""

    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def safe_relative_path(value: object, *, field: str) -> str:
    """Admit only canonical, strictly relative POSIX paths."""

    if not isinstance(value, str) or not value:
        raise EndoEvalError(f"{field} must be a non-empty relative path")
    if "\x00" in value or "\\" in value:
        raise EndoEvalError(f"{field} must use canonical POSIX separators")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise EndoEvalError(f"{field} contains an empty, dot, or parent component")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise EndoEvalError(f"{field} must remain relative")
    return posix.as_posix()


def resolve_inside(base: Path, relative: str, *, field: str) -> Path:
    """Resolve a relative path and require it to stay inside its root."""

    root = base.resolve()
    candidate = (root / safe_relative_path(relative, field=field)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise EndoEvalError(f"{field} escapes its declared root") from exc
    return candidate


__all__ = [
    "EndoEvalError",
    "bytes_sha256",
    "canonical_json_bytes",
    "canonical_sha256",
    "file_sha256",
    "load_json",
    "resolve_inside",
    "safe_relative_path",
    "write_json",
]
