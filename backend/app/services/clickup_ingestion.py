import logging
import requests
from app.core.config import settings
from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"


def _get_token() -> str:
    """Return ClickUp access token — OAuth DB connection first, env var fallback."""
    from app.core.token_store import get_token
    token = get_token("clickup")
    if token:
        return token
    if settings.CLICKUP_API_KEY:
        return settings.CLICKUP_API_KEY
    raise RuntimeError("ClickUp not connected — no OAuth token or API key configured")


def _headers() -> dict:
    return {"Authorization": _get_token(), "Content-Type": "application/json"}


def get_all_spaces(team_id: str) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/team/{team_id}/space", headers=_headers())
    resp.raise_for_status()
    return resp.json().get("spaces", [])


def get_all_lists(space_id: str) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/space/{space_id}/folder", headers=_headers())
    resp.raise_for_status()
    folders = resp.json().get("folders", [])

    lists = []
    for folder in folders:
        for lst in folder.get("lists", []):
            lists.append(lst)

    resp = requests.get(f"{BASE_URL}/space/{space_id}/list", headers=_headers())
    resp.raise_for_status()
    lists.extend(resp.json().get("lists", []))

    return lists


def get_all_tasks(list_id: str) -> list[dict]:
    tasks = []
    page = 0

    while True:
        resp = requests.get(
            f"{BASE_URL}/list/{list_id}/task",
            headers=_headers(),
            params={"include_closed": "true", "page": page},
        )
        resp.raise_for_status()
        batch = resp.json().get("tasks", [])
        if not batch:
            break
        tasks.extend(batch)
        page += 1

    return tasks


def get_task_comments(task_id: str) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/task/{task_id}/comment", headers=_headers())
    resp.raise_for_status()
    return resp.json().get("comments", [])


def get_list_member_emails(list_id: str) -> list[str]:
    """Fetch email addresses of all members who have access to a ClickUp list."""
    try:
        resp = requests.get(f"{BASE_URL}/list/{list_id}/member", headers=_headers(), timeout=10)
        resp.raise_for_status()
        members = resp.json().get("members", [])
        emails = [m.get("email", "") for m in members if m.get("email")]
        return emails
    except Exception as e:
        logger.warning(f"Could not fetch members for list {list_id}: {e}")
        return []


def get_space_member_emails(space_id: str) -> list[str]:
    """Fetch email addresses of all members of a ClickUp space (fallback)."""
    try:
        resp = requests.get(f"{BASE_URL}/space/{space_id}/member", headers=_headers(), timeout=10)
        resp.raise_for_status()
        members = resp.json().get("members", [])
        emails = [m.get("email", "") for m in members if m.get("email")]
        return emails
    except Exception as e:
        logger.warning(f"Could not fetch members for space {space_id}: {e}")
        return []


def ingest_task(task: dict, acl: list[str]):
    task_id = task["id"]
    name = task.get("name", "")
    description = task.get("description", "") or ""

    try:
        comments = get_task_comments(task_id)
    except Exception as e:
        logger.warning(f"Failed to fetch comments for task {task_id}: {e}")
        comments = []

    comment_texts = []
    for c in comments:
        commenter = c.get("user", {}).get("username", "unknown")
        text = c.get("comment_text", "")
        if text:
            comment_texts.append(f"{commenter}: {text}")

    # Status, assignees, due date, priority
    status = task.get("status", {}).get("status", "") if isinstance(task.get("status"), dict) else ""
    assignees = [a.get("username", "") for a in task.get("assignees", []) if a.get("username")]
    due_date_ms = task.get("due_date")
    due_date_str = ""
    if due_date_ms:
        import datetime
        try:
            due_date_str = datetime.datetime.utcfromtimestamp(int(due_date_ms) / 1000).strftime("%d/%m/%Y")
        except Exception:
            pass
    priority = task.get("priority", {}).get("priority", "") if isinstance(task.get("priority"), dict) else ""
    list_name = task.get("list", {}).get("name", "") if isinstance(task.get("list"), dict) else ""

    text_parts = [f"Task: {name}"]
    if list_name:
        text_parts.append(f"List: {list_name}")
    if status:
        text_parts.append(f"Status: {status}")
    if assignees:
        text_parts.append(f"Assignees: {', '.join(assignees)}")
    if due_date_str:
        text_parts.append(f"Due date: {due_date_str}")
    if priority:
        text_parts.append(f"Priority: {priority}")
    if description:
        text_parts.append(f"Description: {description}")
    if comment_texts:
        text_parts.append("Comments:\n" + "\n".join(comment_texts))

    full_text = "\n".join(text_parts)

    if not full_text.strip():
        return

    url = task.get("url", f"https://app.clickup.com/t/{task_id}")

    chunk_and_store(
        source="clickup",
        source_id=f"clickup:task:{task_id}",
        text=full_text,
        url=url,
        acl=acl,
        title=name,
    )


def ingest_all_clickup(team_id: str = None):
    if not team_id:
        # Prefer OAuth connection team_id, fall back to env var
        from app.core.token_store import get_connection
        conn = get_connection("clickup")
        team_id = (conn.team_id if conn else None) or settings.CLICKUP_TEAM_ID
    if not team_id:
        logger.error("No ClickUp team ID configured — connect via OAuth or set CLICKUP_TEAM_ID")
        return 0

    total = 0
    spaces = get_all_spaces(team_id)
    logger.info(f"Found {len(spaces)} spaces")

    from app.services.exclusion_service import is_excluded, refresh_cache
    refresh_cache()

    for space in spaces:
        space_id = space["id"]
        space_name = space.get("name", space_id)
        if is_excluded("clickup", space_id):
            logger.info(f"Skipping excluded ClickUp space '{space_name}'")
            continue
        lists = get_all_lists(space_id)
        logger.info(f"Space '{space_name}': {len(lists)} lists")

        # Fetch space-level members as fallback ACL
        space_emails = get_space_member_emails(space_id)

        for lst in lists:
            list_id = lst["id"]
            list_name = lst.get("name", list_id)
            tasks = get_all_tasks(list_id)
            logger.info(f"  List '{list_name}': {len(tasks)} tasks")

            # List members take priority; fall back to space members; fall back to public
            list_emails = get_list_member_emails(list_id)
            acl = list_emails or space_emails or ["public"]
            logger.info(f"  List '{list_name}' ACL: {acl}")

            for task in tasks:
                try:
                    ingest_task(task, acl)
                    total += 1
                except Exception as e:
                    logger.error(f"Failed to ingest task {task.get('id')}: {e}")

    logger.info(f"ClickUp ingestion complete: {total} tasks ingested")
    return total


def register_webhook(team_id: str, endpoint_url: str):
    payload = {
        "endpoint": endpoint_url,
        "events": ["taskCreated", "taskUpdated", "taskCommentPosted"],
    }
    resp = requests.post(
        f"{BASE_URL}/team/{team_id}/webhook",
        headers=_headers(),
        json=payload,
    )
    resp.raise_for_status()
    webhook = resp.json()
    logger.info(f"Registered ClickUp webhook: {webhook.get('id')}")
    return webhook
