"""Onboarding Agent — generates knowledge packs and project context for team members."""
import re
import logging
from datetime import datetime

from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.agents.research import ResearchAgent
from app.services.llm import generate
from app.services.embeddings import embed_text, search_chunks
from app.core.acl import user_can_see_chunk
from app.core.database import SessionLocal
from app.core.timezone import format_ist_date
from app.models import DecisionRecord, Document
from app.services.settings_service import get_enabled_sources

logger = logging.getLogger(__name__)

ONBOARDING_PROMPT = """You are an onboarding specialist for a company. A new team member is asking about a specific topic. Create a concise, factual briefing.

CRITICAL RULES:
- Include ONLY information directly relevant to the question.
- Ignore tangential details even if they appear in the same source.
- Do not invent facts. If evidence is missing, say so explicitly.

Output format (exactly this, in order):
{topic_heading} - Quick Onboarding Summary
What is {topic_heading}?
Current Setup
Key Decisions
Key People
Challenges
Open Items

Formatting rules:
- Use bullet points only (no paragraphs).
- Each bullet: max 1 short sentence.
- In "What is {topic_heading}?", include exactly 1 bullet.
- Do NOT add citations after every bullet.
- Add citations only as a final line per section when needed, in this format: "Sources: [1], [2]".
- Use only SOURCE_N and Active Decisions provided below.
- Use DD/MM/YYYY IST dates when available.
- If the topic has no evidence in the provided material, output exactly:
  "I cannot find any documented records about this topic."
- If a section has no evidence, write exactly one bullet: "- No information available."
- Do not repeat the same fact across sections.
- Keep grammar natural and direct; avoid robotic wording.
- Render all headings in bold markdown.

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

QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "is", "it", "of", "on", "or", "our", "the", "this", "to",
    "we", "what", "when", "where", "who", "why", "with", "you", "your",
    "about", "me", "us", "team", "project",
}


class OnboardingAgent(BaseAgent):
    name = "onboarding"
    description = "Generates contextual briefings and knowledge packs"

    def can_handle(self, context: AgentContext) -> bool:
        return context.query_type == "onboarding"

    def run(self, context: AgentContext) -> AgentResult:
        """Build onboarding briefing using a simple, Oracle-like retrieval pipeline."""
        query = context.original_query
        project_name = self._extract_project_name(query)
        all_chunks = []
        sources_text = ""
        citation_map = {}
        source_counter = 0
        acl_blocked_count = 0

        # Single-pass retrieval (Oracle-like): one query embedding, broader fetch,
        # then simple filtering + rerank.
        query_terms = self._query_terms(query)
        vec = embed_text(query)
        raw_results = search_chunks(vec, limit=24)
        enabled_sources = set(get_enabled_sources())

        scored = []
        for r in raw_results:
            source = r.payload.get("source", "unknown")
            if source not in enabled_sources:
                continue

            acl = r.payload.get("acl", [])
            if not user_can_see_chunk(context.user_email, acl):
                acl_blocked_count += 1
                continue

            if float(r.score) < 0.35:
                continue

            title = (r.payload.get("title", "") or "").lower()
            text = (r.payload.get("text_preview", "") or "").lower()
            combined = f"{title} {text}"
            if self._is_low_signal_excerpt(combined):
                continue

            # Topic relevance: keep only chunks that mention query terms.
            overlap = sum(1 for t in query_terms if t in combined) if query_terms else 0
            if query_terms and overlap == 0:
                continue
            kw_score = (overlap / max(len(query_terms), 1)) if query_terms else 0.0

            final_score = 0.75 * float(r.score) + 0.25 * kw_score
            scored.append((r, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [r for r, _ in scored[:10]]
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
        decisions_text = self._get_relevant_decisions(
            query,
            context.user_email,
            query_terms=query_terms,
        )

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

        topic_heading = project_name or self._topic_heading_from_query(query)
        prompt = ONBOARDING_PROMPT.format(
            topic_heading=topic_heading,
            question=query,
            decisions=decisions_text or "No formal decisions recorded on this topic.",
            sources=sources_text,
        )

        answer = generate(prompt, max_tokens=900)
        answer = self._enforce_onboarding_format(answer, topic_heading)

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
                "Single-pass semantic retrieval",
                f"Selected {source_counter} relevant sources",
                f"Included {len(decisions_text.splitlines())} decisions",
            ],
            confidence=0.7 if source_counter > 3 else 0.5,
        )

    def _enforce_onboarding_format(self, answer: str, topic_heading: str) -> str:
        """Normalize and compress output to the fixed onboarding format."""
        if not answer:
            return "I cannot find any documented records about this topic."

        no_record_markers = (
            "i cannot find any documented records about this topic",
            "i could not find any documented records",
        )
        lower = answer.lower()
        if any(m in lower for m in no_record_markers):
            return "I cannot find any documented records about this topic."

        section_order = [
            f"{topic_heading} - Quick Onboarding Summary",
            f"What is {topic_heading}?",
            "Current Setup",
            "Key Decisions",
            "Key People",
            "Challenges",
            "Open Items",
        ]
        bullet_caps = {
            f"What is {topic_heading}?": 1,
            "Current Setup": 4,
            "Key Decisions": 4,
            "Key People": 4,
            "Challenges": 3,
            "Open Items": 3,
        }

        lines = [ln.strip() for ln in (answer or "").splitlines() if ln.strip()]
        buckets: dict[str, list[str]] = {k: [] for k in section_order[1:]}
        current = ""

        alias = {
            "overview": f"What is {topic_heading}?",
            "project overview": f"What is {topic_heading}?",
            "what is": f"What is {topic_heading}?",
            "current status": "Current Setup",
            "current setup": "Current Setup",
            "key decisions": "Key Decisions",
            "key people": "Key People",
            "important context": "Challenges",
            "challenges": "Challenges",
            "blockers and challenges": "Challenges",
            "open items": "Open Items",
            "action items": "Open Items",
        }

        def resolve_header(text: str) -> str:
            t = text.strip().lower().strip(":")
            t = re.sub(r"^[#*\-\d\.\s]+", "", t).strip()
            for k, v in alias.items():
                if t == k or t.startswith(k):
                    return v
            return ""

        for ln in lines:
            header = resolve_header(ln)
            if header:
                current = header
                continue
            if not current:
                continue
            if not ln.startswith(("-", "•")):
                ln = f"- {ln}"
            elif ln.startswith("•"):
                ln = "- " + ln[1:].strip()
            ln = re.sub(r"\s+", " ", ln).strip()
            buckets[current].append(ln)

        out = [f"**{section_order[0]}**", ""]
        for sec in section_order[1:]:
            out.append(f"**{sec}**")
            items = buckets.get(sec, [])
            dedup = []
            seen = set()
            for item in items:
                key = re.sub(r"\[[0-9]+\]", "", item).strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                dedup.append(item)
            items = dedup[:bullet_caps.get(sec, 3)]
            if not items:
                items = ["- No information available."]
            out.extend(items)
            out.append("")
            out.append("")

        return "\n".join(out).strip()

    def _run_project_onboarding_via_research(self, context: AgentContext, project_name: str) -> AgentResult:
        """Route project onboarding through ResearchAgent (same path as Oracle/main chatbot)."""
        research = ResearchAgent()
        project_query = (
            f"What is {project_name}? Include: current status, key timeline, and blockers for {project_name} only."
        )
        project_ctx = AgentContext(
            user_email=context.user_email,
            original_query=project_query,
            query_type="onboarding",
            sub_queries=[],
            metadata=dict(context.metadata or {}),
        )
        result = research.run(project_ctx)
        no_records_markers = (
            "i could not find any documented records",
            "i cannot find a documented record",
            "i cannot find documented records",
        )
        if any(marker in (result.answer or "").lower() for marker in no_records_markers):
            # Fallback to Oracle retrieval path, which may recover sources missed by ResearchAgent.
            from app.services.oracle import ask_oracle
            oracle = ask_oracle(f"What is {project_name}?", context.user_email)
            result = AgentResult(
                answer=oracle.get("answer", result.answer),
                citations=oracle.get("citations", []),
                chunks_used=oracle.get("chunks_used", []),
                agent_name=self.name,
                reasoning_steps=[
                    f"ResearchAgent had no records; fallback to Oracle retrieval for '{project_name}'",
                ],
                confidence=0.7 if oracle.get("citations") else 0.4,
            )
        result.agent_name = self.name
        result.reasoning_steps = [
            f"Delegated project onboarding for '{project_name}' to ResearchAgent retrieval pipeline"
        ] + result.reasoning_steps
        return result

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

    def _select_diverse_chunks(
        self,
        chunks: list,
        max_total: int = 12,
        project_name: str = "",
        query_terms: set[str] | None = None,
    ) -> list:
        """Balance sources so one connector (e.g., ClickUp) doesn't dominate."""
        project_terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", project_name) if len(t) > 2]
        query_terms = query_terms or set()

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
            if query_terms and not self._matches_query_terms(r, query_terms):
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
                if query_terms and not self._matches_query_terms(r, query_terms):
                    continue
                text = (r.payload.get("text_preview", "") or "").lower()
                if self._is_low_signal_excerpt(text):
                    continue
                selected.append(r)
                selected_ids.add(str(r.id))
        return selected

    def _query_terms(self, query: str) -> set[str]:
        terms = re.findall(r"[a-zA-Z0-9]+", (query or "").lower())
        return {t for t in terms if len(t) > 2 and t not in QUERY_STOPWORDS}

    def _topic_heading_from_query(self, query: str) -> str:
        terms = [t for t in re.findall(r"[a-zA-Z0-9]+", (query or "").title()) if len(t) > 2]
        if not terms:
            return "Topic"
        return " ".join(terms[:3])

    def _matches_query_terms(self, result, query_terms: set[str]) -> bool:
        title = (result.payload.get("title", "") or "").lower()
        text = (result.payload.get("text_preview", "") or "").lower()
        combined = f"{title} {text}"
        overlap = sum(1 for t in query_terms if t in combined)
        if len(query_terms) <= 3:
            return overlap >= 1
        return overlap >= 2

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

    def _get_relevant_decisions(
        self,
        query: str,
        user_email: str = "",
        query_terms: set[str] | None = None,
    ) -> str:
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
                # Topic guard: for specific queries, require lexical overlap with
                # decision/rationale so unrelated project decisions don't leak in.
                if query_terms:
                    hay = f"{d.decision or ''} {d.rationale or ''}".lower()
                    overlap = sum(1 for t in query_terms if t in hay)
                    if overlap == 0:
                        continue
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
