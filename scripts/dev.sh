#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
settlesum_api_pid=$!
trap 'kill "$settlesum_api_pid" 2>/dev/null || true' EXIT INT TERM
npm --prefix frontend run dev
