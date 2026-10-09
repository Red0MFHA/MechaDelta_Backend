from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import settings_dep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(settings_dep)) -> dict:
    return {
        "ok": True,
        "service": "mechadelta-backend",
        "workspace": "operations",
        "database": "sqlite" if settings.force_sqlite else "postgres",
        "runsRoot": str(settings.mechadelta_runs_root),
    }
