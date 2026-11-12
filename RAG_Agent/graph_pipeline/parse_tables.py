"""Parse registered handbook tables into canonical graph-ready JSON."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .name_normalization import (
    NameNormalizationError,
    canonical_course_label,
    canonical_course_name,
    institution_definition,
    load_name_mappings,
    stable_slug,
)
from .source_registry import (
    ACADEMIC_YEAR,
    DATASET_ID,
    PROJECT_ROOT,
    SourceRegistrationError,
    file_sha256,
)


SCHEMA_VERSION = 1
DEFAULT_REGISTRY = Path("RAG_Agent/generated/source_registry.json")
DEFAULT_OUTPUT = Path("RAG_Agent/generated/graph_data.json")

UNI_CODE_SOURCE_ID = "uni-code-assignments"
REQUIREMENTS_SOURCE_ID = "ol-and-aptitude-requirements"
INTAKE_SOURCE_ID = "intake-distribution"

UNI_CODE_HEADING = "## “Uni-Codes” Assigned for Each Course of Study of University"
OL_HEADING = "### O/L Requirement Mapping"
APTITUDE_HEADING = "### Practical / Aptitude Test Mapping"
ANNEX_A_HEADING = "## Annex (a) — Places Available for Admission"
ANNEX_B_HEADING = (
    "## Annex (b) — Distribution of the Total Number of Places Proposed "
    "for University Admission"
)

SUBJECT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("Sinhala Language & Literature", "Sinhala Language and Literature"),
    ("English", "English"),
    ("Mathematics", "Mathematics"),
    ("Science", "Science"),
    ("Tamil Language & Literature", "Tamil Language and Literature"),
)

NAME_MAPPINGS = load_name_mappings()


class TableParseError(RuntimeError):
    """Raised when registered table data cannot be resolved unambiguously."""


@dataclass(frozen=True)
class MarkdownRow:
    """One Markdown table row with its source location."""

    values: dict[str, str]
    line_number: int
    row_number: int


def _clean_cell(value: str) -> str:
    return value.strip().replace("**", "").strip()


def _split_row(line: str) -> list[str]:
    return [_clean_cell(value) for value in line.strip().strip("|").split("|")]


def _is_separator(values: Sequence[str]) -> bool:
    return bool(values) and all(re.fullmatch(r":?-{3,}:?", value) for value in values)


def _find_heading(lines: Sequence[str], heading: str) -> int:
    try:
        return lines.index(heading)
    except ValueError as exc:
        raise TableParseError(f"Missing expected heading: {heading}") from exc


def _table_after_heading(lines: Sequence[str], heading: str) -> list[MarkdownRow]:
    heading_index = _find_heading(lines, heading)
    table_start: int | None = None
    for index in range(heading_index + 1, len(lines)):
        line = lines[index]
        if line.startswith("|"):
            table_start = index
            break
        if line.startswith("#"):
            break
    if table_start is None:
        raise TableParseError(f"No Markdown table found after heading: {heading}")

    headers = _split_row(lines[table_start])
    if table_start + 1 >= len(lines) or not _is_separator(
        _split_row(lines[table_start + 1])
    ):
        raise TableParseError(f"Invalid Markdown table separator after: {heading}")

    rows: list[MarkdownRow] = []
    for index in range(table_start + 2, len(lines)):
        line = lines[index]
        if not line.startswith("|"):
            break
        values = _split_row(line)
        if len(values) != len(headers):
            raise TableParseError(
                f"Expected {len(headers)} cells at line {index + 1}, "
                f"found {len(values)}"
            )
        rows.append(
            MarkdownRow(
                values=dict(zip(headers, values, strict=True)),
                line_number=index + 1,
                row_number=len(rows) + 1,
            )
        )
    return rows


def _parse_positive_int(value: str, context: str) -> int:
    cleaned = value.replace(",", "").strip()
    if not cleaned.isdigit() or int(cleaned) < 1:
        raise TableParseError(f"Expected a positive integer for {context}: {value!r}")
    return int(cleaned)


def _year_key(academic_year: str) -> str:
    return academic_year.replace("/", "-")


def _source_ref(
    source: dict[str, Any],
    logical_dataset_id: str,
    row: MarkdownRow,
) -> dict[str, Any]:
    datasets = {
        item["id"]: item for item in source.get("logical_datasets", [])
    }
    if logical_dataset_id not in datasets:
        raise TableParseError(
            f"Source {source['id']!r} does not register dataset "
            f"{logical_dataset_id!r}"
        )
    return {
        "source_id": source["id"],
        "logical_dataset_id": logical_dataset_id,
        "path": source["path"],
        "markdown_line": row.line_number,
        "table_row": row.row_number,
        "pdf_pages": datasets[logical_dataset_id]["pdf_pages"],
    }


def _registered_sources(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = {source["id"]: source for source in registry.get("sources", [])}
    required = {UNI_CODE_SOURCE_ID, REQUIREMENTS_SOURCE_ID, INTAKE_SOURCE_ID}
    missing = sorted(required - sources.keys())
    if missing:
        raise TableParseError(
            "Source registry is missing required source IDs: " + ", ".join(missing)
        )
    return sources


def _verify_registry_files(
    project_root: Path,
    registry: dict[str, Any],
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for source in registry.get("sources", []):
        source_id = str(source["id"])
        path = (project_root / str(source["path"])).resolve()
        try:
            path.relative_to(project_root)
        except ValueError as exc:
            raise TableParseError(
                f"Registered source escapes project root: {source['path']}"
            ) from exc
        if not path.is_file():
            raise TableParseError(f"Registered source is missing: {path}")
        expected_checksum = source.get("checksum", {}).get("value")
        actual_checksum = file_sha256(path)
        if actual_checksum != expected_checksum:
            raise TableParseError(
                f"Registered source changed since registration: {source['path']}. "
                "Run the source registry again before parsing."
            )
        paths[source_id] = path
    return paths


def _load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _institution_record(raw_name: str, source: dict[str, Any]) -> dict[str, Any]:
    definition = institution_definition(raw_name, NAME_MAPPINGS)
    canonical_name = str(definition["canonical_name"])
    institution_type = str(definition["type"])
    parent_name = definition["parent_name"]
    aliases = [] if canonical_name == raw_name else [raw_name]
    return {
        "id": f"institution:{stable_slug(canonical_name)}",
        "name": canonical_name,
        "type": institution_type,
        "parent_id": (
            f"institution:{stable_slug(str(parent_name))}" if parent_name else None
        ),
        "aliases": aliases,
        "source": source,
    }


def _expected_count(
    source: dict[str, Any], logical_dataset_id: str
) -> int | None:
    for dataset in source.get("logical_datasets", []):
        if dataset["id"] == logical_dataset_id:
            value = dataset.get("expected_records")
            return int(value) if value is not None else None
    raise TableParseError(
        f"Missing registered logical dataset {logical_dataset_id!r} "
        f"in source {source['id']!r}"
    )


def _assert_expected_count(
    rows: Sequence[Any],
    source: dict[str, Any],
    logical_dataset_id: str,
) -> None:
    expected = _expected_count(source, logical_dataset_id)
    if expected is not None and len(rows) != expected:
        raise TableParseError(
            f"Dataset {logical_dataset_id!r} expected {expected} records, "
            f"found {len(rows)}"
        )


def _unique_by_id(records: Iterable[dict[str, Any]], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        record_id = str(record["id"])
        if record_id in seen:
            duplicates.add(record_id)
        seen.add(record_id)
    if duplicates:
        raise TableParseError(
            f"Duplicate {label} IDs: {', '.join(sorted(duplicates))}"
        )


def build_graph_data(
    project_root: str | Path,
    registry: dict[str, Any],
) -> dict[str, Any]:
    """Parse all registered tables and return deterministic graph-ready data."""

    root = Path(project_root).expanduser().resolve()
    if registry.get("dataset", {}).get("id") != DATASET_ID:
        raise TableParseError(
            f"Unexpected registry dataset: {registry.get('dataset', {}).get('id')!r}"
        )
    if registry.get("dataset", {}).get("academic_year") != ACADEMIC_YEAR:
        raise TableParseError("Registry academic year does not match the parser")

    sources = _registered_sources(registry)
    paths = _verify_registry_files(root, registry)
    year_key = _year_key(ACADEMIC_YEAR)

    uni_source = sources[UNI_CODE_SOURCE_ID]
    requirement_source = sources[REQUIREMENTS_SOURCE_ID]
    intake_source = sources[INTAKE_SOURCE_ID]

    uni_rows = _table_after_heading(
        _load_lines(paths[UNI_CODE_SOURCE_ID]), UNI_CODE_HEADING
    )
    _assert_expected_count(uni_rows, uni_source, "course-offerings")

    intake_lines = _load_lines(paths[INTAKE_SOURCE_ID])
    annex_a_rows = _table_after_heading(intake_lines, ANNEX_A_HEADING)
    _assert_expected_count(annex_a_rows, intake_source, "course-intake")

    courses: list[dict[str, Any]] = []
    course_by_code: dict[str, dict[str, Any]] = {}
    for row in annex_a_rows:
        code = row.values["Course Code"]
        if not re.fullmatch(r"\d{3}", code):
            raise TableParseError(f"Invalid course code at line {row.line_number}: {code}")
        raw_name = row.values["Course of Study"]
        canonical_name = canonical_course_name(code, raw_name, NAME_MAPPINGS)
        aliases = [] if canonical_name == raw_name else [raw_name]
        course = {
            "id": f"course:{code}",
            "code": code,
            "name": canonical_name,
            "aliases": aliases,
            "source": _source_ref(intake_source, "course-intake", row),
        }
        courses.append(course)
        course_by_code[code] = course
    _unique_by_id(courses, "course")

    institution_by_raw_name: dict[str, dict[str, Any]] = {}
    institutions_by_id: dict[str, dict[str, Any]] = {}
    course_offerings: list[dict[str, Any]] = []
    uni_codes: list[dict[str, Any]] = []
    offering_by_unicode: dict[str, dict[str, Any]] = {}
    offering_by_institution_and_course: dict[tuple[str, str], dict[str, Any]] = {}

    for row in uni_rows:
        raw_course_name = row.values["Course of Study"]
        raw_institution_name = row.values["University / Campus / Institute"]
        uni_code = row.values["Uni-Code"]
        if not re.fullmatch(r"\d{3}[A-Z]", uni_code):
            raise TableParseError(
                f"Invalid Uni-Code at line {row.line_number}: {uni_code!r}"
            )
        course_code = uni_code[:3]
        course = course_by_code.get(course_code)
        if course is None:
            raise TableParseError(
                f"Uni-Code {uni_code} references unknown course {course_code}"
            )
        if raw_course_name != course["name"] and raw_course_name not in course["aliases"]:
            course["aliases"].append(raw_course_name)
            course["aliases"].sort()

        if raw_institution_name not in institution_by_raw_name:
            institution = _institution_record(
                raw_institution_name,
                _source_ref(uni_source, "course-offerings", row),
            )
            existing = institutions_by_id.get(institution["id"])
            if existing is not None and existing["name"] != institution["name"]:
                raise TableParseError(
                    f"Institution ID collision: {existing['name']!r} and "
                    f"{institution['name']!r}"
                )
            institutions_by_id[institution["id"]] = institution
            institution_by_raw_name[raw_institution_name] = institution
        institution = institution_by_raw_name[raw_institution_name]

        institution_key = institution["id"].removeprefix("institution:")
        offering_id = f"offering:{course_code}:{institution_key}"
        uni_code_id = f"unicode:{year_key}:{uni_code}"
        source_ref = _source_ref(uni_source, "course-offerings", row)
        offering = {
            "id": offering_id,
            "course_id": course["id"],
            "institution_id": institution["id"],
            "academic_year_id": f"academic-year:{year_key}",
            "uni_code_id": uni_code_id,
            "zscore_lookup": {
                "course": course["name"],
                "institution": institution["name"],
            },
            "source": source_ref,
        }
        uni_code_record = {
            "id": uni_code_id,
            "code": uni_code,
            "academic_year_id": f"academic-year:{year_key}",
            "offering_id": offering_id,
            "source": source_ref,
        }
        pair = (institution["id"], course["id"])
        if pair in offering_by_institution_and_course:
            raise TableParseError(
                f"Duplicate course offering for {course['name']} at "
                f"{institution['name']}"
            )
        offering_by_institution_and_course[pair] = offering
        offering_by_unicode[uni_code] = offering
        course_offerings.append(offering)
        uni_codes.append(uni_code_record)

    _unique_by_id(course_offerings, "course offering")
    _unique_by_id(uni_codes, "Uni-Code")

    institution_ids = set(institutions_by_id)
    for institution in institutions_by_id.values():
        parent_id = institution["parent_id"]
        if parent_id is not None and parent_id not in institution_ids:
            raise TableParseError(
                f"Institution {institution['name']!r} references missing parent "
                f"{parent_id!r}"
            )

    requirement_lines = _load_lines(paths[REQUIREMENTS_SOURCE_ID])
    ol_rows = _table_after_heading(requirement_lines, OL_HEADING)
    aptitude_rows = _table_after_heading(requirement_lines, APTITUDE_HEADING)
    _assert_expected_count(ol_rows, requirement_source, "ol-requirements")
    _assert_expected_count(
        aptitude_rows, requirement_source, "aptitude-test-requirements"
    )

    subjects = [
        {
            "id": f"subject:ol:{stable_slug(canonical_name)}",
            "name": canonical_name,
            "level": "O/L",
        }
        for _, canonical_name in SUBJECT_COLUMNS
    ]
    subject_by_column = {
        column: next(subject for subject in subjects if subject["name"] == name)
        for column, name in SUBJECT_COLUMNS
    }

    requirements: list[dict[str, Any]] = []
    for row in ol_rows:
        referenced_codes = [
            value.strip() for value in row.values["Uni-Code(s)"].split("/")
        ]
        for uni_code in referenced_codes:
            offering = offering_by_unicode.get(uni_code)
            if offering is None:
                raise TableParseError(
                    f"O/L requirement at line {row.line_number} references "
                    f"unknown Uni-Code {uni_code!r}"
                )
            for column, _ in SUBJECT_COLUMNS:
                minimum_grade = row.values[column]
                if not minimum_grade:
                    continue
                if minimum_grade not in {"A", "B", "C", "S"}:
                    raise TableParseError(
                        f"Invalid O/L grade {minimum_grade!r} at line "
                        f"{row.line_number}"
                    )
                subject = subject_by_column[column]
                requirements.append(
                    {
                        "id": (
                            f"requirement:ol:{uni_code}:"
                            f"{subject['id'].removeprefix('subject:ol:')}"
                        ),
                        "offering_id": offering["id"],
                        "uni_code": uni_code,
                        "level": "O/L",
                        "type": "minimum_grade",
                        "subject_id": subject["id"],
                        "minimum_grade": minimum_grade,
                        "source": _source_ref(
                            requirement_source, "ol-requirements", row
                        ),
                    }
                )
    _unique_by_id(requirements, "requirement")

    aptitude_tests: list[dict[str, Any]] = []
    for row in aptitude_rows:
        uni_code = row.values["Uni-Code"]
        offering = offering_by_unicode.get(uni_code)
        if offering is None:
            raise TableParseError(
                f"Aptitude row at line {row.line_number} references unknown "
                f"Uni-Code {uni_code!r}"
            )
        institution = institution_by_raw_name.get(
            row.values["University / Campus / Institute"]
        )
        if institution is None or institution["id"] != offering["institution_id"]:
            raise TableParseError(
                f"Aptitude institution mismatch for Uni-Code {uni_code}"
            )
        if canonical_course_label(
            row.values["Course of Study"], NAME_MAPPINGS
        ) != course_by_code[uni_code[:3]]["name"]:
            raise TableParseError(f"Aptitude course mismatch for Uni-Code {uni_code}")
        aptitude_tests.append(
            {
                "id": f"aptitude-test:{year_key}:{uni_code}",
                "offering_id": offering["id"],
                "uni_code": uni_code,
                "required": True,
                "administered_by_institution_id": institution["id"],
                "source": _source_ref(
                    requirement_source, "aptitude-test-requirements", row
                ),
            }
        )
    _unique_by_id(aptitude_tests, "aptitude test")

    intake_records: list[dict[str, Any]] = []
    for row in annex_a_rows:
        code = row.values["Course Code"]
        intake_records.append(
            {
                "id": f"intake:{year_key}:course:{code}",
                "scope": "course",
                "category": "total_proposed",
                "course_id": f"course:{code}",
                "offering_id": None,
                "academic_year_id": f"academic-year:{year_key}",
                "value": _parse_positive_int(
                    row.values["Intake"], f"course {code} intake"
                ),
                "includes_additional_intake": code == "019",
                "source": _source_ref(intake_source, "course-intake", row),
            }
        )

    annex_b_index = _find_heading(intake_lines, ANNEX_B_HEADING)
    current_section: str | None = None
    section_rows: dict[str, list[MarkdownRow]] = {}
    for index in range(annex_b_index + 1, len(intake_lines)):
        line = intake_lines[index]
        if line.startswith("### "):
            current_section = line[4:].strip()
            section_rows[current_section] = []
            continue
        if current_section is None or not line.startswith("|"):
            continue
        values = _split_row(line)
        if values == ["Course of Study", "No."] or _is_separator(values):
            continue
        if len(values) != 2:
            raise TableParseError(
                f"Invalid Annex (b) row width at line {index + 1}"
            )
        section_rows[current_section].append(
            MarkdownRow(
                values={"Course of Study": values[0], "No.": values[1]},
                line_number=index + 1,
                row_number=len(section_rows[current_section]) + 1,
            )
        )

    offering_intake_count = 0
    additional_intake_count = 0
    annex_b_detail_total = 0
    for section, rows in section_rows.items():
        declared_total: int | None = None
        calculated_total = 0
        if section == "Additional Intake":
            institution = None
        else:
            institution = institution_by_raw_name.get(section)
            if institution is None:
                raise TableParseError(
                    f"Annex (b) contains unknown institution section {section!r}"
                )

        for row in rows:
            raw_course_name = row.values["Course of Study"]
            value = _parse_positive_int(
                row.values["No."], f"Annex (b) line {row.line_number}"
            )
            if raw_course_name == "Total":
                declared_total = value
                continue
            calculated_total += value
            canonical_name = canonical_course_label(raw_course_name, NAME_MAPPINGS)
            matching_courses = [
                course
                for course in courses
                if course["name"] == canonical_name
                or canonical_name in course["aliases"]
            ]
            if len(matching_courses) != 1:
                raise TableParseError(
                    f"Annex (b) course {raw_course_name!r} resolved to "
                    f"{len(matching_courses)} courses"
                )
            course = matching_courses[0]
            if raw_course_name != course["name"] and raw_course_name not in course[
                "aliases"
            ]:
                course["aliases"].append(raw_course_name)
                course["aliases"].sort()

            if institution is None:
                additional_intake_count += 1
                intake_records.append(
                    {
                        "id": f"intake:{year_key}:additional:{course['code']}",
                        "scope": "course",
                        "category": "additional",
                        "course_id": course["id"],
                        "offering_id": None,
                        "academic_year_id": f"academic-year:{year_key}",
                        "value": value,
                        "includes_additional_intake": False,
                        "source": _source_ref(
                            intake_source, "additional-intake", row
                        ),
                    }
                )
                continue

            offering = offering_by_institution_and_course.get(
                (institution["id"], course["id"])
            )
            if offering is None:
                raise TableParseError(
                    f"No registered offering for {course['name']} at "
                    f"{institution['name']}"
                )
            uni_code = next(
                record["code"]
                for record in uni_codes
                if record["offering_id"] == offering["id"]
            )
            offering_intake_count += 1
            annex_b_detail_total += value
            intake_records.append(
                {
                    "id": f"intake:{year_key}:offering:{uni_code}",
                    "scope": "offering",
                    "category": "proposed",
                    "course_id": course["id"],
                    "offering_id": offering["id"],
                    "academic_year_id": f"academic-year:{year_key}",
                    "value": value,
                    "includes_additional_intake": False,
                    "source": _source_ref(
                        intake_source, "offering-intake", row
                    ),
                }
            )
        if declared_total != calculated_total:
            raise TableParseError(
                f"Annex (b) subtotal mismatch for {section}: declared "
                f"{declared_total}, calculated {calculated_total}"
            )

    if offering_intake_count != len(course_offerings):
        raise TableParseError(
            f"Expected one intake for each of {len(course_offerings)} offerings, "
            f"found {offering_intake_count}"
        )
    _assert_expected_count(
        [None] * offering_intake_count, intake_source, "offering-intake"
    )
    _assert_expected_count(
        [None] * additional_intake_count, intake_source, "additional-intake"
    )
    _unique_by_id(intake_records, "intake")

    course_intake_total = sum(
        record["value"]
        for record in intake_records
        if record["category"] == "total_proposed"
    )
    additional_intake_total = sum(
        record["value"]
        for record in intake_records
        if record["category"] == "additional"
    )
    if course_intake_total != annex_b_detail_total + additional_intake_total:
        raise TableParseError(
            "Annex totals do not reconcile: course total "
            f"{course_intake_total}, offering total {annex_b_detail_total}, "
            f"additional total {additional_intake_total}"
        )

    institutions = sorted(institutions_by_id.values(), key=lambda item: item["id"])
    courses.sort(key=lambda item: item["code"])
    course_offerings.sort(key=lambda item: item["uni_code_id"])
    uni_codes.sort(key=lambda item: item["code"])
    requirements.sort(key=lambda item: item["id"])
    aptitude_tests.sort(key=lambda item: item["uni_code"])
    intake_records.sort(key=lambda item: item["id"])

    counts = {
        "academic_years": 1,
        "institutions": len(institutions),
        "courses": len(courses),
        "course_offerings": len(course_offerings),
        "uni_codes": len(uni_codes),
        "subjects": len(subjects),
        "ol_requirements": len(requirements),
        "aptitude_tests": len(aptitude_tests),
        "intake_records": len(intake_records),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generation_stage": "deterministic_table_parsing",
        "dataset": registry["dataset"],
        "source_registry": {
            "schema_version": registry["schema_version"],
            "registered_checksums": {
                source["id"]: source["checksum"]["value"]
                for source in registry["sources"]
            },
        },
        "validation_summary": {
            "status": "passed",
            "counts": counts,
            "intake_totals": {
                "course_total": course_intake_total,
                "offering_total": annex_b_detail_total,
                "additional_total": additional_intake_total,
            },
        },
        "academic_years": [
            {
                "id": f"academic-year:{year_key}",
                "name": ACADEMIC_YEAR,
            }
        ],
        "institutions": institutions,
        "courses": courses,
        "course_offerings": course_offerings,
        "uni_codes": uni_codes,
        "subjects": subjects,
        "requirements": requirements,
        "aptitude_tests": aptitude_tests,
        "intake_records": intake_records,
    }


def load_registry(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path).expanduser().resolve()
    if not registry_path.is_file():
        raise TableParseError(
            f"Source registry not found: {registry_path}. Run source registration first."
        )
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TableParseError(f"Invalid source registry JSON: {exc}") from exc
    if not isinstance(registry, dict):
        raise TableParseError("Source registry root must be a JSON object")
    return registry


def write_graph_data(data: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
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
        description="Parse registered UGC Markdown tables into graph-ready JSON."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository root (default: detected automatically).",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help=f"Source registry path (default: {DEFAULT_REGISTRY.as_posix()}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Graph JSON output path (default: {DEFAULT_OUTPUT.as_posix()}).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Parse and validate without writing graph_data.json.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.project_root.expanduser().resolve()
    registry_path = args.registry
    output_path = args.output
    if not registry_path.is_absolute():
        registry_path = root / registry_path
    if not output_path.is_absolute():
        output_path = root / output_path

    try:
        registry = load_registry(registry_path)
        data = build_graph_data(root, registry)
        counts = data["validation_summary"]["counts"]
        summary = (
            f"Parsed {counts['courses']} courses, "
            f"{counts['course_offerings']} offerings, "
            f"{counts['ol_requirements']} O/L requirements, and "
            f"{counts['intake_records']} intake records"
        )
        if args.check_only:
            print(f"{summary}; validation passed.")
            return 0
        written_path = write_graph_data(data, output_path)
        print(f"{summary} into {written_path}.")
        return 0
    except (
        OSError,
        UnicodeError,
        NameNormalizationError,
        SourceRegistrationError,
        TableParseError,
    ) as exc:
        print(f"Table parsing failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
