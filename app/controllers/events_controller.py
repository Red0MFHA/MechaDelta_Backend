from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import event_service
from app.services.event_service import EventService

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(
    sourceId: str = Query(...),
    search: str | None = None,
    types: list[str] | None = Query(None),
    objectId: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    svc: EventService = Depends(event_service),
):
    return svc.list(
        {
            "sourceId": sourceId,
            "search": search,
            "types": types,
            "objectId": objectId,
            "cursor": cursor,
            "limit": limit,
        }
    )


@router.get("/events/{event_id}")
def get_event(event_id: str, svc: EventService = Depends(event_service)):
    return svc.get(event_id)
