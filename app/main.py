from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.controllers import build_api_router
from app.errors import register_exception_handlers
from app.infrastructure.database import SessionLocal, init_db
from app.services.bootstrap import ensure_default_source


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MechaDelta Backend", version="0.1.0")
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_api_router())

    runs_root = Path(settings.mechadelta_runs_root).expanduser().resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    app.mount("/files/runs", StaticFiles(directory=str(runs_root)), name="run_files")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        db = SessionLocal()
        try:
            ensure_default_source(db, settings)
        finally:
            db.close()

    return app


app = create_app()
