# Knowledge System

AI-powered internal knowledge agent for Seedling Labs. Multi-agent RAG system that ingests Google Drive, Meet transcripts, Calendar, Slack, ClickUp — extracts decisions, answers questions with citations, and proactively prevents redundant conversations.

## First Steps
1. Read `PROJECT_STATUS.md` — the living project tracker with full architecture, feature status, goals, and changelog
2. Check feature status tables before building anything — it may already exist
3. After ANY code change, feature, bug fix, or goal discussion: **update `PROJECT_STATUS.md`** (changelog entry + update relevant status tables). Do this automatically without being asked.

## Stack
- Backend: FastAPI + SQLAlchemy + Qdrant + Redis + Celery (`backend/`)
- Frontend: Next.js 14 + Tailwind (`frontend/`)
- LLM: 3-tier free fallback — Gemini → Groq → OpenRouter (`app/services/llm.py`)
- Embeddings: Local fastembed BAAI/bge-small-en-v1.5, 384 dims, zero API cost
- Multi-agent: Router → Research/Onboarding agents (`app/agents/`)

## Key Paths
- `PROJECT_STATUS.md` — **Living project tracker** (ALWAYS read first, ALWAYS keep updated)
- `backend/app/agents/` — Multi-agent system (router, research, onboarding, orchestrator)
- `backend/app/services/` — Core services (llm, embeddings, oracle, drive/meet/calendar ingestion, chunker)
- `backend/app/core/` — Config, database, ACL, timezone
- `frontend/` — Next.js 14 chat UI + admin panel
- `PRD.md` — Original v1 requirements (partially outdated, use PROJECT_STATUS.md instead)

## Conventions
- All user-facing timestamps: IST (GMT+5:30), DD/MM/YYYY format via `app/core/timezone.py`
- LLM calls always go through `app/services/llm.py` — never call APIs directly
- No hardcoded keywords or rules — use LLM-based intelligence for query understanding
- Free-tier only: no paid API keys (Gemini free, Groq free 14,400 req/day, OpenRouter free)
- Embeddings are local (no API cost)
- Docker services: `docker compose up -d` (Postgres on port 5433, not 5432)
- Citation format: `[N]` not `[SOURCE_N]`
- Meeting summaries: speaker attribution (who said what), no attendee lists, bullet points
