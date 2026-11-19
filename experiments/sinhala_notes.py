"""Experiment: the ranking's per-course notes in Sinhala, with one extra LLM call.

Standalone: it reads a downloaded report and prints English and Sinhala side by side. It does not
change the app, the chat memory or the database.

    1. In the web page, run a search and press the download button (student_report.json).
    2. uv run python experiments/sinhala_notes.py ~/Downloads/student_report.json
       [--limit 10] [--model gpt-4o-mini] [--save notes_si.json]

Course names, university names and place names stay in English; numbers stay as they are.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from campusyamu.core.openai_client import call_structured

SYSTEM = """You translate short notes for Sri Lankan A/L students from English into Sinhala.
- Write natural, simple Sinhala in Sinhala script, the way a friendly school counsellor would speak.
- Keep these EXACTLY as given, in English: course names, university names, campus and place names
  (they are listed with each note). Keep numbers, ranks (#1), and the terms "Z-score" and "cut-off" in English.
- Translate the meaning, not word by word. Do not add, drop or soften anything; no advice of your own.
- Return one translation per note, with the same uni_code."""


def notes_from(report: dict, limit: int) -> list[dict]:
    """The distance ranking's notes, in list order, with the names to keep in English."""

    ranking = (report.get("rankings") or {}).get("distance") or {}
    notes = (ranking.get("feedback") or {}).get("course_notes") or {}
    rows = {r["uni_code"]: r for band in (report.get("bands") or {}).values() for r in band}
    out = []
    for item in ranking.get("suggestions") or []:
        code = item.get("uni_code")
        note = (notes.get(code) or {}).get("note")
        if note:
            row = rows.get(code, {})
            out.append({"uni_code": code, "course_name": item.get("course_name") or row.get("course_name"),
                        "university": item.get("university") or row.get("university"),
                        "site": row.get("site"), "note": note})
    return out[:limit]


def translate(items: list[dict], model: str) -> dict[str, str]:
    payload = {
        "model": model, "store": False, "max_output_tokens": 4000,
        "input": [{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": json.dumps(
                      [{"uni_code": i["uni_code"], "keep_in_english": [n for n in (i["course_name"], i["university"],
                                                                                    i["site"]) if n],
                        "note": i["note"]} for i in items], ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": "sinhala_notes", "strict": True, "schema": {
            "type": "object", "additionalProperties": False, "required": ["notes"],
            "properties": {"notes": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["uni_code", "sinhala"],
                "properties": {"uni_code": {"type": "string", "enum": [i["uni_code"] for i in items]},
                               "sinhala": {"type": "string"}}}}}}}},
    }
    raw = call_structured(payload, os.environ["OPENAI_API_KEY"], 120, "CampusYamu-SinhalaExperiment/0.1")
    return {n["uni_code"]: n["sinhala"].strip() for n in raw.get("notes", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Translate the ranking notes of a report into Sinhala.")
    parser.add_argument("report", type=Path, help="student_report.json from the web page")
    parser.add_argument("--limit", type=int, default=10, help="how many notes (default 10)")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--save", type=Path, help="also write the notes and translations as JSON")
    args = parser.parse_args(argv)

    from campusyamu.knowledge_graph.handbook_prose import _load_env

    _load_env(None)
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is not set (.env)")
    items = notes_from(json.loads(args.report.read_text(encoding="utf-8")), args.limit)
    if not items:
        parser.error("no ranking notes in this report (run a search with AI feedback, then download it)")

    start = time.perf_counter()
    sinhala = translate(items, args.model)
    print(f"{len(items)} notes, 1 call to {args.model}, {time.perf_counter() - start:.1f} s\n")
    for n, item in enumerate(items, 1):
        si = sinhala.get(item["uni_code"], "(missing)")
        kept = [name for name in (item["course_name"], item["university"]) if name and name not in si]
        print(f"{n}. {item['course_name']} {item['uni_code']} — {item['university']}")
        print(f"   EN: {item['note']}")
        print(f"   SI: {si}")
        if kept:
            print(f"   ! not kept in English: {', '.join(kept)}")
        print()
    if args.save:
        args.save.write_text(json.dumps([{**i, "sinhala": sinhala.get(i["uni_code"])} for i in items],
                                        ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"saved {args.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
