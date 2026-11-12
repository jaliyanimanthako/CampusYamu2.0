"""Executable meaning of extracted A/L rules.

``evaluate_rules`` decides whether one student's G.C.E. (A/L) result satisfies
a course's rule set. ``equivalent_rule_sets`` uses it to compare two rule sets
by behaviour: they agree when they accept and reject exactly the same students
over every relevant subject/grade/stream/CGP combination, regardless of which
schema fields each model used to write the requirement.

Field semantics (the prompt states the same contract to the models):

* ``subjects``: a subject listed here and nowhere else in the rule is
  required (at least an S); subjects the structured fields already cover are
  informational (a mirror of required subjects, or a pool).
* ``minimum_grades`` counts are cumulative over the student's subjects:
  a A-or-better, then b more B-or-better, c more C-or-better, s more passes.
* ``subject_grade_requirements``: each item needs one of ``subject`` or its
  ``alternatives`` at ``minimum_grade`` or better; items use distinct subjects.
* ``subject_groups`` are slots: every passed subject that belongs to any group
  is assigned to exactly one of its groups, and each group's assigned count must
  lie within [minimum_required, maximum_allowed] (0 = no cap).
* ``selection_constraints``: minimum_count / maximum_count / required_one_of
  count passed subjects from the list (an empty list in minimum_count means any
  subject); prohibited_combination forbids taking ``count`` (default all) of the
  listed subjects together; allowed_combination constraints in one rule are
  ORed and each needs ``count`` (default all, at most three) of its subjects;
  only_from requires every passed subject to come from its list.
* Rules sharing a non-empty alternative_group form OR options (rules inside
  one option are ANDed); everything else is ANDed.

Anything this module cannot execute (Arts basket references, exceptions,
non-A/L requirements such as height, unknown subject names) makes the rule
"not evaluable"; comparisons then return None so callers fall back to a
structural comparison instead of guessing.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .al_clause_parsers import AL_SUBJECTS, canonical_stream, canonical_subject

GRADE_RANK = {"A": 4, "B": 3, "C": 2, "S": 1, "F": 0}
PASS = GRADE_RANK["S"]
# Handbook Section 1.2: every course also requires three S passes and at least
# 30% in the Common General Test, so rule sets are compared only on students
# who already meet that university minimum.
UNIVERSITY_MINIMUM_CGP = 30
NOT_EVALUABLE_TYPES = {"other_admission_requirement", "al_exception"}
# Names a model uses for "a slot" rather than a subject (e.g. "third subject
# from list", "mathematics choice"); they carry no subject of their own.
PLACEHOLDER_RE = re.compile(
    r"\b(?:subject|subjects|choice|any|other|third|first|second|list|option)\b",
    re.IGNORECASE,
)


class NotEvaluable(ValueError):
    """The rule uses something this module cannot execute."""


@dataclass(frozen=True)
class Student:
    grades: tuple[tuple[str, str], ...]  # (subject, grade) for three subjects
    stream: str | None = None
    cgp: int = 0
    # Opaque conditions (see ``compile_rule``) that hold for this student.
    holds: frozenset[tuple[str, ...]] = frozenset()

    def passed(self) -> list[str]:
        return [subject for subject, grade in self.grades if GRADE_RANK[grade] >= PASS]

    def grade_of(self, subject: str) -> int:
        for name, grade in self.grades:
            if name == subject:
                return GRADE_RANK[grade]
        return -1


def normalize_subject_list(values: Iterable[str]) -> list[str]:
    """Canonical subjects; drop slot placeholders; reject unknown names.

    Repairs two artefacts of copying handbook lists: a name split across two
    bullets ("Information & Communication", "Technology") and slash options in
    one bullet ("Mathematics/ Combined Mathematics", which offers both).
    """

    tokens = [str(value or "").strip() for value in values]
    tokens = [token for token in tokens if token]
    names: list[str] = []
    index = 0
    while index < len(tokens):
        value = tokens[index]
        if (
            canonical_subject(value) is None
            and index + 1 < len(tokens)
            and canonical_subject(f"{value} {tokens[index + 1]}") is not None
        ):
            value = f"{value} {tokens[index + 1]}"
            index += 1
        index += 1
        parts = [value]
        if canonical_subject(value) is None and "/" in value:
            parts = [part.strip() for part in value.split("/") if part.strip()]
        for part in parts:
            subject = canonical_subject(part)
            if subject is None:
                if PLACEHOLDER_RE.search(part):
                    continue
                raise NotEvaluable(f"unknown subject {part!r}")
            if subject not in names:
                names.append(subject)
    return names


@dataclass(frozen=True)
class _CompiledRule:
    group: str
    option: int
    streams: tuple[str, ...]
    grade_counts: tuple[int, int, int, int]
    grade_items: tuple[tuple[int, frozenset[str]], ...]
    groups: tuple[tuple[frozenset[str], int, int], ...]
    min_counts: tuple[tuple[frozenset[str], int], ...]
    max_counts: tuple[tuple[frozenset[str], int], ...]
    one_of: tuple[tuple[frozenset[str], int], ...]
    prohibited: tuple[tuple[frozenset[str], int], ...]
    allowed: tuple[tuple[frozenset[str], int], ...]
    only_from: tuple[frozenset[str], ...]
    opaque: tuple[tuple[str, ...], ...]
    cgp: int

    def mentioned(self) -> set[str]:
        found: set[str] = set()
        for _, options in self.grade_items:
            found |= options
        for collection in (self.groups,):
            for subjects, _, _ in collection:
                found |= subjects
        for collection in (
            self.min_counts, self.max_counts, self.one_of, self.prohibited, self.allowed
        ):
            for subjects, _ in collection:
                found |= subjects
        for subjects in self.only_from:
            found |= subjects
        return found


def compile_rule(rule: dict[str, Any]) -> _CompiledRule:
    if rule.get("requirement_type") in NOT_EVALUABLE_TYPES:
        raise NotEvaluable(f"requirement_type {rule.get('requirement_type')}")
    if str(rule.get("exception_to", "")).strip():
        raise NotEvaluable("exception_to")

    streams: list[str] = []
    for value in rule.get("eligible_streams", []):
        stream = canonical_stream(str(value))
        if stream is None:
            raise NotEvaluable(f"unknown stream {value!r}")
        streams.append(stream)

    grades = rule.get("minimum_grades", {})
    grade_counts = tuple(
        int(grades.get(f"required_{grade}_grades", 0) or 0) for grade in "abcs"
    )

    grade_items = []
    for item in rule.get("subject_grade_requirements", []):
        options = normalize_subject_list([item.get("subject", ""), *item.get("alternatives", [])])
        if not options:
            raise NotEvaluable("grade requirement without a subject")
        grade_items.append((GRADE_RANK[item.get("minimum_grade", "S")], frozenset(options)))

    groups = []
    for group in rule.get("subject_groups", []):
        subjects = normalize_subject_list(group.get("subjects", []))
        if not subjects:
            raise NotEvaluable("subject group without subjects")
        groups.append(
            (
                frozenset(subjects),
                int(group.get("minimum_required", 0) or 0),
                int(group.get("maximum_allowed", 0) or 0),
            )
        )

    min_counts, max_counts, one_of, prohibited, allowed, only_from = [], [], [], [], [], []
    opaque: list[tuple[str, ...]] = []
    for constraint in rule.get("selection_constraints", []):
        kind = constraint.get("constraint_type")
        subjects = frozenset(normalize_subject_list(constraint.get("subjects", [])))
        count = int(constraint.get("count", 0) or 0)
        name = str(constraint.get("group_name", ""))
        if kind == "exception":
            raise NotEvaluable("exception constraint")
        if not subjects and (kind != "minimum_count" or re.search(r"basket", name, re.IGNORECASE)):
            # A reference this module cannot execute yet (an Arts basket rule,
            # "selected per Section 2.2.1.1"): kept as a named yes/no
            # condition. Comparisons try it both ways; evaluation refuses it.
            opaque.append((str(kind), " ".join(name.casefold().split()), str(count)))
            continue
        if kind == "minimum_count":
            min_counts.append((subjects, count))
            continue
        if kind == "maximum_count":
            max_counts.append((subjects, count))
        elif kind == "required_one_of":
            one_of.append((subjects, max(count, 1)))
        elif kind == "prohibited_combination":
            prohibited.append((subjects, count or len(subjects)))
        elif kind == "only_from":
            only_from.append(subjects)
        elif kind == "allowed_combination":
            if not count and len(subjects) > 3:
                # A list longer than a combination is a pool ("the other
                # subjects from this list"), which the schema cannot state.
                raise NotEvaluable("allowed_combination used as a subject pool")
            allowed.append((subjects, count or len(subjects)))
        else:
            raise NotEvaluable(f"constraint {kind}")

    mentioned: set[str] = set()
    for _, options in grade_items:
        mentioned |= options
    for subjects, _, _ in groups:
        mentioned |= subjects
    for subjects, _ in (*min_counts, *max_counts, *one_of, *prohibited, *allowed):
        mentioned |= subjects
    for subjects in only_from:
        mentioned |= subjects
    for subject in normalize_subject_list(rule.get("subjects", [])):
        # A subject named only in ``subjects`` is a required subject; one that
        # the structured fields already cover is just a mirror or a pool.
        if subject not in mentioned:
            grade_items.append((PASS, frozenset([subject])))

    cgp = rule.get("common_general_paper", {}) or {}
    return _CompiledRule(
        group=str(rule.get("alternative_group", "") or ""),
        option=int(rule.get("alternative_option", 0) or 0),
        streams=tuple(streams),
        grade_counts=grade_counts,  # type: ignore[arg-type]
        grade_items=tuple(grade_items),
        groups=tuple(groups),
        min_counts=tuple(min_counts),
        max_counts=tuple(max_counts),
        one_of=tuple(one_of),
        prohibited=tuple(prohibited),
        allowed=tuple(allowed),
        only_from=tuple(only_from),
        opaque=tuple(opaque),
        cgp=int(cgp.get("minimum_percentage", 0) or 0) if cgp.get("required") else 0,
    )


def _distinct_match(items: Sequence[frozenset[str]], available: Sequence[str]) -> bool:
    def assign(index: int, used: frozenset[str]) -> bool:
        if index == len(items):
            return True
        return any(
            assign(index + 1, used | {subject})
            for subject in available
            if subject in items[index] and subject not in used
        )

    return assign(0, frozenset())


def _groups_ok(
    groups: Sequence[tuple[frozenset[str], int, int]], passed: Sequence[str]
) -> bool:
    members = [subject for subject in passed if any(subject in g[0] for g in groups)]
    choices = [
        [index for index, group in enumerate(groups) if subject in group[0]]
        for subject in members
    ]
    for assignment in itertools.product(*choices):
        counts = [assignment.count(index) for index in range(len(groups))]
        if all(
            low <= counts[index] and (high == 0 or counts[index] <= high)
            for index, (_, low, high) in enumerate(groups)
        ):
            return True
    return False


def _rule_ok(rule: _CompiledRule, student: Student) -> bool:
    if rule.streams and student.stream not in rule.streams:
        return False
    if any(key not in student.holds for key in rule.opaque):
        return False
    if rule.cgp and student.cgp < rule.cgp:
        return False
    ranks = sorted((GRADE_RANK[grade] for _, grade in student.grades), reverse=True)
    needed = 0
    for threshold, count in zip((4, 3, 2, 1), rule.grade_counts):
        needed += count
        if sum(rank >= threshold for rank in ranks) < needed:
            return False
    if rule.grade_items:
        # Each item needs its own subject at its grade.
        qualifying = [
            frozenset(s for s in options if student.grade_of(s) >= rank)
            for rank, options in rule.grade_items
        ]
        if not _distinct_match(qualifying, [subject for subject, _ in student.grades]):
            return False
    passed = student.passed()
    if rule.groups and not _groups_ok(rule.groups, passed):
        return False
    for subjects, count in rule.min_counts:
        pool = passed if not subjects else [s for s in passed if s in subjects]
        if len(pool) < count:
            return False
    for subjects, count in rule.max_counts:
        if sum(s in subjects for s in passed) > count:
            return False
    for subjects, count in rule.one_of:
        if sum(s in subjects for s in passed) < count:
            return False
    for subjects, count in rule.prohibited:
        if sum(s in subjects for s in passed) >= count:
            return False
    for subjects in rule.only_from:
        if any(s not in subjects for s in passed):
            return False
    if rule.allowed and not any(
        sum(s in subjects for s in passed) >= count for subjects, count in rule.allowed
    ):
        return False
    return True


def _combine(rules: Sequence[_CompiledRule], student: Student) -> bool:
    options: dict[str, dict[int, list[_CompiledRule]]] = {}
    for rule in rules:
        if not rule.group:
            if not _rule_ok(rule, student):
                return False
        else:
            options.setdefault(rule.group, {}).setdefault(rule.option, []).append(rule)
    return all(
        any(all(_rule_ok(rule, student) for rule in option) for option in group.values())
        for group in options.values()
    )


def evaluate_rules(rules: Sequence[dict[str, Any]], student: Student) -> bool:
    """True when ``student`` satisfies every rule (one course's rule set).

    References to the Arts rules ("selected per Section 2.2.1.1", basket
    limits) are decided by ``arts_rules``; any other reference, or a rule this
    module cannot execute, raises NotEvaluable.
    """

    compiled = [compile_rule(rule) for rule in rules]
    keys = sorted({key for rule in compiled for key in rule.opaque})
    if keys:
        # Referenced conditions are decided by the Arts rules (Section
        # 2.2.1.1) when they name one; anything else stays undecidable.
        from .arts_rules import resolve_arts_condition

        passed = student.passed()
        decided = {key: resolve_arts_condition(key, passed) for key in keys}
        unknown = [key for key, value in decided.items() if value is None]
        if unknown:
            raise NotEvaluable(f"cannot decide referenced conditions: {unknown}")
        student = Student(
            student.grades,
            student.stream,
            student.cgp,
            frozenset(key for key, value in decided.items() if value),
        )
    return _combine(compiled, student)


MAX_OPAQUE_CONDITIONS = 4


def _test_students(compiled: Sequence[_CompiledRule]) -> Iterable[Student]:
    mentioned: set[str] = set()
    levels = {"S"}
    streams: set[str] = set()
    cgps = {UNIVERSITY_MINIMUM_CGP}
    for rule in compiled:
        mentioned |= rule.mentioned()
        for grade, count in zip("ABCS", rule.grade_counts):
            if count:
                levels.add(grade)
        for rank, _ in rule.grade_items:
            levels.add(next(g for g, r in GRADE_RANK.items() if r == rank))
        streams.update(rule.streams)
        if rule.cgp > UNIVERSITY_MINIMUM_CGP:
            cgps.update({rule.cgp - 1, rule.cgp})
    # Three unnamed subjects so a result made only of them is always tested.
    fillers = [subject for subject in AL_SUBJECTS if subject not in mentioned][:3]
    universe = sorted(mentioned) + fillers
    stream_values: list[str | None] = [*sorted(streams), None]
    keys = sorted({key for rule in compiled for key in rule.opaque})
    truth_values = [
        frozenset(combo)
        for size in range(len(keys) + 1)
        for combo in itertools.combinations(keys, size)
    ]
    for subjects in itertools.combinations(universe, 3):
        for grades in itertools.product(sorted(levels), repeat=3):
            pairs = tuple(zip(subjects, grades))
            for stream in stream_values:
                for cgp in sorted(cgps):
                    for holds in truth_values:
                        yield Student(pairs, stream, cgp, holds)


def equivalent_rule_sets(
    first: Sequence[dict[str, Any]], second: Sequence[dict[str, Any]]
) -> bool | None:
    """Behavioural equality per target; None when either set is not evaluable.

    Tested on every three-subject result over the subjects either set names
    (plus three unnamed subjects), every relevant grade level, stream and CGT
    threshold, restricted to students meeting the university minimum. A
    condition the module cannot execute (e.g. "selected per Section 2.2.1.1")
    is tried both true and false, so agreement holds whatever it means; the
    two sets must name it identically (type, group_name, count) to match.
    """

    targets = {rule.get("target_id") for rule in [*first, *second]}
    try:
        compiled = {
            target: (
                [compile_rule(r) for r in first if r.get("target_id") == target],
                [compile_rule(r) for r in second if r.get("target_id") == target],
            )
            for target in targets
        }
    except (NotEvaluable, KeyError, TypeError, ValueError):
        return None
    for left, right in compiled.values():
        if len({key for rule in [*left, *right] for key in rule.opaque}) > MAX_OPAQUE_CONDITIONS:
            return None
        if not left or not right:
            return False
        for student in _test_students([*left, *right]):
            if _combine(left, student) != _combine(right, student):
                return False
    return True
