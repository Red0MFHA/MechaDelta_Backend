from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.timeutil import iso
from app.services.mappers import t_iso, ui_object_id
from app.services.run_context import RunContext


class MemoryService:
    def __init__(self, db: Session, settings: Settings):
        self.ctx = RunContext(db, settings)

    def list(self, query: dict) -> list[dict]:
        source_id = query["sourceId"]
        _, run_id, reader = self.ctx.reader(source_id)
        records: list[dict] = []
        for state in reader.states():
            records.append(
                {
                    "id": f"mem-state-{state['object_id']}",
                    "sourceId": source_id,
                    "runId": run_id,
                    "type": "anchor",
                    "summary": f"{state['object_id']} at {state['support']}",
                    "observedAt": t_iso(state["last_seen"]),
                    "createdAt": t_iso(state["first_seen"]) or iso(),
                    "persistent": True,
                    "residencyState": "persistent_only",
                    "relatedEventIds": [],
                    "relatedObjectIds": [ui_object_id(run_id, state["object_id"])],
                    "metadata": {"support": state["support"], "version": state.get("version", 1)},
                }
            )
        for tr in reader.transitions():
            records.append(
                {
                    "id": f"mem-tr-{tr['id']}",
                    "sourceId": source_id,
                    "runId": run_id,
                    "type": "transition",
                    "summary": f"{tr['object_id']}: {tr['previous_support']} → {tr['new_support']}",
                    "observedAt": t_iso(tr["confirmed_at"]),
                    "createdAt": t_iso(tr["confirmed_at"]) or iso(),
                    "persistent": True,
                    "residencyState": "persistent_only",
                    "relatedEventIds": [f"evt-tr-{tr['id']}"],
                    "relatedObjectIds": [ui_object_id(run_id, tr["object_id"])],
                    "metadata": {"cause": tr.get("cause") or "unknown"},
                }
            )
        for payload in reader.payload_rows():
            records.append(
                {
                    "id": f"mem-payload-{payload['object_id']}",
                    "sourceId": source_id,
                    "runId": run_id,
                    "type": "payload",
                    "summary": f"Payload for {payload['object_id']} ({payload.get('support')})",
                    "observedAt": t_iso(payload.get("capture_time")),
                    "createdAt": t_iso(payload.get("capture_time")) or iso(),
                    "persistent": True,
                    "residencyState": "persistent_only",
                    "bytes": payload.get("decoded_bytes"),
                    "relatedEventIds": [],
                    "relatedObjectIds": [ui_object_id(run_id, payload["object_id"])],
                    "contentHash": payload.get("content_hash"),
                    "metadata": {
                        "stateVersion": payload.get("state_version"),
                        "fileHash": payload.get("file_hash") or "",
                    },
                }
            )
        if query.get("types"):
            types = set(query["types"])
            records = [r for r in records if r["type"] in types]
        if query.get("objectId"):
            oid = query["objectId"]
            records = [r for r in records if oid in r["relatedObjectIds"] or oid.split(":")[-1] in str(r["relatedObjectIds"])]
        if query.get("search"):
            q = query["search"].lower()
            records = [r for r in records if q in r["summary"].lower()]
        return records

    def get(self, memory_id: str) -> dict:
        for src in self.ctx.sources.list():
            for row in self.list({"sourceId": src.id}):
                if row["id"] == memory_id:
                    return row
        raise AppError("not_found", f"Memory {memory_id} was not found.", status_code=404)

    def history(self, memory_id: str) -> list[dict]:
        record = self.get(memory_id)
        return [
            {
                "id": f"led-{memory_id}-1",
                "sequence": 1,
                "sourceId": record["sourceId"],
                "runId": record["runId"],
                "memoryId": memory_id,
                "category": "memory",
                "eventType": "created",
                "occurredAt": record.get("createdAt") or iso(),
                "details": {"note": "Loaded from run folder metadata."},
            }
        ]
