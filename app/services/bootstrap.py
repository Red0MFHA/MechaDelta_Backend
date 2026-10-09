from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.timeutil import utcnow
from app.models.source import SourceRow
from app.repositories.source_repository import SourceRepository
from app.services.mappers import DEFAULT_CAPABILITIES


def ensure_default_source(db: Session, settings: Settings) -> None:
    repo = SourceRepository(db)
    if repo.get(settings.default_source_id):
        return
    now = utcnow()
    row = SourceRow(
        id=settings.default_source_id,
        name="Gazebo demo robot",
        kind="ros2_simulation",
        connection_state="online",
        origin="simulated",
        description="Default simulation source bound to the fixture or latest MechaDelta run.",
        config_json=json.dumps(
            [
                {"key": "runsRoot", "label": "Runs root", "value": str(settings.mechadelta_runs_root), "secret": False},
                {"key": "bridgeUrl", "label": "Bridge URL", "value": settings.bridge_url, "secret": False},
            ]
        ),
        capabilities_json=json.dumps(DEFAULT_CAPABILITIES),
        active_run_id=settings.default_run_id,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    repo.add(row)
