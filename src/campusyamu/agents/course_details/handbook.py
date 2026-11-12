"""Course details straight from the handbook section that describes each course.

The handbook gives every course a block of text:

* a numbered section ("##### 2.2.4.11 Artificial Intelligence ... (Course Code - 117)"), or
* inside 2.2.1.1, a numbered "course of study" paragraph for the Arts courses
  offered with special requirements ("**8. Courses of Study in Music, Dance ...
  offered by the University of the Visual and Performing Arts (Course Codes :
  Music - 068; Dance - 069 ...)**"). A course offered in several such paragraphs
  (Music, Dance) has one block per university.

Blocks are found by the course codes they declare, so no search is involved.
From each block the card fields are read with simple patterns: degree
programmes ("Bachelor of ..."), duration, medium of instruction and notes
worth knowing (aptitude/practical tests, interviews, selection by the
faculty, physical or medical conditions). The block text and its handbook
citation (section, PDF pages, markdown lines, vector-DB passage ids) are kept
so a student can read the original.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from campusyamu.core.paths import HANDBOOK_CHUNKS, HANDBOOK_MD

CHUNKS_JSON = HANDBOOK_CHUNKS

NUMBERED_HEADING = re.compile(r"^#{2,5}\s+(\d+(?:\.\d+)+)\s+(.*)$")
ANY_TOP_HEADING = re.compile(r"^#{2,3}\s+\S")
ARTS_BLOCK = re.compile(r"^\*\*\s*\d+\.\s+Courses?\s+of\s+Study\b", re.IGNORECASE)
CODE_DECL = re.compile(r"Course\s*Codes?\s*[-–:]\s*([^)]*)", re.IGNORECASE)
CODE = re.compile(r"\b(\d{3})\b")
PAGE = re.compile(r"<!--\s*PDF page\s+(\d+)\s*-->")
COMMENT = re.compile(r"<!--.*?-->")
DEGREE = re.compile(r"(Bachelor\s+of\s+[^;\n]*?)(?=\s*(?:;|$|\s-\s+Available|\s{2,}))", re.IGNORECASE)
YEARS = re.compile(r"\b(?:(\d{1,2})|\((\d{2})\)|(three|four|five|six))\s*(?:\((\d{2})\)\s*)?years?\b", re.IGNORECASE)
WORD_NUMBERS = {"three": 3, "four": 4, "five": 5, "six": 6}
LANGUAGES = ("Sinhala", "Tamil", "English")
NOTE_WORDS = re.compile(
    r"aptitude|practical|interview|will do the selection|selection for a particular|height|colou?r\s*blind|"
    r"physical(?:ly)?\s+(?:fit|disab|condition)|medical\s+(?:fitness|test|examination|certificate|board)|"
    r"fitness|ineligible|not be eligible|important|"
    r"conducted only in|special requirement|selected on|press notice", re.IGNORECASE)
MAX_NOTES = 6
MAX_NOTE_CHARS = 320
MAX_TEXT_CHARS = 6000
INSTITUTION_NOISE = {"university", "of", "the", "sri", "lanka", "and", "campus", "institute", "faculty"}


def _clean(line: str) -> str:
    line = COMMENT.sub("", line)
    line = re.sub(r"[*_`]+", "", line)
    line = re.sub(r"^\s*(?:[-•]|\d+\.)\s+", "", line)
    return " ".join(line.split())


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.casefold().replace("swamy", "swami"))} - INSTITUTION_NOISE


@dataclass
class CourseBlock:
    codes: list[str]
    section: str | None
    title: str
    line_start: int
    line_end: int
    pages: list[int]
    text: str
    degree_programmes: list[str] = field(default_factory=list)
    duration: list[str] = field(default_factory=list)
    medium: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    specializations: dict[str, list[str]] = field(default_factory=dict)   # sub-heading (e.g. university) -> fields
    passage_ids: list[str] = field(default_factory=list)

    @property
    def citation(self) -> str:
        pages = f", p. {self.pages[0]}" + (f"–{self.pages[-1]}" if len(self.pages) > 1 else "") if self.pages else ""
        return f"Handbook §{self.section or '?'}{pages}"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "citation": self.citation}


def _merge_split_labels(lines: list[str]) -> list[str]:
    """'Duration' + ': 04 years' on two lines -> 'Duration : 04 years'."""

    merged: list[str] = []
    for line in lines:
        if merged and line.startswith(":") and ":" not in merged[-1] and len(merged[-1]) < 40:
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _specializations(lines: list[str]) -> dict[str, list[str]]:
    """Lists under unnumbered sub-headings naming an institution ("##### _University of Moratuwa:_")."""

    found: dict[str, list[str]] = {}
    current = None
    for raw in lines:
        if raw.startswith("#") and not NUMBERED_HEADING.match(raw):
            heading = _clean(raw.lstrip("#")).rstrip(":")
            current = heading if re.search(r"University|Institute|Campus", heading) else None
            continue
        if current and re.match(r"^\s*-\s+\S", raw) and not raw.lstrip("- ").startswith("#"):
            item = _clean(raw)
            if item and len(item) < 90 and item not in found.setdefault(current, []):
                found[current].append(item)
    return {k: v for k, v in found.items() if v}


def _extract(block: CourseBlock, lines: list[str]) -> None:
    cleaned = [_clean(line) for line in lines]
    cleaned = _merge_split_labels([line for line in cleaned if line])
    degrees: list[str] = []
    for line in cleaned:
        for match in DEGREE.finditer(line):
            name = match.group(1).strip(" .,:-")
            if 12 < len(name) < 200 and name.casefold() not in {d.casefold() for d in degrees}:
                degrees.append(name)
    years: list[str] = []
    for line in cleaned:
        if "duration" not in line.casefold():
            continue
        for match in YEARS.finditer(line):
            digits = match.group(1) or match.group(2) or match.group(4)
            value = int(digits) if digits else WORD_NUMBERS[match.group(3).casefold()]
            text = f"{value} years"
            if 2 <= value <= 7 and text not in years:
                years.append(text)
    mediums: list[str] = []
    for line in cleaned:
        if "medium" in line.casefold():
            mediums += [lang for lang in LANGUAGES if lang.casefold() in line.casefold() and lang not in mediums]
    notes: list[str] = []
    for line in cleaned:
        if NOTE_WORDS.search(line) and not line.casefold().startswith(("at least", "minimum eligibility")):
            note = line if len(line) <= MAX_NOTE_CHARS else line[:MAX_NOTE_CHARS].rsplit(" ", 1)[0] + " …"
            if note not in notes:
                notes.append(note)
    block.degree_programmes, block.duration, block.medium = degrees, years, mediums
    block.notes = notes[:MAX_NOTES]
    block.specializations = _specializations(lines)


class HandbookCourseIndex:
    """Course code -> handbook blocks (usually one; one per university for some Arts courses)."""

    def __init__(self, markdown: Path = HANDBOOK_MD, chunks: Path | None = CHUNKS_JSON) -> None:
        self.lines = Path(markdown).read_text(encoding="utf-8").splitlines()
        self.blocks: list[CourseBlock] = []
        self.by_code: dict[str, list[CourseBlock]] = {}
        self._build()
        if chunks and Path(chunks).is_file():
            self._link_passages(json.loads(Path(chunks).read_text(encoding="utf-8")))

    def _build(self) -> None:
        starts: list[tuple[int, str | None, str]] = []          # (index, section, title)
        section = None
        for i, line in enumerate(self.lines):
            heading = NUMBERED_HEADING.match(line)
            if heading:
                section = heading.group(1)
                starts.append((i, section, _clean(heading.group(2)) or section))
            elif ANY_TOP_HEADING.match(line):
                starts.append((i, None, ""))
            elif ARTS_BLOCK.match(line):
                starts.append((i, section, _clean(line)))
        starts.append((len(self.lines), None, ""))
        page = None
        page_at: list[int | None] = []
        for line in self.lines:
            found = PAGE.search(line)
            if found:
                page = int(found.group(1))
            page_at.append(page)
        for (start, sec, title), (end, _, _) in zip(starts, starts[1:]):
            body = self.lines[start:end]
            codes: list[str] = []
            for line in body:
                for decl in CODE_DECL.finditer(line):
                    codes += [c for c in CODE.findall(decl.group(1)) if c not in codes]
            if not codes or sec is None or not sec.startswith("2.2"):
                continue
            pages = sorted({p for p in page_at[start:end] if p is not None})
            text = "\n".join(COMMENT.sub("", line).rstrip() for line in body).strip()
            text = re.sub(r"\n{3,}", "\n\n", text)
            block = CourseBlock(codes, sec, title or sec, start + 1, end, pages,
                                text if len(text) <= MAX_TEXT_CHARS else text[:MAX_TEXT_CHARS] + "\n…")
            _extract(block, body)
            self.blocks.append(block)
            for code in codes:
                self.by_code.setdefault(code, []).append(block)

    def _link_passages(self, chunks: dict[str, Any]) -> None:
        for block in self.blocks:
            block.passage_ids = [p["id"] for p in chunks.get("parents", [])
                                 if int(p["line_start"]) <= block.line_end and int(p["line_end"]) >= block.line_start]

    def blocks_for(self, code: str) -> list[CourseBlock]:
        return self.by_code.get(code, [])

    def block_for_offering(self, code: str, *names: str | None) -> int | None:
        """Index of the block for this university when a course has several; None = all apply."""

        blocks = self.blocks_for(code)
        if len(blocks) <= 1:
            return 0 if blocks else None
        for name in names:
            wanted = _tokens(name or "")
            if not wanted:
                continue
            hits = [i for i, b in enumerate(blocks) if wanted <= _tokens(b.title)]
            if len(hits) == 1:
                return hits[0]
        return None
