from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import bridge_dep, media_service
from app.infrastructure.bridge.client import BridgeClient
from app.services.media_service import MediaService

router = APIRouter(tags=["media"])


@router.get("/sources/{source_id}/media")
def media(source_id: str, svc: MediaService = Depends(media_service)):
    return svc.get(source_id)


@router.get("/sources/{source_id}/detections")
def detections(source_id: str, svc: MediaService = Depends(media_service)):
    return svc.detections(source_id)


@router.get("/sources/{source_id}/map")
def map_info(source_id: str, svc: MediaService = Depends(media_service)):
    return svc.map(source_id)


@router.get("/sources/{source_id}/pose")
def pose(source_id: str, svc: MediaService = Depends(media_service)):
    return svc.pose(source_id)


@router.get("/sources/{source_id}/lidar")
def lidar(source_id: str, svc: MediaService = Depends(media_service)):
    data = svc.lidar(source_id)
    if data is None:
        return Response(status_code=204)
    return data


@router.get("/sources/{source_id}/camera.jpg")
async def camera_jpeg(
    source_id: str,
    view: str = Query("annotated"),
    bridge: BridgeClient = Depends(bridge_dep),
):
    # Async so rapid UI polls do not exhaust the sync threadpool.
    data = await bridge.camera_jpeg_async(view)
    if not data:
        return Response(status_code=503, content=b"no camera frame yet")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "Connection": "close"},
    )


@router.get("/sources/{source_id}/rviz.jpg")
async def rviz_jpeg(
    source_id: str,
    bridge: BridgeClient = Depends(bridge_dep),
):
    data = await bridge.rviz_jpeg_async()
    if not data:
        return Response(status_code=503, content=b"no rviz frame yet")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "Connection": "close"},
    )
