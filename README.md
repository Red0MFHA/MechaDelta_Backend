# MechaDelta Backend

FastAPI backend for [MechaDeltaUI](https://github.com/Red0MFHA/MechaDeltaUI) Operations workspace. Layered MVC: controller → service → model → repository → PostgreSQL (SQLite fallback for local demo). A separate `ros_bridge` process talks to ROS when the simulation is running.

Research Lab APIs are intentionally unavailable for now.

## Quick start (no Gazebo, no Postgres)

```bash
cd ~/FYP/MechaDelta_Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# FORCE_SQLITE=1 is already set in .env.example
python -m scripts.seed_fixture
uvicorn app.main:app --reload --port 8000
```

Optional stub bridge (pose / lidar / jog / navigate without ROS):

```bash
source .venv/bin/activate
python -m ros_bridge.stub_server
```

Point the UI at this API:

```bash
# in MechaDeltaUI .env.local
NEXT_PUBLIC_DATA_MODE=http
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Sign in still uses the UI mock session (`demo@mechadelta.lab` / `mechadelta`).

## PostgreSQL

```bash
docker compose up -d db
# in .env: FORCE_SQLITE=0 and DATABASE_URL=postgresql+psycopg://mechadelta:mechadelta@localhost:5432/mechadelta
```

## Live simulation (camera + YOLO overlay in the UI)

Use **four terminals**. Keep the UI on Node 22 (`fnm use 22`).

**1. Simulation** (Gazebo + perception — publishes `/camera/color/image_raw` and `/perception/image_annotated`):

```bash
cd ~/FYP/MechaDelta   # or ~/mechadelta_ws
source /opt/ros/$ROS_DISTRO/setup.bash
source install/setup.bash   # after colcon build
./run_transition_poc.sh --fps 8
```

**2. Live ROS bridge** (must use the same ROS env as the sim; replaces the stub):

```bash
# stop any old stub on :8765 first
fuser -k 8765/tcp 2>/dev/null
cd ~/FYP/MechaDelta_Backend
source /opt/ros/$ROS_DISTRO/setup.bash
source /path/to/MechaDelta/install/setup.bash
# system/ROS Python needs cv_bridge + the backend deps, or:
#   /opt/ros/$ROS_DISTRO/bin/python -m pip install --user fastapi uvicorn pillow numpy httpx
python3 -m ros_bridge.live_node
# health should show "mode":"ros" and cameraFresh true once images flow
curl -s http://127.0.0.1:8765/health
```

**3. Backend API** — point at the sim `runs/` folder:

```bash
cd ~/FYP/MechaDelta_Backend
# edit .env:
#   MECHADELTA_RUNS_ROOT=/absolute/path/to/MechaDelta/runs
#   BRIDGE_URL=http://127.0.0.1:8765
source .venv/bin/activate
fuser -k 8000/tcp 2>/dev/null
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**4. UI** (`NEXT_PUBLIC_DATA_MODE=http`, API `http://localhost:8000`):

```bash
fnm use 22
cd ~/FYP/MechaDeltaUI
npm run dev
```

In the app: **Robots → Gazebo demo robot → Connect**, then open **Patrol**.  
`MediaInfo.url` is `.../camera.jpg?view=annotated` (YOLO overlay). Use `view=raw` for the plain camera.

Without a running sim, `python -m ros_bridge.node` / `stub_server` still serves fake frames.

## Architecture

```text
UI → controllers → services → models/repositories → PostgreSQL
                         ↘ infrastructure ports → run folder / ros_bridge
```
