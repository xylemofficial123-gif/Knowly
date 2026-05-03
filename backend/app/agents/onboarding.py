"""Onboarding Agent — generates knowledge packs and project context for team members."""
import re
import logging
from datetime import datetime

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.services.llm import generate
from app.services.embeddings import embed_text, search_chunks
from app.core.acl import user_can_see_chunk
from app.core.database import SessionLocal
from app.core.timezone import format_ist_date
from app.models import DecisionRecord
from app.services.settings_service import get_enabled_sources

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
- If a section has no info, write "No information available" — NEVER invent or guess
- ONLY use information from the provided sources and decisions. If you cannot find evidence for a claim, do not make it.
- If the topic has no documented history at all, say: "I cannot find any documented records about this topic."
- Dates in DD/MM/YYYY IST format
- SKIP entire sections if there's no directly relevant info for them — a shorter, focused answer is better than a padded one

Question: {question}

Active Decisions:
{decisions}

Source Documents:
{sources}

Briefing:"""

BLOCKER_HINTS = ("blocker", "blocked", "stuck", "dependency", "waiting on", "risk")


class OnboardingAgent(BaseAgent):
    name = "onboarding"
    description = "Generates contextual briefings and knowledge packs"

    def can_handle(self, context: AgentContext) -> bool:
        return context.query_type == "onboarding"

    def run(self, context: AgentContext) -> AgentResult:
        """Build a comprehensive onboarding briefing."""
        query = context.original_query
        project_name = self._extract_project_name(query)

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
        acl_blocked_count = 0

        for sq in search_queries:
            vec = embed_text(sq)
            results = search_chunks(vec, limit=6)

            # Source enablement filter
            enabled_sources = get_enabled_sources()
            
            # ACL filter + minimum relevance threshold
            relevant_results = [r for r in results if r.score >= 0.45]
            
            # Only consider results from enabled sources
            enabled_results = [r for r in relevant_results if r.payload.get("source", "unknown") in enabled_sources]
            
            acl_passed = [r for r in enabled_results if
                user_can_see_chunk(context.user_email, r.payload.get("acl", []))
            ]
            
            acl_blocked_count += len(enabled_results) - len(acl_passed)
            filtered = acl_passed

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

        # Get relevant decisions from the database, ACL-filtered.
        decisions_text = self._get_relevant_decisions(query, context.user_email)

        if not sources_text and not decisions_text:
            if acl_blocked_count > 0:
                return AgentResult(
                    answer=(
                        f"I found relevant documents, but you don't have access to view them. "
                        f"{acl_blocked_count} document(s) matched your query but are restricted "
                        f"based on your permissions. Please contact the document owner or your "
                        f"manager if you need access."
                    ),
                    agent_name=self.name,
                    confidence=0.0,
                )
            enabled = get_enabled_sources()
            active_tech_sources = [s for s in enabled if s != "upload"]
            if not active_tech_sources:
                msg = "All knowledge ingestion sources are currently disabled. Please enable them in the 'Ingest Sources' settings to allow research across your company's platforms."
            else:
                msg = "I don't have enough information to create a briefing on this topic yet. Please ensure the relevant documents have been ingested and the source is enabled in settings."
            
            return AgentResult(
                answer=msg,
                agent_name=self.name,
                confidence=0.0,
            )

        # Minimal onboarding "time machine" mode with predictable output blocks.
        if project_name:
            return self._build_time_machine_response(
                project_name=project_name,
                decisions_text=decisions_text,
                citation_map=citation_map,
                all_chunks=all_chunks,
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

    def _extract_project_name(self, query: str) -> str:
        q = query.strip()
        # Only parse the first sentence to avoid including instruction suffixes.
        q_first = re.split(r"[.!?]\s+", q, maxsplit=1)[0].strip()
        patterns = [
            r"catch me up on the history of\s+(?:the\s+)?(.+?)(?:\s+project)?[?.!]*$",
            r"history of\s+(?:the\s+)?(.+?)(?:\s+project)?[?.!]*$",
            r"catch me up on\s+(?:the\s+)?(.+?)(?:\s+project)?[?.!]*$",
            r"project scope:\s*(.+)$",
        ]
        for pattern in patterns:
            m = re.search(pattern, q_first, re.IGNORECASE)
            if m:
                name = m.group(1).strip(" \"'")
                name = re.sub(r"\s+", " ", name)
                # Remove common instruction fragments if they appear inline.
                name = re.split(
                    r"\b(use only|output with|if evidence|ignore other|question:)\b",
                    name,
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip(" \"'")
                if len(name) > 1:
                    return name
        return ""

    def _build_time_machine_response(
        self,
        project_name: str,
        decisions_text: str,
        citation_map: dict,
        all_chunks: list[str],
    ) -> AgentResult:
        timeline_events = []
        blockers = []
        project_terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", project_name) if len(t) > 2]

        for i, meta in enumerate(citation_map.values(), 1):
            excerpt = (meta.get("excerpt") or "").strip()
            title = (meta.get("display") or "").strip()
            if not excerpt:
                continue

            combined = f"{title} {excerpt}".lower()
            # Strict project relevance filter to reduce cross-project noise.
            if project_terms and not any(term in combined for term in project_terms):
                continue

            # Drop common ingestion metadata-heavy lines.
            if "[document metadata]" in combined or "last edited by" in combined:
                continue

            date = self._extract_date(excerpt) or self._extract_date(title) or "Unknown date"
            cleaned = re.sub(r"\s+", " ", excerpt).strip()
            timeline_events.append(f"- {date} — {cleaned[:130]} [{i}]")
            if any(h in excerpt.lower() for h in BLOCKER_HINTS):
                blockers.append(f"- {cleaned[:120]} (Owner: Unknown) [{i}]")

        summary_line = (
            f"{project_name} is an active project with documented decisions and ongoing work."
            if decisions_text.strip() or timeline_events
            else f"I cannot find documented records for {project_name} yet."
        )
        last_updated = format_ist_date(datetime.utcnow())

        timeline_lines = timeline_events[:8] or ["- No timeline events found in accessible sources."]
        blocker_lines = blockers[:3] or ["- No explicit blockers found in currently accessible records."]

        answer = (
            f"## Project Summary\n"
            f"- {summary_line}\n"
            f"- Last updated: {last_updated}\n\n"
            f"## Key Timeline\n"
            f"{chr(10).join(timeline_lines)}\n\n"
            f"## Current Blockers\n"
            f"{chr(10).join(blocker_lines)}\n\n"
            f"Contact project owner for missing context or private docs."
        )

        citations = []
        for num in sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)}):
            label = f"SOURCE_{num}"
            if label in citation_map:
                citations.append(citation_map[label])

        return AgentResult(
            answer=answer,
            citations=citations,
            chunks_used=all_chunks,
            agent_name=self.name,
            reasoning_steps=[
                f"Detected onboarding catch-up query for '{project_name}'",
                f"Compiled {len(timeline_lines)} timeline entries",
                f"Found {len(blocker_lines)} blocker entries",
            ],
            confidence=0.7 if timeline_events else 0.4,
            metadata={"mode": "time_machine"},
        )

    def _extract_date(self, text: str) -> str:
        m = re.search(r"(\d{4}[/-]\d{2}[/-]\d{2})", text)
        if m:
            return m.group(1).replace("/", "-")
        m = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", text)
        if m:
            return m.group(1).replace("/", "-")
        return ""

    def _get_relevant_decisions(self, query: str, user_email: str = "") -> str:
        """Fetch decisions related to the query topic, including reversal history.

        ACL-filtered: a new hire onboarding shouldn't see decisions from
        meetings/channels they don't have access to.
        """
        from app.core.acl import user_can_see_chunk

        db = SessionLocal()
        try:
            # Get all decisions (active + superseded) and check relevance
            decisions = (
                db.query(DecisionRecord)
                .order_by(DecisionRecord.decided_at.desc())
                .limit(100)
                .all()
            )

            if not decisions:
                return ""

            decisions = [d for d in decisions if user_can_see_chunk(user_email, list(d.acl or []))]
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
                if d.status == "superseded":
                    superseded_date = format_ist_date(d.superseded_at) if d.superseded_at else "?"
                    reason = d.reversal_reason or "No reason recorded"
                    lines.append(
                        f"- [REVERSED on {superseded_date}] [{date}] {d.decision} "
                        f"(Rationale: {d.rationale or 'N/A'}) — Reversal reason: {reason}"
                    )
                else:
                    lines.append(f"- [ACTIVE] [{date}] {d.decision} (Rationale: {d.rationale or 'N/A'})")

            return "\n".join(lines)

        finally:
            db.close()
