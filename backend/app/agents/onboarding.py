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
from app.models import DecisionRecord, Document
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
LOW_SIGNAL_PATTERNS = (
    "task:",
    "status:",
    "list:",
    "[document metadata]",
    "last edited by",
)


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
        if project_name:
            search_queries = [
                f"{project_name} project",
                f"{project_name} timeline decisions blockers",
                f"{project_name} slack drive meet updates",
                f"{project_name} current status",
            ]
        else:
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
        candidate_chunks = {}

        for sq in search_queries:
            vec = embed_text(sq)
            results = search_chunks(vec, limit=6)

            # Source enablement filter
            enabled_sources = get_enabled_sources()
            
            # ACL filter + minimum relevance threshold
            threshold = 0.35 if project_name else 0.45
            relevant_results = [r for r in results if r.score >= threshold]
            
            # Only consider results from enabled sources
            enabled_results = [r for r in relevant_results if r.payload.get("source", "unknown") in enabled_sources]
            
            acl_passed = [r for r in enabled_results if
                user_can_see_chunk(context.user_email, r.payload.get("acl", []))
            ]
            
            acl_blocked_count += len(enabled_results) - len(acl_passed)
            filtered = acl_passed

            for r in filtered:
                chunk_id = str(r.id)
                prev = candidate_chunks.get(chunk_id)
                if not prev or float(r.score) > float(prev.score):
                    candidate_chunks[chunk_id] = r

        selected = self._select_diverse_chunks(
            list(candidate_chunks.values()),
            max_total=12,
            project_name=project_name,
        )
        for r in selected:
            chunk_id = str(r.id)
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
                user_email=context.user_email,
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
        user_email: str = "",
    ) -> AgentResult:
        project_terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", project_name) if len(t) > 2]
        filtered_sources = []
        for i, meta in enumerate(citation_map.values(), 1):
            excerpt = (meta.get("excerpt") or "").strip()
            title = (meta.get("display") or "").strip()
            combined = f"{title} {excerpt}".lower()
            if not excerpt:
                continue
            if self._is_low_signal_excerpt(combined):
                continue
            # Hard guard: in project mode, only include explicit project mentions.
            if project_terms and not any(term in combined for term in project_terms):
                continue
            filtered_sources.append(
                f"[SOURCE_{i}] (source: {meta.get('source', 'unknown')}, title: {title})\n{excerpt}"
            )

        # Fallback: if vector retrieval missed project docs, pull from title/content match.
        if not filtered_sources and project_name:
            fallback = self._fallback_sources_from_documents(project_name, user_email, max_items=6)
            if fallback:
                base_idx = len(citation_map)
                for j, item in enumerate(fallback, 1):
                    label = f"SOURCE_{base_idx + j}"
                    citation_map[label] = {
                        "url": item.get("url", ""),
                        "source": item.get("source", "unknown"),
                        "display": item.get("title", "Document"),
                        "excerpt": item.get("excerpt", "")[:300],
                        "score": 0.55,
                    }
                    filtered_sources.append(
                        f"[{label}] (source: {item.get('source', 'unknown')}, title: {item.get('title', 'Document')})\n{item.get('excerpt', '')}"
                    )

        if not filtered_sources:
            answer = (
                "## Project Summary\n"
                f"- I cannot find documented records for {project_name} in accessible sources.\n\n"
                "## Key Timeline\n"
                "- No timeline events found in accessible sources.\n\n"
                "## Current Blockers\n"
                "- No explicit blockers found in currently accessible records."
            )
        else:
            prompt = f"""You are writing an onboarding project brief for "{project_name}".
Return exactly 3 sections with these headings:
## Project Summary
## Key Timeline
## Current Blockers

Rules:
- No fluff, no generic filler.
- Only use facts from sources below.
- Do NOT use information from other projects.
- Prefer Drive/Slack/Meet evidence when available; use ClickUp only as supporting evidence.
- For timeline, include 5-10 bullets with concrete dates when available.
- Skip items with unknown/noisy metadata-only content.
- For blockers, include max 3 bullets and include owner only if explicit; else write "Owner: Unknown".
- Add citations like [1], [2] that map to SOURCE numbers.

Decisions:
{decisions_text or "No formal decisions available."}

Sources:
{chr(10).join(filtered_sources)}
"""
            answer = generate(prompt, max_tokens=900).strip()
            answer = re.sub(r"\[?SOURCE_(\d+)\]?", r"[\1]", answer)

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
                f"Selected {len(filtered_sources)} source snippets",
                f"Returned {len(citations)} cited sources",
            ],
            confidence=0.75 if citations else 0.45,
            metadata={"mode": "time_machine"},
        )

    def _select_diverse_chunks(self, chunks: list, max_total: int = 12, project_name: str = "") -> list:
        """Balance sources so one connector (e.g., ClickUp) doesn't dominate."""
        project_terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", project_name) if len(t) > 2]

        def is_project_match(r) -> bool:
            if not project_terms:
                return True
            title = (r.payload.get("title", "") or "").lower()
            text = (r.payload.get("text_preview", "") or "").lower()
            combined = f"{title} {text}"
            return any(term in combined for term in project_terms)

        by_source = {}
        for r in sorted(chunks, key=lambda x: float(x.score), reverse=True):
            if not is_project_match(r):
                continue
            source = r.payload.get("source", "unknown")
            by_source.setdefault(source, []).append(r)

        selected = []
        # First pass: take up to 2 from each source.
        for source in sorted(by_source.keys()):
            picked = 0
            for r in by_source[source]:
                if picked >= 2 or len(selected) >= max_total:
                    break
                text = (r.payload.get("text_preview", "") or "").lower()
                if self._is_low_signal_excerpt(text):
                    continue
                selected.append(r)
                picked += 1

        # Second pass: fill remaining slots by score, regardless of source.
        if len(selected) < max_total:
            selected_ids = {str(r.id) for r in selected}
            for r in sorted(chunks, key=lambda x: float(x.score), reverse=True):
                if len(selected) >= max_total:
                    break
                if str(r.id) in selected_ids:
                    continue
                text = (r.payload.get("text_preview", "") or "").lower()
                if self._is_low_signal_excerpt(text):
                    continue
                selected.append(r)
                selected_ids.add(str(r.id))
        return selected

    def _is_low_signal_excerpt(self, text: str) -> bool:
        t = (text or "").lower()
        return any(p in t for p in LOW_SIGNAL_PATTERNS)

    def _fallback_sources_from_documents(self, project_name: str, user_email: str, max_items: int = 6) -> list[dict]:
        """Lexical fallback from document title/content when vector recall is poor."""
        db = SessionLocal()
        try:
            q = f"%{project_name}%"
            docs = (
                db.query(Document)
                .filter((Document.title.ilike(q)) | (Document.content.ilike(q)))
                .order_by(Document.updated_at.desc())
                .limit(20)
                .all()
            )

            out = []
            for d in docs:
                acl = list(d.acl or [])
                if not user_can_see_chunk(user_email, acl):
                    continue
                snippet = (d.content or "")[:500]
                if self._is_low_signal_excerpt(f"{d.title or ''} {snippet}"):
                    continue
                out.append(
                    {
                        "title": d.title or "Document",
                        "source": d.source or "unknown",
                        "url": d.url or "",
                        "excerpt": snippet or (d.title or ""),
                    }
                )
                if len(out) >= max_items:
                    break
            return out
        finally:
            db.close()

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
