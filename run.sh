#!/bin/bash
set -e

echo "Starting Volvo EX30 Mate..."
export DATA_DIR="${DATA_DIR:-./data}"
mkdir -p "$DATA_DIR"

# Start poller background process
python3 poller/main.py &
POLLER_PID=$!

# Start web UI
python3 -m uvicorn web.main:app --host 0.0.0.0 --port 4000 &
WEB_PID=$!

trap "kill $POLLER_PID $WEB_PID 2>/dev/null || true" EXIT INT TERM

wait -n $POLLER_PID $WEB_PID
