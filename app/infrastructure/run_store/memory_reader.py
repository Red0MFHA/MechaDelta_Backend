"""Read-only adapter over a MechaDelta run folder memory.db."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class MemoryReader:
    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.db_path = self.run_dir / "memory.db"
        if not self.db_path.exists():
            raise FileNotFoundError(f"No memory.db at {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def identities(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM identities ORDER BY id")]

    def states(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM states ORDER BY object_id")]

    def state(self, object_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM states WHERE object_id=?", (object_id,)).fetchone()
            return dict(row) if row else None

    def transitions(self, object_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if object_id:
                rows = conn.execute(
                    "SELECT * FROM transitions WHERE object_id=? ORDER BY id", (object_id,)
                )
            else:
                rows = conn.execute("SELECT * FROM transitions ORDER BY id")
            return [dict(r) for r in rows]

    def observations(self, object_id: str | None = None, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            if object_id:
                rows = conn.execute(
                    "SELECT * FROM observations WHERE object_id=? ORDER BY captured DESC LIMIT ?",
                    (object_id, limit),
                )
            else:
                rows = conn.execute(
                    "SELECT * FROM observations ORDER BY captured DESC LIMIT ?", (limit,)
                )
            return [dict(r) for r in rows]

    def query_object(self, object_id: str) -> dict:
        with self._connect() as conn:
            current = conn.execute("SELECT * FROM states WHERE object_id=?", (object_id,)).fetchone()
            previous = conn.execute(
                "SELECT * FROM transitions WHERE object_id=? ORDER BY id DESC LIMIT 1",
                (object_id,),
            ).fetchone()
            return {
                "object_id": object_id,
                "last_observed": dict(current) if current else None,
                "previous_location": previous["previous_support"] if previous else None,
                "transition": dict(previous) if previous else None,
                "limitation": None
                if previous
                else "No confirmed previous-location transition retained.",
            }

    def payload_rows(self) -> list[dict]:
        index = self.run_dir / "payloads" / "payload_index.sqlite"
        if not index.exists():
            return []
        conn = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM payloads ORDER BY object_id")]
        finally:
            conn.close()

    def run_json(self, name: str) -> dict | list | None:
        path = self.run_dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
