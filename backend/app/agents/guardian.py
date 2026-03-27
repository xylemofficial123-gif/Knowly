"""
Guardian Agent — cross-source redundancy prevention.

When any user posts a Slack message, creates a ClickUp task, or edits a Drive
doc, the Guardian embeds the text and searches the entire knowledge base for
prior discussions on the same topic.  If a high-confidence match is found it:

  1. Synthesises a concise, source-cited alert via the LLM.
  2. Delivers the alert in-context (Slack thread reply / ClickUp comment).
  3. Logs the alert to the `guardian_alerts` table.

Flow:
  text + user_email + trigger_source
    → embed
    → search ALL chunks (no source filter)
    → ACL filter (respect permissions)
    → deduplicate by document
    → LLM-synthesise alert
    → return GuardianResult
"""
import logging
from dataclasses import dataclass, field

from app.core.acl import get_user_role, get_user_group_ids, user_can_see_chunk
from app.core.timezone import format_ist_date
from app.services.embeddings import embed_text, search_chunks
from app.services.llm import generate

logger = logging.getLogger(__name__)

# Minimum similarity to surface a match.
# Lower than the re-litigation threshold (0.82) because we search ALL content
# types, not just recorded decisions.
GUARDIAN_THRESHOLD = 0.78

# Ignore messages shorter than this — too vague to match meaningfully.
MIN_WORDS = 15

# Maximum unique documents to include in one alert.
MAX_MATCHES = 5


@dataclass
class GuardianMatch:
    source: str          # drive | slack | meet | calendar | clickup | upload
    title: str
    url: str
    date: str            # DD/MM/YYYY IST
    preview: str         # first ~250 chars of the chunk
    score: float
    chunk_type: str      # summary | decision | action_item | full_text


@dataclass
class GuardianResult:
    has_match: bool
    alert_text: str = ""          # Formatted Slack/ClickUp message
    matches: list[GuardianMatch] = field(default_factory=list)
    highest_score: float = 0.0


# ── Source label helpers ───────────────────────────────────────────────────────

_SOURCE_LABELS = {
    "drive":    "Google Drive",
    "meet":     "Google Meet",
    "calendar": "Google Calendar",
    "slack":    "Slack",
    "clickup":  "ClickUp",
    "upload":   "Upload",
}

_SOURCE_EMOJI = {
    "drive":    "📄",
    "meet":     "🎥",
    "calendar": "📅",
    "slack":    "💬",
    "clickup":  "✅",
    "upload":   "📎",
}


def _label(source: str) -> str:
    return _SOURCE_LABELS.get(source.lower(), source.capitalize())


def _emoji(source: str) -> str:
    return _SOURCE_EMOJI.get(source.lower(), "🔗")


def _fmt_date(iso: str) -> str:
    """Convert ISO timestamp to DD/MM/YYYY, or return empty string."""
    if not iso:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return format_ist_date(dt)
    except Exception:
        return iso[:10]


# ── LLM alert synthesis ────────────────────────────────────────────────────────

_ALERT_PROMPT = """You are Xylem, a company knowledge guardian. A team member just wrote something that closely matches prior discussions already in the knowledge base.

Original message (first 300 chars):
{snippet}

Matching sources found:
{sources}

Write a short, helpful Slack thread reply telling the person this topic has been discussed before. Rules:
- Use Slack markdown (*bold*, _italic_)
- Open with: 💡 *This topic has come up before:*
- List each source as one bullet: • [emoji] *Title* — one-sentence takeaway _(date)_
- Close with one line: Reply `/oracle <your question>` for full context
- Max 8 lines total
- Tone: helpful colleague, never condescending

Return only the message text."""


def _synthesise_alert(snippet: str, matches: list[GuardianMatch]) -> str:
    sources_text = "\n".join(
        f"- [{_label(m.source)}] {m.title} ({m.date}): {m.preview[:200]}"
        for m in matches
    )
    prompt = _ALERT_PROMPT.format(snippet=snippet[:300], sources=sources_text)
    try:
        return generate(prompt, max_tokens=400)
    except Exception as e:
        logger.error(f"Guardian LLM synthesis failed: {e}")
        # Fallback: plain text alert without LLM
        lines = ["💡 *This topic has come up before:*"]
        for m in matches:
            date_str = f" _({m.date})_" if m.date else ""
            lines.append(f"• {_emoji(m.source)} *{m.title}*{date_str}")
        lines.append("Reply `/oracle <your question>` for full context")
        return "\n".join(lines)


# ── Core check ────────────────────────────────────────────────────────────────

class GuardianAgent:
    name = "guardian"
    description = "Cross-source redundancy prevention — surfaces prior discussions"

    def check(
        self,
        text: str,
        user_email: str,
        trigger_source: str,
        source_id: str = "",
        source_url: str = "",
    ) -> GuardianResult:
        """
        Check whether `text` has been discussed before anywhere in the
        knowledge base that `user_email` has permission to see.

        Args:
            text:           The triggering content (Slack msg / ClickUp task title+desc).
            user_email:     Used for ACL filtering.  Pass "" to skip ACL (admin use).
            trigger_source: "slack" | "clickup" | "drive" | "manual"
            source_id:      Unique ID of the triggering content — excluded from results
                            to avoid self-matching.
            source_url:     URL of the triggering content (for logging).

        Returns:
            GuardianResult with has_match=False when nothing significant found.
        """
        word_count = len(text.split())
        if word_count < MIN_WORDS:
            logger.debug(f"Guardian: skipping — only {word_count} words")
            return GuardianResult(has_match=False)

        # ── 1. Embed ──────────────────────────────────────────────────────────
        query_vector = embed_text(text[:4000])

        # ── 2. Search all sources ─────────────────────────────────────────────
        # Fetch generously; we'll filter and deduplicate below.
        raw_results = search_chunks(query_vector, limit=40)

        # ── 3. Threshold + ACL filter ─────────────────────────────────────────
        user_role = get_user_role(user_email) if user_email else "admin"
        user_group_ids = get_user_group_ids(user_email) if user_email else []

        visible = []
        for point in raw_results:
            if point.score < GUARDIAN_THRESHOLD:
                continue  # results are sorted, so we can break early
            payload = point.payload

            # Skip the chunk that came from the same source as the trigger
            if source_id and payload.get("source_id", "") == source_id:
                continue

            chunk_acl = payload.get("acl", [])
            if user_email and not user_can_see_chunk(
                user_email, chunk_acl, role=user_role, group_ids=user_group_ids
            ):
                continue

            visible.append(point)

        if not visible:
            logger.debug("Guardian: no matches above threshold after ACL filter")
            return GuardianResult(has_match=False)

        # ── 4. Deduplicate by document ────────────────────────────────────────
        # Keep only the highest-scoring chunk per source document.
        seen_docs: dict[str, object] = {}
        for point in visible:
            doc_key = point.payload.get("document_id") or str(point.id)
            if doc_key not in seen_docs:
                seen_docs[doc_key] = point
            if len(seen_docs) >= MAX_MATCHES:
                break

        top_points = list(seen_docs.values())

        # ── 5. Build match objects ────────────────────────────────────────────
        matches: list[GuardianMatch] = []
        for point in top_points:
            p = point.payload
            date_raw = p.get("ingested_at", "") or p.get("created_at", "")
            matches.append(GuardianMatch(
                source=p.get("source", "unknown"),
                title=p.get("title", "Untitled"),
                url=p.get("source_url", "") or p.get("url", ""),
                date=_fmt_date(date_raw),
                preview=(p.get("text_preview", "") or "")[:250],
                score=round(point.score, 3),
                chunk_type=p.get("chunk_type", "full_text"),
            ))

        # ── 6. Synthesise alert text ──────────────────────────────────────────
        snippet = text[:300]
        alert_text = _synthesise_alert(snippet, matches)

        highest = matches[0].score if matches else 0.0
        logger.info(
            f"Guardian: {len(matches)} match(es) for {trigger_source} "
            f"(top score={highest:.3f}, user={user_email})"
        )

        return GuardianResult(
            has_match=True,
            alert_text=alert_text,
            matches=matches,
            highest_score=highest,
        )


# ── Delivery helpers (called from tasks.py) ────────────────────────────────────

def deliver_slack_alert(result: GuardianResult, channel_id: str, thread_ts: str):
    """Post the guardian alert as a thread reply in Slack."""
    from app.core.config import settings
    if not settings.SLACK_BOT_TOKEN:
        logger.info("Guardian: Slack delivery skipped — no bot token")
        return False
    try:
        from slack_sdk import WebClient
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=result.alert_text,
            unfurl_links=False,
        )
        logger.info(f"Guardian: Slack alert delivered to {channel_id} thread {thread_ts}")
        return True
    except Exception as e:
        logger.error(f"Guardian: Slack delivery failed: {e}")
        return False


def deliver_clickup_comment(result: GuardianResult, task_id: str):
    """Post the guardian alert as a comment on a ClickUp task."""
    from app.core.config import settings
    if not settings.CLICKUP_API_KEY:
        logger.info("Guardian: ClickUp delivery skipped — no API key")
        return False
    try:
        import requests
        headers = {"Authorization": settings.CLICKUP_API_KEY, "Content-Type": "application/json"}
        # Strip Slack markdown for plain-text ClickUp comment
        comment_text = (
            result.alert_text
            .replace("*", "")
            .replace("_", "")
        )
        requests.post(
            f"https://api.clickup.com/api/v2/task/{task_id}/comment",
            headers=headers,
            json={"comment_text": comment_text, "notify_all": False},
            timeout=10,
        )
        logger.info(f"Guardian: ClickUp comment delivered to task {task_id}")
        return True
    except Exception as e:
        logger.error(f"Guardian: ClickUp delivery failed: {e}")
        return False
