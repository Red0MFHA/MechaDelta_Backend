from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.timeutil import iso, utcnow
from app.models.evidence import EvidenceReportRow
from app.models.question import QuestionRow
from app.services.object_service import ObjectService
from app.services.run_context import RunContext


class EvidenceService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.ctx = RunContext(db, settings)
        self.objects = ObjectService(db, settings)

    def get(self, evidence_id: str) -> dict:
        row = self.db.get(EvidenceReportRow, evidence_id)
        if not row:
            raise AppError("not_found", f"Evidence {evidence_id} was not found.", status_code=404)
        return json.loads(row.report_json)

    def create_from_question(self, question_id: str) -> dict:
        q = self.db.get(QuestionRow, question_id)
        if not q:
            raise AppError("not_found", f"Question {question_id} was not found.", status_code=404)
        result = json.loads(q.result_json)
        return self._store(
            source_id=q.source_id,
            title=f"Evidence for: {q.question[:80]}",
            subject_kind="question",
            subject_id=question_id,
            summary=result.get("answer") or "No answer available.",
            evidence=result.get("evidence") or [],
            limitations=result.get("limitations") or [],
        )

    def create_from_object(self, object_id: str) -> dict:
        obj = self.objects.get(object_id)
        transitions = self.objects.transitions(obj["id"])
        evidence = [
            {
                "id": t["id"],
                "kind": "transition",
                "label": f"{t['previousSupport']} → {t['newSupport']}",
                "sourceId": obj["sourceId"],
                "occurredAt": t["confirmedAt"],
                "href": f"/app/operations/objects/{obj['id']}",
                "available": True,
            }
            for t in transitions
        ]
        if obj.get("lastKnownLocation"):
            evidence.append(
                {
                    "id": f"state-{obj['systemId']}",
                    "kind": "object",
                    "label": f"Current support {obj['lastKnownLocation']['support']}",
                    "sourceId": obj["sourceId"],
                    "occurredAt": obj["lastKnownLocation"].get("observedAt"),
                    "available": True,
                }
            )
        return self._store(
            source_id=obj["sourceId"],
            title=f"Evidence for {obj['systemId']}",
            subject_kind="object",
            subject_id=obj["id"],
            summary=f"{obj['systemId']} last known at {obj.get('lastKnownLocation', {}).get('support', 'unknown')}.",
            evidence=evidence,
            limitations=["Cause of movement is unknown unless directly observed."] if transitions else ["No confirmed transition."],
        )

    def _store(self, **kwargs) -> dict:
        now = utcnow()
        eid = f"ev-{uuid.uuid4().hex[:10]}"
        report = {
            "id": eid,
            "sourceId": kwargs["source_id"],
            "title": kwargs["title"],
            "subject": {"kind": kwargs["subject_kind"], "id": kwargs["subject_id"]},
            "summary": kwargs["summary"],
            "generatedSummary": True,
            "createdAt": iso(now),
            "evidence": kwargs["evidence"],
            "limitations": kwargs["limitations"],
        }
        row = EvidenceReportRow(
            id=eid,
            source_id=kwargs["source_id"],
            title=kwargs["title"],
            subject_kind=kwargs["subject_kind"],
            subject_id=kwargs["subject_id"],
            summary=kwargs["summary"],
            report_json=json.dumps(report),
            created_at=now,
        )
        self.db.add(row)
        self.db.commit()
        return report
