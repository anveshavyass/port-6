import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from backend import config

DB_PATH = config.BASE_DIR / "data" / "chat_history.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

TITLE_MAX_LEN = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_title(first_question: str) -> str:
    text = " ".join(first_question.split())
    return text if len(text) <= TITLE_MAX_LEN else text[:TITLE_MAX_LEN].rstrip() + "…"


def create_conversation(first_question: str) -> int:
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
            (_make_title(first_question), now, now),
        )
        return cursor.lastrowid


def save_message(conversation_id: int, message: dict) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, data, created_at) VALUES (?, ?, ?)",
            (conversation_id, json.dumps(message), now),
        )
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))


def list_conversations() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def load_messages(conversation_id: int) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT data FROM messages WHERE conversation_id = ? ORDER BY id", (conversation_id,)
        ).fetchall()
        return [json.loads(row["data"]) for row in rows]


def delete_conversation(conversation_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
