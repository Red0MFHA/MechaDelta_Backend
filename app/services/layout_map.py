"""Build the Operations schematic map from the live MechaDelta layout.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.infrastructure.timeutil import iso

_LAYOUT_CANDIDATES = (
    Path.home() / "mechadelta_ws/install/mechadelta_poc/share/mechadelta_poc/config/layout.yaml",
    Path.home() / "FYP/MechaDelta/src/mechadelta_poc/config/layout.yaml",
    Path.home() / "FYP/MechaDelta/install/mechadelta_poc/share/mechadelta_poc/config/layout.yaml",
)


@lru_cache(maxsize=1)
def _load_layout() -> dict:
    for path in _LAYOUT_CANDIDATES:
        if path.is_file():
            return yaml.safe_load(path.read_text()) or {}
    return {}


def schematic_map(source_id: str) -> dict:
    """Regions/waypoints from the Gazebo layout — not the canned LAB_MAP fixture."""
    layout = _load_layout()
    rooms = layout.get("rooms") or []
    tables = layout.get("tables") or []
    robot = layout.get("robot") or {}

    xs: list[float] = []
    ys: list[float] = []
    regions: list[dict] = []
    for room in rooms:
        bounds = room.get("bounds") or [0, 1, 0, 1]
        x0, x1, y0, y1 = (float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))
        xs.extend([x0, x1])
        ys.extend([y0, y1])
        regions.append(
            {
                "id": str(room.get("id", "room")).lower().replace("_", "-"),
                "label": str(room.get("id", "Room")),
                "x": x0,
                "y": y0,
                "width": max(0.1, x1 - x0),
                "height": max(0.1, y1 - y0),
                "kind": "room",
            }
        )
    for table in tables:
        tw = float(table.get("width", 1.0))
        td = float(table.get("depth", 1.0))
        tx = float(table.get("x", 0.0)) - tw / 2
        ty = float(table.get("y", 0.0)) - td / 2
        xs.extend([tx, tx + tw])
        ys.extend([ty, ty + td])
        regions.append(
            {
                "id": str(table.get("id", "table")).lower().replace("_", "-"),
                "label": str(table.get("id", "Table")),
                "x": tx,
                "y": ty,
                "width": tw,
                "height": td,
                "kind": "furniture",
            }
        )

    width = max(xs) - min(xs) if xs else 12.0
    height = max(ys) - min(ys) if ys else 6.0
    waypoints = [
        {
            "id": "wp-spawn",
            "label": "Spawn",
            "x": float(robot.get("x", 0.0)),
            "y": float(robot.get("y", 0.0)),
            "yaw": float(robot.get("yaw", 0.0)),
        }
    ]
    for table in tables:
        waypoints.append(
            {
                "id": f"wp-{str(table.get('id', 'table')).lower().replace('_', '-')}",
                "label": str(table.get("id", "Table")),
                "x": float(table.get("x", 0.0)),
                "y": float(table.get("y", 0.0)) - float(table.get("depth", 1.0)) / 2 - 0.35,
                "yaw": 1.5708,
            }
        )

    return {
        "sourceId": source_id,
        "frameId": "map",
        "widthMeters": float(width),
        "heightMeters": float(height),
        "regions": regions,
        "waypoints": waypoints,
        "updatedAt": iso(),
        "origin": "layout.yaml",
    }


def table_approach(support: str) -> tuple[float, float] | None:
    """Approach pose in front of a named table from layout.yaml."""
    layout = _load_layout()
    for table in layout.get("tables") or []:
        if str(table.get("id")) == support:
            return (
                float(table.get("x", 0.0)),
                float(table.get("y", 0.0)) - float(table.get("depth", 1.0)) / 2 - 0.35,
            )
    return None
