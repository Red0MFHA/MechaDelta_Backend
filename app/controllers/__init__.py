from __future__ import annotations

from fastapi import APIRouter

from app.controllers import (
    evidence_controller,
    events_controller,
    health_controller,
    ingest_controller,
    livekit_controller,
    media_controller,
    memory_controller,
    objects_controller,
    overview_controller,
    questions_controller,
    runtime_controller,
    sources_controller,
    tasks_controller,
)


def build_api_router() -> APIRouter:
    api = APIRouter()
    api.include_router(health_controller.router)
    api.include_router(sources_controller.router)
    api.include_router(overview_controller.router)
    api.include_router(media_controller.router)
    api.include_router(events_controller.router)
    api.include_router(objects_controller.router)
    api.include_router(questions_controller.router)
    api.include_router(evidence_controller.router)
    api.include_router(memory_controller.router)
    api.include_router(runtime_controller.router)
    api.include_router(tasks_controller.router)
    api.include_router(ingest_controller.router)
    api.include_router(livekit_controller.router)
    return api
