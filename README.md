# Knowledge Agent — AI-Powered Institutional Memory

An AI-powered knowledge agent that ingests company communication from Slack, ClickUp, and Google Meet, automatically extracts decisions, and lets team members ask natural language questions with cited, sourced answers.

## Setup (Zero to Running)

### 1. Clone and configure environment

```bash
cd Knowledge-system/backend
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Start infrastructure services

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, and Qdrant.

### 3. Install backend dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Start the backend API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API auto-creates database tables and the Qdrant collection on startup.

### 5. Start Celery worker (separate terminal)

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

### 6. (Optional) Start Celery Beat for scheduled tasks

```bash
cd backend
celery -A app.workers.celery_app beat --loglevel=info
```

### 7. Install and start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000.

### 8. Run initial data backfill

```bash
# Slack backfill
python scripts/backfill_slack.py

# ClickUp backfill
python scripts/backfill_clickup.py
```

### 9. Configure Slack Bot

- Create a Slack app at api.slack.com
- Add Bot Token Scopes: `channels:history`, `channels:read`, `chat:write`, `commands`, `groups:history`, `groups:read`, `im:write`, `users:read`, `users:read.email`
- Set Event Subscriptions URL to `https://your-domain/slack/events`
- Set Slash Commands URLs to `https://your-domain/slack/commands`
- Set Interactivity URL to `https://your-domain/slack/interactions`
- Add `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` to `.env`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/oracle/ask` | Ask the Knowledge Oracle |
| GET | `/api/admin/audit-log` | View query audit log |
| GET | `/api/admin/review-queue` | View pending decision reviews |
| POST | `/api/admin/review-queue/{id}/approve` | Approve a decision |
| POST | `/api/admin/review-queue/{id}/reject` | Reject a decision |
| POST | `/api/transcripts/upload` | Upload VTT/SRT transcript |
| POST | `/api/ingest/trigger` | Trigger manual ingestion |
| POST | `/api/clickup/webhook` | ClickUp webhook receiver |
| GET | `/health` | Health check |

## Slack Commands

- `/oracle <question>` — Ask the Knowledge Oracle
- `/history <project>` — Get project history
- `/decision <text>` — Record a decision manually
- `/timeline [project]` — Get chronological project timeline
- `/define [term]` — Look up acronyms and terms

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Qdrant + Redis + Celery
- **LLM**: Claude Sonnet for Oracle answers, Claude Haiku for alerts/extraction
- **Embeddings**: BAAI/bge-small-en-v1.5 (local, no API key needed)
- **Frontend**: Next.js 14 + Tailwind CSS
