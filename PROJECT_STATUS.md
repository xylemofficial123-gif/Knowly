# Knowledge Agent — Project Status & Goals

> **Last updated**: 2026-05-03 (Entity Linking / Knowledge Graph: gazetteer + doc-level LLM extraction, Research Agent cross-source graph augmentation)
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
| Google Drive | DONE | Per-user OAuth 2.0 (DB connection), 30-min auto-sync, incremental (skip unchanged), edit history + revisions |
| Google Meet | DONE | Per-user OAuth 2.0 (DB connection), auto-discovers Gemini notes, AI summaries with decisions/action items/takeaways |
| Google Calendar | DONE | Per-user OAuth 2.0 (DB connection), 30 days ahead + 7 behind, IST timestamps, attendees, meet links, 30-min sync |
| Manual Transcripts | DONE | VTT/SRT upload with speaker detection |
| Slack | DONE | OAuth 2.0 connected, real-time message ingestion, `/oracle` slash command for querying, Guardian alerts as thread replies, ghost doc prompts via DM |
| ClickUp | DONE | OAuth 2.0 connected (excylem@gmail.com workspace), real-time webhook, member-email ACL |
| Google (OAuth) | DONE | Per-user OAuth 2.0 at /api/oauth/google/authorize — connects individual accounts for Drive/Meet/Calendar ingestion. Auto-refreshes tokens via refresh_token. |
| Gmail | SKIPPED | Privacy concern — company email contains personal/sensitive content. Drive + Meet + Calendar + Slack covers 90%+ of company knowledge. May revisit with opt-in label-based filtering. |

### Multi-Agent System

| Agent | Status | What It Does |
|-------|--------|--------------|
| Router/Planner | DONE | LLM-based query classification, temporal analysis (date ranges, recency), topic keyword extraction, conversation context for follow-ups |
| Research Agent | DONE | Multi-hop reasoning, LLM-generated search angles, meeting isolation (prevents mixing), topic filtering, cross-source synthesis with citations |
| Onboarding Agent | DONE | Personalized knowledge packs for new hires — project history, key decisions, team structure |
| Orchestrator | DONE | Agent selection, session management, multi-turn conversation support |
| Guardian Agent | DONE | Cross-source redundancy prevention + drift detection — embeds trigger text, searches all sources, ACL filters, LLM-synthesises alert, checks for decision contradictions, delivers as Slack thread reply or ClickUp comment, logs to `guardian_alerts` table |
| Project Manager Agent | NOT STARTED | Action item tracking, follow-up reminders, weekly status reports |

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
| Ghost documentation | DONE | Detects informal decisions, DMs the owner on Slack to confirm. Fires from (a) Slack messages → poster, (b) Google Meet transcripts → meeting owner via `users.lookupByEmail`. Approval writes a `DecisionRecord` with ACL inherited from the source chunk/meeting attendees. Participants stored as email (resolved via `users.info`), not Slack user ID. |
| DecisionRecord ACL | DONE | `decision_records.acl` JSON column mirrors source chunk ACL. Filtered in user-facing reads: Research agent decision context, Onboarding agent decision context, `/api/admin/decisions` list (when `user_email` query param is supplied — frontend `/decisions` page passes it). System-level reads (re-litigation detector, drift detector, Meet discrepancy, reversal detection) intentionally see all decisions to do their job — alert delivery sites are still gated by the original chunk ACL. |
| IST timestamps | DONE | All dates/times in DD/MM/YYYY IST (GMT+5:30) via `app/core/timezone.py` |
| Speaker attribution | DONE | Meeting summaries attribute statements to specific people (who said what). LLM extracts `raised_by`, `assigned_by`, `other_contributors` per discussion point. |
| Source-type boosting | DONE | Meet/transcript chunks boosted 1.3x, calendar chunks penalized 0.5x for meeting content queries |
| Acronym buster | DONE | Glossary + AI-powered term lookup |
| Cross-source redundancy prevention | DONE | Guardian Agent: threshold 0.78, dedup by document, ACL-filtered, LLM alert, Slack thread reply + ClickUp comment delivery, `guardian_alerts` audit table, `POST /api/guardian/check` + `GET /api/guardian/alerts` |
| Entity linking / knowledge graph | DONE | `Entity` + `EntityMention` Postgres tables. Background Celery task `extract_entities_for_document` runs after chunk_and_store: gazetteer-first scan against existing entities, then one LLM call per document to discover new ones (doc-level, not per-chunk). Research Agent's Phase 1.4 augments vector hits with chunks mentioning matched entities from any source — the cross-source connective tissue. ACL-filtered, source-enablement-filtered. |
| Version awareness (draft vs final) | DONE | `doc_status` field on Document model (draft/in_review/finalized/unknown). Drive: title/content heuristics. ClickUp: maps task `status` field — closed/done/complete → finalized, review/qa → in_review, to_do/in_progress → draft. Slack: heuristic — pinned messages → finalized; "let's go with"/"approved"/"decided" → finalized; "wip"/"thinking about"/"wondering" → draft; otherwise unknown. Drafts penalized 0.6x in search, in_review 0.85x. LLM prompts label draft sources explicitly. |
| Drift detection | DONE | `drift_detector.py` compares new Slack/ClickUp content against active DecisionRecords via cosine similarity (≥0.72) + LLM classification (CONTRADICTS/ALIGNED/UNRELATED). Integrated into Guardian check pipeline. Drift alerts delivered alongside Guardian alerts. Manual check via `POST /api/guardian/drift-check`. |
| No-index zones | DONE | `ExclusionRule` model (source_type, identifier, name, reason). Admin CRUD API at `/api/admin/exclusion-rules`. In-memory cache refreshed per sync cycle. Enforced during Drive folder scan, Slack message ingestion + backfill, ClickUp space traversal. Frontend No-Index Zones tab for managing rules. |
| Hallucination guardrails | DONE | All LLM prompts (Oracle, Research, Onboarding) enforce citation-only answers. Explicit "I cannot find a record" fallback when no sources match. Never invents rationale or context. |
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
| Admin panel | DONE | 10 tabs: Connections, Metrics, Audit Log, Review Queue, Feedback, Ingestion, Users, Groups, Upload, No-Index Zones |

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

### ~~Priority 5 — Real-Time Meeting Agent~~ DROPPED

Removed 2026-04-28. A WebSocket "live meeting" UI was built but misread the PRD: the PRD's "Ghost Documentation" feature is an *async scribe over already-ingested transcripts* (Slack DM with approve/reject), not a live mid-meeting copilot. Ghost Documentation is already DONE via `app/services/ghost_docs.py` + `workers/tasks.py`. Mid-meeting live context is not a PRD goal.

### Priority 6 — Authorization & User Identity

**Current state**: Email-based ACL (if your email is on the doc/channel/meeting, you can see it)

**Future options**:
- **Simple (sufficient for now)**: Email-based ACL across all sources. Slack user ID → email mapping.
- **Role-based (later if needed)**: GreytHR API integration to pull org structure (manager → reports chain). Managers see their reports' content.
- **Drive permissions**: Drive Permissions API per file → real ACL with email addresses. Files with link sharing → `["public"]`, restricted files → list of emails with access.

**Decision**: Email-based ACL is sufficient for current team size. Revisit when departments need data isolation.

### ~~Priority 7 — Entity Linking / Knowledge Graph~~ DONE

Implemented: `Entity` + `EntityMention` tables (`app/models/__init__.py`). `app/services/entity_extractor.py` does gazetteer-first scan against existing entity names + aliases, falling back to **one LLM call per document** (not per chunk) to discover new entities — keeps free-tier quota usage low. `extract_entities_for_document` Celery task fires from `chunk_and_store` so ingestion stays non-blocking. Research Agent Phase 1.4 (`app/agents/research.py`) finds entities in the user's query and augments vector-search hits with up to 8 chunks linked via `entity_mentions` from any source, ACL-filtered. Self-improving: each ingestion expands the gazetteer so subsequent ingestions need fewer LLM calls.

### ~~Priority 8 — Version Awareness (Draft vs Finalized)~~ DONE

Implemented: `doc_status` field on Document model + Qdrant payload (`draft`, `in_review`, `finalized`, `unknown`). Auto-detection during Drive ingestion via title/content heuristics (detects "DRAFT", "WIP", "for review", "RFC", etc.). Drafts penalized 0.6x in RAG search scoring, in_review 0.85x. LLM prompts label draft sources and warn users. Applied in both Research Agent and Oracle service.

### ~~Priority 9 — No-Index Zones~~ DONE

Implemented: `ExclusionRule` model with unique constraint on (source_type, identifier). Admin CRUD API at `GET/POST/DELETE /api/admin/exclusion-rules`. In-memory cache (`exclusion_service.py`) refreshed at start of each sync cycle. Enforced in: Drive folder tree traversal (skips excluded folders + subfolders), Slack message ingestion + event handler + backfill, ClickUp space traversal. Frontend "No-Index Zones" tab in admin panel for managing rules.

### Priority 10 — User Feedback on Answers

**Goal**: Let users thumbs-up/thumbs-down Oracle answers to improve quality over time.

**What's needed**:
- Frontend: thumbs up/down buttons on each response
- Backend: `AnswerFeedback` model (query, answer, rating, user_email, timestamp)
- Analytics: surface low-rated answers in admin panel for review
- Future: use feedback to fine-tune retrieval (boost chunks from good answers, penalize from bad)

### ~~Priority 11 — Decision Reversal Tracking (Living History)~~ DONE

Implemented: `superseded_by`, `superseded_at`, `reversal_reason` columns on DecisionRecord. Auto-detection during ingestion/approval via semantic similarity (≥0.80) + LLM confirmation. Manual reversal via `POST /api/admin/decisions/{id}/reverse`. Full chain history via `GET /api/admin/decisions/{id}/history`. Research + Onboarding agents surface reversal timeline in answers.

### ~~Priority 12 — Drift Detection~~ DONE

Implemented: `drift_detector.py` service. Compares new content against all active DecisionRecords via cosine similarity (≥0.72 threshold) + LLM classification (CONTRADICTS/ALIGNED/UNRELATED). Integrated into Guardian Agent pipeline — runs alongside redundancy check on every Slack message and ClickUp task. Drift alerts combined with Guardian alerts and delivered via Slack thread reply / ClickUp comment. Manual check via `POST /api/guardian/drift-check`. Top 5 decision candidates checked per trigger.

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
│   │   │   ├── timeline.py         # Project timeline generation
│   │   │   ├── exclusion_service.py # No-index zone enforcement (cached)
│   │   │   └── drift_detector.py   # Decision contradiction detection
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
| 2026-05-03 | Version awareness extended to ClickUp + Slack: `clickup_ingestion.ingest_task` maps task `status.status` to draft/in_review/finalized; `slack_ingestion.ingest_message` detects pinned messages + decision/draft phrase patterns. Closes the PRD feature 1.3 gap for the team's stack (Drive + ClickUp + Slack). Slack heuristics are intentionally noisy — unmatched messages stay `unknown` rather than being guessed as draft. |
| 2026-05-03 | Entity-to-entity edges + Graph view: new `EntityCooccurrence` table (entity_a_id, entity_b_id, weight) populated from `process_document_entities` whenever ≥2 entities co-occur in the same chunk. `GET /api/admin/graph` returns a new `entity_links` field (top 200 edges by weight, ACL-filtered via visible-entity intersection). Frontend: List/Graph toggle on `/graph` "Linked across sources"; Graph view is a `react-force-graph-2d` force-directed network where node size = mentions, edge thickness = co-occurrence weight, color = entity type. Uses `next/dynamic({ssr:false})` since the lib needs a browser canvas. |
| 2026-05-03 | Bugfix in entity_extractor: prompt template's literal `{"name":...}` JSON example was parsed by `str.format()` as a placeholder, raising `KeyError: '"name"'` for every doc. Escaped to `{{...}}`. Caught locally before pushing to Railway prod. |
| 2026-05-03 | Knowledge Graph UI: `/graph` page (`frontend/app/graph/page.tsx`) gets a new "Linked across sources" section listing the top 60 entities ranked by cross-source coverage, with type-filter chips (All/Project/Person/Feature/Tool/Acronym), source pills, and expandable top-doc lists. Backed by new `entities` field on `GET /api/admin/graph` (ACL-filtered to mentions inside docs the user can see). |
| 2026-05-03 | Entity Linking / Knowledge Graph: new `entities` + `entity_mentions` Postgres tables. `entity_extractor.py` rewritten with gazetteer-first scan + doc-level LLM extraction (one call per document, not per chunk — protects free-tier quota). Background `extract_entities_for_document` Celery task fires from `chunk_and_store` so ingestion stays non-blocking. Research Agent Phase 1.4 finds entities in the user's query via gazetteer match and augments vector-search hits with chunks linked via `entity_mentions` from any source (capped at 8 chunks, ACL-filtered, source-enablement-filtered). Closes the PRD "Connective Tissue" gap. |
| 2026-04-28 | Ghost Documentation now fires from Google Meet ingestion (`_maybe_send_meet_ghost_prompts` in `meet_ingestion.py`): for each extracted decision, looks up the meeting owner's Slack ID via `users.lookupByEmail` and DMs them an approve/reject prompt with the meeting attendees ACL embedded in the callback. Closes the PRD gap where verbal-decision capture was Slack-only. |
| 2026-04-28 | DecisionRecord ACL: added `decision_records.acl` JSON column (+ migration). All seven write sites set ACL: decision_extractor (chunk.acl), ghost_docs.handle_ghost_doc_approve (chunk.acl or callback override), meet_ingestion._store_action_items (attendees), admin.approve_review (source chunk acl), admin.reverse_decision (inherits from old), main.py /decision Slack command (public). User-facing reads filter via `user_can_see_chunk`: Research._get_decision_context, Onboarding._get_relevant_decisions, `GET /api/admin/decisions` (frontend `/decisions` page passes user_email). |
| 2026-04-28 | Ghost-doc participants normalized to email: `handle_ghost_doc_approve` and `/decision` Slack command resolve Slack user_id → email via `users.info` before writing `DecisionRecord.participants`. Falls back to raw Slack ID if lookup fails (no token, etc.). |
| 2026-04-28 | Removed Real-Time Meeting Agent (deleted `realtime_meeting.py`, `api/meeting.py`, `LiveMeetingSession` model, frontend `/meeting` page, sidebar entry, router registration). The live WebSocket "scribe a meeting in progress" UI conflated with PRD's Ghost Documentation, which is async-over-ingested-transcripts. Note: `live_meeting_sessions` Postgres table will linger as an orphan in already-deployed DBs — drop manually if desired. |
| 2026-04-16 | Real-Time Meeting Agent: `realtime_meeting.py` service + `api/meeting.py` WebSocket + REST endpoints. `LiveMeetingSession` model. (REMOVED 2026-04-28 — see above.) |
| 2026-04-07 | Frontend: New leafy-green auth/landing page (pitch-premium layout), `/features` marketing page, `/docs` documentation page, shared `PublicNav` component; middleware + LayoutWrapper updated for public routes |
| 2026-04-07 | No-Index Zones: `ExclusionRule` model, admin CRUD API (`/api/admin/exclusion-rules`), `exclusion_service.py` with in-memory cache, enforced in Drive/Slack/ClickUp ingestion pipelines, frontend No-Index Zones tab |
| 2026-04-07 | Version Awareness: `doc_status` field on Document + Qdrant payload, auto-detection during Drive ingestion (draft/in_review/finalized heuristics), drafts penalized 0.6x in search, LLM prompts label draft sources |
| 2026-04-07 | Drift Detection: `drift_detector.py` service, cosine similarity ≥0.72 + LLM classification against active decisions, integrated into Guardian pipeline, combined alerts, `POST /api/guardian/drift-check` |
| 2026-04-07 | Hallucination guardrails: strengthened all LLM prompts (Oracle, Research, Onboarding) with explicit "I cannot find a record" fallback and never-invent rules |
| 2026-03-24 | Guardian Agent: `app/agents/guardian.py`, `GuardianAlert` model, `process_guardian_check` Celery task, `POST /api/guardian/check` + `GET /api/guardian/alerts`. Wired into Slack `handle_message` and ClickUp webhook. Delivery: Slack thread reply (live when bot token set) and ClickUp comment. |
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
