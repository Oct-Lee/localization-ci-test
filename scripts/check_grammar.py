#!/usr/bin/env python3
"""Run LanguageTool grammar checks on extracted EN/PT strings.

Findings are Warning by default (exit 0). Set LQ_STRICT_GRAMMAR=1 to fail.
Chinese (zh) is skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lq_common import (  # noqa: E402
    LOCALE_LT,
    gh_annotation,
    load_jsonl,
    normalize_for_grammar,
)


def load_ignore_rules(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    rules: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rules.add(line)
    return rules


def wait_ready(url: str, timeout_s: int = 120) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url.replace("/v2/check", "/v2/languages"))
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2)
    raise RuntimeError(f"LanguageTool not ready: {last_err}")


def check_text(
    endpoint: str,
    language: str,
    text: str,
    ignore_rules: set[str],
) -> list[dict]:
    if not text.strip():
        return []
    data = urllib.parse.urlencode(
        {
            "language": language,
            "text": text,
            "enabledOnly": "false",
        }
    ).encode("utf-8")
    request = urllib.request.Request(endpoint, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))
    matches = []
    for item in result.get("matches", []):
        rule = (item.get("rule") or {}).get("id", "")
        category = ((item.get("rule") or {}).get("category") or {}).get("id", "")
        # Keep TYPOS/MORFOLOGIK — spelling mistakes must surface even if
        # cspell is misconfigured; duplicate reports with cspell are OK.
        # Drop pure style / preference suggestions by default
        if category.upper() in {
            "STYLE",
            "REDUNDANCY",
            "CASING",
            "TYPOGRAPHY",
            "MISC",
        }:
            continue
        if rule in ignore_rules or rule.startswith("STYLE_"):
            continue
        # PT orthography reform preferences are noisy for BR product copy
        if rule.startswith("PT_AGREEMENT_REPLACE_"):
            continue
        matches.append(item)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, default=Path("out/texts.jsonl"))
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("LQ_LT_ENDPOINT", "http://localhost:8010/v2/check"),
    )
    parser.add_argument(
        "--ignore-rules",
        type=Path,
        default=Path("languagetool-ignore.txt"),
    )
    args = parser.parse_args()
    strict = os.environ.get("LQ_STRICT_GRAMMAR", "").strip() in {"1", "true", "yes"}

    if not args.input.is_file():
        print(f"Missing input: {args.input}", file=sys.stderr)
        return 1

    ignore_rules = load_ignore_rules(args.ignore_rules)
    wait_ready(args.endpoint)

    records = load_jsonl(args.input)
    findings = 0

    for record in records:
        locale = record["locale"]
        if locale not in LOCALE_LT:
            continue
        language = LOCALE_LT[locale]
        check_text_norm = normalize_for_grammar(record["text"])
        try:
            matches = check_text(
                args.endpoint, language, check_text_norm, ignore_rules
            )
        except urllib.error.URLError as exc:
            print(f"LanguageTool request failed: {exc}", file=sys.stderr)
            return 1

        for item in matches:
            findings += 1
            offset = item.get("offset", 0)
            length = item.get("length", 0)
            wrong = check_text_norm[offset : offset + length]
            rule = (item.get("rule") or {}).get("id", "")
            msg = item.get("message", "")
            replacements = [
                r.get("value") for r in (item.get("replacements") or [])[:5]
            ]
            detail = (
                f"[{record['key']}] {msg} | text={wrong!r} | rule={rule}"
            )
            if replacements:
                detail += f" | suggestions={replacements}"
            severity = "error" if strict else "warning"
            print(f"[{severity.upper()}] {record['file']}:{record['line']}: {detail}")
            gh_annotation(severity, record["file"], record["line"], detail)

    if findings == 0:
        print("LanguageTool check passed (no grammar findings)")
        return 0

    print("")
    print(f"LanguageTool findings: {findings} (strict={strict})")
    if strict:
        return 1
    print("Grammar findings treated as warnings (set LQ_STRICT_GRAMMAR=1 to fail)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
