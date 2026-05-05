"""Research Agent — handles complex queries requiring multi-hop reasoning."""
import re
import logging

# Match the inline timestamp markers we embed in Meet transcripts at ingestion:
# [14:32], [1:14:32]. First match in a chunk = the moment its content started.
_MEET_TS_RE = re.compile(r"\[(\d{1,2}(?::\d{2}){1,2})\]")


def _first_meet_timestamp(text: str):
    if not text:
        return None
    m = _MEET_TS_RE.search(text)
    return m.group(1) if m else None


from app.agents.base import BaseAgent, AgentContext, AgentResult
from app.services.llm import generate
from app.services.embeddings import embed_text, search_chunks
from app.core.acl import user_can_see_chunk
from app.core.timezone import now_ist, format_ist
from app.services.settings_service import get_enabled_sources

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are a research analyst for a company knowledge system. Synthesize a clear, well-structured answer from the search results below.

Current date and time: {current_datetime}

Formatting rules:
- Structure your answer with clear sections using **bold headers**
- Use bullet points for individual items — never write walls of text
- For meetings: structure as Key Decisions, Action Items, and Discussion Summary
- NEVER include an "Attendees" or "Invited" list — only mention people by name when attributing what they said or did
- For every discussion point, decision, or action item: when the source explicitly names the speaker (e.g. text starts with "<Sachin>:" or says "Krithin explained..."), attribute it to that person in bold (e.g. "**Sachin** said..."). When the speaker is NOT identifiable from the source, simply state the fact without attribution — never write "[Unknown]", "[anonymous]", or "the speaker".
- The summary should read like meeting minutes — who said what, who raised which topic, who was assigned what
- NEVER mix information from different meetings in the same summary. If sources are from different meetings, only use the one that best matches the user's question.
- For non-meeting queries: use logical groupings that fit the content
- Keep each bullet concise (1-2 sentences max)
- Cite sources as [1], [2], etc. (use the source number from SOURCE_N)
- When multiple sources say the same thing, pick the most relevant one or two — don't list every source
- Dates/times in DD/MM/YYYY IST (GMT+5:30) format

Content rules:
- ONLY use information that is DIRECTLY relevant to the user's question. Ignore tangentially related content even if it appears in the sources.
- Only use information from the provided sources. NEVER invent facts, rationale, or context.
- Do NOT preemptively mention or deny people, dates, or facts that weren't part of the question. If something isn't in the sources, simply omit it — never write "X is not mentioned" or "Y was not discussed".
- If sources conflict, note the conflict and cite both.
- If you cannot find the answer in the sources, say exactly: "I cannot find a documented record of this in the company's knowledge base." Do not guess or speculate.
- Be concise but thorough — capture all key points that are relevant to the question, not just a few highlights.
- A focused, shorter answer is ALWAYS better than a padded answer with unrelated information.
- If a source is marked as "draft" or "in_review", explicitly note this: "Note: this information comes from a draft document and may not be finalized."
- If a decision was REVERSED, always mention both the original decision and the reversal with dates and reason. Format: "Originally decided X on [date], but this was reversed to Y on [date] because Z."

Original Question: {question}
{conversation_context}
{decision_history}
{glossary}Research conducted:
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
        acl_blocked_count = 0  # Track chunks the user can't access

        for i, query in enumerate(queries):
            vec = embed_text(query)
            results = search_chunks(
                vec,
                limit=8 if topic_filter_enabled else 6,
                freshness_weight=freshness_weight,
                date_from=date_from,
                date_to=date_to,
            )

            # Source enablement filter
            enabled_sources = get_enabled_sources()
            
            # ACL filter + minimum relevance threshold
            relevant_results = [r for r in results if r.score >= 0.40]
            
            # Only consider results from enabled sources for further processing/counting
            enabled_results = [r for r in relevant_results if r.payload.get("source", "unknown") in enabled_sources]
            
            acl_passed = [r for r in enabled_results if
                user_can_see_chunk(context.user_email, r.payload.get("acl", []))
            ]
            
            # Tracks chunks in ENABLED sources that user can't access
            acl_blocked_count += len(enabled_results) - len(acl_passed)
            filtered = acl_passed

            # Topic filter
            if topic_filter_enabled and topic_keywords:
                filtered = [r for r in filtered if self._matches_topic(r, topic_keywords)]

            # Deduplicate across searches
            for r in filtered:
                chunk_id = str(r.id)
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_candidates.append((i, query, r))

        # Phase 1.4: Knowledge-graph augmentation — pull chunks linked to entities
        # in the user's query from any source. This is the "connective tissue":
        # if the query mentions "Atlas", we pull the Slack thread + ClickUp task +
        # Drive doc that all mention Atlas, even if their wording differed enough
        # that vector search missed them.
        try:
            from app.services.entity_extractor import (
                find_entities_in_query,
                get_chunks_for_entities,
            )
            from app.services.embeddings import fetch_chunks_by_ids

            matched_entities = find_entities_in_query(context.original_query)
            if matched_entities:
                graph_chunk_ids = get_chunks_for_entities(
                    [e["id"] for e in matched_entities],
                    limit_per_entity=8,
                )
                # Skip chunks already retrieved by vector search; cap total
                graph_chunk_ids = [cid for cid in graph_chunk_ids if cid not in seen_chunk_ids][:8]
                if graph_chunk_ids:
                    graph_results = fetch_chunks_by_ids(graph_chunk_ids, base_score=0.65)
                    enabled_sources = get_enabled_sources()
                    ent_label = ", ".join(e["canonical_name"] for e in matched_entities[:3])
                    graph_query_label = f"[graph: {ent_label}]"
                    graph_idx = len(queries)
                    added = 0
                    for r in graph_results:
                        src = r.payload.get("source", "unknown")
                        if src not in enabled_sources:
                            continue
                        if not user_can_see_chunk(context.user_email, r.payload.get("acl", [])):
                            acl_blocked_count += 1
                            continue
                        if topic_filter_enabled and topic_keywords and not self._matches_topic(r, topic_keywords):
                            continue
                        cid = str(r.id)
                        if cid in seen_chunk_ids:
                            continue
                        seen_chunk_ids.add(cid)
                        all_candidates.append((graph_idx, graph_query_label, r))
                        added += 1
                    if added:
                        logger.info(
                            f"Graph: query matched {len(matched_entities)} entities, "
                            f"added {added} cross-source chunks"
                        )
        except Exception as e:
            logger.warning(f"Graph augmentation skipped: {e}")

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

        # Phase 1.6: Version awareness — deprioritize draft documents
        for i, q, r in all_candidates:
            status = r.payload.get("doc_status", "unknown")
            if status == "draft":
                r.score *= 0.6   # Heavy penalty for drafts
            elif status == "in_review":
                r.score *= 0.85  # Slight penalty for in-review docs
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
        citation_map = {}
        seen_keys: dict[str, int] = {}  # dedupe_key → source_counter idx

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
                title = r.payload.get("title", "Unknown")
                text = r.payload.get("text_preview", "")
                url = r.payload.get("url", "")
                source = r.payload.get("source", "unknown")
                source_id = r.payload.get("source_id", "")

                # Dedupe by source URL (or source_id / title fallback). A long
                # Slack thread chunked into many pieces collapses into ONE
                # citation — same URL is one source from the user's view.
                dedupe_key = url or source_id or f"{source}:{title}"
                if dedupe_key in seen_keys:
                    label = f"SOURCE_{seen_keys[dedupe_key]}"
                    research_section += f"[{label}] (additional excerpt)\n{text}\n\n"
                    all_chunks.append(str(r.id))
                    continue

                idx = len(seen_keys) + 1
                seen_keys[dedupe_key] = idx
                label = f"SOURCE_{idx}"

                doc_status = r.payload.get("doc_status", "")
                status_tag = f", status: {doc_status}" if doc_status in ("draft", "in_review") else ""
                research_section += f"[{label}] (title: {title}, source: {source}{status_tag})\n{text}\n\n"

                # Pull the first inline [mm:ss] marker out of meet chunks so
                # the citation can say "Standup 14/02 at 14:32" instead of
                # just "Standup 14/02".
                meet_ts = _first_meet_timestamp(text) if source == "meet" else None
                display = title or f"{source} document"
                if meet_ts:
                    display = f"{display} at {meet_ts}"

                citation_map[label] = {
                    "url": url,
                    "source": source,
                    "display": display,
                    "timestamp": meet_ts,
                    "excerpt": text[:300],
                    "score": round(r.score, 3),
                }
                all_chunks.append(str(r.id))
                added += 1

            if added > 0:
                research_results.append(research_section)

        if not research_results:
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
                msg = "I could not find any documented records in the currently enabled sources that address your query. You may need to refine your question or ensure the relevant documents have been ingested."
            
            return AgentResult(
                answer=msg,
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

        # Fetch relevant decision history (including reversals), ACL-filtered.
        decision_history = self._get_decision_context(context.original_query, context.user_email)

        # Acronym buster — auto-define internal jargon mentioned in the query.
        # Saves the user from having to ask "what does LSQ mean?" separately.
        glossary_section = ""
        try:
            from app.services.acronym_buster import glossary_for_query
            glossary = glossary_for_query(context.original_query)
            if glossary:
                lines = ["Glossary (use these definitions when discussing the terms):"]
                for term, definition in glossary.items():
                    lines.append(f"- {term}: {definition}")
                glossary_section = "\n".join(lines) + "\n"
        except Exception as e:
            logger.debug(f"Glossary lookup skipped: {e}")

        # Synthesize across all results
        current_dt = format_ist(now_ist())
        prompt = SYNTHESIS_PROMPT.format(
            question=context.original_query,
            research_results="\n".join(research_results),
            current_datetime=current_dt,
            conversation_context=conversation_context,
            decision_history=decision_history,
            glossary=glossary_section,
        )

        answer = generate(prompt, max_tokens=2048)

        # Extract used citations — catches every style the LLM might use:
        #   [SOURCE_1], SOURCE_1, [1], [2, 3], [Decision Record 04/05/2026, 1]
        # Pull every \d+ from any [..] block, keep only ones that map to a real source.
        citations = []
        used_sources: set[str] = set(re.findall(r"SOURCE_(\d+)", answer))
        for bracket in re.findall(r"\[([^\]]*)\]", answer):
            for num in re.findall(r"\d+", bracket):
                if f"SOURCE_{num}" in citation_map:
                    used_sources.add(num)
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

        # Always include the original query
        angles = [query]

        # Optimization: Skip LLM expansion for very short queries or simple factual lookups
        words = query.split()
        if len(words) < 4 or query_type == "factual":
            return angles

        # Let the LLM generate search angles tailored to the actual query
        angle_prompt = (
            f"Generate 2 short search queries (each under 10 words) to find relevant "
            f"documents for this question. Return ONLY a JSON array of strings.\n\n"
            f"Question: {query}\n"
            f"Query type: {query_type}\n\n"
            f"JSON array:"
        )

        try:
            raw = generate(angle_prompt, max_tokens=128).strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import json
            generated = json.loads(raw.strip())
            if isinstance(generated, list):
                angles.extend([str(a) for a in generated[:2]])
        except Exception:
            # Fallback to rule-based angles if LLM fails or is rate-limited
            if query_type in ("meeting_summary", "timeline"):
                angles.append(f"meeting decisions action items {query}")
            elif query_type == "onboarding":
                angles.append(f"project overview help {query}")
            elif query_type == "multi_hop":
                angles.append(f"background context {query}")

        return angles[:3]  # Limit to 3 angles total to save embeddings calls too

    @staticmethod
    def _get_decision_context(query: str, user_email: str = "") -> str:
        """Fetch relevant decisions including reversal history for RAG context.

        Filters by ACL so a user cannot see decisions extracted from sources
        they don't have access to (e.g. a private leadership meeting).
        """
        from app.core.database import SessionLocal
        from app.models import DecisionRecord
        from app.core.acl import user_can_see_chunk

        db = SessionLocal()
        try:
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
                    if sim > 0.55:
                        scored.append((d, sim))

            if not scored:
                return ""

            scored.sort(key=lambda x: x[1], reverse=True)
            lines = ["Decision records (include in answer if relevant):"]
            for d, sim in scored[:5]:
                date_str = d.decided_at.strftime("%d/%m/%Y") if d.decided_at else "?"
                if d.status == "superseded":
                    rev_date = d.superseded_at.strftime("%d/%m/%Y") if d.superseded_at else "?"
                    reason = d.reversal_reason or "No reason recorded"
                    lines.append(
                        f"- [REVERSED on {rev_date}] Originally decided on {date_str}: "
                        f"{d.decision} (Rationale: {d.rationale or 'N/A'}) — Reversal reason: {reason}"
                    )
                else:
                    lines.append(
                        f"- [ACTIVE, {date_str}] {d.decision} (Rationale: {d.rationale or 'N/A'})"
                    )
            return "\n".join(lines) + "\n"
        except Exception as e:
            logger.warning(f"Decision context fetch failed: {e}")
            return ""
        finally:
            db.close()

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
