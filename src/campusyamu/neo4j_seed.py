"""Fill a Neo4j database with everything the app keeps there, from files already in data/.

    uv run python -m campusyamu.neo4j_seed            # make neo4j-seed (local) / make docker-seed (Docker)

Waits for Neo4j to accept connections, then loads, in order:
  1. the knowledge graph (data/processed/knowledge_graph/knowledge_graph.json)
  2. travel times, linked to the graph's campuses (data/processed/travel/travel_times.db)
  3. handbook passages and chunks with every complete embedding set in the cache, plus the
     vector and keyword indexes (handbook search in the course chat); passages link to step 1

No language-model calls. Each step replaces its own nodes, so re-running is safe.
Connection: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE (.env or the environment).
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Sequence

from .handbook_search import __main__ as handbook_search
from .handbook_search.store import connect
from .knowledge_graph import neo4j_export
from .knowledge_graph.handbook_prose import _load_env
from .agents.travel_time import neo4j_load


def wait_for_neo4j(timeout: float) -> None:
    """Retry until Neo4j answers (it may still be starting); a wrong password stops at once."""

    from neo4j.exceptions import AuthError

    uri = os.environ.get("NEO4J_URI", "")
    deadline = time.monotonic() + timeout
    while True:
        try:
            with connect() as driver:
                driver.verify_connectivity()
            return
        except AuthError as exc:
            raise SystemExit(f"Neo4j at {uri} refused the login: check NEO4J_USER / NEO4J_PASSWORD "
                             f"in .env (the instance's password). {exc}") from exc
        except Exception as exc:                    # not started yet, wrong address...
            if time.monotonic() > deadline:
                raise SystemExit(f"Neo4j at {uri} did not answer within {timeout:.0f} s. Is the instance "
                                 f"started (Neo4j Desktop)? Is NEO4J_URI_DOCKER right in .env? ({exc})") from exc
            time.sleep(3)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--wait", type=float, default=60, help="seconds to wait for Neo4j (default 60)")
    args = parser.parse_args(argv)
    _load_env(args.env_file)

    print("waiting for Neo4j ...", flush=True)
    wait_for_neo4j(args.wait)
    print("1/3 knowledge graph", flush=True)
    neo4j_export.main(["--push"])
    print("2/3 travel times", flush=True)
    neo4j_load.main([])
    print("3/3 handbook search", flush=True)
    handbook_search.main(["load"])
    print("Neo4j is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
