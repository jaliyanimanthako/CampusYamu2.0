"""Build ``data/travel_times.db`` from the DS-division x campus road matrix CSVs.

    uv run python -m travel_time_agent.build_db

Inputs (``data/``):
    campuses.csv                 39 campus sites (A = handbook Annex (c) / course
                                 locations, B = extra sites), coordinates + source
    ds_campus_matrix_long.csv    one row per (DS division, campus): road km,
                                 driving minutes, straight-line km, snap distances
    ds_campus_distance_km.csv    the same matrix, wide (cross-check only)
    ds_campus_duration_min.csv   the same matrix, wide (cross-check only)

The build fails instead of writing a partial database when a pair is missing,
a value is blank, the wide and long files disagree, or a campus/origin in the
matrix is unknown. Softer problems (unusual road/straight-line ratio,
approximate coordinates, unconfirmed sites) are written to ``quality_flags``.

Driving minutes are free-flow car times from the routing engine: a rough,
comparable measure of how far a campus is, not a bus timetable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DB = DATA_DIR / "travel_times.db"
CAMPUSES_CSV = "campuses.csv"
LONG_CSV = "ds_campus_matrix_long.csv"
WIDE_CSVS = {"road_km": "ds_campus_distance_km.csv", "drive_min": "ds_campus_duration_min.csv"}
RATIO_RANGE = (1.0, 3.0)          # road km / straight-line km outside this is flagged
WIDE_TOLERANCE = 0.05

# campus_id -> knowledge-graph Institution id (campus-level institutions first)
INSTITUTION_IDS = {
    "UOC-SRIPALEE": "institution:sripalee-campus",
    "UOC-UCSC": "institution:university-of-colombo-school-of-computing",
    "EUSL-SVIAS": "institution:swamy-vipulananda-institute-of-aesthetic-studies",
    "EUSL-TRINCO": "institution:trincomalee-campus",
}
UNIVERSITY_IDS = {
    "University of Colombo": "institution:university-of-colombo",
    "University of Sri Jayewardenepura": "institution:university-of-sri-jayewardenepura",
    "University of Moratuwa": "institution:university-of-moratuwa",
    "University of the Visual & Performing Arts": "institution:university-of-the-visual-and-performing-arts",
    "University of Kelaniya": "institution:university-of-kelaniya",
    "Gampaha Wickramarachchi Univ. of Indigenous Medicine":
        "institution:gampaha-wickramarachchi-university-of-indigenous-medicine-sri-lanka",
    "University of Peradeniya": "institution:university-of-peradeniya",
    "University of Ruhuna": "institution:university-of-ruhuna",
    "Sabaragamuwa University": "institution:sabaragamuwa-university-of-sri-lanka",
    "Uva Wellassa University": "institution:uva-wellassa-university-of-sri-lanka",
    "Wayamba University": "institution:wayamba-university-of-sri-lanka",
    "Rajarata University": "institution:rajarata-university-of-sri-lanka",
    "University of Jaffna": "institution:university-of-jaffna",
    "University of Vavuniya": "institution:university-of-vavuniya-sri-lanka",
    "Eastern University": "institution:eastern-university-sri-lanka",
    "South Eastern University": "institution:south-eastern-university-of-sri-lanka",
}
DECISIONS_JSON = "travel_decisions.json"      # owner decisions: sites, bus estimate, offering sites
KG_GRAPH = Path(__file__).resolve().parents[1] / "RAG_Agent" / "generated" / "knowledge_graph.json"
DEFAULT_BUS = {"factor": 1.5, "overhead_min": 15}


CANDIDATE_LABEL_RE = re.compile(r"\s*\(candidate\s*\d*:\s*(.*?)\)\s*$", re.IGNORECASE)


def is_candidate(campus_site: str) -> bool:
    """campuses.csv marks alternative locations as '(candidate N: ...)'."""

    return "candidate" in campus_site.casefold()

SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE districts (district TEXT PRIMARY KEY, province TEXT NOT NULL);
CREATE TABLE ds_divisions (
    origin_id TEXT PRIMARY KEY,
    ds_division TEXT NOT NULL UNIQUE,
    district TEXT NOT NULL REFERENCES districts(district),
    province TEXT NOT NULL,
    point_source TEXT NOT NULL,
    snap_m REAL
);
CREATE TABLE campuses (
    campus_id TEXT PRIMARY KEY,
    site_no TEXT NOT NULL UNIQUE,
    university TEXT NOT NULL,
    campus_site TEXT NOT NULL,
    district TEXT NOT NULL REFERENCES districts(district),
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    coord_source TEXT NOT NULL,
    approximate_location INTEGER NOT NULL,   -- needs_review = yes in campuses.csv
    handbook_listed INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'candidate')),
    institution_id TEXT,                     -- KG Institution node (campus-level if one exists)
    university_id TEXT NOT NULL,             -- KG Institution node of the university
    snap_m REAL
);
CREATE TABLE travel (
    origin_id TEXT NOT NULL REFERENCES ds_divisions(origin_id),
    campus_id TEXT NOT NULL REFERENCES campuses(campus_id),
    road_km REAL NOT NULL,
    drive_min REAL NOT NULL,
    straight_km REAL NOT NULL,
    PRIMARY KEY (origin_id, campus_id)
) WITHOUT ROWID;
CREATE INDEX travel_by_campus ON travel(campus_id, drive_min);
CREATE INDEX travel_by_origin ON travel(origin_id, drive_min);
CREATE TABLE quality_flags (
    origin_id TEXT, campus_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE offering_sites (               -- where each KG offering (UGC uni-code) is taught
    uni_code TEXT PRIMARY KEY,
    offering_id TEXT NOT NULL,              -- KG Offering node
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    institution_id TEXT NOT NULL,
    campus_id TEXT NOT NULL REFERENCES campuses(campus_id),
    rule TEXT NOT NULL,                     -- owner_override | campus_institution | single_site | faculty_rule | main_campus
    needs_review INTEGER NOT NULL,
    note TEXT
);
CREATE VIEW travel_detail AS
SELECT d.origin_id, d.ds_division, d.district AS origin_district, d.province,
       c.campus_id, c.university, c.campus_site, c.district AS campus_district,
       c.status, c.approximate_location, c.institution_id, c.university_id,
       t.road_km, t.drive_min, t.straight_km,
       round(t.drive_min * (SELECT value FROM settings WHERE key = 'bus_factor')
             + (SELECT value FROM settings WHERE key = 'bus_overhead_min')) AS bus_min_est,
       d.district = c.district AS same_district
FROM travel t
JOIN ds_divisions d USING (origin_id)
JOIN campuses c USING (campus_id);
CREATE VIEW offering_travel AS
SELECT t.*, s.uni_code, s.course_code, s.course_name, s.offering_id,
       s.needs_review AS site_needs_review
FROM offering_sites s JOIN travel_detail t USING (campus_id);
"""


class BuildError(RuntimeError):
    pass


def _read(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise BuildError(f"Missing input file: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], key: str, where: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        raise BuildError(f"{where}: {key} is missing or not a number ({row.get(key)!r})") from None


def _yes(value: str) -> int:
    return 1 if str(value).strip().lower() in {"yes", "y", "true", "1"} else 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_decisions(data_dir: Path) -> dict:
    path = data_dir / DECISIONS_JSON
    if not path.is_file():
        return {"site_decisions": {}, "bus_estimate": DEFAULT_BUS, "offering_sites": {}}
    decisions = json.loads(path.read_text(encoding="utf-8"))
    for cid, decision in decisions.get("site_decisions", {}).items():
        if decision.get("status") not in {"confirmed", "excluded"}:
            raise BuildError(f"{DECISIONS_JSON}: site {cid} status must be confirmed or excluded")
    return decisions


def load_inputs(data_dir: Path) -> dict:
    campuses = _read(data_dir / CAMPUSES_CSV)
    long_rows = _read(data_dir / LONG_CSV)
    decisions = load_decisions(data_dir)
    site_decisions = decisions.get("site_decisions", {})
    flags: list[tuple] = []

    known = {row["campus_id"].strip() for row in campuses}
    unknown = set(site_decisions) - known
    if unknown:
        raise BuildError(f"{DECISIONS_JSON}: unknown campus ids {sorted(unknown)}")
    excluded = {cid for cid, d in site_decisions.items() if d["status"] == "excluded"}

    campus_rows = []
    for row in campuses:
        cid = row["campus_id"].strip()
        if cid in excluded:
            continue
        university = row["university"].strip()
        if university not in UNIVERSITY_IDS:
            raise BuildError(f"campuses.csv: no KG institution for university {university!r}")
        decision = site_decisions.get(cid, {})
        approximate = _yes(row["needs_review"])
        if decision.get("status") == "confirmed" and not row["coord_source"].strip().lower().startswith("approx"):
            approximate = 0                    # it was under review only because it was a candidate
        status = "candidate" if is_candidate(row["campus_site"]) and not decision else "confirmed"
        site_name = row["campus_site"].strip()
        if status == "confirmed" and is_candidate(site_name):
            # 'Faculty of Engineering (candidate 2: Siddamulla, Kottawa)' -> 'Faculty of Engineering, Siddamulla, Kottawa'
            site_name = CANDIDATE_LABEL_RE.sub(r", \1", site_name)
        campus_rows.append({
            "campus_id": cid, "site_no": row["site_no"].strip(), "university": university,
            "campus_site": site_name, "district": row["district"].strip(),
            "lat": _float(row, "lat", cid), "lon": _float(row, "lon", cid),
            "coord_source": row["coord_source"].strip(), "approximate_location": approximate,
            "handbook_listed": _yes(row["handbook_listed"]), "status": status,
            "institution_id": INSTITUTION_IDS.get(cid, UNIVERSITY_IDS[university]),
            "university_id": UNIVERSITY_IDS[university], "snap_m": None,
        })
        if approximate:
            flags.append((None, cid, "approximate_campus_location", row["coord_source"].strip()))
        if status == "candidate":
            flags.append((None, cid, "candidate_site",
                          "One of two possible locations for this faculty; confirm before use"))
    by_campus = {c["campus_id"]: c for c in campus_rows}
    if len(by_campus) != len(campus_rows):
        raise BuildError("campuses.csv: duplicate campus_id")

    origins: dict[str, dict] = {}
    travel: dict[tuple[str, str], dict] = {}
    for number, row in enumerate(long_rows, start=2):
        where = f"{LONG_CSV} line {number}"
        if row.get("error", "").strip():
            raise BuildError(f"{where}: routing error {row['error']!r}")
        oid, cid = row["origin_id"].strip(), row["campus_id"].strip()
        if cid in excluded:
            continue
        if cid not in by_campus:
            raise BuildError(f"{where}: unknown campus {cid!r}")
        origin = origins.setdefault(oid, {
            "origin_id": oid, "ds_division": row["ds_division"].strip(),
            "district": row["district"].strip(), "province": row["province"].strip(),
            "point_source": row["origin_point_source"].strip(),
            "snap_m": _float(row, "origin_snap_m", where),
        })
        if (origin["ds_division"], origin["district"]) != (row["ds_division"].strip(), row["district"].strip()):
            raise BuildError(f"{where}: origin {oid} has inconsistent names")
        if (oid, cid) in travel:
            raise BuildError(f"{where}: duplicate pair {oid} -> {cid}")
        record = {
            "origin_id": oid, "campus_id": cid,
            "road_km": _float(row, "road_km", where), "drive_min": _float(row, "drive_min", where),
            "straight_km": _float(row, "straight_km", where),
        }
        if record["road_km"] < 0 or record["drive_min"] < 0:
            raise BuildError(f"{where}: negative distance or time")
        travel[(oid, cid)] = record
        by_campus[cid]["snap_m"] = _float(row, "campus_snap_m", where)
        if record["straight_km"] > 1:
            ratio = record["road_km"] / record["straight_km"]
            if not RATIO_RANGE[0] <= ratio <= RATIO_RANGE[1]:
                flags.append((oid, cid, "unusual_road_ratio",
                              f"road {record['road_km']} km vs straight line {record['straight_km']} km "
                              f"(x{ratio:.2f})"))

    missing = [(o, c) for o in origins for c in by_campus if (o, c) not in travel]
    if missing:
        raise BuildError(f"{len(missing)} DS-division/campus pairs missing, e.g. {missing[:3]}")

    # the wide files must say exactly what the long file says
    for field, name in WIDE_CSVS.items():
        path = data_dir / name
        if not path.is_file():
            continue
        for row in _read(path):
            for column, value in row.items():
                if column in {"origin_id", "ds_division", "district"}:
                    continue
                cid = column.split("_", 1)[1] if "_" in column else column
                if cid in excluded:
                    continue
                expected = travel.get((row["origin_id"], cid))
                if expected is None:
                    raise BuildError(f"{name}: unknown pair {row['origin_id']} -> {column}")
                if abs(float(value) - expected[field]) > WIDE_TOLERANCE:
                    raise BuildError(f"{name}: {row['origin_id']} -> {cid} {field} {value} "
                                     f"differs from {LONG_CSV} ({expected[field]})")

    districts = {}
    for origin in origins.values():
        districts.setdefault(origin["district"], origin["province"])
    unknown = {c["district"] for c in campus_rows} - set(districts)
    if unknown:
        raise BuildError(f"Campus districts not among DS-division districts: {sorted(unknown)}")
    return {"campuses": campus_rows, "origins": list(origins.values()),
            "travel": list(travel.values()), "districts": districts, "flags": flags,
            "decisions": decisions, "excluded": sorted(excluded)}


def place(data: dict, graph_path: Path) -> list:
    from .course_sites import place_offerings

    if not graph_path.is_file():
        raise BuildError(f"Knowledge graph not found at {graph_path}; build it first "
                         "(RAG_Agent.graph_pipeline.build_graph) or pass --kg-graph")
    from RAG_Agent.graph_pipeline.build_graph import load_graph

    overrides = data["decisions"].get("offering_sites", {})
    try:
        return place_offerings(load_graph(graph_path), data["campuses"], overrides)
    except ValueError as exc:
        raise BuildError(str(exc)) from exc


def write_review(placements: list, path: Path) -> Path:
    fields = ["uni_code", "course_name", "institution_id", "campus_id", "rule", "note", "confirmed_campus_id"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for p in placements:
            if p.needs_review:
                writer.writerow({**p.__dict__, "confirmed_campus_id": ""})
    return path


def build(data_dir: Path = DATA_DIR, db_path: Path = DEFAULT_DB,
          graph_path: Path = KG_GRAPH) -> dict[str, int]:
    data = load_inputs(data_dir)
    placements = place(data, graph_path)
    bus = {**DEFAULT_BUS, **data["decisions"].get("bus_estimate", {})}
    tmp = db_path.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    connection = sqlite3.connect(tmp)
    try:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO districts VALUES (?, ?)", sorted(data["districts"].items()))
        connection.executemany(
            "INSERT INTO ds_divisions VALUES (:origin_id, :ds_division, :district, :province, "
            ":point_source, :snap_m)", data["origins"])
        connection.executemany(
            "INSERT INTO campuses VALUES (:campus_id, :site_no, :university, :campus_site, :district, "
            ":lat, :lon, :coord_source, :approximate_location, :handbook_listed, :status, "
            ":institution_id, :university_id, :snap_m)", data["campuses"])
        connection.executemany(
            "INSERT INTO travel VALUES (:origin_id, :campus_id, :road_km, :drive_min, :straight_km)",
            data["travel"])
        connection.executemany("INSERT INTO quality_flags VALUES (?, ?, ?, ?)", data["flags"])
        connection.executemany("INSERT INTO settings VALUES (?, ?)", [
            ("bus_factor", float(bus["factor"])), ("bus_overhead_min", float(bus["overhead_min"]))])
        connection.executemany(
            "INSERT INTO offering_sites VALUES (:uni_code, :offering_id, :course_code, :course_name, "
            ":institution_id, :campus_id, :rule, :needs_review, :note)",
            [{**p.__dict__, "needs_review": int(p.needs_review)} for p in placements])
        meta = {
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "time_measure": "free-flow car driving time from the routing engine (minutes)",
            "distance_measure": "road distance (km)",
            "bus_estimate": bus.get("label", f"car time x {bus['factor']} + {bus['overhead_min']} min"),
            "excluded_sites": ", ".join(data["excluded"]),
        }
        for name in [CAMPUSES_CSV, LONG_CSV, *WIDE_CSVS.values(), DECISIONS_JSON]:
            if (data_dir / name).is_file():
                meta[f"sha256:{name}"] = _sha256(data_dir / name)
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", sorted(meta.items()))
        connection.commit()
    finally:
        connection.close()
    tmp.replace(db_path)
    write_review(placements, db_path.parent / "offering_sites_review.csv")
    return {"offerings_placed": len(placements),
            "offerings_to_review": sum(p.needs_review for p in placements),"districts": len(data["districts"]), "ds_divisions": len(data["origins"]),
            "campuses": len(data["campuses"]), "pairs": len(data["travel"]),
            "quality_flags": len(data["flags"])}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the DS-division x campus travel database.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--kg-graph", type=Path, default=KG_GRAPH)
    args = parser.parse_args(argv)
    try:
        counts = build(args.data_dir, args.db, args.kg_graph)
    except BuildError as exc:
        parser.exit(1, f"Build failed: {exc}\n")
    print(f"Wrote {args.db}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
