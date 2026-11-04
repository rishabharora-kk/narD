"""Deterministic, provenance-preserving identifier extraction.

Strict IDs intentionally trade recall for precision. No identity is inferred
from topical similarity, organization names or an LLM alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Identifier:
    kind: str
    canonical: str
    span: tuple[int, int]


_PATTERNS = {
    "cin": re.compile(r"(?<![A-Za-z0-9])[UL][0-9]{5}[A-Za-z]{2}[0-9]{4}PLC[0-9]{6}(?![A-Za-z0-9])", re.I),
    "patent_wo": re.compile(r"(?<![A-Za-z0-9])WO[ /-]?(20[0-9]{2})[ /-]?([0-9]{6})(?:[ /-]?[A-C][0-9]?)?(?![A-Za-z0-9])", re.I),
    "doi": re.compile(r"(?<![A-Za-z0-9])10[.]\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I),
}


def extract_identifiers(text: str) -> list[Identifier]:
    found: set[Identifier] = set()
    for kind, pattern in _PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0).rstrip(".,;)")
            if kind == "patent_wo":
                value = "WO" + match.group(1) + match.group(2)
            else:
                value = value.upper() if kind == "cin" else value.lower()
            found.add(Identifier(kind=kind, canonical=value, span=(match.start(), match.start() + len(match.group(0)))))
    return sorted(found)


def compatible_join(left: list[Identifier], right: list[Identifier]) -> list[tuple[str, str]]:
    """Exact canonical matches only. Requires separate source independence checks."""
    a = {(x.kind, x.canonical) for x in left}
    b = {(x.kind, x.canonical) for x in right}
    return sorted(a & b)
