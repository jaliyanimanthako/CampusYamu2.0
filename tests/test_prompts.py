from __future__ import annotations

import unittest

from campusyamu import prompts


class PromptRegistryTests(unittest.TestCase):
    def test_every_prompt_renders(self) -> None:
        for name in prompts.PROMPTS:
            text = prompts.get(name)
            self.assertIsInstance(text, str, name)
            self.assertGreater(len(text.strip()), 100, name)

    def test_the_code_uses_the_prompts_package(self) -> None:
        """One source of truth: the callers' constants are the same objects as in campusyamu.prompts."""
        from campusyamu.agents.career_trends import career_discovery, future_analytics, research_harness
        from campusyamu.agents.career_trends.harness import context
        from campusyamu.agents.preference import interpreter
        from campusyamu.agents.ranking import feedback
        from campusyamu.knowledge_graph import chat_server, handbook_prose
        from campusyamu.prompts import career, course_chat, handbook, kg_chat, preference
        from campusyamu.prompts import feedback as feedback_prompts
        from campusyamu.web import course_chat as chat

        pairs = [(interpreter.SYSTEM_PROMPT, preference.INTERESTS_SYSTEM),
                 (feedback.SYSTEM_PROMPT, feedback_prompts.FEEDBACK_SYSTEM),
                 (chat.SYSTEM_PROMPT, course_chat.COURSE_CHAT_SYSTEM),
                 (career_discovery.EXTRACTION_PROMPT, career.CAREER_EXTRACTION),
                 (research_harness.AGENT_PROMPT, career.RESEARCH_AGENT),
                 (context.SUMMARY_PROMPT, career.CONTEXT_SUMMARY),
                 (future_analytics.DEVELOPER_PROMPT, career.FUTURE_ANALYSIS),
                 (future_analytics.REVISION_PROMPT, career.FUTURE_REVISION),
                 (chat_server.SYSTEM_PROMPT, kg_chat.KG_CHAT_SYSTEM)]
        for used, defined in pairs:
            self.assertIs(used, defined)
        self.assertEqual(handbook_prose.DEVELOPER_PROMPT,
                         handbook.rule_extraction_prompt(handbook_prose.AL_SUBJECTS,
                                                         handbook_prose.EXPECTED_IGNORE_REASON))

    def test_gemini_questions_use_the_prompt_wording(self) -> None:
        from campusyamu.agents.preference import GeminiDecisionInterpreter, load_course_tags
        from campusyamu.prompts import preference

        [payload] = GeminiDecisionInterpreter(load_course_tags(), api_key="-").request_payloads("design", ["024"])
        self.assertTrue(payload["input"].startswith(preference.DECISION_GUIDE))
        self.assertEqual(payload["questions"]["p0_category"]["instructions"],
                         preference.category_question('"design"'))
        self.assertIs(payload["questions"]["p0_m_024"]["criteria"], preference.MARK_LEVELS)


if __name__ == "__main__":
    unittest.main()
