"""Orchestrator — coordinates agents to answer queries intelligently."""
import json
import hashlib
import logging
import time
import uuid

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AuditLog
from app.agents.base import AgentContext, AgentResult
from app.core.timezone import now_utc
from app.agents.router import RouterAgent
from app.agents.research import ResearchAgent
from app.agents.onboarding import OnboardingAgent

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Initialize agents
router = RouterAgent()
research_agent = ResearchAgent()
onboarding_agent = OnboardingAgent()

# Agent registry — order matters for fallback
AGENTS = [onboarding_agent, research_agent]

# Conversation history TTL (2 hours)
HISTORY_TTL = 7200


def _select_agent(context: AgentContext, plan: dict):
    """Select the best agent based on the router's classification."""
    complexity = plan.get("complexity", "simple")
    query_type = plan.get("query_type", "factual")
    strategy = plan.get("search_strategy", "single_search")

    # Onboarding queries → Onboarding Agent (check first, it has specialized formatting)
    if query_type == "onboarding":
        return onboarding_agent

    # Complex queries or multi-search → Research Agent
    if complexity == "complex" or strategy in ("multi_search", "cross_reference"):
        return research_agent

    # Multi-hop, comparison, timeline → Research Agent
    if query_type in ("multi_hop", "comparison", "timeline"):
        return research_agent

    # Simple factual, who_what, meeting_summary, action_items, decision_history
    # → Research Agent with single search (acts like enhanced Oracle)
    return research_agent


def ask(question: str, user_email: str, session_id: str = "", history: list[dict] = None) -> dict:
    """Main entry point — routes query through the agent system."""
    history = history or []

    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    # Create shared context with conversation history
    context = AgentContext(
        user_email=user_email,
        original_query=question,
    )
    context.metadata["conversation_history"] = history
    context.metadata["session_id"] = session_id

    # Step 1: Router classifies the query (with conversation context)
    start_time = time.time()
    plan = router.run(context)

    # Step 2: Select and run the appropriate agent
    agent = _select_agent(context, plan)
    logger.info(f"Routing to {agent.name} agent (type={context.query_type})")

    result = agent.run(context)
    response_time_ms = (time.time() - start_time) * 1000

    # Build response
    response = {
        "answer": result.answer,
        "citations": result.citations,
        "chunks_used": result.chunks_used,
        "agent": result.agent_name,
        "query_type": context.query_type,
        "reasoning_steps": result.reasoning_steps,
        "confidence": result.confidence,
        "session_id": session_id,
    }

    # Audit log
    audit_log_id = None
    db: Session = SessionLocal()
    try:
        log = AuditLog(
            user_email=user_email,
            query=question,
            chunks_returned=json.dumps(result.chunks_used[:10]),
            result_count=str(len(result.citations)),
            agent=result.agent_name,
            query_type=context.query_type,
            confidence=result.confidence,
            response_time_ms=response_time_ms,
            timestamp=now_utc(),
        )
        db.add(log)
        db.commit()
        audit_log_id = str(log.id)
    except Exception as e:
        db.rollback()
        logger.error(f"Audit log failed: {e}")
    finally:
        db.close()

    response["audit_log_id"] = audit_log_id
    return response
