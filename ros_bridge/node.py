"""ROS bridge entrypoint: live node when rclpy is available, else stub."""

from __future__ import annotations


def main() -> None:
    try:
        import rclpy  # noqa: F401
    except ImportError:
        print("rclpy not available — starting stub bridge on :8765")
        from ros_bridge.stub_server import main as stub_main

        stub_main()
        return

    print("rclpy available — starting LIVE bridge on :8765")
    from ros_bridge.live_node import main as live_main

    live_main()


if __name__ == "__main__":
    main()
