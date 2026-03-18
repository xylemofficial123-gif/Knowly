"""Router/Planner Agent — classifies queries and delegates to specialized agents."""
import json
import logging
from datetime import timedelta

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.services.llm import generate
from app.core.timezone import now_ist, format_ist_date

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """You are a query router for a company knowledge system. Classify the user's question and plan the best retrieval strategy.

Current date and time: {current_datetime}

Analyze the question and return JSON:
{{
  "query_type": one of ["factual", "timeline", "decision_history", "who_what", "comparison", "meeting_summary", "action_items", "onboarding", "multi_hop"],
  "complexity": one of ["simple", "moderate", "complex"],
  "sub_queries": ["list of sub-questions to search for if the query needs to be broken down"],
  "search_strategy": one of ["single_search", "multi_search", "cross_reference", "temporal"],
  "temporal": {{
    "needs_recency": true/false,
    "date_from": "YYYY-MM-DD or null",
    "date_to": "YYYY-MM-DD or null",
    "reasoning": "why this time range"
  }},
  "topic_filter": {{
    "enabled": true/false,
    "keywords": ["list of keywords to identify the specific meeting/document/topic"],
    "reasoning": "why this filter"
  }},
  "reasoning": "brief explanation of your classification"
}}

Query type definitions:
- factual: direct fact lookup ("What is our coding standard?")
- timeline: chronological events ("What happened this week?")
- decision_history: past decisions and rationale ("Why did we choose React?")
- who_what: people-related ("Who edited X?", "What is person Y working on?")
- comparison: comparing things ("How does X differ from Y?")
- meeting_summary: meeting-specific ("What happened in the standup?")
- action_items: tasks and follow-ups ("What are my action items?")
- onboarding: broad context questions ("Tell me about project X", "What does the team do?")
- multi_hop: requires connecting information from multiple sources

Complexity:
- simple: one search is enough
- moderate: needs 2-3 searches or cross-referencing
- complex: needs multiple searches, reasoning across sources, or temporal analysis

Temporal analysis:
- Set needs_recency=true if the user wants recent or time-specific results (e.g., "latest", "today", "this week", "last Monday", "March 5th meeting")
- Set date_from/date_to to narrow the time window. Use the current date to resolve relative references like "today", "yesterday", "last week", etc.
- If no time constraint, set needs_recency=false and dates to null

Topic filtering:
- When the user asks about a specific meeting, project, document, or topic, set enabled=true and extract keywords that identify it
- For example, "latest standup" → keywords: ["standup", "daily standup"]; "all hands meeting" → keywords: ["all hands"]
- These keywords will be used to filter search results so only relevant meetings/documents are included
- If the query is general (not about a specific topic), set enabled=false and keywords to empty list

For sub_queries: break complex questions into 2-4 specific search queries that would help answer the full question. For simple questions, return an empty list.

Return ONLY valid JSON. No explanation.
{conversation_context}
Question: {question}"""


class RouterAgent(BaseAgent):
    name = "router"
    description = "Classifies queries and plans retrieval strategy"

    def run(self, context: AgentContext) -> dict:
        """Classify the query and return routing plan."""
        current_dt = now_ist()
        # Use unambiguous format for LLM (March 12, 2026) to avoid DD/MM vs MM/DD confusion
        current_datetime = current_dt.strftime("%B %d, %Y %H:%M IST (GMT+5:30), %A")

        # Optimization: Bypass LLM for extremely simple queries
        q_lower = context.original_query.lower().strip().strip("?!.")
        if q_lower in ("hi", "hello", "hey", "help", "who are you", "what can you do"):
            logger.info("Router: simple query bypass")
            context.query_type = "onboarding"
            context.sub_queries = []
            return {
                "query_type": "onboarding",
                "complexity": "simple",
                "sub_queries": [],
                "search_strategy": "single_search",
                "temporal": {"needs_recency": False, "date_from": None, "date_to": None},
                "reasoning": "Simple greeting or help query bypass",
            }

        # Build conversation context summary for follow-up questions
        conversation_context = ""
        history = context.metadata.get("conversation_history", [])
        if history:
            recent = history[-6:]  # Last 3 exchanges max
            lines = []
            for msg in recent:
                role = "User" if msg["role"] == "user" else "Agent"
                # Truncate long answers to save tokens
                content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
                lines.append(f"{role}: {content}")
            conversation_context = (
                "\nConversation so far (use this to understand follow-up questions):\n"
                + "\n".join(lines)
                + "\n"
            )

        prompt = ROUTER_PROMPT.format(
            question=context.original_query,
            current_datetime=current_datetime,
            conversation_context=conversation_context,
        )

        try:
            raw = generate(prompt, max_tokens=512)
            raw = raw.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            plan = json.loads(raw)

            context.query_type = plan.get("query_type", "factual")
            context.sub_queries = plan.get("sub_queries", [])

            # Store temporal info in context metadata for agents to use
            temporal = plan.get("temporal", {})
            context.metadata["needs_recency"] = temporal.get("needs_recency", False)
            context.metadata["date_from"] = temporal.get("date_from")
            context.metadata["date_to"] = temporal.get("date_to")

            # Store topic filter for agents to filter irrelevant results
            topic = plan.get("topic_filter", {})
            context.metadata["topic_filter_enabled"] = topic.get("enabled", False)
            context.metadata["topic_keywords"] = topic.get("keywords", [])

            logger.info(
                f"Router: type={plan.get('query_type')}, "
                f"complexity={plan.get('complexity')}, "
                f"strategy={plan.get('search_strategy')}, "
                f"temporal={temporal}, "
                f"sub_queries={len(context.sub_queries)}"
            )

            return plan

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Router classification failed, defaulting to simple: {e}")
            context.query_type = "factual"
            return {
                "query_type": "factual",
                "complexity": "simple",
                "sub_queries": [],
                "search_strategy": "single_search",
                "temporal": {"needs_recency": False, "date_from": None, "date_to": None},
                "reasoning": "Classification failed, using default",
            }
