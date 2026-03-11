# Knowledge Agent — AI-Powered Institutional Memory

An AI-powered knowledge agent that ingests company documents from Google Drive and Google Meet transcripts, automatically extracts decisions and action items, and lets team members ask natural language questions with cited, sourced answers.

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose

### 1. Clone and configure

```bash
git clone https://github.com/sachinkurup/knowledge-agent.git
cd knowledge-agent/backend
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required
DATABASE_URL="postgresql://postgres:postgres@localhost:5433/knowledge_agent"
REDIS_URL="redis://localhost:6379"
QDRANT_URL="http://localhost:6333"
GEMINI_API_KEY="your-google-ai-studio-key"           # Free at https://aistudio.google.com/apikey
OPENROUTER_API_KEY="your-openrouter-key"              # Free at https://openrouter.ai
GOOGLE_CLIENT_ID="your-google-oauth-client-id"        # From Google Cloud Console
GOOGLE_CLIENT_SECRET="your-google-oauth-client-secret"

# Optional (enable when ready)
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
CLICKUP_API_KEY=
CLICKUP_TEAM_ID=
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL (port 5433), Redis (port 6379), and Qdrant (port 6333).

### 3. Install backend dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Start the backend API

```bash
uvicorn app.main:app --reload --port 8000
```

The API auto-creates database tables and the Qdrant vector collection on startup.

### 5. Authenticate Google Drive

On first run, trigger the OAuth flow:

```bash
python -c "from app.services.drive_ingestion import _get_credentials; _get_credentials()"
```

This opens your browser for Google login. The token is saved to `google_token.json` and auto-refreshes.

### 6. Run initial data ingestion

```bash
# Ingest all Google Drive files
python -c "from app.services.drive_ingestion import ingest_all_drive; print(f'Ingested {ingest_all_drive()} files')"

# Ingest Google Meet transcripts (with AI summaries)
python -c "from app.services.meet_ingestion import ingest_drive_transcripts; print(f'Ingested {ingest_drive_transcripts()} meetings')"
```

### 7. Start background workers (separate terminals)

```bash
# Celery worker (processes background tasks)
celery -A app.workers.celery_app worker --loglevel=info

# Celery beat (schedules Drive/Meet sync every 30 min)
celery -A app.workers.celery_app beat --loglevel=info
```

### 8. Install and start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:3000.

## How It Works

### Ask Questions
Open http://localhost:3000 and ask anything about your company's documents and meetings:
- "What are the coding guidelines?"
- "What happened in the March 5th standup?"
- "Who last edited the test cases document?"
- "What action items came from the regroup meeting?"

The Oracle searches your knowledge base, applies ACL filtering, and returns answers with citations back to the source documents.

### Automatic Sync
With Celery worker + beat running, the system automatically:
- **Every 30 minutes**: Syncs new/modified Google Drive files and Meet transcripts
- **Nightly**: Runs decision extraction on all content
- Only processes changed files (incremental sync)

### Meeting Intelligence
Google Meet transcripts (Gemini notes) are automatically processed to extract:
- Meeting summary
- Key decisions (auto-saved to decision records)
- Action items with assignee, deadline, and priority
- Key takeaways
- Follow-ups needed

### Document Tracking
For every Google Drive document, the system captures:
- Document owner
- Last editor and edit timestamp
- Full revision history (who edited, when)
- All searchable via the Oracle

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
| GET | `/health` | Health check |

### Example API Call

```bash
curl -X POST http://localhost:8000/api/oracle/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the coding guidelines?", "user_email": "you@company.com"}'
```

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Qdrant + Redis + Celery
- **LLM**: Gemini 2.5 Flash (primary) + OpenRouter free models (fallback)
- **Embeddings**: BAAI/bge-small-en-v1.5 (local via fastembed, no API cost)
- **Vector DB**: Qdrant (self-hosted via Docker)
- **Frontend**: Next.js 14 + Tailwind CSS

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/                   # Config, database, ACL
│   ├── models/                 # SQLAlchemy models
│   ├── api/                    # API route handlers
│   ├── services/               # Business logic
│   │   ├── llm.py              # Unified LLM (Gemini + fallback)
│   │   ├── oracle.py           # RAG pipeline
│   │   ├── embeddings.py       # Vector embeddings + search
│   │   ├── drive_ingestion.py  # Google Drive sync
│   │   ├── meet_ingestion.py   # Meeting transcript processing
│   │   ├── decision_extractor.py # Decision extraction
│   │   └── ...
│   └── workers/                # Celery tasks + scheduler
├── requirements.txt
└── .env
```

## Troubleshooting

**Gemini rate limit (429 RESOURCE_EXHAUSTED)**
The free tier has limited daily requests. The system automatically falls back to OpenRouter free models. Resets at midnight Pacific time.

**Google OAuth token expired**
Re-run the auth flow:
```bash
rm google_token.json
python -c "from app.services.drive_ingestion import _get_credentials; _get_credentials()"
```

**Port 5432 conflict (PostgreSQL)**
Docker maps to port 5433 to avoid conflicts with local Postgres. The `.env` already uses 5433.

**Slack errors in logs**
Safe to ignore if Slack is not configured. The system works without Slack — it just skips Slack-related ACL checks.

## Getting API Keys (All Free)

1. **Gemini API Key**: https://aistudio.google.com/apikey (no credit card needed)
2. **OpenRouter API Key**: https://openrouter.ai (sign up, free tier)
3. **Google OAuth Credentials**: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID (Desktop app type). Enable the Google Drive API.
