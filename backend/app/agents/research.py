"""Research Agent — handles complex queries requiring multi-hop reasoning."""
import re
import logging

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.services.llm import generate
from app.services.embeddings import embed_text, search_chunks
from app.core.acl import user_can_see_chunk
from app.core.timezone import now_ist, format_ist

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are a research analyst for a company knowledge system. Synthesize a clear, well-structured answer from the search results below.

Current date and time: {current_datetime}

Formatting rules:
- Structure your answer with clear sections using **bold headers**
- Use bullet points for individual items — never write walls of text
- For meetings: structure as Key Decisions, Action Items, and Discussion Summary
- NEVER include an "Attendees" or "Invited" list — only mention people by name when attributing what they said or did
- For every discussion point, decision, or action item: attribute it to the person who said/raised it (e.g., "**Krithin** explained that..." or "**Akanksha** raised an issue with...")
- The summary should read like meeting minutes — who said what, who raised which topic, who was assigned what
- NEVER mix information from different meetings in the same summary. If sources are from different meetings, only use the one that best matches the user's question.
- For non-meeting queries: use logical groupings that fit the content
- Keep each bullet concise (1-2 sentences max)
- Cite sources as [1], [2], etc. (use the source number from SOURCE_N)
- When multiple sources say the same thing, pick the most relevant one or two — don't list every source
- Dates/times in DD/MM/YYYY IST (GMT+5:30) format

Content rules:
- Only use information from the provided sources. Never invent facts.
- If sources conflict, note the conflict and cite both.
- If you can't find the answer, say so honestly.
- Be concise but thorough — capture all key points from the meeting, not just a few highlights.

Original Question: {question}
{conversation_context}
Research conducted:
{research_results}

Provide a well-structured answer:"""


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Multi-hop reasoning across multiple sources"

    def can_handle(self, context: AgentContext) -> bool:
        return context.query_type in ("multi_hop", "comparison", "onboarding", "timeline")

    def run(self, context: AgentContext) -> AgentResult:
        """Execute multi-search strategy and synthesize results."""
        queries = context.sub_queries if context.sub_queries else [context.original_query]

        # If no sub-queries were generated, create some based on query type
        if not context.sub_queries:
            queries = self._generate_search_angles(context)

        # Get temporal parameters from Router's analysis (no hardcoded keywords)
        needs_recency = context.metadata.get("needs_recency", False)
        date_from = context.metadata.get("date_from")
        date_to = context.metadata.get("date_to")
        freshness_weight = 0.3 if needs_recency else 0.0

        # Get topic filter from Router's analysis
        topic_filter_enabled = context.metadata.get("topic_filter_enabled", False)
        topic_keywords = [kw.lower() for kw in context.metadata.get("topic_keywords", [])]

        # Phase 1: Collect all candidate chunks across all search angles
        seen_chunk_ids = set()
        all_candidates = []  # (query_index, query_text, result)

        for i, query in enumerate(queries):
            vec = embed_text(query)
            results = search_chunks(
                vec,
                limit=8 if topic_filter_enabled else 6,
                freshness_weight=freshness_weight,
                date_from=date_from,
                date_to=date_to,
            )

            # ACL filter
            filtered = [r for r in results if user_can_see_chunk(
                context.user_email, r.payload.get("acl", [])
            )]

            # Topic filter
            if topic_filter_enabled and topic_keywords:
                filtered = [r for r in filtered if self._matches_topic(r, topic_keywords)]

            # Deduplicate across searches
            for r in filtered:
                chunk_id = str(r.id)
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_candidates.append((i, query, r))

        # Phase 1.5: Source-type boosting — prefer transcript content over calendar stubs
        # for queries about meeting content (what was discussed, speakers, decisions)
        if context.query_type in ("meeting_summary", "timeline", "multi_hop", "action_items"):
            for i, q, r in all_candidates:
                source = r.payload.get("source", "")
                if source == "meet":
                    r.score *= 1.3  # Boost transcripts
                elif source == "calendar":
                    r.score *= 0.5  # Penalize calendar stubs (they lack content)
            all_candidates.sort(key=lambda x: x[2].score, reverse=True)

        # Phase 2: For meeting queries with recency — isolate the most recent meeting
        # across ALL collected results (not per-query)
        if needs_recency and context.query_type in ("meeting_summary", "timeline") and not topic_filter_enabled:
            all_results_flat = [r for _, _, r in all_candidates]
            isolated = self._isolate_most_recent_meeting(all_results_flat)
            isolated_ids = {str(r.id) for r in isolated}
            all_candidates = [(i, q, r) for i, q, r in all_candidates if str(r.id) in isolated_ids]

        # Phase 3: Build research sections from candidates
        all_chunks = []
        research_results = []
        source_counter = 0
        citation_map = {}

        # Group by search query
        from itertools import groupby
        for query_idx, group in groupby(all_candidates, key=lambda x: (x[0], x[1])):
            items = list(group)
            query_text = items[0][1]
            research_section = f"\n--- Search: \"{query_text}\" ---\n"
            added = 0

            for _, _, r in items:
                if added >= 4:
                    break
                source_counter += 1
                label = f"SOURCE_{source_counter}"
                title = r.payload.get("title", "Unknown")
                text = r.payload.get("text_preview", "")
                url = r.payload.get("url", "")
                source = r.payload.get("source", "unknown")

                research_section += f"[{label}] (title: {title}, source: {source})\n{text}\n\n"

                citation_map[label] = {
                    "url": url,
                    "source": source,
                    "display": title or f"{source} document",
                    "excerpt": text[:300],
                    "score": round(r.score, 3),
                }
                all_chunks.append(str(r.id))
                added += 1

            if added > 0:
                research_results.append(research_section)

        if not research_results:
            return AgentResult(
                answer="I couldn't find relevant information across any of my searches.",
                agent_name=self.name,
                confidence=0.0,
            )

        # Build conversation context for follow-up awareness
        conversation_context = ""
        history = context.metadata.get("conversation_history", [])
        if history:
            recent = history[-6:]  # Last 3 exchanges
            lines = []
            for msg in recent:
                role = "User" if msg["role"] == "user" else "Agent"
                content = msg["content"][:300] + "..." if len(msg["content"]) > 300 else msg["content"]
                lines.append(f"{role}: {content}")
            conversation_context = (
                "\nPrevious conversation (use for context on follow-up questions):\n"
                + "\n".join(lines)
                + "\n"
            )

        # Synthesize across all results
        current_dt = format_ist(now_ist())
        prompt = SYNTHESIS_PROMPT.format(
            question=context.original_query,
            research_results="\n".join(research_results),
            current_datetime=current_dt,
            conversation_context=conversation_context,
        )

        answer = generate(prompt, max_tokens=2048)

        # Extract used citations — catches [1], [SOURCE_1], SOURCE_1, etc.
        citations = []
        used_sources = set(re.findall(r"SOURCE_(\d+)", answer))
        # Also catch plain [N] references the LLM may use
        used_sources.update(re.findall(r"\[(\d+)\]", answer))
        for num in sorted(used_sources, key=int):
            label = f"SOURCE_{num}"
            if label in citation_map:
                citations.append(citation_map[label])

        # Clean up: normalize [SOURCE_N] → [N] for cleaner display
        answer = re.sub(r"\[?SOURCE_(\d+)\]?", r"[\1]", answer)

        return AgentResult(
            answer=answer,
            citations=citations,
            chunks_used=all_chunks,
            agent_name=self.name,
            reasoning_steps=[f"Searched: {q}" for q in queries],
            confidence=0.8 if len(research_results) > 1 else 0.6,
        )

    def _generate_search_angles(self, context: AgentContext) -> list[str]:
        """Generate multiple search angles for a query using LLM when possible."""
        query = context.original_query
        query_type = context.query_type

        # Let the LLM generate search angles tailored to the actual query
        angle_prompt = (
            f"Generate 2-3 short search queries (each under 10 words) to find relevant "
            f"documents for this question. Return ONLY a JSON array of strings.\n\n"
            f"Question: {query}\n"
            f"Query type: {query_type}\n\n"
            f"JSON array:"
        )

        angles = [query]  # Always include the original query

        try:
            raw = generate(angle_prompt, max_tokens=256).strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import json
            generated = json.loads(raw.strip())
            if isinstance(generated, list):
                angles.extend([str(a) for a in generated[:3]])
        except Exception:
            # Fallback to rule-based angles if LLM fails
            if query_type in ("meeting_summary", "timeline"):
                angles.append("daily standup meeting notes summary")
                angles.append(f"meeting decisions action items {query}")
            elif query_type == "action_items":
                angles.append("action items tasks follow-up")
            elif query_type == "comparison":
                angles.append(f"advantages benefits {query}")
                angles.append(f"disadvantages problems {query}")
            elif query_type == "onboarding":
                angles.append(f"project overview history {query}")
                angles.append(f"key decisions rationale {query}")
            elif query_type == "multi_hop":
                angles.append(f"background context {query}")
                angles.append(f"decisions outcomes {query}")

        return angles[:4]

    @staticmethod
    def _matches_topic(result, topic_keywords: list[str]) -> bool:
        """Check if a search result's title or content matches the topic keywords."""
        title = (result.payload.get("title", "") or "").lower()
        text = (result.payload.get("text_preview", "") or "").lower()
        searchable = f"{title} {text}"
        return any(kw in searchable for kw in topic_keywords)

    @staticmethod
    def _isolate_most_recent_meeting(results: list) -> list:
        """From a list of search results, keep only chunks belonging to the most recent meeting.

        Groups chunks by their source document title, finds the one with the most recent date,
        and returns only chunks from that meeting.
        """
        from app.core.timezone import parse_date_from_text

        if not results:
            return results

        # Group by title and find the most recent meeting
        meetings: dict[str, list] = {}
        meeting_dates: dict[str, any] = {}

        for r in results:
            title = r.payload.get("title", "Unknown")
            source = r.payload.get("source", "")
            # Only group meeting/drive sources, skip spreadsheets etc.
            if source not in ("meet", "drive"):
                continue

            if title not in meetings:
                meetings[title] = []
                meeting_dates[title] = parse_date_from_text(title)
            meetings[title].append(r)

        if not meetings:
            return results

        # Find the meeting with the most recent date
        dated_meetings = [(title, dt, chunks) for title, chunks in meetings.items()
                          if (dt := meeting_dates.get(title)) is not None]

        if not dated_meetings:
            return results

        dated_meetings.sort(key=lambda x: x[1], reverse=True)
        most_recent_title = dated_meetings[0][0]

        # Return only chunks from the most recent meeting
        filtered = [r for r in results if r.payload.get("title", "") == most_recent_title]
        return filtered if filtered else results
