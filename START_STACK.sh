#!/usr/bin/env bash
# MechaDelta full stack
#
#   ./START_STACK.sh start    # one shot: sim + bridge + api + ui
#   ./START_STACK.sh stop
#   ./START_STACK.sh status
#   ./START_STACK.sh sim|bridge|api|ui   # single piece (foreground)
#
# Streams use HTTP JPEGs via the ROS bridge (:8765). LiveKit is not required.
set -euo pipefail

ROOT_BACKEND="${MECHADELTA_BACKEND:-$HOME/FYP/MechaDelta_Backend}"
ROOT_UI="${MECHADELTA_UI:-$HOME/FYP/MechaDeltaUI}"
ROOT_WS="${MECHADELTA_WS:-$HOME/mechadelta_ws}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
LOG_DIR="${MECHADELTA_LOG_DIR:-$ROOT_BACKEND/logs/stack}"
PID_DIR="$LOG_DIR/pids"

# Prefer discrete NVIDIA for Gazebo/RViz (prime-select is often "on-demand").
use_nvidia_gl() {
  unset GALLIUM_DRIVER MESA_LOADER_DRIVER_OVERRIDE LIBGL_ALWAYS_SOFTWARE 2>/dev/null || true
  export __NV_PRIME_RENDER_OFFLOAD=1
  export __GLX_VENDOR_LIBRARY_NAME=nvidia
  export __VK_LAYER_NV_optimus=NVIDIA_only
  export QT_QPA_PLATFORM=xcb
  export DISPLAY="${DISPLAY:-:1}"
  export GZ_IP
  GZ_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  export GZ_IP
}

source_ros() {
  set +u
  # shellcheck disable=SC1090
  source "$ROS_SETUP"
  # shellcheck disable=SC1091
  source "$ROOT_WS/install/setup.bash"
  set -u
}

ensure_dirs() {
  mkdir -p "$LOG_DIR" "$PID_DIR"
}

write_pid() {
  local name="$1" pid="$2"
  echo "$pid" >"$PID_DIR/$name.pid"
}

cmd_sim() {
  use_nvidia_gl
  source_ros
  cd "$ROOT_WS"
  mkdir -p logs
  exec ros2 launch mechadelta_poc poc.launch.py \
    gui:=true \
    rviz:=true \
    nav:=true \
    slam:=True \
    perception:=true \
    record:=true \
    record_fps:=8.0 \
    render_driver:=native
}

cmd_bridge() {
  use_nvidia_gl
  source_ros
  cd "$ROOT_BACKEND"
  fuser -k 8765/tcp 2>/dev/null || true
  if [[ -f .venv/bin/activate ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  exec python -m ros_bridge.live_node
}

cmd_api() {
  cd "$ROOT_BACKEND"
  fuser -k 8000/tcp 2>/dev/null || true
  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}

cmd_ui() {
  cd "$ROOT_UI"
  if command -v fnm >/dev/null 2>&1; then
    eval "$(fnm env)"
    fnm use 22 >/dev/null 2>&1 || true
  fi
  exec npm run dev
}

kill_matching() {
  # Kill by pattern without matching this script's own argv.
  local pat="$1"
  local p
  while read -r p; do
    [[ -z "$p" ]] && continue
    [[ "$p" == "$$" || "$p" == "$PPID" ]] && continue
    kill "$p" 2>/dev/null || true
  done < <(pgrep -f "$pat" 2>/dev/null || true)
}

cmd_stop() {
  echo "Stopping UI / API / bridge / sim..."
  if [[ -d "$PID_DIR" ]]; then
    for f in "$PID_DIR"/*.pid; do
      [[ -f "$f" ]] || continue
      pid="$(cat "$f" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$f"
    done
  fi
  fuser -k 3000/tcp 2>/dev/null || true
  fuser -k 8000/tcp 2>/dev/null || true
  fuser -k 8765/tcp 2>/dev/null || true
  kill_matching 'ros_bridge.live_node'
  kill_matching 'uvicorn app.main:app'
  kill_matching 'ros2 launch mechadelta_poc poc.launch'
  kill_matching 'next-server'
  kill_matching 'next dev'
  sleep 2
  kill_matching 'gz sim'
  kill_matching '/rviz2'
  kill_matching 'sync_slam_toolbox_node'
  kill_matching 'mechadelta_poc/perception.py'
  kill_matching 'nav2_bringup'
  kill_matching '/opt/ros/.*/lib/nav2_'
  if [[ -x "$ROOT_WS/stop_demo.sh" ]]; then
    (cd "$ROOT_WS" && ./stop_demo.sh) || true
  fi
  echo "Done."
}

wait_port() {
  local port="$1" label="$2" tries="${3:-60}"
  local i
  for ((i = 1; i <= tries; i++)); do
    if ss -ltn 2>/dev/null | grep -q ":${port} "; then
      echo "  $label :$port up"
      return 0
    fi
    sleep 1
  done
  echo "  WARNING: $label :$port not listening after ${tries}s" >&2
  return 1
}

wait_ros_ready() {
  local tries="${1:-90}"
  local i
  echo "Waiting for ROS /scan (sim + sensors)..."
  use_nvidia_gl
  source_ros
  export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"
  for ((i = 1; i <= tries; i++)); do
    if timeout 2 ros2 topic list 2>/dev/null | grep -qx '/scan'; then
      echo "  /scan is up (${i}s)"
      return 0
    fi
    sleep 1
  done
  echo "  WARNING: /scan not seen after ${tries}s — bridge may start degraded" >&2
  return 1
}

cmd_start() {
  ensure_dirs
  echo "Stopping any previous stack..."
  cmd_stop >/dev/null 2>&1 || true
  sleep 1

  echo "Starting simulation (Gazebo + Nav2 + SLAM + YOLO + RViz)..."
  (
    use_nvidia_gl
    source_ros
    cd "$ROOT_WS"
    mkdir -p logs
    exec ros2 launch mechadelta_poc poc.launch.py \
      gui:=true \
      rviz:=true \
      nav:=true \
      slam:=True \
      perception:=true \
      record:=true \
      record_fps:=8.0 \
      render_driver:=native
  ) >"$LOG_DIR/sim.log" 2>&1 &
  write_pid sim $!
  echo "  sim pid=$(cat "$PID_DIR/sim.pid")  log=$LOG_DIR/sim.log"

  wait_ros_ready 120 || true

  echo "Starting ROS bridge (:8765)..."
  (
    use_nvidia_gl
    source_ros
    cd "$ROOT_BACKEND"
    # shellcheck disable=SC1091
    source .venv/bin/activate
    fuser -k 8765/tcp 2>/dev/null || true
    exec python -m ros_bridge.live_node
  ) >"$LOG_DIR/bridge.log" 2>&1 &
  write_pid bridge $!
  wait_port 8765 bridge 45 || true

  echo "Starting FastAPI (:8000)..."
  (
    cd "$ROOT_BACKEND"
    # shellcheck disable=SC1091
    source .venv/bin/activate
    fuser -k 8000/tcp 2>/dev/null || true
    exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ) >"$LOG_DIR/api.log" 2>&1 &
  write_pid api $!
  wait_port 8000 api 30 || true

  echo "Starting UI (:3000)..."
  (
    cd "$ROOT_UI"
    if command -v fnm >/dev/null 2>&1; then
      eval "$(fnm env)"
      fnm use 22 >/dev/null 2>&1 || true
    fi
    fuser -k 3000/tcp 2>/dev/null || true
    exec npm run dev
  ) >"$LOG_DIR/ui.log" 2>&1 &
  write_pid ui $!
  wait_port 3000 ui 60 || true

  echo
  echo "========================================================================"
  echo " MechaDelta stack started"
  echo "   UI:     http://localhost:3000"
  echo "   API:    http://127.0.0.1:8000"
  echo "   Bridge: http://127.0.0.1:8765/health"
  echo "   Logs:   $LOG_DIR/"
  echo "   Stop:   $ROOT_BACKEND/START_STACK.sh stop"
  echo "========================================================================"
  cmd_status
}

cmd_status() {
  echo "== ports =="
  ss -ltnp 2>/dev/null | rg ':(3000|8000|8765)\b' || echo "(none)"
  echo
  echo "== key processes =="
  ps -eo pcpu,pmem,comm,args --sort=-pcpu \
    | rg -i 'gz sim|rviz|perception|live_node|uvicorn|next|nav2|slam_toolbox|poc.launch' \
    | head -25 || echo "(none)"
  echo
  echo "== health =="
  curl -sf http://127.0.0.1:8765/health && echo || echo "bridge :8765 down"
  curl -sf http://127.0.0.1:8000/docs -o /dev/null -w "api :8000 HTTP %{http_code}\n" || echo "api :8000 down"
  curl -sf http://127.0.0.1:3000/ -o /dev/null -w "ui  :3000 HTTP %{http_code}\n" || echo "ui :3000 down"
}

print_help() {
  cat <<EOF
Usage: $0 <command>

  start     Start sim + bridge + api + ui in the background
  stop      Stop everything
  status    Ports / processes / health
  sim       Foreground: Gazebo + ROS + Nav2 + SLAM + YOLO + RViz
  bridge    Foreground: ROS JPEG / cmd_vel bridge (:8765)
  api       Foreground: FastAPI (:8000)
  ui        Foreground: Next.js (:3000)
  help      This message

Logs for 'start' go to: $LOG_DIR/
EOF
}

case "${1:-}" in
  start|all) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  sim) cmd_sim ;;
  bridge) cmd_bridge ;;
  api) cmd_api ;;
  ui) cmd_ui ;;
  ""|help|-h|--help) print_help ;;
  *)
    echo "Unknown command: $1" >&2
    print_help >&2
    exit 1
    ;;
esac
