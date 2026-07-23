#!/usr/bin/env python3
"""Consistency checks for extracted user-facing strings.

Default (PR incremental):
  - empty / whitespace-only strings — only for files in the PR diff
  - Chinese punctuation in English — only for files in the PR diff
  - placeholder mismatch — for any key that appears in a diff file,
    compare all locales present in the catalog (including same-dir siblings)

Optional (--strict-locale-alignment):
  - require every English key to exist in every other locale present
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lq_common import (  # noqa: E402
    CN_PUNCT_RE,
    gh_annotation,
    load_jsonl,
    placeholder_set,
)


def check_records(
    records: list[dict[str, Any]],
    *,
    strict_locale_alignment: bool,
) -> list[tuple]:
    findings: list[tuple] = []

    # Per-record checks: only for strings that are part of the PR/push diff.
    for record in records:
        if record.get("in_diff", True) is False:
            continue
        text = record.get("text", "")
        key = record["key"]
        locale = record["locale"]
        if not str(text).strip():
            findings.append(
                (
                    "error",
                    record["file"],
                    record["line"],
                    f"Empty string for key {key} ({locale})",
                )
            )
        if locale == "en" and CN_PUNCT_RE.search(text):
            findings.append(
                (
                    "error",
                    record["file"],
                    record["line"],
                    f"Chinese punctuation in English string for key {key}",
                )
            )

    # key -> locale -> list[record]
    by_key: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        by_key[record["key"]][record["locale"]].append(record)

    # Keys touched by the diff (or all keys if no in_diff markers)
    touched_keys = {
        r["key"] for r in records if r.get("in_diff", True) is not False
    }

    for key in sorted(touched_keys):
        locales = by_key.get(key, {})
        if len(locales) < 2:
            continue
        if "en" in locales:
            ref_locale = "en"
        else:
            ref_locale = sorted(locales.keys())[0]
        ref_rec = locales[ref_locale][0]
        ref_ph = placeholder_set(ref_rec["text"])

        for locale, recs in locales.items():
            if locale == ref_locale:
                continue
            for rec in recs:
                other_ph = placeholder_set(rec["text"])
                if other_ph != ref_ph:
                    findings.append(
                        (
                            "error",
                            rec["file"],
                            rec["line"],
                            f"Placeholder mismatch for {key}: "
                            f"{ref_locale}={sorted(ref_ph)} "
                            f"{locale}={sorted(other_ph)}",
                        )
                    )

    if not strict_locale_alignment:
        return findings

    packages: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for record in records:
        packages[record["package"]][record["locale"]][record["key"]] = record

    for pkg, locales in packages.items():
        if "en" not in locales:
            continue
        en = locales["en"]
        for locale, other in locales.items():
            if locale == "en":
                continue
            for key, en_rec in en.items():
                if key not in other:
                    findings.append(
                        (
                            "error",
                            en_rec["file"],
                            en_rec["line"],
                            f"Key {key} missing in {locale} (package {pkg})",
                        )
                    )
            for key, orec in other.items():
                if key not in en:
                    findings.append(
                        (
                            "error",
                            orec["file"],
                            orec["line"],
                            f"Key {key} present in {locale} but missing in "
                            f"english (package {pkg})",
                        )
                    )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, default=Path("out/texts.jsonl"))
    parser.add_argument(
        "--strict-locale-alignment",
        action="store_true",
        help="Require full key alignment across locales (for full-catalog runs)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Missing input: {args.input}", file=sys.stderr)
        return 1

    records = load_jsonl(args.input)
    if not records:
        print("Consistency check passed (empty catalog)")
        return 0

    findings = check_records(
        records, strict_locale_alignment=args.strict_locale_alignment
    )
    if not findings:
        mode = "strict" if args.strict_locale_alignment else "incremental"
        print(f"Consistency check passed ({mode} mode)")
        return 0

    print("")
    print("Consistency issues found:")
    print("")
    for severity, file, line, message in findings:
        print(f"[{severity.upper()}] {file}:{line}: {message}")
        gh_annotation(severity, file, line, message)

    print("")
    print(f"Total: {len(findings)} error(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
