from __future__ import annotations

import itertools
import re

_MEASUREMENT_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(in|ft)\b")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_measurements(text: str) -> str:
    """Normalize measurement units into canonical `in` and `ft` tokens."""
    normalized = text.lower()
    normalized = (
        normalized.replace("\\\"", '"')
        .replace("\u2033", '"')
        .replace("\u201d", '"')
        .replace("\u201c", '"')
        .replace("\u00b4", "'")
        .replace("\u2032", "'")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
    )

    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:''|\"\")", r"\1 in", normalized)
    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*\"", r"\1 in", normalized)
    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:inch(?:es)?|in\.)\b", r"\1 in", normalized)

    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:feet|foot|ft\.)\b", r"\1 ft", normalized)
    normalized = re.sub(r"\b(\d+(?:\.\d+)?)\s*'", r"\1 ft", normalized)

    normalized = re.sub(r"[,:;|]+", " ", normalized)
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized


def expand_measurement_variants(query: str) -> list[str]:
    """Expand measurement tokens into equivalent symbol and word forms."""
    normalized_query = normalize_measurements(query)
    matches = list(_MEASUREMENT_PATTERN.finditer(normalized_query))
    if not matches:
        return [normalized_query] if normalized_query else []

    chunks: list[str] = []
    options_per_measurement: list[list[str]] = []
    cursor = 0
    for match in matches:
        chunks.append(normalized_query[cursor : match.start()])
        value = match.group(1)
        unit = match.group(2)
        if unit == "in":
            options_per_measurement.append([f"{value} in", f'{value}"', f"{value}''", f"{value} inch"])
        else:
            options_per_measurement.append([f"{value} ft", f"{value}'", f"{value} foot"])
        cursor = match.end()
    chunks.append(normalized_query[cursor:])

    variants: list[str] = []
    seen: set[str] = set()
    for replacement_combo in itertools.product(*options_per_measurement):
        assembled = "".join(part + repl for part, repl in zip(chunks, replacement_combo)) + chunks[-1]
        variant = _WHITESPACE_PATTERN.sub(" ", assembled).strip()
        if variant and variant not in seen:
            seen.add(variant)
            variants.append(variant)

    if normalized_query and normalized_query not in seen:
        variants.insert(0, normalized_query)
    return variants
