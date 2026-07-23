#!/usr/bin/env python3
"""Extract user-facing SCREAMING_SNAKE string constants from changed source files.

Scope (default):
  - Any path in the repo (NOT limited to translations/)
  - Supported: *.py module-level NAME = \"...\" constants
  - Locale from known filenames, else inferred from text content

PR / push incremental mode:
  --changed-only --base <sha>  only files changed vs base

Outputs JSONL:
  {"file","line","key","locale","text","package"}
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

SKIP_STEMS = {"__init__"}

SKIP_DIR_PARTS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pants.d",
    "out",
    "dist",
    "build",
    "third_party",
    ".tox",
}

SUPPORTED_SUFFIXES = {".py"}

SCREAMING_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
PT_RE = re.compile(
    r"[ãõáéíóúâêôçÃÕÁÉÍÓÚÂÊÔÇ]|não|configuração|câmera|verifique|por favor",
    re.IGNORECASE,
)


def _join_string(node: ast.AST) -> str | None:
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


def extract_from_file(path: Path, root: Path, *, in_diff: bool = True) -> list[dict]:
    if path.suffix == ".py":
        items = extract_assignments(path)
    else:
        return []
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
            "in_diff": in_diff,
        }
        for lineno, key, text in items
    ]


def sibling_candidate_files(root: Path, changed: list[Path]) -> list[Path]:
    """Include other candidate *.py in the same directories as changed files.

    Needed so consistency can compare placeholders across english/chinese/…
    even when the PR only touches one locale file.
    """
    extra: set[Path] = set()
    for path in changed:
        parent = path.parent
        for sibling in parent.glob("*.py"):
            if is_candidate_file(sibling, root):
                extra.add(sibling.resolve())
    return sorted(extra)


def is_candidate_file(path: Path, root: Path) -> bool:
    """True if path is a supported source file anywhere in the repo."""
    if not path.is_file():
        return False
    if path.suffix not in SUPPORTED_SUFFIXES:
        return False
    if path.stem in SKIP_STEMS:
        return False
    try:
        rel_parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return False
    if any(part in SKIP_DIR_PARTS for part in rel_parts):
        return False
    # Do not extract from the gate's own tooling
    if len(rel_parts) >= 1 and rel_parts[0] in {"scripts"}:
        return False
    return True


def discover_files(root: Path, globs: list[str] | None) -> list[Path]:
    files: set[Path] = set()
    patterns = globs or ["**/*.py"]
    for pattern in patterns:
        for path in root.glob(pattern):
            if is_candidate_file(path, root):
                files.add(path.resolve())
    return sorted(files)


def git_changed_files(root: Path, base: str, head: str = "HEAD") -> list[Path]:
    """Return candidate source files changed between base and head."""
    attempts = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}"],
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head],
    ]
    proc = None
    for cmd in attempts:
        print(f"+ {' '.join(cmd)}", flush=True)
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, check=False
        )
        if proc.returncode == 0:
            break
    if proc is None or proc.returncode != 0:
        err = proc.stderr if proc else "no attempt"
        raise RuntimeError(f"git diff failed against base={base} head={head}: {err}")

    print(proc.stdout)
    files: list[Path] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        path = (root / line).resolve()
        if is_candidate_file(path, root):
            files.append(path)
        else:
            print(f"  (skip non-candidate) {line}")
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--glob", action="append", dest="globs", default=None)
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only extract files changed vs --base (PR/push incremental)",
    )
    parser.add_argument(
        "--base",
        default="",
        help="Git base ref/sha for --changed-only",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Git head ref/sha for --changed-only (default HEAD)",
    )
    parser.add_argument("--files", nargs="*", default=None)
    parser.add_argument("-o", "--output", type=Path, default=Path("out/texts.jsonl"))
    args = parser.parse_args()
    root = args.root.resolve()

    if args.files is not None:
        files = []
        for item in args.files:
            path = Path(item)
            if not path.is_absolute():
                path = root / path
            if is_candidate_file(path, root):
                files.append(path.resolve())
        changed_set = set(files)
        # Same as PR mode: load directory siblings for placeholder consistency.
        files = sibling_candidate_files(root, sorted(changed_set)) or sorted(changed_set)
        print(f"Explicit files (+ same-dir siblings): {len(files)}")
        for path in files:
            mark = "changed" if path in changed_set else "sibling"
            print(f"  - [{mark}] {path.relative_to(root).as_posix()}")
    elif args.changed_only:
        if not args.base:
            print("--changed-only requires --base", file=sys.stderr)
            return 1
        changed = git_changed_files(root, args.base, args.head)
        print(f"Changed candidate files vs {args.base}...{args.head}: {len(changed)}")
        for path in changed:
            print(f"  - {path.relative_to(root).as_posix()}")
        changed_set = set(changed)
        # Pull sibling locale/message modules in the same directories for
        # placeholder consistency, without treating them as "in_diff".
        files = sibling_candidate_files(root, changed)
        if files:
            print(f"With same-directory siblings for consistency: {len(files)}")
            for path in files:
                mark = "changed" if path in changed_set else "sibling"
                print(f"  - [{mark}] {path.relative_to(root).as_posix()}")
    else:
        files = discover_files(root, args.globs)
        changed_set = set(files)

    if not files:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("", encoding="utf-8")
        print("No candidate files to extract; wrote empty catalog.")
        return 0

    records: list[dict] = []
    scanned = 0
    for path in files:
        scanned += 1
        in_diff = path in changed_set
        try:
            extracted = extract_from_file(path, root, in_diff=in_diff)
        except SyntaxError as exc:
            print(f"Syntax error in {path}: {exc}", file=sys.stderr)
            return 1
        if not extracted:
            continue
        locale = extracted[0]["locale"]
        print(
            f"  {path.relative_to(root).as_posix()}: "
            f"{len(extracted)} strings (locale={locale}, in_diff={in_diff})"
        )
        records.extend(extracted)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(
        f"Scanned {scanned} files; extracted {len(records)} strings → {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
