"""Every LLM prompt in CampusYamu, in one place.

Edit wording here; the code that calls the models imports from these modules.
After an edit, restart the API (`make api`).

    uv run python -m campusyamu.prompts                 # list every prompt
    uv run python -m campusyamu.prompts course_chat     # print one in full, exactly as sent

Module            Prompt                    Used by
preference.py     INTERESTS_SYSTEM          reading interests, engine openai (gpt-4o-mini)
                  DECISION_GUIDE, *_LEVELS, reading interests, engine gemini_decision (gemini-decision-1)
                  *_question()
feedback.py       FEEDBACK_SYSTEM           advice on the ranked list
course_chat.py    COURSE_CHAT_SYSTEM        course chat (POST /v1/chat)
guardrail.py      SCOPE_GUIDE, SCOPE_CHOICES course chat scope check, Gemini Decision (in / out of scope / manipulation)
memory.py         STANDALONE_QUESTION       course chat memory: a follow-up -> a standalone handbook search
                  CONVERSATION_SUMMARY      course chat memory: older turns -> the chat's running summary
                  STUDENT_FACTS             course chat memory: the student's lasting facts (all course chats)
university.py     WEBSITE_PROFILE_SYSTEM    official university pages -> the applicant profile of a course
                  SPECIALISATION_SYSTEM     one search per specialisation -> a short card each
career.py         CAREER_EXTRACTION         career research: job titles from web pages
                  RESEARCH_AGENT            career research: the research agent
                  CONTEXT_SUMMARY           career research: agent notes when its context fills
                  FUTURE_ANALYSIS           career research: cited future SWOT
                  FUTURE_REVISION           career research: fix a SWOT that failed the checks
handbook.py       rule_extraction_prompt()  offline handbook rule extraction (paid runs, not the API)
kg_chat.py        KG_CHAT_SYSTEM            graph-viewer chatbot (`make kg-chat`, not the API)

Prompts are plain Python strings (or small functions where values are filled in),
so a test or a debugger can import and print them.
"""

from __future__ import annotations

from typing import Callable


def _decision_example() -> str:
    """The Gemini Decision request for a sample student, as sent (shared input + the questions)."""

    import json

    from campusyamu.agents.preference import GeminiDecisionInterpreter, load_course_tags

    payload = GeminiDecisionInterpreter(load_course_tags(), api_key="-").request_payloads(
        "engineering, design", ["008", "024"])[0]
    return (f"--- input (shared by every question) ---\n{payload['input']}\n\n"
            f"--- questions (sample: \"engineering, design\" x Engineering, Design) ---\n"
            + json.dumps(payload["questions"], indent=1, ensure_ascii=False))


def _guardrail_example() -> str:
    """The scope-check request for a sample follow-up, as sent to Gemini Decision."""

    import json

    from campusyamu.web.guardrail import ScopeGuard

    payload = ScopeGuard(api_key="-").payload(
        "and is there an aptitude test?",
        {"course_name": "Architecture", "uni_code": "023G", "university": "University of Moratuwa"},
        [{"role": "user", "content": "Tell me about Architecture"}, {"role": "assistant", "content": "It is a ..."}])
    return (f"--- input ---\n{payload['input']}\n\n--- question ---\n"
            + json.dumps(payload["questions"], indent=1, ensure_ascii=False))


def _handbook() -> str:
    from campusyamu.knowledge_graph.handbook_prose import DEVELOPER_PROMPT

    return DEVELOPER_PROMPT


def _attr(module: str, name: str) -> Callable[[], str]:
    def get() -> str:
        import importlib

        return getattr(importlib.import_module(f"campusyamu.prompts.{module}"), name)
    return get


# name -> (used by, how to render the full text)
PROMPTS: dict[str, tuple[str, Callable[[], str]]] = {
    "interests_openai": ("reading interests, engine openai", _attr("preference", "INTERESTS_SYSTEM")),
    "interests_gemini": ("reading interests, engine gemini_decision (sample request)", _decision_example),
    "feedback": ("advice on the ranked list", _attr("feedback", "FEEDBACK_SYSTEM")),
    "course_chat": ("course chat, POST /v1/chat", _attr("course_chat", "COURSE_CHAT_SYSTEM")),
    "guardrail_scope": ("course chat scope check, Gemini Decision (sample request)", _guardrail_example),
    "memory_standalone_question": ("chat memory: a follow-up -> a standalone handbook search",
                                   _attr("memory", "STANDALONE_QUESTION")),
    "memory_summary": ("chat memory: older turns -> running summary", _attr("memory", "CONVERSATION_SUMMARY")),
    "memory_student_facts": ("chat memory: the student's lasting facts", _attr("memory", "STUDENT_FACTS")),
    "website_profile": ("university website -> applicant profile of a course",
                        _attr("university", "WEBSITE_PROFILE_SYSTEM")),
    "website_specialisations": ("university website -> a card per specialisation",
                                _attr("university", "SPECIALISATION_SYSTEM")),
    "career_extraction": ("career research: job titles from web pages", _attr("career", "CAREER_EXTRACTION")),
    "research_agent": ("career research: the research agent", _attr("career", "RESEARCH_AGENT")),
    "context_summary": ("career research: agent notes when its context fills", _attr("career", "CONTEXT_SUMMARY")),
    "future_analysis": ("career research: cited future SWOT", _attr("career", "FUTURE_ANALYSIS")),
    "future_revision": ("career research: fix a SWOT that failed the checks", _attr("career", "FUTURE_REVISION")),
    "handbook_extraction": ("offline handbook rule extraction (filled in)", _handbook),
    "kg_chat": ("graph-viewer chatbot, make kg-chat", _attr("kg_chat", "KG_CHAT_SYSTEM")),
}


def get(name: str) -> str:
    """The full text of one prompt, as the model receives it."""

    return PROMPTS[name][1]()
