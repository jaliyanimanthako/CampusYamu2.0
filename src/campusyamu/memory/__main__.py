"""Try and inspect the course chat memory from the terminal.

    uv run python -m campusyamu.memory chat --user demo --uni-code 008G     # chat with memory (OpenAI, paid)
    uv run python -m campusyamu.memory show --user demo [--uni-code 008G]   # facts, chats, summary, messages
    uv run python -m campusyamu.memory forget --user demo [--uni-code 008G] # delete one chat, or everything

Uses the same store as the API: Supabase Postgres when SUPABASE_DB_URL is set (the user must then be a real
Supabase user id), otherwise the SQLite file in memory.db. `chat` runs the memory updates straight after each
answer (not in the background) so you can watch the summary and the facts change.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .chat_memory import ChatMemory
from .store import MemoryStore, open_store


def offering_row(uni_code: str) -> dict[str, Any]:
    """A minimal course row for one offering, from the knowledge graph (the API gets the full row)."""

    from campusyamu.agents.course_finder.finder import CourseFinder

    finder = CourseFinder()
    try:
        for node, attrs in finder.graph.nodes(data=True):
            if attrs.get("type") == "Offering" and attrs.get("uni_code") == uni_code:
                lookup = attrs.get("zscore_lookup") or {}
                return {"uni_code": uni_code, "course_code": str(node).split(":")[1],
                        "course_name": lookup.get("course", ""), "university": lookup.get("institution", "")}
    finally:
        if hasattr(finder, "close"):
            finder.close()
    raise SystemExit(f"No offering with UNI code {uni_code}")


def show(store: MemoryStore, user: str, uni_code: str | None) -> None:
    facts = store.facts(user)
    print(f"Student facts ({len(facts)}):")
    for fact in facts:
        print(f"  [{fact['category']}] {fact['fact']}   (from {fact['source_uni_code'] or '-'})")
    chats = store.conversations(user)
    print(f"\nCourse chats ({len(chats)}):")
    for c in chats:
        print(f"  {c['uni_code']}  {c['course_name']} — {c['university']}: {c['messages']} messages, "
              f"summary up to #{c['summarized_through']}, facts read up to #{c['facts_through']}")
    if uni_code:
        conversation = store.conversation(user, uni_code)
        if conversation is None:
            print(f"\nNo chat for {uni_code}.")
            return
        print(f"\nSummary of {uni_code}:\n  {conversation['summary'] or '(none yet)'}\n\nMessages:")
        for m in store.messages(conversation["id"]):
            mark = " " if m["seq"] > conversation["summarized_through"] else "s"    # s = in the summary
            print(f" {mark}#{m['seq']:<3} {m['role']:<9} {m['content'][:160]}")


def chat(user: str, uni_code: str) -> None:
    from campusyamu.web.career_outlook import CareerOutlookStore
    from campusyamu.web.course_chat import CourseChat
    from campusyamu.web.university_pages import UniversityPages

    course = offering_row(uni_code)
    memory = ChatMemory(background=False)
    bot = CourseChat(outlooks=CareerOutlookStore(), websites=UniversityPages(), memory=memory)
    print(f"Chatting about {course['course_name']} ({uni_code}) at {course['university']} as '{user}'. "
          "Empty line to stop.\n")
    try:
        while True:
            try:
                question = input("you> ").strip()
            except EOFError:
                break
            if not question:
                break
            before = {f["fact"] for f in memory.store.facts(user)}
            result = bot.ask(question, course, user_id=user)
            print(f"\nbot> {result['answer']}")
            if result["search_question"] != question:
                print(f"     (handbook search: {result['search_question']})")
            for note in result["notes"]:
                print(f"     note: {note}")
            conversation = memory.store.conversation(user, uni_code) or {}
            facts = memory.store.facts(user)
            new = [f["fact"] for f in facts if f["fact"] not in before]
            print(f"     memory: summary up to #{conversation.get('summarized_through', 0)}, {len(facts)} fact(s)"
                  + (f"; new: {'; '.join(new)}" if new else "") + "\n")
    finally:
        bot.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m campusyamu.memory", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("chat", "chat about one course with memory (OpenAI, paid)"),
                       ("show", "print what is remembered"), ("forget", "delete one chat, or everything")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--user", required=True, help="student id (a Supabase user id when SUPABASE_DB_URL is set)")
        p.add_argument("--uni-code", required=(name == "chat"), help="course offering, e.g. 008G")
    args = parser.parse_args(argv)
    from campusyamu.knowledge_graph.handbook_prose import _load_env

    _load_env(None)                                     # .env: OPENAI_API_KEY, SUPABASE_DB_URL

    if args.command == "chat":
        chat(args.user, args.uni_code)
        return 0
    store = open_store()
    try:
        if args.command == "show":
            show(store, args.user, args.uni_code)
        elif args.uni_code:
            print("deleted" if store.delete_conversation(args.user, args.uni_code) else "no such chat")
        else:
            store.delete_user(args.user)
            print(f"deleted every chat and fact of {args.user}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
