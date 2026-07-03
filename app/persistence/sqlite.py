from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings


class SessionStore:
    def __init__(self, settings: Settings) -> None:
        self._path = Path(settings.sqlite_path)

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    tool TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    observation_json TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                """
            )

    def create_session(self, order_id: str, status: str) -> str:
        session_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, order_id, status, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, order_id, status, created_at, "{}"),
            )
        return session_id

    def append_tool_call(
        self,
        session_id: str,
        step: int,
        tool: str,
        duration_ms: int,
        observation: dict,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_calls (session_id, step, tool, duration_ms, observation_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    step,
                    tool,
                    duration_ms,
                    json.dumps(observation, ensure_ascii=False),
                ),
            )

    def update_session_status(
        self,
        session_id: str,
        status: str,
        payload: dict | None = None,
    ) -> None:
        with self._connect() as conn:
            if payload is not None:
                conn.execute(
                    """
                    UPDATE sessions
                    SET status = ?, payload_json = ?
                    WHERE id = ?
                    """,
                    (status, json.dumps(payload, ensure_ascii=False), session_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE sessions
                    SET status = ?
                    WHERE id = ?
                    """,
                    (status, session_id),
                )

    def get_session(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, order_id, status, created_at, payload_json
                FROM sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None

            tool_rows = conn.execute(
                """
                SELECT step, tool, duration_ms, observation_json
                FROM tool_calls
                WHERE session_id = ?
                ORDER BY step ASC, id ASC
                """,
                (session_id,),
            ).fetchall()

        steps = [
            {
                "step": tr["step"],
                "tool": tr["tool"],
                "duration_ms": tr["duration_ms"],
                "observation": json.loads(tr["observation_json"]),
            }
            for tr in tool_rows
        ]

        return {
            "session_id": row["id"],
            "order_id": row["order_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "steps": steps,
        }
