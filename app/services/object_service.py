from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.timeutil import utcnow
from app.models.object_label import ObjectLabelRow
from app.services.mappers import intervals_for, object_track, transition_dto
from app.services.run_context import RunContext


class ObjectService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.ctx = RunContext(db, settings)

    def list(self, source_id: str) -> list[dict]:
        _, run_id, reader = self.ctx.reader(source_id)
        labels = {r.object_id: r for r in self.db.query(ObjectLabelRow).filter_by(source_id=source_id)}
        identities = reader.identities()
        states = {s["object_id"]: s for s in reader.states()}
        transitions = reader.transitions()
        observations = reader.observations(limit=1000)
        return [
            object_track(
                source_id,
                run_id,
                ident,
                states.get(ident["id"]),
                transitions,
                observations,
                {
                    "slug": labels[ident["id"]].slug if ident["id"] in labels else None,
                    "photo_url": labels[ident["id"]].photo_url if ident["id"] in labels else None,
                }
                if ident["id"] in labels
                else None,
            )
            for ident in identities
        ]

    def get(self, object_id: str) -> dict:
        for src in self.ctx.sources.list():
            for obj in self.list(src.id):
                if obj["id"] == object_id or obj["systemId"].upper() == object_id.upper():
                    return obj
        raise AppError("not_found", f"Object {object_id} was not found.", status_code=404)

    def transitions(self, object_id: str) -> list[dict]:
        obj = self.get(object_id)
        _, run_id, reader = self.ctx.reader(obj["sourceId"])
        return [transition_dto(run_id, t) for t in reader.transitions(obj["systemId"])]

    def intervals(self, object_id: str) -> list[dict]:
        obj = self.get(object_id)
        _, run_id, reader = self.ctx.reader(obj["sourceId"])
        state = reader.state(obj["systemId"])
        return intervals_for(run_id, obj["id"], state, reader.transitions())

    def set_label(self, object_id: str, payload: dict) -> dict:
        obj = self.get(object_id)
        system_id = obj["systemId"]
        row = self.db.get(ObjectLabelRow, system_id)
        now = utcnow()
        if not row:
            row = ObjectLabelRow(object_id=system_id, source_id=obj["sourceId"], updated_at=now)
        if "slug" in payload:
            row.slug = payload["slug"]
        if "photoUrl" in payload:
            row.photo_url = payload["photoUrl"]
        row.updated_at = now
        self.db.add(row)
        self.db.commit()
        return self.get(obj["id"])
