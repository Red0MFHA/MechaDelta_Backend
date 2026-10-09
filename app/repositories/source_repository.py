from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.source import SourceRow


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[SourceRow]:
        return list(self.db.query(SourceRow).order_by(SourceRow.created_at).all())

    def get(self, source_id: str) -> SourceRow | None:
        return self.db.get(SourceRow, source_id)

    def add(self, row: SourceRow) -> SourceRow:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: SourceRow) -> SourceRow:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: SourceRow) -> None:
        self.db.delete(row)
        self.db.commit()


def source_to_dict(row: SourceRow) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "connectionState": row.connection_state,
        "origin": row.origin,
        "description": row.description,
        "config": json.loads(row.config_json or "[]"),
        "capabilities": json.loads(row.capabilities_json or "{}"),
        "activeRunId": row.active_run_id,
        "lastSeenAt": row.last_seen_at.isoformat().replace("+00:00", "Z") if row.last_seen_at else None,
        "createdAt": row.created_at.isoformat().replace("+00:00", "Z"),
        "updatedAt": row.updated_at.isoformat().replace("+00:00", "Z"),
    }


def mask_config(fields: list[dict]) -> list[dict]:
    out = []
    for f in fields:
        item = dict(f)
        if item.get("secret") and item.get("value"):
            item["value"] = "••••••••"
        out.append(item)
    return out
