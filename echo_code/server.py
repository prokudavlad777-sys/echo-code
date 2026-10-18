import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .db import Database
from .model import SYSTEM_PROMPT, count_tokens, load_backend

WEB = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 1_000_000


def make_handler(db, backend):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EchoCode/" + __version__

        def log_message(self, fmt, *args):
            if os.environ.get("ECHO_VERBOSE"):
                super().log_message(fmt, *args)

        # helpers
        def send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("body too large")
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")

        def static(self, path):
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            f = (WEB / rel).resolve()
            if WEB.resolve() not in f.parents and f != WEB.resolve() or not f.is_file():
                return self.send_json({"error": "not found"}, 404)
            body = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", (mimetypes.guess_type(f.name)[0] or "text/plain") + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # routes
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/health":
                return self.send_json({"status": "ok", "version": __version__, "model": backend.name})
            if path == "/api/chats":
                return self.send_json(db.list_chats())
            m = re.fullmatch(r"/api/chats/(\d+)", path)
            if m:
                chat = db.get_chat(int(m.group(1)))
                if not chat:
                    return self.send_json({"error": "chat not found"}, 404)
                chat["messages"] = db.messages(chat["id"])
                return self.send_json(chat)
            if path.startswith("/api/"):
                return self.send_json({"error": "not found"}, 404)
            self.static(path)

        def do_POST(self):
            path = self.path.split("?")[0]
            try:
                data = self.read_json()
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 400)
            if path == "/api/chats":
                title = str(data.get("title") or "New chat")[:80]
                return self.send_json({"id": db.create_chat(title), "title": title}, 201)
            m = re.fullmatch(r"/api/chats/(\d+)/messages", path)
            if m:
                chat_id = int(m.group(1))
                text = str(data.get("content") or "").strip()
                if not db.get_chat(chat_id):
                    return self.send_json({"error": "chat not found"}, 404)
                if not text:
                    return self.send_json({"error": "empty message"}, 400)
                history = db.messages(chat_id)
                if not history:
                    db.rename_chat(chat_id, text[:40])
                db.add_message(chat_id, "user", text, count_tokens(text))
                prompt = [{"role": "system", "content": SYSTEM_PROMPT}]
                prompt += [{"role": h["role"], "content": h["content"]} for h in history[-20:]]
                prompt.append({"role": "user", "content": text})
                reply = backend.generate(prompt)
                tokens = count_tokens(reply)
                db.add_message(chat_id, "assistant", reply, tokens)
                return self.send_json({"reply": reply, "tokens": tokens})
            self.send_json({"error": "not found"}, 404)

        def do_DELETE(self):
            m = re.fullmatch(r"/api/chats/(\d+)", self.path.split("?")[0])
            if not m:
                return self.send_json({"error": "not found"}, 404)
            db.delete_chat(int(m.group(1)))
            self.send_json({"deleted": True})

    return Handler


def main():
    host = os.environ.get("ECHO_HOST", "127.0.0.1")
    port = int(os.environ.get("ECHO_PORT", "8000"))
    db = Database(os.environ.get("ECHO_DB", "data/echo_code.db"))
    backend = load_backend()
    httpd = ThreadingHTTPServer((host, port), make_handler(db, backend))
    print(f"Echo Code {__version__} | model: {backend.name} | http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
