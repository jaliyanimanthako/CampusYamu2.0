# CampusYamu architecture

CampusYamu turns the UGC *Student Handbook 2024/2025* into an admissions advisor:
which courses a student can apply for, how their Z-score compares with past
cut-offs, how far each campus is from home, which courses fit their interests,
and in what order to list them. Every number comes from data the project builds
and checks; language models only read free text (interests, questions) and word
explanations.

## Student pipeline (LangGraph)

`src/campusyamu/pipeline/graph.py` — one run per student, used by the CLI and the web app.

```mermaid
flowchart TD
    A[validate_profile] -->|bad input| Z([end with errors])
    A --> B[find_courses]
    B -->|one Send per course| C[analyze_course x N<br/>Z-score agent]
    B -->|if interests given| D[score_preferences<br/>preference agent]
    C --> E[assemble]
    D --> E
    B -->|nothing to analyse| E
    E --> F[course_details<br/>handbook section per course]
    F --> G[rank_suggestions<br/>3 orders + what-if]
    G --> H[explain_rankings<br/>feedback per course]
    H --> Y([report])
```

| Node | Agent | What it does | LLM |
| --- | --- | --- | --- |
| validate_profile | course_finder | A/L subjects and grades, admission district (§1.5), home DS division | – |
| find_courses | course_finder + knowledge_graph + travel_time | A/L eligibility from the graph's rules, O/L checks, aptitude tests, teaching site and travel time per offering | – |
| analyze_course | zscore | past cut-offs for the admission district, calibrated estimate ± uncertainty, band | – |
| score_preferences | preference | interests → categories; match (1–10), mismatch (−1…−10), net per course | 1 call (keyword fallback) |
| assemble | – | bands, interest groups, preference score per row | – |
| course_details | course_details | the course's own handbook block (programmes, duration, medium, notes) | – |
| rank_suggestions | ranking | order 1 Z-score, order 2 interests + cut-off, order 3 + distance; what-if re-ranking | – |
| explain_rankings | ranking.feedback | summary, a note per course, "if you care more about…" advice | 1 call (template fallback) |

## Components

```
src/campusyamu/
├── core/              paths.py (every file location), settings.py (config/settings.yaml), openai_client.py
├── knowledge_graph/   handbook → tables/prose → A/L rules → NetworkX graph; eligibility checker; Neo4j export; graph chatbot
├── handbook_search/   parent/child chunks, OpenAI embeddings, Neo4j vector + BM25, RRF, optional cross-encoder rerank
├── agents/
│   ├── course_finder/   step 1: courses a student can apply for
│   ├── zscore/          historical cut-off analysis (SQLite)
│   ├── travel_time/     DS division × campus road matrix (SQLite), teaching-site placement
│   ├── course_details/  handbook block per course, found by course code
│   ├── preference/      interest categories, match/mismatch marks
│   ├── ranking/         suggestion orders, what-if sensitivity, feedback
│   └── career_trends/   web research (Tavily/Firecrawl, Reddit) + research agent + cited future SWOT
├── pipeline/          the LangGraph student pipeline + CLI
└── web/               stdlib HTTP server, single-page UI, course chat, career-outlook cache
```

## Data

```
data/
├── raw/          as received: handbook PDF/Markdown + UGC tables, travel CSVs, Z-score DB
├── reference/    owner-curated: owner_interpretations, A/L subject list, course categories, travel decisions
├── processed/    built by the pipelines: knowledge_graph/ (graph, rules, chunks, embeddings), travel/travel_times.db
└── cache/        career_paths_cache.json, career_outlooks/<course>.json (web research, reused across students)
outputs/          reports and run outputs (gitignored)
config/           settings.yaml — weights, thresholds, default models, web port
```

`data/processed/knowledge_graph/source_registry.json` records each raw source's
path and SHA-256; the build refuses to use a changed source until it is
re-registered (`make kg`).

## Rules and provenance

* **A/L eligibility** — handbook prose is parsed deterministically where possible;
  remaining clauses were proposed by a model, verified, and accepted only when a
  behavioural check over every subject/grade combination agrees
  (`knowledge_graph/al_rule_semantics.py`). Ambiguous wording is settled by the
  project owner in `data/reference/owner_interpretations.json`, with test cases.
* **Arts stream** — §2.2.1.1 basket rules are executed directly (`arts_rules.py`).
* **"N other subjects"** — such clauses are checked jointly with the grade clauses,
  so one subject cannot satisfy both.
* Every eligibility answer cites the handbook section and page.

## Language-model use and guardrails

| Where | Input | Output | Guardrails |
| --- | --- | --- | --- |
| preference | student's interests | categories + marks per eligible course | strict JSON schema with enums; unknown ids dropped; missing marks filled from reviewed category marks |
| ranking feedback | computed what-if facts | summary + note per course | may only reference given courses; template fallback |
| course chat | question + course section + student's facts + handbook search + career outlook | cited answer | answer only from numbered sources; never promise admission; unknown source ids dropped |
| career research | course name | cited 5-year SWOT | runs only when a student asks; evidence-referenced findings, guardrails in `career_trends/analysis_guardrails.py` |
| knowledge graph | handbook clauses | rule proposals | offline, owner-reviewed; not used at request time |

All calls use the OpenAI Responses API with `store: false`. Keys live in `.env`;
models default from `config/settings.yaml` and can be overridden per role.

## Web app

`python -m campusyamu.web` (port 8770): `GET /api/options`, `POST /api/run`
(the pipeline), `POST /api/ask` (course chat), `GET /api/career`,
`POST /api/career/research` (background job, started only from a chat request).
One request at a time; career research runs in a background thread.
