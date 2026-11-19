from __future__ import annotations

import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from campusyamu.web.server import PageHandler


class WebPageServerTests(unittest.TestCase):
    """The web server only serves the page; all data comes from the API (/v1)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_serves_the_page_that_calls_the_api(self) -> None:
        with urllib.request.urlopen(self.base + "/") as res:
            html = res.read().decode("utf-8")
        self.assertIn("API_BASE_URL", html)
        for path in ("/v1/options", "/v1/recommendations", "/v1/chat", "/v1/career-outlook"):
            self.assertIn(path, html)
        self.assertNotIn('"/api/', html)

    def test_config_js_has_only_the_public_values(self) -> None:
        import json
        import os
        from unittest import mock

        env = {"SUPABASE_URL": "https://proj.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
               "SUPABASE_SECRET_KEY": "sb_secret_never", "SUPABASE_DB_URL": "postgresql://never",
               "OPENAI_API_KEY": "sk-never"}
        with mock.patch.dict(os.environ, env), urllib.request.urlopen(self.base + "/config.js") as res:
            body = res.read().decode("utf-8")
        self.assertTrue(body.startswith("window.CAMPUSYAMU_CONFIG = "))
        config = json.loads(body.split("=", 1)[1].strip().rstrip(";"))
        self.assertEqual(config, {"supabaseUrl": "https://proj.supabase.co", "supabaseKey": "sb_publishable_x",
                                  "apiBaseUrl": None})
        self.assertNotIn("never", body)

    def test_page_signs_in_and_sends_the_token(self) -> None:
        with urllib.request.urlopen(self.base + "/") as res:
            html = res.read().decode("utf-8")
        self.assertIn('<script src="/config.js"></script>', html)
        self.assertIn("signInWithPassword", html)
        self.assertIn("Authorization = `Bearer ${data.session.access_token}`", html)
        self.assertNotIn("X-API-Key", html)

    def test_old_api_routes_are_gone(self) -> None:
        for path in ("/api/options", "/api/career?course=Law"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(self.base + path)
            self.assertEqual(ctx.exception.code, 404)
        request = urllib.request.Request(self.base + "/api/run", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 501)       # no POST handler at all


if __name__ == "__main__":
    unittest.main()
