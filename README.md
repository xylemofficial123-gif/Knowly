# Knowledge System

Simple setup guide for new contributors.

## 1. Clone the repo

```bash
git clone https://github.com/sachinkurup/Knowledge-system.git
cd Knowledge-system
```

## 2. Start backend locally (first time)

### Prerequisites
- Python 3.11+
- Docker + Docker Compose

### Start infra

```bash
docker compose up -d
```

### Setup backend venv

```bash
cd backend
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Required `.env` values (minimum)

Set these in `backend/.env`:

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
```

### Run API

```bash
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 3. Start workers locally

Recommended single-process mode:

```bash
celery -A app.workers.celery_app worker --beat --loglevel=info --concurrency=2
```

## 4. Start frontend locally

```bash
cd ../frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

Set frontend env (if needed):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 5. Google auth for ingestion

### Local development

Run once to create `google_token.json`:

```bash
cd backend
source venv/bin/activate
python -c "from app.services.drive_ingestion import _get_credentials; _get_credentials()"
```

### Railway/cloud

Do **not** use interactive OAuth in cloud.
Set this Railway variable instead:

- `GOOGLE_TOKEN_JSON` = full contents of your local `google_token.json`

## 6. Trigger ingestion manually

```bash
curl -X POST http://localhost:8000/api/ingest/trigger \
  -H "Content-Type: application/json" \
  -d '{"source":"all"}'
```

Useful per-source triggers:

```bash
curl -X POST http://localhost:8000/api/ingest/trigger -H "Content-Type: application/json" -d '{"source":"slack"}'
curl -X POST http://localhost:8000/api/ingest/trigger -H "Content-Type: application/json" -d '{"source":"drive"}'
curl -X POST http://localhost:8000/api/ingest/trigger -H "Content-Type: application/json" -d '{"source":"clickup"}'
curl -X POST http://localhost:8000/api/ingest/trigger -H "Content-Type: application/json" -d '{"source":"calendar"}'
curl -X POST http://localhost:8000/api/ingest/trigger -H "Content-Type: application/json" -d '{"source":"meet"}'
```

## 7. Enable data sources

Check current settings:

```bash
curl -sS http://localhost:8000/api/admin/settings
```

Enable all:

```bash
curl -X PATCH http://localhost:8000/api/admin/settings \
  -H "Content-Type: application/json" \
  -d '{"enabled_sources":["slack","drive","meet","clickup","calendar"]}'
```

## 8. Deploy backend to Railway

From `backend/`:

```bash
/tmp/railway-cli/node_modules/.bin/railway up -s backend-api
/tmp/railway-cli/node_modules/.bin/railway up -s beat
```

Check logs:

```bash
/tmp/railway-cli/node_modules/.bin/railway logs -s backend-api --deployment
/tmp/railway-cli/node_modules/.bin/railway logs -s beat --deployment
```

Important Railway vars for `backend-api`:

- `DATABASE_URL`
- `REDIS_URL`
- `QDRANT_URL`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_JSON`
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `CLICKUP_CLIENT_ID`
- `CLICKUP_CLIENT_SECRET`
- `BACKEND_URL` (public Railway URL)
- `FRONTEND_URL` (public Vercel URL)
- `EXTRA_CORS_ORIGINS` (comma-separated allowed frontend domains)

Optional:
- `BYPASS_ACL=true` for debugging/demo only

## 9. Deploy frontend to Vercel

In Vercel project env:

- `NEXT_PUBLIC_API_URL=https://<your-backend-domain>`

Then redeploy Vercel.

## 10. Slack + ClickUp production wiring

Slack:
- Events URL: `https://<your-backend-domain>/slack/events`
- No trailing dot.

ClickUp:
- Connect via `/api/oauth/clickup/authorize` flow (from UI)
- Register webhook via UI action or `POST /api/oauth/clickup/register-webhook`

## 11. Common problems

### `API Request Failed`
- Backend `/api/oracle/ask` returned non-200.
- Check Railway backend logs.
- Verify LLM keys (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`).

### “No documented records in currently enabled sources”
- Sources are disabled.
- Enable via `PATCH /api/admin/settings`.

### “You don't have access to view them”
- ACL restrictions are active.
- Confirm user identity and source ACL.
- For temporary debug only: set `BYPASS_ACL=true` and redeploy backend.

### Google ingestion fails in cloud
- Set `GOOGLE_TOKEN_JSON` in Railway.
- Do not run browser OAuth flow inside Railway.

## 12. Minimal API list

- `POST /api/oracle/ask`
- `GET /api/admin/settings`
- `PATCH /api/admin/settings`
- `POST /api/ingest/trigger`
- `GET /api/ingest/drive/folders`
- `GET /api/oauth/clickup/status`
- `GET /health`
