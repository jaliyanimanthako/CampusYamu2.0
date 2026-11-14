"""Official university web pages for the course chat (sources W1, W2 ...).

The handbook gives the admission facts; a university's own site has the rest:
modules, specialisations, internships, facilities, staff, contacts. For one
offering (uni_code) this module

1. looks up the university's official domains in data/reference/university_domains.json
   (owner-reviewed; subdomains count, so "pdn.ac.lk" covers "eng.pdn.ac.lk");
2. runs ONE web search limited to those domains ("<course> degree programme <university>"),
   with the page text in the same call (Tavily, or Firecrawl with site: filters);
3. keeps the top pages (text trimmed) and caches them per offering in
   data/cache/university_pages/<uni_code>.json for chat.website.cache_days;
4. per question, picks the passages that best fit it (keyword overlap), which the
   chat cites as W1, W2 ... with the page link;
5. (LLM) reads the pages into the same applicant profile for every course: overview,
   faculty, degree, duration, medium, modules, specialisations, industrial training,
   facilities, careers, entry notes, fees, contact, other; each fact cites its page.
   Cached with the pages (extract_profile). Prompt: campusyamu/prompts/university.py.
   Model: models.website in settings.yaml (gpt-4o-mini);
6. (2nd hop) for each specialisation, one more search limited to the official domains
   (the searches run in parallel). The names come from the UGC handbook for this university
   (handbook_specialisations) and, only when it lists none, from the website profile ("Civil Engineering University of Moratuwa"); the LLM picks the
   candidate page that is really about that specialisation and writes a short card,
   or marks it not found. When the official search finds nothing, one open search
   lists pages on other domains for the owner to review (never used). Cached too
   (explore_specialisations).

Pages from any other domain are dropped even if the search returns them. The research
runs as part of the course research (course_research.py), which the course chat starts
when the student asks for it; the chat then reads the cache (W and D sources).
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from campusyamu.core import settings
from campusyamu.core.paths import CACHE_DIR, REFERENCE_DIR

DOMAINS_FILE = REFERENCE_DIR / "university_domains.json"
DEFAULT_DIR = CACHE_DIR / "university_pages"
ENABLED = settings.get("chat.website.enabled", True)    # the chat uses the website research (W, D)
MAX_PAGES = settings.get("chat.website.max_pages", 5)
CACHE_DAYS = settings.get("chat.website.cache_days", 30)
EMPTY_CACHE_DAYS = 1                       # nothing found: try again tomorrow, not next month
PASSAGES = settings.get("chat.website.passages", 4)
PASSAGE_CHARS = settings.get("chat.website.passage_chars", 900)
PAGE_CHARS = 20000                         # kept per page in the cache
LLM_PAGE_CHARS = 8000                      # per page sent to the LLM
LLM_TOTAL_CHARS = 32000                    # all pages together
PROFILE_VERSION = 2                        # bump when the profile request changes: old cached profiles are redone
MAX_SPECIALISATIONS = settings.get("chat.website.max_specialisations", 10)
SPEC_CANDIDATES = 3                        # search results kept per specialisation
SPEC_PAGE_CHARS = 5000                     # per candidate page sent to the LLM
SPEC_TOTAL_CHARS = 60000
SPECIALISATION_VERSION = 3
SEARCH_WORKERS = 4                         # parallel specialisation searches
GENERIC_DEGREE = re.compile(r"^Bachelor of .*Honours$", re.I)    # a degree title, not a specialisation
PROFILE_FIELDS = ("overview", "faculty", "degree_awarded", "duration", "medium", "modules", "specialisations",
                  "industrial_training", "facilities", "careers", "entry_notes", "fees", "contact", "other")
STOPWORDS = set("""a an and are as at be by can do does for from has have how i if in is it its me my of on or
our so that the their them there this to us was we what when where which who why will with you your about any
course degree programme program university""".split())
LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def load_domains(path: Path = DOMAINS_FILE) -> dict[str, list[str]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8")).get("domains", {})
    except (OSError, ValueError):
        return {}
    out = {}
    for name, domains in raw.items():
        cleaned = [re.sub(r"^https?://|/.*$|^www\.", "", str(d).strip().casefold()) for d in domains or []]
        if cleaned := [d for d in cleaned if d]:
            out[name] = cleaned
    return out


def domain_ok(url: str, domains: list[str]) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").casefold().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in domains)


def missing_keys() -> list[str]:
    import os

    from campusyamu.agents.career_trends.providers import web_provider_name

    try:
        provider = web_provider_name(None)
    except ValueError as exc:
        return [str(exc)]
    key = {"tavily": "TAVILY_API_KEY", "firecrawl": "FIRECRAWL_API_KEY"}[provider]
    return [] if os.getenv(key) else [key]


def _clean(markdown: str) -> str:
    """Drop menus and link lists: lines that are mostly links, or a few characters long."""

    lines = []
    for line in markdown.splitlines():
        text = line.strip()
        plain = LINK.sub(r"\1", text).strip(" #*-|>")
        if len(plain) < 3 or (len(LINK.sub("", text).strip(" #*-|>")) < len(plain) * 0.3 and len(plain) < 200):
            if not text:
                lines.append("")
            continue
        lines.append(LINK.sub(r"\1", text))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _chunks(text: str, size: int = PASSAGE_CHARS) -> list[str]:
    out, current = [], ""
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        while len(para) > size:                         # very long paragraph: cut on a sentence
            cut = para.rfind(". ", 0, size)
            cut = cut + 1 if cut > size // 3 else size
            out.append(para[:cut].strip())
            para = para[cut:].strip()
        if current and len(current) + len(para) + 2 > size:
            out.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        out.append(current)
    return out


def _terms(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.casefold()) if len(t) > 2 and t not in STOPWORDS]


class UniversityPageStore:
    def __init__(self, directory: Path = DEFAULT_DIR) -> None:
        self.directory = Path(directory)

    def path(self, uni_code: str) -> Path:
        return self.directory / f"{re.sub(r'[^A-Za-z0-9_-]', '', uni_code) or 'offering'}.json"

    def get(self, uni_code: str, fresh_only: bool = True) -> dict[str, Any] | None:
        try:
            record = json.loads(self.path(uni_code).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if fresh_only:
            days = CACHE_DAYS if record.get("pages") else EMPTY_CACHE_DAYS
            fetched = datetime.fromisoformat(record.get("fetched_at", "1970-01-01T00:00:00+00:00"))
            if datetime.now(timezone.utc) - fetched > timedelta(days=days):
                return None
        return record

    def save(self, record: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path(record["uni_code"]).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


class UniversityPages:
    def __init__(self, store: UniversityPageStore | None = None, domains: dict[str, list[str]] | None = None,
                 crawler_factory: Callable[[], Any] | None = None, enabled: bool | None = None) -> None:
        self.enabled = ENABLED if enabled is None else enabled     # the app follows settings.yaml; the CLI forces on
        self.store = store or UniversityPageStore()
        self.domains = load_domains() if domains is None else domains
        self.crawler_factory = crawler_factory

    # --- configuration ------------------------------------------------------------------------
    def domains_for(self, university: str) -> list[str]:
        return self.domains.get(str(university or ""), [])

    def unavailable_reason(self, course: dict[str, Any]) -> str | None:
        if not self.enabled:
            return "university website lookup is turned off (chat.website.enabled)"
        if not str(course.get("uni_code") or ""):
            return "no offering code for this course"
        if not self.domains_for(course.get("university")):
            return f"no official website on file for {course.get('university') or 'this university'}"
        if self.crawler_factory is None and (missing := missing_keys()):
            return "university website lookup needs " + ", ".join(missing)
        return None

    # --- fetching -----------------------------------------------------------------------------
    def crawler(self):
        if self.crawler_factory is None:
            from campusyamu.agents.career_trends.providers import build_web_crawler

            self.crawler_factory = build_web_crawler
        return self.crawler_factory()

    def fetch(self, course: dict[str, Any]) -> dict[str, Any]:
        """One limited search, saved to the cache. Raises RuntimeError on a provider failure."""

        from campusyamu.agents.career_trends.models import SearchQuery

        uni_code, university = str(course["uni_code"]), str(course.get("university") or "")
        domains = self.domains_for(university)
        text = f"{course.get('course_name', '')} degree programme {university}".strip()
        query = SearchQuery(category="university_website", text=text, include_domains=tuple(domains))
        documents = self.crawler().search_documents(query, MAX_PAGES)
        pages, seen = [], set()
        for doc in documents:
            if doc.url in seen or not domain_ok(doc.url, domains):
                continue
            seen.add(doc.url)
            body = _clean(doc.markdown or doc.description or "")
            if len(body) >= 80:
                pages.append({"url": doc.url, "title": doc.title or doc.url, "domain": doc.domain,
                              "text": body[:PAGE_CHARS]})
        record = {"uni_code": uni_code, "course_name": course.get("course_name"), "university": university,
                  "domains": domains, "query": text, "fetched_at": datetime.now(timezone.utc).isoformat(),
                  "pages": pages[:MAX_PAGES]}
        self.store.save(record)
        return record

    # --- per question ---------------------------------------------------------------------------
    @staticmethod
    def passages(record: dict[str, Any], question: str, course_name: str = "",
                 limit: int = PASSAGES) -> list[dict[str, Any]]:
        """The passages that best fit the question (TF-IDF over keyword terms), best first."""

        chunks = [(page, chunk) for page in record.get("pages", []) for chunk in _chunks(page["text"])]
        if not chunks:
            return []
        terms = Counter(_terms(question)) + Counter({t: 0.5 for t in _terms(course_name)})
        docs = [Counter(_terms(chunk)) for _, chunk in chunks]
        df = Counter(t for doc in docs for t in set(doc))
        scored = []
        for i, ((page, chunk), doc) in enumerate(zip(chunks, docs)):
            score = sum(w * (1 + math.log(doc[t])) * math.log(1 + len(docs) / df[t]) for t, w in terms.items() if doc[t])
            scored.append((score, -i, page, chunk))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        best = [s for s in scored if s[0] > 0][:limit] or scored[:1]    # nothing matches: the top page's start
        return [{"url": page["url"], "title": page["title"], "domain": page.get("domain", ""), "text": chunk}
                for _, _, page, chunk in best]


# --- LLM: the applicant profile from the pages -------------------------------------------------------
def website_model() -> str:
    return settings.model("website")


def _pages_for_llm(record: dict[str, Any]) -> list[dict[str, str]]:
    out, total = [], 0
    for i, page in enumerate(record.get("pages", []), 1):
        text = page["text"][:LLM_PAGE_CHARS]
        if total + len(text) > LLM_TOTAL_CHARS:
            text = text[:max(0, LLM_TOTAL_CHARS - total)]
        if not text:
            break
        total += len(text)
        out.append({"id": f"P{i}", "title": page["title"], "url": page["url"], "text": text})
    return out


def _llm(system: str, user: dict[str, Any], schema: dict[str, Any], name: str, model: str,
         max_tokens: int) -> dict[str, Any]:
    import os

    from campusyamu.core.openai_client import call_structured

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {"model": model, "store": False, "max_output_tokens": max_tokens,
               "input": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
               "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}}}
    return call_structured(payload, key, 90, "CampusYamu-UniversityPages/0.1")


def profile_request(record: dict[str, Any], course: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    pages = _pages_for_llm(record)
    ids = [p["id"] for p in pages] or ["P1"]
    schema = {"type": "object", "additionalProperties": False,
              "required": ["about_this_course", "relevant_pages", "facts", "missing", "specialisation_names"],
              "properties": {
                  "about_this_course": {"type": "boolean"},
                  "relevant_pages": {"type": "array", "items": {"type": "string", "enum": ids}},
                  "facts": {"type": "array", "items": {
                      "type": "object", "additionalProperties": False, "required": ["field", "detail", "sources"],
                      "properties": {"field": {"type": "string", "enum": list(PROFILE_FIELDS)},
                                     "detail": {"type": "string"},
                                     "sources": {"type": "array", "items": {"type": "string", "enum": ids}}}}},
                  "missing": {"type": "array", "items": {"type": "string", "enum": list(PROFILE_FIELDS)}},
                  "specialisation_names": {"type": "array", "items": {"type": "string"}}}}
    user = {"course": course.get("course_name"), "university": course.get("university"), "pages": pages}
    return user, schema


def extract_profile(record: dict[str, Any], course: dict[str, Any], model: str | None = None,
                    store: UniversityPageStore | None = None) -> dict[str, Any]:
    """The pages read into a cited course profile (one LLM call); saved into the cached record."""

    from campusyamu.prompts.university import WEBSITE_PROFILE_SYSTEM

    model = model or website_model()
    pages = _pages_for_llm(record)
    if not pages:
        profile = {"about_this_course": False, "relevant_pages": [], "facts": [], "missing": list(PROFILE_FIELDS),
                   "specialisation_names": []}
    else:
        user, schema = profile_request(record, course)
        raw = _llm(WEBSITE_PROFILE_SYSTEM, user, schema, "course_website_profile", model, 3500)
        known = {p["id"]: p for p in pages}
        facts = []
        for fact in raw.get("facts", []):
            cited = [s for s in fact.get("sources", []) if s in known]
            if fact.get("field") in PROFILE_FIELDS and str(fact.get("detail", "")).strip() and cited:
                facts.append({"field": fact["field"], "detail": str(fact["detail"]).strip(), "sources": cited})
        facts.sort(key=lambda f: PROFILE_FIELDS.index(f["field"]))
        covered = {f["field"] for f in facts}
        profile = {"about_this_course": bool(raw.get("about_this_course")) and bool(facts),
                   "relevant_pages": [s for s in raw.get("relevant_pages", []) if s in known],
                   "facts": facts,
                   "missing": [f for f in PROFILE_FIELDS if f not in covered],
                   "specialisation_names": list(dict.fromkeys(
                       n for n in (" ".join(str(x).split()) for x in raw.get("specialisation_names", []))
                       if 2 < len(n) <= 120))[:30]}
    profile.update(model=model, generated_at=datetime.now(timezone.utc).isoformat(), version=PROFILE_VERSION,
                   pages={p["id"]: {"title": p["title"], "url": p["url"]} for p in pages})
    record["profile"] = profile
    (store or UniversityPageStore()).save(record)
    return profile


# --- specialisation names: the UGC handbook first ---------------------------------------------------
def handbook_specialisations(course_code: str, university: str, handbook=None) -> list[str]:
    """The specialisations the UGC handbook lists for this course at this university ([] if none).
    Generic degree titles ("Bachelor of ... Honours") are not specialisations and are left out."""

    if handbook is None:
        from campusyamu.agents.course_details import HandbookCourseIndex

        handbook = HandbookCourseIndex()
    for block in handbook.blocks_for(str(course_code or "")):
        for heading, names in block.specializations.items():
            if same_institution(heading, university):
                return [n for n in names if not GENERIC_DEGREE.match(n.strip())]
    return []


def same_institution(heading: str, university: str, institutions: list[str] | None = None) -> bool:
    """Handbook sub-headings spell some institutions differently. "Trincomalee Campus of the Eastern
    University, Sri Lanka" is the Trincomalee Campus, not the Eastern University: the institution named
    FIRST in the heading wins."""

    h, u = heading.casefold().strip(" :_*"), str(university or "").casefold()
    if not u or u not in h:
        return False
    if h == u:
        return True
    names = [n.casefold() for n in (institutions if institutions is not None else load_domains())]
    positions = [(h.find(n), -len(n), n) for n in names if n in h]
    return bool(positions) and min(positions)[2] == u


# --- 2nd hop: one search per specialisation ---------------------------------------------------------
POSTGRADUATE = re.compile(r"post-?graduate|\bmsc\b|\bphd\b|\bmphil\b|\bpgd\b", re.I)


def _spec_rank(name: str, title: str, url: str) -> tuple[int, int]:
    """Prefer results whose title/URL carry the specialisation's words and are not postgraduate pages."""

    words = set(_terms(name))
    hay = set(_terms(f"{title} {re.sub(r'[/._-]', ' ', url)}"))
    return (len(words & hay) - 3 * bool(POSTGRADUATE.search(f"{title} {url}")), -len(url))


def _url_key(url: str) -> str:
    """http/https, www. and a trailing slash do not make a different page."""

    parts = urllib.parse.urlsplit(url.strip())
    host = (parts.hostname or "").casefold().removeprefix("www.")
    return f"{host}{parts.path.rstrip('/')}{'?' + parts.query if parts.query else ''}"


QUERY_FORMS = ("{name} {university}", "Department of {name} {university}")   # 2nd form: retry for not-found ones


def search_specialisations(record: dict[str, Any], course: dict[str, Any], names: list[str], crawler,
                           form: str = QUERY_FORMS[0], exclude: dict[str, set[str]] | None = None,
                           open_search: bool = True) -> list[dict[str, Any]]:
    """For each name: a search limited to the official domains (all names in parallel). Pages already tried
    (exclude: name -> url keys) are skipped. If nothing is found and open_search, one open search lists pages
    on other domains for review only. Returns one entry per specialisation, in the names' order."""

    from campusyamu.agents.career_trends.models import SearchQuery

    domains, university = record["domains"], str(course.get("university") or "")
    course_pages = {_url_key(p["url"]) for p in record.get("pages", [])}
    exclude = exclude or {}

    def one(name: str) -> dict[str, Any]:
        text = form.format(name=name, university=university)
        entry: dict[str, Any] = {"name": name, "query": text, "candidates": [], "off_list": [], "error": None}
        try:
            docs = crawler.search_documents(SearchQuery(category="university_specialisation", text=text,
                                                        include_domains=tuple(domains)), SPEC_CANDIDATES + 4)
        except RuntimeError as exc:
            entry["error"] = str(exc)[:200]
            docs = []
        seen = set(course_pages) | exclude.get(name, set())
        for doc in sorted(docs, key=lambda d: _spec_rank(name, d.title, d.url), reverse=True):
            key = _url_key(doc.url)
            body = _clean(doc.markdown or doc.description or "")
            if key in seen or not domain_ok(doc.url, domains) or len(body) < 80:
                continue
            seen.add(key)
            entry["candidates"].append({"url": doc.url, "title": doc.title or doc.url, "text": body[:PAGE_CHARS]})
            if len(entry["candidates"]) >= SPEC_CANDIDATES:
                break
        if open_search and not entry["candidates"] and entry["error"] is None:
            try:
                docs = crawler.search_documents(SearchQuery(category="university_specialisation_open", text=text), 5)
            except RuntimeError:
                docs = []
            entry["off_list"] = [{"url": d.url, "title": d.title or d.url} for d in docs
                                 if not domain_ok(d.url, domains)][:3]
        return entry

    wanted = names[:MAX_SPECIALISATIONS]
    if len(wanted) <= 1:
        return [one(n) for n in wanted]
    with ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, len(wanted))) as pool:
        return list(pool.map(one, wanted))


def specialisation_request(found: list[dict[str, Any]], course: dict[str, Any]
                           ) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    pages: dict[str, dict[str, Any]] = {}
    items, total = [], 0
    for entry in found:
        candidates = []
        for cand in entry["candidates"]:
            text = cand["text"][:SPEC_PAGE_CHARS][:max(0, SPEC_TOTAL_CHARS - total)]
            if not text:
                break
            pid = f"D{len(pages) + 1}"
            total += len(text)
            pages[pid] = {"name": entry["name"], "url": cand["url"], "title": cand["title"]}
            candidates.append({"id": pid, "title": cand["title"], "url": cand["url"], "text": text})
        if candidates:
            items.append({"name": entry["name"], "candidate_pages": candidates})
    names = [i["name"] for i in items] or ["-"]
    schema = {"type": "object", "additionalProperties": False, "required": ["cards"],
              "properties": {"cards": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False,
                  "required": ["name", "page", "reason", "overview", "modules", "facilities", "careers"],
                  "properties": {"name": {"type": "string", "enum": names},
                                 "page": {"type": "string", "enum": [*pages, "none"]},
                                 "reason": {"type": "string"},
                                 "overview": {"type": "string"}, "modules": {"type": "string"},
                                 "facilities": {"type": "string"}, "careers": {"type": "string"}}}}}}
    user = {"course": course.get("course_name"), "university": course.get("university"), "specialisations": items}
    return user, schema, pages


def _judge(found: list[dict[str, Any]], course: dict[str, Any], model: str
           ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """One LLM call over the candidates: (cards by name, reasons by name)."""

    from campusyamu.prompts.university import SPECIALISATION_SYSTEM

    cards: dict[str, dict[str, Any]] = {}
    reasons: dict[str, str] = {}
    if not any(e["candidates"] for e in found):
        return cards, reasons
    user, schema, pages = specialisation_request(found, course)
    raw = _llm(SPECIALISATION_SYSTEM, user, schema, "course_specialisation_cards", model, 4000)
    for card in raw.get("cards", []):
        name = card.get("name")
        reasons[name] = str(card.get("reason", "")).strip()
        page = pages.get(card.get("page"))           # "none" and unknown ids give no page
        if page and page["name"] == name and str(card.get("overview", "")).strip():
            cards[name] = {k: str(card.get(k, "")).strip() for k in ("overview", "modules", "facilities", "careers")}
            cards[name].update(page=card["page"], url=page["url"], title=page["title"])
    return cards, reasons


def _candidate_summary(cand: dict[str, Any]) -> dict[str, Any]:
    return {"url": cand["url"], "title": cand["title"], "chars": len(cand["text"]),
            "preview": " ".join(cand["text"].split())[:300]}


def specialisation_names(record: dict[str, Any], course: dict[str, Any], handbook=None) -> tuple[list[str], str]:
    """(names, source): the handbook's list for this university, else the website profile's, else none."""

    names = handbook_specialisations(course.get("course_code"), course.get("university"), handbook)
    if names:
        return names, "handbook"
    names = (record.get("profile") or {}).get("specialisation_names") or []
    return (names, "website") if names else ([], "none")


def explore_specialisations(record: dict[str, Any], course: dict[str, Any], crawler, model: str | None = None,
                            store: UniversityPageStore | None = None, names: list[str] | None = None,
                            source: str | None = None, save: bool = True) -> dict[str, Any]:
    """The 2nd hop: one search per specialisation (in parallel) and one LLM call to pick each page and write
    its card; then, for the ones still not found, one retry search ("Department of <name> <university>")
    over pages not tried yet, and one more LLM call. names default to specialisation_names(); the section is
    saved into the cached record unless save=False."""

    model = model or website_model()
    if names is None:
        names, source = specialisation_names(record, course)
    found = search_specialisations(record, course, names, crawler, open_search=False) if names else []
    cards, reasons = _judge(found, course, model)
    tried = {e["name"]: list(e["candidates"]) for e in found}
    queries = {e["name"]: [e["query"]] for e in found}
    errors = {e["name"]: e["error"] for e in found}
    off_list: dict[str, list[dict[str, str]]] = {}

    retry = [e["name"] for e in found if e["name"] not in cards and not e["error"]]
    if retry:
        again = search_specialisations(record, course, retry, crawler, form=QUERY_FORMS[1],
                                       exclude={n: {_url_key(c["url"]) for c in tried[n]} for n in retry})
        more_cards, more_reasons = _judge(again, course, model)
        cards.update(more_cards)
        for e in again:
            queries[e["name"]].append(e["query"])
            tried[e["name"]] += e["candidates"]
            off_list[e["name"]] = e["off_list"]
            errors[e["name"]] = errors[e["name"]] or e["error"]
            if e["name"] in more_reasons and (e["name"] in more_cards or e["candidates"]):
                reasons[e["name"]] = more_reasons[e["name"]]

    results = []
    for entry in found:
        name = entry["name"]
        card = cards.get(name)
        state = "found" if card else ("search_failed" if errors[name] else "not_found")
        results.append({"name": name, "state": state, "query": " | ".join(queries[name]), "card": card,
                        "reason": reasons.get(name, "" if tried[name] else "the search returned no usable page"),
                        "candidates": [_candidate_summary(c) for c in tried[name]],
                        "off_list": off_list.get(name, []), "error": errors[name]})
    section = {"version": SPECIALISATION_VERSION, "model": model, "source": source or "given",
               "generated_at": datetime.now(timezone.utc).isoformat(),
               "skipped": names[MAX_SPECIALISATIONS:], "results": results}
    record["specialisations"] = section
    if save:
        (store or UniversityPageStore()).save(record)
    return section


# --- printing (shared with campusyamu.web.course_research) -------------------------------------------
def format_profile(profile: dict[str, Any]) -> list[str]:
    lines = []
    if not profile.get("about_this_course"):
        lines.append("WARNING    : none of the pages is clearly about this course; the facts may be about the faculty")
    label = {f: f.replace("_", " ") for f in PROFILE_FIELDS}
    for fact in profile.get("facts", []):
        lines.append(f"\n  {label[fact['field']]:<20} {fact['detail']}  [{', '.join(fact['sources'])}]")
    if profile.get("missing"):
        lines.append(f"\n  not on the website: {', '.join(label[f] for f in profile['missing'])}")
    if profile.get("pages"):
        lines.append("\n  pages: " + "\n         ".join(f"{pid} {p['url']}" for pid, p in profile["pages"].items()))
    return lines


def format_specialisations(section: dict[str, Any]) -> list[str]:
    mark = {"found": "found", "not_found": "NOT FOUND", "search_failed": "SEARCH FAILED"}
    lines = []
    for r in section.get("results", []):
        card = r["card"]
        lines.append(f"\n  {r['name']}  [{mark[r['state']]}]  search: \"{r['query']}\"")
        if card:
            lines.append(f"     page       {card['page']}  {card['url']}")
            lines += [f"     {key:<10} {card[key]}" for key in ("overview", "modules", "facilities", "careers")
                      if card[key]]
            continue
        if r.get("reason"):
            lines.append(f"     why        {r['reason']}")
        lines += [f"     rejected   {c['url']}  ({c.get('chars', '?')} chars of text)" for c in r["candidates"]]
        lines += [f"     off-list   {c['url']}   (not on the domain list; add it to university_domains.json if "
                  "it is official)" for c in r["off_list"]]
        if r["error"]:
            lines.append(f"     error      {r['error']}")
    if section.get("skipped"):
        lines.append(f"\n  not searched (over the limit of {MAX_SPECIALISATIONS}): {', '.join(section['skipped'])}")
    return lines


# --- try it on its own --------------------------------------------------------------------------
def _resolve(course: str, university: str) -> dict[str, Any]:
    """Course + university names (loosely spelt) -> the offering from the knowledge graph."""

    import difflib

    from campusyamu.knowledge_graph.build_graph import load_graph

    graph, offerings = load_graph(), []
    for node, attrs in graph.nodes(data=True):
        if attrs["type"] == "Offering":
            linked = {graph.nodes[t]["type"]: graph.nodes[t] for _, t in graph.out_edges(node)}
            if "Course" in linked and "Institution" in linked:
                offerings.append({"uni_code": attrs["uni_code"], "course_code": linked["Course"].get("code"),
                                  "course_name": linked["Course"]["name"], "university": linked["Institution"]["name"]})

    def best(wanted: str, names: list[str], what: str) -> str:
        exact = {n.casefold(): n for n in names}
        if wanted.casefold() in exact:
            return exact[wanted.casefold()]
        contains = [n for n in names if wanted.casefold() in n.casefold()]
        if len(contains) == 1:
            return contains[0]
        close = difflib.get_close_matches(wanted, names, n=1, cutoff=0.5) or contains[:1]
        if not close:
            raise SystemExit(f"no {what} like {wanted!r}. Some options: {', '.join(sorted(names)[:15])} ...")
        return close[0]

    uni = best(university, sorted({o["university"] for o in offerings}), "university")
    here = [o for o in offerings if o["university"] == uni]
    name = best(course, sorted({o["course_name"] for o in here}), f"course at {uni}")
    return next(o for o in here if o["course_name"] == name)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from campusyamu.knowledge_graph.handbook_prose import _load_env

    parser = argparse.ArgumentParser(
        description="A course's applicant profile from the university's official website: one web search, then an "
                    "LLM reads the pages (overview, faculty, modules, specialisations, training, ...). Both cached.",
        epilog='e.g.  uv run python -m campusyamu.web.university_pages --course "Artificial Intelligence" '
               '--university Moratuwa')
    parser.add_argument("--course", required=True, help="course name, loosely spelt")
    parser.add_argument("--university", required=True, help='university name, loosely spelt (e.g. "Moratuwa")')
    parser.add_argument("--refresh", action="store_true", help="ignore the cache and search again")
    parser.add_argument("--full", action="store_true", help="print each page's full kept text")
    parser.add_argument("--no-llm", action="store_true", help="skip the LLM; show keyword-matched passages only")
    parser.add_argument("--no-specialisations", action="store_true",
                        help="skip the 2nd hop (one search per specialisation)")
    args = parser.parse_args(argv)
    _load_env(None)

    offering = _resolve(args.course, args.university)
    agent = UniversityPages(enabled=True)
    print(f"course     : {offering['course_name']}  ({offering['uni_code']})")
    print(f"university : {offering['university']}")
    print(f"domains    : {', '.join(agent.domains_for(offering['university'])) or '-'}")
    if reason := agent.unavailable_reason(offering):
        print(f"cannot search: {reason}")
        return 1
    record = None if args.refresh else agent.store.get(offering["uni_code"])
    if record:
        print(f"source     : cache from {record['fetched_at'][:16]} (no search; --refresh to search again)")
    else:
        started = time.perf_counter()
        try:
            record = agent.fetch(offering)
        except RuntimeError as exc:
            print(f"search failed: {exc}")
            return 1
        print(f"source     : web search \"{record['query']}\"  ({time.perf_counter() - started:.1f} s)")

    pages = record["pages"]
    print(f"\n{len(pages)} official page(s) found:")
    for i, page in enumerate(pages, 1):
        print(f"  [{i}] {page['title'][:90]}\n      {page['url']}  ({len(page['text'])} chars kept)")
        if args.full:
            print("      " + page["text"].replace("\n", "\n      ") + "\n")
    if not pages:
        print("  nothing on those domains matched; try the university's site by hand to check the course page exists")
        return 0

    if args.no_llm:
        question = f"what is the {offering['course_name']} degree about modules specialisations faculty"
        print("\nbest passages (keyword match, no LLM):")
        for i, p in enumerate(UniversityPages.passages(record, question, offering["course_name"]), 1):
            print(f"\n  W{i}  {p['url']}\n  " + p["text"].replace("\n", "\n  "))
        return 0

    profile = record.get("profile")
    try:
        if profile and not args.refresh and profile.get("version") == PROFILE_VERSION:
            print(f"\nprofile    : cached ({profile['model']}, {profile['generated_at'][:16]})")
        else:
            started = time.perf_counter()
            profile = extract_profile(record, offering, store=agent.store)
            print(f"\nprofile    : {profile['model']} read {len(profile['pages'])} page(s) "
                  f"({time.perf_counter() - started:.1f} s)")
    except RuntimeError as exc:
        print(f"\nLLM failed: {exc}  (use --no-llm to see the keyword passages)")
        return 1
    print("\n".join(format_profile(profile)))

    names, source = specialisation_names(record, offering)
    if not names or args.no_specialisations:
        if not names:
            print("\nspecialisations: none in the handbook or on the website")
        return 0
    section = record.get("specialisations")
    fresh = (section and not args.refresh and section.get("version") == SPECIALISATION_VERSION
             and section.get("generated_at", "") >= profile["generated_at"])
    try:
        if fresh:
            print(f"\nspecialisations: cached ({section['generated_at'][:16]})")
        else:
            started = time.perf_counter()
            print(f"\nspecialisations ({source}): one search each for {min(len(names), MAX_SPECIALISATIONS)} on "
                  f"{', '.join(record['domains'])}, in parallel ...")
            section = explore_specialisations(record, offering, agent.crawler(), store=agent.store)
            print(f"                 done ({time.perf_counter() - started:.1f} s)")
    except RuntimeError as exc:
        print(f"\nspecialisations failed: {exc}")
        return 1
    print("\n".join(format_specialisations(section)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
