import logging
from slack_sdk import WebClient
from app.core.config import settings
from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)


def _get_client() -> WebClient:
    return WebClient(token=settings.SLACK_BOT_TOKEN)


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


def format_message_for_storage(msg: dict, channel_id: str) -> dict:
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
        "acl": [channel_id],
        "slack_user_id": user,
        "title": f"Slack message in #{channel_id}",
        "thread_ts": thread_ts,
    }


def ingest_message(msg: dict, channel_id: str):
    if msg.get("bot_id"):
        return
    if not msg.get("text"):
        return

    no_index = settings.no_index_channels
    if channel_id in no_index:
        return

    formatted = format_message_for_storage(msg, channel_id)

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
    )


def backfill_channel(channel_id: str):
    logger.info(f"Backfilling channel {channel_id}")
    messages = get_channel_history(channel_id)
    count = 0

    for msg in messages:
        try:
            ingest_message(msg, channel_id)
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
    total = 0

    for ch in channels:
        if ch["id"] in no_index:
            logger.info(f"Skipping no-index channel {ch['id']} ({ch.get('name')})")
            continue
        if not ch.get("is_member", False):
            continue
        total += backfill_channel(ch["id"])

    logger.info(f"Backfill complete: {total} total messages ingested")
    return total
