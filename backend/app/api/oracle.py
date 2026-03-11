from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oracle", tags=["oracle"])


class AskRequest(BaseModel):
    question: str
    user_email: str = "demo@yourcompany.com"


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


@router.post("/ask", response_model=OracleResponse)
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        from app.services.oracle import ask_oracle

        result = ask_oracle(req.question, req.user_email)
        return OracleResponse(**result)
    except Exception as e:
        logger.error(f"Oracle error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
