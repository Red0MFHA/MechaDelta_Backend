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
    return svc.lidar(source_id)


@router.get("/sources/{source_id}/camera.jpg")
def camera_jpeg(
    source_id: str,
    view: str = Query("annotated"),
    bridge: BridgeClient = Depends(bridge_dep),
):
    data = bridge.camera_jpeg(view)
    if not data:
        # 1x1 pixel jpeg placeholder
        import base64

        data = base64.b64decode(
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAGcP//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAQUCf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQMBAT8Bf//EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQIBAT8Bf//Z"
        )
    return Response(content=data, media_type="image/jpeg")
