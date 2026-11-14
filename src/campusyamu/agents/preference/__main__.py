"""Read a student's interests with the engine set in config and time it.

    uv run python -m campusyamu.agents.preference "engineering, design"

Uses preferences.engine from config/settings.yaml (or PREFERENCE_ENGINE in .env):
openai or gemini_decision. To compare the two, run it, change the setting, run it
again with the same text. Both runs mark the same courses and print the SAME rows
in the SAME order (chosen from the reviewed category marks, which do not depend on
the engine), so the outputs line up row by row. `rank` is where this engine puts the
course among all the courses it marked.

`coverage` says how many interest x course marks the engine itself gave; the rest
were named courses (fixed at 10 / -1) or filled from the reviewed category marks.
Low coverage means the run mostly shows the reviewed marks, not the engine.
One paid call per run (OpenAI ~$0.002-0.005, Gemini Decision ~$0.005).
"""

from __future__ import annotations

import argparse
import time

from campusyamu.knowledge_graph.handbook_prose import _load_env

from .categories import load_course_tags
from .interpreter import KeywordInterpreter, Preference, PreferenceInterpreter, _norm, preference_engine


def _net(pref: Preference, code: str) -> int:
    return pref.marks.get(code, 0) + pref.mismatches.get(code, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", help='the student\'s interests, e.g. "engineering, design"')
    parser.add_argument("--courses", default="all",
                        help="course codes to mark, comma-separated, or 'all' (default: all 126, the realistic "
                             "size: a student is usually eligible for 50-100). Given codes are all shown, in order")
    parser.add_argument("--top", type=int, default=12, help="rows shown per interest with --courses all (default 12)")
    args = parser.parse_args(argv)

    _load_env(None)                                     # before reading the engine and keys
    tags = load_course_tags()
    explicit = args.courses != "all"
    courses = [c.strip() for c in args.courses.split(",") if c.strip() in tags] if explicit else sorted(tags)
    engine = preference_engine()
    interpreter = PreferenceInterpreter(tags, use_llm=True)
    if interpreter.llm is None:
        print(f"engine {engine}: not available ({interpreter.reason})")
        return 1

    started = time.perf_counter()
    result = interpreter.interpret(args.text, courses)
    seconds = time.perf_counter() - started

    pairs = len(result.preferences) * len(courses)
    named = sum(len(set(p.courses) & set(courses)) for p in result.preferences)
    own = pairs - named - result.baseline_marks if result.method == "llm" else 0
    print(f"engine   : {engine}  (model {result.model or '-'})")
    print(f"time     : {seconds:.1f} s")
    print(f"size     : {len(result.preferences)} interest(s) x {len(courses)} courses = {pairs} marks")
    print(f"coverage : {own} marked by the engine, {named} named courses (10/-1), "
          f"{pairs - own - named} from reviewed category marks")
    if result.method != "llm":
        print(f"WARNING  : the {engine} call failed, these are keyword-matching marks: {result.notes[-1]}")

    # the rows: engine-independent (reviewed marks for the same phrase), so both runs line up
    reference = {_norm(p.phrase): p for p in KeywordInterpreter(tags).interpret(args.text, courses).preferences}
    for pref in result.preferences:
        ranking = sorted(courses, key=lambda c: (-_net(pref, c), tags[c].name))
        position = {code: i + 1 for i, code in enumerate(ranking)}
        if explicit:
            rows = courses
        elif (ref := reference.get(_norm(pref.phrase))) is not None:
            rows = sorted(courses, key=lambda c: (-_net(ref, c), tags[c].name))[:args.top]
        else:                                   # the keyword matcher did not understand the phrase
            rows = ranking[:args.top]
        print(f"\n#{pref.rank} {pref.phrase!r} -> {', '.join(pref.categories)}"
              + (f"  (named: {', '.join(tags[c].name for c in pref.courses)})" if pref.courses else ""))
        print(f"   {'course':<52}{'mark':>5}{'mismatch':>9}{'net':>5}{'rank':>6}")
        for code in rows:
            print(f"   {tags[code].name[:51]:<52}{pref.marks.get(code, 0):>5}{pref.mismatches.get(code, 0):>9}"
                  f"{_net(pref, code):>5}{position[code]:>6}")
    for label, items in (("unmatched", result.unmatched), ("notes", result.notes)):
        if items:
            print(f"\n{label}: {items}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
