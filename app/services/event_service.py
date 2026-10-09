from __future__ import annotations

from app.config import Settings
from app.errors import AppError
from app.services.mappers import events_from_run
from app.services.run_context import RunContext
from sqlalchemy.orm import Session


class EventService:
    def __init__(self, db: Session, settings: Settings):
        self.ctx = RunContext(db, settings)

    def list(self, query: dict) -> dict:
        source_id = query["sourceId"]
        _, run_id, reader = self.ctx.reader(source_id)
        items = events_from_run(
            source_id,
            run_id,
            reader.identities(),
            reader.states(),
            reader.transitions(),
            reader.observations(limit=200),
        )
        if query.get("types"):
            types = set(query["types"])
            items = [e for e in items if e["type"] in types]
        if query.get("objectId"):
            oid = query["objectId"]
            items = [e for e in items if oid in e["objectIds"] or oid.split(":")[-1] in str(e["objectIds"])]
        if query.get("search"):
            q = query["search"].lower()
            items = [e for e in items if q in e["summary"].lower()]
        limit = int(query.get("limit") or 50)
        cursor = int(query.get("cursor") or 0)
        page = items[cursor : cursor + limit]
        next_cursor = str(cursor + limit) if cursor + limit < len(items) else None
        return {"items": page, "total": len(items), "nextCursor": next_cursor}

    def get(self, event_id: str) -> dict:
        # scan default source events
        for src in self.ctx.sources.list():
            page = self.list({"sourceId": src.id, "limit": 1000})
            for item in page["items"]:
                if item["id"] == event_id:
                    return item
        raise AppError("not_found", f"Event {event_id} was not found.", status_code=404)
