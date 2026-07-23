#!/usr/bin/env python3
"""Cross-locale consistency checks for extracted translation strings.

Error-level findings (exit 1):
  - missing keys vs english baseline
  - placeholder set mismatch across locales
  - Chinese punctuation inside english strings
  - empty / whitespace-only strings
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/check_consistency.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lq_common import (  # noqa: E402
    CN_PUNCT_RE,
    gh_annotation,
    group_by_package,
    load_jsonl,
    placeholder_set,
)


def check_package(pkg: str, locales: dict) -> list[tuple]:
    """Return list of (severity, file, line, message)."""
    findings: list[tuple] = []
    en = locales.get("en", {})

    # Empty / whitespace + Chinese punctuation on every locale record
    for locale, keys in locales.items():
        for key, record in keys.items():
            text = record["text"]
            if not text.strip():
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
                        f"Chinese punctuation in english string for key {key}",
                    )
                )

    # Incremental PR catalogs may contain only zh/pt; skip cross-locale
    # alignment when there is no english baseline in this extract.
    if not en:
        if not findings:
            print(
                f"Package {pkg}: no english strings in catalog; "
                "skipped cross-locale key alignment"
            )
        return findings

    for locale, other in locales.items():
        if locale == "en":
            continue
        # Missing keys in other locale
        for key, en_rec in en.items():
            if key not in other:
                findings.append(
                    (
                        "error",
                        en_rec["file"],
                        en_rec["line"],
                        f"Key {key} missing in {locale} "
                        f"(package {pkg})",
                    )
                )
                continue
            en_ph = placeholder_set(en_rec["text"])
            other_ph = placeholder_set(other[key]["text"])
            if en_ph != other_ph:
                orec = other[key]
                findings.append(
                    (
                        "error",
                        orec["file"],
                        orec["line"],
                        f"Placeholder mismatch for {key}: "
                        f"en={sorted(en_ph)} {locale}={sorted(other_ph)}",
                    )
                )

        # Extra keys in other locale
        for key, orec in other.items():
            if key not in en:
                findings.append(
                    (
                        "error",
                        orec["file"],
                        orec["line"],
                        f"Key {key} present in {locale} but missing in english "
                        f"(package {pkg})",
                    )
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("out/texts.jsonl"),
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Missing input: {args.input}", file=sys.stderr)
        return 1

    records = load_jsonl(args.input)
    packages = group_by_package(records)
    all_findings: list[tuple] = []
    for pkg, locales in packages.items():
        all_findings.extend(check_package(pkg, locales))

    errors = [f for f in all_findings if f[0] == "error"]
    if not all_findings:
        print("Consistency check passed")
        return 0

    print("")
    print("Consistency issues found:")
    print("")
    for severity, file, line, message in all_findings:
        print(f"[{severity.upper()}] {file}:{line}: {message}")
        gh_annotation(severity, file, line, message)

    print("")
    print(f"Total: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
