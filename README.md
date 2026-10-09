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

## Live simulation

1. Launch MechaDelta as usual (`run_transition_poc.sh`).
2. Set `MECHADELTA_RUNS_ROOT` to that workspace’s `runs/` directory.
3. Run `python -m ros_bridge.node` in a ROS-sourced shell (falls back to the stub if rclpy is missing).

## Architecture

```text
UI → controllers → services → models/repositories → PostgreSQL
                         ↘ infrastructure ports → run folder / ros_bridge
```
