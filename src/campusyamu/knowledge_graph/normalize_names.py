"""Normalize graph entity names and build collision-free lookup indexes."""

from __future__ import annotations

import argparse
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Sequence

from .name_normalization import (
    DEFAULT_MAPPINGS_PATH,
    NameNormalizationError,
    load_name_mappings,
    lookup_key,
    stable_slug,
)
from .source_registry import PROJECT_ROOT, file_sha256


SCHEMA_VERSION = 1
DEFAULT_INPUT = Path("data/processed/knowledge_graph/graph_data.json")
DEFAULT_OUTPUT = Path("data/processed/knowledge_graph/normalized_graph_data.json")
DEFAULT_REPORT = Path("data/processed/knowledge_graph/normalization_report.json")


class GraphNormalizationError(RuntimeError):
    """Raised when names or stable identifiers cannot be normalized safely."""


def _require_records(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise GraphNormalizationError(f"Graph data field {key!r} must be a list")
    return value


def _records_by_id(
    records: Iterable[dict[str, Any]],
    entity_type: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = str(record.get("id", ""))
        if not record_id:
            raise GraphNormalizationError(f"{entity_type} record has no ID")
        if record_id in result:
            raise GraphNormalizationError(
                f"Duplicate {entity_type} ID during normalization: {record_id}"
            )
        result[record_id] = record
    return result


def _normalize_named_records(
    records: list[dict[str, Any]],
    entity_type: str,
) -> dict[str, str]:
    """Add normalized keys and return a collision-free alias lookup index."""

    lookup: dict[str, str] = {}
    for record in records:
        record_id = str(record["id"])
        name = str(record.get("name", "")).strip()
        if not name:
            raise GraphNormalizationError(f"{entity_type} {record_id} has no name")
        aliases = record.get("aliases", [])
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise GraphNormalizationError(
                f"{entity_type} {record_id} has invalid aliases"
            )
        aliases = sorted(set(aliases) - {name})
        record["aliases"] = aliases
        record["normalized_name"] = lookup_key(name)
        search_keys = sorted({lookup_key(value) for value in [name, *aliases]})
        if not all(search_keys):
            raise GraphNormalizationError(
                f"{entity_type} {record_id} produced an empty search key"
            )
        record["search_keys"] = search_keys
        for key in search_keys:
            existing = lookup.get(key)
            if existing is not None and existing != record_id:
                raise GraphNormalizationError(
                    f"{entity_type} lookup collision for {key!r}: "
                    f"{existing} and {record_id}"
                )
            lookup[key] = record_id
    return dict(sorted(lookup.items()))


def _validate_mapping_coverage(
    courses: list[dict[str, Any]],
    institutions: list[dict[str, Any]],
    mappings: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    courses_by_name = {str(course["name"]): course for course in courses}
    institution_by_name = {
        str(institution["name"]): institution for institution in institutions
    }

    course_applications: list[dict[str, str]] = []
    for alias, canonical_name in mappings["course_aliases"].items():
        course = courses_by_name.get(str(canonical_name))
        if course is None:
            raise GraphNormalizationError(
                f"Course alias {alias!r} targets unknown canonical name "
                f"{canonical_name!r}"
            )
        if alias != canonical_name and alias not in course["aliases"]:
            raise GraphNormalizationError(
                f"Configured course alias {alias!r} was not found in parsed data"
            )
        course_applications.append(
            {
                "alias": str(alias),
                "canonical_name": str(canonical_name),
                "entity_id": str(course["id"]),
            }
        )

    institution_applications: list[dict[str, str]] = []
    for alias, definition in mappings["institution_aliases"].items():
        canonical_name = str(definition["canonical_name"])
        institution = institution_by_name.get(canonical_name)
        if institution is None:
            raise GraphNormalizationError(
                f"Institution alias {alias!r} targets unknown canonical name "
                f"{canonical_name!r}"
            )
        if alias != canonical_name and alias not in institution["aliases"]:
            raise GraphNormalizationError(
                f"Configured institution alias {alias!r} was not found in parsed data"
            )
        expected_type = str(definition["type"])
        if institution["type"] != expected_type:
            raise GraphNormalizationError(
                f"Institution {canonical_name!r} has type {institution['type']!r}; "
                f"expected {expected_type!r}"
            )
        institution_applications.append(
            {
                "alias": str(alias),
                "canonical_name": canonical_name,
                "entity_id": str(institution["id"]),
            }
        )
    return course_applications, institution_applications


def _validate_stable_ids(
    data: dict[str, Any],
    courses_by_id: dict[str, dict[str, Any]],
    institutions_by_id: dict[str, dict[str, Any]],
) -> None:
    for course in courses_by_id.values():
        expected = f"course:{course['code']}"
        if course["id"] != expected:
            raise GraphNormalizationError(
                f"Unstable course ID {course['id']!r}; expected {expected!r}"
            )

    for institution in institutions_by_id.values():
        expected = f"institution:{stable_slug(str(institution['name']))}"
        if institution["id"] != expected:
            raise GraphNormalizationError(
                f"Unstable institution ID {institution['id']!r}; expected {expected!r}"
            )
        parent_id = institution.get("parent_id")
        if parent_id is not None and parent_id not in institutions_by_id:
            raise GraphNormalizationError(
                f"Institution {institution['id']} has unknown parent {parent_id}"
            )

    offerings = _require_records(data, "course_offerings")
    offerings_by_id = _records_by_id(offerings, "course offering")
    for offering in offerings:
        course = courses_by_id.get(str(offering.get("course_id")))
        institution = institutions_by_id.get(str(offering.get("institution_id")))
        if course is None or institution is None:
            raise GraphNormalizationError(
                f"Offering {offering['id']} has an unknown course or institution"
            )
        expected = (
            f"offering:{course['code']}:"
            f"{institution['id'].removeprefix('institution:')}"
        )
        if offering["id"] != expected:
            raise GraphNormalizationError(
                f"Unstable offering ID {offering['id']!r}; expected {expected!r}"
            )

    years = _records_by_id(_require_records(data, "academic_years"), "academic year")
    uni_codes = _require_records(data, "uni_codes")
    uni_codes_by_id = _records_by_id(uni_codes, "Uni-Code")
    for uni_code in uni_codes:
        year_id = str(uni_code.get("academic_year_id"))
        if year_id not in years:
            raise GraphNormalizationError(
                f"Uni-Code {uni_code['id']} has unknown academic year {year_id}"
            )
        if str(uni_code.get("offering_id")) not in offerings_by_id:
            raise GraphNormalizationError(
                f"Uni-Code {uni_code['id']} has an unknown offering"
            )
        year_key = year_id.removeprefix("academic-year:")
        expected = f"unicode:{year_key}:{uni_code['code']}"
        if uni_code["id"] != expected:
            raise GraphNormalizationError(
                f"Unstable Uni-Code ID {uni_code['id']!r}; expected {expected!r}"
            )

    for offering in offerings:
        if str(offering.get("uni_code_id")) not in uni_codes_by_id:
            raise GraphNormalizationError(
                f"Offering {offering['id']} has an unknown Uni-Code"
            )


def _validate_protected_distinctions(
    courses_by_id: dict[str, dict[str, Any]],
    mappings: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for rule in mappings["protected_course_distinctions"]:
        course_ids = [str(value) for value in rule["course_ids"]]
        if len(course_ids) < 2:
            raise GraphNormalizationError(
                "Protected course distinction must name at least two courses"
            )
        courses = []
        for course_id in course_ids:
            course = courses_by_id.get(course_id)
            if course is None:
                raise GraphNormalizationError(
                    f"Protected distinction references unknown course {course_id}"
                )
            courses.append(course)
        keys = [str(course["normalized_name"]) for course in courses]
        if len(set(keys)) != len(keys):
            raise GraphNormalizationError(
                f"Protected courses normalize to the same name: {course_ids}"
            )
        results.append(
            {
                "course_ids": course_ids,
                "normalized_names": keys,
                "reason": str(rule["reason"]),
                "status": "distinct",
            }
        )
    return results


def normalize_graph_data(
    graph_data: dict[str, Any],
    mappings: dict[str, Any],
    *,
    input_checksum: str | None = None,
    mapping_checksum: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize names, validate stable IDs, and return data plus audit report."""

    if graph_data.get("generation_stage") != "deterministic_table_parsing":
        raise GraphNormalizationError(
            "Expected graph data from deterministic_table_parsing"
        )
    normalized = deepcopy(graph_data)
    courses = _require_records(normalized, "courses")
    institutions = _require_records(normalized, "institutions")
    subjects = _require_records(normalized, "subjects")

    course_lookup = _normalize_named_records(courses, "course")
    institution_lookup = _normalize_named_records(institutions, "institution")
    subject_lookup = _normalize_named_records(subjects, "subject")

    courses_by_id = _records_by_id(courses, "course")
    institutions_by_id = _records_by_id(institutions, "institution")
    _validate_stable_ids(normalized, courses_by_id, institutions_by_id)
    course_aliases, institution_aliases = _validate_mapping_coverage(
        courses, institutions, mappings
    )
    protected = _validate_protected_distinctions(courses_by_id, mappings)

    uni_codes = _require_records(normalized, "uni_codes")
    uni_codes_by_id = _records_by_id(uni_codes, "Uni-Code")
    unicode_lookup: dict[str, str] = {}
    for record in uni_codes:
        code = str(record["code"])
        key = lookup_key(code)
        if key in unicode_lookup and unicode_lookup[key] != record["id"]:
            raise GraphNormalizationError(f"Uni-Code lookup collision for {code}")
        record["normalized_code"] = key
        record["search_keys"] = [key]
        unicode_lookup[key] = str(record["id"])

    offering_lookup: dict[str, str] = {}
    for offering in _require_records(normalized, "course_offerings"):
        course = courses_by_id[str(offering["course_id"])]
        institution = institutions_by_id[str(offering["institution_id"])]
        uni_code = uni_codes_by_id[str(offering["uni_code_id"])]
        combined_keys = {
            f"{course_key}::{institution_key}"
            for course_key in course["search_keys"]
            for institution_key in institution["search_keys"]
        }
        combined_keys.add(str(uni_code["normalized_code"]))
        search_keys = sorted(combined_keys)
        offering["resolution_key"] = (
            f"{course['normalized_name']}::{institution['normalized_name']}"
        )
        offering["search_keys"] = search_keys
        offering["zscore_lookup"]["normalized_course"] = course[
            "normalized_name"
        ]
        offering["zscore_lookup"]["normalized_institution"] = institution[
            "normalized_name"
        ]
        for key in search_keys:
            existing = offering_lookup.get(key)
            if existing is not None and existing != offering["id"]:
                raise GraphNormalizationError(
                    f"Course-offering lookup collision for {key!r}: "
                    f"{existing} and {offering['id']}"
                )
            offering_lookup[key] = str(offering["id"])

    normalized["input_generation_stage"] = normalized["generation_stage"]
    normalized["generation_stage"] = "name_normalization"
    normalized["normalization"] = {
        "schema_version": SCHEMA_VERSION,
        "mapping_schema_version": mappings["schema_version"],
        "mapping_checksum": mapping_checksum,
        "status": "passed",
    }
    normalized["entity_resolution"] = {
        "courses": course_lookup,
        "institutions": institution_lookup,
        "subjects": subject_lookup,
        "uni_codes": dict(sorted(unicode_lookup.items())),
        "course_offerings": dict(sorted(offering_lookup.items())),
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": normalized["dataset"]["id"],
        "status": "passed",
        "input": {
            "generation_stage": normalized["input_generation_stage"],
            "checksum": input_checksum,
        },
        "mapping": {
            "schema_version": mappings["schema_version"],
            "checksum": mapping_checksum,
        },
        "counts": {
            "courses": len(courses),
            "course_aliases": sum(len(item["aliases"]) for item in courses),
            "course_lookup_keys": len(course_lookup),
            "institutions": len(institutions),
            "institution_aliases": sum(
                len(item["aliases"]) for item in institutions
            ),
            "institution_lookup_keys": len(institution_lookup),
            "course_offering_lookup_keys": len(offering_lookup),
        },
        "course_alias_applications": course_aliases,
        "institution_alias_applications": institution_aliases,
        "protected_course_distinctions": protected,
        "collisions": [],
        "unresolved_aliases": [],
        "stable_id_validation": "passed",
    }
    return normalized, report


def _load_json_object(path: Path, description: str) -> dict[str, Any]:
    if not path.is_file():
        raise GraphNormalizationError(f"{description} not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GraphNormalizationError(f"Invalid {description} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise GraphNormalizationError(f"{description} root must be a JSON object")
    return value


def _write_json(value: dict[str, Any], output_path: Path) -> Path:
    output = output_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_name = temporary_file.name
        Path(temporary_name).replace(output)
    finally:
        if temporary_name is not None:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize CampusYamu graph names and stable identifiers."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate normalization without writing output files.",
    )
    return parser


def _resolve(root: Path, path: Path) -> Path:
    return path.expanduser().resolve() if path.is_absolute() else (root / path).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.project_root.expanduser().resolve()
    input_path = _resolve(root, args.input)
    mapping_path = _resolve(root, args.mappings)
    output_path = _resolve(root, args.output)
    report_path = _resolve(root, args.report)
    try:
        graph_data = _load_json_object(input_path, "graph data")
        mappings = load_name_mappings(mapping_path)
        normalized, report = normalize_graph_data(
            graph_data,
            mappings,
            input_checksum=file_sha256(input_path),
            mapping_checksum=file_sha256(mapping_path),
        )
        if args.check_only:
            print(
                f"Validated {report['counts']['courses']} course names and "
                f"{report['counts']['institutions']} institution names; "
                "no collisions found."
            )
            return 0
        written_output = _write_json(normalized, output_path)
        written_report = _write_json(report, report_path)
        print(f"Normalized graph data written to {written_output}.")
        print(f"Normalization report written to {written_report}.")
        return 0
    except (OSError, UnicodeError, GraphNormalizationError, NameNormalizationError) as exc:
        print(f"Name normalization failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
