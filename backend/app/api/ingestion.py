from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import logging
import io
from typing import Optional, List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


class TriggerRequest(BaseModel):
    source: str = "all"
    team_id: str = ""
    folder_ids: Optional[List[str]] = None


@router.post("/trigger")
def trigger_ingestion(req: TriggerRequest):
    from app.services.settings_service import is_source_enabled
    results = {}

    try:
        if req.source in ("slack", "all"):
            if not is_source_enabled("slack"):
                results["slack"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.slack_ingestion import backfill_all_channels
                try:
                    count = backfill_all_channels()
                    results["slack"] = {"status": "ok", "messages_ingested": count}
                except Exception as e:
                    results["slack"] = {"status": "error", "detail": str(e)}

        if req.source in ("clickup", "all"):
            if not is_source_enabled("clickup"):
                results["clickup"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.clickup_ingestion import ingest_all_clickup
                try:
                    count = ingest_all_clickup(req.team_id or None)
                    results["clickup"] = {"status": "ok", "tasks_ingested": count}
                except Exception as e:
                    results["clickup"] = {"status": "error", "detail": str(e)}

        if req.source in ("meet", "all"):
            if not is_source_enabled("meet"):
                results["meet"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.meet_ingestion import ingest_drive_transcripts
                try:
                    count = ingest_drive_transcripts()
                    results["meet"] = {"status": "ok", "transcripts_ingested": count}
                except Exception as e:
                    results["meet"] = {"status": "error", "detail": str(e)}

        if req.source in ("drive", "all"):
            if not is_source_enabled("drive"):
                results["drive"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.drive_ingestion import ingest_all_drive
                from app.models import GlobalSettings
                from app.core.database import SessionLocal
                try:
                    folder_ids = req.folder_ids
                    # If no folder_ids in the request, read from saved GlobalSettings
                    if not folder_ids:
                        db = SessionLocal()
                        try:
                            gs = db.query(GlobalSettings).filter(GlobalSettings.id == "default").first()
                            if gs and gs.google_drive_folder_ids:
                                folder_ids = gs.google_drive_folder_ids
                        finally:
                            db.close()

                    count = ingest_all_drive(folder_ids=folder_ids if folder_ids else None)
                    results["drive"] = {"status": "ok", "files_ingested": count}
                except Exception as e:
                    results["drive"] = {"status": "error", "detail": str(e)}

        if req.source in ("calendar", "all"):
            if not is_source_enabled("calendar"):
                results["calendar"] = {"status": "skipped", "detail": "Source disabled in settings"}
            else:
                from app.services.calendar_sync import sync_calendar
                try:
                    count = sync_calendar()
                    results["calendar"] = {"status": "ok", "events_synced": count}
                except Exception as e:
                    results["calendar"] = {"status": "error", "detail": str(e)}

        if req.source not in ("slack", "clickup", "meet", "drive", "calendar", "all"):
            raise HTTPException(status_code=400, detail=f"Unknown source: {req.source}")

        return {"status": "triggered", "results": results}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/drive/folders")
def list_folders():
    """List available Google Drive folders for selection."""
    from app.services.drive_ingestion import list_drive_folders

    try:
        folders = list_drive_folders()
        return {"status": "ok", "folders": folders}
    except Exception as e:
        logger.error(f"Failed to list Drive folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_email: str = Form(...),
    scope: str = Form("private"),          # public | group | private
    group_id: str = Form(""),              # required when scope=group
    title: str = Form(""),
    shared_with: str = Form(""),           # comma-separated emails for private shares
):
    """
    Upload a document with explicit scope.

    - scope=public   → visible to everyone (admin only)
    - scope=group    → visible to all members of group_id
    - scope=private  → visible only to the uploader (+ any shared_with emails)
    """
    from app.core.acl import build_acl, get_user_role
    from app.services.chunker import chunk_and_store

    # Validate scope
    if scope not in ("public", "group", "private"):
        raise HTTPException(status_code=400, detail="scope must be public, group, or private")

    # Only admins can set public scope
    role = get_user_role(user_email)
    if scope == "public" and role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can upload public documents")

    # Group scope validation
    if scope == "group":
        if not group_id:
            raise HTTPException(status_code=400, detail="group_id is required for group scope")
        # group_admin or admin can upload for a group
        if role not in ("admin", "group_admin"):
            raise HTTPException(status_code=403, detail="Only admins or group admins can upload group documents")

    extra_emails = [e.strip() for e in shared_with.split(",") if e.strip()] if shared_with else None
    acl = build_acl(scope, user_email, group_id=group_id or None, extra_emails=extra_emails)

    # Read file content
    content_bytes = await file.read()
    filename = title or file.filename or "uploaded_document"
    content_type = file.content_type or ""

    # Decode text
    try:
        if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
            # Basic PDF text extraction
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content_bytes))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except ImportError:
                text = content_bytes.decode("utf-8", errors="ignore")
        else:
            text = content_bytes.decode("utf-8", errors="ignore")
    except Exception:
        text = content_bytes.decode("latin-1", errors="ignore")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file")

    source_id = f"upload:{user_email}:{filename}"

    chunk_and_store(
        source="upload",
        source_id=source_id,
        text=text,
        url="",
        acl=acl,
        title=filename,
        extra_metadata={
            "uploaded_by": user_email,
            "scope": scope,
            "group_id": group_id or None,
            "filename": filename,
        },
        chunk_type="full_text",
    )

    logger.info(f"Uploaded '{filename}' by {user_email} with scope={scope}, acl={acl}")
    return {
        "status": "ok",
        "filename": filename,
        "scope": scope,
        "acl": acl,
        "uploader": user_email,
    }
