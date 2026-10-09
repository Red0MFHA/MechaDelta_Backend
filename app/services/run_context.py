from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.infrastructure.run_store.memory_reader import MemoryReader
from app.infrastructure.run_store.run_resolver import RunResolver
from app.repositories.source_repository import SourceRepository


class RunContext:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.sources = SourceRepository(db)
        self.resolver = RunResolver(settings)

    def source(self, source_id: str):
        row = self.sources.get(source_id)
        if not row:
            raise AppError("not_found", f"Source {source_id} was not found.", status_code=404)
        return row

    def reader(self, source_id: str) -> tuple[object, str, MemoryReader]:
        row = self.source(source_id)
        run_id = row.active_run_id or self.settings.default_run_id
        path = self.resolver.resolve(run_id)
        return row, run_id, MemoryReader(path)
