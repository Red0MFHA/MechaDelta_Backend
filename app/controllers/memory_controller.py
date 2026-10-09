from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import memory_service
from app.services.memory_service import MemoryService

router = APIRouter(tags=["memory"])


@router.get("/memory")
def list_memory(
    sourceId: str = Query(...),
    search: str | None = None,
    types: list[str] | None = Query(None),
    objectId: str | None = None,
    svc: MemoryService = Depends(memory_service),
):
    return svc.list(
        {"sourceId": sourceId, "search": search, "types": types, "objectId": objectId}
    )


@router.get("/memory/{memory_id}")
def get_memory(memory_id: str, svc: MemoryService = Depends(memory_service)):
    return svc.get(memory_id)


@router.get("/memory/{memory_id}/history")
def memory_history(memory_id: str, svc: MemoryService = Depends(memory_service)):
    return svc.history(memory_id)
