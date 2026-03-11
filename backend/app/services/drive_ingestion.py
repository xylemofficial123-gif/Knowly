import logging
import io

from app.core.config import settings
from app.services.chunker import chunk_and_store

logger = logging.getLogger(__name__)

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
        "export_mime": None,  # download directly
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
}


def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes. Falls back to empty string if PyPDF not available."""
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
        logger.warning("pypdf not installed — PDF text extraction unavailable. pip install pypdf")
        return ""
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""


def _get_file_text(service, file_info: dict) -> str:
    """Download or export a Drive file as text."""
    file_id = file_info["id"]
    mime_type = file_info.get("mimeType", "")

    type_config = SUPPORTED_TYPES.get(mime_type)
    if not type_config:
        return ""

    if type_config["export_mime"]:
        # Google Workspace file — export
        content = (
            service.files()
            .export(fileId=file_id, mimeType=type_config["export_mime"])
            .execute()
        )
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)
    elif mime_type == "application/pdf":
        # Binary PDF — download and extract
        request = service.files().get_media(fileId=file_id)
        content = request.execute()
        return _extract_text_from_pdf(content)
    else:
        # Plain text file — download
        request = service.files().get_media(fileId=file_id)
        content = request.execute()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)


def _get_acl_from_permissions(service, file_id: str) -> list[str]:
    """Get email-based ACL from file permissions."""
    try:
        perms = service.permissions().list(
            fileId=file_id, fields="permissions(emailAddress, role)"
        ).execute()
        emails = []
        for p in perms.get("permissions", []):
            email = p.get("emailAddress")
            if email:
                emails.append(email)
        return emails if emails else ["public"]
    except Exception:
        return ["public"]


def list_drive_files(folder_id: str = None, max_results: int = 500) -> list[dict]:
    """List indexable files from Drive, optionally within a folder."""
    service = _get_drive_service()

    mime_queries = [f"mimeType='{mt}'" for mt in SUPPORTED_TYPES.keys()]
    mime_filter = "(" + " or ".join(mime_queries) + ")"

    query = mime_filter
    if folder_id:
        query = f"'{folder_id}' in parents and " + query

    # Exclude trashed files
    query += " and trashed=false"

    results = []
    page_token = None

    while len(results) < max_results:
        resp = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, webViewLink)",
                pageSize=min(100, max_results - len(results)),
                pageToken=page_token,
            )
            .execute()
        )
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results


def ingest_drive_file(file_info: dict) -> bool:
    """Ingest a single Drive file into the knowledge base."""
    service = _get_drive_service()
    file_id = file_info["id"]
    title = file_info.get("name", f"Drive file {file_id}")
    url = file_info.get("webViewLink", f"https://drive.google.com/file/d/{file_id}")

    text = _get_file_text(service, file_info)
    if not text or len(text.strip()) < 20:
        logger.debug(f"Skipping empty/short file: {title}")
        return False

    acl = _get_acl_from_permissions(service, file_id)

    chunk_and_store(
        source="drive",
        source_id=f"drive:{file_id}",
        text=text,
        url=url,
        acl=acl,
        title=title,
    )
    return True


def ingest_all_drive(folder_id: str = None) -> int:
    """Ingest all supported files from Google Drive."""
    files = list_drive_files(folder_id=folder_id)
    logger.info(f"Found {len(files)} Drive files to ingest")

    count = 0
    for f in files:
        try:
            if ingest_drive_file(f):
                count += 1
        except Exception as e:
            logger.error(f"Failed to ingest Drive file {f.get('name', f.get('id'))}: {e}")

    logger.info(f"Drive ingestion complete: {count} files ingested")
    return count
