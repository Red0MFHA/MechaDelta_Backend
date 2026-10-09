from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.errors import AppError
from app.infrastructure.timeutil import iso, utcnow
from app.models.ingest import IngestionJobRow
from app.services.run_context import RunContext
from app.config import Settings


class IngestService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.ctx = RunContext(db, settings)

    def list(self, source_id: str | None = None) -> list[dict]:
        q = self.db.query(IngestionJobRow)
        if source_id:
            q = q.filter(IngestionJobRow.source_id == source_id)
        return [json.loads(r.job_json) for r in q.order_by(IngestionJobRow.created_at.desc()).all()]

    def get(self, job_id: str) -> dict:
        row = self.db.get(IngestionJobRow, job_id)
        if not row:
            raise AppError("not_found", f"Ingestion job {job_id} was not found.", status_code=404)
        return json.loads(row.job_json)

    def create(self, payload: dict) -> dict:
        self.ctx.source(payload["sourceId"])
        now = utcnow()
        jid = f"ing-{uuid.uuid4().hex[:10]}"
        job = {
            "id": jid,
            "sourceId": payload["sourceId"],
            "fileName": payload["fileName"],
            "fileSizeBytes": payload["fileSizeBytes"],
            "mimeType": payload["mimeType"],
            "status": "failed",
            "progress": 0,
            "createdAt": iso(now),
            "completedAt": iso(now),
            "failureReason": "Offline video ingestion pipeline is not wired yet. Use a ros2_simulation source with an existing run folder.",
            "settings": payload["settings"],
        }
        row = IngestionJobRow(
            id=jid,
            source_id=payload["sourceId"],
            file_name=payload["fileName"],
            file_size_bytes=payload["fileSizeBytes"],
            mime_type=payload["mimeType"],
            status="failed",
            progress=0,
            job_json=json.dumps(job),
            created_at=now,
            completed_at=now,
            failure_reason=job["failureReason"],
        )
        self.db.add(row)
        self.db.commit()
        return job

    def retry(self, job_id: str) -> dict:
        job = self.get(job_id)
        return self.create(
            {
                "sourceId": job["sourceId"],
                "fileName": job["fileName"],
                "fileSizeBytes": job["fileSizeBytes"],
                "mimeType": job["mimeType"],
                "settings": job["settings"],
            }
        )
