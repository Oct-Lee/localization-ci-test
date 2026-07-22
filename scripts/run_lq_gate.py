#!/usr/bin/env python3
"""Orchestrate Localization Quality Gate steps.

Steps: extract → consistency → spelling → grammar
Exit non-zero if any Error-level step fails.
Grammar is Warning unless LQ_STRICT_GRAMMAR=1.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent


def run_step(name: str, cmd: list[str], cwd: Path) -> int:
    print("")
    print("=" * 60)
    print(f"STEP: {name}")
    print("=" * 60)
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=cwd, check=False)
    print(f"→ exit {proc.returncode}", flush=True)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--skip-grammar", action="store_true")
    parser.add_argument("--skip-spell", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "out" / "texts.jsonl"
    py = sys.executable

    codes: dict[str, int] = {}

    codes["extract"] = run_step(
        "extract",
        [py, str(SCRIPTS / "extract_messages.py"), "--root", str(root), "-o", str(out)],
        root,
    )
    if codes["extract"] != 0:
        return codes["extract"]

    codes["consistency"] = run_step(
        "consistency",
        [py, str(SCRIPTS / "check_consistency.py"), "-i", str(out)],
        root,
    )

    if not args.skip_spell:
        codes["spelling"] = run_step(
            "spelling",
            [py, str(SCRIPTS / "check_spelling.py"), "-i", str(out)],
            root,
        )
    else:
        codes["spelling"] = 0

    if not args.skip_grammar:
        env_note = os.environ.get("LQ_STRICT_GRAMMAR", "")
        print(f"(LQ_STRICT_GRAMMAR={env_note!r})")
        codes["grammar"] = run_step(
            "grammar",
            [py, str(SCRIPTS / "check_grammar.py"), "-i", str(out)],
            root,
        )
    else:
        codes["grammar"] = 0

    print("")
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    failed = False
    for name, code in codes.items():
        status = "PASS" if code == 0 else "FAIL"
        print(f"  {name}: {status} ({code})")
        if code != 0:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
