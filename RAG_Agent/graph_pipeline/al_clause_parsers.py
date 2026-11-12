"""Deterministic parsers for recurring G.C.E. (A/L) eligibility phrasings.

Each parser turns ONE ledger clause (plus, when the clause says "from the
following subjects", the bullet list that follows it) into the rule fields of
the A/L extraction schema. Parsers are deliberately narrow:

* every subject must resolve to the closed A/L subject vocabulary below;
* every stream must resolve to a known subject stream;
* any wording a parser does not fully understand returns ``None``.

The caller (``handbook_prose.deterministic_clause_proposal``) only converts a
unit when *every* A/L clause parses, so a partially understood unit always
falls back to the LLM harness instead of being half-converted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Sequence

# Closed vocabulary of G.C.E. (A/L) subjects used in the handbook's
# eligibility clauses, with the spellings that appear in the source.
AL_SUBJECTS = (
    "Accounting",
    "Agricultural Science",
    "Agro Technology",
    "Arabic",
    "Art",
    "Bio-Resource Technology",
    "Biology",
    "Biosystems Technology",
    "Buddhism",
    "Buddhist Civilization",
    "Business Statistics",
    "Business Studies",
    "Chemistry",
    "Chinese",
    "Christian Civilization",
    "Christianity",
    "Civil Technology",
    "Combined Mathematics",
    "Communication & Media Studies",
    "Dance",
    "Drama & Theatre",
    "Economics",
    "Electrical, Electronic & Information Technology",
    "Engineering Technology",
    "English",
    "Food Technology",
    "French",
    "Geography",
    "German",
    "Greek & Roman Civilization",
    "Higher Mathematics",
    "Hindi",
    "Hindu Civilization",
    "Hinduism",
    "History",
    "Home Economics",
    "Information & Communication Technology",
    "Islam",
    "Islamic Civilization",
    "Japanese",
    "Korean",
    "Logic & Scientific Method",
    "Malay",
    "Mathematics",
    "Mechanical Technology",
    "Music",
    "Pali",
    "Physics",
    "Political Science",
    "Russian",
    "Sanskrit",
    "Science for Technology",
    "Sinhala",
    "Tamil",
)
SUBJECT_ALIASES = {
    "accountancy": "Accounting",
    "communication and media studies": "Communication & Media Studies",
    "information and communication technology": "Information & Communication Technology",
    "ict": "Information & Communication Technology",
    "biosystem technology": "Biosystems Technology",
    "logic and scientific method": "Logic & Scientific Method",
    "logic & scientific methods": "Logic & Scientific Method",
    "logic and scientific methods": "Logic & Scientific Method",
    "drama and theatre": "Drama & Theatre",
    "arabic language": "Arabic",
    "english language": "English",
    # The handbook writes "Agriculture" in some option lists for the A/L
    # subject Agricultural Science (there is no A/L subject "Agriculture").
    "agriculture": "Agricultural Science",
    "dancing": "Dance",
    # common ways students write subject names
    "combined maths": "Combined Mathematics",
    "combined math": "Combined Mathematics",
    "c. maths": "Combined Mathematics",
    "c maths": "Combined Mathematics",
    "higher maths": "Higher Mathematics",
    "bio": "Biology",
}
OFFICIAL_SUBJECTS_PATH = (
    Path(__file__).resolve().parents[1] / "reference" / "doe_al_subjects.json"
)


def _official_subject_aliases() -> dict[str, str]:
    """Official Department of Examinations names -> handbook rule subjects."""

    data = json.loads(OFFICIAL_SUBJECTS_PATH.read_text(encoding="utf-8"))
    aliases: dict[str, str] = {}
    for item in [*data["subjects"], *data.get("old_syllabus_aliases", [])]:
        rule_subject = item.get("rule_subject")
        if not rule_subject:
            continue
        if rule_subject not in AL_SUBJECTS:
            raise ValueError(f"Official subject maps to unknown rule subject {rule_subject!r}")
        if item["name"] != rule_subject:
            aliases[item["name"].casefold()] = rule_subject
    return aliases


SUBJECT_ALIASES = {**_official_subject_aliases(), **SUBJECT_ALIASES}
STREAMS = (
    "Arts",
    "Commerce",
    "Biological Science",
    "Physical Science",
    "Engineering Technology",
    "Biosystems Technology",
    "Information Communication Technology",
)
STREAM_ALIASES = {
    "art": "Arts",
    "biosystem technology": "Biosystems Technology",
}
COUNTS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3}

_AL = r"\s+at\s+the\s+G\.C\.E\.\s*\(Advanced Level\)\s*Examination"
_END = r"\s*[.;:,]?$"
_LIST_MARKER = re.compile(
    r"^(?:[-*]\s*)?(?:\((?:[ivx]{1,4}|[a-h])\)|(?:[ivx]{1,4}|[a-h])[).]|I{1,3}\s)\s*\.?\s*",
    re.IGNORECASE,
)
_PAREN_ABBREVIATION = re.compile(r"\s*\([A-Z]{2,5}\)")
_GRADES = ("A", "B", "C", "S")


def normalize_clause(text: str) -> str:
    """Normalize quotes, Markdown emphasis, list markers and whitespace."""

    value = (
        text.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("**", "")
    )
    value = " ".join(value.split())
    value = re.sub(r"^[-*]\s+", "", value)
    value = _LIST_MARKER.sub("", value)
    return value.strip()


def canonical_subject(value: str) -> str | None:
    name = _PAREN_ABBREVIATION.sub("", normalize_clause(value))
    name = re.sub(r"\s*-\s*", "-", name).strip(" .;:,").strip()
    if not name:
        return None
    for subject in AL_SUBJECTS:
        if subject.casefold() == name.casefold():
            return subject
    return SUBJECT_ALIASES.get(name.casefold())


def canonical_stream(value: str) -> str | None:
    name = re.sub(r"^(?:the)\s+", "", value.strip(), flags=re.IGNORECASE)
    name = re.sub(r"\s+Stream$", "", name, flags=re.IGNORECASE).strip()
    for stream in STREAMS:
        if stream.casefold() == name.casefold():
            return stream
    return STREAM_ALIASES.get(name.casefold())


def _split_list(value: str) -> list[str]:
    parts = [part.strip() for part in re.split(r",\s*", value) if part.strip()]
    if not parts:
        return []
    last = re.split(r"\s+and\s+", parts[-1], maxsplit=1)
    return [*parts[:-1], *last]


def parse_subject_list(value: str) -> list[tuple[str, list[str]]] | None:
    """Parse 'A, B and C' / 'A, B or C' items; each item may be 'X or Y'."""

    items: list[tuple[str, list[str]]] = []
    for token in _split_list(value):
        options = [canonical_subject(part) for part in re.split(r"\s+or\s+", token)]
        if not options or any(option is None for option in options):
            return None
        primary, *alternatives = options  # type: ignore[misc]
        items.append((primary, alternatives))  # type: ignore[arg-type]
    return items or None


def parse_stream_list(value: str) -> list[str] | None:
    streams = [canonical_stream(part) for part in re.split(r"\s+or\s+", value)]
    if not streams or any(stream is None for stream in streams):
        return None
    return list(dict.fromkeys(streams))  # type: ignore[arg-type]


def _grades(**counts: int) -> dict[str, Any]:
    return {
        "required_a_grades": counts.get("a", 0),
        "required_b_grades": counts.get("b", 0),
        "required_c_grades": counts.get("c", 0),
        "required_s_grades": counts.get("s", 0),
    }


def _grade_requirement(
    subject: str, grade: str, alternatives: Sequence[str], condition: str
) -> dict[str, Any]:
    return {
        "subject": subject,
        "minimum_grade": grade,
        "alternatives": list(alternatives),
        "condition": condition,
    }


def _constraint(
    constraint_type: str,
    group_name: str,
    count: int,
    condition: str,
    subjects: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "constraint_type": constraint_type,
        "group_name": group_name,
        "subjects": list(subjects),
        "count": count,
        "condition": condition,
    }


def _spec(
    requirement_type: str,
    condition: str,
    *,
    streams: Sequence[str] = (),
    subjects: Sequence[str] = (),
    grades: dict[str, Any] | None = None,
    subject_grades: Sequence[dict[str, Any]] = (),
    constraints: Sequence[dict[str, Any]] = (),
    cgp_percentage: int = 0,
    consumed: int = 0,
    parser: str,
) -> dict[str, Any]:
    minimum_grades = {**(grades or _grades()), "grade_condition_text": ""}
    if any(minimum_grades[key] for key in minimum_grades if key != "grade_condition_text"):
        minimum_grades["grade_condition_text"] = condition
    return {
        "requirement_type": requirement_type,
        "eligible_streams": list(streams),
        "subjects": list(subjects),
        "subject_groups": [],
        "minimum_grades": minimum_grades,
        "subject_grade_requirements": list(subject_grades),
        "common_general_paper": {
            "required": bool(cgp_percentage),
            "minimum_percentage": cgp_percentage,
            "condition": condition if cgp_percentage else "",
        },
        "selection_constraints": list(constraints),
        "consumed_following_lines": consumed,
        "parser": parser,
    }


def _exact_subjects(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least (three) 'S' grades in Chemistry, Physics and Biology (at A/L).'"""

    match = re.match(
        r"^(?:(?:A candidate )?should have obtained )?at least (?:three )?'S' grades "
        r"(?:in|for) (?P<subjects>.+?)(?:" + _AL + r")?" + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    items = parse_subject_list(match.group("subjects"))
    if items is None or len(items) < 2:
        return None
    return _spec(
        "al_subject_combination",
        raw,
        subjects=[subject for subject, _ in items],
        grades=_grades(s=len(items)),
        subject_grades=[
            _grade_requirement(subject, "S", alternatives, raw)
            for subject, alternatives in items
        ],
        parser="exact_subjects",
    )


def _any_three_subjects(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least 'S' grades in any three subjects at A/L.' (+ optional 'must include')."""

    match = re.match(
        r"^(?:Candidates with )?at least (?:Ordinary Passes \(S\)|'S' grades) in any three "
        r"subjects" + _AL + r"(?: are eligible)?\.?"
        r"(?:\s*However,? one must include a subject of (?P<required>.+?))?" + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    constraints: list[dict[str, Any]] = []
    if match.group("required"):
        items = parse_subject_list(match.group("required"))
        if items is None or len(items) != 1:
            return None
        primary, alternatives = items[0]
        constraints.append(
            _constraint(
                "required_one_of",
                "Required subject",
                1,
                raw,
                [primary, *alternatives],
            )
        )
    return _spec(
        "al_minimum_grades",
        raw,
        grades=_grades(s=3),
        constraints=constraints,
        parser="any_three_subjects",
    )


def _stream_subjects(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least 'S' grades in any three subjects in the Commerce Stream or ... at A/L.'"""

    match = re.match(
        r"^at least (?:three )?'S' grades (?:in|for) (?:(?:any |the )?three subjects in )?"
        r"(?:the )?(?P<streams>[A-Za-z ]+? Stream(?: or (?:the )?[A-Za-z ]+? Stream)*)"
        + _AL
        + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    streams = parse_stream_list(match.group("streams"))
    if streams is None:
        return None
    return _spec(
        "al_stream_eligibility",
        raw,
        streams=streams,
        grades=_grades(s=3),
        parser="stream_subjects",
    )


_CHOICE_TAIL = re.compile(
    r"(?:^|,?\s*(?:and\s+)?)(?:for\s+)?(?:at least\s+)?(?:the\s+)?"
    r"(?:(?P<third>third subject)|(?:any\s+)?(?P<count>one|two|three)(?:\s+other)?"
    r"(?:\s+subjects?)?(?:\s+of)?)\s+(?:from\s+)?(?:the\s+)?"
    r"(?:following(?:\s+list)?(?:\s+of)?(?:\s+subjects)?|given below|listed below|among)$",
    re.IGNORECASE,
)
_METADATA_BULLET = re.compile(
    r"^(?:Degree Programmes?|Available|Duration|Medium|Location|Fields? of)\b|^:",
    re.IGNORECASE,
)


def _subject_bullets(following: Sequence[str]) -> tuple[list[str], int] | None:
    """Read the leading run of subject bullets ('X' or 'X/ Y/ Z').

    Returns (options, consumed) or None when the run is followed by anything
    other than programme metadata or the end of the bullet list.
    """

    options: list[str] = []
    consumed = 0
    for line in following:
        parts = [
            canonical_subject(part)
            for part in re.split(r"\s*/\s*|\s+or\s+", normalize_clause(line))
        ]
        if not parts or any(part is None for part in parts):
            break
        options.extend(part for part in parts if part not in options)  # type: ignore[misc]
        consumed += 1
    if consumed < len(following):
        stop = normalize_clause(following[consumed])
        # A list may end at programme metadata or at an "or"/"and" line that
        # joins it to the next requirement (handled by the caller).
        if not _METADATA_BULLET.match(stop) and not re.fullmatch(
            r"(?:<sup>)?\s*(?:or|and)\s*(?:</sup>)?", stop, re.IGNORECASE
        ):
            return None
    return options, consumed


# Heads of "choose N from the following list" clauses: (pattern, grade kind).
# "S" heads: the listed choices are 'S' passes like the fixed subjects.
# "passed_three" heads: three passes overall, N of them at the stated grade.
_CHOICE_HEADS = (
    (
        r"^(?:A candidate should have obtained )?at least (?:three )?"
        r"(?:'S' grades|Ordinary Passes \(S\)) (?:in|for) ",
        "S",
    ),
    (
        r"^The candidates should have passed the three subjects with at least "
        r"'(?P<grade>[ABC])' grades in ",
        "passed_three",
    ),
    (r"^Three passes including at least an? '(?P<grade>[ABC])' grade in ", "passed_three"),
)


def _choice_from_list(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least 'S' grades in Biology, Chemistry and the third subject from the following subjects;'"""

    for head, kind in _CHOICE_HEADS:
        match = re.match(
            head + r"(?P<body>.+?)(?:" + _AL + r")?" + _END, text, re.IGNORECASE
        )
        if match is not None:
            break
    else:
        return None
    body = match.group("body").strip()
    tail = _CHOICE_TAIL.search(body)
    if tail is None:
        return None
    count = 1 if tail.group("third") else COUNTS[tail.group("count").casefold()]
    fixed_text = body[: tail.start()].strip(" ,")
    fixed = parse_subject_list(fixed_text) if fixed_text else []
    if fixed is None:
        return None
    bullets = _subject_bullets(following)
    if bullets is None:
        return None
    options, consumed = bullets
    if len(options) < max(2, count):
        return None
    if kind == "S":
        grade = "S"
        grades = _grades(s=len(fixed) + count)
    else:
        if fixed:
            return None
        grade = match.group("grade").upper()
        grades = _grades(**{grade.lower(): count, "s": 3 - count})
    group = "Listed subject options" + ("" if grade == "S" else f" (at least '{grade}')")
    return _spec(
        "al_subject_combination",
        raw,
        subjects=[subject for subject, _ in fixed],
        grades=grades,
        subject_grades=[
            _grade_requirement(subject, "S", alternatives, raw)
            for subject, alternatives in fixed
        ],
        constraints=[
            _constraint(
                "required_one_of" if count == 1 else "minimum_count",
                group,
                count,
                raw,
                options,
            )
        ],
        consumed=consumed,
        parser="choice_from_list",
    )


_COMBINATION_MARKER = re.compile(r"\((?:[ivx]{1,4}|\d{1,2})\)\.?", re.IGNORECASE)


def _combinations(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least three 'S' grades for one of the following combinations of subjects;'

    Each listed combination may contain slot alternatives ("Physics or
    Mathematics"); they are expanded so every allowed_combination constraint
    names exactly the three subjects it permits.
    """

    if not re.match(
        r"^at least (?:three )?'S' grades for (?:the three subjects in )?one of (?:the )?"
        r"following combinations of subjects(?:" + _AL + r")?" + _END,
        text,
        re.IGNORECASE,
    ):
        return None
    chunks: list[str] = []
    consumed = 0
    for line in following:
        value = normalize_clause(line) if not line.lstrip("-* ").startswith("(") else (
            line.replace("**", "").lstrip("-* ").strip()
        )
        if re.fullmatch(r"or", value, re.IGNORECASE):
            consumed += 1
            continue
        if not _COMBINATION_MARKER.match(value):
            break
        chunks.append(value)
        consumed += 1
    if not chunks or (
        consumed < len(following)
        and not _METADATA_BULLET.match(normalize_clause(following[consumed]))
    ):
        return None
    combinations: list[list[str]] = []
    for item in _COMBINATION_MARKER.split(" ".join(chunks)):
        item = item.strip(" ;,.")
        if not item:
            continue
        separator = ";" if ";" in item else ","
        slots_text = [
            re.sub(r"^and\s+", "", part.strip(), flags=re.IGNORECASE)
            for part in item.split(separator)
            if part.strip()
        ]
        if separator == "," and slots_text:
            slots_text = [*slots_text[:-1], *re.split(r"\s+and\s+", slots_text[-1])]
        slots: list[list[str]] = []
        for slot in slots_text:
            options = [canonical_subject(part) for part in re.split(r"\s+or\s+", slot)]
            if any(option is None for option in options):
                return None
            slots.append(options)  # type: ignore[arg-type]
        if len(slots) != 3:
            return None
        expanded: list[list[str]] = [[]]
        for slot in slots:
            expanded = [prefix + [option] for prefix in expanded for option in slot]
        for combination in expanded:
            if len(set(combination)) == 3 and not any(
                set(combination) == set(existing) for existing in combinations
            ):
                combinations.append(combination)
    if len(combinations) < 2:
        return None
    return _spec(
        "al_subject_combination",
        raw,
        grades=_grades(s=3),
        constraints=[
            _constraint(
                "allowed_combination",
                f"Allowed combination {index}",
                3,
                raw,
                combination,
            )
            for index, combination in enumerate(combinations, start=1)
        ],
        consumed=consumed,
        parser="combinations",
    )


def _fixed_plus_any(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least 'S' grades for Combined Mathematics and any other two subjects at A/L.'
    'At least a 'B' grade in Economics and at least 'S' grades for any other two subjects
    in Art Stream or Commerce Stream at A/L.'"""

    match = re.match(
        r"^at least (?:'S' grades (?:in|for) (?P<fixed>.+?)|an? '(?P<grade>[ABC])' grade in "
        r"(?P<graded>[A-Za-z& ]+?) and at least 'S' grades for),? (?:and )?(?:in )?any other "
        r"(?:(?P<count>one|two) )?subjects?(?: available)?"
        r"(?: in (?P<streams>[A-Za-z ]+? Stream(?: or [A-Za-z ]+? Stream)*))?" + _AL + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    count = COUNTS[(match.group("count") or "one").casefold()]
    streams: list[str] = []
    if match.group("streams"):
        parsed_streams = parse_stream_list(match.group("streams"))
        if parsed_streams is None:
            return None
        streams = parsed_streams
    if match.group("graded"):
        subject = canonical_subject(match.group("graded"))
        if subject is None:
            return None
        grade = match.group("grade").upper()
        fixed_grades = [_grade_requirement(subject, grade, [], raw)]
        grades = _grades(**{grade.lower(): 1, "s": count})
    else:
        items = parse_subject_list(match.group("fixed"))
        if items is None:
            return None
        fixed_grades = [_grade_requirement(s, "S", alts, raw) for s, alts in items]
        grades = _grades(s=len(items) + count)
    return _spec(
        "al_stream_eligibility" if streams else "al_subject_combination",
        raw,
        streams=streams,
        subjects=[item["subject"] for item in fixed_grades],
        grades=grades,
        subject_grades=fixed_grades,
        constraints=[
            _constraint("minimum_count", "Any other subjects", count, raw)
        ],
        parser="fixed_plus_any",
    )


def _arts_basket_reference(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'...any three subjects of the Arts Stream ..., selected according to the conditions
    specified in the Section 2.2.1.1 of this handbook.' (optionally '..., Biological Science
    Stream or Physical Science Stream'). The Arts basket rules themselves live on course 019
    (section 2.2.1.1); this rule references them instead of copying them."""

    match = re.match(
        r"^(?:In order to be eligible for this course of study, candidates should have obtained "
        r"at least Ordinary Passes \(S\)|At least 'S' grades) in any three subjects (?:of|in) the "
        r"Arts Stream,?(?:" + _AL + r",)? selected according to the conditions specified in "
        r"the Section (?P<section>2\.2\.1\.1) of this handbook"
        r"(?:, (?P<streams>[A-Za-z ]+? Stream(?: or [A-Za-z ]+? Stream)*))?(?:" + _AL + r")?"
        + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    streams = ["Arts"]
    if match.group("streams"):
        extra = parse_stream_list(match.group("streams"))
        if extra is None:
            return None
        streams.extend(stream for stream in extra if stream not in streams)
    return _spec(
        "al_stream_eligibility",
        raw,
        streams=streams,
        grades=_grades(s=3),
        constraints=[
            _constraint(
                "allowed_combination",
                f"Arts Stream subjects selected per Section {match.group('section')}",
                3,
                raw,
            )
        ],
        parser="arts_basket_reference",
    )


def _physical_condition(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'In addition, the candidates should be a minimum of 4'10" in height and should
    not have any kind of deformity. ...' -- a non-A/L admission condition kept
    verbatim (in ``conditions``) as an other_admission_requirement."""

    if not re.match(
        r"^(?:In addition,? )?(?:the )?candidates should be a minimum of [^.]{1,20} in height\b",
        text,
        re.IGNORECASE,
    ):
        return None
    return _spec("other_admission_requirement", raw, parser="physical_condition")


def _one_of_with_grade(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least a 'C' grade in Combined Mathematics or Physics or Higher Mathematics;'"""

    match = re.match(
        r"^at least an? '(?P<grade>[ABC])' grade in (?P<subjects>[^,;]+?(?:\s+or\s+[^,;]+?)+)"
        r"(?:" + _AL + r")?" + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    options = [canonical_subject(part) for part in re.split(r"\s+or\s+", match.group("subjects"))]
    if any(option is None for option in options) or len(options) < 2:
        return None
    grade = match.group("grade").upper()
    return _spec(
        "al_subject_choice",
        raw,
        grades=_grades(**{grade.lower(): 1}),
        subject_grades=[_grade_requirement(options[0], grade, options[1:], raw)],  # type: ignore[arg-type]
        constraints=[
            _constraint("required_one_of", f"'{grade}' grade subject", 1, raw, options)  # type: ignore[arg-type]
        ],
        parser="one_of_with_grade",
    )


def _grade_counts_in_subjects(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least two 'C' grades and a 'S' grade in Biology, Chemistry and Physics at A/L.'"""

    match = re.match(
        r"^at least (?P<n1>a|an|one|two|three) '(?P<g1>[ABC])' grades? and (?:at least )?"
        r"(?P<n2>a|an|one|two) '(?P<g2>[ABCS])' grades? in (?P<subjects>.+?)" + _AL + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    items = parse_subject_list(match.group("subjects"))
    n1, n2 = COUNTS[match.group("n1").casefold()], COUNTS[match.group("n2").casefold()]
    g1, g2 = match.group("g1").upper(), match.group("g2").upper()
    if items is None or len(items) != n1 + n2 or g1 == g2:
        return None
    return _spec(
        "al_minimum_grades",
        raw,
        subjects=[subject for subject, _ in items],
        grades=_grades(**{g1.lower(): n1, g2.lower(): n2}),
        subject_grades=[
            _grade_requirement(subject, "S", alternatives, raw)
            for subject, alternatives in items
        ],
        parser="grade_counts_in_subjects",
    )


def _per_subject_grades(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least a 'C' grade in Chemistry and 'S' grades in Physics and Biology at A/L.'"""

    match = re.match(
        r"^at least an? '(?P<g1>[ABC])' grade in (?P<s1>[A-Za-z& ]+?) and (?:at least )?"
        r"'(?P<g2>[ABCS])' grades in (?P<s2>.+?)" + _AL + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    first = parse_subject_list(match.group("s1"))
    rest = parse_subject_list(match.group("s2"))
    if first is None or rest is None or len(first) != 1:
        return None
    g1, g2 = match.group("g1").upper(), match.group("g2").upper()
    requirements = [
        _grade_requirement(first[0][0], g1, first[0][1], raw),
        *(_grade_requirement(subject, g2, alts, raw) for subject, alts in rest),
    ]
    counts: dict[str, int] = {}
    for item in requirements:
        key = item["minimum_grade"].lower()
        counts[key] = counts.get(key, 0) + 1
    return _spec(
        "al_subject_combination",
        raw,
        subjects=[item["subject"] for item in requirements],
        grades=_grades(**counts),
        subject_grades=requirements,
        parser="per_subject_grades",
    )


_UNI_MIN = (
    r"minimum requirements for university admission \[minimum of Ordinary Passes \(S\) "
    r"in three subjects and (?P<cgp>\d{1,2})% or more for the Common General Paper\]"
)


def _university_minimum(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """Explicit '[minimum of Ordinary Passes (S) in three subjects and 30% ... CGP]' clauses."""

    match = re.match(
        r"^(?:Selection criteria for this course of study are very flexible\. That is, )?"
        r"(?:any student|candidates) who ha(?:ve|s) satisfied the " + _UNI_MIN +
        r"(?: having offered any three subjects available)?" + _AL +
        r" (?:are|is) eligible(?: to seek admission to this programme)?"
        r"(?: but one of the three subjects must have a Credit Pass \(C\) in (?P<credit>.+?))?"
        + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    subject_grades: list[dict[str, Any]] = []
    grades = _grades(s=3)
    if match.group("credit"):
        options = [canonical_subject(part) for part in _split_list(match.group("credit").replace(" or ", ", "))]
        if any(option is None for option in options) or len(options) < 2:
            return None
        subject_grades.append(_grade_requirement(options[0], "C", options[1:], raw))  # type: ignore[arg-type]
        grades = _grades(c=1, s=2)
    return _spec(
        "al_minimum_grades",
        raw,
        grades=grades,
        subject_grades=subject_grades,
        cgp_percentage=int(match.group("cgp")),
        parser="university_minimum",
    )


def _minimum_requirements_reference(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'Students who have satisfied the minimum requirements for admission in Arts Stream or ...'

    These clauses refer to the general university minimum (Handbook Section
    1.2, applied to every course by the graph builder) and only add a stream
    restriction, or none ("any three subjects"). No grade counts are invented.
    """

    streams_match = re.match(
        r"^Students who have satisfied the minimum requirements for admission in "
        r"(?P<streams>[A-Za-z ]+? Stream(?: or [A-Za-z ]+? Stream)*) are eligible to seek "
        r"admission for this programme\.(?: The two degree programmes offered are:)?$",
        text,
        re.IGNORECASE,
    )
    if streams_match is not None:
        streams = parse_stream_list(streams_match.group("streams"))
        if streams is None:
            return None
        return _spec("al_stream_eligibility", raw, streams=streams, parser="minimum_requirements_reference")
    any_match = re.match(
        r"^Candidates who have satisfied the minimum requirements for admission having "
        r"offered any three subjects" + _AL + r" are eligible to seek admission\b.*$",
        text,
        re.IGNORECASE,
    )
    if any_match is not None:
        return _spec("al_stream_eligibility", raw, parser="minimum_requirements_reference")
    return None


def _named_subject_plus_any(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'...minimum grade of 'S' or above for English and passes in any other two subjects at A/L.'
    '...at least two Ordinary Passes (S) in any two subjects and at least a Credit Pass (C) in Music.'"""

    english = re.match(
        r"^In order to be eligible for this course of study, candidates should have obtained "
        r"a minimum grade of '(?P<grade>[ABCS])' or above for (?P<subject>[A-Za-z& ]+?) and "
        r"passes in any other two subjects" + _AL + _END,
        text,
        re.IGNORECASE,
    )
    if english is not None:
        subject = canonical_subject(english.group("subject"))
        grade = english.group("grade").upper()
        if subject is None:
            return None
        return _spec(
            "al_subject_combination",
            raw,
            subjects=[subject],
            grades=_grades(s=3) if grade == "S" else _grades(**{grade.lower(): 1, "s": 2}),
            subject_grades=[_grade_requirement(subject, grade, [], raw)],
            parser="named_subject_plus_any",
        )
    credit = re.match(
        r"^In the three subjects" + _AL + r", students must obtain at least two Ordinary "
        r"Passes \(S\) in any two subjects and at least a Credit Pass \(C\) in "
        r"(?P<subject>[A-Za-z& ]+?)\.(?: This requirement is mandatory\.)?$",
        text,
        re.IGNORECASE,
    )
    if credit is not None:
        subject = canonical_subject(credit.group("subject"))
        if subject is None:
            return None
        return _spec(
            "al_subject_combination",
            raw,
            subjects=[subject],
            grades=_grades(c=1, s=2),
            subject_grades=[_grade_requirement(subject, "C", [], raw)],
            parser="named_subject_plus_any",
        )
    return None


def _option_list(value: str) -> list[str] | None:
    """Parse 'A, B, C or D' into canonical subjects."""

    parts = [part.strip() for part in re.split(r",\s*", value) if part.strip()]
    if not parts:
        return None
    parts = [*parts[:-1], *re.split(r"\s+or\s+", parts[-1])]
    options = [canonical_subject(part) for part in parts]
    if any(option is None for option in options) or len(options) < 2:
        return None
    return options  # type: ignore[return-value]


def _following_exact(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least 'S' grades for following three subjects at A/L;' + a 3-subject list."""

    if not re.match(
        r"^(?:To obtain admission to the above mentioned courses of study, a student should "
        r"have obtained )?at least (?:'S' grades (?:in|for) (?:the )?following three subjects|"
        r"three 'S' grades for one of the following combinations of subjects)" + _AL + _END,
        text,
        re.IGNORECASE,
    ):
        return None
    bullets = _subject_bullets(following)
    if bullets is None:
        return None
    subjects, consumed = bullets
    if len(subjects) != 3 or consumed != 3:
        return None
    return _spec(
        "al_subject_combination",
        raw,
        subjects=subjects,
        grades=_grades(s=3),
        subject_grades=[_grade_requirement(subject, "S", [], raw) for subject in subjects],
        consumed=consumed,
        parser="following_exact",
    )


def _stream_sat(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'Should have sat for the G.C.E. (A/L) from Commerce Stream and obtained at least
    'S' grades for Business Studies, Economics and Accounting.' (or '...for any three
    subjects from A, B, C, D or E.')"""

    match = re.match(
        r"^Should have sat for the G\.C\.E\.\s*\(Advanced Level\)\s*Examination from "
        r"(?P<streams>[A-Za-z ]+? Stream(?: or [A-Za-z ]+? Stream)*) and obtained at least "
        r"'S' grades for (?:any three subjects from (?P<options>.+?)|(?P<fixed>.+?))" + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    streams = parse_stream_list(match.group("streams"))
    if streams is None:
        return None
    if match.group("options"):
        options = _option_list(match.group("options"))
        if options is None:
            return None
        return _spec(
            "al_stream_eligibility",
            raw,
            streams=streams,
            grades=_grades(s=3),
            constraints=[_constraint("minimum_count", "Listed subject options", 3, raw, options)],
            parser="stream_sat",
        )
    items = parse_subject_list(match.group("fixed"))
    if items is None or len(items) != 3:
        return None
    return _spec(
        "al_stream_eligibility",
        raw,
        streams=streams,
        subjects=[subject for subject, _ in items],
        grades=_grades(s=3),
        subject_grades=[_grade_requirement(s, "S", alts, raw) for s, alts in items],
        parser="stream_sat",
    )


def _streams_plus_subject(text: str, raw: str, following: Sequence[str]) -> dict | None:
    """'At least 'S' grades in the two subjects in Physical Science Stream or Commerce Stream
    and at least 'S' grade in Information & Communication Technology as the third subject.'"""

    match = re.match(
        r"^at least 'S' grades in (?:the )?two subjects in (?:the )?"
        r"(?P<streams>[A-Za-z ]+? Stream(?: or [A-Za-z ]+? Stream)*) and at least 'S' grade in "
        r"(?P<subject>.+?) as the third subject(?:" + _AL + r")?" + _END,
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    streams = parse_stream_list(match.group("streams"))
    subject = canonical_subject(match.group("subject"))
    if streams is None or subject is None:
        return None
    return _spec(
        "al_stream_eligibility",
        raw,
        streams=streams,
        subjects=[subject],
        grades=_grades(s=3),
        subject_grades=[_grade_requirement(subject, "S", [], raw)],
        constraints=[_constraint("minimum_count", "Subjects from the eligible streams", 2, raw)],
        parser="streams_plus_subject",
    )


def _given_above_choice(
    text: str, raw: str, following: Sequence[str], previous_subjects: Sequence[str]
) -> dict | None:
    """'At least 'S' grades for two subjects given above and the third subject from the
    subjects given below;' -- "given above" is the previous clause's subject list."""

    if len(previous_subjects) < 2 or not re.match(
        r"^at least (?:'S' grades for )?two subjects given above and the third subject from "
        r"the subjects given below" + _END,
        text,
        re.IGNORECASE,
    ):
        return None
    bullets = _subject_bullets(following)
    if bullets is None:
        return None
    options, consumed = bullets
    if len(options) < 2:
        return None
    return _spec(
        "al_subject_combination",
        raw,
        grades=_grades(s=3),
        constraints=[
            _constraint("minimum_count", "Subjects given above", 2, raw, previous_subjects),
            _constraint("required_one_of", "Listed subject options", 1, raw, options),
        ],
        consumed=consumed,
        parser="given_above_choice",
    )


# Order matters: more specific shapes first.
CLAUSE_PARSERS: tuple[Callable[[str, str, Sequence[str]], dict | None], ...] = (
    _physical_condition,
    _following_exact,
    _stream_sat,
    _streams_plus_subject,
    _university_minimum,
    _minimum_requirements_reference,
    _arts_basket_reference,
    _named_subject_plus_any,
    _grade_counts_in_subjects,
    _per_subject_grades,
    _one_of_with_grade,
    _any_three_subjects,
    _stream_subjects,
    _combinations,
    _fixed_plus_any,
    _choice_from_list,
    _exact_subjects,
)


def parse_al_clause(
    text: str,
    following: Sequence[str] = (),
    *,
    previous_subjects: Sequence[str] = (),
) -> dict[str, Any] | None:
    """Return rule fields for one A/L clause, or None when it is not understood.

    ``previous_subjects`` is the subject list of the preceding clause in the
    same unit, used to resolve "two subjects given above".
    """

    raw = text.strip()
    normalized = normalize_clause(raw)
    spec = _given_above_choice(normalized, raw, following, previous_subjects)
    if spec is not None:
        return spec
    for parser in CLAUSE_PARSERS:
        spec = parser(normalized, raw, following)
        if spec is not None:
            return spec
    return None
