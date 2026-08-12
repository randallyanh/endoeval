from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


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


def _empty_headlines(root: Path) -> None:
    path = root / "records" / "HEADLINES.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["checks"] = []
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _add_extra_python(root: Path) -> None:
    (root / "unlisted.py").write_text("raise RuntimeError('must never execute')\n", encoding="utf-8")


class CapsuleTamperTests(unittest.TestCase):
    def test_isolated_tampering_fails_closed(self) -> None:
        cases: dict[str, Callable[[Path], None]] = {
            "literature-result": _append(
                "records/paper3_literature_audit_result.json", b"\n"
            ),
            "package-init": _append(
                "src/benchmark_integrity/__init__.py", b"\nTAMPERED = True\n"
            ),
            "verifier": _append("reproduce.py", b"\n# tampered\n"),
            "headline-policy": _empty_headlines,
            "extra-python": _add_extra_python,
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = _copy_capsule(Path(directory))
                mutate(root)
                completed = subprocess.run(
                    [sys.executable, "-I", "reproduce.py", "verify"],
                    cwd=root,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertNotIn('"status": "pass"', completed.stdout + completed.stderr)
                failure = json.loads(completed.stderr)
                self.assertEqual(failure["status"], "fail")


if __name__ == "__main__":
    unittest.main()
