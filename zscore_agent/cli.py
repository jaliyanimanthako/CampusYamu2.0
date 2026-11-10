"""Command-line adapter for the deterministic Z-score agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .agent import ZScoreAgent
from .constants import DEFAULT_DATABASE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare a student's Z-score with historical course cutoffs."
    )
    parser.add_argument("--district", required=True, help="Applicant district")
    parser.add_argument("--course", required=True, help="Course of study")
    parser.add_argument("--z-score", required=True, type=float, help="Student Z-score")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    agent = ZScoreAgent(args.db)
    result = agent.analyze(
        district=args.district,
        course=args.course,
        z_score=args.z_score,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2) if args.as_json else agent.format_answer(result))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
