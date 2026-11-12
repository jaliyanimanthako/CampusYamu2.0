"""Arts Stream subject-selection rules (UGC Handbook 2024/2025, Section 2.2.1.1).

The handbook classifies Arts subjects into four baskets and states selection
rules per basket, with exceptions. The extraction pipeline stores those rules
as references (basket names, exceptions) that the generic rule evaluator
cannot execute; this module executes them directly from the handbook wording:

* three subjects, all from the Arts baskets (2.2.1.1: "passes in three
  subjects ... from the following baskets");
* basket 01: at least one subject, except (1) three National Languages,
  (2) a combination of National and Classical languages, (3) two languages
  from basket 04 plus a basket 02 or 03 subject; at most one Technological
  subject (item 11: "One subject from Technological Subjects");
* basket 02: at most two; a religion and its own civilization never together;
* basket 03: at most two, never two from the same subject area;
* basket 04: at most two, except three National Languages, or at least one
  National plus two Classical languages; never three Classical or three
  Foreign languages.

Basket membership comes from ``reference/doe_al_subjects.json`` (handbook
basket lists mapped to official subjects). Subjects are handbook rule names;
two official subjects of one area (e.g. Oriental Music, Western Music) both
appear as that area's name ("Music"), which is what the same-area rule needs.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from .al_clause_parsers import OFFICIAL_SUBJECTS_PATH

ARTS_SECTION = "2.2.1.1"
NATIONAL_LANGUAGES = frozenset({"Sinhala", "Tamil", "English"})
CLASSICAL_LANGUAGES = frozenset({"Arabic", "Pali", "Sanskrit"})
FOREIGN_LANGUAGES = frozenset(
    {"Chinese", "French", "German", "Hindi", "Japanese", "Malay", "Russian", "Korean"}
)
TECHNOLOGICAL_SUBJECTS = frozenset(
    {
        "Civil Technology",
        "Electrical, Electronic & Information Technology",
        "Agro Technology",
        "Mechanical Technology",
        "Food Technology",
        "Bio-Resource Technology",
    }
)
RELATED_CIVILIZATION = {
    "Buddhism": "Buddhist Civilization",
    "Hinduism": "Hindu Civilization",
    "Christianity": "Christian Civilization",
    "Islam": "Islamic Civilization",
}


def _load_baskets() -> dict[str, int]:
    data = json.loads(OFFICIAL_SUBJECTS_PATH.read_text(encoding="utf-8"))
    baskets: dict[str, int] = {}
    for item in [*data["subjects"], *data.get("handbook_only_subjects", [])]:
        if item.get("rule_subject") and item.get("arts_basket"):
            baskets[item["rule_subject"]] = int(item["arts_basket"])
    return baskets


BASKET_OF = _load_baskets()


@dataclass(frozen=True)
class ArtsCheck:
    eligible: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def check_arts_combination(subjects: Sequence[str]) -> ArtsCheck:
    """Apply Section 2.2.1.1 to a student's three (passed) subjects."""

    subjects = list(subjects)
    reasons: list[str] = []
    if len(subjects) != 3:
        return ArtsCheck(False, ("Arts requires exactly three subjects",))
    outside = [s for s in subjects if s not in BASKET_OF]
    if outside:
        reasons.append(f"Not an Arts basket subject: {', '.join(outside)}")
        return ArtsCheck(False, tuple(reasons))

    count = Counter(BASKET_OF[s] for s in subjects)
    national = sum(s in NATIONAL_LANGUAGES for s in subjects)
    classical = sum(s in CLASSICAL_LANGUAGES for s in subjects)
    foreign = sum(s in FOREIGN_LANGUAGES for s in subjects)
    three_national = national == 3
    national_and_classical = national + classical == 3 and national >= 1 and classical >= 1
    two_languages_plus_02_03 = count[4] == 2 and (count[2] == 1 or count[3] == 1)

    # Basket 01.
    if count[1] == 0 and not (three_national or national_and_classical or two_languages_plus_02_03):
        reasons.append(
            "At least one subject from basket 01 is required (exceptions: three National "
            "Languages; National and Classical languages; two languages plus a basket 02 "
            "or 03 subject)"
        )
    if sum(s in TECHNOLOGICAL_SUBJECTS for s in subjects) > 1:
        reasons.append("Only one Technological subject may be selected from basket 01")

    # Basket 02.
    if count[2] > 2:
        reasons.append("At most two subjects from basket 02 (Religions and Civilizations)")
    for religion, civilization in RELATED_CIVILIZATION.items():
        if religion in subjects and civilization in subjects:
            reasons.append(f"{religion} cannot be offered with {civilization}")

    # Basket 03.
    if count[3] > 2:
        reasons.append("At most two subjects from basket 03 (Aesthetic Studies)")
    repeated_areas = [s for s, n in Counter(s for s in subjects if BASKET_OF[s] == 3).items() if n > 1]
    if repeated_areas:
        reasons.append(
            "Two basket 03 subjects cannot come from the same subject area: "
            + ", ".join(repeated_areas)
        )

    # Basket 04.
    if count[4] > 2 and not (three_national or (national >= 1 and classical == 2)):
        reasons.append(
            "At most two subjects from basket 04 (exceptions: three National Languages; "
            "one National plus two Classical languages)"
        )
    if classical == 3:
        reasons.append("Three Classical Languages cannot be offered")
    if foreign == 3:
        reasons.append("Three Foreign Languages cannot be offered")
    return ArtsCheck(not reasons, tuple(reasons))


def all_arts_subjects(subjects: Sequence[str]) -> bool:
    return len(subjects) == 3 and all(s in BASKET_OF for s in subjects)


# Opaque conditions (see al_rule_semantics.compile_rule) whose meaning is the
# Arts rules above, keyed by (constraint_type, normalised group_name, count).
def resolve_arts_condition(key: tuple[str, ...], subjects: Sequence[str]) -> bool | None:
    kind, name, count_text = key
    count = int(count_text or 0)
    baskets = Counter(BASKET_OF.get(s) for s in subjects)
    if (kind, name) == ("allowed_combination", "arts stream subjects selected per section 2.2.1.1"):
        return check_arts_combination(subjects).eligible
    if kind == "minimum_count" and name in {"arts stream subjects", "arts subject baskets"}:
        return all_arts_subjects(subjects) and len(subjects) >= count
    if kind == "maximum_count":
        if name == "languages":
            return baskets[4] <= count
        if name in {"religions and civilizations basket", "basket 02"}:
            return baskets[2] <= count
        if name == "technological subject":
            return sum(s in TECHNOLOGICAL_SUBJECTS for s in subjects) <= count
    return None
