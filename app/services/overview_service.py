from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.bridge.client import BridgeClient
from app.infrastructure.timeutil import iso
from app.services.event_service import EventService
from app.services.object_service import ObjectService
from app.services.question_service import QuestionService
from app.services.runtime_service import RuntimeService
from app.services.task_service import TaskService


class OverviewService:
    def __init__(self, db: Session, settings: Settings, bridge: BridgeClient):
        self.events = EventService(db, settings)
        self.objects = ObjectService(db, settings)
        self.questions = QuestionService(db, settings)
        self.tasks = TaskService(db, settings, bridge)
        self.runtime = RuntimeService(db, settings)

    def get(self, source_id: str) -> dict:
        events = self.events.list({"sourceId": source_id, "limit": 5})["items"]
        objects = self.objects.list(source_id)
        transitions = sum(len(o.get("transitionIds") or []) for o in objects)
        questions = self.questions.list(source_id)[:5]
        tasks = self.tasks.list({"sourceId": source_id})[:5]
        runtime = self.runtime.snapshot(source_id)
        return {
            "sourceId": source_id,
            "generatedAt": iso(),
            "recentEvents": events,
            "recentTasks": tasks,
            "recentQuestions": questions,
            "objectCount": len(objects),
            "transitionCount": transitions,
            "runtime": {
                "ramBudgetBytes": runtime["ramBudgetBytes"],
                "residentPayloadBytes": runtime["residentPayloadBytes"],
                "diskPayloadBytes": runtime["diskPayloadBytes"],
                "measuredAt": runtime["measuredAt"],
                "live": runtime["live"],
            },
        }
