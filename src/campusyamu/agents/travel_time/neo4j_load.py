"""Load ``data/processed/travel/travel_times.db`` into Neo4j, linked to the knowledge graph.

    uv run python -m campusyamu.agents.travel_time.neo4j_load

    (:District:CampusTravel)
    (:DSDivision:CampusTravel)-[:IN_DISTRICT]->(:District)
    (:Campus:CampusTravel)-[:IN_DISTRICT]->(:District)
    (:Campus)-[:CAMPUS_OF]->(:Institution)          # KG node; campus-level when it exists
    (:Campus)-[:OF_UNIVERSITY]->(:Institution)      # KG university node
    (:DSDivision)-[:TRAVEL_TO {road_km, drive_min, straight_km}]->(:Campus)
    (:Offering)-[:TAUGHT_AT {rule, needs_review}]->(:Campus)   # KG offering -> teaching site

Loading replaces every ``CampusTravel`` node and never touches KG
(``CampusKG``) or handbook (``CampusDocs``) nodes. The KG export re-creates
the CAMPUS_OF / OF_UNIVERSITY links after a KG reload.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Sequence

from .build_db import DEFAULT_DB

LABEL = "CampusTravel"
BATCH = 1000
LINK_INSTITUTIONS = [
    "MATCH (c:Campus) MATCH (i:Institution {id: c.institution_id}) MERGE (c)-[:CAMPUS_OF]->(i)",
    "MATCH (c:Campus) MATCH (u:Institution {id: c.university_id}) MERGE (c)-[:OF_UNIVERSITY]->(u)",
    # offering ids are kept on the campus so the KG export can re-create these after a KG reload
    "MATCH (c:Campus) UNWIND coalesce(c.taught_offerings, []) AS oid MATCH (o:Offering {id: oid}) "
    "MERGE (o)-[t:TAUGHT_AT]->(c) SET t.needs_review = oid IN coalesce(c.review_offerings, [])",
]


def _rows(db: Path, sql: str) -> list[dict]:
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [{k: r[k] for k in r.keys() if r[k] is not None} for r in connection.execute(sql)]
    finally:
        connection.close()


def statements(db: Path):
    districts = _rows(db, "SELECT district AS name, province FROM districts")
    origins = _rows(db, "SELECT origin_id AS id, ds_division AS name, district, province, point_source, "
                        "snap_m FROM ds_divisions")
    campuses = _rows(db, "SELECT campus_id AS id, site_no, university, campus_site AS name, district, lat, "
                         "lon, coord_source, approximate_location = 1 AS approximate_location, "
                         "handbook_listed = 1 AS handbook_listed, status, institution_id, university_id "
                         "FROM campuses")
    travel = _rows(db, "SELECT origin_id, campus_id, road_km, drive_min, straight_km FROM travel")
    taught: dict[str, list[str]] = {}
    review: dict[str, list[str]] = {}
    for row in _rows(db, "SELECT offering_id, campus_id, needs_review FROM offering_sites ORDER BY uni_code"):
        taught.setdefault(row["campus_id"], []).append(row["offering_id"])
        if row["needs_review"]:
            review.setdefault(row["campus_id"], []).append(row["offering_id"])
    for campus in campuses:
        campus["taught_offerings"] = taught.get(campus["id"], [])
        campus["review_offerings"] = review.get(campus["id"], [])

    yield f"MATCH (n:{LABEL}) DETACH DELETE n", {}
    for label in ("District", "DSDivision", "Campus"):
        key = "name" if label == "District" else "id"
        yield (f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
               f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"), {}
    yield f"UNWIND $rows AS row CREATE (d:District:{LABEL}) SET d = row", {"rows": districts}
    for label, rows in (("DSDivision", origins), ("Campus", campuses)):
        yield (f"UNWIND $rows AS row CREATE (n:{label}:{LABEL}) SET n = row "
               "WITH n, row MATCH (d:District {name: row.district}) CREATE (n)-[:IN_DISTRICT]->(d)",
               {"rows": rows})
    for start in range(0, len(travel), BATCH):
        yield ("UNWIND $rows AS row MATCH (o:DSDivision {id: row.origin_id}) "
               "MATCH (c:Campus {id: row.campus_id}) "
               "CREATE (o)-[:TRAVEL_TO {road_km: row.road_km, drive_min: row.drive_min, "
               "straight_km: row.straight_km}]->(c)",
               {"rows": travel[start:start + BATCH]})
    for query in LINK_INSTITUTIONS:
        yield query, {}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the travel database into Neo4j.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    from campusyamu.knowledge_graph.handbook_prose import _load_env
    from campusyamu.handbook_search.store import HandbookStore, connect

    _load_env(args.env_file)
    with connect() as driver:
        store = HandbookStore(driver)          # reused for its database selection and _run helper
        for query, params in statements(args.db):
            store._run(query, **params)
        counts = store._run(
            "MATCH (o:DSDivision) WITH count(o) AS ds "
            "MATCH (c:Campus) WITH ds, count(c) AS campuses "
            "MATCH (:DSDivision)-[t:TRAVEL_TO]->(:Campus) WITH ds, campuses, count(t) AS travel "
            "OPTIONAL MATCH (:Campus)-[l:CAMPUS_OF]->(:Institution) "
            "RETURN ds, campuses, travel, count(l) AS linked")[0]
    print(f"Loaded {counts['ds']} DS divisions, {counts['campuses']} campuses, {counts['travel']} "
          f"TRAVEL_TO relationships; {counts['linked']} campuses linked to KG institutions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
