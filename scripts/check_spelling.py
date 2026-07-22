#!/usr/bin/env python3
"""Spell-check extracted EN/PT strings with cspell.

Writes one text file per string under out/spell/ so cspell never sees
identifier names. Maps cspell hits back to source file:line annotations.
Chinese (zh) is skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lq_common import gh_annotation, load_jsonl  # noqa: E402

CSPELL_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+)\s+-\s+(?P<msg>.+)$"
)


def resolve_cspell_cmd() -> list[str] | None:
    """Prefer local node_modules/.bin, then PATH, then npx."""
    local = Path("node_modules/.bin/cspell")
    if local.is_file():
        return [str(local.resolve())]
    which = shutil.which("cspell")
    if which:
        return [which]
    if shutil.which("npx"):
        return ["npx", "--no-install", "cspell"]
    return None


def prepare_spell_inputs(
    records: list[dict],
    spell_root: Path,
) -> dict[str, dict]:
    """Write spell input files; return map absolute_path -> record."""
    if spell_root.exists():
        shutil.rmtree(spell_root)
    mapping: dict[str, dict] = {}
    index = 0
    for record in records:
        if record["locale"] not in {"en", "pt"}:
            continue
        index += 1
        locale_dir = spell_root / record["locale"]
        locale_dir.mkdir(parents=True, exist_ok=True)
        name = f"{index:04d}_{record['key']}.txt"
        out_path = (locale_dir / name).resolve()
        out_path.write_text(record["text"] + "\n", encoding="utf-8")
        mapping[str(out_path)] = record
        mapping[out_path.as_posix()] = record
    return mapping


def resolve_record(path: str, mapping: dict[str, dict]) -> dict | None:
    candidates = [
        path,
        Path(path).as_posix(),
    ]
    try:
        resolved = Path(path).resolve()
        candidates.extend([str(resolved), resolved.as_posix()])
    except OSError:
        pass
    for candidate in candidates:
        if candidate in mapping:
            return mapping[candidate]
    # Filename fallback: 0001_CAMERA_NOT_FOUND_ERROR.txt
    stem = Path(path).stem
    for record in mapping.values():
        if stem.endswith("_" + record["key"]) or stem == f"xxxx_{record['key']}":
            return record
        if stem.split("_", 1)[-1] == record["key"]:
            return record
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, default=Path("out/texts.jsonl"))
    parser.add_argument("--spell-dir", type=Path, default=Path("out/spell"))
    parser.add_argument("--config", type=Path, default=Path("cspell.json"))
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Missing input: {args.input}", file=sys.stderr)
        return 1

    records = load_jsonl(args.input)
    spell_root = args.spell_dir.resolve()
    mapping = prepare_spell_inputs(records, spell_root)
    if not mapping:
        print("No EN/PT strings to spell-check")
        return 0

    # Unique records for manifest
    unique = {}
    for key, value in mapping.items():
        unique[key] = {
            "file": value["file"],
            "line": value["line"],
            "key": value["key"],
            "locale": value["locale"],
        }
    (spell_root / "manifest.json").write_text(
        json.dumps(unique, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    cmd = resolve_cspell_cmd()
    if cmd is None:
        print(
            "cspell not found. Install with: npm install -D cspell "
            "or npm install -g cspell",
            file=sys.stderr,
        )
        return 1

    cmd.extend(
        [
            "lint",
            "--no-progress",
            "--no-summary",
            "--unique",
            f"{spell_root}/en/**",
            f"{spell_root}/pt/**",
        ]
    )
    if args.config.is_file():
        cmd.extend(["--config", str(args.config.resolve())])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = (proc.stdout or "") + (proc.stderr or "")
    errors = 0
    seen: set[tuple] = set()

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = CSPELL_LINE.match(line)
        if not match:
            continue
        record = resolve_record(match.group("path"), mapping)
        msg = match.group("msg")
        if record is None:
            print(f"[ERROR] {match.group('path')}: {msg}")
            errors += 1
            continue
        fingerprint = (record["file"], record["line"], msg)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        detail = f"[{record['key']}] {msg}"
        print(f"[ERROR] {record['file']}:{record['line']}: {detail}")
        gh_annotation("error", record["file"], record["line"], detail)
        errors += 1

    if errors == 0 and proc.returncode == 0:
        print("Spell check passed")
        return 0
    if errors == 0 and proc.returncode != 0:
        # Surface raw cspell stderr (e.g. unsupported Node version).
        print(output, file=sys.stderr)
        print("cspell failed without parseable findings", file=sys.stderr)
        return proc.returncode or 1

    print("")
    print(f"Spell check findings: {errors}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
