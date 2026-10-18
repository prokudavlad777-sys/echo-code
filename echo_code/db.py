import sqlite3
import threading
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


class Database:
    def __init__(self, path="data/echo_code.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    def _all(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _one(self, sql, args=()):
        rows = self._all(sql, args)
        return rows[0] if rows else None

    def _run(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def create_chat(self, title="New chat"):
        return self._run("INSERT INTO chats(title) VALUES (?)", (title,))

    def list_chats(self):
        return self._all("SELECT * FROM chat_stats ORDER BY chat_id DESC")

    def get_chat(self, chat_id):
        return self._one("SELECT * FROM chats WHERE id = ?", (chat_id,))

    def rename_chat(self, chat_id, title):
        self._run("UPDATE chats SET title = ?, updated_at = datetime('now') WHERE id = ?", (title, chat_id))

    def delete_chat(self, chat_id):
        self._run("DELETE FROM chats WHERE id = ?", (chat_id,))

    def add_message(self, chat_id, role, content, tokens=0):
        mid = self._run(
            "INSERT INTO messages(chat_id, role, content, tokens) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, tokens),
        )
        self._run("UPDATE chats SET updated_at = datetime('now') WHERE id = ?", (chat_id,))
        return mid

    def messages(self, chat_id):
        return self._all(
            "SELECT id, role, content, tokens, created_at FROM messages WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        )

    def set_info(self, key, value):
        self._run(
            "INSERT INTO info(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
            (key, value),
        )

    def get_info(self, key, default=None):
        row = self._one("SELECT value FROM info WHERE key = ?", (key,))
        return row["value"] if row else default
