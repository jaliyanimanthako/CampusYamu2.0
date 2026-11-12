"""Parent-child chunks of the UGC handbook markdown, with citations.

Parents are handbook sections (§1.2, §2.2.3.1, Annex (b), ...), split at
sub-headings or paragraph boundaries when longer than ``PARENT_MAX_WORDS``.
They are what the reader (or an LLM) gets back. Children are small runs of
paragraphs/list items inside one parent; they are what gets embedded and
BM25-indexed, so matching is precise while answers keep their context.

Heading levels in this markdown are not a reliable tree (``##### 2.2.1.1
Arts`` and ``##### Basket 01`` share a level), so sections come from the
numbering: a heading starts a section when it carries a section number
(``2.2.1.1``), is a ``Section N`` / ``Annex`` heading, or is a ``##``-level
heading. Other headings are sub-headings inside the current section and are
kept in each child's heading path.

Every chunk records its section number, heading path, markdown lines and PDF
pages (from the ``<!-- PDF page N -->`` markers).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from ..graph_pipeline.handbook_prose import PROJECT_ROOT

HANDBOOK = Path("RAG_Agent/student_handbook_english_structured.md")
DEFAULT_CHUNKS = Path("RAG_Agent/generated/handbook_chunks.json")
PARENT_MAX_WORDS = 800
CHILD_MAX_WORDS = 180
PARENT_MIN_TAIL_WORDS = 150
CHILD_MIN_WORDS = 40
SKIPPED_SECTIONS = {"Contents"}       # the table of contents only repeats headings

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
PAGE_RE = re.compile(r"<!--\s*PDF page (\d+)\s*-->")
COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)+)\b")
SECTION_RE = re.compile(r"^Section\s+(\d+)\b")
ANNEX_RE = re.compile(r"^Annex\b[\s\-–—]*(\(?[A-Za-z]+\)?|[IVX]+)?")


@dataclass
class Block:
    text: str
    line_start: int
    line_end: int
    page: int | None
    subheading: str | None


@dataclass
class Section:
    key: str                  # section number or a heading-based key
    title: str
    path: list[str]           # ancestor headings, outermost first, ending with this one
    line: int
    page: int | None
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Parent:
    id: str
    section_number: str
    title: str
    heading_path: list[str]
    text: str
    line_start: int
    line_end: int
    page_start: int | None
    page_end: int | None
    part: int = 1
    parts: int = 1


@dataclass
class Child:
    id: str
    parent_id: str
    section_number: str
    heading_path: list[str]
    text: str
    embed_text: str           # heading path + text: what is embedded and BM25-indexed
    line_start: int
    line_end: int
    page_start: int | None
    page_end: int | None


def _words(text: str) -> int:
    return len(text.split())


def _section_key(level: int, title: str) -> tuple[str, int] | None:
    """(key, depth) when this heading starts a section, else None."""

    if match := NUMBER_RE.match(title):
        return match.group(1), match.group(1).count(".") + 1
    if match := SECTION_RE.match(title):
        return match.group(1), 1
    if ANNEX_RE.match(title):
        return title.split("—")[0].strip(), 2
    if level <= 2:
        return title, 1
    return None


def parse_sections(lines: Sequence[str]) -> list[Section]:
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []          # (depth, heading)
    page: int | None = None
    current: Section | None = None
    subheading: str | None = None
    paragraph: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal paragraph
        if current is not None and paragraph:
            text = "\n".join(t for _, t in paragraph).strip()
            if text:
                current.blocks.append(Block(text, paragraph[0][0], paragraph[-1][0], page, subheading))
        paragraph = []

    for number, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if match := PAGE_RE.search(line):
            flush()
            page = int(match.group(1))
            continue
        if COMMENT_RE.match(line):
            continue
        if heading := HEADING_RE.match(line):
            flush()
            level, title = len(heading.group(1)), heading.group(2).strip()
            started = _section_key(level, title)
            if started:
                key, depth = started
                stack = [(d, h) for d, h in stack if d < depth] + [(depth, title)]
                current = Section(key, title, [h for _, h in stack], number, page)
                sections.append(current)
                subheading = None
            else:
                subheading = title
            continue
        if not line.strip():
            flush()
            continue
        paragraph.append((number, line.strip()))
    flush()
    return [s for s in sections if s.title not in SKIPPED_SECTIONS]


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha1("|".join(map(str, parts)).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def _short(heading: str, limit: int = 70) -> str:
    """'Section 2 — Essential information for ...' -> 'Section 2 — Essential information ...'."""

    return heading if len(heading) <= limit else heading[:limit].rsplit(" ", 1)[0] + " …"


def _block_text(blocks: Sequence[Block]) -> str:
    out: list[str] = []
    shown: str | None = None
    for block in blocks:
        if block.subheading and block.subheading != shown:
            out.append(f"**{block.subheading}**")
            shown = block.subheading
        out.append(block.text)
    return "\n\n".join(out)


def _split(blocks: Sequence[Block], limit: int) -> list[list[Block]]:
    """Consecutive groups of at most ``limit`` words, preferring sub-heading breaks."""

    groups: list[list[Block]] = [[]]
    size = 0
    for block in blocks:
        words = _words(block.text)
        new_heading = groups[-1] and block.subheading != groups[-1][-1].subheading
        if groups[-1] and (size + words > limit or (new_heading and size > limit * 0.6)):
            groups.append([])
            size = 0
        groups[-1].append(block)
        size += words
    return [g for g in groups if g]


def _children(parent: Parent, blocks: Sequence[Block]) -> list[Child]:
    groups = _split(blocks, CHILD_MAX_WORDS)
    # fold a short tail into the previous child so tiny fragments are not indexed alone
    if len(groups) > 1 and sum(_words(b.text) for b in groups[-1]) < CHILD_MIN_WORDS:
        groups[-2].extend(groups.pop())
    children = []
    for index, group in enumerate(groups):
        text = _block_text(group)
        path = parent.heading_path + ([group[0].subheading] if group[0].subheading else [])
        pages = [b.page for b in group if b.page is not None]
        children.append(Child(
            id=_stable_id("chunk", parent.id, index, text),
            parent_id=parent.id,
            section_number=parent.section_number,
            heading_path=path,
            text=text,
            embed_text=" > ".join(_short(h) for h in path) + "\n\n" + text,
            line_start=group[0].line_start,
            line_end=group[-1].line_end,
            page_start=min(pages) if pages else None,
            page_end=max(pages) if pages else None,
        ))
    return children


def build_chunks(markdown: str) -> tuple[list[Parent], list[Child]]:
    parents: list[Parent] = []
    children: list[Child] = []
    for section in parse_sections(markdown.splitlines()):
        if not section.blocks:
            continue
        groups = _split(section.blocks, PARENT_MAX_WORDS)
        tail = sum(_words(b.text) for b in groups[-1])
        if len(groups) > 1 and tail < PARENT_MIN_TAIL_WORDS and (
            tail + sum(_words(b.text) for b in groups[-2]) <= PARENT_MAX_WORDS + PARENT_MIN_TAIL_WORDS
        ):
            groups[-2].extend(groups.pop())       # no near-empty "part 2/2"
        for part, group in enumerate(groups, start=1):
            first = [section.page] if part == 1 else []
            pages = [p for p in [*first, *(b.page for b in group)] if p is not None]
            parent = Parent(
                id=_stable_id("passage", section.key, section.line, part),
                section_number=section.key,
                title=section.title,
                heading_path=section.path,
                text=_block_text(group),
                line_start=section.line if part == 1 else group[0].line_start,
                line_end=group[-1].line_end,
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
                part=part,
                parts=len(groups),
            )
            parents.append(parent)
            children.extend(_children(parent, group))
    return parents, children


def citation(chunk: Parent | Child | dict) -> str:
    data = chunk if isinstance(chunk, dict) else asdict(chunk)
    section = data["section_number"]
    label = f"§{section}" if NUMBER_RE.match(section) or section.isdigit() else section
    start, end = data.get("page_start"), data.get("page_end")
    pages = "" if start is None else (f", p. {start}" if start == end else f", pp. {start}–{end}")
    return f"Handbook {label}{pages}, lines {data['line_start']}–{data['line_end']}"


def write_chunks(parents: Iterable[Parent], children: Iterable[Child], path: Path,
                 source: Path) -> Path:
    payload = {
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "settings": {"parent_max_words": PARENT_MAX_WORDS, "child_max_words": CHILD_MAX_WORDS},
        "parents": [asdict(p) for p in parents],
        "children": [asdict(c) for c in children],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_chunks(path: Path = PROJECT_ROOT / DEFAULT_CHUNKS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split the handbook into parent/child chunks.")
    parser.add_argument("--handbook", type=Path, default=PROJECT_ROOT / HANDBOOK)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / DEFAULT_CHUNKS)
    args = parser.parse_args(argv)
    parents, children = build_chunks(args.handbook.read_text(encoding="utf-8"))
    path = write_chunks(parents, children, args.output, args.handbook)
    words = [_words(c.text) for c in children]
    print(f"Wrote {path}: {len(parents)} parents, {len(children)} children "
          f"(child words: median {sorted(words)[len(words) // 2]}, max {max(words)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
