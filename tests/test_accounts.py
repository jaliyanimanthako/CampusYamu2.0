"""Signed-in students: daily limits on the paid calls and their saved chats (GET/DELETE /v1/me...)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from campusyamu.api.limits import DailyLimits
from campusyamu.api.service import AdvisorService, course_from_report, student_from_report
from campusyamu.memory import ChatMemory, MemoryStore
from campusyamu.web.career_outlook import CareerOutlookStore

COURSE = {"course_code": "023", "uni_code": "023G", "course_name": "Architecture", "university": "University of Moratuwa"}
FORM = {"stream": "Physical Science",
        "al": [{"subject": "Combined Mathematics", "grade": "A"}, {"subject": "Physics", "grade": "B"},
               {"subject": "Chemistry", "grade": "C"}],
        "cgt": 40, "z_score": 1.56, "admission_district": "Kandy", "ds_division": "Gangawata Korale",
        "preferences": "design", "use_llm": True}


REPORT = {
    "profile": {"stream": "Physical Science", "al_results": [["Physics", "A"]], "z_score": 1.5,
                "admission_district": "Kandy"},
    "origin": {"district": "Kandy", "ds_division": "Gangawata Korale"},
    "preferences": {"text": "design"},
    "bands": {"strong": [COURSE], "reach": [{"uni_code": "008G", "course_code": "008", "course_name": "Engineering"}]},
    "rankings": {"distance": {"suggestions": [{"uni_code": "023G", "position": 2, "parts": {"travel": 0.9}}],
                              "feedback": {"course_notes": {"023G": {"note": "close to home"}}}}},
}


class ReportLookupTests(unittest.TestCase):
    def test_course_and_student_from_a_saved_report(self) -> None:
        course = course_from_report(REPORT, "023G")
        self.assertEqual((course["course_name"], course["order3_position"], course["parts"], course["order3_note"]),
                         ("Architecture", 2, {"travel": 0.9}, "close to home"))
        self.assertIsNone(course_from_report(REPORT, "008G")["order3_position"])
        self.assertIsNone(course_from_report(REPORT, "999X"))
        self.assertEqual(student_from_report(REPORT)["home"], "Gangawata Korale (Kandy)")
        self.assertEqual(student_from_report(REPORT)["interests"], "design")


class DailyLimitsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = MemoryStore(Path(tmp.name) / "m.db")
        self.limits = DailyLimits(lambda: self.store, {"chat": 2, "ai_recommendations": 0, "research": 1})

    def test_check_and_record(self) -> None:
        self.assertIsNone(self.limits.check("u", "chat"))
        self.assertEqual(self.limits.record("u", "chat"), {"used": 1, "limit": 2})
        self.assertEqual(self.limits.record("u", "chat"), {"used": 2, "limit": 2})
        self.assertEqual(self.limits.check("u", "chat"), "Daily limit reached: 2 chat questions a day. Try again tomorrow.")
        self.assertIsNone(self.limits.check("someone-else", "chat"))
        self.assertEqual(self.limits.status("u"), {"chat": {"used": 2, "limit": 2},
                                                   "ai_recommendations": {"used": 0, "limit": 0},
                                                   "research": {"used": 0, "limit": 1}})

    def test_zero_or_no_user_is_unlimited_and_days_reset(self) -> None:
        for _ in range(5):
            self.limits.record("u", "ai_recommendations")
        self.assertIsNone(self.limits.check("u", "ai_recommendations"))       # 0 = no limit
        self.assertIsNone(self.limits.check(None, "chat"))                    # sign-in off
        self.assertIsNone(self.limits.record(None, "chat"))
        self.limits.record("u", "research")
        self.assertIsNotNone(self.limits.check("u", "research"))
        self.limits.today = lambda: "2099-01-01"                              # the next day
        self.assertIsNone(self.limits.check("u", "research"))

    def test_settings_defaults(self) -> None:
        self.assertEqual(set(DailyLimits(lambda: self.store).limits), {"chat", "ai_recommendations", "research"})


class FakeChat:
    def __init__(self) -> None:
        self.fail, self.research = False, False
        self.asked: list[tuple] = []

    def ask(self, question, course, student, history, user_id=None):
        self.asked.append((course, student))
        if self.fail:
            raise RuntimeError("OpenAI down")
        return {"answer": "ok", "status": "answered", "sources": [], "notes": [], "model": "m",
                "career_research": False, "start_career_research": self.research}


class FakeJobs:
    def __init__(self) -> None:
        self.started: list[str] = []

    def start(self, course, offering=None):
        self.started.append(course)
        return True, "started"

    def status(self, course):
        return None


class ServiceAccountTests(unittest.TestCase):
    """AdvisorService's account parts, without the heavy course finder."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = MemoryStore(Path(tmp.name) / "m.db")
        svc = object.__new__(AdvisorService)
        svc.options = {"llm_available": True, "preference_ai_available": False}
        svc.course_names = {"Architecture"}
        svc.outlooks = CareerOutlookStore(Path(tmp.name))
        svc.career_jobs = FakeJobs()
        svc.chat = FakeChat()
        svc.memory = ChatMemory(self.store, model="m", caller=lambda p: {}, background=False)
        svc.limits = DailyLimits(lambda: self.store, {"chat": 2, "ai_recommendations": 1, "research": 1})
        self.svc = svc
        import campusyamu.api.service as service
        from unittest import mock

        patcher = mock.patch.object(service, "missing_keys", lambda: [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def ask(self, user="u"):
        return self.svc.ask({"question": "q", "course": COURSE}, user)

    def test_chat_limit_counts_only_answers(self) -> None:
        self.svc.chat.fail = True
        self.assertEqual(self.ask()[0], 502)                                   # failed: not counted
        self.svc.chat.fail = False
        status, data = self.ask()
        self.assertEqual((status, data["usage"]), (200, {"used": 1, "limit": 2}))
        self.assertEqual(self.ask()[1]["usage"], {"used": 2, "limit": 2})
        status, data = self.ask()
        self.assertEqual(status, 429)
        self.assertIn("Daily limit reached", data["errors"][0])
        self.assertEqual(self.ask(user=None)[1]["usage"], None)                # sign-in off: no limit

    def test_research_limit_from_the_chat_and_the_endpoint(self) -> None:
        self.svc.chat.research = True
        self.assertEqual(self.ask()[1]["notes"], [])
        self.assertEqual(self.svc.career_jobs.started, ["Architecture"])
        notes = self.ask()[1]["notes"]                                          # second research today
        self.assertIn("Daily limit reached: 1 web research runs a day", notes[0])
        self.assertEqual(self.svc.career_jobs.started, ["Architecture"])
        status, data = self.svc.start_career({"course": "Architecture"}, "u")
        self.assertEqual(status, 429)
        self.assertEqual(self.svc.start_career({"course": "Architecture"}, "v")[0], 202)

    def test_ai_search_limit(self) -> None:
        self.svc.limits.record("u", "ai_recommendations")
        status, data = self.svc.run(FORM, "u")
        self.assertEqual(status, 429)
        self.assertIn('Untick "Use AI"', data["errors"][0])

    def test_each_search_is_saved_and_the_chat_can_use_uni_code(self) -> None:
        import campusyamu.api.service as service
        from unittest import mock

        self.svc.pipeline = lambda use_llm, suggestions: None
        with mock.patch.object(service, "run_pipeline", lambda inputs, graph: {"report": REPORT}):
            self.assertEqual(self.svc.results("u")[0], 404)
            self.assertEqual(self.svc.run({**FORM, "use_llm": False}, "u")[0], 200)
            self.svc.run({**FORM, "use_llm": False}, None)                     # sign-in off: nothing saved
        status, saved = self.svc.results("u")
        self.assertEqual((status, saved["form"]["stream"], saved["report"]["origin"]["district"], saved["used_llm"]),
                         (200, "Physical Science", "Kandy", False))
        self.assertEqual(self.svc.results("someone-else")[0], 404)

        self.assertEqual(self.svc.ask({"question": "q", "uni_code": "023G"}, "u")[0], 200)
        course, student = self.svc.chat.asked[-1]
        self.assertEqual((course["course_code"], course["order3_note"], student["z_score"]),
                         ("023", "close to home", 1.5))
        status, data = self.svc.ask({"question": "q", "uni_code": "999X"}, "u")
        self.assertEqual(status, 400)
        self.assertIn("not in your saved results", data["errors"][0])
        self.assertEqual(self.svc.ask({"question": "q", "uni_code": "023G"}, None)[0], 400)   # needs sign-in
        self.assertEqual(self.svc.ask({"question": "q", "uni_code": "023G"}, "someone-else")[0], 400)

    def test_saved_chats_and_paging(self) -> None:
        self.assertEqual(self.svc.chat_history("u", "023G")[0], 404)
        for i in range(1, 4):
            self.svc.memory.save_turn("u", COURSE, f"q{i}", f"a{i}", [{"id": "S1"}])
        [chat] = self.svc.chats("u")
        self.assertEqual((chat["uni_code"], chat["messages"], chat["course_name"]), ("023G", 6, "Architecture"))
        status, page = self.svc.chat_history("u", "023G", limit=4)
        self.assertEqual(status, 200)
        self.assertEqual([m["content"] for m in page["messages"]], ["q2", "a2", "q3", "a3"])
        self.assertTrue(page["has_more"])
        self.assertEqual(page["messages"][1]["sources"], [{"id": "S1"}])
        older = self.svc.chat_history("u", "023G", before=page["messages"][0]["seq"], limit=4)[1]
        self.assertEqual(([m["content"] for m in older["messages"]], older["has_more"]), (["q1", "a1"], False))
        self.assertEqual(self.svc.chat_history("someone-else", "023G")[0], 404)  # only your own chats
        self.assertEqual(self.svc.delete_chat("someone-else", "023G")[0], 404)
        self.assertEqual(self.svc.delete_chat("u", "023G"), (200, {"deleted": "023G"}))
        self.assertEqual(self.svc.chats("u"), [])
        self.assertEqual(self.svc.me("u")["usage"]["chat"], {"used": 0, "limit": 2})


if __name__ == "__main__":
    unittest.main()
