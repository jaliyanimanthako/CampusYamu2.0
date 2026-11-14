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
