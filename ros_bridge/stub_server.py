"""Localhost bridge stub so Operations tasks/media work without ROS."""

from __future__ import annotations

import math
import time
from io import BytesIO

from fastapi import FastAPI, Query
from fastapi.responses import Response
import uvicorn

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

app = FastAPI(title="MechaDelta ROS bridge stub")
STATE = {
    "x": 2.65,
    "y": 1.4,
    "yaw": 1.32,
    "goal": None,
    "mode": "stub",
}


@app.get("/health")
def health():
    return {"ok": True, "mode": "stub", "ros": False}


@app.get("/snapshot")
def snapshot():
    ranges = [2.5 + 0.3 * math.sin(i / 4 + time.time()) for i in range(72)]
    return {
        "pose": {
            "x": STATE["x"],
            "y": STATE["y"],
            "yaw": STATE["yaw"],
            "frameId": "map",
            "observedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "lidar": {
            "sourceId": "stub",
            "frameId": "base_link",
            "observedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "angleMin": -math.pi,
            "angleIncrement": (2 * math.pi) / 72,
            "rangeMax": 10.0,
            "ranges": ranges,
        },
        "connectionState": "online",
    }


@app.post("/jog")
def jog(payload: dict):
    direction = payload.get("direction", "forward")
    step = 0.15
    if direction == "forward":
        STATE["x"] += step * math.cos(STATE["yaw"])
        STATE["y"] += step * math.sin(STATE["yaw"])
    elif direction == "back":
        STATE["x"] -= step * math.cos(STATE["yaw"])
        STATE["y"] -= step * math.sin(STATE["yaw"])
    elif direction == "turn_left":
        STATE["yaw"] += 0.25
    elif direction == "turn_right":
        STATE["yaw"] -= 0.25
    return {"ok": True, "pose": snapshot()["pose"]}


@app.post("/cmd_vel")
def cmd_vel(payload: dict):
    linear_x = float(payload.get("linearX") or 0)
    angular_z = float(payload.get("angularZ") or 0)
    dt = 0.1
    STATE["yaw"] += angular_z * dt
    STATE["x"] += linear_x * math.cos(STATE["yaw"]) * dt
    STATE["y"] += linear_x * math.sin(STATE["yaw"]) * dt
    return {"ok": True, "pose": snapshot()["pose"]}


@app.post("/navigate")
def navigate(payload: dict):
    STATE["x"] = float(payload["x"])
    STATE["y"] = float(payload["y"])
    STATE["yaw"] = float(payload.get("yaw") or 0)
    STATE["goal"] = payload
    return {"ok": True, "accepted": True, "pose": snapshot()["pose"]}


@app.post("/cancel")
def cancel():
    STATE["goal"] = None
    return {"ok": True, "cancelled": True}


@app.get("/camera.jpg")
def camera(view: str = Query("annotated")):
    if Image is None:
        return Response(status_code=503)
    img = Image.new("RGB", (640, 360), (24, 28, 36) if view == "raw" else (18, 40, 32))
    draw = ImageDraw.Draw(img)
    label = "RAW /camera/color/image_raw" if view == "raw" else "YOLO /perception/image_annotated"
    draw.rectangle((180, 120, 280, 220), outline=(240, 180, 40), width=3)
    draw.text((20, 20), label, fill=(230, 230, 230))
    draw.text((20, 50), f"pose=({STATE['x']:.2f},{STATE['y']:.2f})", fill=(180, 200, 220))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
