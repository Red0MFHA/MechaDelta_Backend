"""ROS bridge entrypoint.

Uses the stub server when rclpy is unavailable. Replace the body of `run_ros`
with the real subscriptions when running inside a sourced ROS workspace.
"""

from __future__ import annotations


def main() -> None:
    try:
        import rclpy  # noqa: F401
    except ImportError:
        print("rclpy not available — starting stub bridge on :8765")
        from ros_bridge.stub_server import main as stub_main

        stub_main()
        return

    print("rclpy available — stub still used until full node is wired; starting stub on :8765")
    from ros_bridge.stub_server import main as stub_main

    stub_main()


if __name__ == "__main__":
    main()
