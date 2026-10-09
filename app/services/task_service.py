from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.bridge.client import BridgeClient
from app.infrastructure.timeutil import iso, utcnow
from app.models.task import TaskRow
from app.services.object_service import ObjectService
from app.services.run_context import RunContext

JOG_MAP = {
    "forward": "forward",
    "back": "back",
    "look_up": "look_up",
    "look_down": "look_down",
    "turn_left": "turn_left",
    "turn_right": "turn_right",
}


class TaskService:
    def __init__(self, db: Session, settings: Settings, bridge: BridgeClient):
        self.db = db
        self.ctx = RunContext(db, settings)
        self.bridge = bridge
        self.objects = ObjectService(db, settings)

    def list(self, query: dict) -> list[dict]:
        q = self.db.query(TaskRow)
        if query.get("sourceId"):
            q = q.filter(TaskRow.source_id == query["sourceId"])
        rows = q.order_by(TaskRow.created_at.desc()).all()
        items = [json.loads(r.task_json) for r in rows]
        if query.get("status"):
            statuses = set(query["status"])
            items = [t for t in items if t["status"] in statuses]
        if query.get("search"):
            s = query["search"].lower()
            items = [t for t in items if s in t["command"].lower()]
        return items

    def get(self, task_id: str) -> dict:
        row = self.db.get(TaskRow, task_id)
        if not row:
            raise AppError("not_found", f"Task {task_id} was not found.", status_code=404)
        return json.loads(row.task_json)

    def jog(self, request: dict) -> dict:
        source = self.ctx.source(request["sourceId"])
        direction = request["direction"]
        if direction not in JOG_MAP:
            raise AppError("validation_error", f"Unknown jog direction {direction}")
        now = utcnow()
        tid = f"task-{uuid.uuid4().hex[:10]}"
        simulated = True
        status = "succeeded"
        error = None
        try:
            self.bridge.jog(direction)
            simulated = self.bridge.health().get("mode") == "stub"
            status = "succeeded"
        except AppError as exc:
            status = "failed"
            error = exc.message
        task = {
            "id": tid,
            "sourceId": source.id,
            "type": "jog",
            "status": status,
            "command": request.get("command") or f"jog {direction}",
            "createdAt": iso(now),
            "startedAt": iso(now),
            "completedAt": iso(now),
            "jog": direction,
            "history": [
                {"status": "accepted", "at": iso(now)},
                {"status": status, "at": iso(now), "note": error},
            ],
            "resultSummary": "Jog command sent." if status == "succeeded" else error,
            "errorMessage": error,
            "simulated": simulated,
        }
        self._persist(task, now)
        return task

    def navigate(self, request: dict) -> dict:
        source = self.ctx.source(request["sourceId"])
        if not request.get("confirmation"):
            raise AppError("validation_error", "Navigation requires confirmation: true.")
        target = dict(request.get("target") or {})
        reason = request.get("reason") or "navigate_to_waypoint"
        if reason == "navigate_to_last_known_object_location" and target.get("objectId"):
            obj = self.objects.get(target["objectId"])
            loc = obj.get("lastKnownLocation") or {}
            target["x"] = loc.get("x") if loc.get("x") is not None else target.get("x")
            target["y"] = loc.get("y") if loc.get("y") is not None else target.get("y")
            target["label"] = target.get("label") or loc.get("support")
            target["locationObservedAt"] = loc.get("observedAt")
            # Fallback table waypoints if xyz missing
            if target.get("x") is None and loc.get("support") == "Table-A":
                target["x"], target["y"] = 2.65, 1.4
            if target.get("x") is None and loc.get("support") == "Table-B":
                target["x"], target["y"] = 8.85, 1.4
        if target.get("x") is None or target.get("y") is None:
            raise AppError("validation_error", "Navigate target is missing x/y.")
        now = utcnow()
        tid = f"task-{uuid.uuid4().hex[:10]}"
        simulated = True
        status = "succeeded"
        error = None
        try:
            self.bridge.navigate(float(target["x"]), float(target["y"]), float(target.get("yaw") or 0))
            simulated = self.bridge.health().get("mode") == "stub"
        except AppError as exc:
            status = "failed"
            error = exc.message
        task = {
            "id": tid,
            "sourceId": source.id,
            "type": "navigate_last_known" if "last_known" in reason else "navigate_waypoint",
            "status": status,
            "command": request.get("command") or "navigate",
            "createdAt": iso(now),
            "startedAt": iso(now),
            "completedAt": iso(now),
            "target": target,
            "history": [
                {"status": "accepted", "at": iso(now)},
                {"status": status, "at": iso(now), "note": error},
            ],
            "resultSummary": "Navigation goal sent." if status == "succeeded" else error,
            "errorMessage": error,
            "simulated": simulated,
        }
        self._persist(task, now)
        return task

    def log_unsupported(self, request: dict) -> dict:
        now = utcnow()
        tid = f"task-{uuid.uuid4().hex[:10]}"
        task = {
            "id": tid,
            "sourceId": request["sourceId"],
            "type": "unsupported",
            "status": "rejected",
            "command": request["command"],
            "createdAt": iso(now),
            "completedAt": iso(now),
            "history": [{"status": "rejected", "at": iso(now), "note": request.get("reason")}],
            "resultSummary": request.get("reason") or "Unsupported command.",
            "errorCode": "unsupported",
            "errorMessage": request.get("reason"),
            "simulated": True,
        }
        self._persist(task, now)
        return task

    def cancel(self, task_id: str) -> dict:
        row = self.db.get(TaskRow, task_id)
        if not row:
            raise AppError("not_found", f"Task {task_id} was not found.", status_code=404)
        task = json.loads(row.task_json)
        now = utcnow()
        try:
            self.bridge.cancel()
        except AppError:
            pass
        task["status"] = "cancelled"
        task["completedAt"] = iso(now)
        task["history"].append({"status": "cancelled", "at": iso(now)})
        row.status = "cancelled"
        row.completed_at = now
        row.task_json = json.dumps(task)
        self.db.add(row)
        self.db.commit()
        return task

    def _persist(self, task: dict, now) -> None:
        row = TaskRow(
            id=task["id"],
            source_id=task["sourceId"],
            type=task["type"],
            status=task["status"],
            command=task["command"],
            task_json=json.dumps(task),
            created_at=now,
            started_at=now,
            completed_at=now if task["status"] in {"succeeded", "failed", "rejected", "cancelled"} else None,
            simulated=bool(task.get("simulated")),
        )
        self.db.add(row)
        self.db.commit()
