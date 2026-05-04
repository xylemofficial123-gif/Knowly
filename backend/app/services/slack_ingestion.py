import logging
import re
from slack_sdk import WebClient
from app.core.config import settings
from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)


# ── Version awareness heuristics ──────────────────────────────────────────────
# Slack has no native draft/finalized concept. We approximate with three signals:
#   1. Pinned messages → explicit team elevation → finalized
#   2. Decision phrases ("let's go with", "approved", "decided") → finalized
#   3. Draft phrases ("thinking about", "wip", "wondering") → draft
# Otherwise unknown — being honest beats guessing.

_SLACK_DECISION_PATTERN = re.compile(
    r"\b("
    r"let'?s\s+go\s+with|we'?ll\s+go\s+with|going\s+with|"
    r"(?:we|i)'?ve?\s+decided|decided\s+to|decision\s+is|"
    r"approv(?:ed|ing)|sign(?:ed)?\s*off|confirmed|finaliz(?:ed|ing)|"
    r"go\s+ahead\s+with|ship\s+it"
    r")\b",
    re.IGNORECASE,
)

_SLACK_DRAFT_PATTERN = re.compile(
    r"\b("
    r"thinking\s+about|wondering\s+if|what\s+if\s+we|"
    r"\bwip\b|work\s+in\s+progress|just\s+brainstorm(?:ing)?|"
    r"rough\s+thoughts?|exploring|maybe\s+we\s+could|"
    r"could\s+we|should\s+we|hot\s+take|half[\s-]baked|"
    r":wip:|:thinking_face:|:thought_balloon:"
    r")\b",
    re.IGNORECASE,
)


def _detect_slack_doc_status(msg: dict, full_text: str) -> str:
    # Slack API includes `pinned_to: [channel_id, ...]` on messages that are
    # pinned to one or more channels. Treat as explicit elevation → finalized.
    if msg.get("pinned_to") or msg.get("pinned"):
        return "finalized"
    # Decision phrases trump draft phrases — a thread with both means a decision
    # was reached after debate.
    if _SLACK_DECISION_PATTERN.search(full_text):
        return "finalized"
    if _SLACK_DRAFT_PATTERN.search(full_text):
        return "draft"
    return "unknown"


def _get_client() -> WebClient:
    """Return a Slack WebClient. Prefers DB-stored OAuth bot token over env var."""
    try:
        from app.core.token_store import get_latest_slack_connection
        conn = get_latest_slack_connection()
        if conn and conn.access_token:
            return WebClient(token=conn.access_token)
    except Exception as e:
        logger.debug(f"Could not load Slack token from DB: {e}")
    return WebClient(token=settings.SLACK_BOT_TOKEN)


def get_channel_member_emails(channel_id: str) -> list[str]:
    """Fetch email addresses of all members in a Slack channel.

    Returns a list of emails, or ["public"] if unable to fetch.
    Skips bots and members without verified emails.
    """
    client = _get_client()
    try:
        member_ids = []
        cursor = None
        while True:
            kwargs = {"channel": channel_id, "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            result = client.conversations_members(**kwargs)
            member_ids.extend(result.get("members", []))
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        emails = []
        for user_id in member_ids:
            try:
                info = client.users_info(user=user_id)
                user = info.get("user", {})
                if user.get("is_bot") or user.get("id") == "USLACKBOT":
                    continue
                email = user.get("profile", {}).get("email", "")
                if email:
                    emails.append(email)
            except Exception:
                continue

        return emails if emails else ["public"]
    except Exception as e:
        logger.warning(f"Could not fetch members for channel {channel_id}: {e}")
        return ["public"]


def get_channel_history(channel_id: str, limit: int = 1000) -> list[dict]:
    client = _get_client()
    messages = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "limit": min(limit - len(messages), 200)}
        if cursor:
            kwargs["cursor"] = cursor

        result = client.conversations_history(**kwargs)
        batch = result.get("messages", [])
        messages.extend(batch)

        if len(messages) >= limit:
            break

        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return messages


def get_thread_replies(channel_id: str, thread_ts: str) -> list[dict]:
    client = _get_client()
    replies = []
    cursor = None

    while True:
        kwargs = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor

        result = client.conversations_replies(**kwargs)
        batch = result.get("messages", [])
        replies.extend(batch)

        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return replies


def format_message_for_storage(msg: dict, channel_id: str, acl: list[str] = None) -> dict:
    ts = msg.get("ts", "")
    user = msg.get("user", "unknown")
    text = msg.get("text", "")
    thread_ts = msg.get("thread_ts")

    source_id = f"slack:{channel_id}:{ts}"
    url = f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}"

    return {
        "source_id": source_id,
        "text": text,
        "url": url,
        "acl": acl if acl else ["public"],
        "slack_user_id": user,
        "title": f"Slack message in #{channel_id}",
        "thread_ts": thread_ts,
    }


def ingest_message(msg: dict, channel_id: str, channel_acl: list[str] = None):
    if msg.get("bot_id"):
        return
    if not msg.get("text"):
        return

    no_index = settings.no_index_channels
    if channel_id in no_index:
        return

    # Check DB-based exclusion rules (no-index zones)
    from app.services.exclusion_service import is_excluded
    if is_excluded("slack", channel_id):
        return

    # If no ACL provided (real-time event), fetch channel members now
    if channel_acl is None:
        channel_acl = get_channel_member_emails(channel_id)

    formatted = format_message_for_storage(msg, channel_id, acl=channel_acl)

    reply_count = msg.get("reply_count", 0)
    thread_text = formatted["text"]

    if reply_count > 0:
        thread_ts = msg.get("ts")
        replies = get_thread_replies(channel_id, thread_ts)
        for reply in replies:
            if reply.get("ts") == thread_ts:
                continue
            if reply.get("bot_id"):
                continue
            reply_user = reply.get("user", "unknown")
            reply_text = reply.get("text", "")
            thread_text += f"\n<@{reply_user}>: {reply_text}"

    chunk_and_store(
        source="slack",
        source_id=formatted["source_id"],
        text=thread_text,
        url=formatted["url"],
        acl=formatted["acl"],
        title=formatted["title"],
        slack_user_id=formatted["slack_user_id"],
        doc_status=_detect_slack_doc_status(msg, thread_text),
    )


def backfill_channel(channel_id: str):
    logger.info(f"Backfilling channel {channel_id}")
    messages = get_channel_history(channel_id)

    # Fetch channel member emails once — reused for every message in this channel
    channel_acl = get_channel_member_emails(channel_id)
    logger.info(f"Channel {channel_id} ACL: {channel_acl}")

    count = 0
    for msg in messages:
        try:
            ingest_message(msg, channel_id, channel_acl=channel_acl)
            count += 1
        except Exception as e:
            logger.error(f"Failed to ingest message {msg.get('ts')}: {e}")

    logger.info(f"Backfilled {count} messages from channel {channel_id}")
    return count


def backfill_all_channels():
    client = _get_client()
    channels = []
    cursor = None

    while True:
        kwargs = {"types": "public_channel,private_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        result = client.conversations_list(**kwargs)
        channels.extend(result.get("channels", []))
        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    no_index = settings.no_index_channels
    from app.services.exclusion_service import get_excluded_ids, refresh_cache
    refresh_cache()  # Refresh at start of backfill
    excluded_channels = get_excluded_ids("slack")
    total = 0

    for ch in channels:
        ch_id = ch["id"]
        if ch_id in no_index or ch_id in excluded_channels:
            logger.info(f"Skipping no-index channel {ch_id} ({ch.get('name')})")
            continue
        if not ch.get("is_member", False):
            continue
        total += backfill_channel(ch["id"])

    logger.info(f"Backfill complete: {total} total messages ingested")
    return total
