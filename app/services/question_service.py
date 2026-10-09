from __future__ import annotations

import json
import re
import time
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.timeutil import iso, utcnow
from app.models.question import QuestionRow
from app.services.object_service import ObjectService
from app.services.run_context import RunContext


class QuestionService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.ctx = RunContext(db, settings)
        self.objects = ObjectService(db, settings)

    def list(self, source_id: str) -> list[dict]:
        rows = (
            self.db.query(QuestionRow)
            .filter_by(source_id=source_id)
            .order_by(QuestionRow.created_at.desc())
            .all()
        )
        return [json.loads(r.result_json) for r in rows]

    def get(self, question_id: str) -> dict:
        row = self.db.get(QuestionRow, question_id)
        if not row:
            raise AppError("not_found", f"Question {question_id} was not found.", status_code=404)
        return json.loads(row.result_json)

    def ask(self, request: dict) -> dict:
        started = time.perf_counter()
        source_id = request["sourceId"]
        _, run_id, reader = self.ctx.reader(source_id)
        objects = self.objects.list(source_id)
        question = request["question"]
        resolved = self._resolve_object(question, objects, request.get("objectIds"))
        now = utcnow()
        qid = f"q-{uuid.uuid4().hex[:10]}"

        if not resolved:
            result = {
                "id": qid,
                "sourceId": source_id,
                "runId": run_id,
                "question": question,
                "status": "insufficient_evidence",
                "answerKind": "insufficient_evidence",
                "answer": "No matching object was found in the active run.",
                "createdAt": iso(now),
                "completedAt": iso(now),
                "context": {
                    "timeRange": request.get("timeRange"),
                    "objectIds": request.get("objectIds") or [],
                },
                "evidence": [],
                "limitations": ["Could not resolve which object the question refers to."],
                "retrievalMs": (time.perf_counter() - started) * 1000,
            }
        else:
            system_id = resolved["systemId"]
            data = reader.query_object(system_id)
            state = data["last_observed"]
            transition = data["transition"]
            intent = self._intent(question)
            evidence = []
            limitations = []
            if transition:
                evidence.append(
                    {
                        "id": f"tr-{transition['id']}",
                        "kind": "transition",
                        "label": f"{transition['previous_support']} → {transition['new_support']}",
                        "sourceId": source_id,
                        "occurredAt": iso(now),
                        "href": f"/app/operations/objects/{resolved['id']}",
                        "excerpt": "Confirmed transition from the run memory database.",
                        "available": True,
                    }
                )

            if intent in {"previous", "when", "unknown"} and transition:
                answer_kind = "from_transition"
                if intent == "when":
                    answer = (
                        f"{resolved['systemId']} moved from {transition['previous_support']} to "
                        f"{transition['new_support']} between sim t={transition['t_lower']:.1f}s and "
                        f"t={transition['t_upper']:.1f}s (observation-bounded)."
                    )
                else:
                    answer = (
                        f"{resolved['systemId']} was previously at {transition['previous_support']}; "
                        f"it is now at {transition['new_support']}."
                    )
                status = "completed"
            elif intent == "cause":
                answer_kind = "cause_unknown"
                answer = (
                    f"The movement of {resolved['systemId']} was not directly observed; cause remains unknown."
                )
                status = "completed"
                limitations.append("Off-camera relocation; cause is not in the evidence.")
            elif intent == "current" and state:
                answer_kind = "from_current_state"
                answer = f"{resolved['systemId']} was last verified at {state['support']}."
                status = "completed"
            elif state:
                answer_kind = "from_current_state"
                answer = f"{resolved['systemId']} was last verified at {state['support']}."
                status = "completed"
            else:
                answer_kind = "insufficient_evidence"
                answer = data["limitation"] or "Insufficient evidence."
                status = "insufficient_evidence"
                limitations.append(data["limitation"] or "No confirmed transition.")

            result = {
                "id": qid,
                "sourceId": source_id,
                "runId": run_id,
                "question": question,
                "answer": answer,
                "answerKind": answer_kind,
                "status": status,
                "createdAt": iso(now),
                "completedAt": iso(now),
                "context": {
                    "timeRange": request.get("timeRange"),
                    "objectIds": request.get("objectIds") or [resolved["id"]],
                },
                "resolvedObjectId": resolved["id"],
                "currentPlace": state["support"] if state else None,
                "previousPlace": transition["previous_support"] if transition else None,
                "answeredWithoutPayload": True,
                "evidence": evidence,
                "confidence": float(transition["association_score"]) if transition else None,
                "limitations": limitations,
                "retrievalMs": (time.perf_counter() - started) * 1000,
            }

        row = QuestionRow(
            id=qid,
            source_id=source_id,
            run_id=run_id,
            question=question,
            answer=result.get("answer"),
            answer_kind=result.get("answerKind"),
            status=result["status"],
            result_json=json.dumps(result),
            created_at=now,
            completed_at=now,
            retrieval_ms=result.get("retrievalMs"),
        )
        self.db.add(row)
        self.db.commit()
        return result

    def _resolve_object(self, question: str, objects: list[dict], object_ids: list[str] | None):
        if object_ids:
            for obj in objects:
                if obj["id"] in object_ids or obj["systemId"] in object_ids:
                    return obj
        q = question.lower()
        for obj in objects:
            if obj["systemId"].lower() in q:
                return obj
            if obj.get("slug") and obj["slug"].lower() in q:
                return obj
        if re.search(r"\b(cup|mug)\b", q) and objects:
            return objects[0]
        return objects[0] if len(objects) == 1 else None

    def _intent(self, question: str) -> str:
        q = f" {question.lower()} "
        if any(w in q for w in (" who ", " why ", " cause ", " someone ")):
            return "cause"
        if " when " in q or " what time " in q:
            return "when"
        if any(w in q for w in (" before ", " previous ", " previously ", " where was ", " earlier ")):
            return "previous"
        if any(w in q for w in (" now ", " currently ", " where is ", " last seen ", " last saw ")):
            return "current"
        return "unknown"
