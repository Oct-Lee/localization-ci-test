#!/usr/bin/env python3
"""Shared helpers for the Localization Quality Gate."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

# Named placeholders {camera_id} and positional {}
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}|\{\}")
CN_PUNCT_RE = re.compile(r"[，。；：！？]")
LOCALE_LT = {"en": "en-US", "pt": "pt-PT"}
LOCALE_CSPELL = {"en": "en", "pt": "pt"}

# Product names / identifiers replaced before LanguageTool to cut noise.
PRODUCT_TERMS = (
    "ProdX",
    "OptiX",
    "CorteX",
    "Digix",
    "UnitX",
    "V6Flex",
    "V6",
)


def normalize_for_grammar(text: str) -> str:
    """Replace format placeholders and product terms for LanguageTool."""
    text = re.sub(r"\{[A-Za-z_][A-Za-z0-9_]*\}", "Item", text)
    text = text.replace("{}", "Item")
    # Quoted technical identifiers: 'camera_id'
    text = re.sub(r"'[A-Za-z_][A-Za-z0-9_]*'", "'field'", text)
    text = re.sub(r'"[A-Za-z_][A-Za-z0-9_]*"', '"field"', text)
    for term in PRODUCT_TERMS:
        text = text.replace(term, "App")
    # Strip residual Chinese punctuation that confuses EN/PT analyzers
    text = CN_PUNCT_RE.sub(",", text)
    return text


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def placeholders(text: str) -> list[str]:
    """Return placeholder tokens in order, e.g. ['{camera_id}', '{}']."""
    found: list[str] = []
    for match in PLACEHOLDER_RE.finditer(text):
        if match.group(0) == "{}":
            found.append("{}")
        else:
            found.append("{" + match.group(1) + "}")
    return found


def placeholder_set(text: str) -> set[str]:
    return set(placeholders(text))


def gh_annotation(
    severity: str,
    file: str,
    line: int,
    message: str,
) -> None:
    """Emit a GitHub Actions workflow command annotation."""
    # Escape for workflow commands
    safe = (
        message.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
    )
    level = "error" if severity == "error" else "warning"
    print(f"::{level} file={file},line={line}::{safe}")


def group_by_package(
    records: Iterable[dict[str, Any]],
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    """package -> locale -> key -> record"""
    packages: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for record in records:
        pkg = record["package"]
        locale = record["locale"]
        key = record["key"]
        packages.setdefault(pkg, {}).setdefault(locale, {})[key] = record
    return packages
