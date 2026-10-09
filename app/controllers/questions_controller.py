from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import question_service
from app.services.question_service import QuestionService

router = APIRouter(tags=["questions"])


@router.post("/questions")
def ask(payload: dict, svc: QuestionService = Depends(question_service)):
    return svc.ask(payload)


@router.get("/questions")
def list_questions(sourceId: str = Query(...), svc: QuestionService = Depends(question_service)):
    return svc.list(sourceId)


@router.get("/questions/{question_id}")
def get_question(question_id: str, svc: QuestionService = Depends(question_service)):
    return svc.get(question_id)
