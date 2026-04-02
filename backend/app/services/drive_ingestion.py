import io
import json
import logging
import os

from app.core.config import settings
from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "google_token.json")

# Supported MIME types and their export formats
SUPPORTED_TYPES = {
    "application/vnd.google-apps.document": {
        "export_mime": "text/plain",
        "label": "Google Doc",
    },
    "application/vnd.google-apps.spreadsheet": {
        "export_mime": "text/csv",
        "label": "Google Sheet",
    },
    "application/vnd.google-apps.presentation": {
        "export_mime": "text/plain",
        "label": "Google Slides",
    },
    "application/pdf": {
        "export_mime": None,
        "label": "PDF",
    },
    "text/plain": {
        "export_mime": None,
        "label": "Text file",
    },
    "text/markdown": {
        "export_mime": None,
        "label": "Markdown",
    },
    "text/x-markdown": {
        "export_mime": None,
        "label": "Markdown",
    },
    "text/x-python": {
        "export_mime": None,
        "label": "Python script",
    },
    "application/x-python-code": {
        "export_mime": None,
        "label": "Python script",
    },
    "application/octet-stream": {
        "export_mime": None,
        "label": "Binary/Text file",
    },
}


def _get_credentials():
    """Get Google OAuth credentials, prompting browser login if needed."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    # Preferred for deployed environments (Railway/Render/etc):
    # pass full token JSON via env var to avoid interactive local-server OAuth.
    if settings.GOOGLE_TOKEN_JSON:
        try:
            token_info = json.loads(settings.GOOGLE_TOKEN_JSON)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception as e:
            logger.warning(f"Failed to parse GOOGLE_TOKEN_JSON: {e}")
            creds = None

    # Load saved token if it exists
    if not creds and os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If no valid creds, do browser login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            # In hosted environments (Railway/Render/etc), interactive OAuth is not supported.
            # Require GOOGLE_TOKEN_JSON to avoid binding a local callback server.
            if os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("RAILWAY_PROJECT_ID"):
                raise ValueError(
                    "Missing valid Google token in deployment. Set GOOGLE_TOKEN_JSON "
                    "to a full authorized_user JSON value."
                )

            if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
                raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env")

            client_config = {
                "installed": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:8080"],
                }
            }

            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True, prompt="consent")

        # Save token for next time
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        logger.info(f"Google token saved to {TOKEN_PATH}")

    return creds


def _get_drive_service():
    from googleapiclient.discovery import build

    creds = _get_credentials()
    return build("drive", "v3", credentials=creds)


def _extract_text_from_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)
    except ImportError:
        logger.warning("pypdf not installed — pip install pypdf")
        return ""
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""


def _get_file_text(service, file_info: dict) -> str:
    file_id = file_info["id"]
    mime_type = file_info.get("mimeType", "")
    name = file_info.get("name", "").lower()

    # Special handling for octet-stream: only allow known extensions
    if mime_type == "application/octet-stream":
        if not (name.endswith(".md") or name.endswith(".txt") or name.endswith(".py")):
            return ""

    type_config = SUPPORTED_TYPES.get(mime_type)
    if not type_config:
        return ""

    if type_config["export_mime"]:
        content = (
            service.files()
            .export(fileId=file_id, mimeType=type_config["export_mime"])
            .execute()
        )
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)
    elif mime_type == "application/pdf":
        request = service.files().get_media(fileId=file_id)
        content = request.execute()
        return _extract_text_from_pdf(content)
    else:
        request = service.files().get_media(fileId=file_id)
        content = request.execute()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)


def _get_folder_tree(service, root_ids: list[str]) -> set[str]:
    """Recursively find all subfolder IDs for a list of root folders."""
    all_folders = set(root_ids)
    to_process = list(root_ids)

    while to_process:
        current_id = to_process.pop(0)
        query = f"'{current_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id)",
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                f_id = f["id"]
                if f_id not in all_folders:
                    all_folders.add(f_id)
                    to_process.append(f_id)
            
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
                
    return all_folders


def list_drive_files(
    folder_id: str = None, 
    folder_ids: list[str] = None, 
    max_results: int = 500,
    recursive: bool = True
) -> list[dict]:
    service = _get_drive_service()

    mime_queries = [f"mimeType='{mt}'" for mt in SUPPORTED_TYPES.keys()]
    mime_filter = "(" + " or ".join(mime_queries) + ")"

    # If folder_ids is provided, we'll collect from all of them
    entry_points = folder_ids if folder_ids else ([folder_id] if folder_id else [])
    entry_points = [eid for eid in entry_points if eid]
    
    # If recursive, find the full folder tree
    if recursive and entry_points:
        target_folders = list(_get_folder_tree(service, entry_points))
        logger.info(f"Recursive scan: found {len(target_folders)} folders in tree")
    else:
        target_folders = entry_points if entry_points else [None]
    
    all_results = []
    # If we have many folders, we can chunk them in groups of 10-15 to keep query length safe
    # But for now, let's keep it simple and iterate
    for f_id in target_folders:
        query = mime_filter
        if f_id:
            query = f"'{f_id}' in parents and " + query
        query += " and trashed=false"

        results = []
        page_token = None
        while len(all_results) + len(results) < max_results:
            resp = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink, lastModifyingUser, owners)",
                    pageSize=min(100, max_results - (len(all_results) + len(results))),
                    pageToken=page_token,
                )
                .execute()
            )
            results.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        all_results.extend(results)
        if len(all_results) >= max_results:
            break

    return all_results


def list_drive_folders() -> list[dict]:
    """List all non-trashed folders in the user's Drive."""
    service = _get_drive_service()
    query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
    
    results = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            )
            .execute()
        )
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
            
    return results


def _get_file_permissions(service, file_id: str) -> list[str]:
    """Fetch the real permission list for a Drive file.

    Returns a list of email addresses who have access.
    Falls back to ["public"] if permissions can't be fetched
    or if the file is shared with 'anyone' (link sharing on).
    """
    try:
        resp = service.permissions().list(
            fileId=file_id,
            fields="permissions(emailAddress, type, role)",
        ).execute()

        emails = []
        for p in resp.get("permissions", []):
            # If shared with "anyone" or "domain", treat as public
            if p.get("type") in ("anyone", "domain"):
                return ["public"]
            email = p.get("emailAddress")
            if email:
                emails.append(email)

        return emails if emails else ["public"]
    except Exception as e:
        logger.debug(f"Could not fetch permissions for {file_id}: {e}")
        return ["public"]


def _get_revision_history(service, file_id: str, max_revisions: int = 20) -> list[dict]:
    """Fetch recent revision history for a file."""
    try:
        resp = service.revisions().list(
            fileId=file_id,
            fields="revisions(id, modifiedTime, lastModifyingUser)",
            pageSize=max_revisions,
        ).execute()

        history = []
        for rev in resp.get("revisions", []):
            user = rev.get("lastModifyingUser", {})
            history.append({
                "modified_at": rev.get("modifiedTime", ""),
                "modified_by": user.get("displayName", "Unknown"),
                "email": user.get("emailAddress", ""),
            })
        return history
    except Exception as e:
        logger.debug(f"Could not fetch revisions for {file_id}: {e}")
        return []


def _build_edit_history_text(file_info: dict, revision_history: list[dict]) -> str:
    """Build a human-readable edit history summary to embed alongside content."""
    parts = []

    # Owner
    owners = file_info.get("owners", [])
    if owners:
        owner_names = [f"{o.get('displayName', '?')} ({o.get('emailAddress', '?')})" for o in owners]
        parts.append(f"Document owner: {', '.join(owner_names)}")

    # Last editor
    last_editor = file_info.get("lastModifyingUser", {})
    if last_editor:
        modified_time = file_info.get("modifiedTime", "")
        parts.append(
            f"Last edited by: {last_editor.get('displayName', '?')} "
            f"({last_editor.get('emailAddress', '?')}) on {modified_time}"
        )

    # Revision history
    if revision_history:
        parts.append(f"Edit history ({len(revision_history)} revisions):")
        for rev in revision_history[-10:]:  # Last 10 revisions
            parts.append(f"  - {rev['modified_at']}: edited by {rev['modified_by']} ({rev['email']})")

    return "\n".join(parts)


def ingest_drive_file(file_info: dict) -> bool:
    service = _get_drive_service()
    file_id = file_info["id"]
    title = file_info.get("name", f"Drive file {file_id}")
    url = file_info.get("webViewLink", f"https://drive.google.com/file/d/{file_id}")

    text = _get_file_text(service, file_info)
    if not text or len(text.strip()) < 20:
        logger.debug(f"Skipping empty/short file: {title}")
        return False

    # Fetch revision history
    revision_history = _get_revision_history(service, file_id)

    # Build edit history metadata
    edit_history_text = _build_edit_history_text(file_info, revision_history)

    # Prepend edit history to the document text so it's searchable
    full_text = f"[Document Metadata]\n{edit_history_text}\n\n[Document Content]\n{text}"

    # Build structured metadata for chunk payload
    last_editor = file_info.get("lastModifyingUser", {})
    owners = file_info.get("owners", [])

    metadata = {
        "owner": owners[0].get("displayName", "") if owners else "",
        "owner_email": owners[0].get("emailAddress", "") if owners else "",
        "last_edited_by": last_editor.get("displayName", ""),
        "last_edited_by_email": last_editor.get("emailAddress", ""),
        "last_edited_at": file_info.get("modifiedTime", ""),
        "created_at": file_info.get("createdTime", ""),
        "revision_count": len(revision_history),
        "revision_history": revision_history[-10:],
    }

    # Fetch real permissions from Drive API
    acl = _get_file_permissions(service, file_id)

    chunk_and_store(
        source="drive",
        source_id=f"drive:{file_id}",
        text=full_text,
        url=url,
        acl=acl,
        title=title,
        extra_metadata=metadata,
    )
    return True


def ingest_all_drive(folder_id: str = None, folder_ids: list[str] = None) -> int:
    from app.core.database import SessionLocal
    from app.models import Document

    # Priority: 
    # 1. folder_ids (list passed from tasks or API)
    # 2. folder_id (single string passed from API)
    # 3. settings.google_drive_folder_ids (from .env)
    
    target_ids = None
    if folder_ids is not None:
        target_ids = folder_ids
    elif folder_id is not None:
        target_ids = [folder_id]
    else:
        target_ids = settings.google_drive_folder_ids

    if target_ids:
        logger.info(f"Scanning for files in folders: {target_ids}")
        files = list_drive_files(folder_ids=target_ids)
    else:
        logger.info("Scanning all Drive files (no folder restriction)")
        files = list_drive_files()

    logger.info(f"Found {len(files)} Drive files to check")

    # Build a lookup of existing documents by source_id to skip unchanged files
    db = SessionLocal()
    try:
        existing_docs = {
            doc.source_id: doc.updated_at
            for doc in db.query(Document.source_id, Document.updated_at)
            .filter(Document.source.startswith("drive"))
            .all()
        }
    finally:
        db.close()

    count = 0
    skipped = 0
    for f in files:
        file_id = f["id"]
        source_id = f"drive:{file_id}"
        modified_time = f.get("modifiedTime", "")

        # Skip if we already have this file and it hasn't been modified
        if source_id in existing_docs and existing_docs[source_id]:
            from datetime import datetime, timezone
            try:
                drive_modified = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
                our_updated = existing_docs[source_id].replace(tzinfo=timezone.utc)
                if drive_modified <= our_updated:
                    skipped += 1
                    continue
            except (ValueError, AttributeError):
                pass  # If we can't parse the date, re-ingest to be safe

        try:
            if ingest_drive_file(f):
                count += 1
                logger.info(f"  Ingested: {f.get('name')}")
        except Exception as e:
            logger.error(f"Failed to ingest Drive file {f.get('name', f.get('id'))}: {e}")

    logger.info(f"Drive sync complete: {count} new/updated, {skipped} unchanged")
    return count


def is_authenticated() -> bool:
    """Check if we already have a valid Google token."""
    if not os.path.exists(TOKEN_PATH):
        return False
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        return creds.valid or (creds.expired and creds.refresh_token)
    except Exception:
        return False
