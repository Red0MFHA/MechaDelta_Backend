from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import runtime_service
from app.services.runtime_service import RuntimeService

router = APIRouter(tags=["runtime"])


@router.get("/sources/{source_id}/runtime")
def snapshot(source_id: str, svc: RuntimeService = Depends(runtime_service)):
    return svc.snapshot(source_id)


@router.get("/runtime/ledger")
def ledger(
    sourceId: str = Query(...),
    runId: str | None = None,
    svc: RuntimeService = Depends(runtime_service),
):
    return svc.ledger({"sourceId": sourceId, "runId": runId})


@router.get("/sources/{source_id}/runtime/series")
def series(source_id: str, runId: str | None = None, svc: RuntimeService = Depends(runtime_service)):
    return svc.series(source_id, runId)
