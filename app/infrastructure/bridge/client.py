from __future__ import annotations

from typing import Any

import httpx

from app.errors import AppError


class BridgeClient:
    def __init__(self, base_url: str, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.request(method, f"{self.base_url}{path}", json=json)
        except httpx.HTTPError as exc:
            raise AppError(
                "unavailable",
                f"ROS bridge at {self.base_url} is unreachable.",
                status_code=503,
                details={"reason": str(exc)},
            ) from exc
        if res.status_code >= 400:
            raise AppError(
                "unavailable",
                res.json().get("message", res.text) if res.headers.get("content-type", "").startswith("application/json") else res.text,
                status_code=503,
            )
        if res.status_code == 204 or not res.content:
            return None
        return res.json()

    def health(self) -> dict:
        try:
            return self._request("GET", "/health")
        except AppError:
            return {"ok": False, "mode": "down"}

    def snapshot(self) -> dict:
        return self._request("GET", "/snapshot")

    def jog(self, direction: str) -> dict:
        return self._request("POST", "/jog", {"direction": direction})

    def cmd_vel(self, linear_x: float, angular_z: float, hold_s: float = 0.45) -> dict:
        return self._request(
            "POST",
            "/cmd_vel",
            {"linearX": linear_x, "angularZ": angular_z, "holdS": hold_s},
        )

    def navigate(self, x: float, y: float, yaw: float = 0.0, frame_id: str = "map") -> dict:
        return self._request(
            "POST",
            "/navigate",
            {"x": x, "y": y, "yaw": yaw, "frame_id": frame_id},
        )

    def cancel(self) -> dict:
        return self._request("POST", "/cancel")

    def camera_jpeg(self, view: str = "annotated") -> bytes | None:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(f"{self.base_url}/camera.jpg", params={"view": view})
            if res.status_code != 200:
                return None
            return res.content
        except httpx.HTTPError:
            return None

    async def camera_jpeg_async(self, view: str = "annotated") -> bytes | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if view in ("rviz", "map"):
                    res = await client.get(f"{self.base_url}/rviz.jpg")
                else:
                    res = await client.get(f"{self.base_url}/camera.jpg", params={"view": view})
            if res.status_code != 200:
                return None
            return res.content
        except httpx.HTTPError:
            return None

    async def rviz_jpeg_async(self) -> bytes | None:
        return await self.camera_jpeg_async("rviz")
