from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import evidence_service
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{evidence_id}")
def get_evidence(evidence_id: str, svc: EvidenceService = Depends(evidence_service)):
    return svc.get(evidence_id)


@router.post("/from-question/{question_id}")
def from_question(question_id: str, svc: EvidenceService = Depends(evidence_service)):
    return svc.create_from_question(question_id)


@router.post("/from-object/{object_id:path}")
def from_object(object_id: str, svc: EvidenceService = Depends(evidence_service)):
    return svc.create_from_object(object_id)
