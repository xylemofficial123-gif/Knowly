"""Base agent class that all specialized agents inherit from."""
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Shared context passed between agents during a query."""
    user_email: str
    original_query: str
    query_type: str = ""
    sub_queries: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    intermediate_results: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Standard result returned by any agent."""
    answer: str
    citations: list[dict] = field(default_factory=list)
    chunks_used: list[str] = field(default_factory=list)
    agent_name: str = ""
    reasoning_steps: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


class BaseAgent:
    """Base class for all agents."""
    name: str = "base"
    description: str = "Base agent"

    def run(self, context: AgentContext) -> AgentResult:
        raise NotImplementedError

    def can_handle(self, context: AgentContext) -> bool:
        """Return True if this agent can handle the given context."""
        return False
