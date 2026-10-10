#!/usr/bin/env bash
# Starts all three services. HTTPS=1 ./start.sh to serve the dashboard over HTTPS for phones.
cd "$(dirname "$0")"
(cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
sleep 3
(cd video_service && ../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8001) &
(cd frontend && npm run dev) &
trap 'kill 0' EXIT
wait
