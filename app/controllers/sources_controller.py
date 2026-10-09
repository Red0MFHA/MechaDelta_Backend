from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import source_service
from app.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources(svc: SourceService = Depends(source_service)):
    return svc.list()


@router.get("/{source_id}")
def get_source(source_id: str, svc: SourceService = Depends(source_service)):
    return svc.get(source_id)


@router.post("")
def register_source(payload: dict, svc: SourceService = Depends(source_service)):
    return svc.register(payload)


@router.patch("/{source_id}")
def update_source(source_id: str, payload: dict, svc: SourceService = Depends(source_service)):
    return svc.update(source_id, payload)


@router.post("/{source_id}/connect")
def connect_source(source_id: str, svc: SourceService = Depends(source_service)):
    return svc.connect(source_id)


@router.post("/{source_id}/disconnect")
def disconnect_source(source_id: str, svc: SourceService = Depends(source_service)):
    return svc.disconnect(source_id)


@router.delete("/{source_id}", status_code=204)
def remove_source(source_id: str, svc: SourceService = Depends(source_service)):
    svc.remove(source_id)
