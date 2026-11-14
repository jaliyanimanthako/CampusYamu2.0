from __future__ import annotations

import os
import threading
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from campusyamu.api import create_app

FORM = {"stream": "Physical Science",
        "al": [{"subject": "Combined Mathematics", "grade": "A"}, {"subject": "Physics", "grade": "B"},
               {"subject": "Chemistry", "grade": "C"}],
        "cgt": 40, "z_score": 1.56, "admission_district": "Kandy", "ds_division": "Gangawata Korale",
        "ol": [{"subject": "Science", "grade": "B"}, {"subject": "English", "grade": "B"},
               {"subject": "Mathematics", "grade": ""}],
        "preferences": "engineering, design", "use_llm": False, "suggestions": 8}


class RealServiceTests(unittest.TestCase):
    """The API over the real AdvisorService (offline: no OpenAI calls)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.env = mock.patch.dict(os.environ, {"CAMPUSYAMU_API_KEY": ""})
        cls.env.start()
        cls.client = TestClient(create_app())
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        cls.env.stop()

    def test_health_and_docs(self) -> None:
        r = self.client.get("/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        spec = self.client.get("/openapi.json").json()
        for path in ("/v1/options", "/v1/recommendations", "/v1/chat", "/v1/career-outlook",
                     "/v1/career-outlook/research", "/v1/courses"):
            self.assertIn(path, spec["paths"])

    def test_options(self) -> None:
        o = self.client.get("/v1/options").json()
        self.assertEqual(len(o["districts"]), 25)
        self.assertIn("Gangawata Korale", o["ds_divisions"]["Kandy"])
        self.assertIn("Physical Science", o["streams"])

    def test_courses(self) -> None:
        names = self.client.get("/v1/courses").json()
        self.assertIn("Quantity Surveying", names)
        self.assertEqual(names, sorted(names))

    def test_recommendations(self) -> None:
        r = self.client.post("/v1/recommendations", json=FORM)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertFalse(data["used_llm"])
        self.assertTrue(any(data["report"]["bands"].values()))

    def test_service_errors_keep_their_status(self) -> None:
        form = {**FORM, "al": FORM["al"][:2]}
        r = self.client.post("/v1/recommendations", json=form)
        self.assertEqual(r.status_code, 400)
        self.assertIn("three A/L subjects", r.json()["errors"][0])

    def test_validation_errors_use_the_same_shape(self) -> None:
        r = self.client.post("/v1/recommendations", json={**FORM, "stream": ""})
        self.assertEqual(r.status_code, 422)
        self.assertTrue(r.json()["errors"][0].startswith("stream:"))
        r = self.client.post("/v1/recommendations", json={**FORM, "suggestions": 500})
        self.assertEqual(r.status_code, 422)

    def test_unknown_course_for_research(self) -> None:
        r = self.client.post("/v1/career-outlook/research", json={"course": "Not A Course"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {"errors": ["Unknown course"]})

    def test_not_found_shape(self) -> None:
        r = self.client.get("/v1/nope")
        self.assertEqual(r.status_code, 404)
        self.assertIn("errors", r.json())


class FakeWeb:
    def __init__(self) -> None:
        self.options = {"streams": [], "stream_hints": {}, "al_subjects": [], "al_grades": [], "ol_subjects": [],
                        "ol_grades": [], "districts": [], "ds_divisions": {}, "llm_available": True}
        self.course_names = {"Law"}
        self.threads: set[int] = set()
        self.closed = False
        self.finder = self

    def close(self) -> None:
        self.closed = True

    def career(self, course):
        self.threads.add(threading.get_ident())
        return {"course": course, "available": True, "missing_keys": [], "outlook": None,
                "job": {"course": course, "state": "running", "started": 1.0, "message": "starting…"}}

    def start_career(self, body):
        self.threads.add(threading.get_ident())
        return 202, {"message": "started", **self.career(body["course"])}

    def ask(self, body):
        self.threads.add(threading.get_ident())
        self.last_ask = body
        return 200, {"answer": "Yes.", "status": "answered", "notes": [], "model": "m", "career_research": False,
                     "sources": [{"id": "h1", "kind": "handbook", "title": "p. 12"}], "career": self.career("Law")}

    def run(self, form):
        return 200, {"report": {}, "used_llm": False}


class FakeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.web = FakeWeb()
        self.app = create_app(lambda: self.web)

    def test_chat_passes_the_whole_course_row(self) -> None:
        body = {"question": "Is there a hostel?", "course": {"course_code": "001A", "course_name": "Law",
                                                             "university": "Colombo"},
                "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
        with mock.patch.dict(os.environ, {"CAMPUSYAMU_API_KEY": ""}), TestClient(self.app) as client:
            r = client.post("/v1/chat", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["career"]["job"]["state"], "running")
        self.assertEqual(self.web.last_ask["course"]["university"], "Colombo")
        self.assertEqual(self.web.last_ask["student"], {})

    def test_research_is_202_and_every_call_uses_one_thread(self) -> None:
        with mock.patch.dict(os.environ, {"CAMPUSYAMU_API_KEY": ""}), TestClient(self.app) as client:
            self.assertEqual(client.post("/v1/career-outlook/research", json={"course": "Law"}).status_code, 202)
            self.assertEqual(client.get("/v1/career-outlook", params={"course": "Law"}).status_code, 200)
            client.post("/v1/chat", json={"question": "q", "course": {"course_code": "1"}})
        self.assertEqual(len(self.web.threads), 1)
        self.assertNotIn(threading.get_ident(), self.web.threads)
        self.assertTrue(self.web.closed)

    def test_api_key(self) -> None:
        with mock.patch.dict(os.environ, {"CAMPUSYAMU_API_KEY": "secret"}), TestClient(self.app) as client:
            self.assertEqual(client.get("/v1/health").status_code, 200)
            r = client.get("/v1/options")
            self.assertEqual(r.status_code, 401)
            self.assertEqual(r.json(), {"errors": ["Missing or invalid X-API-Key"]})
            self.assertEqual(client.get("/v1/options", headers={"X-API-Key": "wrong"}).status_code, 401)
            self.assertEqual(client.get("/v1/options", headers={"X-API-Key": "secret"}).status_code, 200)

    def test_cors_preflight(self) -> None:
        with mock.patch.dict(os.environ, {"API_CORS_ORIGINS": "https://app.example"}):
            app = create_app(lambda: self.web)
        with TestClient(app) as client:
            r = client.options("/v1/chat", headers={"Origin": "https://app.example",
                                                    "Access-Control-Request-Method": "POST"})
        self.assertEqual(r.headers.get("access-control-allow-origin"), "https://app.example")


if __name__ == "__main__":
    unittest.main()
