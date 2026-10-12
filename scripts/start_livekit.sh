#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/bin/livekit-server" --config "$ROOT/livekit.yaml" --dev
