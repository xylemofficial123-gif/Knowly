# Knowledge Agent — Product Requirements Document

## Vision

Build an AI-powered **Internal Knowledge & Decision Memory Agent** (Living Institutional Brain) for startups. The system ingests company communication, automatically extracts decisions and context, and lets team members ask natural language questions with cited, sourced answers.

**North Star**: A fully autonomous multi-agent system that reasons, understands organizational context, proactively informs team members of prior decisions, onboards new hires with project history, and manages action items across meetings — all without manual intervention.

---

## Current State (v1 — MVP, Built)

### What's Working

#### Data Ingestion
- **Google Drive**: OAuth 2.0 browser flow, auto-syncs every 30 minutes
  - Supports: Google Docs, Sheets, Slides, PDFs, plain text, markdown
  - Incremental sync: only re-ingests new/modified files
  - Captures edit history: owner, last editor, full revision history with timestamps
- **Google Meet Transcripts**: Auto-discovers Gemini-generated meeting notes from Drive
  - Generates AI summaries, key decisions, action items, takeaways, follow-ups
  - Stores with attendee-based ACL (only meeting participants can see)
- **Manual Transcript Upload**: VTT/SRT file upload with speaker detection
- **Slack Ingestion**: Built but not connected (needs bot token)
- **ClickUp Ingestion**: Built but not connected (needs API key)

#### Knowledge Processing
- **Chunking**: 400-word chunks with 40-word overlap
- **Embeddings**: Local BAAI/bge-small-en-v1.5 via fastembed (384 dimensions, no API cost)
- **Vector Storage**: Qdrant with document metadata, entities, ACL
- **Entity Extraction**: Regex-based extraction of people, projects, dates, acronyms

#### Intelligence Layer
- **Oracle (RAG)**: Semantic search → ACL filter → re-rank (0.7 vector + 0.3 keyword) → LLM synthesis with citations
- **Decision Extraction**: AI identifies explicit/implicit decisions from all content, routes by confidence:
  - >= 0.75 → DecisionRecord (auto-saved)
  - 0.50-0.74 → ReviewQueue (human review)
  - < 0.50 → discarded
- **Ghost Documentation**: Detects informal decisions, can prompt users to confirm (via Slack when connected)
- **Re-litigation Detection**: Cosine similarity check against active decisions (threshold: 0.82)
- **Meeting Summaries**: Auto-generated summaries with action items, decisions, takeaways, follow-ups
- **Acronym Buster**: Glossary + AI-powered term lookup from knowledge base

#### LLM Strategy
- **Primary**: Google Gemini 2.5 Flash (free tier, 20 req/day)
- **Fallback chain**: Gemma 3 27B → Gemma 3 4B → Mistral Small 3.1 → Qwen 3 30B (all free via OpenRouter)
- **Last resort**: Wait 30s + retry Gemini
- Centralized in `app/services/llm.py` — single place to change models

#### Infrastructure
- PostgreSQL 15 (documents, chunks, decisions, audit log, review queue)
- Qdrant (vector search)
- Redis (caching + Celery broker)
- Celery worker + beat scheduler (background tasks)

#### Frontend
- Next.js 14 + Tailwind CSS
- Oracle chat interface with citation cards and freshness badges
- Admin panel: Audit Log + Review Queue tabs

#### APIs
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

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                │
│          Oracle Chat UI  │  Admin Panel              │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP
┌───────────────────────▼─────────────────────────────┐
│                  FastAPI Backend                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Oracle   │  │ Admin    │  │ Ingestion API    │   │
│  │ API      │  │ API      │  │ (Drive/Meet/     │   │
│  │          │  │          │  │  Slack/ClickUp)   │   │
│  └────┬─────┘  └──────────┘  └────────┬─────────┘   │
│       │                               │              │
│  ┌────▼─────────────────────────────────▼──────────┐ │
│  │              Service Layer                       │ │
│  │  llm.py │ oracle.py │ decision_extractor.py     │ │
│  │  chunker.py │ embeddings.py │ meet_ingestion.py │ │
│  │  drive_ingestion.py │ ghost_docs.py             │ │
│  │  relitigation_detector.py │ acronym_buster.py   │ │
│  └──────┬──────────┬──────────────┬────────────────┘ │
│         │          │              │                   │
│    ┌────▼───┐ ┌────▼───┐  ┌──────▼──────┐           │
│    │Postgres│ │ Qdrant │  │   Redis     │           │
│    │(data)  │ │(vectors│  │(cache+queue)│           │
│    └────────┘ └────────┘  └──────┬──────┘           │
│                                  │                   │
│                           ┌──────▼──────┐           │
│                           │Celery Worker│           │
│                           │+ Beat       │           │
│                           └─────────────┘           │
└─────────────────────────────────────────────────────┘
```

---

## File Structure

```
knowledge_system/
├── docker-compose.yml          # Postgres, Redis, Qdrant
├── PRD.md                      # This document
├── README.md                   # Setup guide for teammates
│
├── backend/
│   ├── .env                    # API keys and config (not in git)
│   ├── .env.example            # Template for .env
│   ├── requirements.txt        # Python dependencies
│   ├── google_token.json       # Google OAuth token (auto-generated, not in git)
│   │
│   ├── app/
│   │   ├── main.py             # FastAPI app, lifespan, Slack handlers
│   │   │
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic Settings (env vars)
│   │   │   ├── database.py     # SQLAlchemy engine + session
│   │   │   └── acl.py          # ACL enforcement (Slack channel membership)
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py     # Document, Chunk, DecisionRecord, AuditLog
│   │   │   └── review_queue.py # ReviewQueueItem model
│   │   │
│   │   ├── api/
│   │   │   ├── oracle.py       # POST /api/oracle/ask
│   │   │   ├── admin.py        # GET audit-log, review-queue, approve/reject
│   │   │   ├── transcripts.py  # POST /api/transcripts/upload
│   │   │   └── ingestion.py    # POST /api/ingest/trigger
│   │   │
│   │   ├── services/
│   │   │   ├── llm.py              # Unified LLM client (Gemini + OpenRouter fallback)
│   │   │   ├── oracle.py           # RAG pipeline: embed → search → ACL → re-rank → synthesize
│   │   │   ├── embeddings.py       # fastembed + Qdrant operations
│   │   │   ├── chunker.py          # Text splitting + document storage
│   │   │   ├── entity_extractor.py # Regex entity extraction
│   │   │   ├── drive_ingestion.py  # Google Drive OAuth + file ingestion
│   │   │   ├── meet_ingestion.py   # Meeting transcript processing + AI summaries
│   │   │   ├── slack_ingestion.py  # Slack message ingestion
│   │   │   ├── clickup_ingestion.py# ClickUp task ingestion
│   │   │   ├── decision_extractor.py# AI decision extraction + routing
│   │   │   ├── ghost_docs.py       # Ghost documentation prompts
│   │   │   ├── relitigation_detector.py # Re-litigation detection
│   │   │   ├── acronym_buster.py   # Term/acronym definitions
│   │   │   └── timeline.py         # Project timeline generation
│   │   │
│   │   └── workers/
│   │       ├── celery_app.py   # Celery config + beat schedule
│   │       └── tasks.py        # Background tasks (sync, extraction)
│   │
│   └── scripts/
│       ├── backfill_slack.py
│       ├── backfill_clickup.py
│       └── backfill_drive.py
│
└── frontend/
    ├── app/
    │   ├── page.tsx            # Oracle chat UI
    │   └── admin/page.tsx      # Admin panel (audit log + review queue)
    ├── components/
    │   ├── OracleResponse.tsx  # Citation link rendering
    │   └── CitationCard.tsx    # Source cards with freshness badges
    └── package.json
```

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embeddings | Local fastembed (BAAI/bge-small-en-v1.5) | Free, no API key, 384 dims, fast |
| Primary LLM | Gemini 2.5 Flash | Free tier, good quality |
| LLM fallback | OpenRouter free models (Gemma, Mistral, Qwen) | Zero cost, automatic failover |
| Google Auth | OAuth 2.0 browser flow | Simpler than service account JSON |
| Vector DB | Qdrant | Payload filtering (ACL), self-hosted |
| Task Queue | Celery + Redis | Reliable, scheduled tasks |
| Chunk size | 400 words, 40 overlap | Good for RAG retrieval |
| Decision confidence | 0.75+ auto-save, 0.5-0.74 review queue | Balance automation vs accuracy |

---

## v2 Roadmap — Multi-Agent System

### North Star Architecture

Transform from a pipeline-based system into an autonomous multi-agent system where specialized agents collaborate to manage organizational knowledge.

### Planned Agents

#### 1. Router/Planner Agent
- Classifies incoming questions (factual lookup, timeline, decision history, comparison, "who" questions)
- Chooses retrieval strategy (single search vs multi-search vs cross-reference)
- Decides if it needs to break a complex query into sub-queries
- Delegates to specialized agents

#### 2. Real-Time Meeting Agent
- Monitors meetings in real-time (not just post-meeting)
- Interrupts when re-litigation is detected: "This was decided on Jan 15"
- Suggests relevant context during discussions
- Auto-generates live action items

#### 3. Research Agent
- For complex questions requiring multi-hop reasoning
- Searches multiple sources, cross-references, resolves conflicts
- Builds comprehensive answers from scattered information
- Identifies information gaps

#### 4. Project Manager Agent
- Tracks action items across all meetings
- Follows up on overdue items (via Slack DM or ClickUp)
- Escalates blocked items
- Generates weekly status reports

#### 5. Onboarding Agent
- Detects new team members (from Slack joins or manual trigger)
- Builds personalized knowledge packs: project history, key decisions, team structure
- Provides progressive disclosure — doesn't dump everything at once
- Answers "why was X decided?" with full context chain

#### 6. Guardian Agent
- Continuously monitors for re-litigation across all channels
- Proactively surfaces relevant past decisions in Slack threads
- Detects decision drift (when practice diverges from recorded decisions)
- Alerts on conflicting decisions across teams

### Agent Communication
- Agents communicate via a shared message bus (Redis Streams or similar)
- Each agent has its own context/memory but can query the shared knowledge base
- Orchestrator agent routes tasks and manages agent lifecycle
- Human-in-the-loop via Slack approve/reject interactions

### Prerequisites for v2
- [ ] Slack bot fully connected (for real-time monitoring + DMs)
- [ ] ClickUp integration active (for task creation)
- [ ] Agent SDK or framework (e.g., Claude Agent SDK, LangGraph, or custom)
- [ ] Streaming LLM responses for real-time interactions
- [ ] WebSocket support for live meeting monitoring
- [ ] Proper auth system (replace hardcoded email with Clerk/OAuth)
- [ ] Paid LLM tier for higher rate limits (agent-heavy workloads)

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `QDRANT_URL` | Yes | Qdrant connection string |
| `GEMINI_API_KEY` | Yes | Google AI Studio API key (free) |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key (free fallback) |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID (for Drive/Meet) |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `OPENAI_API_KEY` | No | OpenAI key (unused currently) |
| `ANTHROPIC_API_KEY` | No | Anthropic key (unused, using Gemini/OpenRouter) |
| `SLACK_BOT_TOKEN` | No | Slack bot token (enables Slack features) |
| `SLACK_SIGNING_SECRET` | No | Slack signing secret |
| `CLICKUP_API_KEY` | No | ClickUp API key |
| `CLICKUP_TEAM_ID` | No | ClickUp team ID |
| `CLERK_SECRET_KEY` | No | Clerk auth key |
| `GOOGLE_TRANSCRIPTS_FOLDER_ID` | No | Specific Drive folder for transcripts |

---

## Data Flow

### Ingestion
```
Google Drive/Meet → list files → check modified time → skip unchanged
  → extract text (export/download) → fetch edit history + revisions
  → generate AI summary (meetings only)
  → split into 400-word chunks → embed locally (fastembed)
  → upsert to Qdrant + PostgreSQL
  → extract decisions → route by confidence
```

### Query (Oracle)
```
User question → check Redis cache → embed question
  → Qdrant vector search (top 24) → ACL filter
  → re-rank (0.7 vector + 0.3 keyword overlap)
  → top 8 chunks → LLM synthesis with citations
  → cache result → log to audit table → return
```

### Meeting Processing
```
Gemini meeting notes in Drive → detect "Notes by Gemini" files
  → export text → AI generates structured summary:
    - Summary (2-4 sentences)
    - Key decisions (with who/context)
    - Action items (with assignee/deadline/priority)
    - Key takeaways
    - Follow-ups needed
  → store enriched text + metadata in knowledge base
  → high-priority action items → review queue
  → decisions → DecisionRecord table
```
