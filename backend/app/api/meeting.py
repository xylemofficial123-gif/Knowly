"""
Real-Time Meeting Agent API
WebSocket endpoint for live transcript streaming + REST session management.

WebSocket protocol
==================
Client → Server:
  {"type": "chunk", "speaker": "Alice", "text": "...", "timestamp": "..."}
  {"type": "end"}
  {"type": "ping"}

Server → Client:
  {"type": "connected", "session_id": "..."}
  {"type": "alert", "kind": "relitigation|decision_forming|action_item", "text": "...", "metadata": {}}
  {"type": "processing"}
  {"type": "session_ended", "summary": "...", "decisions": [...], "action_items": [...], "takeaways": [...], "follow_ups": [...]}
  {"type": "pong"}
  {"type": "error", "text": "..."}
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.models import LiveMeetingSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meeting", tags=["meeting"])


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    title: str = "Untitled Meeting"
    user_email: str = ""


@router.post("/start")
def start_session(req: StartSessionRequest):
    from app.services.realtime_meeting import create_session
    session_id = create_session(req.title, req.user_email)
    return {"session_id": session_id, "status": "active"}


@router.post("/{session_id}/end")
def end_session_rest(session_id: str):
    """Safety-valve REST endpoint — ends session and triggers summary generation."""
    from app.services.realtime_meeting import get_session, end_session
    state = get_session(session_id)
    if state:
        result = end_session(session_id)
        return {"status": "ended", **result}
    # Session already ended or never existed — return DB record
    db = SessionLocal()
    try:
        s = db.query(LiveMeetingSession).filter(LiveMeetingSession.id == session_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "status": s.status,
            "summary": s.summary or "",
            "decisions": s.decisions_extracted or [],
            "action_items": s.action_items_extracted or [],
        }
    finally:
        db.close()


@router.get("/sessions")
def list_sessions(
    user_email: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    db = SessionLocal()
    try:
        q = db.query(LiveMeetingSession).order_by(LiveMeetingSession.started_at.desc())
        if user_email:
            q = q.filter(LiveMeetingSession.user_email == user_email)
        if status:
            q = q.filter(LiveMeetingSession.status == status)
        sessions = q.offset(offset).limit(limit).all()
        return {
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "user_email": s.user_email,
                    "status": s.status,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "summary": s.summary or "",
                }
                for s in sessions
            ]
        }
    finally:
        db.close()


@router.get("/{session_id}")
def get_session_detail(session_id: str):
    db = SessionLocal()
    try:
        s = db.query(LiveMeetingSession).filter(LiveMeetingSession.id == session_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "id": s.id,
            "title": s.title,
            "user_email": s.user_email,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "summary": s.summary or "",
            "decisions": s.decisions_extracted or [],
            "action_items": s.action_items_extracted or [],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/{session_id}")
async def meeting_websocket(websocket: WebSocket, session_id: str):
    from app.services.realtime_meeting import (
        get_session,
        add_chunk,
        should_analyze,
        drain_buffer,
        analyze_segment,
        end_session,
    )

    await websocket.accept()

    # Validate session exists
    state = get_session(session_id)
    if not state:
        # Try recovering from DB (server may have restarted mid-session)
        db = SessionLocal()
        try:
            s = db.query(LiveMeetingSession).filter(
                LiveMeetingSession.id == session_id,
                LiveMeetingSession.status == "active",
            ).first()
        finally:
            db.close()

        if not s:
            await websocket.send_text(json.dumps({
                "type": "error",
                "text": "Session not found. Create one with POST /api/meeting/start",
            }))
            await websocket.close()
            return

        # Re-initialize in-memory state (transcript lost on restart)
        from app.services.realtime_meeting import create_session, _sessions, SessionState
        import time
        _sessions[session_id] = SessionState(
            session_id=session_id,
            title=s.title,
            user_email=s.user_email,
            started_at=time.time(),
        )

    await websocket.send_text(json.dumps({"type": "connected", "session_id": session_id}))
    loop = asyncio.get_event_loop()

    async def _analyze_and_send(chunks: list):
        """Run analysis in a thread pool and send results back over the WebSocket."""
        try:
            alerts = await loop.run_in_executor(None, analyze_segment, session_id, chunks)
            for alert in alerts:
                try:
                    await websocket.send_text(json.dumps({
                        "type": "alert",
                        "kind": alert.kind,
                        "text": alert.text,
                        "metadata": alert.metadata,
                    }))
                except (WebSocketDisconnect, RuntimeError):
                    pass  # Client disconnected before alert was sent
        except Exception as e:
            logger.error(f"Analysis task failed for session {session_id}: {e}")

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "text": "Invalid JSON"}))
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "chunk":
                speaker = msg.get("speaker", "")
                text = msg.get("text", "")
                timestamp = msg.get("timestamp", "")

                if not text:
                    continue

                add_chunk(session_id, speaker, text, timestamp)

                # Fire-and-forget analysis task when buffer is ready
                if should_analyze(session_id):
                    chunks = drain_buffer(session_id)
                    asyncio.create_task(_analyze_and_send(chunks))

            elif msg_type == "end":
                await websocket.send_text(json.dumps({
                    "type": "processing",
                    "text": "Generating meeting summary…",
                }))

                result = await loop.run_in_executor(None, end_session, session_id)

                await websocket.send_text(json.dumps({
                    "type": "session_ended",
                    "summary": result.get("summary", ""),
                    "decisions": result.get("decisions", []),
                    "action_items": result.get("action_items", []),
                    "takeaways": result.get("takeaways", []),
                    "follow_ups": result.get("follow_ups", []),
                }))
                break

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "text": f"Unknown message type: {msg_type}",
                }))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
        # If session is still active in memory, clean up
        if get_session(session_id):
            await loop.run_in_executor(None, end_session, session_id)
