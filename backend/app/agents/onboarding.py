"""Onboarding Agent — generates knowledge packs and project context for team members."""
import re
import logging

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.services.llm import generate
from app.services.embeddings import embed_text, search_chunks
from app.core.acl import user_can_see_chunk
from app.core.database import SessionLocal
from app.core.timezone import format_ist_date
from app.models import DecisionRecord

logger = logging.getLogger(__name__)

ONBOARDING_PROMPT = """You are an onboarding specialist for a company. A team member is asking about a specific topic. Create a focused, structured briefing.

CRITICAL RULE: ONLY include information that is DIRECTLY relevant to the question asked. If a source document mentions something unrelated to the question — even if it's from the same meeting or document — DO NOT include it. Stay strictly on-topic. Do not pad the answer with tangentially related information.

Structure your response as:
1. **Overview** — What this is about (2-3 sentences)
2. **Key Decisions** — Decisions directly related to this topic and WHY they were made (bullet points)
3. **Current Status** — Where things stand right now for THIS topic specifically
4. **Key People** — Who's directly involved in THIS topic and their roles (bullet points)
5. **Important Context** — Things a newcomer wouldn't know about THIS topic
6. **Open Items** — Unresolved questions or pending action items for THIS topic

Formatting rules:
- Use bullet points throughout — no walls of text
- Keep each bullet concise (1-2 sentences max)
- Cite sources as [1], [2], etc. (use the number from SOURCE_N)
- Don't over-cite — pick the 1-2 most relevant sources per claim
- If a section has no info, write "No information available" — don't invent
- Dates in DD/MM/YYYY IST format
- SKIP entire sections if there's no directly relevant info for them — a shorter, focused answer is better than a padded one

Question: {question}

Active Decisions:
{decisions}

Source Documents:
{sources}

Briefing:"""


class OnboardingAgent(BaseAgent):
    name = "onboarding"
    description = "Generates contextual briefings and knowledge packs"

    def can_handle(self, context: AgentContext) -> bool:
        return context.query_type == "onboarding"

    def run(self, context: AgentContext) -> AgentResult:
        """Build a comprehensive onboarding briefing."""
        query = context.original_query

        # Search from multiple angles for comprehensive coverage
        search_queries = [
            query,
            f"project overview background {query}",
            f"decisions rationale {query}",
            f"action items status {query}",
        ]

        all_chunks = []
        sources_text = ""
        citation_map = {}
        source_counter = 0

        for sq in search_queries:
            vec = embed_text(sq)
            results = search_chunks(vec, limit=6)

            # ACL filter + minimum relevance threshold
            filtered = [r for r in results if (
                user_can_see_chunk(context.user_email, r.payload.get("acl", []))
                and r.score >= 0.45
            )]

            for r in filtered[:3]:
                # Deduplicate by ID
                chunk_id = str(r.id)
                if chunk_id in all_chunks:
                    continue

                source_counter += 1
                label = f"SOURCE_{source_counter}"
                title = r.payload.get("title", "Unknown")
                text = r.payload.get("text_preview", "")
                url = r.payload.get("url", "")
                source = r.payload.get("source", "unknown")

                sources_text += f"[{label}] (title: {title}, source: {source})\n{text}\n\n"
                citation_map[label] = {
                    "url": url,
                    "source": source,
                    "display": title or f"{source} document",
                    "excerpt": text[:300],
                    "score": round(r.score, 3),
                }
                all_chunks.append(chunk_id)

        # Get relevant decisions from the database
        decisions_text = self._get_relevant_decisions(query)

        if not sources_text and not decisions_text:
            return AgentResult(
                answer="I don't have enough information to create a briefing on this topic yet. "
                       "More documents or meeting notes about this topic need to be ingested.",
                agent_name=self.name,
                confidence=0.0,
            )

        prompt = ONBOARDING_PROMPT.format(
            question=query,
            decisions=decisions_text or "No formal decisions recorded on this topic.",
            sources=sources_text,
        )

        answer = generate(prompt, max_tokens=2048)

        # Extract citations — catches [1], [SOURCE_1], SOURCE_1, etc.
        citations = []
        used_sources = set(re.findall(r"SOURCE_(\d+)", answer))
        used_sources.update(re.findall(r"\[(\d+)\]", answer))
        for num in sorted(used_sources, key=int):
            label = f"SOURCE_{num}"
            if label in citation_map:
                citations.append(citation_map[label])

        # Clean up: normalize [SOURCE_N] → [N]
        answer = re.sub(r"\[?SOURCE_(\d+)\]?", r"[\1]", answer)

        return AgentResult(
            answer=answer,
            citations=citations,
            chunks_used=all_chunks,
            agent_name=self.name,
            reasoning_steps=[
                f"Searched {len(search_queries)} angles",
                f"Found {source_counter} relevant sources",
                f"Included {len(decisions_text.splitlines())} decisions",
            ],
            confidence=0.7 if source_counter > 3 else 0.5,
        )

    def _get_relevant_decisions(self, query: str) -> str:
        """Fetch decisions related to the query topic."""
        db = SessionLocal()
        try:
            # Get recent active decisions and check relevance via embedding similarity
            decisions = (
                db.query(DecisionRecord)
                .filter(DecisionRecord.status == "active")
                .order_by(DecisionRecord.decided_at.desc())
                .limit(50)
                .all()
            )

            if not decisions:
                return ""

            query_vec = embed_text(query)
            scored = []
            for d in decisions:
                d_vec = embed_text(d.decision)
                dot = sum(a * b for a, b in zip(query_vec, d_vec))
                norm_q = sum(a * a for a in query_vec) ** 0.5
                norm_d = sum(a * a for a in d_vec) ** 0.5
                if norm_q > 0 and norm_d > 0:
                    sim = dot / (norm_q * norm_d)
                    if sim > 0.5:
                        scored.append((d, sim))

            scored.sort(key=lambda x: x[1], reverse=True)

            lines = []
            for d, sim in scored[:8]:
                date = format_ist_date(d.decided_at) if d.decided_at else "?"
                lines.append(f"- [{date}] {d.decision} (Rationale: {d.rationale or 'N/A'})")

            return "\n".join(lines)

        finally:
            db.close()
