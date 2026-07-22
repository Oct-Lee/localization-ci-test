#!/usr/bin/env python3
"""Extract SCREAMING_SNAKE string constants from translations*.py modules.

Outputs JSONL records:
  {"file","line","key","locale","text","package"}
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

LOCALE_BY_STEM = {
    "english": "en",
    "chinese": "zh",
    "portuguese": "pt",
}

SCREAMING_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")
TRANSLATIONS_DIR = re.compile(r"(^|/)translations[^/]*/", re.IGNORECASE)


def _join_string(node: ast.AST) -> str | None:
    """Evaluate constant string expressions (literals and implicit concat)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-strings are out of scope for Phase 1
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _join_string(node.left)
        right = _join_string(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    # Implicit string concatenation: ("a" "b") appears as Constant in 3.8+
    # or as a Tuple of Constants in some forms — handle Tuple of strings.
    if isinstance(node, ast.Tuple):
        parts: list[str] = []
        for elt in node.elts:
            part = _join_string(elt)
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    return None


def extract_from_file(path: Path, root: Path) -> list[dict]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    locale = LOCALE_BY_STEM.get(path.stem)
    if locale is None:
        return []

    rel = path.relative_to(root).as_posix()
    package = path.parent.relative_to(root).as_posix()
    records: list[dict] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        key = node.targets[0].id
        if not SCREAMING_SNAKE.match(key):
            continue
        text = _join_string(node.value)
        if text is None:
            continue
        records.append(
            {
                "file": rel,
                "line": node.lineno,
                "key": key,
                "locale": locale,
                "text": text,
                "package": package,
            }
        )
    return records


def discover_files(root: Path, globs: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in globs:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if path.stem not in LOCALE_BY_STEM:
                continue
            # Prefer translations* directories; also allow explicit src/translations
            rel = path.as_posix()
            if TRANSLATIONS_DIR.search(rel) or "translations" in path.parts:
                files.add(path.resolve())
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: cwd)",
    )
    parser.add_argument(
        "--glob",
        action="append",
        dest="globs",
        default=None,
        help="Glob under root (repeatable). "
        "Default: **/translations*/english.py etc.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("out/texts.jsonl"),
        help="Output JSONL path",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    globs = args.globs or [
        "**/translations*/english.py",
        "**/translations*/chinese.py",
        "**/translations*/portuguese.py",
        "**/translations/english.py",
        "**/translations/chinese.py",
        "**/translations/portuguese.py",
    ]

    files = discover_files(root, globs)
    if not files:
        print("No translation files found.", file=sys.stderr)
        return 1

    records: list[dict] = []
    for path in files:
        try:
            records.extend(extract_from_file(path, root))
        except SyntaxError as exc:
            print(f"Syntax error in {path}: {exc}", file=sys.stderr)
            return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Extracted {len(records)} strings from {len(files)} files → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
