from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import task_service
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(
    sourceId: str | None = None,
    status: list[str] | None = Query(None),
    search: str | None = None,
    svc: TaskService = Depends(task_service),
):
    return svc.list({"sourceId": sourceId, "status": status, "search": search})


@router.get("/{task_id}")
def get_task(task_id: str, svc: TaskService = Depends(task_service)):
    return svc.get(task_id)


@router.post("/jog")
def jog(payload: dict, svc: TaskService = Depends(task_service)):
    return svc.jog(payload)


@router.post("/cmd_vel")
def cmd_vel(payload: dict, svc: TaskService = Depends(task_service)):
    return svc.cmd_vel(payload)


@router.post("/navigate")
def navigate(payload: dict, svc: TaskService = Depends(task_service)):
    return svc.navigate(payload)


@router.post("/unsupported")
def unsupported(payload: dict, svc: TaskService = Depends(task_service)):
    return svc.log_unsupported(payload)


@router.post("/{task_id}/cancel")
def cancel(task_id: str, svc: TaskService = Depends(task_service)):
    return svc.cancel(task_id)
