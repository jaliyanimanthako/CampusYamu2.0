"""Code checks on the SWOT: specific, analysis-only, no individual job adverts.

A finding passes when it names at least one concrete detail (an "anchor":
a body, employer, place, tool, standard or qualification) that also appears in
the sources it cites. Generic words ("high demand", "digital skills", "stable
prospects") are not anchors. Failing items go back to the model once with the
reasons; whatever still fails is dropped rather than shown to the student.

The SWOT is an analysis, not advice, and a forecast, not a job board. So
sentences that instruct the student ("consider...", "you should...") or point
to individual job adverts ("X has advertised...", "apply by...") are also sent
back, and removed if they survive the revision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SWOT_CATEGORIES = ("strengths", "weaknesses", "opportunities", "threats")

# Words that do not make a sentence specific to one course.
GENERIC_WORDS = frozenset(
    """
    a an and are as at be been but by can could for from has have in into is it
    its may might more most much not of on or so such than that the their there
    these this those to was were which while will with would you your who what
    about after also any both each every many some other over under very well
    high higher strong stronger growing growth demand demanded rising increasing
    jobs job work working works roles role career careers opportunity
    opportunities salary salaries pay paid wages wage income graduates graduate
    entry level junior senior experience experienced skills skill local
    overseas abroad international global worldwide market markets industry
    industries sector sectors economic economy uncertainty automation automated
    technology technologies technological digital tech sustainable
    sustainability green competition competitive stable stability prospects
    field profession professional professionals students student degree study
    studies further training qualification qualifications practical knowledge
    new emerging future trends trend modest low lower better good great
    significant potential relevant important valuable key various several
    including especially particularly enhance improve improves help helps
    make makes open opens offer offers provide provides need needs require
    requires required employers employer companies firms clients projects
    project construction building cost costs management manage data tools
    software services practices practice areas area specialisation
    specialization specialisations specializations certifications
    certification years year time next first five four people country
    countries region regional
    """.split()
)


ADVICE_START = re.compile(
    r"^(?:so\s+|therefore\s+|instead\s+)?(?:consider|try|seek|build|learn|practi[sc]e|plan|budget|"
    r"check|focus|keep|take|look|use|get|study|enrol|enroll|pursue|engage|aim|start|"
    r"join|gain|develop|choose|explore|prepare|apply|register|target|invest|avoid|"
    r"remember|expect|do not|don't|be ready|be prepared|make)\b",
    re.I,
)
ADVICE_PHRASES = re.compile(
    r"\b(?:you should|you need to|you must|you(?:'ll| will) need to|make sure|"
    r"be sure to|it is worth|it's worth|worth considering|we recommend|i recommend|"
    r"is advisable|it would be wise|you may want to|you might want to|"
    r"you could (?:consider|try|look|aim|focus)|consider (?:taking|doing|getting|learning))\b",
    re.I,
)
JOB_ADVERT = re.compile(
    r"\b(?:advertis\w*|job ads?|job posting\w*|posted (?:a|an) (?:job|role|vacancy)|"
    r"(?:is|are|was|were) hiring|a vacancy|the vacancy|apply\w*|applications? (?:close|deadline)|"
    r"deadline\w*)\b",
    re.I,
)


def offending_sentences(text: str) -> list[str]:
    """Sentences that give advice or point to an individual job advert."""

    return [
        sentence
        for sentence in _sentences(text)
        if ADVICE_START.match(sentence) or ADVICE_PHRASES.search(sentence) or JOB_ADVERT.search(sentence)
    ]


def strip_offending(analysis: dict[str, Any]) -> int:
    """Remove advice and job-advert sentences everywhere. Returns how many."""

    removed = 0

    def clean(container: dict[str, Any], key: str) -> None:
        nonlocal removed
        text = str(container.get(key) or "")
        bad = offending_sentences(text)
        if bad:
            container[key] = " ".join(s for s in _sentences(text) if s not in bad)
            removed += len(bad)

    for category in SWOT_CATEGORIES:
        for finding in analysis.get("future_swot", {}).get(category, []):
            clean(finding, "finding")
    for niche in analysis.get("niche_specialisations", []):
        clean(niche, "why_it_matters")
    for key in ("local_vs_overseas", "further_study"):
        if isinstance(analysis.get(key), dict):
            clean(analysis[key], "explanation")
    if isinstance(analysis.get("overall_outlook"), dict):
        clean(analysis["overall_outlook"], "summary")
    if isinstance(analysis.get("course_introduction"), dict):
        clean(analysis["course_introduction"], "overview")
    analysis["limitations"] = [
        item for item in analysis.get("limitations", []) if not offending_sentences(str(item))
    ]
    return removed


@dataclass(frozen=True)
class Problem:
    path: tuple[str, int] | None  # (section, index) of a droppable item; None if not droppable
    message: str


def anchors(text: str, exclude: set[str]) -> set[str]:
    """Distinctive words in ``text``: not generic, not the course or region."""

    words = re.findall(r"[a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9]{3,}", text.casefold())
    return {
        _stem(word)
        for word in words
        if len(word) >= 3 and word not in GENERIC_WORDS and word not in exclude
    }


def specificity_problems(
    analysis: dict[str, Any],
    evidence: list[dict[str, Any]],
    course: str,
    region: str,
) -> list[Problem]:
    exclude = set(re.findall(r"[a-z]+", f"{course} {region}".casefold()))
    content = {item["evidence_id"]: _stems(item.get("content", "") + " " + item.get("title", "")) for item in evidence}
    problems: list[Problem] = []

    swot = analysis.get("future_swot", {})
    for category in SWOT_CATEGORIES:
        for index, finding in enumerate(swot.get(category, [])):
            message = _finding_problem(finding, content, exclude)
            if message is None and not str(finding.get("finding", "")).strip():
                message = "is empty."
            if message:
                problems.append(Problem((category, index), f"{category}[{index}] {message}"))

    for index, niche in enumerate(analysis.get("niche_specialisations", [])):
        cited = _cited(niche.get("evidence_refs", []), content)
        area_anchors = anchors(str(niche.get("area", "")), exclude)
        if not area_anchors:
            problems.append(
                Problem(("niche_specialisations", index),
                        f"niche_specialisations[{index}] '{niche.get('area')}' is too broad; "
                        "name the specific method, standard, law, certification or tool.")
            )
        elif not area_anchors & cited:
            problems.append(
                Problem(("niche_specialisations", index),
                        f"niche_specialisations[{index}] '{niche.get('area')}' is not named "
                        "in the sources it cites.")
            )

    for label, text in _student_texts(analysis):
        for sentence in offending_sentences(text):
            problems.append(
                Problem(None, f"{label} gives advice or points to an individual job advert: "
                              f"\"{sentence}\". State what the evidence shows instead.")
            )

    outlook = analysis.get("overall_outlook", {})
    everything = set().union(*content.values()) if content else set()
    named = anchors(str(outlook.get("summary", "")), exclude) & everything
    if len(named) < 2:
        problems.append(
            Problem(None, "overall_outlook.summary names fewer than two concrete details "
                          "from the sources (a body, employer, country, tool or qualification).")
        )
    return problems


def drop_items(analysis: dict[str, Any], problems: list[Problem]) -> int:
    """Remove the items that still fail. Returns how many were removed."""

    doomed: dict[str, set[int]] = {}
    for problem in problems:
        if problem.path:
            doomed.setdefault(problem.path[0], set()).add(problem.path[1])
    removed = 0
    for section, indexes in doomed.items():
        container = analysis["future_swot"] if section in SWOT_CATEGORIES else analysis
        items = container.get(section, [])
        container[section] = [item for i, item in enumerate(items) if i not in indexes]
        removed += len(items) - len(container[section])
    return removed


def _finding_problem(finding: dict[str, Any], content: dict[str, set[str]], exclude: set[str]) -> str | None:
    specifics = [str(item) for item in finding.get("course_specifics", []) if str(item).strip()]
    if not specifics:
        return "has no course_specifics."
    cited = _cited(finding.get("evidence_refs", []), content)
    grounded = set()
    for specific in specifics:
        grounded |= anchors(specific, exclude) & cited
    if not grounded:
        return (
            f"is generic: none of its course_specifics ({'; '.join(specifics)}) names a "
            "concrete body, employer, place, tool or qualification found in its cited sources."
        )
    if not anchors(str(finding.get("finding", "")), exclude) & grounded:
        return "does not mention its course_specifics in the finding text."
    return None


def _student_texts(analysis: dict[str, Any]) -> list[tuple[str, str]]:
    texts = []
    for category in SWOT_CATEGORIES:
        for index, finding in enumerate(analysis.get("future_swot", {}).get(category, [])):
            texts.append((f"{category}[{index}]", str(finding.get("finding", ""))))
    for index, niche in enumerate(analysis.get("niche_specialisations", [])):
        texts.append((f"niche_specialisations[{index}]", str(niche.get("why_it_matters", ""))))
    for key in ("local_vs_overseas", "further_study"):
        texts.append((key, str((analysis.get(key) or {}).get("explanation", ""))))
    texts.append(("overall_outlook.summary", str((analysis.get("overall_outlook") or {}).get("summary", ""))))
    texts.append(("course_introduction.overview", str((analysis.get("course_introduction") or {}).get("overview", ""))))
    for index, item in enumerate(analysis.get("limitations", [])):
        texts.append((f"limitations[{index}]", str(item)))
    return texts


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _cited(refs: list[str], content: dict[str, set[str]]) -> set[str]:
    return set().union(*(content.get(ref, set()) for ref in refs)) if refs else set()


def _stems(text: str) -> set[str]:
    return {_stem(word) for word in re.findall(r"[a-z0-9][a-z0-9\-]*[a-z0-9]|[a-z0-9]{3,}", text.casefold())}


def _stem(word: str) -> str:
    # "certified"/"certification", "surveyors"/"surveying" share a stem.
    return word[:6] if len(word) > 7 else word
