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
cp .env.example .env    # add GEMINI_API_KEY or OPENAI_API_KEY (optional: NEO4J_*, TAVILY_API_KEY …)
make api                # the API (FastAPI): http://127.0.0.1:8780/docs  (web page + mobile app use it)
make web                # the web page: http://127.0.0.1:8770  (needs `make api` running in another terminal)
```

The language model is Gemini or OpenAI: `llm.provider` in `config/settings.yaml` picks it, with
models per provider under `models.gemini` / `models.openai`. `make llm-check` makes three tiny calls
to confirm the setup. Without the provider's key everything still runs: interests use keyword
matching, feedback uses templates, and the course chat is disabled.

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

#### Backend for frontend development

Runs the API in Docker against your own Neo4j instance (Neo4j Desktop); the frontend
(`frontend/`, `npm run dev`) calls http://127.0.0.1:8780. Needs Docker Desktop (or Docker Engine
with compose v2) and a Neo4j 5+ instance. From a fresh clone:

```bash
cp .env.example .env     # then fill in .env (below)
                         # start your instance in Neo4j Desktop
make docker-backend      # build, load your Neo4j from data/, start the API, wait until healthy
```

It prints `backend ready` when the API answers. The first build takes a few minutes; later runs
take under a minute. Loading Neo4j uses only files in the repo (no API calls) and replaces only
the app's own nodes. Re-run it after pulling changes (it rebuilds and reloads Neo4j).

`.env` for the backend:

| Key | For |
|---|---|
| The key of `llm.provider` in `config/settings.yaml`: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY` | chat, recommendations with AI, research |
| The key of `llm.embedding_provider` (handbook search) | one small embedding call per chat question |
| `GEMINI_API_KEY` | the chat's scope check (skipped without it) |
| `NEO4J_PASSWORD` (your instance's password), `NEO4J_DATABASE=neo4j`; keep `NEO4J_URI_DOCKER=bolt://host.docker.internal:7687` (how a container reaches Neo4j Desktop on your machine) | your Neo4j instance |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_DB_URL` (from the backend owner) | sign-in and chat memory. With `SUPABASE_URL` set, every endpoint except `/v1/health` needs `Authorization: Bearer <Supabase access token>`; leave it empty for an open API without memory |
| `TAVILY_API_KEY` (optional) | web research for careers and university websites |

What the frontend uses:

- API: http://127.0.0.1:8780; interactive docs at `/docs`; the OpenAPI file at `/openapi.json`
  (regenerate typed clients from it); endpoints, errors and sign-in in [docs/API.md](docs/API.md).
- Health: `curl http://127.0.0.1:8780/v1/health`.
- CORS allows any origin (`api.cors_origins` in settings.yaml, or `API_CORS_ORIGINS` in `.env`).

Day to day: keep the Neo4j instance started; `make docker-logs` (API logs), `make docker-down`
(stop). Settings (`config/settings.yaml`) are mounted: edit, then `docker compose restart api`.
Without make, the same steps are listed at the top of `docker-compose.yml`. On Linux, Neo4j must
listen beyond localhost for the container to reach it (`server.default_listen_address=0.0.0.0`);
Docker Desktop on Mac and Windows needs nothing.

`make docker-demo`: the backend plus the built-in web page on http://127.0.0.1:8770.

### Monitoring with Langfuse (optional)

Every AI call (course chat, memory, guardrail, interests, feedback, website and career research,
embeddings) is traced to a self-hosted [Langfuse](https://langfuse.com): prompt, reply, model,
provider, tokens, cost, time and errors, grouped per API request (`chat`, `recommendations`,
`career research`) and tagged with the signed-in student's id (never email or name). Off until the
keys are set; a Langfuse outage never breaks a request.

1. Run Langfuse (its own Docker setup, separate from this repo; needs about 4 GB RAM):
   ```bash
   git clone https://github.com/langfuse/langfuse.git && cd langfuse
   docker compose up -d          # http://localhost:3000; change the CHANGEME secrets before exposing it
   ```
2. In Langfuse: sign up, create a project, then Settings → API keys.
3. In `.env`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST=http://localhost:3000`
   (the Docker backend reaches it through `LANGFUSE_HOST_DOCKER`, default
   `http://host.docker.internal:3000`).
4. `make llm-check`: the three test calls appear as a trace named `llm-check`, and the last line
   says whether Langfuse accepted the keys.

`tracing:` in `config/settings.yaml`: `capture_content: false` sends no prompts or answers (only
models, tokens, cost and timings); `prices` sets USD per 1M tokens for models Langfuse has no price
for (free tiers: 0); `sample_rate`, `environment`.

## Project structure

```
.
├── src/campusyamu/        the package (see docs/ARCHITECTURE.md)
│   ├── core/              paths, settings, language-model client (llm.py: OpenAI, Gemini, OpenRouter or Groq)
│   ├── knowledge_graph/   handbook → rules → graph, eligibility, Neo4j export
│   ├── handbook_search/   vector + BM25 handbook search
│   ├── agents/            course_finder, zscore, travel_time, course_details,
│   │                      preference, ranking, career_trends
│   ├── pipeline/          LangGraph student pipeline + CLI
│   ├── api/               FastAPI service (/v1): the backend for the web page and the mobile app
│   ├── prompts/           every LLM prompt in one place (python -m campusyamu.prompts lists them)
│   └── web/               web page (static), course chat, career-outlook cache
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
| Public API (FastAPI, see [docs/API.md](docs/API.md)) | `make api` |
| Rebuild the knowledge graph (no API calls) | `make kg` |
| Load graph + travel data into Neo4j | `make neo4j-push` |
| Handbook search index | `make search-chunk search-embed search-load` (embed is paid, cents) |
| Rebuild travel DB from the CSVs | `make travel-db` |
| Career research for a course (paid) | `make career COURSE="Quantity Surveying"` |

## Agents in detail

* [Public API](docs/API.md) — endpoints, request/response shapes, flow for app clients
* [Z-score agent](docs/zscore_agent.md)
* [Career-trends agent](docs/career_trends_agent.md) — web evidence, research agent, cited future SWOT

## Notes

* Z-score bands describe last year's cut-offs, not admission probabilities.
* The handbook is the only source for eligibility; anything it does not say is
  reported as such rather than guessed.
