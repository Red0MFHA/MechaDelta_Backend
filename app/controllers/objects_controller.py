from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import object_service
from app.services.object_service import ObjectService

router = APIRouter(tags=["objects"])


@router.get("/sources/{source_id}/objects")
def list_objects(source_id: str, svc: ObjectService = Depends(object_service)):
    return svc.list(source_id)


@router.get("/objects/{object_id:path}")
def get_object(object_id: str, svc: ObjectService = Depends(object_service)):
    return svc.get(object_id)


@router.get("/objects/{object_id:path}/transitions")
def transitions(object_id: str, svc: ObjectService = Depends(object_service)):
    return svc.transitions(object_id)


@router.get("/objects/{object_id:path}/intervals")
def intervals(object_id: str, svc: ObjectService = Depends(object_service)):
    return svc.intervals(object_id)


@router.patch("/objects/{object_id:path}/label")
def set_label(object_id: str, payload: dict, svc: ObjectService = Depends(object_service)):
    return svc.set_label(object_id, payload)
