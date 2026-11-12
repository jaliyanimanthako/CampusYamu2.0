"""Which campus site each offering (UGC uni-code) is taught at.

Offerings in the knowledge graph belong to an institution, but several
universities teach on more than one site (Ruhuna Engineering at Hapugala,
Moratuwa Medicine at Kalutara, Jaffna Engineering at Kilinochchi, ...). Each
offering is placed by the first rule that applies:

1. ``owner_override``   -- data/travel_decisions.json ``offering_sites``
2. ``campus_institution`` -- the KG institution is itself a campus (Sripalee,
   UCSC, Trincomalee Campus, SVIAS): its only site
3. ``single_site``      -- the university has one site in campuses.csv
4. ``faculty_rule``     -- a course-code rule below (Medicine -> Faculty of
   Medicine site, Technology-stream courses -> Faculty of Technology site, ...)
5. ``main_campus``      -- otherwise the university's main site

Rules marked ``review`` are reasonable guesses that the owner should confirm;
they are written to the review list (``offering_sites_review.csv``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

TECHNOLOGY = {"102", "103", "104"}                       # ET, BST, ICT (Technology stream)
ENGINEERING = {"008", "009", "010"}
ALLIED_HEALTH = {"037", "050", "051", "052", "054", "083", "115", "116", "138"}


@dataclass(frozen=True)
class Rule:
    university: str            # KG institution id suffix
    codes: frozenset[str]      # 3-digit UGC course codes
    campus_id: str
    review: bool
    note: str


def _rule(university: str, codes: Iterable[str], campus_id: str, note: str, review: bool = False) -> Rule:
    return Rule(university, frozenset(codes), campus_id, review, note)


FACULTY_RULES: list[Rule] = [
    # Medicine (handbook §2.2.3.1 'Location -' lines)
    _rule("university-of-colombo", {"001"}, "UOC-MED", "Faculty of Medicine, Kynsey Rd (§2.2.3.1)"),
    _rule("university-of-moratuwa", {"001"}, "UOM-MED", "Faculty of Medicine, Kalutara (§2.2.3.1)"),
    _rule("university-of-kelaniya", {"001"}, "UOK-MED", "Faculty of Medicine, Ragama (§2.2.3.1)"),
    _rule("university-of-ruhuna", {"001"}, "UOR-MED", "Faculty of Medicine, Karapitiya (§2.2.3.1)"),
    _rule("sabaragamuwa-university-of-sri-lanka", {"001"}, "SUSL-MED", "Faculty of Medicine, Ratnapura (§2.2.3.1)"),
    _rule("rajarata-university-of-sri-lanka", {"001"}, "RUSL-MED", "Faculty of Medicine & Allied Sciences, Saliyapura (§2.2.3.1)"),
    _rule("eastern-university-sri-lanka", {"001"}, "EUSL-FHCS", "Faculty of Health-Care Sciences, Batticaloa (§2.2.3.1)"),
    # Allied health: usually taught with the medical faculty -- to confirm
    _rule("university-of-colombo", {"037", "054", "138"}, "UOC-MED", "allied health with the Faculty of Medicine", True),
    _rule("university-of-ruhuna", {"037", "051", "052"}, "UOR-MED", "Faculty of Allied Health Sciences, Galle (near Karapitiya)", True),
    _rule("university-of-kelaniya", {"083", "115"}, "UOK-MED", "taught by the Faculty of Medicine, Ragama", True),
    _rule("eastern-university-sri-lanka", {"037"}, "EUSL-FHCS", "Faculty of Health-Care Sciences", True),
    _rule("rajarata-university-of-sri-lanka", {"050"}, "RUSL-MED", "Faculty of Medicine & Allied Sciences", True),
    # Indigenous medicine: their institutes are not in campuses.csv -- main campus as placeholder
    _rule("university-of-colombo", {"032", "033"}, "UOC-MAIN",
          "Institute of Indigenous Medicine (Rajagiriya) is not in campuses.csv", True),
    _rule("university-of-jaffna", {"036"}, "UOJ-MAIN",
          "Unit of Siddha Medicine (Kaithady) is not in campuses.csv", True),
    # Engineering
    _rule("university-of-sri-jayewardenepura", ENGINEERING, "USJ-ENG-SIDDAMULLA", "Faculty of Engineering, Siddamulla (owner)"),
    _rule("university-of-ruhuna", ENGINEERING, "UOR-ENG", "Faculty of Engineering, Hapugala (Annex (c))"),
    _rule("university-of-jaffna", ENGINEERING, "UOJ-KILI", "Faculty of Engineering, Kilinochchi premises"),
    # Technology stream (Faculties of Technology)
    _rule("university-of-colombo", TECHNOLOGY, "UOC-FOT", "Faculty of Technology, Pitipana"),
    _rule("university-of-sri-jayewardenepura", TECHNOLOGY, "USJ-FOT", "Faculty of Technology, Pitipana"),
    _rule("university-of-ruhuna", TECHNOLOGY, "UOR-FOT", "Faculty of Technology, Kamburupitiya"),
    _rule("university-of-ruhuna", {"095"}, "UOR-FOT", "Green Technology, assumed Faculty of Technology", True),
    _rule("university-of-jaffna", TECHNOLOGY, "UOJ-KILI", "Faculty of Technology, Kilinochchi premises"),
    # Agriculture and related
    _rule("university-of-ruhuna", {"093", "094"}, "UOR-AGRI", "Faculty of Agriculture, Mapalana (Annex (c))"),
    _rule("rajarata-university-of-sri-lanka", {"004"}, "RUSL-AGRI", "Faculty of Agriculture, Puliyankulama"),
    _rule("university-of-jaffna", {"004"}, "UOJ-KILI", "Faculty of Agriculture, Kilinochchi premises"),
    _rule("wayamba-university-of-sri-lanka", {"004"}, "WUSL-MAKANDURA",
          "Faculty of Agriculture & Plantation Management, Makandura (Annex (c))"),
    _rule("wayamba-university-of-sri-lanka", {"005", "087"}, "WUSL-LFN",
          "Faculty of Livestock, Fisheries & Nutrition, Makandura"),
    # Applied sciences
    _rule("south-eastern-university-of-sri-lanka", {"006", "013"}, "SEUSL-FAS",
          "Faculty of Applied Sciences, Sammanthurai"),
]

MAIN_SITE_SUFFIX = "-MAIN"


@dataclass(frozen=True)
class Placement:
    offering_id: str
    uni_code: str
    course_code: str
    course_name: str
    institution_id: str
    campus_id: str
    rule: str
    needs_review: bool
    note: str


def place_offerings(graph, campuses: list[dict], overrides: dict[str, str]) -> list[Placement]:
    """One Placement per KG Offering; raises when an offering cannot be placed."""

    by_institution: dict[str, list[dict]] = {}
    by_university: dict[str, list[dict]] = {}
    for campus in campuses:
        by_institution.setdefault(campus["institution_id"], []).append(campus)
        by_university.setdefault(campus["university_id"], []).append(campus)
    campus_ids = {c["campus_id"] for c in campuses}
    rules = {(r.university, code): r for r in FACULTY_RULES for code in r.codes}

    placements = []
    for node, attrs in sorted(graph.nodes(data=True)):
        if attrs["type"] != "Offering":
            continue
        institution = next(t for _, t, k in graph.out_edges(node, keys=True) if k == "AT_INSTITUTION")
        course = next(t for _, t, k in graph.out_edges(node, keys=True) if k == "OFFERS_COURSE")
        code, name, uni_code = graph.nodes[course]["code"], graph.nodes[course]["name"], attrs["uni_code"]

        def make(campus_id: str, rule: str, review: bool, note: str) -> Placement:
            if campus_id not in campus_ids:
                raise ValueError(f"{uni_code}: rule {rule} names unknown campus {campus_id}")
            return Placement(node, uni_code, code, name, institution, campus_id, rule, review, note)

        own = [c for c in by_institution.get(institution, []) if c["institution_id"] != c["university_id"]]
        sites = [c for c in by_university.get(institution, []) if c["institution_id"] == institution]
        rule = rules.get((institution.split(":", 1)[1], code))
        if uni_code in overrides:
            placements.append(make(overrides[uni_code], "owner_override", False, "data/travel_decisions.json"))
        elif len(own) == 1:
            placements.append(make(own[0]["campus_id"], "campus_institution", False, own[0]["campus_site"]))
        elif len(sites) == 1:
            placements.append(make(sites[0]["campus_id"], "single_site", False, sites[0]["campus_site"]))
        elif rule:
            placements.append(make(rule.campus_id, "faculty_rule", rule.review, rule.note))
        else:
            main = [c for c in sites if c["campus_id"].endswith(MAIN_SITE_SUFFIX)]
            if len(main) != 1:
                raise ValueError(f"{uni_code} {name}: no rule and no single main campus for {institution}")
            placements.append(make(main[0]["campus_id"], "main_campus", False, main[0]["campus_site"]))
    return placements
