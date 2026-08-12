#!/usr/bin/env python3
"""Run the private EndoEval product foundation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from endoeval.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
