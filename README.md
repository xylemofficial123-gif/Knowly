# Knowledge Agent — AI-Powered Institutional Memory

Knowledge Agent ingests organizational knowledge (Drive, Slack, Meet transcripts, Calendar, ClickUp), stores embeddings in Qdrant, and answers questions with source-grounded responses.

## Repository

```bash
git clone https://github.com/sachinkurup/Knowledge-system.git
cd Knowledge-system
```

## Local Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker + Docker Compose

### 1. Start infrastructure

```bash
docker compose up -d
```

Expected local services:
- Postgres
- Redis
- Qdrant

### 2. Backend setup

```bash
cd backend
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure backend env

Set at least:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/knowledge_agent
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333

GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=

CLICKUP_CLIENT_ID=
CLICKUP_CLIENT_SECRET=

# Optional legacy fallback
CLICKUP_API_KEY=
CLICKUP_TEAM_ID=

# Optional runtime flags
BYPASS_ACL=false
EXTRA_CORS_ORIGINS=
```

### 4. Start backend API

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Google auth (local)

For local development, run once to create `google_token.json`:

```bash
python -c "from app.services.drive_ingestion import _get_credentials; _get_credentials()"
```

### 6. Start workers

Recommended single-process mode:

```bash
celery -A app.workers.celery_app worker --beat --loglevel=info --concurrency=2
```

Optional separate processes:

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

### 7. Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

## Cloud Deployment Notes (Railway + Vercel)

### Backend (Railway)

Set service variables on `backend-api`:
- `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_JSON` (full authorized_user JSON string for non-interactive cloud auth)
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` (if Slack enabled)
- `CLICKUP_CLIENT_ID`, `CLICKUP_CLIENT_SECRET` (if ClickUp OAuth enabled)
- `BACKEND_URL` (public Railway URL)
- `FRONTEND_URL` (public Vercel URL)
- `EXTRA_CORS_ORIGINS` (comma-separated frontend origins)
- `BYPASS_ACL=true|false` (debug/demo only)

Deploy:

```bash
cd backend
/tmp/railway-cli/node_modules/.bin/railway up -s backend-api
/tmp/railway-cli/node_modules/.bin/railway up -s beat
```

### Frontend (Vercel)

Project env vars:
- `NEXT_PUBLIC_API_URL=https://<your-backend-domain>`

Redeploy frontend after env changes.

## Ingestion

Manual trigger:

```bash
curl -X POST http://localhost:8000/api/ingest/trigger \
  -H "Content-Type: application/json" \
  -d '{"source":"all"}'
```

Drive folder discovery:

```bash
curl http://localhost:8000/api/ingest/drive/folders
```

## Key API Endpoints

### Core
- `POST /api/oracle/ask`
- `POST /api/oracle/ask/simple`
- `GET /health`

### Ingestion
- `POST /api/ingest/trigger`
- `GET /api/ingest/drive/folders`
- `POST /api/ingest/upload`
- `POST /api/transcripts/upload`

### Admin
- `GET /api/admin/audit-log`
- `GET /api/admin/metrics`
- `GET /api/admin/settings`
- `GET /api/admin/graph`
- `GET /api/admin/review-queue`
- `POST /api/admin/review-queue/{item_id}/approve`
- `POST /api/admin/review-queue/{item_id}/reject`
- `GET /api/admin/decisions`
- `POST /api/admin/decisions/extract`

### Users / Groups
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{email}`
- `DELETE /api/users/{email}`
- `GET /api/groups`
- `POST /api/groups`
- `GET /api/groups/{group_id}`
- `POST /api/groups/{group_id}/members`
- `DELETE /api/groups/{group_id}/members/{user_email}`

### OAuth / Integrations
- `GET /api/oauth/clickup/authorize`
- `GET /api/oauth/clickup/callback`
- `GET /api/oauth/clickup/status`
- `DELETE /api/oauth/clickup/disconnect`
- `POST /api/oauth/clickup/register-webhook`
- `POST /api/clickup/webhook`
- `POST /slack/events`
- `POST /slack/commands`
- `POST /slack/interactions`

## LLM Fallback Behavior

Answer generation tries providers in this order:
1. Gemini models
2. Groq models
3. OpenRouter fallback models

If all providers fail, backend now returns a graceful response instead of crashing the UI request.

## Troubleshooting

### `API Request Failed` in frontend
- Verify `NEXT_PUBLIC_API_URL` in Vercel project env.
- Verify backend `/health` responds with `{"status":"ok"}`.
- Check Railway backend logs for `/api/oracle/ask` errors.

### `Address already in use` during cloud Google ingestion
- Ensure `GOOGLE_TOKEN_JSON` is set in Railway.
- Do not use local browser OAuth flow in cloud runtime.

### Access denied despite ingestion
- Check ACL settings and user identity.
- For temporary debugging only, set `BYPASS_ACL=true` on backend.

### Slack events 404
- Use exact URL: `https://<backend-domain>/slack/events` (no trailing dot).
