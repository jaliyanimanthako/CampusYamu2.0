"""Register the immutable source files used by the knowledge-graph pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = 1
DATASET_ID = "ugc-handbook-2024-2025"
ACADEMIC_YEAR = "2024/2025"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path("RAG_Agent/generated/source_registry.json")


class SourceRegistrationError(RuntimeError):
    """Raised when a required source cannot be registered safely."""


@dataclass(frozen=True)
class LogicalDataset:
    """One logical dataset contained in a registered Markdown source."""

    dataset_id: str
    description: str
    pdf_page_start: int
    pdf_page_end: int
    expected_records: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.dataset_id,
            "description": self.description,
            "pdf_pages": {
                "start": self.pdf_page_start,
                "end": self.pdf_page_end,
            },
        }
        if self.expected_records is not None:
            result["expected_records"] = self.expected_records
        return result


@dataclass(frozen=True)
class SourceSpec:
    """Static registration contract for one required Markdown file."""

    source_id: str
    relative_path: str
    role: str
    description: str
    required_markers: tuple[str, ...]
    logical_datasets: tuple[LogicalDataset, ...]


SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="structured-handbook",
        relative_path="RAG_Agent/student_handbook_english_structured.md",
        role="narrative_evidence",
        description=(
            "Cleaned handbook prose, section hierarchy, admission policies, "
            "course descriptions, and PDF page markers."
        ),
        required_markers=(
            "# Admission to Undergraduate Courses of the Universities in Sri Lanka",
            "## Section 1 — Policies and Principles",
            "## Section 2 — Essential information",
        ),
        logical_datasets=(
            LogicalDataset(
                dataset_id="handbook-narrative",
                description="Narrative evidence and admission rules",
                pdf_page_start=1,
                pdf_page_end=208,
            ),
        ),
    ),
    SourceSpec(
        source_id="uni-code-assignments",
        relative_path="RAG_Agent/ugc_uni_codes_2024_2025.md",
        role="course_offerings",
        description="Course, institution, and Uni-Code assignments.",
        required_markers=(
            "## “Uni-Codes” Assigned for Each Course of Study of University",
            "| Course of Study | University / Campus / Institute | Uni-Code |",
        ),
        logical_datasets=(
            LogicalDataset(
                dataset_id="course-offerings",
                description="Course offerings and their Uni-Codes",
                pdf_page_start=150,
                pdf_page_end=156,
                expected_records=261,
            ),
        ),
    ),
    SourceSpec(
        source_id="ol-and-aptitude-requirements",
        relative_path=(
            "RAG_Agent/ugc_ol_requirements_and_aptitude_tests_2024_2025.md"
        ),
        role="eligibility_requirements",
        description="O/L subject-grade requirements and aptitude-test mappings.",
        required_markers=(
            "### O/L Requirement Mapping",
            "### Practical / Aptitude Test Mapping",
        ),
        logical_datasets=(
            LogicalDataset(
                dataset_id="ol-requirements",
                description="O/L requirement table rows before Uni-Code expansion",
                pdf_page_start=157,
                pdf_page_end=158,
                expected_records=31,
            ),
            LogicalDataset(
                dataset_id="aptitude-test-requirements",
                description="Course offerings requiring an aptitude test",
                pdf_page_start=159,
                pdf_page_end=159,
                expected_records=24,
            ),
        ),
    ),
    SourceSpec(
        source_id="intake-distribution",
        relative_path="RAG_Agent/ugc_annex_a_b_intake_distribution_2024_2025.md",
        role="intake_records",
        description="Course-level and institution-level proposed intake records.",
        required_markers=(
            "## Annex (a) — Places Available for Admission",
            (
                "## Annex (b) — Distribution of the Total Number of Places "
                "Proposed for University Admission"
            ),
        ),
        logical_datasets=(
            LogicalDataset(
                dataset_id="course-intake",
                description="Aggregate intake by course",
                pdf_page_start=198,
                pdf_page_end=201,
                expected_records=126,
            ),
            LogicalDataset(
                dataset_id="offering-intake",
                description="Institution-specific intake by course offering",
                pdf_page_start=202,
                pdf_page_end=205,
                expected_records=261,
            ),
            LogicalDataset(
                dataset_id="additional-intake",
                description="Additional Arts intake not assigned to one offering",
                pdf_page_start=205,
                pdf_page_end=205,
                expected_records=1,
            ),
        ),
    ),
)


def file_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for block in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise SourceRegistrationError(f"Missing {description}: {path}")


def _relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise SourceRegistrationError(
            f"Source must be inside the project root: {path}"
        ) from exc


def _file_record(path: Path, project_root: Path, media_type: str) -> dict[str, Any]:
    _require_file(path, "source file")
    stat = path.stat()
    record: dict[str, Any] = {
        "path": _relative_path(path, project_root),
        "media_type": media_type,
        "size_bytes": stat.st_size,
        "checksum": {
            "algorithm": "sha256",
            "value": file_sha256(path),
        },
    }
    if media_type.startswith("text/"):
        text = path.read_text(encoding="utf-8")
        record["line_count"] = len(text.splitlines())
    return record


def _register_markdown(spec: SourceSpec, project_root: Path) -> dict[str, Any]:
    path = project_root / spec.relative_path
    _require_file(path, f"required Markdown source '{spec.source_id}'")
    text = path.read_text(encoding="utf-8")
    missing_markers = [marker for marker in spec.required_markers if marker not in text]
    if missing_markers:
        formatted = ", ".join(repr(marker) for marker in missing_markers)
        raise SourceRegistrationError(
            f"Source '{spec.source_id}' is missing required marker(s): {formatted}"
        )

    return {
        "id": spec.source_id,
        "role": spec.role,
        "description": spec.description,
        "academic_year": ACADEMIC_YEAR,
        "required": True,
        **_file_record(path, project_root, "text/markdown"),
        "logical_datasets": [item.to_dict() for item in spec.logical_datasets],
    }


def build_registry(project_root: str | Path = PROJECT_ROOT) -> dict[str, Any]:
    """Validate and describe every source used by the graph pipeline."""

    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise SourceRegistrationError(f"Project root does not exist: {root}")

    pdf_path = root / "RAG_Agent/student_handbook_english.pdf"
    original_document = {
        "id": "ugc-handbook-original-pdf",
        "title": "Admission to Undergraduate Courses of the Universities in Sri Lanka",
        "publisher": "University Grants Commission, Sri Lanka",
        "academic_year": ACADEMIC_YEAR,
        "expected_page_count": 208,
        **_file_record(pdf_path, root, "application/pdf"),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "id": DATASET_ID,
            "academic_year": ACADEMIC_YEAR,
            "description": (
                "Non-cutoff handbook sources for the CampusYamu knowledge graph."
            ),
        },
        "original_document": original_document,
        "sources": [_register_markdown(spec, root) for spec in SOURCE_SPECS],
        "excluded_sources": [
            {
                "path": "data/z_scores.db",
                "owner": "zscore_agent",
                "reason": (
                    "Historical cutoff data and forecasts remain outside the "
                    "knowledge graph."
                ),
            }
        ],
    }


def write_registry(registry: dict[str, Any], output_path: str | Path) -> Path:
    """Write the registry atomically and return its resolved output path."""

    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(registry, indent=2, ensure_ascii=False) + "\n"

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
        description="Validate and register CampusYamu knowledge-graph sources."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository root containing RAG_Agent (default: detected automatically).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Registry output path, relative to the project root unless absolute "
            f"(default: {DEFAULT_OUTPUT.as_posix()})."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate all registered sources without writing JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    try:
        registry = build_registry(project_root)
        if args.check_only:
            print(
                f"Validated {len(registry['sources'])} Markdown sources for "
                f"{registry['dataset']['id']}."
            )
            return 0

        output = args.output
        if not output.is_absolute():
            output = project_root / output
        written_path = write_registry(registry, output)
        print(
            f"Registered {len(registry['sources'])} Markdown sources in "
            f"{written_path}."
        )
        return 0
    except (OSError, UnicodeError, SourceRegistrationError) as exc:
        print(f"Source registration failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
