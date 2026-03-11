import logging
import requests
from app.core.config import settings
from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)

BASE_URL = "https://api.clickup.com/api/v2"


def _headers() -> dict:
    return {"Authorization": settings.CLICKUP_API_KEY, "Content-Type": "application/json"}


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


def ingest_task(task: dict, space_id: str, list_id: str):
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

    text_parts = [f"Task: {name}"]
    if description:
        text_parts.append(f"Description: {description}")
    if comment_texts:
        text_parts.append("Comments:\n" + "\n".join(comment_texts))

    full_text = "\n".join(text_parts)

    if not full_text.strip():
        return

    url = task.get("url", f"https://app.clickup.com/t/{task_id}")
    acl = [space_id, list_id]

    chunk_and_store(
        source="clickup",
        source_id=f"clickup:task:{task_id}",
        text=full_text,
        url=url,
        acl=acl,
        title=name,
    )


def ingest_all_clickup(team_id: str = None):
    team_id = team_id or settings.CLICKUP_TEAM_ID
    if not team_id:
        logger.error("No ClickUp team ID configured")
        return 0

    total = 0
    spaces = get_all_spaces(team_id)
    logger.info(f"Found {len(spaces)} spaces")

    for space in spaces:
        space_id = space["id"]
        space_name = space.get("name", space_id)
        lists = get_all_lists(space_id)
        logger.info(f"Space '{space_name}': {len(lists)} lists")

        for lst in lists:
            list_id = lst["id"]
            list_name = lst.get("name", list_id)
            tasks = get_all_tasks(list_id)
            logger.info(f"  List '{list_name}': {len(tasks)} tasks")

            for task in tasks:
                try:
                    ingest_task(task, space_id, list_id)
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
