from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from livekit.api import AccessToken, VideoGrants

from app.config import Settings
from app.dependencies import settings_dep
from app.errors import AppError

router = APIRouter(prefix="/livekit", tags=["livekit"])


@router.get("/token")
def viewer_token(
    sourceId: str = Query(...),
    identity: str = Query("ui-viewer"),
    settings: Settings = Depends(settings_dep),
) -> dict:
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise AppError("unavailable", "LiveKit is not configured.", status_code=503)
    room = f"{settings.livekit_room_prefix}-{sourceId}"
    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room,
                can_subscribe=True,
                can_publish=False,
            )
        )
        .to_jwt()
    )
    return {
        "url": settings.livekit_url,
        "token": token,
        "room": room,
        "tracks": {
            "raw": "camera_raw",
            "annotated": "camera_annotated",
            "map": "rviz_map",
        },
    }
