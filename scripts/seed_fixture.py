#!/usr/bin/env python3
"""Create a demo run folder with memory.db matching the MechaDelta POC schema."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "fixtures" / "runs" / "demo-transition"


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "payloads").mkdir(exist_ok=True)
    db_path = RUN / "memory.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE identities(id TEXT PRIMARY KEY, created REAL, last_seen REAL);
        CREATE TABLE views(id INTEGER PRIMARY KEY, object_id TEXT, embedding BLOB, histogram BLOB, evidence TEXT, captured REAL);
        CREATE TABLE observations(id INTEGER PRIMARY KEY, object_id TEXT, captured REAL, support TEXT, x REAL,y REAL,z REAL, score REAL,evidence TEXT);
        CREATE TABLE states(object_id TEXT PRIMARY KEY, support TEXT, first_seen REAL,last_seen REAL,version INTEGER DEFAULT 1);
        CREATE TABLE transitions(id INTEGER PRIMARY KEY,object_id TEXT,previous_support TEXT,new_support TEXT,t_lower REAL,t_upper REAL,confirmed_at REAL,association_score REAL,cause TEXT DEFAULT 'unknown',evidence TEXT);
        """
    )
    conn.execute("INSERT INTO identities VALUES (?,?,?)", ("CUP-001", 10.0, 120.0))
    conn.execute("INSERT INTO identities VALUES (?,?,?)", ("CUP-002", 12.0, 40.0))
    observations = [
        ("CUP-001", 10.0, "Table-A", 2.5, 2.4, 0.8, 0.91, "view-a1"),
        ("CUP-001", 18.0, "Table-A", 2.52, 2.41, 0.8, 0.93, "view-a2"),
        ("CUP-001", 28.0, "Table-A", 2.48, 2.39, 0.8, 0.90, "view-a3"),
        ("CUP-002", 14.0, "Table-A", 2.1, 2.5, 0.8, 0.88, "view-b1"),
        ("CUP-001", 110.0, "Table-B", 8.6, 2.4, 0.8, 0.89, "view-c1"),
        ("CUP-001", 120.0, "Table-B", 8.62, 2.42, 0.8, 0.92, "view-c2"),
    ]
    conn.executemany(
        "INSERT INTO observations(object_id,captured,support,x,y,z,score,evidence) VALUES (?,?,?,?,?,?,?,?)",
        observations,
    )
    conn.execute(
        "INSERT INTO states VALUES (?,?,?,?,?)",
        ("CUP-001", "Table-B", 110.0, 120.0, 2),
    )
    conn.execute(
        "INSERT INTO states VALUES (?,?,?,?,?)",
        ("CUP-002", "Table-A", 14.0, 40.0, 1),
    )
    conn.execute(
        "INSERT INTO transitions(object_id,previous_support,new_support,t_lower,t_upper,confirmed_at,association_score,cause,evidence) VALUES (?,?,?,?,?,?,?,?,?)",
        ("CUP-001", "Table-A", "Table-B", 28.0, 110.0, 110.0, 0.87, "unknown", "view-c1"),
    )
    conn.commit()
    conn.close()

    (RUN / "transition_answers.json").write_text(
        json.dumps(
            {
                "object_id": "CUP-001",
                "previous_location": "Table-A",
                "current_location": "Table-B",
                "cause": "unknown",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN / "ram_results.json").write_text(
        json.dumps({"ram_budget_bytes": 210000, "resident_payload_bytes": 0}, indent=2),
        encoding="utf-8",
    )
    latest = ROOT / "fixtures" / "runs" / "latest"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(RUN.name)
    print(f"Seeded fixture run at {RUN}")


if __name__ == "__main__":
    main()
