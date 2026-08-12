from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
VERIFY_COMMAND = [sys.executable, "-I", "-S", "-B", "reproduce.py", "verify"]


def _copy_capsule(destination: Path) -> Path:
    target = destination / "capsule"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "build",
            "dist",
        ),
    )
    return target


def _append(relative: str, payload: bytes) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        with (root / relative).open("ab") as handle:
            handle.write(payload)

    return mutate


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _refresh_manifest_entry(root: Path, relative: str) -> None:
    manifest_path = root / "CAPSULE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = (root / relative).read_bytes()
    manifest["files"][relative]["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest["files"][relative]["size"] = len(payload)
    _write_json(manifest_path, manifest)


def _empty_headlines(root: Path) -> None:
    path = root / "records" / "HEADLINES.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["checks"] = []
    _write_json(path, document)


def _add_extra_python(root: Path) -> None:
    (root / "unlisted.py").write_text(
        "raise RuntimeError('must never execute')\n",
        encoding="utf-8",
    )


def _add_declared_extra_file(root: Path) -> None:
    relative = "EXTRA.md"
    payload = b"not part of the frozen Phase-0 surface\n"
    (root / relative).write_bytes(payload)
    manifest_path = root / "CAPSULE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][relative] = {
        "kind": "documentation",
        "mode": "100644",
        "origin": {"type": "authored_private_staging"},
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    _write_json(manifest_path, manifest)


def _wrong_manifest_kind(root: Path) -> None:
    path = root / "CAPSULE_MANIFEST.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["files"]["README.md"]["kind"] = "test"
    _write_json(path, document)


def _remove_source_ref(root: Path) -> None:
    path = root / "SOURCE_REFS.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["materialised_files"].pop(
        "src/benchmark_integrity/comparability.py"
    )
    _write_json(path, document)
    _refresh_manifest_entry(root, "SOURCE_REFS.json")


def _disagree_source_ref(root: Path) -> None:
    path = root / "SOURCE_REFS.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["materialised_files"][
        "src/benchmark_integrity/comparability.py"
    ]["source_ref"] = "f" * 40
    _write_json(path, document)
    _refresh_manifest_entry(root, "SOURCE_REFS.json")


def _duplicate_manifest_key(root: Path) -> None:
    path = root / "CAPSULE_MANIFEST.json"
    text = path.read_text(encoding="utf-8")
    marker = '  "files": {\n'
    duplicate = '    ".gitattributes": {},\n'
    path.write_text(text.replace(marker, marker + duplicate, 1), encoding="utf-8")


def _unsafe_manifest_path(value: str) -> Callable[[Path], None]:
    def mutate(root: Path) -> None:
        path = root / "CAPSULE_MANIFEST.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["files"][value] = {
            "kind": "documentation",
            "mode": "100644",
            "origin": {"type": "authored_private_staging"},
            "sha256": "0" * 64,
            "size": 0,
        }
        _write_json(path, document)

    return mutate


def _add_unchecked_bytecode(root: Path) -> None:
    marker = root / "BYTECODE_EXECUTED"
    with tempfile.TemporaryDirectory() as directory:
        malicious = Path(directory) / "comparability.py"
        malicious.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n",
            encoding="utf-8",
        )
        source = root / "src" / "benchmark_integrity" / "comparability.py"
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(
            str(malicious),
            cfile=str(cache),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )


class CapsuleTamperTests(unittest.TestCase):
    def _assert_fails_closed(
        self,
        root: Path,
        *,
        marker_must_not_exist: Path | None = None,
    ) -> None:
        completed = subprocess.run(
            VERIFY_COMMAND,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotIn('"status": "pass"', completed.stdout + completed.stderr)
        failure = json.loads(completed.stderr)
        self.assertEqual(failure["status"], "fail")
        if marker_must_not_exist is not None:
            self.assertFalse(marker_must_not_exist.exists())

    def test_isolated_tampering_fails_closed(self) -> None:
        cases: dict[str, Callable[[Path], None]] = {
            "literature-result": _append(
                "records/paper3_literature_audit_result.json",
                b"\n",
            ),
            "package-init": _append(
                "src/benchmark_integrity/__init__.py",
                b"\nTAMPERED = True\n",
            ),
            "verifier": _append("reproduce.py", b"\n# tampered\n"),
            "headline-policy": _empty_headlines,
            "extra-python": _add_extra_python,
            "declared-extra-file": _add_declared_extra_file,
            "wrong-manifest-kind": _wrong_manifest_kind,
            "source-ref-omission": _remove_source_ref,
            "source-ref-disagreement": _disagree_source_ref,
            "duplicate-manifest-key": _duplicate_manifest_key,
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = _copy_capsule(Path(directory))
                mutate(root)
                self._assert_fails_closed(root)

    def test_unsafe_manifest_paths_fail_closed(self) -> None:
        paths = (
            r"..\outside",
            r"C:\outside",
            r"\\server\share\outside",
            "a/../outside",
            "/absolute/outside",
            "a//outside",
        )
        for value in paths:
            with self.subTest(path=value), tempfile.TemporaryDirectory() as directory:
                root = _copy_capsule(Path(directory))
                _unsafe_manifest_path(value)(root)
                self._assert_fails_closed(root)

    def test_unchecked_bytecode_is_rejected_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _copy_capsule(Path(directory))
            _add_unchecked_bytecode(root)
            self._assert_fails_closed(
                root,
                marker_must_not_exist=root / "BYTECODE_EXECUTED",
            )


if __name__ == "__main__":
    unittest.main()
