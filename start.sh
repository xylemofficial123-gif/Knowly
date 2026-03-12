#!/bin/bash
# Start all Knowledge Agent services
# Usage: ./start.sh

cd "$(dirname "$0")"

echo "Starting Docker services..."
docker compose up -d

echo "Starting backend API..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000 &
echo $! > .pids

echo "Starting Celery worker..."
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 &
echo $! >> .pids

echo "Starting Celery beat (scheduler)..."
celery -A app.workers.celery_app beat --loglevel=info &
echo $! >> .pids

cd ..

echo "Starting frontend..."
cd frontend
npm run dev &
echo $! >> ../backend/.pids

echo ""
echo "All services started!"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  Drive/Meet sync: every 30 minutes"
echo ""
echo "To stop: ./stop.sh"
