from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import overview_service
from app.services.overview_service import OverviewService

router = APIRouter(tags=["overview"])


@router.get("/sources/{source_id}/overview")
def overview(source_id: str, svc: OverviewService = Depends(overview_service)):
    return svc.get(source_id)
