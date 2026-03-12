#!/bin/bash
# Stop all Knowledge Agent services
cd "$(dirname "$0")"

if [ -f backend/.pids ]; then
    while read pid; do
        kill "$pid" 2>/dev/null
    done < backend/.pids
    rm backend/.pids
    echo "Services stopped."
else
    echo "No .pids file found. Killing by name..."
    pkill -f "uvicorn app.main" 2>/dev/null
    pkill -f "celery -A app.workers" 2>/dev/null
    echo "Done."
fi
