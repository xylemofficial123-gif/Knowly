import time
import logging
from slack_sdk import WebClient
from app.core.config import settings

logger = logging.getLogger(__name__)

_channel_cache: dict[str, tuple[list[str], float]] = {}
_CACHE_TTL = 3600  # 60 minutes


def _get_slack_client() -> WebClient:
    return WebClient(token=settings.SLACK_BOT_TOKEN)


def get_user_slack_channels(user_email: str) -> list[str]:
    if not settings.SLACK_BOT_TOKEN:
        return []

    now = time.time()
    cached = _channel_cache.get(user_email)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]

    try:
        client = _get_slack_client()
        resp = client.users_lookupByEmail(email=user_email)
        if not resp["ok"]:
            return []
        user_id = resp["user"]["id"]

        channels = []
        cursor = None
        while True:
            kwargs = {"user": user_id, "types": "public_channel,private_channel", "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            result = client.users_conversations(**kwargs)
            for ch in result.get("channels", []):
                channels.append(ch["id"])
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        _channel_cache[user_email] = (channels, now)
        return channels
    except Exception as e:
        logger.warning(f"Failed to fetch Slack channels for {user_email}: {e}")
        return []


def user_can_see_chunk(user_email: str, chunk_acl: list) -> bool:
    # Local development bypass
    if getattr(settings, "BYPASS_ACL", False):
        return True

    if not chunk_acl:
        return True
    if "public" in chunk_acl:
        return True
    if user_email in chunk_acl:
        return True
    user_channels = get_user_slack_channels(user_email)
    return bool(set(chunk_acl) & set(user_channels))
