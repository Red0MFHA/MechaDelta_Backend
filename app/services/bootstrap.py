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
    existing = repo.get(settings.default_source_id)
    now = utcnow()
    if existing:
        # Keep the seeded source aimed at the live perception symlink, not fixtures.
        changed = False
        if existing.active_run_id != "latest":
            existing.active_run_id = "latest"
            changed = True
        if existing.connection_state != "online":
            existing.connection_state = "online"
            changed = True
        if changed:
            existing.updated_at = now
            existing.last_seen_at = now
            db.add(existing)
            db.commit()
        return
    row = SourceRow(
        id=settings.default_source_id,
        name="Gazebo demo robot",
        kind="ros2_simulation",
        connection_state="online",
        origin="simulated",
        description="Gazebo + perception source; active run follows mechadelta_ws/runs/latest.",
        config_json=json.dumps(
            [
                {"key": "runsRoot", "label": "Runs root", "value": str(settings.mechadelta_runs_root), "secret": False},
                {"key": "bridgeUrl", "label": "Bridge URL", "value": settings.bridge_url, "secret": False},
            ]
        ),
        capabilities_json=json.dumps(DEFAULT_CAPABILITIES),
        active_run_id="latest",
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    repo.add(row)
