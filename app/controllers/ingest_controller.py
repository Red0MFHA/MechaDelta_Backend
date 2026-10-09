from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import ingest_service
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("")
def list_jobs(sourceId: str | None = Query(None), svc: IngestService = Depends(ingest_service)):
    return svc.list(sourceId)


@router.get("/{job_id}")
def get_job(job_id: str, svc: IngestService = Depends(ingest_service)):
    return svc.get(job_id)


@router.post("")
def create_job(payload: dict, svc: IngestService = Depends(ingest_service)):
    return svc.create(payload)


@router.post("/{job_id}/retry")
def retry_job(job_id: str, svc: IngestService = Depends(ingest_service)):
    return svc.retry(job_id)
