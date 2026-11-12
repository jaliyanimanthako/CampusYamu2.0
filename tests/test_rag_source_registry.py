from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from campusyamu.knowledge_graph.source_registry import (
    DATASET_ID,
    PROJECT_ROOT,
    SourceRegistrationError,
    build_registry,
    write_registry,
)


class SourceRegistryTests(unittest.TestCase):
    def test_registers_expected_sources_and_datasets(self) -> None:
        registry = build_registry(PROJECT_ROOT)

        self.assertEqual(registry["schema_version"], 1)
        self.assertEqual(registry["dataset"]["id"], DATASET_ID)
        self.assertEqual(registry["original_document"]["expected_page_count"], 208)
        self.assertEqual(len(registry["sources"]), 4)

        sources = {source["id"]: source for source in registry["sources"]}
        offerings = sources["uni-code-assignments"]["logical_datasets"][0]
        self.assertEqual(offerings["expected_records"], 261)

        requirement_sets = sources["ol-and-aptitude-requirements"][
            "logical_datasets"
        ]
        self.assertEqual(
            [dataset["expected_records"] for dataset in requirement_sets],
            [31, 24],
        )

        intake_sets = sources["intake-distribution"]["logical_datasets"]
        self.assertEqual(
            [dataset["expected_records"] for dataset in intake_sets],
            [126, 261, 1],
        )

        for source in registry["sources"]:
            self.assertRegex(source["checksum"]["value"], r"^[0-9a-f]{64}$")
            self.assertGreater(source["size_bytes"], 0)
            self.assertGreater(source["line_count"], 0)

    def test_registry_is_deterministic(self) -> None:
        first = build_registry(PROJECT_ROOT)
        second = build_registry(PROJECT_ROOT)
        self.assertEqual(first, second)

    def test_writes_valid_json(self) -> None:
        registry = build_registry(PROJECT_ROOT)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "source_registry.json"
            write_registry(registry, output)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                registry,
            )

    def test_rejects_missing_project_root(self) -> None:
        missing = PROJECT_ROOT / "directory-that-does-not-exist"
        with self.assertRaises(SourceRegistrationError):
            build_registry(missing)


if __name__ == "__main__":
    unittest.main()
