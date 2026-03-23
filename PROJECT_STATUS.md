# Knowledge Agent — Project Status & Goals

> **Last updated**: 2026-03-23
> **Owner**: Sachin Kurup (sachin.kurup@seedlinglabs.com)
> **Company**: Seedling Labs

---

## Vision

An AI-powered **Internal Knowledge & Decision Memory Agent** that ingests ALL company communication (Drive, Meet, Slack, ClickUp, Gmail, Calendar), extracts decisions and context, answers natural language questions with citations, and **proactively prevents redundant conversations** by alerting users when something has already been discussed — with timestamps, source links, and summaries.

**North Star**: A fully autonomous multi-agent system that reasons across all company data, understands organizational context, proactively informs team members of prior decisions, onboards new hires, manages action items, and acts as the company's living institutional brain — all without manual intervention.

---

## Current Architecture

```
Frontend (Next.js 14 + Tailwind)
  │  Multi-turn chat UI + Admin panel
  │
FastAPI Backend
  ├── Multi-Agent System
  │   ├── Router Agent (LLM-based query classification + temporal analysis)
  │   ├── Research Agent (multi-hop reasoning, meeting isolation, topic filtering)
  │   └── Onboarding Agent (personalized knowledge packs for new hires)
  │
  ├── Data Sources (ingested into unified knowledge base)
  │   ├── Google Drive (Docs, Sheets, Slides, PDFs, text, markdown)
  │   ├── Google Meet transcripts (AI summaries, decisions, action items)
  │   ├── Google Calendar (upcoming + recent events)
  │   ├── Slack (built, not connected)
  │   └── ClickUp (built, not connected)
  │
  ├── Intelligence Layer
  │   ├── RAG pipeline (embed → search → ACL filter → re-rank → synthesize)
  │   ├── Decision extraction (auto-save ≥0.75, review queue 0.50-0.74)
  │   ├── Re-litigation detection (cosine similarity ≥0.82)
  │   ├── Ghost documentation (informal decision capture)
  │   └── Temporal intelligence (LLM-extracted date ranges + freshness boost)
  │
  ├── LLM Strategy (3-tier fallback, all free)
  │   ├── Tier 1: Gemini 2.5 Flash → 2.0 Flash → 2.5 Flash Lite
  │   ├── Tier 2: Groq (Llama 3.3 70B → Gemma2 9B → Llama 3.1 8B) — 14,400 req/day
  │   └── Tier 3: OpenRouter free (Gemma 3 27B → Gemma 3 4B → Mistral Small 3.1)
  │
  └── Infrastructure
      ├── PostgreSQL 15 (documents, chunks, decisions, audit log, review queue)
      ├── Qdrant (vector search, 384-dim BAAI/bge-small-en-v1.5)
      ├── Redis (cache + Celery broker)
      └── Celery worker + beat (30-min sync cycles)
```

---

## Feature Status

### Data Ingestion

| Source | Status | Details |
|--------|--------|---------|
| Google Drive | DONE | OAuth 2.0, 30-min auto-sync, incremental (skip unchanged), edit history + revisions |
| Google Meet | DONE | Auto-discovers Gemini notes, AI summaries with decisions/action items/takeaways |
| Google Calendar | DONE | 30 days ahead + 7 behind, IST timestamps, attendees, meet links, 30-min sync |
| Manual Transcripts | DONE | VTT/SRT upload with speaker detection |
| Slack | BUILT, NOT CONNECTED | Code exists, needs bot token. Will enable real-time monitoring + Guardian Agent |
| ClickUp | BUILT, NOT CONNECTED | Code exists, needs API key |
| Gmail | SKIPPED | Privacy concern — company email contains personal/sensitive content. Drive + Meet + Calendar + Slack covers 90%+ of company knowledge. May revisit with opt-in label-based filtering. |

### Multi-Agent System

| Agent | Status | What It Does |
|-------|--------|--------------|
| Router/Planner | DONE | LLM-based query classification, temporal analysis (date ranges, recency), topic keyword extraction, conversation context for follow-ups |
| Research Agent | DONE | Multi-hop reasoning, LLM-generated search angles, meeting isolation (prevents mixing), topic filtering, cross-source synthesis with citations |
| Onboarding Agent | DONE | Personalized knowledge packs for new hires — project history, key decisions, team structure |
| Orchestrator | DONE | Agent selection, session management, multi-turn conversation support |
| Guardian Agent | NOT STARTED | Cross-source proactive alerts (see below) |
| Project Manager Agent | NOT STARTED | Action item tracking, follow-up reminders, weekly status reports |
| Real-Time Meeting Agent | NOT STARTED | Live meeting monitoring, real-time re-litigation alerts |

### Intelligence Features

| Feature | Status | Details |
|---------|--------|---------|
| Three-tier RBAC | DONE | Admin / Group Admin / Member roles; ACL supports public, group:<id>, user:<email>, legacy email |
| Scoped document upload | DONE | POST /api/ingest/upload with public/group/private scope; PDF + text support |
| User & Group management | DONE | Full CRUD; group memberships with group_admin role; frontend Users + Groups tabs |
| Meet discrepancy detection | DONE | Compares new meeting decisions vs active DecisionRecords (embed + LLM classify); flags contradictions, updates, reconfirmations |
| Context optimization | DONE | chunk_type field (summary/decision/action_item/full_text); summary chunks boosted +0.12, decision +0.10; meeting summaries stored as separate priority chunks |
| RAG with citations | DONE | Semantic search → ACL filter → re-rank → LLM synthesis, `[N]` citation format |
| Multi-turn conversation | DONE | Session IDs, conversation history in Router + Research prompts, chatbot UI |
| Temporal intelligence | DONE | LLM extracts date ranges from natural language ("last week", "yesterday"), freshness boost for recency queries |
| Topic filtering | DONE | Router extracts keywords, Research Agent filters chunks to isolate specific meetings/topics |
| Meeting isolation | DONE | Groups chunks by title, parses dates, returns only chunks from the most recent matching meeting |
| Decision extraction | DONE | AI identifies decisions, routes by confidence (≥0.75 auto-save, 0.50-0.74 review queue) |
| Re-litigation detection | DONE | Cosine similarity ≥0.82 against active decisions |
| Ghost documentation | DONE | Detects informal decisions, prompts users to confirm |
| IST timestamps | DONE | All dates/times in DD/MM/YYYY IST (GMT+5:30) via `app/core/timezone.py` |
| Speaker attribution | DONE | Meeting summaries attribute statements to specific people (who said what). LLM extracts `raised_by`, `assigned_by`, `other_contributors` per discussion point. |
| Source-type boosting | DONE | Meet/transcript chunks boosted 1.3x, calendar chunks penalized 0.5x for meeting content queries |
| Acronym buster | DONE | Glossary + AI-powered term lookup |
| Cross-source redundancy prevention | NOT STARTED | Guardian Agent feature (see Goals section) |
| Entity linking / knowledge graph | NOT STARTED | Auto-link Slack discussion → ClickUp task → Drive doc about same topic. Unified cross-source graph. |
| Version awareness (draft vs final) | NOT STARTED | Distinguish between draft docs and finalized decisions. Prevent retrieving outdated drafts as truth. |
| Drift detection | NOT STARTED | Flag when actions (ClickUp tasks, code) contradict recorded decisions. Notify relevant leads. |
| No-index zones | NOT STARTED | Ability to mark Slack channels or Drive folders as excluded from ingestion (HR, M&A, personal). |
| User feedback on answers | DONE | Thumbs up/down on every Oracle answer. Stored in `answer_feedback` table. Viewable in admin Feedback tab. **Feedback-driven learning**: chunks used in helpful answers get score boost (+0.02), not helpful get penalty (-0.02), clamped to [-0.2, 0.2]. Applied during search re-ranking. |
| Decision reversal tracking | DONE | `superseded_by`, `superseded_at`, `reversal_reason` fields on DecisionRecord. Auto-detection via semantic similarity + LLM confirmation during extraction/approval. Manual reversal via admin API. Full chain history. Agents surface reversal timeline in answers. |
| Success metrics dashboard | DONE | Admin Metrics tab: total queries, daily usage chart, avg confidence, avg response time, agent/query type breakdown, feedback helpfulness rate. |

### Frontend

| Feature | Status | Details |
|---------|--------|---------|
| Chat UI | DONE | Multi-turn conversation, message thread, session tracking, auto-scroll |
| Markdown rendering | DONE | react-markdown for bold, bullets, headers |
| Clickable citations | DONE | `[N]` badges link to source URLs |
| Agent metadata bar | DONE | Shows agent name, query type, confidence |
| Collapsible sources | DONE | `<details>` toggle for source list |
| Admin panel | DONE | 4 tabs: Metrics, Audit Log, Review Queue, Feedback |

### Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| PostgreSQL | DONE | Port 5433, documents/chunks/decisions/audit/review tables |
| Qdrant | DONE | 384-dim vectors, payload filtering |
| Redis | DONE | Cache + Celery broker |
| Celery beat | DONE | Drive (30 min), Meet (30 min), Calendar (30 min), Decisions (daily) |
| LLM fallback chain | DONE | Gemini → Groq → OpenRouter (3 tiers, all free) |
| Local embeddings | DONE | fastembed BAAI/bge-small-en-v1.5, zero API cost |

---

## Goals & Roadmap

### Priority 1 — Guardian Agent (Cross-Source Redundancy Prevention)

**Goal**: When a user posts a message (Slack) or creates a task (ClickUp) or writes a doc (Drive), the system automatically checks if this topic has been discussed before ANYWHERE in the company — Slack, Drive, Meet, Calendar, Gmail — and proactively alerts the user.

**How it works**:
```
User action (Slack message / ClickUp task / Drive doc edit)
  → Webhook fires to backend
  → Embed the text
  → Vector similarity search across ALL chunks (all sources)
  → ACL filter (only show what this user has access to)
  → If high-confidence match (score > 0.85):
      → Pull original source: timestamp, link, summary
      → Reply in-context:
          - Slack: thread reply with cross-source summary
          - ClickUp: comment on task
          - Drive: comment on document
      → Include: date, source location, summary, link to full conversation
      → Ask: "This was already discussed. Want to see the full context?"
```

**What the user sees** (example Slack reply):
> This topic was already discussed:
> - **Google Doc**: [Product Pricing v3](link) — Section 2 covers this
> - **Slack #product**: [Thread by Mihir on 15/02/2026](link) — confirmed final pricing
> - **Meeting**: LeadSquared standup 14/02/2026 — **Akanksha** raised this, **Krithin** approved
>
> Want me to pull the full context?

**Prerequisites**: Slack bot token connected, webhooks for real-time events

### Priority 2 — Slack Integration (Full)

**Goal**: Connect the Slack bot for real-time message ingestion + Guardian Agent delivery channel.

**What's needed**:
- Slack bot token (`SLACK_BOT_TOKEN`)
- Slack signing secret (`SLACK_SIGNING_SECRET`)
- Slack Events API webhook endpoint
- User identity mapping: Slack user ID → email (for ACL)
- Channel membership caching (for ACL)

**Already built**: `app/services/slack_ingestion.py`, `app/main.py` has Slack event handlers

### ~~Priority 3 — User Permissions / Consent Dashboard~~ DONE (Three-Tier RBAC)

**Implemented as three-tier role system** — see Three-Tier Access Control section above.

---

### Three-Tier Access Control

**Status: DONE**

| Model | Status | Details |
|-------|--------|---------|
| `User` | DONE | email, display_name, role (admin/group_admin/member) |
| `Group` | DONE | name, description, created_by_email |
| `GroupMembership` | DONE | user_email → group_id with role |
| ACL engine | DONE | Admin bypass, group membership, private user docs, legacy email |
| User management API | DONE | GET/POST/PUT/DELETE /api/users |
| Group management API | DONE | GET/POST/PUT/DELETE /api/groups + /members |
| Scoped upload API | DONE | POST /api/ingest/upload (public/group/private) |
| Frontend Users tab | DONE | Add users, set roles, remove users |
| Frontend Groups tab | DONE | Create groups, manage members, set group admins |
| Frontend Upload tab | DONE | Scoped upload with scope selector |

**ACL format:**
- `"public"` → visible to all
- `"group:<uuid>"` → visible to group members
- `"user:<email>"` → private to that user
- `"email@domain.com"` → legacy (Drive permissions, meeting attendees)
- Admin role → bypasses all ACL checks

**Tier capabilities:**
| Tier | Role | Can do |
|------|------|--------|
| Admin | `admin` | Upload public/group/private, see all, manage users & groups |
| Team Leader | `group_admin` | Upload for their group, see public + group + own private |
| Individual | `member` | Upload private docs (can share selectively), see public + group + own |

---

### Original Priority 3 — User Permissions / Consent Dashboard

**Goal**: When users install the product, they can choose which integrations the system can access (Google Drive, Calendar, Slack, ClickUp, etc.). Per-user toggles for read/write access.

**What it looks like**:
- Settings page in the frontend with toggle switches per integration
- User connects their accounts individually (OAuth per service)
- Each user's enabled integrations stored in the database
- Sync logic only processes sources the user has enabled
- Admin can see which users have connected which integrations

**What's needed**:
- Proper user auth system (Clerk integration or similar — key already exists)
- `UserIntegration` database model (user_id, integration_name, enabled, oauth_token, connected_at)
- Settings API endpoints (GET/PUT per integration)
- Frontend settings page with OAuth connect buttons + toggles
- Conditional sync: check user's enabled integrations before syncing their data
- Per-user OAuth tokens (currently shared single token for all)

**Prerequisites**: User authentication system (Clerk), per-user token storage

### Priority 4 — Project Manager Agent

**Goal**: Track action items from meetings across time, follow up on overdue items, generate weekly status reports.

**What it does**:
- Extracts action items from meeting summaries (already partially done in decision_extractor)
- Tracks assignee + deadline + status
- Sends follow-up reminders via Slack DM when items are overdue
- Generates weekly digest: what was completed, what's overdue, what's blocked
- Escalates blocked items to managers

**Prerequisites**: Slack bot connected (for DM delivery), ClickUp connected (for task creation)

### Priority 5 — Real-Time Meeting Agent

**Goal**: Monitor meetings in real-time and provide live context/alerts.

**What it does**:
- Listens to live meeting transcription stream
- Detects re-litigation in real-time: "This was decided on Jan 15"
- Suggests relevant docs/decisions during discussion
- Auto-generates live action items
- Post-meeting: immediately processes and syncs

**Prerequisites**: WebSocket support, streaming LLM, live transcription API access

### Priority 6 — Authorization & User Identity

**Current state**: Email-based ACL (if your email is on the doc/channel/meeting, you can see it)

**Future options**:
- **Simple (sufficient for now)**: Email-based ACL across all sources. Slack user ID → email mapping.
- **Role-based (later if needed)**: GreytHR API integration to pull org structure (manager → reports chain). Managers see their reports' content.
- **Drive permissions**: Drive Permissions API per file → real ACL with email addresses. Files with link sharing → `["public"]`, restricted files → list of emails with access.

**Decision**: Email-based ACL is sufficient for current team size. Revisit when departments need data isolation.

### Priority 7 — Entity Linking / Knowledge Graph

**Goal**: Automatically connect related items across sources. When a Slack thread mentions "Project X", link it to the ClickUp task and Google Doc spec for "Project X" — creating a unified knowledge graph.

**How it works**:
- Extract entity names (projects, people, features) from every chunk during ingestion
- Build a graph of entity → chunks relationships in Postgres or a dedicated graph store
- When searching, pull related chunks from linked entities (not just vector similarity)
- Enables queries like "Show me everything about Project X" across all sources

**Prerequisites**: Entity extraction improvements (currently regex-based), Slack + ClickUp connected

### Priority 8 — Version Awareness (Draft vs Finalized)

**Goal**: Distinguish between draft documents and finalized decisions. Prevent the agent from presenting outdated drafts as truth.

**How it works**:
- Tag documents with status: `draft`, `in_review`, `finalized`, `superseded`
- For Google Drive: detect "DRAFT" in title/content, check sharing settings (restricted = likely draft)
- For decisions: already have `active`/`superseded` status in DecisionRecord
- In RAG responses: clearly label draft sources and prioritize finalized content

### Priority 9 — No-Index Zones

**Goal**: Allow admins to mark specific Slack channels, Drive folders, or ClickUp spaces as excluded from ingestion.

**What's needed**:
- Admin UI with a list of connected sources and toggle to exclude
- `ExclusionRule` model in database (source_type, identifier, reason)
- Check exclusion rules during sync before ingesting content
- Examples: HR channel, salary docs folder, M&A discussions

### Priority 10 — User Feedback on Answers

**Goal**: Let users thumbs-up/thumbs-down Oracle answers to improve quality over time.

**What's needed**:
- Frontend: thumbs up/down buttons on each response
- Backend: `AnswerFeedback` model (query, answer, rating, user_email, timestamp)
- Analytics: surface low-rated answers in admin panel for review
- Future: use feedback to fine-tune retrieval (boost chunks from good answers, penalize from bad)

### ~~Priority 11 — Decision Reversal Tracking (Living History)~~ DONE

Implemented: `superseded_by`, `superseded_at`, `reversal_reason` columns on DecisionRecord. Auto-detection during ingestion/approval via semantic similarity (≥0.80) + LLM confirmation. Manual reversal via `POST /api/admin/decisions/{id}/reverse`. Full chain history via `GET /api/admin/decisions/{id}/history`. Research + Onboarding agents surface reversal timeline in answers.

### Priority 12 — Drift Detection

**Goal**: If the team starts doing something that contradicts a recorded decision, flag the inconsistency.

**How it works**:
- Monitor new ClickUp tasks, Slack messages, and Drive docs against active decisions
- Use semantic similarity between new content and decision text
- If high similarity + contradicting intent detected → alert relevant leads
- Harder than re-litigation detection (requires understanding intent, not just topic overlap)

**Prerequisites**: Guardian Agent, Slack connected, ClickUp connected

### Priority 13 — Success Metrics Dashboard

**Goal**: Track and display the PRD's success metrics in the admin panel.

**Metrics**:
- **Deflection Rate**: Track "Has this been asked before?" patterns. Compare repeated question frequency over time.
- **Retrieval Time**: Measure time from query to answer delivery (target: <30 seconds)
- **Decision Adherence**: Track how often re-litigation alerts are triggered (lower = better adherence)
- **Usage**: Queries per day, unique users, most-queried topics
- **Quality**: Average confidence score, user feedback ratings

**What's needed**:
- Aggregate audit log data into daily/weekly metrics
- New admin panel tab: "Metrics" with charts
- Baseline measurement before vs after deployment

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embeddings | Local fastembed (BAAI/bge-small-en-v1.5) | Free, no API key, 384 dims, fast |
| Primary LLM | Gemini 2.5 Flash | Free tier, best quality among free options |
| LLM fallback | Groq (14,400 req/day) → OpenRouter free | Zero cost, automatic failover, 3 tiers |
| Google Auth | OAuth 2.0 browser flow | Simpler than service account |
| Vector DB | Qdrant | Payload filtering (ACL), self-hosted |
| Task Queue | Celery + Redis | Reliable scheduled tasks |
| Chunk size | 400 words, 40 overlap | Good for RAG retrieval |
| Decision confidence | 0.75+ auto-save, 0.5-0.74 review | Balance automation vs accuracy |
| Temporal analysis | LLM-based (no hardcoded keywords) | Generic for any user/query type |
| Timestamps | DD/MM/YYYY IST (GMT+5:30) | Indian format, consistent everywhere |
| Multi-turn chat | Session-based with history in prompts | Enables follow-up questions with context |
| Agent framework | Custom (not LangGraph/CrewAI) | Lightweight, no extra dependencies |

---

## Environment Variables

| Variable | Required | Status | Description |
|----------|----------|--------|-------------|
| `DATABASE_URL` | Yes | SET | PostgreSQL connection |
| `REDIS_URL` | Yes | SET | Redis connection |
| `QDRANT_URL` | Yes | SET | Qdrant connection |
| `GEMINI_API_KEY` | Yes | SET | Google AI Studio (free) |
| `GROQ_API_KEY` | Yes | SET | Groq API (14,400 req/day free) |
| `OPENROUTER_API_KEY` | Yes | SET | OpenRouter (free fallback) |
| `GOOGLE_CLIENT_ID` | Yes | SET | Google OAuth (Drive + Calendar) |
| `GOOGLE_CLIENT_SECRET` | Yes | SET | Google OAuth secret |
| `OPENAI_API_KEY` | No | SET | Unused currently |
| `ANTHROPIC_API_KEY` | No | SET | Unused currently |
| `SLACK_BOT_TOKEN` | No | NOT SET | Needed for Slack integration |
| `SLACK_SIGNING_SECRET` | No | NOT SET | Needed for Slack integration |
| `CLERK_SECRET_KEY` | No | SET | Auth (future use) |

---

## File Map

```
knowledge_system/
├── PROJECT_STATUS.md          # THIS FILE — living project tracker
├── PRD.md                     # Original PRD (v1 spec, partially outdated)
├── CLAUDE.md                  # Compact project context for Claude Code
│
├── backend/
│   ├── .env                   # API keys and config
│   ├── google_token.json      # Google OAuth token (auto-generated)
│   │
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, Slack handlers
│   │   │
│   │   ├── core/
│   │   │   ├── config.py      # Pydantic Settings (all env vars)
│   │   │   ├── database.py    # SQLAlchemy engine + session
│   │   │   ├── acl.py         # ACL enforcement (email-based)
│   │   │   └── timezone.py    # IST timezone utilities (DD/MM/YYYY, GMT+5:30)
│   │   │
│   │   ├── agents/
│   │   │   ├── base.py        # AgentContext + AgentResult dataclasses
│   │   │   ├── orchestrator.py# Agent selection, session management, multi-turn
│   │   │   ├── router.py      # LLM-based query classification + temporal analysis
│   │   │   ├── research.py    # Multi-hop reasoning, meeting isolation, topic filter
│   │   │   └── onboarding.py  # Personalized knowledge packs
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py    # Document, Chunk, DecisionRecord, AuditLog
│   │   │   └── review_queue.py# ReviewQueueItem model
│   │   │
│   │   ├── api/
│   │   │   ├── oracle.py      # POST /api/oracle/ask (multi-turn chat)
│   │   │   ├── admin.py       # Audit log + review queue
│   │   │   ├── transcripts.py # VTT/SRT upload
│   │   │   └── ingestion.py   # Manual ingestion trigger (drive/meet/calendar/slack/clickup)
│   │   │
│   │   ├── services/
│   │   │   ├── llm.py              # 3-tier LLM fallback (Gemini → Groq → OpenRouter)
│   │   │   ├── oracle.py           # Legacy RAG pipeline (pre-agent)
│   │   │   ├── embeddings.py       # fastembed + Qdrant + freshness boost + date filtering
│   │   │   ├── chunker.py          # Text splitting + document storage + ingested_at timestamps
│   │   │   ├── entity_extractor.py # Regex entity extraction
│   │   │   ├── drive_ingestion.py  # Google Drive OAuth + incremental sync + edit history
│   │   │   ├── meet_ingestion.py   # Meeting transcript processing + AI summaries
│   │   │   ├── calendar_sync.py    # Google Calendar sync (events, attendees, meet links)
│   │   │   ├── slack_ingestion.py  # Slack message ingestion (needs bot token)
│   │   │   ├── clickup_ingestion.py# ClickUp task ingestion (needs API key)
│   │   │   ├── decision_extractor.py# AI decision extraction + confidence routing
│   │   │   ├── ghost_docs.py       # Ghost documentation prompts
│   │   │   ├── relitigation_detector.py # Re-litigation detection
│   │   │   ├── acronym_buster.py   # Term/acronym definitions
│   │   │   └── timeline.py         # Project timeline generation
│   │   │
│   │   └── workers/
│   │       ├── celery_app.py  # Celery config + beat schedule (Drive/Meet/Calendar every 30 min)
│   │       └── tasks.py       # Background tasks (sync, extraction, calendar)
│   │
│   └── scripts/
│       ├── backfill_slack.py
│       ├── backfill_clickup.py
│       └── backfill_drive.py
│
└── frontend/
    ├── app/
    │   ├── page.tsx            # Multi-turn chat UI with session tracking
    │   └── admin/page.tsx      # Admin panel (audit log + review queue)
    ├── components/
    │   ├── OracleResponse.tsx  # react-markdown + clickable [N] citation badges
    │   └── CitationCard.tsx    # Source cards with freshness badges
    └── package.json
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-23 | Three-tier RBAC: User/Group/GroupMembership models, ACL overhaul (admin bypass, group:<uuid>, user:<email>), User+Group management APIs + frontend tabs |
| 2026-03-23 | Scoped document upload: POST /api/ingest/upload with public/group/private scope + PDF extraction |
| 2026-03-23 | Meet discrepancy detection: new meeting decisions compared against all active DecisionRecords via cosine similarity + LLM classification (CONTRADICTION/UPDATE/RECONFIRMATION) |
| 2026-03-23 | Context optimization: chunk_type field on Chunk model + Qdrant payload; summary/decision chunks boosted in search ranking; meeting summaries stored as separate high-priority chunks |
| 2026-03-23 | Frontend: Users tab (add/role/remove), Groups tab (create/member management), Upload tab (scoped upload with scope selector) |
| 2026-03-13 | Drive ACL: real per-file permissions from Drive Permissions API (replaces hardcoded "public") |
| 2026-03-12 | Decision reversal tracking: auto-detection, manual reversal API, chain history, agents surface reversals in answers |
| 2026-03-12 | Feedback-driven learning: chunk scores adjust based on user helpful/not helpful ratings |
| 2026-03-12 | User feedback system: thumbs up/down on answers, AnswerFeedback model, admin Feedback tab |
| 2026-03-12 | Metrics dashboard: overview cards, daily usage chart, agent/query type breakdown, feedback stats |
| 2026-03-12 | Enriched audit logs: agent, query_type, confidence, response_time_ms now tracked per query |
| 2026-03-12 | PRD gap analysis: added 7 missing features to roadmap (entity linking, version awareness, no-index, feedback, drift detection, decision reversal, metrics) |
| 2026-03-12 | Gmail integration skipped (privacy concern), added User Permissions Dashboard to roadmap |
| 2026-03-12 | Fix: speaker attribution in meeting summaries (discussion_points with raised_by) |
| 2026-03-12 | Fix: source-type boosting (meet > calendar for content queries) |
| 2026-03-12 | Fix: text_preview increased from 500 to 2000 chars (transcript content no longer truncated) |
| 2026-03-12 | PROJECT_STATUS.md created as living project tracker |
| 2026-03-12 | Google Calendar integration (sync + Celery task + API endpoint) |
| 2026-03-12 | Groq added to LLM fallback chain (14,400 req/day free) |
| 2026-03-12 | Multi-turn conversation (session IDs, history in prompts) |
| 2026-03-12 | Meeting isolation (prevents mixing chunks from different meetings) |
| 2026-03-12 | Topic filtering (Router extracts keywords, Research filters) |
| 2026-03-12 | IST timezone module (`app/core/timezone.py`) |
| 2026-03-12 | Speaker attribution in meeting summaries |
| 2026-03-12 | Citation format: `[SOURCE_N]` → `[N]` with clickable badges |
| 2026-03-12 | Frontend: react-markdown, multi-turn chat UI |
| 2026-03-12 | Multi-agent system: Router, Research, Onboarding agents |
| 2026-03-12 | LLM-based temporal intelligence (no hardcoded keywords) |
| 2026-03-11 | v1 MVP: Drive sync, Meet transcripts, Oracle RAG, Decision extraction |
