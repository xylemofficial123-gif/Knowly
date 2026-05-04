from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from app.core.auth import get_current_user_email
from app.services import query_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oracle", tags=["oracle"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AskRequest(BaseModel):
    question: str
    user_email: str = ""
    session_id: str = ""
    history: list[ChatMessage] = []


class CitationResponse(BaseModel):
    url: str = ""
    source: str = ""
    display: str = ""
    excerpt: str = ""
    freshness: float = 0.5
    score: float = 0.0


class OracleResponse(BaseModel):
    answer: str
    citations: list[CitationResponse] = []
    chunks_used: list[str] = []


class AgentResponse(BaseModel):
    answer: str
    citations: list[CitationResponse] = []
    chunks_used: list[str] = []
    agent: str = ""
    query_type: str = ""
    reasoning_steps: list[str] = []
    confidence: float = 0.0
    session_id: str = ""
    audit_log_id: str = ""


@router.post("/ask", response_model=AgentResponse)
def ask(req: AskRequest, actor_email: str = Depends(get_current_user_email)):
    """Main query endpoint — routes through the multi-agent system."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Skip cache when there's conversation history — replies depend on prior turns.
    use_cache = not req.history
    if use_cache:
        cached = query_cache.get(actor_email, req.question)
        if cached is not None:
            return AgentResponse(**cached)

    try:
        from app.agents.orchestrator import ask as agent_ask

        # Convert history to list of dicts
        history = [{"role": m.role, "content": m.content} for m in req.history]

        result = agent_ask(
            req.question,
            actor_email,
            session_id=req.session_id,
            history=history,
        )
        if use_cache:
            query_cache.set(actor_email, req.question, result)
        return AgentResponse(**result)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        # Graceful degradation: never bubble provider outages to the UI as 500.
        return AgentResponse(
            answer=(
                "I can reach your knowledge sources, but the answer model is temporarily "
                "unavailable. Please try again in 1-2 minutes."
            ),
            citations=[],
            chunks_used=[],
            agent="research",
            query_type="factual",
            reasoning_steps=[],
            confidence=0.0,
            session_id=req.session_id,
            audit_log_id="",
        )


@router.post("/ask/simple", response_model=OracleResponse)
def ask_simple(req: AskRequest, actor_email: str = Depends(get_current_user_email)):
    """Legacy simple Oracle endpoint (single-search, no routing)."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    cached = query_cache.get(f"simple:{actor_email}", req.question)
    if cached is not None:
        return OracleResponse(**cached)

    try:
        from app.services.oracle import ask_oracle

        result = ask_oracle(req.question, actor_email)
        query_cache.set(f"simple:{actor_email}", req.question, result)
        return OracleResponse(**result)
    except Exception as e:
        logger.error(f"Oracle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
