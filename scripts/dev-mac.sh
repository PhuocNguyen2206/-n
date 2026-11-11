#!/bin/bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PROJECT_ROOT/.tools/node-v22.23.5-darwin-arm64/bin:$PROJECT_ROOT/.tools/bin:$PATH"
cd "$PROJECT_ROOT/backend"
./.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
trap 'exit 130' INT TERM
cd "$PROJECT_ROOT/frontend"
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
