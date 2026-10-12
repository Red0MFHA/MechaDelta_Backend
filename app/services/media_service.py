from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.bridge.client import BridgeClient
from app.infrastructure.timeutil import iso
from app.services.layout_map import schematic_map
from app.services.mappers import t_iso, ui_object_id
from app.services.run_context import RunContext


class MediaService:
    def __init__(self, db: Session, settings: Settings, bridge: BridgeClient):
        self.ctx = RunContext(db, settings)
        self.settings = settings
        self.bridge = bridge

    def get(self, source_id: str) -> dict | None:
        _, run_id, reader = self.ctx.reader(source_id)
        run_dir = reader.run_dir
        for candidate in (
            run_dir / "review.mp4",
            run_dir / "camera.mp4",
            run_dir / "demonstration" / "full.mp4",
            run_dir / "review_playback.mp4",
            run_dir / "patrol.mp4",
        ):
            if candidate.exists():
                return {
                    "id": f"media-{run_id}",
                    "sourceId": source_id,
                    "origin": "recorded",
                    "url": f"{self.settings.public_api_base}/files/runs/{run_id}/{candidate.relative_to(run_dir).as_posix()}",
                    "title": f"Run {run_id}",
                    "durationMs": 0,
                    "recordedAt": iso(),
                }
        health = self.bridge.health()
        if health.get("ok"):
            return {
                "id": f"media-{run_id}-live",
                "sourceId": source_id,
                "origin": "live",
                "url": f"{self.settings.public_api_base}/sources/{source_id}/camera.jpg?view=annotated",
                "title": "Live annotated camera",
                "durationMs": 0,
                "frameRate": 2,
            }
        return None

    def detections(self, source_id: str) -> list[dict]:
        _, run_id, reader = self.ctx.reader(source_id)
        out = []
        for obs in reader.observations(limit=40):
            out.append(
                {
                    "id": f"det-{obs['id']}",
                    "eventId": f"evt-obs-{obs['id']}",
                    "sourceId": source_id,
                    "label": "cup",
                    "confidence": float(obs.get("score") or 0),
                    "observedAt": t_iso(obs["captured"]),
                    "objectId": ui_object_id(run_id, obs["object_id"]),
                }
            )
        return out

    def map(self, source_id: str) -> dict:
        return schematic_map(source_id)

    def pose(self, source_id: str) -> list[dict]:
        snap = self._safe_snapshot()
        if snap and snap.get("pose"):
            pose = dict(snap["pose"])
            pose["sourceId"] = source_id
            return [pose]
        return []

    def lidar(self, source_id: str) -> dict | None:
        snap = self._safe_snapshot()
        if snap and snap.get("lidar"):
            lidar = dict(snap["lidar"])
            lidar["sourceId"] = source_id
            return lidar
        return None

    def _safe_snapshot(self) -> dict | None:
        try:
            return self.bridge.snapshot()
        except Exception:  # noqa: BLE001
            return None
