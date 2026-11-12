# CampusYamu

Admissions advisor for Sri Lankan state universities, built from the UGC
*Student Handbook 2024/2025*. For one student it finds the courses they can apply
for, compares their Z-score with past cut-offs, measures travel from home, scores
each course against their interests, and suggests three orderings with an
explanation per course. A web app adds a course chat that answers from the
handbook (and, on request, from web research on careers).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it fits together.

## Quick start

```bash
make install            # uv sync
cp .env.example .env    # add OPENAI_API_KEY (optional: NEO4J_*, TAVILY_API_KEY …)
make web                # http://127.0.0.1:8770
```

Without an OpenAI key everything still runs: interests use keyword matching,
feedback uses templates, and the course chat is disabled.

### Command line

```bash
uv run python -m campusyamu.pipeline \
  --stream "Physical Science" \
  --al "Combined Mathematics:A" --al "Physics:B" --al "Chemistry:C" --cgt 40 \
  --admission-district Gampaha --home Minuwangoda \
  --ol Science:B --ol English:B --ol Maths:A --z-score 1.56 \
  --prefer "engineering, design" --view rankings --save outputs/student_report.json
```

Run with no flags to be asked the questions. `--no-llm` keeps everything offline.

### Docker

```bash
docker compose up --build -d                    # web app
docker compose --profile neo4j up --build -d    # + Neo4j for handbook search in the chat
```

## Project structure

```
.
├── src/campusyamu/        the package (see docs/ARCHITECTURE.md)
│   ├── core/              paths, settings, OpenAI client
│   ├── knowledge_graph/   handbook → rules → graph, eligibility, Neo4j export
│   ├── handbook_search/   vector + BM25 handbook search
│   ├── agents/            course_finder, zscore, travel_time, course_details,
│   │                      preference, ranking, career_trends
│   ├── pipeline/          LangGraph student pipeline + CLI
│   └── web/               web app, course chat, career-outlook cache
├── data/
│   ├── raw/               handbook, UGC tables, travel CSVs, Z-score DB
│   ├── reference/         owner-curated decisions and mappings
│   ├── processed/         knowledge graph, chunks, embeddings, travel DB
│   └── cache/             career research cache
├── config/settings.yaml   weights, thresholds, default models, port
├── tests/                 unittest suite
├── scripts/               one-off source preparation
├── docker/ + docker-compose.yml
├── docs/                  architecture and agent guides
└── outputs/               reports and run outputs (gitignored)
```

## Configuration

* **Secrets** — `.env` only (template: [.env.example](.env.example)).
* **Tunables** — [config/settings.yaml](config/settings.yaml): ranking weights
  (`cutoff_weight` 2.5, distance mode), what-if nudge, interest thresholds,
  default models, web host/port. Restart the web app after editing.
* **Owner decisions** — `data/reference/`: rule interpretations, course category
  marks, travel site decisions. These are data, reviewed by hand; tests guard them.

## Common tasks

`make help` lists everything. The main ones:

| Task | Command |
| --- | --- |
| Run tests | `make test` |
| Web app | `make web` |
| Rebuild the knowledge graph (no API calls) | `make kg` |
| Load graph + travel data into Neo4j | `make neo4j-push` |
| Handbook search index | `make search-chunk search-embed search-load` (embed is paid, cents) |
| Rebuild travel DB from the CSVs | `make travel-db` |
| Career research for a course (paid) | `make career COURSE="Quantity Surveying"` |

## Agents in detail

* [Z-score agent](docs/zscore_agent.md)
* [Career-trends agent](docs/career_trends_agent.md) — web evidence, research agent, cited future SWOT

## Notes

* Z-score bands describe last year's cut-offs, not admission probabilities.
* The handbook is the only source for eligibility; anything it does not say is
  reported as such rather than guessed.
