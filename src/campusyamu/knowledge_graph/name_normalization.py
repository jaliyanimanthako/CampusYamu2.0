"""Shared, auditable name-normalization rules for graph preparation."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_MAPPINGS_PATH = Path(__file__).with_name("name_mappings.json")


class NameNormalizationError(RuntimeError):
    """Raised when the name-mapping contract is missing or inconsistent."""


def load_name_mappings(path: str | Path = DEFAULT_MAPPINGS_PATH) -> dict[str, Any]:
    """Load and minimally validate the authoritative name-mapping file."""

    mapping_path = Path(path).expanduser().resolve()
    if not mapping_path.is_file():
        raise NameNormalizationError(f"Name-mapping file not found: {mapping_path}")
    try:
        mappings = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NameNormalizationError(f"Invalid name-mapping JSON: {exc}") from exc
    if not isinstance(mappings, dict) or mappings.get("schema_version") != 1:
        raise NameNormalizationError("Unsupported name-mapping schema")
    for key in (
        "annotation_suffixes",
        "course_name_overrides_by_code",
        "course_aliases",
        "institution_aliases",
        "protected_course_distinctions",
    ):
        if key not in mappings:
            raise NameNormalizationError(f"Name mappings are missing {key!r}")
    return mappings


def stable_slug(value: str) -> str:
    """Create the stable ASCII slug used in graph entity IDs."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")


def lookup_key(value: str) -> str:
    """Normalize a display name for deterministic entity resolution."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))


def strip_annotations(value: str, mappings: dict[str, Any]) -> str:
    """Remove configured suffix annotations such as ``(New)``."""

    result = value.strip()
    for suffix in mappings["annotation_suffixes"]:
        pattern = rf"\s*{re.escape(str(suffix))}\s*$"
        result = re.sub(pattern, "", result, flags=re.IGNORECASE).strip()
    return result


def canonical_course_label(value: str, mappings: dict[str, Any]) -> str:
    """Resolve a raw course label through explicit aliases and annotations."""

    aliases = mappings["course_aliases"]
    if value in aliases:
        return str(aliases[value])
    stripped = strip_annotations(value, mappings)
    return str(aliases.get(stripped, stripped))


def canonical_course_name(
    course_code: str,
    raw_name: str,
    mappings: dict[str, Any],
) -> str:
    """Return the canonical display name for a course code and raw label."""

    override = mappings["course_name_overrides_by_code"].get(course_code)
    if override is not None:
        return str(override)
    return canonical_course_label(raw_name, mappings)


def institution_definition(
    raw_name: str,
    mappings: dict[str, Any],
) -> dict[str, str | None]:
    """Return canonical institution name, type, and optional parent name."""

    override = mappings["institution_aliases"].get(raw_name)
    if override is None:
        return {
            "canonical_name": raw_name,
            "type": "University",
            "parent_name": None,
        }
    return {
        "canonical_name": str(override["canonical_name"]),
        "type": str(override["type"]),
        "parent_name": (
            str(override["parent_name"])
            if override.get("parent_name") is not None
            else None
        ),
    }
