import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from echo_code.db import Database
from echo_code.model import DemoBackend
from echo_code.server import make_handler


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        db = Database(str(Path(cls.tmp.name) / "t.db"))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db, DemoBackend()))
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def call(self, method, path, body=None):
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())

    def test_flow(self):
        self.assertEqual(self.call("GET", "/api/health")["status"], "ok")
        cid = self.call("POST", "/api/chats", {})["id"]
        out = self.call("POST", f"/api/chats/{cid}/messages", {"content": "write rust hello"})
        self.assertIn("println", out["reply"])
        chat = self.call("GET", f"/api/chats/{cid}")
        self.assertEqual([m["role"] for m in chat["messages"]], ["user", "assistant"])
        self.call("DELETE", f"/api/chats/{cid}")
        self.assertEqual(self.call("GET", "/api/chats"), [])


if __name__ == "__main__":
    unittest.main()
