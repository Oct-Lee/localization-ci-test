#!/usr/bin/env python3
"""Extract user-facing message strings from changed source files.

Only extracts strings that look like Log / UI / Error / CLI copy — not
arbitrary constants, and not test/tooling files.

Rules:
  - Message catalogs (under *translations* or named english/chinese/portuguese):
    all module-level SCREAMING_SNAKE = \"...\" strings
  - Other *.py files: only keys matching *_ERROR / *_MSG / *_TITLE / ...
  - Skip tests/, test_*.py, scripts/, third_party/, ...
  - Syntax errors are skipped with a warning (do not fail the gate)

PR mode: --changed-only --base <sha> [--head HEAD]
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

SKIP_STEMS = {"__init__", "conftest", "setup", "language"}

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
    "scripts",
    "tests",
    "test",
    "__tests__",
}

SUPPORTED_SUFFIXES = {".py"}

SCREAMING_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")
# User-facing message constant names outside dedicated catalog files.
USER_FACING_KEY = re.compile(
    r"(?:^|_)(?:"
    r"ERROR|ERR|MSG|MESSAGE|TITLE|HINT|DIALOG|LABEL|TEXT|PROMPT|"
    r"WARNING|WARN|INFO|CONFIRMATION|CONFIRM|REMINDER|TIP|TOOLTIP|"
    r"DESCRIPTION|NOTIFICATION|NOTICE|ALERT|BANNER|TOAST|STATUS_TEXT|"
    r"MODE|NAME|BUTTON|MENU|HEADER|FOOTER|PLACEHOLDER|CONTENT|HELP"
    r")$"
)
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


def is_message_catalog(path: Path, root: Path) -> bool:
    """Dedicated i18n / translation modules — extract all SCREAMING_SNAKE."""
    if path.stem.lower() in LOCALE_BY_STEM:
        return True
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        parts = path.parts
    return any("translation" in p.lower() for p in parts)


def is_user_facing_key(key: str, *, catalog: bool) -> bool:
    if not SCREAMING_SNAKE.match(key):
        return False
    if catalog:
        return True
    return bool(USER_FACING_KEY.search(key))


def is_test_path(path: Path, root: Path) -> bool:
    """Skip unit-test trees; allow root demo files like test.py with message constants."""
    stem = path.stem.lower()
    if stem.startswith("test_") or stem.endswith("_test"):
        return True
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        parts = path.parts
    # Only directory segments named tests/test — not a lone test.py at repo root.
    if len(parts) >= 2:
        lowered_dirs = {p.lower() for p in parts[:-1]}
        if lowered_dirs & {"tests", "test", "__tests__", "testing"}:
            return True
    return False


def extract_assignments(
    path: Path, *, catalog: bool
) -> list[tuple[int, str, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    items: list[tuple[int, str, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        key = node.targets[0].id
        if not is_user_facing_key(key, catalog=catalog):
            continue
        text = _join_string(node.value)
        if text is None:
            continue
        items.append((node.lineno, key, text))
    return items


def extract_from_file(path: Path, root: Path, *, in_diff: bool = True) -> list[dict]:
    if path.suffix != ".py":
        return []
    catalog = is_message_catalog(path, root)
    try:
        items = extract_assignments(path, catalog=catalog)
    except SyntaxError as exc:
        # Not a localization finding — do not fail the gate on junk/unparseable files.
        rel = path.relative_to(root).as_posix()
        print(
            f"::notice file={rel},line={exc.lineno or 1}::"
            f"Skip unparseable file (not a spell/grammar finding): {exc.msg}",
            file=sys.stderr,
        )
        print(
            f"Warning: skip {rel} (Python syntax error at line {exc.lineno}: {exc.msg}). "
            f"Fix the file syntax or remove it; LQ gate only checks string constants.",
            file=sys.stderr,
        )
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


def is_candidate_file(path: Path, root: Path) -> bool:
    """True if path might contain user-facing message strings."""
    if not path.is_file():
        return False
    if path.suffix not in SUPPORTED_SUFFIXES:
        return False
    if path.stem in SKIP_STEMS:
        return False
    if is_test_path(path, root):
        return False
    try:
        rel_parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return False
    if any(part in SKIP_DIR_PARTS for part in rel_parts):
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
            print(f"  (skip non-user-facing path) {line}")
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
    parser.add_argument("--base", default="", help="Git base ref/sha")
    parser.add_argument("--head", default="HEAD", help="Git head ref/sha")
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
            else:
                print(f"  (skip non-user-facing path) {item}")
        files = sorted(set(files))
        changed_set = set(files)
    elif args.changed_only:
        if not args.base:
            print("--changed-only requires --base", file=sys.stderr)
            return 1
        changed = git_changed_files(root, args.base, args.head)
        print(f"Changed candidate files vs {args.base}...{args.head}: {len(changed)}")
        for path in changed:
            print(f"  - {path.relative_to(root).as_posix()}")
        files = changed
        changed_set = set(changed)
    else:
        files = discover_files(root, args.globs)
        changed_set = set(files)

    if not files:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("", encoding="utf-8")
        print("No user-facing message files to extract; wrote empty catalog.")
        return 0

    records: list[dict] = []
    scanned = 0
    for path in files:
        scanned += 1
        in_diff = path in changed_set
        extracted = extract_from_file(path, root, in_diff=in_diff)
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
        f"Scanned {scanned} files; extracted {len(records)} user-facing "
        f"strings → {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
