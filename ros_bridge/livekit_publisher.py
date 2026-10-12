"""Publish camera / YOLO / map-lidar frames into a LiveKit room.

Works with the HTTP bridge stub (or live_node) on BRIDGE_URL, so you can
demo without Gazebo. When ROS live_node is up, the same JPEGs become real.

  LIVEKIT_URL=ws://127.0.0.1:7880 \\
  LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret \\
  BRIDGE_URL=http://127.0.0.1:8765 \\
  SOURCE_ID=src-sim-1 \\
  .venv/bin/python -m ros_bridge.livekit_publisher
"""

from __future__ import annotations

import asyncio
import math
import os
import time
from io import BytesIO

import httpx
import numpy as np
from livekit import api, rtc
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 640, 360
FPS = 10


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def jpeg_to_rgba(data: bytes, size: tuple[int, int] = (WIDTH, HEIGHT)) -> np.ndarray:
    img = Image.open(BytesIO(data)).convert("RGBA").resize(size, Image.BILINEAR)
    return np.asarray(img)


def draw_placeholder(title: str, subtitle: str, color: tuple[int, int, int]) -> np.ndarray:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (*color, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((16, 16, WIDTH - 16, HEIGHT - 16), outline=(240, 240, 240, 255), width=2)
    draw.text((28, 28), title, fill=(245, 245, 245, 255))
    draw.text((28, 60), subtitle, fill=(200, 210, 220, 255))
    draw.text((28, HEIGHT - 40), time.strftime("%H:%M:%S"), fill=(180, 190, 200, 255))
    return np.asarray(img)


def draw_map_frame(snapshot: dict | None) -> np.ndarray:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (12, 16, 22, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(60, 80, 100, 255))
    draw.text((16, 12), "RViz / LiDAR map (LiveKit)", fill=(230, 230, 230, 255))

    # Room outline in map meters → pixels (fixture lab ~11x5m)
    scale = 48
    ox, oy = 40, HEIGHT - 40

    def px(x: float, y: float) -> tuple[int, int]:
        return int(ox + x * scale), int(oy - y * scale)

    # tables
    for label, x, y, w, h in (
        ("Table-A", 2.1, 2.2, 1.1, 0.6),
        ("Table-B", 8.3, 2.2, 1.1, 0.6),
    ):
        x0, y0 = px(x, y)
        x1, y1 = px(x + w, y + h)
        draw.rectangle((x0, y1, x1, y0), outline=(120, 160, 200, 255), width=2)
        draw.text((x0, y1 - 14), label, fill=(160, 180, 200, 255))

    pose = (snapshot or {}).get("pose") or {}
    lidar = (snapshot or {}).get("lidar") or {}
    if pose:
        rx, ry = px(float(pose.get("x", 0)), float(pose.get("y", 0)))
        yaw = float(pose.get("yaw", 0))
        draw.ellipse((rx - 6, ry - 6, rx + 6, ry + 6), fill=(80, 220, 120, 255))
        draw.line((rx, ry, rx + int(18 * math.cos(yaw)), ry - int(18 * math.sin(yaw))), fill=(80, 220, 120, 255), width=2)
        # lidar rays
        ranges = lidar.get("ranges") or []
        amin = float(lidar.get("angleMin", -math.pi))
        ainc = float(lidar.get("angleIncrement", (2 * math.pi) / max(len(ranges), 1)))
        for i, r in enumerate(ranges):
            if r is None or r <= 0 or r > 8:
                continue
            a = amin + i * ainc + yaw
            x2 = float(pose.get("x", 0)) + float(r) * math.cos(a)
            y2 = float(pose.get("y", 0)) + float(r) * math.sin(a)
            draw.line((rx, ry, *px(x2, y2)), fill=(40, 90, 140, 180), width=1)
    else:
        draw.text((16, 48), "Waiting for bridge pose/lidar…", fill=(200, 160, 80, 255))

    return np.asarray(img)


async def fetch_jpeg(client: httpx.AsyncClient, bridge: str, view: str) -> bytes | None:
    try:
        res = await client.get(f"{bridge}/camera.jpg", params={"view": view}, timeout=1.5)
        if res.status_code == 200 and res.content:
            return res.content
    except Exception:
        return None
    return None


async def fetch_snapshot(client: httpx.AsyncClient, bridge: str) -> dict | None:
    try:
        res = await client.get(f"{bridge}/snapshot", timeout=1.5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        return None
    return None


def push(source: rtc.VideoSource, rgba: np.ndarray) -> None:
    if rgba.dtype != np.uint8:
        rgba = rgba.astype(np.uint8)
    if rgba.shape[2] == 3:
        # pad alpha
        a = np.full((*rgba.shape[:2], 1), 255, dtype=np.uint8)
        rgba = np.concatenate([rgba, a], axis=2)
    frame = rtc.VideoFrame(WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, rgba.tobytes())
    source.capture_frame(frame)


async def publish_loop(room: rtc.Room, bridge: str) -> None:
    raw_src = rtc.VideoSource(WIDTH, HEIGHT)
    ann_src = rtc.VideoSource(WIDTH, HEIGHT)
    map_src = rtc.VideoSource(WIDTH, HEIGHT)

    for name, src in (
        ("camera_raw", raw_src),
        ("camera_annotated", ann_src),
        ("rviz_map", map_src),
    ):
        track = rtc.LocalVideoTrack.create_video_track(name, src)
        await room.local_participant.publish_track(
            track,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA),
        )
        print(f"published track {name}")

    period = 1.0 / FPS
    async with httpx.AsyncClient() as client:
        while True:
            t0 = time.perf_counter()
            raw = await fetch_jpeg(client, bridge, "raw")
            ann = await fetch_jpeg(client, bridge, "annotated")
            snap = await fetch_snapshot(client, bridge)

            push(
                raw_src,
                jpeg_to_rgba(raw) if raw else draw_placeholder("RAW camera", "bridge offline", (30, 40, 55)),
            )
            push(
                ann_src,
                jpeg_to_rgba(ann)
                if ann
                else draw_placeholder("YOLO annotated", "bridge offline", (20, 55, 40)),
            )
            push(map_src, draw_map_frame(snap))

            elapsed = time.perf_counter() - t0
            await asyncio.sleep(max(0.01, period - elapsed))


async def main() -> None:
    url = env("LIVEKIT_URL", "ws://127.0.0.1:7880")
    key = env("LIVEKIT_API_KEY", "devkey")
    secret = env("LIVEKIT_API_SECRET", "secret")
    source_id = env("SOURCE_ID", "src-sim-1")
    bridge = env("BRIDGE_URL", "http://127.0.0.1:8765").rstrip("/")
    room_name = f"{env('LIVEKIT_ROOM_PREFIX', 'mechadelta')}-{source_id}"

    token = (
        api.AccessToken(key, secret)
        .with_identity("mechadelta-publisher")
        .with_name("MechaDelta Publisher")
        .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=False))
        .to_jwt()
    )

    room = rtc.Room()
    print(f"connecting to {url} room={room_name}")
    await room.connect(url, token)
    print("connected — publishing tracks")
    try:
        await publish_loop(room, bridge)
    finally:
        await room.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
