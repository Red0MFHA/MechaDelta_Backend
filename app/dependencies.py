from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.bridge.client import BridgeClient
from app.infrastructure.database import get_db
from app.services.evidence_service import EvidenceService
from app.services.event_service import EventService
from app.services.ingest_service import IngestService
from app.services.media_service import MediaService
from app.services.memory_service import MemoryService
from app.services.object_service import ObjectService
from app.services.overview_service import OverviewService
from app.services.question_service import QuestionService
from app.services.runtime_service import RuntimeService
from app.services.source_service import SourceService
from app.services.task_service import TaskService


def settings_dep() -> Settings:
    return get_settings()


def bridge_dep(settings: Settings = Depends(settings_dep)) -> BridgeClient:
    return BridgeClient(settings.bridge_url)


def source_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    bridge: BridgeClient = Depends(bridge_dep),
) -> SourceService:
    return SourceService(db, settings, bridge)


def object_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> ObjectService:
    return ObjectService(db, settings)


def event_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> EventService:
    return EventService(db, settings)


def question_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> QuestionService:
    return QuestionService(db, settings)


def evidence_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> EvidenceService:
    return EvidenceService(db, settings)


def memory_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> MemoryService:
    return MemoryService(db, settings)


def runtime_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> RuntimeService:
    return RuntimeService(db, settings)


def media_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    bridge: BridgeClient = Depends(bridge_dep),
) -> MediaService:
    return MediaService(db, settings, bridge)


def task_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    bridge: BridgeClient = Depends(bridge_dep),
) -> TaskService:
    return TaskService(db, settings, bridge)


def overview_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    bridge: BridgeClient = Depends(bridge_dep),
) -> OverviewService:
    return OverviewService(db, settings, bridge)


def ingest_service(db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)) -> IngestService:
    return IngestService(db, settings)
