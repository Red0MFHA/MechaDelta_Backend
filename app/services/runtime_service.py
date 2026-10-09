from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.timeutil import iso
from app.services.mappers import t_iso, ui_object_id
from app.services.run_context import RunContext


class RuntimeService:
    def __init__(self, db: Session, settings: Settings):
        self.ctx = RunContext(db, settings)

    def snapshot(self, source_id: str) -> dict:
        _, run_id, reader = self.ctx.reader(source_id)
        payloads = reader.payload_rows()
        disk = sum(int(p.get("decoded_bytes") or 0) for p in payloads)
        folded = []
        for state in reader.states():
            folded.append(
                {
                    "id": f"fold-{state['object_id']}",
                    "objectId": ui_object_id(run_id, state["object_id"]),
                    "support": state["support"],
                    "intervalId": f"iv-{state['object_id']}-curr",
                    "sightingCount": 1,
                    "firstSeenAt": t_iso(state["first_seen"]),
                    "lastSeenAt": t_iso(state["last_seen"]),
                }
            )
        ram = reader.run_json("ram_results.json")
        budget = 210_000
        resident = 0
        if isinstance(ram, dict):
            budget = int(ram.get("ram_budget_bytes") or budget)
            resident = int(ram.get("resident_payload_bytes") or 0)
        return {
            "sourceId": source_id,
            "runId": run_id,
            "measuredAt": iso(),
            "origin": "simulated",
            "live": False,
            "ramBudgetBytes": budget,
            "residentPayloadBytes": resident,
            "perceptionFloorBytes": None,
            "processRssBytes": None,
            "diskPayloadBytes": disk,
            "databaseBytes": (reader.db_path.stat().st_size if reader.db_path.exists() else 0),
            "evidenceBytes": disk,
            "floorCrossings": 0,
            "kept": [],
            "released": [
                {
                    "id": f"rel-{p['object_id']}",
                    "objectId": ui_object_id(run_id, p["object_id"]),
                    "memoryId": f"mem-payload-{p['object_id']}",
                    "bytes": int(p.get("decoded_bytes") or 0),
                    "releasedAt": t_iso(p.get("capture_time")) or iso(),
                    "stillOnDisk": True,
                    "stale": False,
                }
                for p in payloads
            ],
            "folded": folded,
            "series": [],
        }

    def ledger(self, query: dict) -> list[dict]:
        snap = self.snapshot(query["sourceId"])
        return [
            {
                "id": f"led-runtime-{i}",
                "sequence": i + 1,
                "sourceId": query["sourceId"],
                "runId": snap["runId"],
                "category": "memory",
                "eventType": "created",
                "occurredAt": snap["measuredAt"],
                "details": {"note": "Derived from run folder; full process ledger unavailable."},
            }
            for i in range(1)
        ]

    def series(self, source_id: str, run_id: str | None = None) -> list[dict]:
        return []
