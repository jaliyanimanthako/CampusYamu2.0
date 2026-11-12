from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from campusyamu.agents.travel_time import build_db
from campusyamu.agents.travel_time.neo4j_load import statements
from campusyamu.agents.travel_time.repository import LookupError_, TravelRepository


class TravelDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "travel.db"
        cls.counts = build_db.build(build_db.DATA_DIR, cls.db)
        cls.repo = TravelRepository(cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.repo.close()
        cls.tmp.cleanup()

    def test_complete_matrix(self) -> None:
        self.assertEqual(self.counts["districts"], 25)
        self.assertEqual(self.counts["pairs"], self.counts["ds_divisions"] * self.counts["campuses"])

    def test_every_campus_maps_to_a_kg_institution(self) -> None:
        from campusyamu.knowledge_graph.build_graph import load_graph
        graph = load_graph()
        rows = self.repo._all("SELECT campus_id, institution_id, university_id FROM campuses")
        for row in rows:
            self.assertEqual(graph.nodes[row["institution_id"]]["type"], "Institution", row)
            self.assertEqual(graph.nodes[row["university_id"]]["type"], "Institution", row)
        sripalee = next(r for r in rows if r["campus_id"] == "UOC-SRIPALEE")
        self.assertEqual(sripalee["institution_id"], "institution:sripalee-campus")

    def test_border_district_case(self) -> None:
        summary = self.repo.summary(self.repo.find_origin("Haldummulla"))
        self.assertTrue(summary["nearest_is_outside_home_district"])
        self.assertEqual(summary["nearest"]["campus_id"], "SUSL-MAIN")          # Belihuloya, Ratnapura
        self.assertEqual(summary["nearest_in_home_district"]["campus_district"], "Badulla")

    def test_owner_site_decisions(self) -> None:
        campuses = {r["campus_id"]: r for r in self.repo._all("SELECT * FROM campuses")}
        self.assertNotIn("USJ-ENG-RATMALANA", campuses)                     # excluded by the owner
        siddamulla = campuses["USJ-ENG-SIDDAMULLA"]
        self.assertEqual((siddamulla["status"], siddamulla["approximate_location"]), ("confirmed", 0))
        self.assertEqual(siddamulla["campus_site"], "Faculty of Engineering, Siddamulla, Kottawa")
        self.assertEqual(self.counts["pairs"], 339 * 38)

    def test_offerings_are_placed_at_their_teaching_site(self) -> None:
        sites = {r["uni_code"]: r for r in self.repo._all("SELECT * FROM offering_sites")}
        self.assertEqual(len(sites), 261)
        expected = {
            "008F": "UOR-ENG",            # Ruhuna Engineering, Hapugala
            "001G": "UOM-MED",            # Moratuwa Medicine, Kalutara
            "008C": "USJ-ENG-SIDDAMULLA",
            "008E": "UOJ-KILI",           # Jaffna Engineering, Kilinochchi
            "013H": "EUSL-MAIN",          # Eastern Physical Science, not the Trincomalee Campus
            "015W": "EUSL-TRINCO",        # a Trincomalee Campus offering
            "102A": "UOC-FOT",
            "001B": "UOP-MAIN",           # single-site university
        }
        for code, campus in expected.items():
            self.assertEqual(sites[code]["campus_id"], campus, code)
        self.assertTrue(sites["037F"]["needs_review"])                         # allied health guess
        self.assertFalse(sites["008F"]["needs_review"])

    def test_bus_estimate_and_course_ranking(self) -> None:
        origin = self.repo.find_origin("Galle 4 Gravets")
        rows = self.repo.course_offerings(origin, "Engineering")
        self.assertEqual(rows[0]["uni_code"], "008F")
        first = rows[0]
        self.assertEqual(first["bus_min_est"], round(first["drive_min"] * 1.5 + 15))
        self.assertTrue(all(r["course_name"].lower().find("engineering") >= 0 for r in rows))

    def test_faculty_query(self) -> None:
        origin = self.repo.find_origin("Minuwangoda")
        ruhuna = self.repo.faculty_sites(origin, "Faculty of Engineering", "Ruhuna")
        self.assertEqual(ruhuna[0]["campus_id"], "UOR-ENG")
        self.assertTrue(ruhuna[0]["named_faculty_site"])
        self.assertIn("008F Engineering", ruhuna[0]["matching_courses"])
        moratuwa = self.repo.faculty_sites(origin, "Engineering", "Moratuwa")
        self.assertEqual([r["campus_id"] for r in moratuwa], ["UOM-MAIN"])     # found via its courses
        medicine = {r["campus_id"] for r in self.repo.faculty_sites(origin, "Medicine", "Ruhuna")}
        self.assertEqual(medicine, {"UOR-MED"})

    def test_lookups(self) -> None:
        self.assertEqual(self.repo.find_origin("kantle").ds_division, "Kantale")      # typo
        self.assertEqual(self.repo.find_university("jayewardenepura"), "University of Sri Jayewardenepura")
        with self.assertRaises(LookupError_):
            self.repo.find_origin("Atlantis")
        with self.assertRaises(LookupError_):
            self.repo.find_university("University")                                   # ambiguous

    def test_results_sorted_by_time(self) -> None:
        rows = self.repo.from_origin(self.repo.find_origin("Kantale"), limit=None)
        self.assertEqual([r["drive_min"] for r in rows], sorted(r["drive_min"] for r in rows))

    def test_neo4j_statements_cover_every_pair(self) -> None:
        travel_rows = sum(len(p.get("rows", [])) for q, p in statements(self.db) if "TRAVEL_TO" in q)
        self.assertEqual(travel_rows, self.counts["pairs"])
        deletes = [q for q, _ in statements(self.db) if "DELETE" in q]
        self.assertEqual(deletes, ["MATCH (n:CampusTravel) DETACH DELETE n"])


class BuildValidationTests(unittest.TestCase):
    def _copy(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        for name in (build_db.CAMPUSES_CSV, build_db.LONG_CSV, *build_db.WIDE_CSVS.values()):
            shutil.copy(build_db.DATA_DIR / name, tmp / name)
        return tmp

    def _rewrite_long(self, folder: Path, change) -> None:
        path = folder / build_db.LONG_CSV
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields, rows = reader.fieldnames, list(reader)
        rows = change(rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_missing_pair_fails_the_build(self) -> None:
        folder = self._copy()
        self._rewrite_long(folder, lambda rows: rows[1:])
        with self.assertRaisesRegex(build_db.BuildError, "missing"):
            build_db.load_inputs(folder)

    def test_wide_and_long_must_agree(self) -> None:
        folder = self._copy()

        def bump(rows):
            rows[0]["drive_min"] = str(float(rows[0]["drive_min"]) + 5)
            return rows
        self._rewrite_long(folder, bump)
        with self.assertRaisesRegex(build_db.BuildError, "differs"):
            build_db.load_inputs(folder)

    def test_routing_error_fails_the_build(self) -> None:
        folder = self._copy()

        def broken(rows):
            rows[5]["error"] = "NoRoute"
            return rows
        self._rewrite_long(folder, broken)
        with self.assertRaisesRegex(build_db.BuildError, "routing error"):
            build_db.load_inputs(folder)


if __name__ == "__main__":
    unittest.main()
