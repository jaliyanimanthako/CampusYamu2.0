# CampusYamu — common tasks.  `make help` lists them.
# Targets marked (paid) call the language model (llm.provider in config/settings.yaml: OpenAI, Gemini, OpenRouter or Groq)
# or web-search APIs, with the keys in .env.

UV ?= uv
RUN = $(UV) run
KG = campusyamu.knowledge_graph
PORT ?= 8770
API_PORT ?= 8780
COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: llm-check help install install-rerank frontend-install frontend-build test web web-react api student kg kg-refresh kg-viewer kg-chat neo4j-push \
        search-chunk search-embed search-load travel-db career research clean docker-build docker-up docker-down docker-logs \
        neo4j-seed docker-demo docker-seed docker-backend

help:
	@echo "Setup"
	@echo "  make install          install the package and dependencies (uv sync)"
	@echo "  make install-rerank   also install the local cross-encoder reranker (large)"
	@echo "Run"
	@echo "  make api              the API on http://127.0.0.1:$(API_PORT)/docs (used by the web page and the mobile app)"
	@echo "  make web              built-in web page on http://127.0.0.1:$(PORT) (API: make api or make docker-backend)"
	@echo "  make web-react        build the React frontend, then serve it on http://127.0.0.1:$(PORT)"
	@echo "  make student          student pipeline in the terminal (asks the questions)"
	@echo "  make test             run the test suite"
	@echo "  make llm-check        three tiny calls to the llm.provider model: JSON, tool call, embedding (paid, ~free)"
	@echo "Knowledge graph (handbook -> rules -> graph)"
	@echo "  make kg               validate sources and rebuild the graph (no API calls)"
	@echo "  make kg-refresh       re-check owner interpretations against the rules (no API calls)"
	@echo "  make kg-viewer        rebuild the HTML graph viewer"
	@echo "  make kg-chat          graph chatbot server (paid per question)"
	@echo "  make neo4j-push       load the graph + travel data into Neo4j (needs NEO4J_* in .env)"
	@echo "  make neo4j-seed       fill Neo4j from data/: graph, travel times, handbook search (no API calls)"
	@echo "Handbook search (Neo4j vector + BM25)"
	@echo "  make search-chunk     parent/child chunks from the handbook"
	@echo "  make search-embed     embed the chunks for llm.provider (paid, cents; cached; PROVIDER=all for every key set)"
	@echo "  make search-load      load chunks + embeddings into Neo4j"
	@echo "Data"
	@echo "  make travel-db        rebuild data/processed/travel/travel_times.db from the CSVs"
	@echo "  make career COURSE=\"Quantity Surveying\"   web career research for one course (paid)"
	@echo "  make research COURSE=Engineering UNI=Moratuwa   career + university website + specialisations, in parallel (paid)"
	@echo "Docker"
	@echo "  make docker-backend   load your Neo4j (NEO4J_URI_DOCKER), start the API, wait until healthy"
	@echo "  make docker-demo      docker-backend plus the built-in web page"
	@echo "  make docker-up        build and start API + web page (no Neo4j loading)"
	@echo "  make docker-seed      load the graph + handbook search into the NEO4J_URI_DOCKER instance"
	@echo "  make docker-down / docker-logs"
	@echo "  make clean            remove caches and build files"

install:
	$(UV) sync

install-rerank:
	$(UV) sync --extra rerank

frontend-install:
	cd frontend && npm ci

frontend-build:
	cd frontend && (test -x node_modules/.bin/tsc || npm ci) && npm run build

test:
	$(RUN) python -m unittest discover -s tests

llm-check:
	$(RUN) python -m campusyamu.core.llm --check

web:
	$(RUN) python -m campusyamu.web --port $(PORT) --page builtin

web-react: frontend-build
	$(RUN) python -m campusyamu.web --port $(PORT)

api:
	$(RUN) python -m campusyamu.api --port $(API_PORT)

student:
	$(RUN) python -m campusyamu.pipeline

kg:
	$(RUN) python -m $(KG).source_registry
	$(RUN) python -m $(KG).build_graph

kg-refresh:
	$(RUN) python -m $(KG).handbook_prose --refresh-deterministic
	$(RUN) python -m $(KG).build_graph

kg-viewer:
	$(RUN) python -m $(KG).graph_viewer

kg-chat:
	$(RUN) python -m $(KG).chat_server

neo4j-seed:
	$(RUN) python -m campusyamu.neo4j_seed

neo4j-push:
	$(RUN) python -m $(KG).neo4j_export --push
	$(RUN) python -m campusyamu.agents.travel_time.neo4j_load

search-chunk:
	$(RUN) python -m campusyamu.handbook_search chunk

search-embed:
	$(RUN) python -m campusyamu.handbook_search embed $(if $(PROVIDER),--provider $(PROVIDER))

search-load:
	$(RUN) python -m campusyamu.handbook_search load

travel-db:
	$(RUN) python -m campusyamu.agents.travel_time.build_db

career:
	@test -n "$(COURSE)" || (echo 'usage: make career COURSE="Quantity Surveying"' && exit 1)
	$(RUN) python -m campusyamu.web.career_outlook --course "$(COURSE)"

research:
	$(RUN) python -m campusyamu.web.course_research --course "$(COURSE)" --university "$(UNI)"

clean:
	find . -name __pycache__ -type d -prune -not -path "./.venv/*" -exec rm -rf {} +
	rm -rf .pytest_cache build dist src/*.egg-info

docker-build:
	$(COMPOSE) build api

# Neo4j: your own instance (NEO4J_URI_DOCKER in .env, default Neo4j Desktop on this machine).
docker-backend:
	$(COMPOSE) build api
	$(COMPOSE) run --rm seed
	$(COMPOSE) up -d --wait api
	@echo "backend ready: http://127.0.0.1:8780   docs: http://127.0.0.1:8780/docs   OpenAPI: /openapi.json"

docker-demo: docker-backend
	$(COMPOSE) up -d --wait web
	@echo "frontend: http://127.0.0.1:8770"

docker-up:
	$(COMPOSE) up --build -d --wait api web
	@echo "API: http://127.0.0.1:8780/docs   frontend: http://127.0.0.1:8770"

docker-seed:
	$(COMPOSE) run --rm seed

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f api
