"""
Real-Time Meeting Agent
Processes live transcript chunks via WebSocket, detects re-litigation,
forming decisions, and action items in real-time. On session end, generates
a full structured summary and stores it in the knowledge base.
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Trigger analysis after this many new unanalyzed words
WORD_THRESHOLD = 40
# Minimum seconds between consecutive analyses (avoid LLM spam)
COOLDOWN_SECS = 20
# Minimum words for a re-litigation check to be meaningful
RELITIGATION_MIN_WORDS = 20


@dataclass
class MeetingAlert:
    kind: str   # relitigation | decision_forming | action_item
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SessionState:
    session_id: str
    title: str
    user_email: str
    started_at: float
    # Rolling buffer — words since last analysis
    unanalyzed_chunks: list = field(default_factory=list)
    unanalyzed_word_count: int = 0
    last_analysis_at: float = 0
    # Full transcript for post-session summary
    all_chunks: list = field(default_factory=list)
    # Track which decision IDs we've already alerted about (avoid repeat alerts)
    seen_decision_ids: set = field(default_factory=set)


# Module-level in-memory session store (single process — safe for asyncio single-thread model)
_sessions: dict[str, SessionState] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_session(title: str, user_email: str) -> str:
    """Create a new meeting session. Returns the session_id."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = SessionState(
        session_id=session_id,
        title=title or f"Live Meeting {session_id[:8]}",
        user_email=user_email or "",
        started_at=time.time(),
    )
    _save_session_to_db(session_id, title, user_email)
    logger.info(f"Live meeting session created: {session_id}")
    return session_id


def get_session(session_id: str) -> Optional[SessionState]:
    return _sessions.get(session_id)


def add_chunk(session_id: str, speaker: str, text: str, timestamp: str) -> None:
    """Append a transcript chunk to the session state (synchronous, no analysis)."""
    state = _sessions.get(session_id)
    if not state:
        return
    chunk = {"speaker": speaker, "text": text, "timestamp": timestamp}
    state.all_chunks.append(chunk)
    state.unanalyzed_chunks.append(chunk)
    state.unanalyzed_word_count += len(text.split())


def should_analyze(session_id: str) -> bool:
    """Return True if the buffer is full and cooldown has passed."""
    state = _sessions.get(session_id)
    if not state:
        return False
    now = time.time()
    return (
        state.unanalyzed_word_count >= WORD_THRESHOLD
        and (now - state.last_analysis_at) >= COOLDOWN_SECS
    )


def drain_buffer(session_id: str) -> list[dict]:
    """
    Drain the unanalyzed buffer and return the chunks for analysis.
    Resets the rolling counters.
    """
    state = _sessions.get(session_id)
    if not state:
        return []
    chunks = list(state.unanalyzed_chunks)
    state.unanalyzed_chunks = []
    state.unanalyzed_word_count = 0
    state.last_analysis_at = time.time()
    return chunks


def analyze_segment(session_id: str, chunks: list[dict]) -> list[MeetingAlert]:
    """
    Run re-litigation + LLM detection on a set of transcript chunks.
    Synchronous — designed to be called inside run_in_executor.
    """
    if not chunks:
        return []

    state = _sessions.get(session_id)
    combined_text = " ".join(
        (f"{c['speaker']}: " if c.get("speaker") else "") + c["text"]
        for c in chunks
    )

    alerts = []
    alerts.extend(_check_relitigation(state, combined_text))
    alerts.extend(_detect_forming_items(combined_text))
    return alerts


def end_session(session_id: str) -> dict:
    """
    End a meeting session: generate full summary + store in knowledge base.
    Synchronous — designed to be called inside run_in_executor.
    Returns the summary dict.
    """
    state = _sessions.get(session_id)
    if not state:
        return {"error": "Session not found"}

    full_transcript = _build_full_transcript(state)

    if not full_transcript.strip():
        _update_session_db(session_id, "ended", "", [], [])
        _sessions.pop(session_id, None)
        return {"summary": "", "decisions": [], "action_items": [], "takeaways": [], "follow_ups": []}

    _update_session_db(session_id, "processing", "", [], [])

    try:
        summary_data = _generate_summary(full_transcript, state.title)
        _store_in_knowledge_base(state, full_transcript, summary_data)
        _update_session_db(
            session_id,
            "completed",
            summary_data.get("summary", ""),
            summary_data.get("key_decisions", []),
            summary_data.get("action_items", []),
        )
        result = {
            "summary": summary_data.get("summary", ""),
            "decisions": summary_data.get("key_decisions", []),
            "action_items": summary_data.get("action_items", []),
            "takeaways": summary_data.get("key_takeaways", []),
            "follow_ups": summary_data.get("follow_ups", []),
        }
    except Exception as e:
        logger.error(f"End session {session_id} failed: {e}")
        _update_session_db(session_id, "ended", "", [], [])
        result = {"error": str(e)}
    finally:
        _sessions.pop(session_id, None)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_full_transcript(state: SessionState) -> str:
    parts = []
    for c in state.all_chunks:
        prefix = f"{c['speaker']}: " if c.get("speaker") else ""
        parts.append(prefix + c["text"])
    return "\n".join(parts)


def _check_relitigation(state: Optional[SessionState], text: str) -> list[MeetingAlert]:
    if len(text.split()) < RELITIGATION_MIN_WORDS:
        return []
    try:
        from app.services.relitigation_detector import find_similar_decisions
        matches = find_similar_decisions(text)
        alerts = []
        for match in matches[:2]:
            decision_id = match["decision_id"]
            if state and decision_id in state.seen_decision_ids:
                continue
            if state:
                state.seen_decision_ids.add(decision_id)

            decided_at = (match.get("decided_at") or "")[:10] or "unknown date"
            alert_text = (
                f'This topic was already decided on {decided_at}: "{match["decision"]}"'
            )
            if match.get("rationale"):
                alert_text += f"\nRationale: {match['rationale']}"

            alerts.append(MeetingAlert(
                kind="relitigation",
                text=alert_text,
                metadata={
                    "decision_id": decision_id,
                    "similarity": match["similarity"],
                    "decided_at": match.get("decided_at"),
                },
            ))
        return alerts
    except Exception as e:
        logger.error(f"Re-litigation check failed: {e}")
        return []


def _detect_forming_items(text: str) -> list[MeetingAlert]:
    """Use LLM to detect forming decisions and action items in a transcript segment."""
    try:
        from app.services.llm import generate

        prompt = f"""Analyze this meeting transcript excerpt. Identify any FORMING decisions (being discussed or agreed upon) and action items being assigned.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "forming_decisions": [{{"text": "...", "confidence": 0.0}}],
  "action_items": [{{"task": "...", "assignee": "...", "deadline": "...", "confidence": 0.0}}]
}}

If none found: {{"forming_decisions": [], "action_items": []}}

Only include items with confidence >= 0.6. Only use what is explicitly stated — do not infer.

Transcript excerpt:
{text}"""

        raw = generate(prompt, max_tokens=512)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        alerts = []

        for d in data.get("forming_decisions", []):
            if d.get("confidence", 0) >= 0.6 and d.get("text"):
                alerts.append(MeetingAlert(
                    kind="decision_forming",
                    text=f"Decision forming: {d['text']}",
                    metadata={"confidence": d.get("confidence", 0)},
                ))

        for a in data.get("action_items", []):
            if a.get("confidence", 0) >= 0.6 and a.get("task"):
                parts = [f"Action item: {a['task']}"]
                if a.get("assignee"):
                    parts.append(f"Assigned to: {a['assignee']}")
                if a.get("deadline"):
                    parts.append(f"By: {a['deadline']}")
                alerts.append(MeetingAlert(
                    kind="action_item",
                    text="\n".join(parts),
                    metadata={
                        "task": a["task"],
                        "assignee": a.get("assignee", ""),
                        "deadline": a.get("deadline", ""),
                        "confidence": a.get("confidence", 0),
                    },
                ))

        return alerts
    except Exception as e:
        logger.error(f"Forming-items detection failed: {e}")
        return []


def _generate_summary(transcript: str, title: str) -> dict:
    """Generate a full structured meeting summary using the existing MEETING_SUMMARY_PROMPT."""
    from app.services.meet_ingestion import generate_meeting_summary
    return generate_meeting_summary(transcript, title)


def _store_in_knowledge_base(state: SessionState, transcript: str, summary_data: dict):
    """Store completed meeting in the knowledge base (same pipeline as meet_ingestion)."""
    from app.services.meet_ingestion import _build_enriched_text, _store_action_items
    from app.services.chunker import chunk_and_store

    title = state.title
    enriched = _build_enriched_text(transcript, title, summary_data)
    source_id = f"live_meeting:{state.session_id}"
    url = f"/meeting/{state.session_id}"
    acl = [f"user:{state.user_email}"] if state.user_email else ["public"]

    extra_metadata = {
        "meeting_title": title,
        "summary": summary_data.get("summary", ""),
        "action_items": summary_data.get("action_items", []),
        "key_decisions": summary_data.get("key_decisions", []),
        "key_takeaways": summary_data.get("key_takeaways", []),
        "follow_ups": summary_data.get("follow_ups", []),
        "session_id": state.session_id,
    }

    # Full transcript chunk
    chunk_and_store(
        source_id=source_id,
        title=title,
        text=enriched,
        url=url,
        acl=acl,
        source="meet",
        extra_metadata=extra_metadata,
        chunk_type="full_text",
        doc_status="finalized",
    )

    # Separate high-priority summary chunk (boosted in search)
    summary_text = summary_data.get("summary", "")
    if summary_text:
        chunk_and_store(
            source_id=f"{source_id}:summary",
            title=f"{title} [Live Summary]",
            text=f"Live Meeting Summary — {title}\n\n{summary_text}",
            url=url,
            acl=acl,
            source="meet",
            chunk_type="summary",
            doc_status="finalized",
        )

    # Store action items + decisions in review queue / DecisionRecord
    _store_action_items(summary_data, title, url)
    logger.info(f"Stored live meeting {state.session_id} in knowledge base")


def _save_session_to_db(session_id: str, title: str, user_email: str):
    try:
        import datetime
        from app.core.database import SessionLocal
        from app.models import LiveMeetingSession
        db = SessionLocal()
        try:
            session = LiveMeetingSession(
                id=session_id,
                title=title or "Untitled Meeting",
                user_email=user_email or "",
                status="active",
                started_at=datetime.datetime.utcnow(),
            )
            db.add(session)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to persist session to DB: {e}")


def _update_session_db(
    session_id: str,
    status: str,
    summary: str,
    decisions: list,
    action_items: list,
):
    try:
        import datetime
        from app.core.database import SessionLocal
        from app.models import LiveMeetingSession
        db = SessionLocal()
        try:
            s = db.query(LiveMeetingSession).filter(LiveMeetingSession.id == session_id).first()
            if s:
                s.status = status
                s.summary = summary
                s.decisions_extracted = decisions
                s.action_items_extracted = action_items
                s.ended_at = datetime.datetime.utcnow()
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to update session DB record: {e}")
