from __future__ import annotations

"""Map simulation SQLite rows + labels into UI contract dicts."""


from datetime import datetime, timezone

from app.infrastructure.timeutil import from_sim_seconds, iso

PATROL_BASE = datetime(2026, 10, 8, 10, 20, 0, tzinfo=timezone.utc)

DEFAULT_CAPABILITIES = {
    "video": True,
    "recordedMedia": True,
    "detections": True,
    "objectTracking": True,
    "pose": True,
    "map": True,
    "lidar": True,
    "driveControl": True,
    "navigation": True,
    "telemetry": True,
}

LAB_MAP = {
    "sourceId": "",
    "frameId": "map",
    "widthMeters": 11.0,
    "heightMeters": 5.0,
    "regions": [
        {"id": "room-a", "label": "Room A", "x": 0, "y": 0, "width": 6, "height": 5, "kind": "room"},
        {"id": "room-b", "label": "Room B", "x": 6, "y": 0, "width": 5, "height": 5, "kind": "room"},
        {
            "id": "table-a",
            "label": "Table-A",
            "x": 2.1,
            "y": 2.2,
            "width": 1.1,
            "height": 0.6,
            "kind": "furniture",
        },
        {
            "id": "table-b",
            "label": "Table-B",
            "x": 8.3,
            "y": 2.2,
            "width": 1.1,
            "height": 0.6,
            "kind": "furniture",
        },
    ],
    "waypoints": [
        {"id": "wp-dock", "label": "Dock", "x": 0.8, "y": 0.8, "yaw": 0},
        {"id": "wp-table-a", "label": "Table-A", "x": 2.65, "y": 1.4, "yaw": 1.32},
        {"id": "wp-table-b", "label": "Table-B", "x": 8.85, "y": 1.4, "yaw": 1.57},
    ],
    "updatedAt": iso(),
}


def t_iso(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    return from_sim_seconds(PATROL_BASE, float(seconds))


def ui_object_id(run_id: str, system_id: str) -> str:
    """Stable UI id without ':' so Next.js dynamic routes stay happy."""
    slug = system_id.lower().replace("_", "-")
    return f"{run_id}-{slug}"


def system_id_from_ui(object_id: str, run_id: str | None = None) -> str:
    if run_id and object_id.startswith(f"{run_id}-"):
        rest = object_id[len(run_id) + 1 :]
        return rest.upper()
    if ":" in object_id:
        return object_id.split(":", 1)[1]
    # bare CUP-001 or cup-001
    return object_id.upper()


def object_track(
    source_id: str,
    run_id: str,
    identity: dict,
    state: dict | None,
    transitions: list[dict],
    observations: list[dict],
    label: dict | None,
) -> dict:
    oid = identity["id"]
    uid = ui_object_id(run_id, oid)
    obj_transitions = [tr for tr in transitions if tr["object_id"] == oid]
    obj_obs = [o for o in observations if o["object_id"] == oid]
    last_known = None
    if state:
        last_known = {
            "support": state["support"],
            "x": None,
            "y": None,
            "frameId": "map",
            "observedAt": t_iso(state["last_seen"]),
            "confidence": None,
            "stateVersion": int(state.get("version") or 1),
        }
        # Prefer last observation xyz at current support
        for o in obj_obs:
            if o.get("support") == state["support"] and o.get("x") is not None:
                last_known["x"] = o["x"]
                last_known["y"] = o["y"]
                break

    status = "confirmed"
    score = None
    if obj_transitions:
        score = float(obj_transitions[-1].get("association_score") or 0)
    elif obj_obs:
        score = float(obj_obs[0].get("score") or 0)

    return {
        "id": uid,
        "systemId": oid,
        "sourceId": source_id,
        "runId": run_id,
        "label": "cup",
        "slug": (label or {}).get("slug"),
        "photoUrl": (label or {}).get("photo_url"),
        "identityStatus": status,
        "associationScore": score,
        "firstSeenAt": t_iso(state["first_seen"]) if state else t_iso(identity.get("created")),
        "lastSeenAt": t_iso(state["last_seen"]) if state else t_iso(identity.get("last_seen")),
        "sightingCount": len(obj_obs),
        "lastKnownLocation": last_known,
        "eventIds": [f"evt-obs-{o['id']}" for o in obj_obs[:20]],
        "transitionIds": [f"tr-{t['id']}" for t in obj_transitions],
        "intervalIds": [f"iv-{oid}-1"],
    }


def transition_dto(run_id: str, row: dict) -> dict:
    return {
        "id": f"tr-{row['id']}",
        "objectId": ui_object_id(run_id, row["object_id"]),
        "runId": run_id,
        "previousSupport": row["previous_support"],
        "newSupport": row["new_support"],
        "tLower": t_iso(row["t_lower"]),
        "tUpper": t_iso(row["t_upper"]),
        "confirmedAt": t_iso(row["confirmed_at"]),
        "associationScore": float(row.get("association_score") or 0),
        "cause": row.get("cause") or "unknown",
        "evidenceId": None,
    }


def intervals_for(run_id: str, object_id: str, state: dict | None, transitions: list[dict]) -> list[dict]:
    out: list[dict] = []
    system_id = system_id_from_ui(object_id, run_id)
    obj_tr = [t for t in transitions if t["object_id"] == system_id]
    if state and not obj_tr:
        out.append(
            {
                "id": f"iv-{system_id}-1",
                "objectId": object_id,
                "support": state["support"],
                "firstSeenAt": t_iso(state["first_seen"]),
                "lastSeenAt": t_iso(state["last_seen"]),
                "sightingCount": 1,
                "open": True,
            }
        )
        return out
    if state and obj_tr:
        first = obj_tr[0]
        out.append(
            {
                "id": f"iv-{system_id}-prev",
                "objectId": object_id,
                "support": first["previous_support"],
                "firstSeenAt": t_iso(first["t_lower"]),
                "lastSeenAt": t_iso(first["t_lower"]),
                "sightingCount": 1,
                "open": False,
            }
        )
        out.append(
            {
                "id": f"iv-{system_id}-curr",
                "objectId": object_id,
                "support": state["support"],
                "firstSeenAt": t_iso(state["first_seen"]),
                "lastSeenAt": t_iso(state["last_seen"]),
                "sightingCount": 1,
                "open": True,
            }
        )
    return out


def events_from_run(source_id: str, run_id: str, identities, states, transitions, observations) -> list[dict]:
    events: list[dict] = []
    for ident in identities:
        events.append(
            {
                "id": f"evt-id-{ident['id']}",
                "sourceId": source_id,
                "runId": run_id,
                "type": "identity_registered",
                "observedAt": t_iso(ident.get("created")) or iso(),
                "origin": "simulated",
                "objectIds": [ui_object_id(run_id, ident["id"])],
                "detectionIds": [],
                "summary": f"Identity {ident['id']} registered.",
            }
        )
    for tr in transitions:
        events.append(
            {
                "id": f"evt-tr-{tr['id']}",
                "sourceId": source_id,
                "runId": run_id,
                "type": "transition_confirmed",
                "observedAt": t_iso(tr["confirmed_at"]) or iso(),
                "origin": "simulated",
                "objectIds": [ui_object_id(run_id, tr["object_id"])],
                "detectionIds": [],
                "support": tr["new_support"],
                "confidence": float(tr.get("association_score") or 0),
                "summary": f"{tr['object_id']}: {tr['previous_support']} → {tr['new_support']}",
            }
        )
    for obs in observations[:80]:
        events.append(
            {
                "id": f"evt-obs-{obs['id']}",
                "sourceId": source_id,
                "runId": run_id,
                "type": "detection",
                "observedAt": t_iso(obs["captured"]) or iso(),
                "origin": "simulated",
                "objectIds": [ui_object_id(run_id, obs["object_id"])],
                "detectionIds": [f"det-{obs['id']}"],
                "support": obs.get("support"),
                "confidence": float(obs.get("score") or 0),
                "summary": f"Detection of {obs['object_id']} at {obs.get('support') or 'unknown'}",
            }
        )
    events.sort(key=lambda e: e["observedAt"])
    return events
