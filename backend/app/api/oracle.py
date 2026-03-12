from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oracle", tags=["oracle"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AskRequest(BaseModel):
    question: str
    user_email: str = "demo@yourcompany.com"
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
def ask(req: AskRequest):
    """Main query endpoint — routes through the multi-agent system."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        from app.agents.orchestrator import ask as agent_ask

        # Convert history to list of dicts
        history = [{"role": m.role, "content": m.content} for m in req.history]

        result = agent_ask(
            req.question,
            req.user_email,
            session_id=req.session_id,
            history=history,
        )
        return AgentResponse(**result)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask/simple", response_model=OracleResponse)
def ask_simple(req: AskRequest):
    """Legacy simple Oracle endpoint (single-search, no routing)."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        from app.services.oracle import ask_oracle

        result = ask_oracle(req.question, req.user_email)
        return OracleResponse(**result)
    except Exception as e:
        logger.error(f"Oracle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
