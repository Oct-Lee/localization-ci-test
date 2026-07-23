#!/usr/bin/env python3
"""Extract SCREAMING_SNAKE string constants from translation modules.

Discovers *.py under translations*/ (not only english/chinese/portuguese.py).
Locale is taken from known filenames, else inferred from string content.

Outputs JSONL records:
  {"file","line","key","locale","text","package"}

PR mode:
  --changed-only --base <sha>  only extract from files changed vs base
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

LOCALE_BY_STEM = {
    "english": "en",
    "chinese": "zh",
    "portuguese": "pt",
    "en": "en",
    "zh": "zh",
    "pt": "pt",
}

SKIP_STEMS = {
    "__init__",
    "language",
}

SCREAMING_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# Common Portuguese orthography markers
PT_RE = re.compile(
    r"[ãõáéíóúâêôçÃÕÁÉÍÓÚÂÊÔÇ]|não|configuração|câmera|verifique|por favor",
    re.IGNORECASE,
)


def _join_string(node: ast.AST) -> str | None:
    """Evaluate constant string expressions (literals and implicit concat)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _join_string(node.left)
        right = _join_string(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.Tuple):
        parts: list[str] = []
        for elt in node.elts:
            part = _join_string(elt)
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    return None


def infer_locale(stem: str, texts: list[str]) -> str:
    """Map filename or content to locale code."""
    known = LOCALE_BY_STEM.get(stem.lower())
    if known:
        return known
    sample = "\n".join(texts)
    if CJK_RE.search(sample):
        return "zh"
    if PT_RE.search(sample):
        return "pt"
    return "en"


def extract_assignments(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (lineno, key, text)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    items: list[tuple[int, str, str]] = []
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
        items.append((node.lineno, key, text))
    return items


def extract_from_file(path: Path, root: Path) -> list[dict]:
    items = extract_assignments(path)
    if not items:
        return []
    texts = [t for _, _, t in items]
    locale = infer_locale(path.stem, texts)
    rel = path.relative_to(root).as_posix()
    package = path.parent.relative_to(root).as_posix()
    return [
        {
            "file": rel,
            "line": lineno,
            "key": key,
            "locale": locale,
            "text": text,
            "package": package,
        }
        for lineno, key, text in items
    ]


def is_translation_py(path: Path, root: Path) -> bool:
    if path.suffix != ".py" or not path.is_file():
        return False
    if path.stem in SKIP_STEMS:
        return False
    try:
        rel_parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        rel_parts = path.parts
    return any(p.startswith("translations") for p in rel_parts)


def discover_files(root: Path, globs: list[str] | None) -> list[Path]:
    files: set[Path] = set()
    patterns = globs or [
        "**/translations*/**/*.py",
        "**/translations/**/*.py",
    ]
    for pattern in patterns:
        for path in root.glob(pattern):
            if is_translation_py(path, root):
                files.add(path.resolve())
    return sorted(files)


def changed_translation_files(root: Path, base: str) -> list[Path]:
    """Return translation *.py files changed vs git base ref."""
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"]
    proc = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # Fallback for shallow / first push
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}", "HEAD"]
        proc = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"git diff failed against base={base}")

    files: list[Path] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        path = (root / line).resolve()
        if is_translation_py(path, root):
            files.append(path)
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--glob",
        action="append",
        dest="globs",
        default=None,
        help="Glob under root (repeatable)",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only extract files changed vs --base (PR incremental mode)",
    )
    parser.add_argument(
        "--base",
        default="",
        help="Git base ref/sha for --changed-only (e.g. origin/main or PR base sha)",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Explicit file paths to extract (repo-relative or absolute)",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("out/texts.jsonl"))
    args = parser.parse_args()
    root = args.root.resolve()

    if args.files:
        files = []
        for item in args.files:
            path = Path(item)
            if not path.is_absolute():
                path = root / path
            if is_translation_py(path, root):
                files.append(path.resolve())
        files = sorted(set(files))
    elif args.changed_only:
        if not args.base:
            print("--changed-only requires --base", file=sys.stderr)
            return 1
        files = changed_translation_files(root, args.base)
        print(f"Changed translation files vs {args.base}: {len(files)}")
        for path in files:
            print(f"  - {path.relative_to(root).as_posix()}")
    else:
        files = discover_files(root, args.globs)

    if not files:
        # PR with no translation file changes: empty catalog, checks pass.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("", encoding="utf-8")
        print("No translation files to extract; wrote empty catalog.")
        return 0

    records: list[dict] = []
    for path in files:
        try:
            extracted = extract_from_file(path, root)
        except SyntaxError as exc:
            print(f"Syntax error in {path}: {exc}", file=sys.stderr)
            return 1
        if not extracted:
            print(
                f"Warning: no SCREAMING_SNAKE strings in "
                f"{path.relative_to(root).as_posix()}",
                file=sys.stderr,
            )
            continue
        locale = extracted[0]["locale"]
        print(
            f"  {path.relative_to(root).as_posix()}: "
            f"{len(extracted)} strings (locale={locale})"
        )
        records.extend(extracted)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Extracted {len(records)} strings from {len(files)} files → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
