"""ROS 2 live bridge: camera/pose/lidar + localhost HTTP for the FastAPI backend.

Run inside a sourced ROS + MechaDelta workspace shell:

  source /opt/ros/$ROS_DISTRO/setup.bash
  source ~/mechadelta_ws/install/setup.bash   # or your FYP MechaDelta install
  cd ~/FYP/MechaDelta_Backend
  python -m ros_bridge.live_node
"""

from __future__ import annotations

import math
import threading
import time
from io import BytesIO
from typing import Any

import numpy as np
import rclpy
from cv_bridge import CvBridge
from fastapi import FastAPI, Query
from fastapi.responses import Response
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, LaserScan
import uvicorn

try:
    from nav2_msgs.action import NavigateToPose
    from geometry_msgs.msg import PoseStamped
except ImportError:  # pragma: no cover
    NavigateToPose = None  # type: ignore
    PoseStamped = None  # type: ignore

try:
    from PIL import Image as PilImage
except ImportError:  # pragma: no cover
    PilImage = None  # type: ignore


STATE: dict[str, Any] = {
    "ok": False,
    "mode": "ros",
    "pose": None,
    "lidar": None,
    "raw_jpeg": None,
    "annotated_jpeg": None,
    "rviz_jpeg": None,
    "rviz_jpeg_at": None,
    "last_image_age": None,
    "goal_handle": None,
}


def _bgr_to_jpeg(bgr: np.ndarray, quality: int = 75) -> bytes | None:
    if PilImage is None:
        return None
    rgb = bgr[:, :, ::-1]
    img = PilImage.fromarray(rgb)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


class LiveBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("mechadelta_ui_bridge")
        self.bridge = CvBridge()
        self.cmd = self.create_publisher(Twist, "/cmd_vel_unstamped", 10)
        self._twist = Twist()
        self._cmd_deadline = 0.0
        self.create_timer(0.05, self._publish_held_cmd)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.create_subscription(LaserScan, "/scan", self._on_scan, qos_profile_sensor_data)
        self.create_subscription(
            Image, "/camera/color/image_raw", self._on_raw, qos_profile_sensor_data
        )
        self.create_subscription(
            Image, "/perception/image_annotated", self._on_annotated, qos_profile_sensor_data
        )
        self.nav_client = None
        if NavigateToPose is not None:
            self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        STATE["ok"] = True
        self.get_logger().info("MechaDelta UI bridge listening for camera/odom/scan")

    def _publish_held_cmd(self) -> None:
        """Re-publish the last joystick twist until it expires (DiffDrive needs continuous cmd)."""
        if time.monotonic() > self._cmd_deadline:
            if self._twist.linear.x or self._twist.angular.z:
                self._twist = Twist()
                self.cmd.publish(self._twist)
            return
        self.cmd.publish(self._twist)

    def cmd_vel(self, linear_x: float, angular_z: float, hold_s: float = 0.45) -> dict:
        twist = Twist()
        twist.linear.x = max(-0.25, min(0.25, float(linear_x)))
        twist.angular.z = max(-0.7, min(0.7, float(angular_z)))
        self._twist = twist
        if twist.linear.x == 0.0 and twist.angular.z == 0.0:
            self._cmd_deadline = 0.0
            self.cmd.publish(twist)
        else:
            self._cmd_deadline = time.monotonic() + max(0.1, float(hold_s))
            self.cmd.publish(twist)
        return {"ok": True, "pose": STATE.get("pose")}

    def _on_odom(self, msg: Odometry) -> None:
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        STATE["pose"] = {
            "x": float(msg.pose.pose.position.x),
            "y": float(msg.pose.pose.position.y),
            "yaw": float(yaw),
            "frameId": msg.header.frame_id or "odom",
            "observedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _on_scan(self, msg: LaserScan) -> None:
        step = max(1, len(msg.ranges) // 72)
        ranges = [float(r) if math.isfinite(r) else msg.range_max for r in msg.ranges[::step][:72]]
        STATE["lidar"] = {
            "sourceId": "live",
            "frameId": msg.header.frame_id or "base_link",
            "observedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "angleMin": float(msg.angle_min),
            "angleIncrement": float(msg.angle_increment * step),
            "rangeMax": float(msg.range_max),
            "ranges": ranges,
        }

    def _on_raw(self, msg: Image) -> None:
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            STATE["raw_jpeg"] = _bgr_to_jpeg(bgr)
            STATE["last_image_age"] = time.time()
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f"raw encode failed: {exc}")

    def _on_annotated(self, msg: Image) -> None:
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            STATE["annotated_jpeg"] = _bgr_to_jpeg(bgr)
            STATE["last_image_age"] = time.time()
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f"annotated encode failed: {exc}")

    def jog(self, direction: str) -> dict:
        twist = Twist()
        if direction == "forward":
            twist.linear.x = 0.2
        elif direction == "back":
            twist.linear.x = -0.2
        elif direction == "turn_left":
            twist.angular.z = 0.6
        elif direction == "turn_right":
            twist.angular.z = -0.6
        # look_up / look_down unused on differential base
        # Publish a sustained burst: sim RTF is often <<1, so a single
        # short pulse is barely visible in Gazebo / the UI streams.
        rate_hz = 20.0
        duration_s = 1.5
        period = 1.0 / rate_hz
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            self.cmd.publish(twist)
            time.sleep(period)
        self.cmd.publish(Twist())
        return {"ok": True, "pose": STATE.get("pose")}

    def navigate(self, x: float, y: float, yaw: float = 0.0, frame_id: str = "map") -> dict:
        if self.nav_client is None or PoseStamped is None:
            return {"ok": False, "message": "nav2_msgs not available in this environment"}
        if not self.nav_client.wait_for_server(timeout_sec=2.0):
            return {"ok": False, "message": "NavigateToPose action server not ready"}
        goal = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = frame_id
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation.z = math.sin(yaw / 2)
        pose.pose.orientation.w = math.cos(yaw / 2)
        goal.pose = pose
        future = self.nav_client.send_goal_async(goal)
        # Non-blocking accept; UI task marks succeeded on accept for now
        STATE["goal_handle"] = future
        return {"ok": True, "accepted": True, "pose": STATE.get("pose")}

    def cancel(self) -> dict:
        handle_future = STATE.get("goal_handle")
        if handle_future is not None and handle_future.done():
            handle = handle_future.result()
            if handle is not None:
                handle.cancel_goal_async()
        self.cmd_vel(0.0, 0.0)
        return {"ok": True, "cancelled": True}


def build_http(node: LiveBridgeNode) -> FastAPI:
    app = FastAPI(title="MechaDelta ROS live bridge")

    @app.get("/health")
    def health():
        age = STATE.get("last_image_age")
        fresh = age is not None and (time.time() - age) < 5.0
        return {
            "ok": True,
            "mode": "ros",
            "ros": True,
            "cameraFresh": fresh,
            "hasAnnotated": STATE.get("annotated_jpeg") is not None,
            "hasRaw": STATE.get("raw_jpeg") is not None,
        }

    @app.get("/snapshot")
    def snapshot():
        return {
            "pose": STATE.get("pose"),
            "lidar": STATE.get("lidar"),
            "connectionState": "online" if STATE.get("pose") else "degraded",
        }

    @app.post("/jog")
    def jog(payload: dict):
        return node.jog(payload.get("direction", "forward"))

    @app.post("/cmd_vel")
    def cmd_vel(payload: dict):
        return node.cmd_vel(
            float(payload.get("linearX") or payload.get("linear_x") or 0),
            float(payload.get("angularZ") or payload.get("angular_z") or 0),
            float(payload.get("holdS") or payload.get("hold_s") or 0.45),
        )

    @app.post("/navigate")
    def navigate(payload: dict):
        return node.navigate(
            float(payload["x"]),
            float(payload["y"]),
            float(payload.get("yaw") or 0),
            str(payload.get("frame_id") or "map"),
        )

    @app.post("/cancel")
    def cancel():
        return node.cancel()

    @app.get("/camera.jpg")
    def camera(view: str = Query("annotated")):
        if view in ("rviz", "map"):
            data = STATE.get("rviz_jpeg")
        elif view == "annotated":
            data = STATE.get("annotated_jpeg") or STATE.get("raw_jpeg")
        else:
            data = STATE.get("raw_jpeg")
        if data is None:
            return Response(status_code=503, content=b"no camera frame yet")
        return Response(content=data, media_type="image/jpeg")

    @app.get("/rviz.jpg")
    def rviz():
        data = STATE.get("rviz_jpeg")
        if data is None:
            return Response(status_code=503, content=b"no rviz frame yet")
        return Response(content=data, media_type="image/jpeg")

    return app


def _rviz_loop(period: float = 0.28) -> None:
    """Capture RViz ~3–4 Hz so LiDAR/robot motion looks live in the UI."""
    from ros_bridge.rviz_capture import capture_rviz_jpeg

    misses = 0
    while True:
        try:
            jpeg = capture_rviz_jpeg()
            if jpeg:
                STATE["rviz_jpeg"] = jpeg
                STATE["rviz_jpeg_at"] = time.time()
                misses = 0
            else:
                misses += 1
                # Drop stale frame after ~3s of failed grabs so the UI shows 503, not a freeze.
                age = STATE.get("rviz_jpeg_at")
                if age is not None and (time.time() - age) > 3.0 and misses >= 8:
                    STATE["rviz_jpeg"] = None
                    STATE["rviz_jpeg_at"] = None
        except Exception:
            misses += 1
        time.sleep(period)


def main() -> None:
    rclpy.init()
    node = LiveBridgeNode()
    app = build_http(node)

    def spin() -> None:
        try:
            rclpy.spin(node)
        finally:
            node.destroy_node()
            rclpy.shutdown()

    threading.Thread(target=spin, daemon=True).start()
    threading.Thread(target=_rviz_loop, daemon=True).start()
    print("Live ROS bridge HTTP on http://127.0.0.1:8765 (camera + rviz capture)")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
