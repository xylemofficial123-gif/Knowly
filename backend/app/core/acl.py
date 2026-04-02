"""
Three-tier ACL enforcement.

Tiers:
  admin       – sees everything, no ACL check applied
  group_admin – sees public, their group docs, their own private docs
  member      – sees public, groups they belong to, their own private docs

ACL list formats (all backward-compatible):
  "public"           → visible to everyone
  "group:<uuid>"     → visible to members of that group
  "user:<email>"     → private to that user (or shared explicitly)
  "<email>"          → legacy email match (Drive permissions, meeting attendees)
  "<slack_channel>"  → Slack channel membership (existing behaviour)
"""

import logging
import time
from typing import Optional, List

from slack_sdk import WebClient
from sqlalchemy import func

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Slack channel cache (existing) ────────────────────────────────────────────

_channel_cache: dict[str, tuple[list[str], float]] = {}
_CACHE_TTL = 3600  # 60 minutes


def _get_slack_client() -> WebClient:
    return WebClient(token=settings.SLACK_BOT_TOKEN)


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def get_user_slack_channels(user_email: str) -> list[str]:
    if not settings.SLACK_BOT_TOKEN:
        return []

    user_email = _norm_email(user_email)
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


# ── User / Group helpers ──────────────────────────────────────────────────────

_user_role_cache: dict[str, tuple[str, float]] = {}
_user_groups_cache: dict[str, tuple[list[str], float]] = {}
_ROLE_CACHE_TTL = 300  # 5 minutes


def get_user_role(user_email: str) -> str:
    """Return the user's role: admin | group_admin | member. Defaults to member."""
    user_email = _norm_email(user_email)
    now = time.time()
    cached = _user_role_cache.get(user_email)
    if cached and (now - cached[1]) < _ROLE_CACHE_TTL:
        return cached[0]

    try:
        from app.core.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(func.lower(User.email) == user_email).first()
            role = user.role if user else "member"
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not fetch role for {user_email}: {e}")
        role = "member"

    _user_role_cache[user_email] = (role, now)
    return role


def get_user_group_ids(user_email: str) -> list[str]:
    """Return list of group UUIDs (as strings) the user belongs to."""
    user_email = _norm_email(user_email)
    now = time.time()
    cached = _user_groups_cache.get(user_email)
    if cached and (now - cached[1]) < _ROLE_CACHE_TTL:
        return cached[0]

    try:
        from app.core.database import SessionLocal
        from app.models import GroupMembership

        db = SessionLocal()
        try:
            memberships = (
                db.query(GroupMembership)
                .filter(func.lower(GroupMembership.user_email) == user_email)
                .all()
            )
            group_ids = [str(m.group_id) for m in memberships]
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not fetch groups for {user_email}: {e}")
        group_ids = []

    _user_groups_cache[user_email] = (group_ids, now)
    return group_ids


def invalidate_user_cache(user_email: str) -> None:
    """Call after modifying user role or group memberships."""
    _user_role_cache.pop(user_email, None)
    _user_groups_cache.pop(user_email, None)
    _channel_cache.pop(user_email, None)


# ── Core ACL check ────────────────────────────────────────────────────────────

def user_can_see_chunk(
    user_email: str,
    chunk_acl: list,
    *,
    role: Optional[str] = None,
    group_ids: Optional[List[str]] = None,
) -> bool:
    """
    Return True if user_email is allowed to see a chunk with the given ACL.

    Pass `role` and `group_ids` if already fetched (avoids redundant DB hits
    when filtering many chunks in a single request).
    """
    # Emergency switch for demos/debugging: bypass ACL checks entirely.
    if settings.BYPASS_ACL:
        return True

    # Empty ACL → public
    if not chunk_acl:
        return True

    user_email = _norm_email(user_email)

    # Admins see everything
    if role is None:
        role = get_user_role(user_email)
    if role == "admin":
        return True

    for entry in chunk_acl:
        # Public
        if entry == "public":
            return True

        # Group ACL: "group:<uuid>"
        if entry.startswith("group:"):
            gid = entry[len("group:"):]
            if group_ids is None:
                group_ids = get_user_group_ids(user_email)
            if gid in group_ids:
                return True

        # Private user ACL: "user:<email>"
        elif entry.startswith("user:"):
            target_email = _norm_email(entry[len("user:"):])
            if target_email == user_email:
                return True

        # Legacy: bare email match (Drive permissions, meeting attendees)
        elif _norm_email(entry) == user_email:
            return True

    # Slack channel ACL (legacy)
    user_channels = get_user_slack_channels(user_email)
    if user_channels and set(chunk_acl) & set(user_channels):
        return True

    return False


def build_acl(
    scope: str,
    user_email: str,
    group_id: Optional[str] = None,
    extra_emails: Optional[List[str]] = None,
) -> list[str]:
    """
    Build an ACL list from a scope string.

    scope values:
      "public"  → ["public"]
      "group"   → ["group:<group_id>"]  (group_id required)
      "private" → ["user:<user_email>"]

    extra_emails: additional specific emails to grant access (e.g. shared with)
    """
    if scope == "public":
        acl = ["public"]
    elif scope == "group":
        if not group_id:
            raise ValueError("group_id is required for group scope")
        acl = [f"group:{group_id}"]
    else:  # private (default)
        acl = [f"user:{user_email}"]

    if extra_emails:
        for email in extra_emails:
            entry = f"user:{email}"
            if entry not in acl:
                acl.append(entry)

    return acl
