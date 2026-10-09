from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.errors import AppError


class RunResolver:
    def __init__(self, settings: Settings):
        self.root = Path(settings.mechadelta_runs_root).expanduser().resolve()

    def resolve(self, run_id: str | None) -> Path:
        if not run_id:
            raise AppError("unavailable", "This source has no active run.", status_code=503)
        # Support runs/latest symlink and explicit folder names.
        if run_id == "latest":
            latest = self.root / "latest"
            if latest.exists():
                return latest.resolve()
        path = self.root / run_id
        if not path.exists():
            raise AppError("not_found", f"Run folder {run_id} was not found.", status_code=404)
        return path
