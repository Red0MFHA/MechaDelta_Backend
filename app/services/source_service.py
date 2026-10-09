from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.bridge.client import BridgeClient
from app.infrastructure.timeutil import utcnow
from app.models.source import SourceRow
from app.repositories.source_repository import SourceRepository, mask_config, source_to_dict
from app.services.mappers import DEFAULT_CAPABILITIES


class SourceService:
    def __init__(self, db: Session, settings: Settings, bridge: BridgeClient):
        self.repo = SourceRepository(db)
        self.settings = settings
        self.bridge = bridge

    def list(self) -> list[dict]:
        return [self._view(r) for r in self.repo.list()]

    def get(self, source_id: str) -> dict:
        return self._view(self._require(source_id))

    def register(self, payload: dict) -> dict:
        now = utcnow()
        config_fields = [
            {"key": k, "label": k, "value": v, "secret": k.lower() in {"token", "password", "secret"}}
            for k, v in (payload.get("config") or {}).items()
        ]
        row = SourceRow(
            id=f"src-{uuid.uuid4().hex[:10]}",
            name=payload["name"],
            kind=payload["kind"],
            connection_state="offline",
            origin="simulated" if payload["kind"] == "ros2_simulation" else "recorded",
            description=payload.get("description"),
            config_json=json.dumps(config_fields),
            capabilities_json=json.dumps(DEFAULT_CAPABILITIES),
            active_run_id=None,
            created_at=now,
            updated_at=now,
        )
        return self._view(self.repo.add(row))

    def update(self, source_id: str, payload: dict) -> dict:
        row = self._require(source_id)
        if "name" in payload and payload["name"] is not None:
            row.name = payload["name"]
        if "description" in payload:
            row.description = payload["description"]
        row.updated_at = utcnow()
        return self._view(self.repo.save(row))

    def connect(self, source_id: str) -> dict:
        row = self._require(source_id)
        health = self.bridge.health()
        row.connection_state = "online" if health.get("ok") else "degraded"
        row.active_run_id = row.active_run_id or self.settings.default_run_id
        row.last_seen_at = utcnow()
        row.updated_at = utcnow()
        return self._view(self.repo.save(row))

    def disconnect(self, source_id: str) -> dict:
        row = self._require(source_id)
        row.connection_state = "offline"
        row.updated_at = utcnow()
        return self._view(self.repo.save(row))

    def remove(self, source_id: str) -> None:
        self.repo.delete(self._require(source_id))

    def _require(self, source_id: str) -> SourceRow:
        row = self.repo.get(source_id)
        if not row:
            raise AppError("not_found", f"Source {source_id} was not found.", status_code=404)
        return row

    def _view(self, row: SourceRow) -> dict:
        data = source_to_dict(row)
        data["config"] = mask_config(data["config"])
        return data
