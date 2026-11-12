"""Every file location the project uses, in one place.

The project root is found from this file (src/campusyamu/core/paths.py) and can
be overridden with CAMPUSYAMU_HOME (e.g. in Docker, where the code is installed
but data/ and config/ are mounted next to it).

    data/raw/         source material as received (handbook, travel matrix, Z-score DB)
    data/reference/   owner-curated decisions and mappings (edited by hand, reviewed)
    data/processed/   files the pipelines build (knowledge graph, chunks, travel DB)
    data/cache/       web-research caches (career paths, career outlooks)
    outputs/          reports and run outputs (gitignored)
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CAMPUSYAMU_HOME") or Path(__file__).resolve().parents[3])

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

RAW_DIR = DATA_DIR / "raw"
HANDBOOK_DIR = RAW_DIR / "handbook"
TRAVEL_RAW_DIR = RAW_DIR / "travel"
ZSCORE_DB = RAW_DIR / "zscores" / "z_scores.db"

REFERENCE_DIR = DATA_DIR / "reference"
PROCESSED_DIR = DATA_DIR / "processed"
KG_DIR = PROCESSED_DIR / "knowledge_graph"
TRAVEL_DIR = PROCESSED_DIR / "travel"
CACHE_DIR = DATA_DIR / "cache"

HANDBOOK_PDF = HANDBOOK_DIR / "student_handbook_english.pdf"
HANDBOOK_MD = HANDBOOK_DIR / "student_handbook_english_structured.md"
KNOWLEDGE_GRAPH = KG_DIR / "knowledge_graph.json"
HANDBOOK_CHUNKS = KG_DIR / "handbook_chunks.json"
TRAVEL_DB = TRAVEL_DIR / "travel_times.db"
OWNER_INTERPRETATIONS = REFERENCE_DIR / "owner_interpretations.json"
COURSE_CATEGORIES = REFERENCE_DIR / "course_categories.json"
TRAVEL_DECISIONS = REFERENCE_DIR / "travel_decisions.json"


def relative(path: Path) -> str:
    """Project-relative POSIX path, as stored in provenance records."""

    return Path(path).resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
