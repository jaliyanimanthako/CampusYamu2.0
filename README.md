# CampusYamu agents

This repository contains focused components for the larger CampusYamu agentic
system.

## Z-score agent

The deterministic Z-score agent accepts:

- applicant district
- course of study
- student Z-score

It retrieves every available academic year for that course and district from
the read-only SQLite database. Results are grouped by institution and analyzed
with ordinary Python statistics.

### Use from Python

```python
from zscore_agent import ZScoreAgent

agent = ZScoreAgent()
result = agent.analyze(
    district="Gampaha",
    course="Medicine",
    z_score=2.10,
)
```

The response contains all numeric and NQC history, statistical summaries,
`historical_alignment`, and `evidence_confidence`. Historical alignment is a
comparison with calibrated historical cutoffs, not an admission probability.

### Run from the command line

```bash
python -m zscore_agent.cli \
  --district Gampaha \
  --course Medicine \
  --z-score 2.10
```

Add `--json` for the complete structured response.

The database currently has no syllabus column. If a future dataset contains old
and new syllabus cutoffs, add syllabus as an explicit fourth input rather than
guessing it.

## Career-trends agent

The current career agent is a collection layer. It expands each course into
occupation search terms, runs bounded Firecrawl web searches for local jobs,
local labour-market evidence, local challenges, global outlook evidence, and
field-specific sources. Challenge searches explicitly include layoffs, hiring
slowdowns, internship shortages, entry-level competition, unemployment, skills
gaps, automation, and displacement. It retains the raw scraped Markdown with
its URL and search query.

```python
from career_trends_agent import CareerWebResearchAgent, WebResearchRequest

agent = CareerWebResearchAgent()
result = agent.research(
    WebResearchRequest(
        courses=("Medicine", "IT"),
        region="Sri Lanka",
    )
)
```

The response contains one `course_research` entry per input course, including
the generated queries, discovered documents, raw Markdown, source tier, trust
classification, and any failed searches. Unknown courses fall back to their
original course name as the search term.

### Run from the command line

The CLI automatically loads `.env` from the current project directory, so no
shell export commands are needed:

```bash
python3 -m career_trends_agent.cli \
  --course Medicine \
  --region "Sri Lanka" \
  --results-per-query 3 \
  --max-sources 10 \
  --json
```

Use `--json` to include the scraped Markdown. For an installed package, the
equivalent command is `campus-career-trends`. Search progress is printed as each
query finishes; pass `--quiet` to hide it.

Web search uses Tavily (`TAVILY_API_KEY`) or Firecrawl (`FIRECRAWL_API_KEY`).
Choose with `--provider tavily|firecrawl` or `SEARCH_PROVIDER` in `.env`; by
default Tavily is used whenever its key is present. Tavily runs `advanced`
searches (2 credits each, about 10 per course); set `TAVILY_SEARCH_DEPTH=basic`
to halve that. The planner expresses site restrictions, recency windows, and
country boosting as structured query fields, which each provider translates
into its own syntax.

All searches, web and Reddit, run concurrently on one asyncio event loop
(`await agent.aresearch(request)` inside async apps; `agent.research(request)`
from scripts). Reddit has its own concurrency limit, so a slow Apify run never
delays web searches, and successful results are cached in memory for 24
hours within a long-lived process. URLs are deduplicated and classified against
a registry of Sri Lankan job portals, official institutions, professional
bodies, and global outlook organizations. Unrecognized domains are retained as
`unverified` so later analysis cannot silently treat them as authoritative.

### Reddit community signals (optional)

Set `APIFY_API_TOKEN` in `.env` to add a `community_signals` search that
collects Reddit posts and their top comments through the Apify actor
`harshmaur/reddit-scraper` (override with `APIFY_REDDIT_ACTOR`; `trudax/reddit-scraper-lite` is also supported). Without the
token, or with `--no-reddit`, this step is skipped and the run is otherwise
unchanged. Reddit evidence is tagged `community_discussion`, is never marked
trusted, and the SWOT prompt forbids high-confidence findings based on it
alone. Apify is a prototype-stage source: `ApifyRedditClient` sits behind the
same `search_documents` interface as Firecrawl, so it can be replaced with an
official Reddit API client before commercial launch without other changes.
Opportunity and challenge documents are selected in a category-balanced order,
so job advertisements cannot use the entire source limit and hide risk evidence.
The result reports `category_coverage` and shows categories where no evidence
was found; no negative result is interpreted as proof that no risk exists.

## Future SWOT analytics

The analytics stage is separate from web collection. It reads a JSON evidence
file, sends only that collected evidence to the OpenAI Responses API, and
produces a structured SWOT for the likely job market four or five years later.
It does not perform another web search.

### One command: course in, SWOT out

```bash
python3 -m career_trends_agent.pipeline_cli \
  --course "Computer Science" \
  --horizon-years 5 \
  --save-evidence cs_evidence.json
```

This runs web and Reddit collection concurrently, then the cited future SWOT,
and prints the outlook, SWOT findings, limitations, and the numbered sources
each finding cites. Each course is searched from eight angles: live local jobs,
local market, local challenges, global outlook, international pathways
(overseas demand, migration, remote work), further study (postgraduate,
specialisation, scholarships), field-specific official sources, and Reddit.
Before the job searches, a career-discovery step runs one web search for
career pages about the course ("what jobs can graduates do") and has the model
list the job titles those pages name; titles whose key words do not appear in
the page text are discarded. Discovered titles lead the job searches, with the
built-in course taxonomy filling any gaps, so unlisted courses such as
Financial Mathematics are searched by real roles (risk analyst, actuarial
analyst, quantitative analyst) instead of by their name. Results are cached for
30 days in `data/career_paths_cache.json` (`--refresh` ignores the cache,
`--no-discovery` skips the step, `DISCOVERY_MODEL` can name a cheaper model).
Reddit collection starts immediately and runs alongside discovery.

Discovery also looks for emerging specialisations: small, growing areas inside
the profession that job searches rarely surface (for quantity surveying:
model-based measurement, green building certification, construction law and
disputes). Two extra worldwide searches cover "the future of the profession" and
change driven by sustainability, law and regulation, and contracts. The model
lists the areas those pages name, spread across different kinds of change, and
the same grounding check applies. One more search then targets the discovered
areas (or asks about them generally when discovery is off). The analysis reports
2 to 4 of them as "Smaller areas worth knowing about" (`niche_specialisations`),
each with why it matters. A single source is enough for this section, and each
area is labelled as a niche, not a mass hiring market.

The SWOT is an analysis, not advice, and a forecast, not a job board. The
prompt forbids recommendations ("consider...", "you should...") and references
to individual job adverts. Job listings are used only together, to describe the
current situation, and the summary says once that current hiring may look
different by the entry year. `analysis_guardrails.py` enforces the same rules
in code, along with specificity: every finding must name a concrete detail
found in the sources it cites. Failing items go back to the model once with the
reasons; advice or advert sentences that survive are cut, and findings left
generic or empty are dropped. `analysis_context` records how many of each.

### Research agent (gap filling)

Between collection and the SWOT, a small agent reviews what the fixed searches
found and searches for what they missed. It is built on a reusable harness in
`career_trends_agent/harness/`:

| Part | File | What it does here |
| --- | --- | --- |
| Tool registry | `harness/tools.py` | One tool, `web_search` (the configured Tavily/Firecrawl crawler). Tool errors go back to the model as text. |
| Model | `harness/model.py` | Tool calling through the Responses API. `AGENT_MODEL`, default `gpt-4o-mini`. |
| Context management | `harness/context.py` | Every 3 turns the transcript is replaced by the model's notes plus a state summary from the harness (sources, searches, open gaps), so code-tracked facts are never lost. |
| Guardrails | `research_harness.py` | Search budget (6), at most 3 searches per turn, no repeated queries. The answer is refused until every angle has sources, 3 trusted sources are held, all three drivers of change (technology; sustainability or climate; law, regulation or contracts) have been searched, and 3 niche areas are verified. A niche area must be specific (not "sustainability" or "AI and technology") and named in the pages it cites. |
| Agent loop | `harness/loop.py` | Model turn, guarded tool calls, compaction, guarded finish, up to 9 turns. |

A gap the agent cannot fill after its retries or budget does not block forever.
It is reported (`status: partial`, `unfilled_gaps`), never hidden. The agent's
pages join the evidence, and its verified niche areas reach the analysis as
leads that the SWOT model checks against those pages. `--no-agent` skips it;
`--agent-iterations` and `--agent-searches` change the limits.

Besides the SWOT, the analysis gives two verdicts: where the stronger
opportunities are (`local_stronger`, `balanced`, `overseas_stronger`,
`unclear`) and the role of further study (`essential`, `helpful`, `optional`,
`unclear`). Social-media pages (Facebook, Instagram, TikTok, X, YouTube) are
excluded because they yield little usable text. All API keys are checked before any credits are spent.
Use `--json` for machine-readable output (`campus-career-swot` when installed),
or `CareerTrendsPipeline().run(request)` / `await ...arun(request)` in code.

The two stages can also be run separately.

First collect and save evidence:

```bash
python3 -m career_trends_agent.cli \
  --course Law \
  --json > law_evidence.json
```

Then analyze that exact evidence:

```bash
python3 -m career_trends_agent.analysis_cli \
  --evidence law_evidence.json \
  --horizon-years 5 \
  --json
```

The analytics CLI loads `OPENAI_API_KEY` and `OPENAI_MODEL` from `.env`. Every
SWOT finding contains evidence IDs, a `direct_evidence` or `forward_inference`
label, and confidence. Unknown evidence references cause that course analysis
to fail rather than returning an unsupported finding. Scraped page instructions
are explicitly treated as untrusted data.

The OpenAI call uses the Responses API with strict Structured Outputs. This
stage makes plausible future inferences; it does not claim to be a precise or
guaranteed forecast.

## Structure

- `zscore_agent/`: read-only historical cutoff analysis
- `career_trends_agent/`: raw web collection and evidence-grounded future SWOT
- `tests/`: one end-to-end behavior test for each agent

## Test

```bash
python -m unittest discover -s tests -v
```
