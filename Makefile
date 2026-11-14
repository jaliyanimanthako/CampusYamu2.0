# CampusYamu — common tasks.  `make help` lists them.
# Targets marked (paid) call OpenAI or web-search APIs with the keys in .env.

UV ?= uv
RUN = $(UV) run
KG = campusyamu.knowledge_graph
PORT ?= 8770
API_PORT ?= 8780
COMPOSE ?= docker compose

.DEFAULT_GOAL := help
.PHONY: help install install-rerank test web api student kg kg-refresh kg-viewer kg-chat neo4j-push \
        search-chunk search-embed search-load travel-db career research clean docker-build docker-up docker-down docker-logs

help:
	@echo "Setup"
	@echo "  make install          install the package and dependencies (uv sync)"
	@echo "  make install-rerank   also install the local cross-encoder reranker (large)"
	@echo "Run"
	@echo "  make api              the API on http://127.0.0.1:$(API_PORT)/docs (used by the web page and the mobile app)"
	@echo "  make web              web page on http://127.0.0.1:$(PORT) (run make api too)"
	@echo "  make student          student pipeline in the terminal (asks the questions)"
	@echo "  make test             run the test suite"
	@echo "Knowledge graph (handbook -> rules -> graph)"
	@echo "  make kg               validate sources and rebuild the graph (no API calls)"
	@echo "  make kg-refresh       re-check owner interpretations against the rules (no API calls)"
	@echo "  make kg-viewer        rebuild the HTML graph viewer"
	@echo "  make kg-chat          graph chatbot server (paid per question)"
	@echo "  make neo4j-push       load the graph + travel data into Neo4j (needs NEO4J_* in .env)"
	@echo "Handbook search (Neo4j vector + BM25)"
	@echo "  make search-chunk     parent/child chunks from the handbook"
	@echo "  make search-embed     embed the chunks (paid, cents; cached)"
	@echo "  make search-load      load chunks + embeddings into Neo4j"
	@echo "Data"
	@echo "  make travel-db        rebuild data/processed/travel/travel_times.db from the CSVs"
	@echo "  make career COURSE=\"Quantity Surveying\"   web career research for one course (paid)"
	@echo "  make research COURSE=Engineering UNI=Moratuwa   career + university website + specialisations, in parallel (paid)"
	@echo "Docker"
	@echo "  make docker-up        build and start the web app (+ Neo4j) with docker compose"
	@echo "  make docker-down / docker-logs"
	@echo "  make clean            remove caches and build files"

install:
	$(UV) sync

install-rerank:
	$(UV) sync --extra rerank

test:
	$(RUN) python -m unittest discover -s tests

web:
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

neo4j-push:
	$(RUN) python -m $(KG).neo4j_export --push
	$(RUN) python -m campusyamu.agents.travel_time.neo4j_load

search-chunk:
	$(RUN) python -m campusyamu.handbook_search chunk

search-embed:
	$(RUN) python -m campusyamu.handbook_search embed

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
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d
	@echo "web app: http://127.0.0.1:$(PORT)   (Neo4j browser: http://127.0.0.1:7474)"

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f web
