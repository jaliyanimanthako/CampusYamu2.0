"""Course chat memory, per student: conversations, running summaries and student facts.

    from campusyamu.memory import ChatMemory
    memory = ChatMemory()                       # SQLite file, or Supabase Postgres when SUPABASE_DB_URL is set
    recall = memory.recall(user_id, "008G")     # facts + summary + newest turns, within the token budget
    memory.save_turn(user_id, course, question, answer, sources)

CLI: uv run python -m campusyamu.memory --help
"""

from .chat_memory import ChatMemory, Recall, tokens
from .store import MemoryStore, PostgresMemoryStore, open_store

__all__ = ["ChatMemory", "MemoryStore", "PostgresMemoryStore", "Recall", "open_store", "tokens"]
